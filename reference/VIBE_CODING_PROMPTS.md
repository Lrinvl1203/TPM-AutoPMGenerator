# PM Checklist Automator — 바이브코딩 프롬프트 모음

> **사용법**: 각 Phase를 순서대로 AI 코딩 어시스턴트(Cursor, Windsurf, Claude Code)에 붙여넣기.  
> 각 Phase 완료 후 다음 단계 진행. 중간에 오류 발생 시 오류 메시지와 함께 재입력.

---

## ✅ Phase 0: 프로젝트 초기화

```
다음 스펙으로 Python 프로젝트를 초기화해줘.

프로젝트명: pm-checklist-automator
Python: 3.11
패키지 매니저: uv (없으면 pip + venv)

디렉토리 구조:
pm-checklist-automator/
├── app/
│   ├── __init__.py
│   ├── api/
│   │   ├── __init__.py
│   │   └── routes.py
│   ├── core/
│   │   ├── __init__.py
│   │   ├── ocr_engine.py       # PaddleOCR 래퍼
│   │   ├── pdf_processor.py    # PDF → 이미지 변환
│   │   ├── pm_classifier.py    # Claude API 기반 PM 분류
│   │   ├── checklist_builder.py # 체크리스트 생성
│   │   └── export_engine.py    # 다형식 출력
│   ├── models/
│   │   ├── __init__.py
│   │   └── schemas.py          # Pydantic 데이터 모델
│   └── db/
│       ├── __init__.py
│       └── database.py
├── ui/
│   └── streamlit_app.py        # Streamlit UI
├── tests/
│   └── test_pipeline.py
├── docker-compose.yml
├── Dockerfile
├── requirements.txt
└── .env.example

requirements.txt 내용:
paddleocr==2.8.1
paddlepaddle==2.6.1  # CPU 버전
PyMuPDF==1.24.0
pdf2image==1.17.0
anthropic==0.40.0
fastapi==0.115.0
uvicorn==0.32.0
pydantic==2.9.0
sqlalchemy==2.0.36
psycopg2-binary==2.9.10
redis==5.1.1
openpyxl==3.1.5
python-docx==1.1.2
reportlab==4.2.5
streamlit==1.40.0
pandas==2.2.3
Pillow==11.0.0
python-multipart==0.0.18
python-dotenv==1.0.1

.env.example:
ANTHROPIC_API_KEY=your_key_here
DATABASE_URL=postgresql://user:password@localhost:5432/pm_checklist
REDIS_URL=redis://localhost:6379/0
UPLOAD_DIR=./uploads
OUTPUT_DIR=./outputs
MAX_FILE_SIZE_MB=200

모든 파일에 타입 힌트 포함, 한국어 docstring 작성.
```

---

## ✅ Phase 1: PDF 처리 + PaddleOCR 엔진

```
app/core/pdf_processor.py 와 app/core/ocr_engine.py 를 구현해줘.

### pdf_processor.py 요구사항
- PDFProcessor 클래스 구현
- 메서드:
  - load_pdf(file_path: str) -> dict: 메타데이터 반환 (총 페이지 수, 제목, 작성자 등)
  - pdf_to_images(file_path: str, dpi: int = 200) -> list[PIL.Image]: 페이지별 이미지 변환
    - PyMuPDF(fitz) 사용, fitz.open() → page.get_pixmap(matrix=fitz.Matrix(dpi/72, dpi/72))
  - extract_text_native(file_path: str) -> list[dict]: 텍스트 레이어가 있는 PDF는 직접 추출
    - 반환: [{"page": 1, "text": "...", "has_text": True}, ...]
  - is_scanned_pdf(file_path: str) -> bool: 텍스트 레이어 유무 판별

### ocr_engine.py 요구사항
- OCREngine 클래스 구현
- PaddleOCR 초기화: PaddleOCR(use_angle_cls=True, lang='korean', show_log=False)
- 메서드:
  - extract_text_from_image(image: PIL.Image) -> list[dict]:
    - 반환 형식: [{"text": "내용", "confidence": 0.95, "bbox": [[x1,y1],[x2,y2],[x3,y3],[x4,y4]]}, ...]
  - extract_text_from_pdf(file_path: str) -> list[dict]:
    - 텍스트 PDF: extract_text_native 우선 사용
    - 스캔 PDF: 이미지 변환 후 OCR
    - 반환: [{"page": 1, "blocks": [{"text": "...", "confidence": 0.95, "bbox": [...]}]}, ...]
  - extract_tables_from_image(image: PIL.Image) -> list[dict]:
    - PaddleOCR 구조 분석으로 표 인식
    - 반환: [{"rows": [["셀1", "셀2"], ["셀3", "셀4"]], "page": 1}]

에러 처리: 신뢰도 0.7 미만 블록에 "low_confidence": True 플래그 추가.
단위 테스트 코드도 tests/test_ocr.py에 작성해줘 (pytest, Mock PDF 사용).
```

