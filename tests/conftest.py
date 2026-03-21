import pytest
from app.models.schemas import PMItem, PMPeriod

@pytest.fixture
def sample_pm_items():
    """기본 PMItem 리스트 fixture."""
    return [
        PMItem(
            item_name="오일레벨 확인",
            period=PMPeriod.DAILY,
            equipment_part="오일탱크",
            area="유압계통",
            method="육안점검",
            standard_value="5~7 kgf/cm²",
            source_page=1,
            confidence=0.9,
        ),
        PMItem(
            item_name="필터 교체",
            period=PMPeriod.MONTHLY,
            equipment_part="유압필터",
            area="유압계통",
            method="교체",
            source_page=3,
            confidence=0.85,
        ),
        PMItem(
            item_name="벨트 장력 점검",
            period=PMPeriod.QUARTERLY,
            equipment_part="구동벨트",
            area="기계계통",
            method="측정",
            standard_value="10~15 kgf",
            source_page=5,
            confidence=0.75,
        ),
        PMItem(
            item_name="절연 저항 측정",
            period=PMPeriod.ANNUAL,
            equipment_part="모터",
            area="전기계통",
            method="측정",
            standard_value="1 MΩ 이상",
            source_page=8,
            confidence=0.8,
        ),
    ]

@pytest.fixture
def empty_pm_items():
    """빈 PMItem 리스트 fixture."""
    return []
