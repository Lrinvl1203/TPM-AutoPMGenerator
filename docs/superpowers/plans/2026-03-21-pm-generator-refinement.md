# PM Generator - Complete Refinement Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** TPM 기반 PM 체크리스트 자동화 시스템을 프로덕션 품질로 완성한다 — 테스트 커버리지, 견고한 에러 핸들링, UX 폴리싱, 코드 클린업, 성능 개선을 포함한 전면 다듬기.

**Architecture:** Streamlit 3-stage Jidoka UI → (PDF → PaddleOCR → Gemini/RuleClassifier → ChecklistBuilder → openpyxl Export) 파이프라인. FastAPI 백엔드는 존재하나 미완성 상태. 테스트 없음. 이번 작업은 백엔드 API 완성을 제외한 현재 Streamlit-first 아키텍처 내에서 완벽한 다듬기에 집중한다.

**Tech Stack:** Python 3.11, Streamlit 1.40, PaddleOCR 2.8, PyMuPDF, Google Gemini 2.5-Flash, Pydantic 2.9, openpyxl 3.1, pandas 2.2

---

## 현황 분석 요약

| 영역 | 현재 상태 | 우선순위 |
|------|-----------|---------|
| 미커밋 변경사항 (`ui/streamlit_app.py`) | ⚠️ 존재 | 즉시 |
| 테스트 커버리지 | ❌ 없음 | 높음 |
| 하드코딩된 상수 | ⚠️ 다수 | 중간 |
| 에러 핸들링 엣지케이스 | ⚠️ 미완 | 중간 |
| 로깅 전략 | ⚠️ 비일관적 | 중간 |
| 중복 코드 (Gemini fallback parser) | ⚠️ pm_classifier.py | 낮음 |
| 문서 (VIBE_CODING_PROMPTS.md 오래됨) | ⚠️ 부분 stale | 낮음 |
| UI UX 폴리싱 | ⚠️ 개선 여지 | 중간 |
| 성능 (OCR 블로킹) | ⚠️ 개선 여지 | 낮음 |

---

## File Structure (변경될 파일)

```
app/
  core/
    pm_classifier.py          # 중복 fallback JSON 파서 제거, 상수 추출
    rule_classifier.py        # 상수 추출 (하드코딩된 키워드 → config)
    ocr_engine.py             # 상수 추출 (DPI, chunk size)
    export_engine.py          # 에러 핸들링 강화
    checklist_builder.py      # 엣지케이스 (빈 리스트) 핸들링
  config/
    settings.py               # [NEW] 프로젝트 전역 상수/설정 중앙화
ui/
  streamlit_app.py            # UX 폴리싱, 에러 핸들링 강화
tests/
  test_rule_classifier.py     # [NEW] RuleClassifier 단위 테스트
  test_checklist_builder.py   # [NEW] ChecklistBuilder 단위 테스트
  test_export_engine.py       # [NEW] ExportEngine 단위 테스트
  test_pdf_processor.py       # [NEW] PDFProcessor 단위 테스트
  conftest.py                 # [NEW] 공용 fixtures
  fixtures/
    sample_pm_items.py        # [NEW] 테스트용 PMItem 생성 헬퍼
README.md                     # [NEW] 프로젝트 문서
.env.example                  # 검토 및 보완
```

---

## Chunk 1: 즉각 정리 (Git 커밋 + 중복 코드 제거)

### Task 1: 미커밋 변경사항 커밋

**Files:** `ui/streamlit_app.py`

- [x] **Step 1: 현재 변경사항 확인**

  Run: `cd "p:/0_지키기/02_PROJECT/99_Working/50_PM_generator" && git diff --stat`
  Expected: `ui/streamlit_app.py | N lines changed`

- [x] **Step 2: 커밋**

  ```bash
  cd "p:/0_지키기/02_PROJECT/99_Working/50_PM_generator"
  git add ui/streamlit_app.py
  git commit -m "feat: PM 후보 텍스트 1차 추출 및 다운로드 기능 추가"
  ```

  Expected: `[main XXXXXXX] feat: ...`