---

## ✅ Phase 2: Claude API 기반 PM 분류 엔진

```
app/core/pm_classifier.py 를 구현해줘.

### PMClassifier 클래스 요구사항

의존성:
- anthropic 라이브러리
- app/models/schemas.py의 PMItem Pydantic 모델

PMItem 스키마 (schemas.py에 먼저 정의):
```python
from pydantic import BaseModel, Field
from enum import Enum
from typing import Optional
import uuid

class PMPeriod(str, Enum):
    DAILY = "일"
    MONTHLY = "월"
    QUARTERLY = "분기"
    SEMI_ANNUAL = "반기"
    ANNUAL = "년"

class PMItem(BaseModel):
    item_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    item_name: str
    period: PMPeriod
    equipment_part: str        # 부위 (예: 주축, 오일탱크)
    area: str                  # 영역 (예: 기계계통, 전기계통, 유압계통, 공압계통, 냉각계통)
    method: str                # 점검 방법 (예: 육안점검, 측정, 교체, 청소)
    standard_value: Optional[str] = None
    source_page: Optional[int] = None
    confidence: float = 1.0
    note: Optional[str] = None
```

PMClassifier 메서드:

1. classify_pm_items(ocr_results: list[dict]) -> list[PMItem]
   - OCR 결과를 청크로 분할 (페이지 5개씩)
   - 각 청크를 Claude API에 전송
   - 반환된 JSON 파싱 후 PMItem 리스트 생성

2. _build_system_prompt() -> str:
   시스템 프롬프트 내용:
   """
   당신은 제조업 설비 유지보수 전문가입니다. 
   주어진 설비 매뉴얼 텍스트에서 PM(예방보전) 관련 항목을 추출합니다.
   
   PM 항목 판별 기준:
   - 정기 점검, 교체, 청소, 측정, 조정, 윤활 등의 유지보수 행위
   - "~주기로", "매~", "~마다", "~개월", "정기적으로" 등의 주기 표현
   - 점검 항목 표(테이블)의 내용
   
   주기 분류 기준:
   - 일(Daily): 매일, 매 근무 시작, 8시간마다
   - 월(Monthly): 매월, 1개월, 30일마다
   - 분기(Quarterly): 3개월, 분기별, 1/4년
   - 반기(Semi-annual): 6개월, 반년, 2/4분기
   - 년(Annual): 12개월, 매년, 연간, 오버홀
   
   영역(area) 분류:
   - 기계계통: 베드, 주축, 이송계, 척, 공구대
   - 전기계통: 전원, 케이블, 전기함, 센서, 제어판
   - 유압계통: 유압펌프, 오일탱크, 유압실린더, 배관
   - 공압계통: 에어필터, 공압밸브, 실린더
   - 냉각계통: 쿨런트탱크, 필터, 펌프, 노즐
   - 기타: 위 분류에 해당하지 않는 항목
   
   반드시 다음 JSON 배열 형식으로만 응답하세요. 다른 텍스트 없이 JSON만:
   [
     {
       "item_name": "항목명",
       "period": "일|월|분기|반기|년",
       "equipment_part": "부위명",
       "area": "영역명",
       "method": "점검방법",
       "standard_value": "기준값 또는 null",
       "source_page": 페이지번호,
       "confidence": 0.0~1.0,
       "note": "특이사항 또는 null"
     }
   ]
   """

3. _extract_json_from_response(text: str) -> list[dict]:
   - JSON 파싱, 오류 시 빈 리스트 반환

Claude API 호출 설정:
- model: "claude-sonnet-4-20250514"
- max_tokens: 4096
- 재시도 로직: 최대 3회, 지수 백오프 (1s, 2s, 4s)

tests/test_classifier.py에 단위 테스트 작성 (Anthropic API mock 사용).
```

