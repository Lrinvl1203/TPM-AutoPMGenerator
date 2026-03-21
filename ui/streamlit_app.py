"""
Streamlit Web UI (MVP-2 TPM Edition)

LEAN과 TPM의 8대 기둥(특히 자주보전, 계획보전) 사상을 반영하여,
인간과 기계의 협업(Jidoka)을 통해 완벽한 품질의 PM 점검표를 생성하는 3단계 워크플로우 대시보드입니다.
"""

import os
import sys
import time
from pathlib import Path
import pandas as pd

import streamlit as st

# 모듈 경로 추가
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.core.pdf_processor import PDFProcessor
from app.core.ocr_engine import OCREngine
from app.core.pm_classifier import PMClassifier
from app.core.rule_classifier import RuleClassifier
from app.core.checklist_builder import ChecklistBuilder
from app.core.export_engine import ExportEngine
from app.models.schemas import PMItem
import json

# PM 키워드 로드
config_path = Path(__file__).parent.parent / "app" / "config" / "area_taxonomy.json"
try:
    with open(config_path, "r", encoding="utf-8") as f:
        TAXONOMY_CONFIG = json.load(f)
    PM_KEYWORDS = TAXONOMY_CONFIG.get("PM_판별_키워드", [])
except Exception:
    PM_KEYWORDS = ["점검", "교체", "청소", "윤활", "주기", "매월", "매년"]

