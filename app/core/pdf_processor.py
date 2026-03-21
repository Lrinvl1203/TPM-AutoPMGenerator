"""
PDF 처리 엔진

PyMuPDF(fitz)를 사용하여 PDF 파일을 이미지로 변환하고,
텍스트 레이어를 직접 추출합니다.
"""

import logging
from pathlib import Path
from typing import Optional

import fitz  # PyMuPDF
from PIL import Image

logger = logging.getLogger(__name__)


class PDFProcessor:
    """PDF 파일 처리 클래스"""

    def __init__(self, default_dpi: int = 200):
        """
        Args:
            default_dpi: 기본 이미지 변환 DPI (200 권장, 저해상도 시 300 자동 상향)
        """
        self.default_dpi = default_dpi

    def load_pdf(self, file_path: str) -> dict:
        """
        PDF 메타데이터 반환

        Args:
            file_path: PDF 파일 경로

        Returns:
            메타데이터 딕셔너리 (총 페이지 수, 제목, 작성자 등)
        """
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"PDF 파일을 찾을 수 없습니다: {file_path}")

        doc = fitz.open(file_path)
        metadata = {
            "file_path": str(path.absolute()),
            "file_name": path.name,
            "total_pages": len(doc),
            "title": doc.metadata.get("title", ""),
            "author": doc.metadata.get("author", ""),
            "subject": doc.metadata.get("subject", ""),
            "creator": doc.metadata.get("creator", ""),
            "file_size_mb": round(path.stat().st_size / (1024 * 1024), 2),
            "is_scanned": self.is_scanned_pdf(file_path),
        }
        doc.close()
        return metadata

    def pdf_to_images(
        self,
        file_path: str,
        dpi: Optional[int] = None,
        pages: Optional[list[int]] = None,
    ) -> list[Image.Image]:
        """
        PDF 페이지를 이미지로 변환

        Args:
            file_path: PDF 파일 경로
            dpi: DPI (기본값: self.default_dpi)
            pages: 변환할 페이지 번호 목록 (0-indexed, None이면 전체)

        Returns:
            PIL Image 리스트
        """
        dpi = dpi or self.default_dpi
        zoom = dpi / 72  # fitz 기본 DPI는 72
        matrix = fitz.Matrix(zoom, zoom)

        doc = fitz.open(file_path)
        images: list[Image.Image] = []

        page_range = pages if pages else range(len(doc))

        for page_num in page_range:
            if page_num >= len(doc):
                logger.warning(f"페이지 {page_num}이 범위를 초과합니다 (총 {len(doc)} 페이지)")
                continue

            page = doc[page_num]
            pixmap = page.get_pixmap(matrix=matrix)

            # Pixmap → PIL Image 변환
            img = Image.frombytes("RGB", [pixmap.width, pixmap.height], pixmap.samples)
            images.append(img)
            logger.debug(f"페이지 {page_num + 1}/{len(doc)} 이미지 변환 완료 ({pixmap.width}x{pixmap.height})")

        doc.close()
        logger.info(f"총 {len(images)}개 페이지 이미지 변환 완료 (DPI: {dpi})")
        return images

    def extract_text_native(self, file_path: str) -> list[dict]:
        """
        텍스트 레이어가 있는 PDF에서 직접 텍스트 추출

        Args:
            file_path: PDF 파일 경로

        Returns:
            페이지별 텍스트 딕셔너리 리스트
            [{"page": 1, "text": "...", "has_text": True}, ...]
        """
        doc = fitz.open(file_path)
        results: list[dict] = []

        for page_num in range(len(doc)):
            page = doc[page_num]
            text = page.get_text("text").strip()
            results.append({
                "page": page_num + 1,
                "text": text,
                "has_text": len(text) > 0,
            })

        doc.close()
        return results

    def extract_text_with_layout(self, file_path: str) -> list[dict]:
        """
        텍스트 블록 단위로 레이아웃 정보와 함께 추출

        Args:
            file_path: PDF 파일 경로

        Returns:
            페이지별 텍스트 블록 리스트
        """
        doc = fitz.open(file_path)
        results: list[dict] = []

        for page_num in range(len(doc)):
            page = doc[page_num]
            blocks = page.get_text("blocks")  # (x0, y0, x1, y1, text, block_no, block_type)
            text_blocks = []
            for block in blocks:
                if block[6] == 0:  # text block (not image)
                    text_blocks.append({
                        "text": block[4].strip(),
                        "bbox": [block[0], block[1], block[2], block[3]],
                        "block_no": block[5],
                    })
            results.append({
                "page": page_num + 1,
                "blocks": text_blocks,
                "has_text": len(text_blocks) > 0,
            })

        doc.close()
        return results

    def extract_tables_native(self, file_path: str) -> list[dict]:
        """
        PyMuPDF를 이용한 표 추출 (텍스트 PDF 전용)

        fitz의 find_tables() 메서드를 사용합니다.

        Args:
            file_path: PDF 파일 경로

        Returns:
            표 데이터 리스트 [{"page": 1, "rows": [["셀1", "셀2"], ...]}, ...]
        """
        doc = fitz.open(file_path)
        tables_result: list[dict] = []

        for page_num in range(len(doc)):
            page = doc[page_num]
            try:
                tabs = page.find_tables()
                for table in tabs:
                    rows = []
                    for row in table.extract():
                        cleaned_row = [cell if cell else "" for cell in row]
                        rows.append(cleaned_row)
                    if rows:
                        tables_result.append({
                            "page": page_num + 1,
                            "rows": rows,
                        })
            except Exception as e:
                logger.warning(f"페이지 {page_num + 1} 표 추출 실패: {e}")

        doc.close()
        logger.info(f"총 {len(tables_result)}개 표 추출 완료")
        return tables_result

    def is_scanned_pdf(self, file_path: str) -> bool:
        """
        PDF가 스캔본(이미지 PDF)인지 판별

        각 페이지의 텍스트 총 글자 수가 100자 미만이면 스캔본으로 판정.

        Args:
            file_path: PDF 파일 경로

        Returns:
            True면 스캔본
        """
        doc = fitz.open(file_path)
        total_chars = 0

        # 최대 5페이지만 샘플링하여 판별
        sample_pages = min(5, len(doc))
        for page_num in range(sample_pages):
            page = doc[page_num]
            text = page.get_text("text")
            total_chars += len(text.strip())

        doc.close()

        avg_chars = total_chars / sample_pages if sample_pages > 0 else 0
        is_scanned = avg_chars < 100
        logger.info(f"스캔본 판별: {'예' if is_scanned else '아니오'} (평균 {avg_chars:.0f}자/페이지)")
        return is_scanned