---

### Task 2: pm_classifier.py 중복 코드 제거

**Files:** `app/core/pm_classifier.py`

**배경:** Gemini Structured Output API를 사용하므로 별도 JSON 파싱 fallback은 불필요하다. `response.text` 파싱 시도 블록(약 208-210행)이 중복이다.

- [x] **Step 1: 해당 코드 확인**

  Read: `app/core/pm_classifier.py` 전체 → 중복 fallback JSON 파서 위치 특정

- [x] **Step 2: 중복 블록 제거**

  Structured Output API가 실패하면 이미 `except` 블록에서 fallback classifier로 넘어간다. `response.text`를 별도로 파싱하는 시도가 있다면 제거한다.

- [x] **Step 3: 변경 후 CLI 실행 테스트**

  Run: `cd "p:/0_지키기/02_PROJECT/99_Working/50_PM_generator" && python -c "from app.core.pm_classifier import PMClassifier; print('OK')"`
  Expected: `OK`

- [x] **Step 4: 커밋**

  ```bash
  git add app/core/pm_classifier.py
  git commit -m "refactor: pm_classifier 중복 JSON fallback 파서 제거"
  ```

---

## Chunk 2: 설정 중앙화 (하드코딩 상수 제거)

### Task 3: settings.py 생성 및 상수 추출

**Files:**
- Create: `app/config/settings.py`
- Modify: `app/core/ocr_engine.py`
- Modify: `app/core/pm_classifier.py`
- Modify: `app/core/rule_classifier.py`

**배경:** DPI(200), chunk_size(5), retry_count(3), confidence_threshold(0.7) 등이 여러 파일에 흩어져 있다. 단일 설정 파일로 모은다.

- [x] **Step 1: 현재 하드코딩 상수 목록 수집**

  Read: `app/core/ocr_engine.py`, `app/core/pm_classifier.py`, `app/core/rule_classifier.py`
  → 수치 상수 목록 작성

- [x] **Step 2: settings.py 작성**

  ```python
  # app/config/settings.py
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
  ```

- [x] **Step 3: ocr_engine.py에서 settings import 적용**

  `OCR_DEFAULT_DPI`, `OCR_CONFIDENCE_THRESHOLD` 등을 하드코딩 대신 settings에서 가져오도록 수정.

- [x] **Step 4: pm_classifier.py에서 settings import 적용**

  `GEMINI_MODEL`, `GEMINI_MAX_RETRIES`, `GEMINI_CHUNK_SIZE` 적용.

- [x] **Step 5: rule_classifier.py에서 settings import 적용**

  confidence 점수 상수 적용.

- [x] **Step 6: 임포트 확인**

  Run: `python -c "from app.config.settings import OCR_DEFAULT_DPI; print(OCR_DEFAULT_DPI)"`
  Expected: `200`

- [x] **Step 7: 커밋**

  ```bash
  git add app/config/settings.py app/core/ocr_engine.py app/core/pm_classifier.py app/core/rule_classifier.py
  git commit -m "refactor: 하드코딩 상수 → app/config/settings.py 중앙화"
  ```

---

## Chunk 3: 테스트 인프라 구축

### Task 4: conftest.py와 fixtures 작성

**Files:**
- Create: `tests/conftest.py`
- Create: `tests/fixtures/sample_pm_items.py`

- [x] **Step 1: conftest.py 작성**

  ```python
  # tests/conftest.py
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
  ```

- [x] **Step 2: fixtures/__init__.py 추가**

  ```python
  # tests/fixtures/__init__.py
  ```

- [x] **Step 3: pytest 실행 확인 (0개 테스트지만 에러 없어야 함)**

  Run: `cd "p:/0_지키기/02_PROJECT/99_Working/50_PM_generator" && python -m pytest tests/ -v --collect-only`
  Expected: `no tests ran`, 에러 없음