---

## ✅ Phase 3: 체크리스트 빌더

```
app/core/checklist_builder.py 를 구현해줘.

### ChecklistBuilder 클래스 요구사항

입력: list[PMItem] (Phase 2에서 생성된 PM 항목 리스트)

메서드:

1. build_by_period(items: list[PMItem]) -> dict[str, list[PMItem]]:
   - 주기별로 그룹핑
   - 반환: {"일": [...], "월": [...], "분기": [...], "반기": [...], "년": [...]}
   - 각 그룹 내에서 area → equipment_part → item_name 순으로 정렬

2. build_by_part(items: list[PMItem]) -> dict[str, list[PMItem]]:
   - equipment_part로 그룹핑 후 정렬
   - 반환: {"주축": [...], "오일탱크": [...], ...}
   - 각 그룹 내에서 period(일<월<분기<반기<년) → item_name 순 정렬

3. build_by_area(items: list[PMItem]) -> dict[str, list[PMItem]]:
   - area로 그룹핑
   - 반환: {"기계계통": [...], "전기계통": [...], ...}
   - 고정 순서: 기계→전기→유압→공압→냉각→기타

4. build_matrix(items: list[PMItem]) -> dict:
   - 부위(행) × 주기(열) 교차 매트릭스
   - 반환: {"parts": ["주축", "오일탱크"], "periods": ["일","월","분기","반기","년"], "matrix": {"주축": {"일": [item1, item2], "월": [item3]}}}

5. get_statistics(items: list[PMItem]) -> dict:
   - 총 항목 수, 주기별 항목 수, 영역별 항목 수, 부위 수 반환

체크리스트 행 포맷 (각 PMItem을 행으로 변환):
[No, 점검항목, 점검방법, 기준값, 점검결과(빈칸), 비고, 담당자(빈칸), 날짜(빈칸)]
```

---

## ✅ Phase 4: 출력 엔진 (Excel + Word)

```
app/core/export_engine.py 를 구현해줘.

### ExportEngine 클래스

#### Excel 출력 (generate_excel)
입력: manual_name: str, equipment_name: str, all_items: list[PMItem]
출력: bytes (xlsx 파일)

openpyxl로 다음 시트 구성:
1. "요약" 시트: 설비명, 매뉴얼명, 생성일, 총 PM 항목 수, 주기별 항목 수 표
2. "일간 PM" 시트 (일 주기 항목)
3. "월간 PM" 시트 (월 주기 항목)
4. "분기 PM" 시트 (분기 주기 항목)
5. "반기 PM" 시트 (반기 주기 항목)
6. "연간 PM" 시트 (연 주기 항목)
7. "전체 목록" 시트 (모든 항목)

각 PM 시트 컬럼:
A: No. (숫자, 너비 6)
B: 영역 (너비 15)
C: 부위 (너비 18)
D: 점검 항목 (너비 35)
E: 점검 방법 (너비 18)
F: 기준값 (너비 20)
G: 점검 결과 (너비 12, 연한 노란색 배경)
H: 비고 (너비 20)
I: 담당자 (너비 12, 연한 파란색 배경)
J: 점검일 (너비 14, 연한 파란색 배경)

스타일:
- 헤더 행: 진한 파란색 배경(1A3A5C), 흰색 글씨, 굵게
- 영역이 바뀔 때마다 연한 파란색 구분선
- 행 높이 22px
- 테두리: 전체 셀 얇은 선

#### Word 출력 (generate_word)
입력: manual_name: str, equipment_name: str, all_items: list[PMItem]
출력: bytes (docx 파일)

python-docx로 구성:
1. 표지: 설비명, "PM 체크리스트", 생성일
2. 목차
3. 각 주기별 섹션 (H1: "일간 PM 체크리스트" 등)
4. 섹션 내 부위별 소제목 (H2)
5. 각 항목을 표로 구성 (컬럼: No/점검항목/방법/기준값/결과/비고)

에러 처리: 항목이 없는 시트/섹션은 "해당 주기의 PM 항목이 없습니다." 안내 문구 삽입.
반환 타입은 BytesIO로.
```

