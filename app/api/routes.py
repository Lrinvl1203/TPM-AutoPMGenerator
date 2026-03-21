"""
FastAPI 라우터 (MVP-2)

웹 UI(Streamlit) 등에서 호출할 수 있는 백엔드 API 엔드포인트입니다.
PDF 파일 업로드 처리를 담당하고, 핵심 파이프라인(PDF->OCR->분류->Excel)을 백그라운드로 실행합니다.
"""

import logging
import os
import time
import uuid
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, File, Form, UploadFile, HTTPException
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel

from app.core.pdf_processor import PDFProcessor
from app.core.ocr_engine import OCREngine
from app.core.pm_classifier import PMClassifier
from app.core.rule_classifier import RuleClassifier
from app.core.checklist_builder import ChecklistBuilder
from app.core.export_engine import ExportEngine

logger = logging.getLogger(__name__)
router = APIRouter()

# 전역 작업 상태 관리 (단순화를 위해 메모리 딕셔너리 사용, 실무에선 Redis/DB 권장)
jobs = {}

# 기본 디렉토리 설정
UPLOAD_DIR = os.getenv("UPLOAD_DIR", "./uploads")
OUTPUT_DIR = os.getenv("OUTPUT_DIR", "./outputs")
os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(OUTPUT_DIR, exist_ok=True)


class JobStatusResponse(BaseModel):
    job_id: str
    status: str
    progress: int
    message: str
    result_url: Optional[str] = None


@router.post("/upload", response_model=JobStatusResponse)
async def upload_pdf(
    file: UploadFile = File(...),
    equipment_name: str = Form(...),
    use_offline: bool = Form(False),
):
    """
    PDF 매뉴얼을 업로드하여 PM 체크리스트 추출 작업을 시작합니다.
    """
    if not file.filename.lower().endswith('.pdf'):
        raise HTTPException(status_code=400, detail="PDF 파일만 업로드 가능합니다.")

    job_id = str(uuid.uuid4())
    file_path = os.path.join(UPLOAD_DIR, f"{job_id}_{file.filename}")

    # 파일 저장
    content = await file.read()
    with open(file_path, "wb") as f:
        f.write(content)

    # 작업 상태 초기화
    jobs[job_id] = {
        "status": "pending",
        "progress": 0,
        "message": "작업 시작 대기 중...",
        "file_path": file_path,
        "filename": file.filename,
        "equipment_name": equipment_name,
        "use_offline": use_offline,
        "result_path": None,
    }

    # TODO: 실제 프로덕션에서는 Celery나 BackgroundTasks를 사용하여 비동기로 실행해야 합니다.
    # 여기서는 MVP 테스트를 위해 Fast API BackgroundTasks를 생략하고
    # Streamlit이 동기적으로 기다리는 방식으로 간략화하거나, 상태 폴링을 구현합니다.
    # MVP-2의 단일 서버 구동을 위해 단순 동기 처리 함수를 직접 호출하는 별도 엔드포인트를 노출할 수도 있습니다.

    return JobStatusResponse(
        job_id=job_id,
        status=jobs[job_id]["status"],
        progress=jobs[job_id]["progress"],
        message=jobs[job_id]["message"],
    )


@router.get("/status/{job_id}", response_model=JobStatusResponse)
async def get_job_status(job_id: str):
    """작업 진행 상태를 조회합니다."""
    if job_id not in jobs:
        raise HTTPException(status_code=404, detail="작업을 찾을 수 없습니다.")

    job = jobs[job_id]
    return JobStatusResponse(
        job_id=job_id,
        status=job["status"],
        progress=job["progress"],
        message=job["message"],
        result_url=f"/api/download/{job_id}" if job["result_path"] else None,
    )


@router.get("/download/{job_id}")
async def download_result(job_id: str):
    """생성된 Excel 체크리스트를 다운로드합니다."""
    if job_id not in jobs:
        raise HTTPException(status_code=404, detail="작업을 찾을 수 없습니다.")

    job = jobs[job_id]
    if job["status"] != "completed" or not job["result_path"]:
        raise HTTPException(status_code=400, detail="작업이 아직 완료되지 않았거나 결과가 없습니다.")

    # 공백과 특수문자가 포함된 파일명을 안전하게 처리
    safe_filename = Path(job["result_path"]).name
    return FileResponse(
        path=job["result_path"],
        filename=safe_filename,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )

# MVP용 동기식 처리 엔드포인트 (콜백을 통해 UI에 상태 반영이 어려우므로, 
# Streamlit에서 직접 모듈을 호출하는 편이 더 직관적일 수 있습니다. 
# 여기서는 백엔드 분리 시 사용할 API 스펙만 정의해 둡니다.)