- [x] **Step 4: 커밋**

  ```bash
  git add tests/conftest.py tests/fixtures/__init__.py
  git commit -m "test: pytest conftest 및 공용 fixture 추가"
  ```

---

### Task 5: RuleClassifier 단위 테스트

**Files:**
- Create: `tests/test_rule_classifier.py`
- Read first: `app/core/rule_classifier.py`

- [x] **Step 1: rule_classifier.py 정독**

  Read: `app/core/rule_classifier.py` → `classify_pm_items()` 입력/출력 인터페이스 파악

- [x] **Step 2: 실패하는 테스트 작성**

- [x] **Step 3: 실패 확인**

  Run: `python -m pytest tests/test_rule_classifier.py -v`
  Expected: 일부 또는 전체 PASS (이미 구현됨), 에러 없음

- [x] **Step 4: 실패하는 테스트 있으면 구현 수정 → PASS까지 반복**

- [x] **Step 5: 커밋**

  ```bash
  git add tests/test_rule_classifier.py
  git commit -m "test: RuleClassifier 단위 테스트 추가"
  ```

---

### Task 6: ChecklistBuilder 단위 테스트

**Files:**
- Create: `tests/test_checklist_builder.py`

- [x] **Step 1: checklist_builder.py 정독**

  Read: `app/core/checklist_builder.py`

- [x] **Step 2: 실패하는 테스트 작성**

- [x] **Step 3: 테스트 실행**

  Run: `python -m pytest tests/test_checklist_builder.py -v`

- [x] **Step 4: 실패하는 테스트 있으면 builder 수정 → PASS**

  특히 빈 리스트 처리 엣지케이스 확인.

- [x] **Step 5: 커밋**

  ```bash
  git add tests/test_checklist_builder.py
  git commit -m "test: ChecklistBuilder 단위 테스트 추가"
  ```

---

### Task 7: ExportEngine 단위 테스트

**Files:**
- Create: `tests/test_export_engine.py`

- [x] **Step 1: export_engine.py 정독**

  Read: `app/core/export_engine.py`

- [x] **Step 2: 실패하는 테스트 작성**

- [x] **Step 3: 테스트 실행**

  Run: `python -m pytest tests/test_export_engine.py -v`

- [x] **Step 4: 실패 시 export_engine.py 수정**

- [x] **Step 5: 커밋**

  ```bash
  git add tests/test_export_engine.py app/core/export_engine.py
  git commit -m "test: ExportEngine 단위 테스트 추가 + 파일명 sanitize 수정"
  ```

---

## Chunk 4: 에러 핸들링 강화

### Task 8: OCR 실패 엣지케이스 처리

**Files:** `app/core/ocr_engine.py`, `app/core/pdf_processor.py`

**배경:** 빈 PDF, 완전히 이미지로만 된 낮은 품질 PDF, 텍스트 0개 페이지에서 조용히 실패하는 케이스들이 있다.

- [x] **Step 1: 현재 예외 처리 파악**

  Read: `app/core/ocr_engine.py` → try/except 블록 목록 파악

- [x] **Step 2: 빈 페이지 처리 강화**

  `extract_text_from_pdf()` 내부에서 페이지별로 OCR 결과가 비어있을 때 `has_text=False`로 명확히 마킹하는 로직이 있는지 확인, 없으면 추가.

  ```python
  # 페이지 결과가 비어있으면 명시적 처리
  if not blocks:
      logger.warning(f"페이지 {page_num}: OCR 텍스트 추출 결과 없음")
      results.append(OCRPageResult(page=page_num, blocks=[], has_text=False))
      continue
  ```

- [x] **Step 3: PDF 로드 실패 처리**

  `pdf_processor.py`의 `load_pdf()` 에서 파일 손상/암호화 PDF에 대한 명시적 예외 처리:
  ```python
  except fitz.FileDataError as e:
      raise ValueError(f"PDF 파일이 손상되었거나 지원하지 않는 형식입니다: {e}") from e
  ```

