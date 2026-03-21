import pytest
import os
from app.core.export_engine import ExportEngine

class TestExportEngineBasic:
    def setup_method(self):
        self.engine = ExportEngine()

    def test_정상_excel_생성(self, sample_pm_items, tmp_path):
        out_path = os.path.join(str(tmp_path), "test.xlsx")
        result = self.engine.save_to_file(
            manual_name="test_manual",
            equipment_name="테스트설비",
            all_items=sample_pm_items,
            output_path=out_path
        )
        assert os.path.exists(result)
        assert result.endswith(".xlsx")

    def test_excel_파일_크기_0이상(self, sample_pm_items, tmp_path):
        out_path = os.path.join(str(tmp_path), "test.xlsx")
        result = self.engine.save_to_file(
            manual_name="test_manual",
            equipment_name="테스트설비",
            all_items=sample_pm_items,
            output_path=out_path
        )
        assert os.path.getsize(result) > 0

    def test_빈_pm_items_처리(self, empty_pm_items, tmp_path):
        """빈 리스트에서도 크래시 없이 파일 생성되어야 함."""
        out_path = os.path.join(str(tmp_path), "empty.xlsx")
        result = self.engine.save_to_file(
            manual_name="test_manual",
            equipment_name="빈설비",
            all_items=empty_pm_items,
            output_path=out_path
        )
        assert os.path.exists(result)