---

## ✅ Phase 5: FastAPI 백엔드

```
app/api/routes.py 와 app/main.py 를 구현해줘.

### FastAPI 앱 구성

엔드포인트:

1. POST /api/manuals/upload
   - multipart/form-data로 PDF 파일 + equipment_name(str) 수신
   - 파일 저장 → 백그라운드 태스크로 처리 시작
   - 응답: {"manual_id": "uuid", "status": "processing", "message": "처리를 시작했습니다."}

2. GET /api/manuals/{manual_id}/status
   - 처리 상태 반환: {"status": "processing|completed|failed", "progress": 0~100, "message": "OCR 처리 중... (23/50 페이지)"}
   - 상태는 메모리 딕셔너리로 관리 (MVP용, 추후 Redis 교체)

3. GET /api/manuals/{manual_id}/pm-items
   - 추출된 PM 항목 목록 반환
   - 쿼리 파라미터: period(선택), area(선택), part(선택)

4. PATCH /api/pm-items/{item_id}
   - PM 항목 수정 (item_name, period, equipment_part, area, method, standard_value, note)
   - 인메모리 데이터 업데이트

5. POST /api/checklists/generate
   - Body: {"manual_id": "uuid", "format": "excel|word|pdf", "view_type": "period|part|area|all"}
   - 체크리스트 생성 후 파일 반환 (StreamingResponse)

6. GET /api/manuals/{manual_id}/statistics
   - 항목 통계 반환

처리 파이프라인 (백그라운드 태스크):
async def process_manual(manual_id, file_path, equipment_name):
    1. PDFProcessor.pdf_to_images() → 페이지 이미지
    2. OCREngine.extract_text_from_pdf() → OCR 결과  
    3. PMClassifier.classify_pm_items() → PM 항목
    4. 결과를 인메모리 저장소(manual_store dict)에 저장
    5. 상태를 "completed"로 업데이트

CORS 설정: 모든 origin 허용 (개발용)
파일 저장 경로: 환경변수 UPLOAD_DIR, OUTPUT_DIR 사용
```

---

## ✅ Phase 6: Streamlit UI

```
ui/streamlit_app.py 를 구현해줘.

### Streamlit 앱 전체 구성

페이지 설정:
- 타이틀: "🔧 PM Checklist Automator"
- 레이아웃: wide
- 사이드바: 설비 정보 입력

### 사이드바
- 설비명 입력 (text_input)
- 설비 모델명 입력 (text_input)
- 제조사 입력 (text_input)

### 메인 화면 (탭 구성)

탭1: 📤 매뉴얼 업로드
- st.file_uploader (PDF, 최대 200MB, 복수 파일 가능)
- "분석 시작" 버튼
- 진행 상황: st.progress + st.status 위젯
- 처리 완료 후: 추출 통계 (총 N개 PM 항목, 주기별 분포 bar chart)

탭2: 📋 PM 항목 검토
- 필터: 주기 (multiselect), 영역 (multiselect), 신뢰도 (slider 0.0~1.0)
- st.data_editor로 편집 가능한 테이블 표시
- 낮은 신뢰도 행은 빨간 배경 하이라이트
- 항목 추가 버튼 (빈 행 삽입)

탭3: 👁 체크리스트 미리보기
- 뷰 타입 선택 (radio: 주기별 / 부위별 / 영역별)
- 선택에 따라 st.expander로 각 그룹 펼쳐서 표시
- 각 그룹 내 항목은 st.dataframe으로 표시

탭4: 📥 다운로드
- 출력 포맷 선택 (checkbox: Excel, Word, PDF)
- "체크리스트 생성 및 다운로드" 버튼
- 각 포맷별 st.download_button

백엔드 연결:
- FastAPI URL: 환경변수 API_URL (기본값: http://localhost:8000)
- requests 라이브러리로 API 호출
- st.session_state로 manual_id, pm_items 상태 관리

에러 처리: API 연결 실패 시 st.error로 안내, 폴링은 time.sleep(2) + st.rerun() 사용.
```

