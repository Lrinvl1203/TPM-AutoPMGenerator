import pytest
from app.core.rule_classifier import RuleClassifier
from app.models.schemas import OCRPageResult, OCRBlock, PMPeriod

def make_page(page_num: int, text: str) -> OCRPageResult:
    """단일 블록으로 구성된 OCRPageResult 생성 헬퍼."""
    return OCRPageResult(
        page=page_num,
        blocks=[OCRBlock(text=text, confidence=0.9, bbox=[0, 0, 100, 20])],
        has_text=True,
    )

class TestRuleClassifierBasic:
    def setup_method(self):
        self.classifier = RuleClassifier()

    def test_빈_입력_빈_결과(self):
        result = self.classifier.classify_pm_items([])
        assert result == []

    def test_pm_키워드_없는_텍스트_0개(self):
        pages = [make_page(1, "이 텍스트는 PM과 무관합니다.")]
        result = self.classifier.classify_pm_items(pages)
        assert len(result) == 0

    def test_일간_점검_항목_추출(self):
        pages = [make_page(1, "매일 오일레벨 확인 - 육안점검")]
        result = self.classifier.classify_pm_items(pages)
        assert len(result) >= 1
        daily_items = [r for r in result if r.period == PMPeriod.DAILY]
        assert len(daily_items) >= 1

    def test_월간_점검_항목_추출(self):
        pages = [make_page(1, "매월 필터 교체 - 교체")]
        result = self.classifier.classify_pm_items(pages)
        monthly = [r for r in result if r.period == PMPeriod.MONTHLY]
        assert len(monthly) >= 1

    def test_중복_항목_제거(self):
        text = "매일 오일레벨 확인 - 육안점검"
        pages = [make_page(1, text), make_page(2, text)]
        result = self.classifier.classify_pm_items(pages)
        names = [r.item_name for r in result]
        # 동일 이름+주기 중복 제거됨
        assert len(names) == len(set(names))

    def test_confidence_범위(self):
        pages = [make_page(1, "매일 오일레벨 확인 - 육안점검")]
        result = self.classifier.classify_pm_items(pages)
        for item in result:
            assert 0.0 <= item.confidence <= 1.0

    def test_item_id_고유(self):
        pages = [make_page(1, "매일 점검 A, 매월 점검 B 교체")]
        result = self.classifier.classify_pm_items(pages)
        ids = [r.item_id for r in result]
        assert len(ids) == len(set(ids))
