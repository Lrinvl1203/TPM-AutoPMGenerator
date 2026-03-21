"""
PM 분류 엔진 (Gemini API)

OCR로 추출한 텍스트를 Gemini API에 전달하여
PM(예방보전) 항목을 구조화된 JSON으로 추출합니다.
"""

import json
import logging
import os
import time
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv

from app.config.logger import setup_logger
from app.config.settings import GEMINI_CHUNK_SIZE, GEMINI_MAX_RETRIES, GEMINI_MODEL
from app.models.schemas import PMItem, PMItemForGemini, OCRPageResult

load_dotenv()

logger = setup_logger(__name__)

# 영역 분류 설정 로드
_config_path = Path(__file__).parent.parent / "config" / "area_taxonomy.json"
with open(_config_path, "r", encoding="utf-8") as f:
    TAXONOMY_CONFIG = json.load(f)

# PM 관련 키워드 (사전 필터링용)
PM_KEYWORDS = TAXONOMY_CONFIG.get("PM_판별_키워드", [])


class PMClassifier:
    """Gemini API 기반 PM 항목 분류기"""

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        max_retries: Optional[int] = None,
    ):
        """
        Args:
            api_key: Gemini API 키 (없으면 환경변수 GEMINI_API_KEY 사용)
            model: Gemini 모델명 (기본: gemini-2.5-flash)
            max_retries: API 호출 최대 재시도 횟수
        """
        self.api_key = api_key or os.getenv("GEMINI_API_KEY", "")
        self.model = model or GEMINI_MODEL
        self.max_retries = max_retries if max_retries is not None else GEMINI_MAX_RETRIES
        self._client = None

    @property
    def client(self):
        """Gemini 클라이언트 (지연 초기화)"""
        if self._client is None:
            from google import genai
            self._client = genai.Client(api_key=self.api_key)
            logger.info(f"Gemini 클라이언트 초기화 완료 (모델: {self.model})")
        return self._client

    def classify_pm_items(
        self,
        ocr_results: list[OCRPageResult],
        equipment_name: str = "",
        progress_callback: Optional[callable] = None,
    ) -> list[PMItem]:
        """
        OCR 결과에서 PM 항목을 추출하고 분류

        Args:
            ocr_results: OCR 페이지별 결과 리스트
            equipment_name: 설비명 (프롬프트 컨텍스트용)
            progress_callback: 진행률 콜백 fn(current_chunk, total_chunks)

        Returns:
            PMItem 리스트
        """
        # 1. OCR 결과를 텍스트 청크로 변환
        chunks = self._build_chunks(ocr_results)
        logger.info(f"총 {len(chunks)}개 청크 생성 (사전 필터링 후)")

        if not chunks:
            logger.warning("PM 관련 텍스트를 찾지 못했습니다.")
            return []

        # 2. 각 청크를 Gemini API에 전송
        all_items: list[PMItem] = []
        system_prompt = self._build_system_prompt(equipment_name)

        for i, chunk in enumerate(chunks):
            logger.info(f"청크 {i + 1}/{len(chunks)} 처리 중...")
            items = self._classify_chunk(chunk, system_prompt)
            all_items.extend(items)

            if progress_callback:
                progress_callback(i + 1, len(chunks))

        logger.info(f"총 {len(all_items)}개 PM 항목 추출 완료")
        return all_items

    def _build_chunks(
        self,
        ocr_results: list[OCRPageResult],
        pages_per_chunk: Optional[int] = None,
    ) -> list[dict]:
        """
        OCR 결과를 청크로 분할 (사전 키워드 필터링 포함)

        Args:
            ocr_results: 페이지별 OCR 결과
            pages_per_chunk: 청크당 페이지 수

        Returns:
            청크 리스트 [{"text": "...", "pages": [1,2,3]}, ...]
        """
        chunks: list[dict] = []
        current_text = ""
        current_pages: list[int] = []
        actual_pages_per_chunk = pages_per_chunk or GEMINI_CHUNK_SIZE

        for page_result in ocr_results:
            # 페이지 텍스트 합치기
            page_text = "\n".join(block.text for block in page_result.blocks if block.text)

            # 사전 필터링: PM 관련 키워드가 최소 1개 이상 있는 페이지만 포함
            has_pm_keyword = any(kw in page_text for kw in PM_KEYWORDS)
            if not has_pm_keyword and page_text:
                logger.debug(f"페이지 {page_result.page}: PM 키워드 없음 — 건너뜀")
                continue

            current_text += f"\n\n--- 페이지 {page_result.page} ---\n{page_text}"
            current_pages.append(page_result.page)

            # 청크 크기 도달 시 분할
            if len(current_pages) >= actual_pages_per_chunk:
                chunks.append({
                    "text": current_text.strip(),
                    "pages": current_pages.copy(),
                })
                # 오버랩: 마지막 페이지 텍스트 일부를 다음 청크에 포함
                current_text = f"\n--- 페이지 {page_result.page} (계속) ---\n{page_text[-500:]}" if len(page_text) > 500 else ""
                current_pages = []

        # 마지막 청크
        if current_text.strip():
            chunks.append({
                "text": current_text.strip(),
                "pages": current_pages,
            })

        return chunks

    def _build_system_prompt(self, equipment_name: str = "") -> str:
        """시스템 프롬프트 생성"""
        equipment_context = f"현재 분석 대상 설비: {equipment_name}\n" if equipment_name else ""

        # 영역 분류 정보를 taxonomy에서 동적 생성
        area_info = ""
        for area_name, area_data in TAXONOMY_CONFIG.get("영역_분류", {}).items():
            keywords = ", ".join(area_data.get("키워드", []))
            if keywords:
                area_info += f"    - {area_name}: {keywords}\n"

        return f"""당신은 제조업 설비 유지보수 전문가입니다.
주어진 설비 매뉴얼 텍스트에서 PM(예방보전, Preventive Maintenance) 관련 항목을 추출합니다.
{equipment_context}
PM 항목 판별 기준:
- 정기 점검, 교체, 청소, 측정, 조정, 윤활 등의 유지보수 행위
- "~주기로", "매~", "~마다", "~개월", "정기적으로" 등의 주기 표현
- 점검 항목 표(테이블)의 내용

주기 분류 기준:
- 일(Daily): 매일, 매 근무 시작, 8시간마다, 가동 전 점검
- 월(Monthly): 매월, 1개월, 30일마다
- 분기(Quarterly): 3개월, 분기별, 1/4년
- 반기(Semi-annual): 6개월, 반년, 2/4분기
- 년(Annual): 12개월, 매년, 연간, 오버홀

영역(area) 분류:
{area_info}    - 기타: 위 분류에 해당하지 않는 항목

반드시 다음 JSON 배열 형식으로만 응답하세요. PM 항목이 없으면 빈 배열 []을 반환하세요.
다른 텍스트 없이 JSON만 출력하세요.
"""

    def _classify_chunk(self, chunk: dict, system_prompt: str) -> list[PMItem]:
        """
        단일 청크를 Gemini API로 분류

        재시도 로직 포함 (지수 백오프)
        """
        from google.genai import types

        user_prompt = f"다음 설비 매뉴얼 텍스트에서 PM 항목을 추출하세요:\n\n{chunk['text']}"

        for attempt in range(self.max_retries):
            try:
                response = self.client.models.generate_content(
                    model=self.model,
                    contents=user_prompt,
                    config=types.GenerateContentConfig(
                        response_mime_type="application/json",
                        response_schema=list[PMItemForGemini],
                        system_instruction=system_prompt,
                        temperature=0.1,  # 낮은 temperature로 일관성 보장
                    ),
                )

                # 응답 파싱
                raw_items = json.loads(response.text)
                pm_items: list[PMItem] = []

                for raw in raw_items:
                    try:
                        gemini_item = PMItemForGemini(**raw)
                        pm_item = gemini_item.to_pm_item()

                        # 소스 페이지 보정: 청크의 페이지 범위 내에서 설정
                        if pm_item.source_page is None and chunk["pages"]:
                            pm_item.source_page = chunk["pages"][0]

                        pm_items.append(pm_item)
                    except Exception as e:
                        logger.warning(f"항목 파싱 실패: {e} — 원본: {raw}")

                logger.info(f"청크에서 {len(pm_items)}개 PM 항목 추출 (페이지: {chunk['pages']})")
                return pm_items

            except json.JSONDecodeError as e:
                logger.warning(f"JSON 파싱 실패 (시도 {attempt + 1}/{self.max_retries}): {e}")
            except Exception as e:
                logger.warning(f"API 호출 실패 (시도 {attempt + 1}/{self.max_retries}): {e}")

            # 지수 백오프
            if attempt < self.max_retries - 1:
                wait_time = 2 ** attempt
                logger.info(f"{wait_time}초 후 재시도...")
                time.sleep(wait_time)

        logger.error(f"청크 처리 실패 (최대 재시도 초과): 페이지 {chunk['pages']}")
        return []