---

## ✅ Phase 7: Docker 설정

```
Docker Compose로 전체 스택을 실행할 수 있게 설정해줘.

### docker-compose.yml 구성

서비스:
1. api: FastAPI 앱
   - Dockerfile 빌드
   - 포트: 8000:8000
   - 환경변수: .env 파일 참조
   - 볼륨: ./uploads:/app/uploads, ./outputs:/app/outputs

2. ui: Streamlit 앱
   - 같은 Dockerfile 또는 별도
   - 포트: 8501:8501
   - 명령어: streamlit run ui/streamlit_app.py

3. db: PostgreSQL 14 (선택, MVP는 인메모리로 대체 가능)
   - 포트: 5432:5432
   - 초기화 SQL 포함

### Dockerfile 요구사항
- Base: python:3.11-slim
- PaddleOCR GPU/CPU 선택 가능 (ARG USE_GPU=false)
- poppler-utils, libGL 등 OCR 의존성 설치
- 멀티스테이지 빌드로 이미지 크기 최소화

### Makefile 명령어
- make build: Docker 이미지 빌드
- make up: 서비스 시작
- make down: 서비스 종료
- make logs: 로그 확인
- make test: 테스트 실행
- make dev: 로컬 개발 서버 시작 (Docker 없이)

README.md 도 작성해줘:
- 설치 방법 (Docker / 로컬 두 가지)
- 사용 방법 (스크린샷 플레이스홀더 포함)
- 환경 변수 설명
- 지원 포맷 설명
```

---

## ✅ Phase 8: 테스트 및 품질 검증

```
다음 테스트와 품질 검증 코드를 작성해줘.

### 1. 정확도 평가 스크립트 (scripts/evaluate_accuracy.py)
- 테스트 PDF 폴더를 입력받아 전체 파이프라인 실행
- 수동 레이블 JSON과 자동 추출 결과 비교
- F1-Score, Precision, Recall 계산
- 주기 분류 정확도, 영역 분류 정확도 별도 출력
- 결과를 evaluation_report.json으로 저장

수동 레이블 포맷 (ground_truth.json):
{
  "manual_name": "CNC_머시닝센터_매뉴얼.pdf",
  "pm_items": [
    {"item_name": "오일레벨 확인", "period": "일", "equipment_part": "오일탱크", "area": "유압계통"}
  ]
}

### 2. 통합 테스트 (tests/test_integration.py)
- 샘플 PDF(테스트용 간단한 PDF 생성 또는 reportlab으로 생성)로 전체 파이프라인 테스트
- API 엔드포인트 테스트 (httpx + pytest-asyncio)
- Excel/Word 출력 파일 검증 (파일 열리는지, 시트/섹션 있는지)

### 3. 성능 벤치마크 (scripts/benchmark.py)
- 페이지 수별(10/25/50/100) 처리 시간 측정
- OCR 단계, 분류 단계, 출력 단계 별도 측정
- 결과를 benchmark_results.csv로 저장

pytest 설정 파일(pytest.ini)도 포함:
- 비동기 테스트 지원
- 커버리지 80% 목표
```

