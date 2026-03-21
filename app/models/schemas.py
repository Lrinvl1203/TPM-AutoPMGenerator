"""
PM Checklist Automator — 데이터 모델 정의

Pydantic 기반 데이터 모델. Gemini API Structured Output 스키마로도 사용됩니다.
"""

import uuid
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class PMPeriod(str, Enum):
    """PM 점검 주기"""
    DAILY = "일"
    MONTHLY = "월"
    QUARTERLY = "분기"
    SEMI_ANNUAL = "반기"
    ANNUAL = "년"


# 주기 정렬 우선순위 (짧은 주기 → 긴 주기)
PERIOD_ORDER: dict[PMPeriod, int] = {
    PMPeriod.DAILY: 0,
    PMPeriod.MONTHLY: 1,
    PMPeriod.QUARTERLY: 2,
    PMPeriod.SEMI_ANNUAL: 3,
    PMPeriod.ANNUAL: 4,
}


class PMItem(BaseModel):
    """
    PM(예방보전) 항목 모델

    Gemini API의 response_schema로 직접 사용됩니다.
    """
    item_id: str = Field(
        default_factory=lambda: str(uuid.uuid4()),
        description="고유 식별자 (UUID4, 자동 생성)"
    )
    item_name: str = Field(
        ...,
        description="PM 점검 항목명 (예: 오일레벨 확인, 필터 청소)"
    )
    period: PMPeriod = Field(
        ...,
        description="점검 주기: 일/월/분기/반기/년"
    )
    equipment_part: str = Field(
        ...,
        description="설비 부위 (예: 주축, 오일탱크, 냉각팬, 볼스크류)"
    )
    area: str = Field(
        ...,
        description="설비 영역 (예: 기계계통, 전기계통, 유압계통, 공압계통, 냉각계통, 기타)"
    )
    method: str = Field(
        ...,
        description="점검 방법 (예: 육안점검, 측정, 교체, 청소, 윤활)"
    )
    standard_value: Optional[str] = Field(
        default=None,
        description="기준값 또는 합격 기준 (예: 5~7 kgf/cm², NAS 7등급 이하)"
    )
    source_page: Optional[int] = Field(
        default=None,
        description="원본 PDF 페이지 번호"
    )
    confidence: float = Field(
        default=1.0,
        ge=0.0,
        le=1.0,
        description="AI 추출 신뢰도 (0.0~1.0)"
    )
    note: Optional[str] = Field(
        default=None,
        description="특이사항 및 추가 설명"
    )


class PMItemForGemini(BaseModel):
    """
    Gemini API Structured Output 전용 스키마

    item_id를 제외한 PMItem (Gemini가 생성할 필요 없는 필드 제거)
    """
    item_name: str = Field(
        ...,
        description="PM 점검 항목명"
    )
    period: str = Field(
        ...,
        description="점검 주기: 일, 월, 분기, 반기, 년 중 하나"
    )
    equipment_part: str = Field(
        ...,
        description="설비 부위명"
    )
    area: str = Field(
        ...,
        description="설비 영역명"
    )
    method: str = Field(
        ...,
        description="점검 방법"
    )
    standard_value: Optional[str] = Field(
        default=None,
        description="기준값 또는 null"
    )
    source_page: Optional[int] = Field(
        default=None,
        description="원본 PDF 페이지 번호"
    )
    confidence: float = Field(
        default=0.9,
        description="추출 신뢰도 0.0~1.0"
    )
    note: Optional[str] = Field(
        default=None,
        description="특이사항 또는 null"
    )

    def to_pm_item(self) -> PMItem:
        """PMItemForGemini → PMItem 변환"""
        # period 문자열을 enum으로 매핑
        period_map = {
            "일": PMPeriod.DAILY,
            "월": PMPeriod.MONTHLY,
            "분기": PMPeriod.QUARTERLY,
            "반기": PMPeriod.SEMI_ANNUAL,
            "년": PMPeriod.ANNUAL,
        }
        return PMItem(
            item_name=self.item_name,
            period=period_map.get(self.period, PMPeriod.DAILY),
            equipment_part=self.equipment_part,
            area=self.area,
            method=self.method,
            standard_value=self.standard_value,
            source_page=self.source_page,
            confidence=self.confidence,
            note=self.note,
        )


class ProcessingStatus(BaseModel):
    """매뉴얼 처리 상태"""
    status: str = Field(
        default="pending",
        description="처리 상태: pending|processing|completed|failed"
    )
    progress: int = Field(
        default=0,
        ge=0,
        le=100,
        description="진행률 (0~100)"
    )
    message: str = Field(
        default="대기 중",
        description="현재 처리 단계 설명"
    )
    equipment_name: str = Field(
        default="",
        description="설비명"
    )
    pm_items: list[PMItem] = Field(
        default_factory=list,
        description="추출된 PM 항목 목록"
    )
    error: Optional[str] = Field(
        default=None,
        description="오류 메시지"
    )


class OCRBlock(BaseModel):
    """OCR 인식 블록"""
    text: str = Field(..., description="인식된 텍스트")
    confidence: float = Field(default=1.0, description="인식 신뢰도")
    bbox: Optional[list] = Field(default=None, description="바운딩 박스 좌표")
    low_confidence: bool = Field(default=False, description="낮은 신뢰도 플래그")


class OCRPageResult(BaseModel):
    """페이지별 OCR 결과"""
    page: int = Field(..., description="페이지 번호")
    blocks: list[OCRBlock] = Field(default_factory=list, description="텍스트 블록 목록")
    has_text: bool = Field(default=True, description="텍스트 레이어 존재 여부")


class TableResult(BaseModel):
    """표 인식 결과"""
    rows: list[list[str]] = Field(default_factory=list, description="표 행 데이터")
    page: int = Field(..., description="페이지 번호")