- [x] **Step 4: 변경 후 import 확인**

  Run: `python -c "from app.core.ocr_engine import OCREngine; print('OK')"`

- [x] **Step 5: 커밋**

  ```bash
  git add app/core/ocr_engine.py app/core/pdf_processor.py
  git commit -m "fix: OCR 빈 페이지 및 PDF 로드 실패 엣지케이스 처리 강화"
  ```

---

### Task 9: Streamlit UI 에러 핸들링 강화

**Files:** `ui/streamlit_app.py`

**배경:** PM 추출 결과가 0개일 때, OCR이 완전히 실패할 때, API 키 없이 Gemini를 시도할 때 더 명확한 안내가 필요하다.

- [x] **Step 1: 현재 UI 에러 처리 파악**

  Read: `ui/streamlit_app.py` → 에러 표시 로직 파악

- [x] **Step 2: PM 추출 0개 케이스 처리**

  현재 `st.warning()`만 표시 → 아래 블록으로 교체:
  ```python
  if len(pm_items) == 0:
      st.error("⚠️ PM 점검 항목을 추출하지 못했습니다.")
      st.info("""
      **가능한 원인:**
      - 매뉴얼에 점검 관련 내용이 없거나 다른 언어로 작성됨
      - OCR 품질이 낮아 텍스트 인식 실패
      - 규칙 기반 분류기의 키워드와 매뉴얼 표현이 불일치

      **해결 방법:**
      - Gemini API를 사용해 AI 분류 시도 (사이드바에 API 키 입력)
      - 텍스트 미리보기에서 매뉴얼 내용 확인
      - 아래 데이터 에디터에서 항목을 직접 추가하세요
      """)
      # 빈 데이터 에디터로 수동 입력 허용
      st.session_state.pm_items = []
  ```

- [x] **Step 3: API 키 없이 Gemini 시도 방어**

  Stage 2 버튼 핸들러에서:
  ```python
  if not use_offline and not api_key:
      st.warning("🔑 Gemini API 키가 없습니다. 오프라인 규칙 기반 분류로 전환합니다.")
      use_offline = True
  ```

- [x] **Step 4: 업로드 파일 없이 1단계 실행 방어**

  ```python
  if uploaded_file is None:
      st.error("먼저 PDF 파일을 업로드해 주세요.")
      st.stop()
  ```

- [x] **Step 5: 테스트 (수동)**

  Streamlit 실행 후 각 엣지케이스 수동 확인.

- [x] **Step 6: 커밋**

  ```bash
  git add ui/streamlit_app.py
  git commit -m "fix: Streamlit UI 에러 핸들링 및 사용자 안내 강화"
  ```

---

## Chunk 5: UX 폴리싱

### Task 10: 진행 상태 표시 개선

**Files:** `ui/streamlit_app.py`

**배경:** PaddleOCR 초기화(~3-5초)와 Gemini API 호출 중 스피너만 있고 세부 진행 상황 표시가 없다.

- [ ] **Step 1: 현재 progress 표시 파악**

  Read: `ui/streamlit_app.py` → `st.spinner`, `st.progress` 사용 위치 파악

- [ ] **Step 2: 1단계 OCR 진행바 개선**

  ```python
  progress_bar = st.progress(0, text="PDF 분석 중...")

  def on_progress(current: int, total: int):
      pct = int(current / total * 100)
      progress_bar.progress(pct / 100, text=f"페이지 {current}/{total} 처리 중...")

  ocr_results = ocr_engine.extract_text_from_pdf(
      pdf_path=temp_path,
      progress_callback=on_progress,
  )
  progress_bar.progress(1.0, text="✅ 텍스트 추출 완료")
  ```

- [ ] **Step 3: 2단계 AI 분류 상태 표시**

  ```python
  with st.status("🤖 AI 분석 중...", expanded=True) as status:
      st.write("텍스트 필터링...")
      # ... classifier call ...
      st.write(f"✅ {len(pm_items)}개 PM 항목 추출 완료")
      status.update(label="AI 분석 완료", state="complete")
  ```

