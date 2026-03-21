"""
체크리스트 빌더

PM 항목 리스트를 주기별/부위별/영역별로 그룹핑하고 정렬하여
체크리스트 구조를 생성합니다.
"""

import logging
from collections import defaultdict

from app.models.schemas import PMItem, PMPeriod, PERIOD_ORDER

logger = logging.getLogger(__name__)

# 영역 고정 정렬 순서
AREA_ORDER = {
    "기계계통": 1,
    "전기계통": 2,
    "유압계통": 3,
    "공압계통": 4,
    "냉각계통": 5,
    "윤활계통": 6,
    "안전장치": 7,
    "기타": 99,
}


class ChecklistBuilder:
    """PM 체크리스트 빌더"""

    def build_by_period(self, items: list[PMItem]) -> dict[str, list[PMItem]]:
        """
        주기별로 그룹핑

        Args:
            items: PMItem 리스트

        Returns:
            {"일": [...], "월": [...], "분기": [...], "반기": [...], "년": [...]}
            각 그룹 내에서 area → equipment_part → item_name 순 정렬
        """
        grouped: dict[str, list[PMItem]] = defaultdict(list)

        for item in items:
            grouped[item.period.value].append(item)

        # 각 그룹 내 정렬
        for period_key in grouped:
            grouped[period_key].sort(
                key=lambda x: (
                    AREA_ORDER.get(x.area, 99),
                    x.equipment_part,
                    x.item_name,
                )
            )

        # 주기 순서대로 정렬
        ordered = {}
        for period in [PMPeriod.DAILY, PMPeriod.MONTHLY, PMPeriod.QUARTERLY, PMPeriod.SEMI_ANNUAL, PMPeriod.ANNUAL]:
            if period.value in grouped:
                ordered[period.value] = grouped[period.value]

        return ordered

    def build_by_part(self, items: list[PMItem]) -> dict[str, list[PMItem]]:
        """
        부위별로 그룹핑

        Args:
            items: PMItem 리스트

        Returns:
            {"주축": [...], "오일탱크": [...], ...}
            각 그룹 내에서 period(일<월<분기<반기<년) → item_name 순 정렬
        """
        grouped: dict[str, list[PMItem]] = defaultdict(list)

        for item in items:
            grouped[item.equipment_part].append(item)

        # 각 그룹 내 정렬
        for part_key in grouped:
            grouped[part_key].sort(
                key=lambda x: (PERIOD_ORDER[x.period], x.item_name)
            )

        # 부위명 알파벳/가나다 순 정렬
        return dict(sorted(grouped.items()))

    def build_by_area(self, items: list[PMItem]) -> dict[str, list[PMItem]]:
        """
        영역별로 그룹핑 (고정 순서)

        Args:
            items: PMItem 리스트

        Returns:
            {"기계계통": [...], "전기계통": [...], ...}
            고정 순서: 기계→전기→유압→공압→냉각→윤활→안전→기타
        """
        grouped: dict[str, list[PMItem]] = defaultdict(list)

        for item in items:
            grouped[item.area].append(item)

        # 각 그룹 내 정렬: period → equipment_part → item_name
        for area_key in grouped:
            grouped[area_key].sort(
                key=lambda x: (
                    PERIOD_ORDER[x.period],
                    x.equipment_part,
                    x.item_name,
                )
            )

        # 고정 순서로 정렬
        ordered = {}
        for area_name in sorted(grouped.keys(), key=lambda x: AREA_ORDER.get(x, 99)):
            ordered[area_name] = grouped[area_name]

        return ordered

    def build_matrix(self, items: list[PMItem]) -> dict:
        """
        부위(행) × 주기(열) 교차 매트릭스

        Args:
            items: PMItem 리스트

        Returns:
            {
                "parts": ["주축", "오일탱크", ...],
                "periods": ["일", "월", "분기", "반기", "년"],
                "matrix": {"주축": {"일": [item1], "월": [item2]}, ...}
            }
        """
        matrix: dict[str, dict[str, list[PMItem]]] = defaultdict(lambda: defaultdict(list))

        for item in items:
            matrix[item.equipment_part][item.period.value].append(item)

        parts = sorted(matrix.keys())
        periods = [p.value for p in PMPeriod]

        return {
            "parts": parts,
            "periods": periods,
            "matrix": {part: dict(matrix[part]) for part in parts},
        }

    def get_statistics(self, items: list[PMItem]) -> dict:
        """
        PM 항목 통계

        Args:
            items: PMItem 리스트

        Returns:
            통계 딕셔너리
        """
        period_count: dict[str, int] = defaultdict(int)
        area_count: dict[str, int] = defaultdict(int)
        part_set: set[str] = set()
        low_confidence_count = 0

        for item in items:
            period_count[item.period.value] += 1
            area_count[item.area] += 1
            part_set.add(item.equipment_part)
            if item.confidence < 0.7:
                low_confidence_count += 1

        return {
            "total_items": len(items),
            "by_period": dict(period_count),
            "by_area": dict(area_count),
            "total_parts": len(part_set),
            "parts_list": sorted(part_set),
            "low_confidence_count": low_confidence_count,
        }

    def format_checklist_row(self, index: int, item: PMItem) -> list[str]:
        """
        PMItem을 체크리스트 행으로 변환

        Returns:
            [No, 점검항목, 점검방법, 기준값, 점검결과(빈칸), 비고, 담당자(빈칸), 날짜(빈칸)]
        """
        return [
            str(index),
            item.item_name,
            item.method,
            item.standard_value or "-",
            "",  # 점검 결과
            item.note or "",
            "",  # 담당자
            "",  # 날짜
        ]
