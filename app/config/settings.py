"""프로젝트 전역 설정 상수. 환경변수 오버라이드 지원."""
import os

# OCR
OCR_DEFAULT_DPI: int = int(os.getenv("OCR_DEFAULT_DPI", "200"))
OCR_LOW_RES_DPI: int = int(os.getenv("OCR_LOW_RES_DPI", "300"))
OCR_CONFIDENCE_THRESHOLD: float = float(os.getenv("OCR_CONFIDENCE_THRESHOLD", "0.7"))
OCR_LOW_RES_CHAR_THRESHOLD: int = 100  # 페이지당 문자 수 이하 → 저해상도 판정

# PDF Processing
PDF_SCANNED_THRESHOLD: int = int(os.getenv("PDF_SCANNED_THRESHOLD", "10"))  # 문자/페이지 기준

# PM Classifier (AI)
GEMINI_MODEL: str = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
GEMINI_MAX_RETRIES: int = int(os.getenv("GEMINI_MAX_RETRIES", "3"))
GEMINI_CHUNK_SIZE: int = int(os.getenv("GEMINI_CHUNK_SIZE", "5"))  # 페이지/청크
GEMINI_TIMEOUT_SECONDS: int = int(os.getenv("GEMINI_TIMEOUT_SECONDS", "60"))

# PM Classifier (Rule-based)
RULE_CONFIDENCE_SCORE: float = 0.55
RULE_TABLE_CONFIDENCE_SCORE: float = 0.6

# Export
EXCEL_ROW_HEIGHT: int = 22
EXCEL_HEADER_COLOR: str = "1A3A5C"
EXCEL_HEADER_FONT_COLOR: str = "FFFFFF"
EXCEL_RESULT_COL_COLOR: str = "FFFF99"
EXCEL_FILL_COL_COLOR: str = "CCE5FF"
EXCEL_AREA_SEP_COLOR: str = "D0E4F7"