- [ ] **Step 4: 설비명 미입력 시 자동 기본값**

  ```python
  equipment_name = st.text_input("설비명", placeholder="예: CNC 선반 #1")
  if not equipment_name.strip():
      equipment_name = "설비"
  ```

- [ ] **Step 5: 커밋**

  ```bash
  git add ui/streamlit_app.py
  git commit -m "feat: OCR/AI 진행 상태 표시 개선 및 설비명 기본값 처리"
  ```

---

### Task 11: 통계 요약 개선 (Step 3)

**Files:** `ui/streamlit_app.py`

**배경:** Step 3 완료 후 통계 표시가 기본적이다. 시각적 요약을 개선한다.

- [ ] **Step 1: 현재 통계 표시 코드 확인**

  Read: `ui/streamlit_app.py` → Step 3 완료 후 표시 부분

- [ ] **Step 2: 메트릭 카드 추가**

  ```python
  col1, col2, col3, col4 = st.columns(4)
  col1.metric("총 점검 항목", stats["total_items"])
  col2.metric("점검 부위 수", len(stats.get("by_part", {})))
  col3.metric("점검 영역 수", len(stats.get("by_area", {})))
  col4.metric("저신뢰도 항목", stats.get("low_confidence_count", 0))
  ```

- [ ] **Step 3: 주기 분포 표 개선**

  ```python
  period_data = {
      "주기": ["일간", "월간", "분기", "반기", "연간"],
      "항목 수": [
          stats["by_period"].get("일", 0),
          stats["by_period"].get("월", 0),
          stats["by_period"].get("분기", 0),
          stats["by_period"].get("반기", 0),
          stats["by_period"].get("년", 0),
      ]
  }
  st.table(pd.DataFrame(period_data))
  ```

- [ ] **Step 4: 커밋**

  ```bash
  git add ui/streamlit_app.py
  git commit -m "feat: Step 3 통계 요약 메트릭 카드 및 분포 표 개선"
  ```

---

## Chunk 6: 로깅 전략 통일

### Task 12: 로깅 레벨 및 포맷 통일

**Files:** `app/core/*.py` 전체

**배경:** 각 모듈이 `logging.getLogger(__name__)`을 사용하지만 레벨과 포맷이 일관적이지 않다. 실행 시 어디서 무슨 일이 일어나는지 파악하기 어렵다.

- [ ] **Step 1: 각 파일의 로깅 현황 파악**

  Read: `app/core/ocr_engine.py`, `pm_classifier.py`, `rule_classifier.py`, `export_engine.py`
  → 현재 로그 메시지 확인

- [ ] **Step 2: 로깅 규칙 정의 및 적용**

  각 모듈에 다음 패턴으로 통일:
  ```python
  import logging
  logger = logging.getLogger(__name__)

  # DEBUG: 내부 처리 상세 (청크 크기, 페이지별 결과 등)
  # INFO:  중요 단계 완료 (파일 로드 완료, 항목 N개 추출 등)
  # WARNING: 폴백 발생, 저신뢰도, 빈 결과
  # ERROR: 예외 발생, 파일 저장 실패
  ```

- [ ] **Step 3: ocr_engine.py 로그 개선**

  - `DEBUG`: 각 페이지 OCR 결과 블록 수
  - `INFO`: 전체 완료 메시지 "총 N페이지, M개 블록 추출"
  - `WARNING`: 빈 페이지, 저신뢰도 블록 비율 높을 때

- [ ] **Step 4: pm_classifier.py 로그 개선**

  - `INFO`: 청크 처리 시작 "청크 N/M 처리 중..."
  - `INFO`: 완료 "총 N개 PM 항목 추출"
  - `WARNING`: 재시도 발생, fallback 전환
  - `ERROR`: API 실패

- [ ] **Step 5: run_pipeline.py에 로깅 기본 설정 추가**

  ```python
  logging.basicConfig(
      level=logging.INFO,
      format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
      datefmt="%H:%M:%S",
  )
  ```

