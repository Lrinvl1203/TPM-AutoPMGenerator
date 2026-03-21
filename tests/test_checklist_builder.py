import pytest
from app.core.checklist_builder import ChecklistBuilder
from app.models.schemas import PMPeriod

class TestChecklistBuilderEmpty:
    def setup_method(self):
        self.builder = ChecklistBuilder()

    def test_빈_입력_build_by_period(self):
        result = self.builder.build_by_period([])
        assert isinstance(result, dict)
        # Period keys should exist but be empty
        assert all(len(v) == 0 for v in result.values())

    def test_빈_입력_get_statistics(self):
        stats = self.builder.get_statistics([])
        assert stats["total_items"] == 0

class TestChecklistBuilderNormal:
    def setup_method(self):
        self.builder = ChecklistBuilder()

    def test_기간별_그룹핑(self, sample_pm_items):
        result = self.builder.build_by_period(sample_pm_items)
        assert PMPeriod.DAILY.value in result  # Check strings if builder converts to str
        assert PMPeriod.MONTHLY.value in result
        assert len(result[PMPeriod.DAILY.value]) == 1
        assert len(result[PMPeriod.MONTHLY.value]) == 1

    def test_통계_총계(self, sample_pm_items):
        stats = self.builder.get_statistics(sample_pm_items)
        assert stats["total_items"] == len(sample_pm_items)

    def test_부위별_그룹핑(self, sample_pm_items):
        stats = self.builder.get_statistics(sample_pm_items)
        parts = stats.get("parts_list", [])
        assert "오일탱크" in parts
        assert "유압필터" in parts

    def test_영역별_그룹핑(self, sample_pm_items):
        stats = self.builder.get_statistics(sample_pm_items)
        areas = stats.get("by_area", {})
        assert "유압계통" in areas
        assert "전기계통" in areas