---

## 🔧 트러블슈팅 프롬프트

### OCR 품질 개선
```
PaddleOCR에서 한글 인식률이 낮을 때 개선 방법:

현재 코드에서 다음을 개선해줘:
1. 전처리 파이프라인 추가:
   - OpenCV로 이미지 이진화 (Otsu threshold)
   - 노이즈 제거 (morphological operations)
   - 대비 향상 (CLAHE)
2. DPI를 150에서 300으로 상향
3. PaddleOCR det_db_thresh를 0.3으로 낮춰 작은 텍스트도 인식
4. 인식 결과 후처리: 단어 단위 줄바꿈 복원 알고리즘 추가
```

### Claude API 비용 최적화
```
Claude API 호출 비용을 줄이는 방법으로 pm_classifier.py를 최적화해줘:

1. 청크 크기 조정: 페이지 5개 → 토큰 수 기준으로 동적 청크 (max 8000 tokens per chunk)
2. 사전 필터링: "점검", "교체", "청소", "윤활", "주기" 키워드가 포함된 블록만 API 전송
3. 캐싱: 동일 텍스트 블록의 재처리 방지 (텍스트 해시 기반 로컬 캐시)
4. 배치 처리: 여러 청크를 단일 API 호출로 처리
예상 비용 절감: 40~60%
```

### 복잡한 표 인식
```
설비 매뉴얼의 PM 점검 표가 복잡한 경우 (병합 셀, 다단 헤더 등) 처리를 개선해줘:

ocr_engine.py의 extract_tables_from_image 메서드에:
1. PaddleOCR Structure Recognition 모델 추가 사용
2. 병합 셀 처리: colspan/rowspan 추적
3. 표 헤더 자동 감지: 첫 행 또는 짙은 배경 행을 헤더로 인식
4. 표를 마크다운 형식으로 변환 후 PM Classifier에 전달
   (| 헤더1 | 헤더2 | \n | 값1 | 값2 | 형식)
```

---

## 📊 샘플 데이터 생성 프롬프트

```
테스트용 샘플 설비 매뉴얼 PDF를 reportlab으로 생성해줘.

scripts/create_sample_manual.py 파일 작성:

내용 구성:
1. 표지: "CNC 수직 머시닝센터 유지보수 매뉴얼 V2.1"
2. 목차
3. Chapter 3: 정기 점검 및 유지보수
   3.1 일상 점검 항목 (표 형식):
   - 주축 오일레벨 확인 (육안점검, 매일)
   - 냉각수 탱크 레벨 확인 (육안점검, 매일)
   - 공압 압력 확인 (압력계 확인, 5~7 kgf/cm², 매일)
   - 칩 컨베이어 작동 확인 (작동점검, 매일)
   
   3.2 월간 점검 항목 (표 형식):
   - 주축 윤활유 보충 (ISO VG68, 월 1회)
   - ATC 매거진 체인 장력 확인 (월 1회)
   - 전기함 팬 필터 청소 (월 1회)
   - 이송계 볼스크류 윤활 (그리스, 월 1회)
   
   3.3 분기 점검 항목 (리스트 형식):
   - 유압 오일 오염도 측정 (NAS 7등급 이하, 분기 1회)
   - 냉각수 농도 확인 (3~5%, 분기 1회)
   - 각 축 백래시 측정 (0.005mm 이하, 분기 1회)
   
   3.4 연간 점검 항목 (리스트 형식):
   - 주축 베어링 예압 확인 (년 1회, 전문 기술자)
   - 유압 오일 전량 교체 (ISO VG46, 년 1회)
   - 서보 드라이브 파라미터 백업 (년 1회)

4. 한국어 텍스트, 실제 매뉴얼과 유사한 레이아웃으로 작성
출력 경로: tests/fixtures/sample_cnc_manual.pdf
```

---

*MUMULAB PM Checklist Automator — Vibe Coding Prompts v1.0*
