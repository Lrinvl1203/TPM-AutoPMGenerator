"""
PM Checklist Automator — CLI 실행 스크립트

PDF 매뉴얼 → OCR → PM 분류 → Excel 체크리스트 생성
MVP-1 검증용 커맨드라인 인터페이스

사용법:
    python run_pipeline.py --pdf "매뉴얼.pdf" --equipment "CNC 머시닝센터"
    python run_pipeline.py --pdf "매뉴얼.pdf" --equipment "CNC 머시닝센터" --offline
"""

import argparse
import json
import logging
import os
import sys
import time
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv

# 프로젝트 루트를 Python path에 추가
sys.path.insert(0, str(Path(__file__).parent))

load_dotenv()

from app.core.pdf_processor import PDFProcessor
from app.core.ocr_engine import OCREngine
from app.core.pm_classifier import PMClassifier
from app.core.rule_classifier import RuleClassifier
from app.core.checklist_builder import ChecklistBuilder
from app.core.export_engine import ExportEngine
from app.models.schemas import PMItem

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("PM-Pipeline")


def create_progress_callback(stage_name: str):
    """진행률 콜백 팩토리"""
    def callback(current: int, total: int):
        pct = int(current / total * 100)
        bar = "█" * (pct // 5) + "░" * (20 - pct // 5)
        print(f"\r  {stage_name}: [{bar}] {pct}% ({current}/{total})", end="", flush=True)
        if current == total:
            print()
    return callback


def run_pipeline(
    pdf_path: str,
    equipment_name: str,
    output_dir: str = "./outputs",
    use_offline: bool = False,
    save_intermediate: bool = True,
) -> str:
    """
    전체 파이프라인 실행

    Args:
        pdf_path: PDF 파일 경로
        equipment_name: 설비명
        output_dir: 출력 디렉토리
        use_offline: True면 규칙 기반 분류기만 사용 (API 호출 없음)
        save_intermediate: True면 중간 결과도 저장

    Returns:
        생성된 Excel 파일 경로
    """
    start_time = time.time()
    os.makedirs(output_dir, exist_ok=True)
    pdf_name = Path(pdf_path).stem

    print("\n" + "=" * 60)
    print("  🔧 PM Checklist Automator")
    print("=" * 60)
    print(f"  📄 매뉴얼: {pdf_path}")
    print(f"  🏭 설비명: {equipment_name}")
    print(f"  📂 출력: {output_dir}")
    print(f"  🤖 분류기: {'규칙 기반 (오프라인)' if use_offline else 'Gemini AI'}")
    print("=" * 60 + "\n")

    # ── Step 1: PDF 로드 및 분석 ──
    logger.info("Step 1/5: PDF 파일 분석 중...")
    pdf_processor = PDFProcessor()
    metadata = pdf_processor.load_pdf(pdf_path)

    print(f"  📊 총 {metadata['total_pages']} 페이지, "
          f"{'스캔본' if metadata['is_scanned'] else '텍스트 PDF'}, "
          f"{metadata['file_size_mb']}MB")

    # ── Step 2: OCR/텍스트 추출 ──
    logger.info("Step 2/5: 텍스트 추출 중...")
    ocr_engine = OCREngine()
    ocr_results = ocr_engine.extract_text_from_pdf(
        pdf_path,
        progress_callback=create_progress_callback("OCR 추출"),
    )

    total_blocks = sum(len(p.blocks) for p in ocr_results)
    print(f"  ✅ {len(ocr_results)}개 페이지에서 {total_blocks}개 텍스트 블록 추출")

    # 중간 결과 저장 (체크포인팅)
    if save_intermediate:
        ocr_json_path = os.path.join(output_dir, f"{pdf_name}_ocr_results.json")
        ocr_data = [
            {
                "page": p.page,
                "blocks": [{"text": b.text, "confidence": b.confidence} for b in p.blocks],
            }
            for p in ocr_results
        ]
        with open(ocr_json_path, "w", encoding="utf-8") as f:
            json.dump(ocr_data, f, ensure_ascii=False, indent=2)
        logger.info(f"OCR 결과 저장: {ocr_json_path}")

    # ── Step 3: PM 항목 분류 ──
    logger.info("Step 3/5: PM 항목 분류 중...")

    pm_items: list[PMItem] = []

    if use_offline:
        # 규칙 기반 분류기
        rule_classifier = RuleClassifier()
        pm_items = rule_classifier.classify_pm_items(
            ocr_results,
            equipment_name=equipment_name,
            progress_callback=create_progress_callback("규칙 기반 분류"),
        )
    else:
        # Gemini AI 분류기
        api_key = os.getenv("GEMINI_API_KEY", "")
        if not api_key or api_key == "your_gemini_api_key_here":
            logger.warning("GEMINI_API_KEY가 설정되지 않았습니다. 규칙 기반 분류기로 전환합니다.")
            rule_classifier = RuleClassifier()
            pm_items = rule_classifier.classify_pm_items(
                ocr_results,
                equipment_name=equipment_name,
                progress_callback=create_progress_callback("규칙 기반 분류 (fallback)"),
            )
        else:
            try:
                classifier = PMClassifier(api_key=api_key)
                pm_items = classifier.classify_pm_items(
                    ocr_results,
                    equipment_name=equipment_name,
                    progress_callback=create_progress_callback("Gemini AI 분류"),
                )
            except Exception as e:
                logger.error(f"Gemini API 오류: {e}")
                logger.warning("규칙 기반 분류기로 전환합니다.")
                rule_classifier = RuleClassifier()
                pm_items = rule_classifier.classify_pm_items(
                    ocr_results,
                    equipment_name=equipment_name,
                    progress_callback=create_progress_callback("규칙 기반 분류 (fallback)"),
                )

    print(f"  ✅ {len(pm_items)}개 PM 항목 추출 완료")

    # 중간 결과 저장
    if save_intermediate:
        items_json_path = os.path.join(output_dir, f"{pdf_name}_pm_items.json")
        items_data = [item.model_dump() for item in pm_items]
        with open(items_json_path, "w", encoding="utf-8") as f:
            json.dump(items_data, f, ensure_ascii=False, indent=2, default=str)
        logger.info(f"PM 항목 저장: {items_json_path}")

    # ── Step 4: 통계 출력 ──
    logger.info("Step 4/5: 통계 분석 중...")
    builder = ChecklistBuilder()
    stats = builder.get_statistics(pm_items)

    print(f"\n  📊 PM 항목 통계:")
    print(f"    총 항목 수: {stats['total_items']}")
    print(f"    부위 수: {stats['total_parts']}개")
    if stats['low_confidence_count'] > 0:
        print(f"    ⚠️ 낮은 신뢰도 항목: {stats['low_confidence_count']}개")

    print(f"\n    주기별:")
    for period, count in stats['by_period'].items():
        bar = "■" * count
        print(f"      {period:4s}: {bar} ({count})")

    print(f"\n    영역별:")
    for area, count in stats['by_area'].items():
        print(f"      {area:8s}: {count}개")

    # ── Step 5: Excel 체크리스트 생성 ──
    logger.info("Step 5/5: Excel 체크리스트 생성 중...")

    if not pm_items:
        logger.warning("추출된 PM 항목이 없습니다. 빈 체크리스트를 생성합니다.")

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    excel_filename = f"{pdf_name}_PM_Checklist_{timestamp}.xlsx"
    excel_path = os.path.join(output_dir, excel_filename)

    export_engine = ExportEngine()
    export_engine.save_to_file(
        manual_name=Path(pdf_path).name,
        equipment_name=equipment_name,
        all_items=pm_items,
        output_path=excel_path,
    )

    elapsed = time.time() - start_time

    print(f"\n" + "=" * 60)
    print(f"  ✅ 완료! ({elapsed:.1f}초)")
    print(f"  📁 Excel: {excel_path}")
    if save_intermediate:
        print(f"  📁 OCR 결과: {ocr_json_path}")
        print(f"  📁 PM 항목: {items_json_path}")
    print("=" * 60 + "\n")

    return excel_path


def main():
    parser = argparse.ArgumentParser(
        description="PM Checklist Automator — 설비 매뉴얼 PDF → PM 체크리스트 자동 생성",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
사용 예시:
  python run_pipeline.py --pdf "manual.pdf" --equipment "CNC 머시닝센터"
  python run_pipeline.py --pdf "manual.pdf" --equipment "CNC" --offline
  python run_pipeline.py --pdf "manual.pdf" --equipment "CNC" -o ./results
        """,
    )
    parser.add_argument("--pdf", required=True, help="입력 PDF 파일 경로")
    parser.add_argument("--equipment", required=True, help="설비명")
    parser.add_argument("-o", "--output", default="./outputs", help="출력 디렉토리 (기본: ./outputs)")
    parser.add_argument("--offline", action="store_true", help="오프라인 모드 (규칙 기반 분류기만 사용)")
    parser.add_argument("--no-save-intermediate", action="store_true", help="중간 결과 저장 안함")
    parser.add_argument("-v", "--verbose", action="store_true", help="디버그 로그 출력")

    args = parser.parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    if not os.path.exists(args.pdf):
        print(f"❌ 파일을 찾을 수 없습니다: {args.pdf}")
        sys.exit(1)

    run_pipeline(
        pdf_path=args.pdf,
        equipment_name=args.equipment,
        output_dir=args.output,
        use_offline=args.offline,
        save_intermediate=not args.no_save_intermediate,
    )


if __name__ == "__main__":
    main()
