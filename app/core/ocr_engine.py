"""
OCR 엔진

PaddleOCR을 사용하여 이미지에서 텍스트를 추출합니다.
텍스트 PDF는 네이티브 추출을 우선 사용하고,
스캔본 PDF는 이미지로 변환 후 OCR을 수행합니다.
"""

import logging
from typing import Optional

import numpy as np
from PIL import Image

from app.core.pdf_processor import PDFProcessor
from app.models.schemas import OCRBlock, OCRPageResult, TableResult

logger = logging.getLogger(__name__)


class OCREngine:
    """PaddleOCR 기반 텍스트 추출 엔진"""

    def __init__(
        self,
        lang: str = "korean",
        use_angle_cls: bool = True,
        det_db_thresh: float = 0.3,
        show_log: bool = False,
    ):
        """
        Args:
            lang: OCR 언어 (korean, en, japan 등)
            use_angle_cls: 기울어진 텍스트 자동 보정
            det_db_thresh: 텍스트 검출 임계값 (낮을수록 작은 텍스트도 인식)
            show_log: PaddleOCR 로그 출력 여부
        """
        self.lang = lang
        self._ocr = None
        self._ocr_config = {
            "use_angle_cls": use_angle_cls,
            "lang": lang,
            "show_log": show_log,
            "det_db_thresh": det_db_thresh,
        }
        self.pdf_processor = PDFProcessor()

    @property
    def ocr(self):
        """PaddleOCR 인스턴스 (지연 초기화)"""
        if self._ocr is None:
            from paddleocr import PaddleOCR
            logger.info("PaddleOCR 초기화 중...")
            self._ocr = PaddleOCR(**self._ocr_config)
            logger.info("PaddleOCR 초기화 완료")
        return self._ocr

    def extract_text_from_image(self, image: Image.Image) -> list[OCRBlock]:
        """
        단일 이미지에서 텍스트 추출

        Args:
            image: PIL Image 객체

        Returns:
            OCRBlock 리스트 (텍스트, 신뢰도, bbox 포함)
        """
        # PIL Image → numpy array 변환
        img_array = np.array(image)

        result = self.ocr.ocr(img_array, cls=True)
        blocks: list[OCRBlock] = []

        if result and result[0]:
            for line in result[0]:
                bbox = line[0]           # [[x1,y1],[x2,y2],[x3,y3],[x4,y4]]
                text = line[1][0]        # 인식 텍스트
                confidence = line[1][1]  # 인식 신뢰도

                block = OCRBlock(
                    text=text,
                    confidence=round(confidence, 4),
                    bbox=bbox,
                    low_confidence=confidence < 0.7,
                )
                blocks.append(block)

        return blocks

    def extract_text_from_pdf(
        self,
        file_path: str,
        dpi: int = 200,
        progress_callback: Optional[callable] = None,
        force_ocr: bool = False,
    ) -> list[OCRPageResult]:
        """
        PDF에서 텍스트 추출 (텍스트 PDF → 직접, 스캔본/강제 → OCR)

        Args:
            file_path: PDF 파일 경로
            dpi: OCR용 이미지 DPI
            progress_callback: 진행률 콜백 fn(current_page, total_pages)
            force_ocr: 글꼴 깨짐 등을 방지하기 위해 강제로 이미지 OCR을 수행할지 여부

        Returns:
            페이지별 OCR 결과 리스트
        """
        is_scanned = self.pdf_processor.is_scanned_pdf(file_path)

        if not is_scanned and not force_ocr:
            logger.info("텍스트 PDF 감지 — 네이티브 텍스트 추출 + 표 추출 사용")
            return self._extract_from_text_pdf(file_path, progress_callback)
        else:
            reason = "강제 설정" if force_ocr else "스캔본"
            logger.info(f"{reason} PDF 감지 — OCR 처리 시작")
            try:
                # PaddleOCR이 설치되어 있는지 확인 (지연 초기화 호출)
                _ = self.ocr
                return self._extract_from_scanned_pdf(file_path, dpi, progress_callback)
            except ImportError:
                logger.error("PaddleOCR 패키지가 설치되어 있지 않아 OCR을 수행할 수 없습니다.")
                # Fallback: OCR 없이 빈 결과 또는 네이티브 텍스트 추출 시도
                return self._extract_from_text_pdf(file_path, progress_callback)

    def _extract_from_text_pdf(
        self,
        file_path: str,
        progress_callback: Optional[callable] = None,
    ) -> list[OCRPageResult]:
        """텍스트 PDF에서 직접 추출"""
        native_results = self.pdf_processor.extract_text_native(file_path)
        results: list[OCRPageResult] = []

        for i, page_data in enumerate(native_results):
            blocks = []
            if page_data["text"]:
                # 텍스트를 단락 단위로 분할
                paragraphs = [p.strip() for p in page_data["text"].split("\n") if p.strip()]
                for para in paragraphs:
                    blocks.append(OCRBlock(
                        text=para,
                        confidence=1.0,
                        low_confidence=False,
                    ))

            results.append(OCRPageResult(
                page=page_data["page"],
                blocks=blocks,
                has_text=page_data["has_text"],
            ))

            if progress_callback:
                progress_callback(i + 1, len(native_results))

        # 표도 추출하여 결과에 추가
        try:
            tables = self.pdf_processor.extract_tables_native(file_path)
            for table in tables:
                page_idx = table["page"] - 1
                if page_idx < len(results):
                    # 표 내용을 마크다운 형식으로 변환하여 텍스트 블록에 추가
                    table_text = self._table_to_markdown(table["rows"])
                    results[page_idx].blocks.append(OCRBlock(
                        text=table_text,
                        confidence=1.0,
                        low_confidence=False,
                    ))
        except Exception as e:
            logger.warning(f"표 추출 중 오류: {e}")

        return results

    def _extract_from_scanned_pdf(
        self,
        file_path: str,
        dpi: int,
        progress_callback: Optional[callable] = None,
    ) -> list[OCRPageResult]:
        """스캔본 PDF에서 OCR 추출"""
        images = self.pdf_processor.pdf_to_images(file_path, dpi=dpi)
        results: list[OCRPageResult] = []

        for i, img in enumerate(images):
            logger.info(f"OCR 처리 중... ({i + 1}/{len(images)} 페이지)")
            blocks = self.extract_text_from_image(img)

            results.append(OCRPageResult(
                page=i + 1,
                blocks=blocks,
                has_text=len(blocks) > 0,
            ))

            if progress_callback:
                progress_callback(i + 1, len(images))

        return results

    def extract_tables_from_image(self, image: Image.Image) -> list[TableResult]:
        """
        이미지에서 표 구조 인식

        PaddleOCR의 레이아웃 분석을 통해 표를 인식합니다.

        Args:
            image: PIL Image 객체

        Returns:
            TableResult 리스트
        """
        # 기본 OCR 결과에서 위치 기반으로 표 구조를 추정
        blocks = self.extract_text_from_image(image)
        if not blocks:
            return []

        # 간단한 행 그룹핑: y 좌표 기준으로 그룹화
        rows_dict: dict[int, list[OCRBlock]] = {}
        for block in blocks:
            if block.bbox:
                y_center = int((block.bbox[0][1] + block.bbox[2][1]) / 2)
                y_key = y_center // 20 * 20  # 20px 단위로 그룹화
                if y_key not in rows_dict:
                    rows_dict[y_key] = []
                rows_dict[y_key].append(block)

        # 2열 이상인 행이 3개 이상이면 표로 간주
        table_rows = []
        for y_key in sorted(rows_dict.keys()):
            row_blocks = sorted(rows_dict[y_key], key=lambda b: b.bbox[0][0] if b.bbox else 0)
            if len(row_blocks) >= 2:
                table_rows.append([b.text for b in row_blocks])

        if len(table_rows) >= 3:
            return [TableResult(rows=table_rows, page=0)]

        return []

    @staticmethod
    def _table_to_markdown(rows: list[list[str]]) -> str:
        """표 데이터를 마크다운 테이블 형식으로 변환"""
        if not rows:
            return ""

        lines = []
        for i, row in enumerate(rows):
            line = "| " + " | ".join(cell.replace("\n", " ") for cell in row) + " |"
            lines.append(line)
            if i == 0:
                # 헤더 구분선
                separator = "| " + " | ".join("---" for _ in row) + " |"
                lines.append(separator)

        return "\n".join(lines)