# 페이지 설정
st.set_page_config(
    page_title="TPM PM Checklist Automator",
    page_icon="🏭",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Custom CSS
st.markdown("""
<style>
    .main-header {
        font-size: 2.2rem;
        font-weight: 800;
        color: #1A3A5C;
        margin-bottom: 0.5rem;
    }
    .sub-header {
        font-size: 1.1rem;
        color: #555555;
        margin-bottom: 2rem;
    }
    .step-header {
        background-color: #F0F4F8;
        padding: 1rem;
        border-radius: 0.5rem;
        margin-top: 2rem;
        margin-bottom: 1rem;
        border-left: 5px solid #1A3A5C;
    }
    .stButton>button {
        background-color: #1A3A5C;
        color: white;
        font-weight: bold;
    }
    .stButton>button:hover {
        background-color: #2c5282;
        color: white;
    }
</style>
""", unsafe_allow_html=True)

def init_session_state():
    """세션 상태 초기화"""
    defaults = {
        'step1_done': False,
        'step2_started': False,
        'step2_done': False,
        'ocr_results': None,
        'pm_items': None,
        'metadata': None,
        'pdf_path': None,
        'job_time': None,
        'equipment_name': "",
        'uploaded_filename': None,
        'editor_df': None,
        'final_pm_df': None,
        'excel_path': None,
        'md_path': None,
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value

def reset_pipeline():
    """새로운 문서 업로드 시 파이프라인 리셋"""
    st.session_state.step1_done = False
    st.session_state.step2_started = False
    st.session_state.step2_done = False
    st.session_state.ocr_results = None
    st.session_state.pm_items = None
    st.session_state.editor_df = None
    st.session_state.final_pm_df = None
    st.session_state.excel_path = None
    st.session_state.md_path = None

def main():
    init_session_state()

    st.markdown('<div class="main-header">🏭 TPM 기반 PM 점검표 스튜디오</div>', unsafe_allow_html=True)
    st.markdown('<div class="sub-header">LEAN 철학(낭비 제거)과 Jidoka(인간-기계 협업)를 통해 현장에 즉시 배포 가능한 결함 제로의 예방보전(PM) 체크리스트를 만듭니다.</div>', unsafe_allow_html=True)

    # 사이드바 (설정)
    with st.sidebar:
        st.header("⚙️ 환경 설정")
        api_key = st.text_input("Gemini API Key (선택)", type="password", help="강력한 AI 분류를 위한 키입니다. 없으면 규칙 기반으로 동작합니다.")
        st.divider()
        st.markdown("### 고급 옵션")
        use_offline = st.checkbox("강제 오프라인 모드 작동 (규칙 기반)", value=False)
        st.info("💡 **LEAN Guide:** 각 단계를 차례대로 눈으로 직접 확인해야만 다음 단계로 넘어갈 수 있는 Jidoka(자동화) 시스템이 적용되어 있습니다.")
        if st.button("초기화 (Reset Pipeline)"):
            reset_pipeline()
            st.rerun()

    outputs_dir = Path("./outputs")
    outputs_dir.mkdir(exist_ok=True)
    uploads_dir = Path("./uploads")
    uploads_dir.mkdir(exist_ok=True)

    # =========================================================================
    # Step 1: 설비 매뉴얼 디지털화 (현상 파악 - Genchi Genbutsu)
    # =========================================================================
    st.markdown('<div class="step-header"><h3>🟡 Step 1: 설비 매뉴얼 디지털화 (현상 파악 - Genchi Genbutsu)</h3><p style="margin:0;color:#555;">비정형 문서(종이/PDF) 내에 잠든 데이터를 가공할 수 있도록 OCR 처리하여 눈에 띄게 시각화합니다.</p></div>', unsafe_allow_html=True)
    
    col1_1, col1_2 = st.columns([1, 1])
    
    with col1_1:
        uploaded_file = st.file_uploader("현장의 설비 유지보수 매뉴얼(PDF)을 업로드하세요", type=["pdf"], key="pdf_uploader")
        
        # 새 파일이 들어오면 리셋
        if uploaded_file and (st.session_state.uploaded_filename != uploaded_file.name):
            reset_pipeline()
            st.session_state.uploaded_filename = uploaded_file.name
            
        st.session_state.equipment_name = st.text_input("설비명 기입 (예: MCT, 사출기 등)", value=st.session_state.equipment_name)

    with col1_2:
        if uploaded_file and st.session_state.equipment_name:
            if not st.session_state.step1_done:
                if st.button("1단계: 문서 스캔 및 데이터화 실행", type="primary"):
                    job_time = time.strftime("%Y%m%d_%H%M%S")
                    st.session_state.job_time = job_time
                    pdf_path = uploads_dir / f"job_{job_time}_{uploaded_file.name}"
                    
                    with open(pdf_path, "wb") as f:
                        f.write(uploaded_file.getbuffer())
                    st.session_state.pdf_path = str(pdf_path)

                    with st.spinner("문서 전체를 스캔 중입니다... (OCR Extract)"):
                        pdf_processor = PDFProcessor()
                        st.session_state.metadata = pdf_processor.load_pdf(str(pdf_path))
                        
                        ocr_engine = OCREngine()
                        ocr_results = ocr_engine.extract_text_from_pdf(str(pdf_path))
                        
                        st.session_state.ocr_results = ocr_results
                        st.session_state.step1_done = True
                    st.rerun()
            else:
                st.success("✅ Step 1 스캔 완료")
                
                # 텍스트 결합 로직
                all_blocks = []
                for page in st.session_state.ocr_results:
                    page_text = f"--- [Page {page.page}] ---\n"
                    page_text += "\n".join([b.text for b in page.blocks if b.text])
                    all_blocks.append(page_text)
                final_text = "\n\n".join(all_blocks)
                
                with st.expander("👀 추출된 전체 텍스트 원본 샘플 미리보기", expanded=False):
                    st.text_area("OCR Data (기계가 읽은 문서 원본)", final_text, height=200, disabled=True)
                
                # 옵션: 원본 텍스트 다운로드 (사용자가 원할 경우)
                export_filename = f"Extracted_Text_{st.session_state.job_time}.txt"
                export_path = outputs_dir / export_filename
                with open(export_path, "w", encoding="utf-8") as f:
                    f.write(final_text)
                with open(export_path, "rb") as file:
                    st.download_button("📥 전체 텍스트 원본 다운로드 (.txt)", data=file, file_name=export_filename, mime="text/plain")


    # =========================================================================
    # Step 2: 예방보전(PM) 기준 정보 추출 및 검증 (가치 분류 및 Jidoka)
    # =========================================================================
    if st.session_state.step1_done:
        st.markdown('<div class="step-header"><h3>🟢 Step 2: 예방보전(PM) 기준 정보 추출 및 검증 (가치 흐름 속 품질 확보)</h3><p style="margin:0;color:#555;">방대한 매뉴얼 중 청소/점검/윤활/수리(CILR) 등 가치를 더하는 정보만 골라냅니다. <b>반드시 엔지니어가 육안으로 데이터를 보완 및 확정해야 합니다. (Jidoka)</b></p></div>', unsafe_allow_html=True)
        
        if not st.session_state.step2_started:
            if st.button("2단계: AI 기반 핵심 예방보전(PM) 정보 선별", type="primary"):
                st.session_state.step2_started = True
                st.rerun()

        if st.session_state.step2_started:
            if st.session_state.pm_items is None:
                with st.spinner("AI가 방대한 문서 속에서 PM/자주보전 항목만 찾고 있습니다... 🔍"):
                    final_use_offline = use_offline or (not api_key and not os.getenv("GEMINI_API_KEY"))

                    if final_use_offline:
                        classifier = RuleClassifier()
                        pm_items = classifier.classify_pm_items(st.session_state.ocr_results)
                    else:
                        actual_key = api_key if api_key else os.getenv("GEMINI_API_KEY")
                        try:
                            classifier = PMClassifier(api_key=actual_key)
                            pm_items = classifier.classify_pm_items(
                                st.session_state.ocr_results, 
                                equipment_name=st.session_state.equipment_name
                            )
                        except Exception as e:
                            st.warning(f"AI 처리 중 오류가 발생하여 룰(규칙) 기반으로 대체진행합니다. ({e})")
                            classifier = RuleClassifier()
                            pm_items = classifier.classify_pm_items(st.session_state.ocr_results)
                            
                    st.session_state.pm_items = pm_items
                    
                    # PMItem 객체를 DataFrame으로 변환
                    if pm_items:
                        df = pd.DataFrame([item.model_dump() for item in pm_items])
                    else:
                        # 빈 데이터프레임 구조 생성
                        df = pd.DataFrame(columns=["item_id", "item_name", "period", "equipment_part", "area", "method", "standard_value", "source_page", "confidence", "note"])
                    st.session_state.editor_df = df
                    st.rerun()

            else:
                # 1차 필터링 텍스트 추출 (PM 후보 페이지 모음)
                pm_text_blocks = []
                for page in st.session_state.ocr_results:
                    page_text = "\n".join([b.text for b in page.blocks if b.text])
                    if any(kw in page_text for kw in PM_KEYWORDS):
                        pm_text_blocks.append(f"--- [Page {page.page}] ---\n{page_text}")
                
                raw_pm_text = "\n\n".join(pm_text_blocks)
                if not raw_pm_text:
                    raw_pm_text = "이 매뉴얼 내에 유지보수(PM) 관련 키워드가 포함된 페이지가 없는 것으로 보입니다. 다른 매뉴얼을 확인해 주세요."
                
                # PM 필터된 텍스트 다운로드 영역
                st.info("🔔 **[1차 추출: PM 후보 텍스트 모음]** AI가 구체적인 표 형식으로 가공하기 전, 예방보전 관련 단어(점검, 청소 등)가 쓰인 페이지만 원본에서 발라낸 기초 텍스트입니다. (아래 탭을 열어 확인 및 다운로드 가능)")
                with st.expander("📄 [PM 후보 텍스트 (Raw)] 전체 보기 및 1차 텍스트 다운로드"):
                    st.text_area("PM 대상 후보 원본 텍스트", raw_pm_text, height=200, disabled=True)
                    export_filename = f"Filtered_PM_RawText_{st.session_state.job_time}.txt"
                    export_path = outputs_dir / export_filename
                    with open(export_path, "w", encoding="utf-8") as f:
                        f.write(raw_pm_text)
                    with open(export_path, "rb") as file:
                        st.download_button("📥 1차 발라낸 PM 원본 텍스트 전부 다운로드 (.txt)", data=file, file_name=export_filename, mime="text/plain")

                st.markdown("---")
                
                # 기존 인간의 가치 검증 에디터 영역
                if st.session_state.pm_items:
                    st.success(f"🤖 **[인간의 가치 검증]** AI가 총 {len(st.session_state.pm_items)}건의 보전 항목을 표 형태로 구조화했습니다. 표 안의 데이터를 더블클릭하여 **불필요한 내용은 삭제**하거나 **부족한 내용은 직접 타이핑**하여 완벽하게 만드세요.")
                else:
                    st.warning("⚠️ **[AI 구조화 실패(0건)]** 기계가 명확한 CILR(점검/교체 등) 표 형식이나 문장을 구조화하지 못해 목록이 비어있습니다. 위의 '1차 추출 텍스트'를 보고 엑셀 표 빈칸에 직접 내용을 타이핑하여 점검표를 구축해 주세요.")
                
                # 데이터 에디터 기능 제공
                edited_df = st.data_editor(
                    st.session_state.editor_df, 
                    num_rows="dynamic",
                    use_container_width=True,
                    height=300,
                    column_config={
                        "item_id": None,
                        "confidence": None,
                        "area": st.column_config.TextColumn("설비 영역"),
                        "equipment_part": st.column_config.TextColumn("점검 부위", required=True),
                        "item_name": st.column_config.TextColumn("점검 항목명", required=True),
                        "period": st.column_config.SelectboxColumn("점검 주기", options=["일", "월", "분기", "반기", "년"]),
                        "method": st.column_config.TextColumn("점검 방법"),
                        "standard_value": st.column_config.TextColumn("판정 기준(기준값)"),
                        "note": st.column_config.TextColumn("특이사항/도구"),
                        "source_page": st.column_config.NumberColumn("출처(Page)", disabled=True),
                    }
                )

                if st.button("✅ 2단계: 현장 지식 검증 완료 및 확정 (Confirm)", type="primary"):
                    st.session_state.final_pm_df = edited_df
                    st.session_state.step2_done = True
                    st.rerun()


    # =========================================================================
    # Step 3: 현장 실행용 표준 PM 점검표(Checklist) 생성 (표준화 Poka-yoke)
    # =========================================================================
    if st.session_state.step2_done:
        st.markdown('<div class="step-header"><h3>🔵 Step 3: 현장 실행용 표준 PM 점검표(Checklist) 양식 발행 (표준작업, Poka-yoke)</h3><p style="margin:0;color:#555;">현장의 작업자들이 헷갈림 없이 즉시 활용 가능한(풀-프루프) 규격화된 엑셀 시트로 변환합니다.</p></div>', unsafe_allow_html=True)
        
        if not st.session_state.excel_path:
            if st.button("3단계: 현장 배포용 엑셀(Checklist) 양식 생성", type="primary"):
                with st.spinner("표준 엑셀 서식을 생성하고 있습니다... 📊"):
                    # DataFrame을 다시 PMItem 객체 리스트로 복원
                    # 빈 셀(NaN, NaT)들을 None으로 치환하여 Pydantic 모델 변환 오류(AttributeError/ValidationError) 방지
                    safe_df = st.session_state.final_pm_df.where(pd.notnull(st.session_state.final_pm_df), None)
                    dict_records = safe_df.to_dict('records')
                    
                    try:
                        validated_pm_items = [PMItem(**rec) for rec in dict_records]
                    except Exception as e:
                        st.error(f"데이터 변환 오류가 발생했습니다. 빈칸 등에 올바르지 않은 값이 들어갔을 수 있습니다. 상세: {e}")
                        st.stop()
                    
                    export_engine = ExportEngine()
                    excel_filename = f"TPM_Checklist_{st.session_state.equipment_name}_{st.session_state.job_time}.xlsx"
                    excel_path = str(outputs_dir / excel_filename)
                    
                    export_engine.save_to_file(
                        manual_name=st.session_state.uploaded_filename,
                        equipment_name=st.session_state.equipment_name,
                        all_items=validated_pm_items,
                        output_path=excel_path
                    )
                    
                    # 마크다운(.md) 파일도 추가 생성
                    md_filename = f"TPM_Checklist_{st.session_state.equipment_name}_{st.session_state.job_time}.md"
                    md_path = str(outputs_dir / md_filename)
                    md_content = f"# {st.session_state.equipment_name} PM Checklist\n\n"
                    md_content += f"- **원본 매뉴얼:** {st.session_state.uploaded_filename}\n"
                    md_content += f"- **생성 일시:** {time.strftime('%Y-%m-%d %H:%M')}\n\n"
                    md_content += "| 점검 부위 | 점검 내용 | 점검 주기 | 점검 방법 | 판정 기준 | 특정사항 |\n"
                    md_content += "| --- | --- | --- | --- | --- | --- |\n"
                    for item in validated_pm_items:
                        method = str(item.method).replace('\n', ' ') if item.method else '-'
                        note = str(item.note).replace('\n', ' ') if item.note else '-'
                        criteria = str(item.standard_value).replace('\n', ' ') if item.standard_value else '-'
                        task = str(item.item_name).replace('\n', ' ') if item.item_name else '-'
                        period_str = item.period.value if hasattr(item.period, 'value') else str(item.period)
                        md_content += f"| {item.equipment_part} | {task} | {period_str} | {method} | {criteria} | {note} |\n"
                    
                    with open(md_path, "w", encoding="utf-8") as f:
                        f.write(md_content)
                    
                    st.session_state.excel_path = excel_path
                    st.session_state.md_path = md_path
                st.rerun()
        else:
            st.success("✅ 모든 프로세스가 완료되었습니다! 현장을 혁신할 준비가 끝났습니다.")
            
            # 최종 통계 요약표 노출
            safe_df_stats = st.session_state.final_pm_df.where(pd.notnull(st.session_state.final_pm_df), None)
            val_items = [PMItem(**rec) for rec in safe_df_stats.to_dict('records')]
            builder = ChecklistBuilder()
            stats = builder.get_statistics(val_items)
            
            st.markdown(f"""
            <div style="padding:1rem; border:1px solid #ccc; border-radius:0.5rem;">
                <h4>📊 반영된 현장 PM 지표 요약</h4>
                <ul>
                    <li><b>총 점검 대상 (부위):</b> {stats['total_parts']}곳</li>
                    <li><b>총 점검 행동 내역:</b> {len(val_items)}건</li>
                    <li><b>가장 많은 주기 분류:</b> {max(stats['by_period'], key=stats['by_period'].get) if stats['by_period'] else '없음'}</li>
                </ul>
            </div>
            """, unsafe_allow_html=True)
            
            st.info("💡 아래 버튼을 클릭하시면 각 파일이 사용 중이신 **기본 윈도우 다운로드 폴더** (일반적으로 `C:\\Users\\계정명\\Downloads`)에 저장됩니다.")
            
            colDL1, colDL2 = st.columns(2)
            with colDL1:
                with open(st.session_state.excel_path, "rb") as file:
                    st.download_button(
                        label="📥 최종 현장용 체크리스트 내려받기 [Excel .xlsx]",
                        data=file,
                        file_name=Path(st.session_state.excel_path).name,
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        use_container_width=True,
                        type="primary"
                    )
            with colDL2:
                with open(st.session_state.md_path, "rb") as file:
                    st.download_button(
                        label="📥 최종 현장용 체크리스트 내려받기 [Markdown .md]",
                        data=file,
                        file_name=Path(st.session_state.md_path).name,
                        mime="text/markdown",
                        use_container_width=True,
                        type="secondary"
                    )

if __name__ == "__main__":
    main()
