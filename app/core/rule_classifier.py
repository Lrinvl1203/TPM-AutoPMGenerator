"""
규칙 기반 PM 분류기 (Fallback)

Gemini API 없이 정규식 + 키워드 매칭으로 PM 항목을 추출합니다.
오프라인 환경이나 API 실패 시 대안으로 사용합니다.
정확도는 AI 분류기보다 낮지만 기본 추출을 보장합니다.
"""

import json
import logging
import re
from pathlib import Path
from typing import Optional

from app.config.logger import setup_logger
from app.config.settings import RULE_CONFIDENCE_SCORE, RULE_TABLE_CONFIDENCE_SCORE
from app.models.schemas import PMItem, PMPeriod, OCRPageResult

logger = setup_logger(__name__)

# 영역 분류 설정 로드
_config_path = Path(__file__).parent.parent / "config" / "area_taxonomy.json"
with open(_config_path, "r", encoding="utf-8") as f:
    TAXONOMY_CONFIG = json.load(f)


class RuleClassifier:
    """규칙 기반 PM 항목 분류기"""

    def __init__(self):
        """키워드 사전 초기화"""
        # 주기 판별 키워드
        config_periods = TAXONOMY_CONFIG.get("주기_키워드", {})
        self.period_keywords: dict[PMPeriod, list[str]] = {
            PMPeriod.DAILY: config_periods.get("일", []),
            PMPeriod.MONTHLY: config_periods.get("월", []),
            PMPeriod.QUARTERLY: config_periods.get("분기", []),
            PMPeriod.SEMI_ANNUAL: config_periods.get("반기", []),
            PMPeriod.ANNUAL: config_periods.get("년", []),
        }

        # 영역 분류 키워드
        self.area_keywords: dict[str, list[str]] = {}
        for area_name, area_data in TAXONOMY_CONFIG.get("영역_분류", {}).items():
            self.area_keywords[area_name] = area_data.get("키워드", [])

        # PM 판별 키워드
        self.pm_keywords = TAXONOMY_CONFIG.get("PM_판별_키워드", [])

        # 점검 방법 패턴
        self.method_patterns = {
            "육안점검": ["육안", "눈으로", "확인", "외관"],
            "측정": ["측정", "게이지", "미터", "수치", "온도", "압력", "농도"],
            "교체": ["교체", "교환", "바꾸", "신품"],
            "청소": ["청소", "세척", "클리닝", "제거", "닦"],
            "윤활": ["윤활", "급유", "그리스", "오일"],
            "조정": ["조정", "세팅", "설정", "보정", "교정"],
            "작동점검": ["작동", "동작", "기능", "테스트"],
            "보충": ["보충", "충전", "추가", "보급"],
        }

    def classify_pm_items(
        self,
        ocr_results: list[OCRPageResult],
        equipment_name: str = "",
        progress_callback: Optional[callable] = None,
    ) -> list[PMItem]:
        """
        OCR 결과에서 규칙 기반으로 PM 항목 추출

        Args:
            ocr_results: 페이지별 OCR 결과
            equipment_name: 설비명 (미사용, API 호환성 유지)
            progress_callback: 진행률 콜백

        Returns:
            PMItem 리스트
        """
        all_items: list[PMItem] = []

        for i, page_result in enumerate(ocr_results):
            page_text = "\n".join(block.text for block in page_result.blocks)
            items = self._extract_from_page(page_text, page_result.page)
            all_items.extend(items)

            if progress_callback:
                progress_callback(i + 1, len(ocr_results))

        # 중복 제거
        seen_names: set[str] = set()
        unique_items: list[PMItem] = []
        for item in all_items:
            key = f"{item.item_name}_{item.period.value}"
            if key not in seen_names:
                seen_names.add(key)
                unique_items.append(item)

        logger.info(f"규칙 기반 분류: {len(unique_items)}개 PM 항목 추출 ({len(all_items) - len(unique_items)}개 중복 제거)")
        return unique_items

    def _extract_from_page(self, text: str, page_num: int) -> list[PMItem]:
        """단일 페이지에서 PM 항목 추출"""
        items: list[PMItem] = []

        # 테이블 행 패턴 매칭 (|로 구분된 행)
        table_items = self._extract_from_table_text(text, page_num)
        items.extend(table_items)

        # 리스트/문장 패턴 매칭
        line_items = self._extract_from_lines(text, page_num)
        items.extend(line_items)

        return items

    def _extract_from_table_text(self, text: str, page_num: int) -> list[PMItem]:
        """마크다운 테이블 형식에서 PM 항목 추출"""
        items: list[PMItem] = []
        lines = text.split("\n")

        for line in lines:
            if "|" not in line or line.strip().startswith("|---"):
                continue

            cells = [c.strip() for c in line.split("|") if c.strip()]
            if len(cells) < 2:
                continue

            # PM 관련 키워드가 있는 행 찾기
            full_text = " ".join(cells)
            if not any(kw in full_text for kw in self.pm_keywords):
                continue

            # 항목명 추출 (가장 긴 셀을 항목명으로 추정)
            item_name = max(cells, key=len)
            if len(item_name) < 3:
                continue

            period = self._detect_period(full_text)
            area = self._detect_area(full_text)
            method = self._detect_method(full_text)
            standard = self._detect_standard_value(full_text)

            if period:
                items.append(PMItem(
                    item_name=item_name,
                    period=period,
                    equipment_part=self._extract_part(full_text),
                    area=area,
                    method=method,
                    standard_value=standard,
                    source_page=page_num,
                    confidence=RULE_TABLE_CONFIDENCE_SCORE,
                    note="규칙 기반 추출",
                ))

        return items

    def _extract_from_lines(self, text: str, page_num: int) -> list[PMItem]:
        """일반 텍스트 라인에서 PM 항목 추출"""
        items: list[PMItem] = []
        lines = text.split("\n")

        # PM 관련 키워드가 있고 주기 표현이 있는 문장 찾기
        for line in lines:
            line = line.strip()
            if len(line) < 5 or "|" in line:
                continue

            has_pm = any(kw in line for kw in self.pm_keywords)
            period = self._detect_period(line)

            if has_pm and period:
                # 항목명: 줄 전체 또는 주요 내용
                item_name = self._clean_item_name(line)
                if len(item_name) < 3:
                    continue

                items.append(PMItem(
                    item_name=item_name,
                    period=period,
                    equipment_part=self._extract_part(line),
                    area=self._detect_area(line),
                    method=self._detect_method(line),
                    standard_value=self._detect_standard_value(line),
                    source_page=page_num,
                    confidence=RULE_CONFIDENCE_SCORE,
                    note="규칙 기반 추출 (문장)",
                ))

        return items

    def _detect_period(self, text: str) -> Optional[PMPeriod]:
        """텍스트에서 주기 감지 (여러 주기 감지 시 가장 짧은 주기 반환)"""
        detected: list[PMPeriod] = []

        # 긴 주기부터 검사 (짧은 키워드가 긴 키워드에 포함될 수 있으므로)
        for period in [PMPeriod.ANNUAL, PMPeriod.SEMI_ANNUAL, PMPeriod.QUARTERLY, PMPeriod.MONTHLY, PMPeriod.DAILY]:
            keywords = self.period_keywords[period]
            if any(kw in text for kw in keywords):
                detected.append(period)

        if not detected:
            return None

        # 짧은 주기 우선
        from app.models.schemas import PERIOD_ORDER
        detected.sort(key=lambda p: PERIOD_ORDER[p])
        return detected[0]

    def _detect_area(self, text: str) -> str:
        """텍스트에서 영역 감지"""
        for area_name, keywords in self.area_keywords.items():
            if area_name == "기타":
                continue
            if any(kw in text for kw in keywords):
                return area_name
        return "기타"

    def _detect_method(self, text: str) -> str:
        """텍스트에서 점검 방법 감지"""
        for method_name, keywords in self.method_patterns.items():
            if any(kw in text for kw in keywords):
                return method_name
        return "점검"

    def _detect_standard_value(self, text: str) -> Optional[str]:
        """텍스트에서 기준값 추출 (숫자+단위 패턴)"""
        # 숫자~숫자 단위 패턴 (예: 5~7 kgf/cm²)
        pattern = r'(\d+(?:\.\d+)?)\s*[~\-]\s*(\d+(?:\.\d+)?)\s*([a-zA-Z가-힣/%°℃²³]+)'
        match = re.search(pattern, text)
        if match:
            return f"{match.group(1)}~{match.group(2)} {match.group(3)}"

        # 숫자 + 단위 패턴 (예: 0.005mm 이하)
        pattern2 = r'(\d+(?:\.\d+)?)\s*([a-zA-Z가-힣/%°℃²³]+)\s*(이하|이상|미만|초과)?'
        match2 = re.search(pattern2, text)
        if match2:
            result = f"{match2.group(1)} {match2.group(2)}"
            if match2.group(3):
                result += f" {match2.group(3)}"
            return result

        return None

    def _extract_part(self, text: str) -> str:
        """텍스트에서 설비 부위 추출"""
        # 영역 키워드에서 부위 후보 추출
        for area_data in TAXONOMY_CONFIG.get("영역_분류", {}).values():
            for kw in area_data.get("키워드", []):
                if kw in text:
                    return kw
        return "일반"

    def _clean_item_name(self, text: str) -> str:
        """항목명 정리 (불필요한 문자 제거)"""
        # 번호, 기호 등 제거
        cleaned = re.sub(r'^[\d\.\-\)\]\s]+', '', text)
        # 주기 관련 키워드 뒤의 내용 제거 (너무 길면)
        if len(cleaned) > 50:
            cleaned = cleaned[:50] + "..."
        return cleaned.strip()
