# PM Checklist Automator (TPM AI)

생성형 AI와 OCR을 활용하여 설비 매뉴얼(PDF)에서 예방보전(PM) 항목을 자동 추출하고 엑셀 체크리스트로 변환하는 도구입니다. 공장 현장에서의 TPM(Total Productive Maintenance) 활동을 돕고, Jidoka(지능화) 원칙에 따라 사용자 검증 단계를 포함하여 데이터의 정확성을 보장합니다.

## ✨ 주요 기능
- **다양한 PDF 포맷 지원**: 텍스트 레이어가 있는 깨끗한 PDF 뿐만 아니라, 폰트가 깨지거나 스캔본인 PDF에 대해서도 PaddleOCR을 통해 정확한 텍스트를 추출합니다.
- **LLM 기반 지능형 PM 추출**: Gemini API 형(Context) 인지와 함께 매뉴얼 본문에서 예방보전 주기(일, 월, 분기, 반기, 년), 영역, 점검 방법을 자동으로 구조화하여 추출합니다.
- **오프라인 융합 분류 파이프라인**: API 응답이 실패하거나 비용 문제가 있을 때를 대비한 Regex 및 규칙 기반 오프라인(Rule-based) 폴백 분류기가 내장되어 있습니다.
- **Human-in-the-loop 검수 (Streamlit)**: 추출된 항목들을 사용자가 직접 바로잡고(수정/추가/삭제) 승인할 수 있는 데이터 에디터를 제공합니다.
- **현장 배포용 Excel 즉시 생성**: 엑셀 양식으로 정리된(주기별/영역별 색상 구분 마킹) 체크리스트와 마크다운 문서를 다운로드 제공하여, 즉시 유지보수 현장에 배포 가능합니다.

## 🚀 시작하기

### ⚙️ 요구 구동 환경
- Python 3.11 이상
- 지원 OS: Windows, macOS, Linux

### 📦 설치 방법
1. 저장소를 클론합니다.
```bash
git clone https://github.com/Lrinvl1203/TPM-AutoPMGenerator.git
cd TPM-AutoPMGenerator
```

2. 가상환경을 생성하고 패키지를 설치합니다.
```bash
python -m venv venv
# Windows의 경우
venv\Scripts\activate
# macOS/Linux의 경우
source venv/bin/activate

pip install -r requirements.txt
```

3. 환경변수 파일(`.env`)을 생성하고 Gemini API 키를 입력합니다 (앱의 관리 메뉴에서도 입력 가능합니다).
```env
GEMINI_API_KEY=your_api_key_here
```

### 🏃 앱 실행하기
```bash
python run_pipeline.py
```
브라우저에서 `http://localhost:8501` 이 자동으로 열립니다.

## 🛠️ 프로젝트 구조
- `app/core/`: OCR, PDF 프로세싱, AI 분류, 상태 관리 로직 
- `app/config/`: 상수, 로거 구성 및 설정 (`settings.py`, `logger.py`)
- `app/models/`: Pydantic 기반 데이터 검증 스키마
- `ui/`: Streamlit 기반 프론트엔드 및 데이터 에디터 로직
- `tests/`: Pytest 프레임워크를 적용한 단위 테스트 및 fixtures 코어 로직 검증

## 🤝 라이선스
본 프로젝트의 사용 및 배포는 작성자(Lrinvl1203)의 허락을 구해야 합니다.