- [ ] **Step 6: 커밋**

  ```bash
  git add app/core/ run_pipeline.py
  git commit -m "refactor: 로깅 레벨 및 포맷 전 모듈 통일"
  ```

---

## Chunk 7: 문서화

### Task 13: README.md 작성

**Files:**
- Create: `README.md`

- [ ] **Step 1: README.md 작성**

  ```markdown
  # TPM 기반 PM 체크리스트 자동화 시스템

  설비 매뉴얼(PDF)에서 예방 보전(PM) 점검 항목을 자동 추출하여
  현장 배포용 Excel 체크리스트로 변환하는 도구입니다.

  ## 주요 기능

  - **PDF 디지털화**: 텍스트 PDF + 스캔 PDF(PaddleOCR) 모두 지원
  - **AI 추출**: Google Gemini 2.5-Flash 기반 구조화 PM 항목 추출
  - **오프라인 모드**: API 없이도 규칙 기반 분류로 동작
  - **Jidoka 검증**: 현장 담당자가 AI 결과를 편집 후 최종 확정
  - **Excel 출력**: 주기별(일간/월간/분기/반기/연간) 시트 자동 생성

  ## 빠른 시작

  ### 사전 준비

  ```bash
  pip install -r requirements.txt
  cp .env.example .env
  # .env에 GEMINI_API_KEY 입력 (선택, 없으면 오프라인 모드)
  ```

  ### Streamlit UI 실행

  ```bash
  streamlit run ui/streamlit_app.py
  ```

  브라우저에서 `http://localhost:8501` 접속

  ### CLI 배치 처리

  ```bash
  python run_pipeline.py --pdf "매뉴얼.pdf" --equipment "CNC선반" [--offline]
  ```

  ## 3단계 워크플로우

  1. **디지털화** → PDF 업로드 → OCR 텍스트 추출
  2. **AI 분류 + 검증** → PM 항목 추출 → 편집기에서 수정
  3. **표준화** → Excel + Markdown 체크리스트 다운로드

  ## 환경 변수

  | 변수 | 설명 | 기본값 |
  |------|------|--------|
  | `GEMINI_API_KEY` | Gemini API 키 | (없으면 오프라인) |
  | `GEMINI_MODEL` | Gemini 모델명 | `gemini-2.5-flash` |
  | `OCR_DEFAULT_DPI` | OCR DPI | `200` |
  | `GEMINI_CHUNK_SIZE` | 청크당 페이지 수 | `5` |

  ## 프로젝트 구조

  ```
  app/
    core/        # PDF처리, OCR, AI분류, 체크리스트 빌더, Excel 내보내기
    config/      # area_taxonomy.json, settings.py
    models/      # Pydantic 스키마 (PMItem, OCRPageResult 등)
  ui/            # Streamlit 대시보드
  tests/         # 단위 테스트
  ```

  ## 테스트

  ```bash
  python -m pytest tests/ -v
  ```
  ```

- [ ] **Step 2: .env.example 보완**

  Read: `.env.example` → 새로 추가된 `GEMINI_CHUNK_SIZE`, `OCR_DEFAULT_DPI` 등 추가

- [ ] **Step 3: 커밋**

  ```bash
  git add README.md .env.example
  git commit -m "docs: README.md 작성 및 .env.example 업데이트"
  ```

---

### Task 14: VIBE_CODING_PROMPTS.md 업데이트 (선택)

**Files:** `reference/VIBE_CODING_PROMPTS.md`

- [ ] **Step 1: 파일 읽기**

  Read: `reference/VIBE_CODING_PROMPTS.md` → Anthropic/Claude API 언급 찾기

- [ ] **Step 2: stale 내용 수정**

  - "Anthropic API" → "Google Gemini API"로 수정
  - `claude-3-5-sonnet` 등의 레퍼런스 → `gemini-2.5-flash`로 수정

- [ ] **Step 3: 커밋**

  ```bash
  git add reference/VIBE_CODING_PROMPTS.md
  git commit -m "docs: VIBE_CODING_PROMPTS AI 모델 레퍼런스 Gemini로 업데이트"
  ```

---

## Chunk 8: 최종 검증 및 정리

### Task 15: 전체 테스트 실행 및 최종 커밋

- [ ] **Step 1: 전체 테스트 실행**

  Run: `python -m pytest tests/ -v --tb=short`
  Expected: ALL PASS (또는 xfail 허용)

- [ ] **Step 2: import 체크 (모든 모듈)**

  ```bash
  python -c "
  from app.core.ocr_engine import OCREngine
  from app.core.pm_classifier import PMClassifier
  from app.core.rule_classifier import RuleClassifier
  from app.core.checklist_builder import ChecklistBuilder
  from app.core.export_engine import ExportEngine
  from app.config.settings import OCR_DEFAULT_DPI
  print('All imports OK')
  "
  ```
  Expected: `All imports OK`

- [ ] **Step 3: CLI 파이프라인 dry-run**

  샘플 PDF 있으면:
  ```bash
  python run_pipeline.py --offline --pdf "scripts/sample_output.pdf" --equipment "테스트"
  ```
  없으면:
  ```bash
  python scripts/create_sample_manual.py
  python run_pipeline.py --offline --pdf outputs/sample_manual.pdf --equipment "테스트CNC"
  ```

- [ ] **Step 4: Streamlit 실행 확인 (수동)**

  ```bash
  streamlit run ui/streamlit_app.py
  ```
  브라우저에서 기본 흐름(PDF 없이 버튼 클릭 → 에러 표시) 확인

- [ ] **Step 5: git log 최종 확인**

  Run: `git log --oneline -15`
  Expected: 이 플랜의 모든 커밋이 깔끔하게 정리됨

- [ ] **Step 6: 최종 정리 커밋 (미완성 파일 없으면 불필요)**

  ```bash
  git status
  # 미커밋 파일 있으면 추가 커밋
  ```

---

## 실행 우선순위 요약

| 순서 | Task | 예상 시간 | 의존성 |
|------|------|---------|--------|
| 1 | Task 1: git 커밋 | 5분 | 없음 |
| 2 | Task 2: 중복 코드 제거 | 15분 | Task 1 |
| 3 | Task 3: settings.py | 30분 | Task 2 |
| 4 | Task 4: conftest | 20분 | Task 3 |
| 5 | Task 5: RuleClassifier 테스트 | 30분 | Task 4 |
| 6 | Task 6: Builder 테스트 | 30분 | Task 4 |
| 7 | Task 7: Export 테스트 | 40분 | Task 4 |
| 8 | Task 8: OCR 에러 핸들링 | 30분 | Task 3 |
| 9 | Task 9: UI 에러 핸들링 | 30분 | Task 8 |
| 10 | Task 10: 진행 표시 개선 | 20분 | Task 9 |
| 11 | Task 11: 통계 개선 | 15분 | Task 10 |
| 12 | Task 12: 로깅 통일 | 30분 | Task 3 |
| 13 | Task 13: README | 20분 | 없음 (병렬 가능) |
| 14 | Task 14: VIBE 문서 | 10분 | 없음 (병렬 가능) |
| 15 | Task 15: 최종 검증 | 20분 | 모두 |

**총 예상 작업: ~6시간 (병렬화 시 3-4시간)**

---

## 범위 외 (이번 플랜 제외)

- **FastAPI 백엔드 완성**: 별도 플랜으로 진행 권장 (비동기 job queue, WebSocket 상태 알림 등 복잡도 높음)
- **데이터베이스 연동**: PostgreSQL + Redis (배포 환경 결정 후 별도 진행)
- **멀티유저 지원**: 위 두 항목 선결 필요
- **비동기 OCR**: asyncio 전환 (Streamlit 제약으로 별도 아키텍처 필요)
- **중국어/일본어 지원**: PaddleOCR 모델 추가 로드 필요
