"""
테스트용 샘플 CNC 매뉴얼 PDF 생성 스크립트

reportlab을 사용하여 실제 매뉴얼과 유사한 구조의
테스트용 PDF를 생성합니다.

사용법:
    python scripts/create_sample_manual.py
"""

import os
import sys
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
    PageBreak,
)
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

# 루트 경로 추가
sys.path.insert(0, str(Path(__file__).parent.parent))


def register_korean_font():
    """한국어 폰트 등록"""
    # Windows 기본 한글 폰트 시도
    font_paths = [
        "C:/Windows/Fonts/malgun.ttf",       # 맑은 고딕
        "C:/Windows/Fonts/gulim.ttc",         # 굴림
        "/usr/share/fonts/truetype/nanum/NanumGothic.ttf",  # Linux
    ]

    for font_path in font_paths:
        if os.path.exists(font_path):
            try:
                pdfmetrics.registerFont(TTFont("Korean", font_path))
                return "Korean"
            except Exception:
                continue

    # 폰트를 찾지 못한 경우 기본 폰트 사용
    print("⚠️ 한국어 폰트를 찾지 못했습니다. 기본 폰트를 사용합니다.")
    return "Helvetica"


def create_sample_manual(output_path: str = None):
    """
    테스트용 CNC 머시닝센터 유지보수 매뉴얼 PDF 생성

    Args:
        output_path: 출력 파일 경로 (기본: tests/fixtures/sample_cnc_manual.pdf)
    """
    if output_path is None:
        output_dir = Path(__file__).parent.parent / "tests" / "fixtures"
        output_dir.mkdir(parents=True, exist_ok=True)
        output_path = str(output_dir / "sample_cnc_manual.pdf")

    font_name = register_korean_font()

    doc = SimpleDocTemplate(
        output_path,
        pagesize=A4,
        rightMargin=20 * mm,
        leftMargin=20 * mm,
        topMargin=25 * mm,
        bottomMargin=25 * mm,
    )

    # 스타일 정의
    styles = getSampleStyleSheet()

    title_style = ParagraphStyle(
        "KoreanTitle",
        parent=styles["Title"],
        fontName=font_name,
        fontSize=22,
        spaceAfter=12,
        textColor=colors.HexColor("#1A3A5C"),
    )

    h1_style = ParagraphStyle(
        "KoreanH1",
        parent=styles["Heading1"],
        fontName=font_name,
        fontSize=16,
        spaceAfter=8,
        spaceBefore=16,
        textColor=colors.HexColor("#1A3A5C"),
    )

    h2_style = ParagraphStyle(
        "KoreanH2",
        parent=styles["Heading2"],
        fontName=font_name,
        fontSize=13,
        spaceAfter=6,
        spaceBefore=12,
        textColor=colors.HexColor("#333333"),
    )

    body_style = ParagraphStyle(
        "KoreanBody",
        parent=styles["Normal"],
        fontName=font_name,
        fontSize=10,
        spaceAfter=6,
        leading=14,
    )

    small_style = ParagraphStyle(
        "KoreanSmall",
        parent=styles["Normal"],
        fontName=font_name,
        fontSize=8,
        textColor=colors.grey,
    )

    # 테이블 스타일
    table_header_style = TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1A3A5C")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
        ("FONTNAME", (0, 0), (-1, -1), font_name),
        ("FONTSIZE", (0, 0), (-1, 0), 9),
        ("FONTSIZE", (0, 1), (-1, -1), 8),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F5F5F5")]),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ])

    # 콘텐츠 구성
    elements = []

    # ─── 표지 ───
    elements.append(Spacer(1, 80 * mm))
    elements.append(Paragraph("CNC 수직 머시닝센터", title_style))
    elements.append(Paragraph("유지보수 매뉴얼 V2.1", title_style))
    elements.append(Spacer(1, 20 * mm))
    elements.append(Paragraph("모델: VMC-850", body_style))
    elements.append(Paragraph("제조사: MUMULAB Machinery Co., Ltd.", body_style))
    elements.append(Paragraph("문서번호: MM-VMC850-PM-2026-001", body_style))
    elements.append(Spacer(1, 40 * mm))
    elements.append(Paragraph("2026년 3월", body_style))
    elements.append(PageBreak())

    # ─── 목차 ───
    elements.append(Paragraph("목차", h1_style))
    toc_items = [
        "1. 안전 주의사항",
        "2. 설비 개요",
        "3. 정기 점검 및 유지보수",
        "  3.1 일상 점검 항목 (매일)",
        "  3.2 월간 점검 항목",
        "  3.3 분기 점검 항목",
        "  3.4 반기 점검 항목",
        "  3.5 연간 점검 항목",
        "4. 윤활 계통도",
        "5. 전기 배선도",
    ]
    for item in toc_items:
        elements.append(Paragraph(item, body_style))
    elements.append(PageBreak())

    # ─── Chapter 1: 안전 주의사항 (PM 없음 — 필터링 대상) ───
    elements.append(Paragraph("1. 안전 주의사항", h1_style))
    elements.append(Paragraph(
        "본 설비를 조작하기 전에 반드시 다음 안전 수칙을 숙지하십시오. "
        "설비 운전 중 보호 커버를 열지 마십시오. 비상 정지 버튼의 위치를 확인하십시오. "
        "작업 전 개인 보호구(PPE)를 착용하십시오.", body_style
    ))
    elements.append(PageBreak())

    # ─── Chapter 2: 설비 개요 (PM 없음) ───
    elements.append(Paragraph("2. 설비 개요", h1_style))
    elements.append(Paragraph(
        "VMC-850 수직 머시닝센터는 고속·고정밀 가공을 위한 CNC 공작기계입니다. "
        "주축 회전수 최대 12,000rpm, 급속이송 속도 36m/min, ATC 매거진 24공구 장착.", body_style
    ))

    spec_data = [
        ["항목", "사양"],
        ["주축 회전수", "최대 12,000 rpm"],
        ["급속이송 속도", "X/Y: 36 m/min, Z: 24 m/min"],
        ["ATC 공구 수", "24 Tool"],
        ["테이블 크기", "800 x 500 mm"],
        ["주축 테이퍼", "BT-40"],
        ["주축 모터", "11/15 kW"],
        ["기계 중량", "약 6,500 kg"],
    ]
    spec_table = Table(spec_data, colWidths=[60 * mm, 90 * mm])
    spec_table.setStyle(table_header_style)
    elements.append(Spacer(1, 10 * mm))
    elements.append(spec_table)
    elements.append(PageBreak())

    # ─── Chapter 3: 정기 점검 및 유지보수 ───
    elements.append(Paragraph("3. 정기 점검 및 유지보수", h1_style))
    elements.append(Paragraph(
        "설비의 안정적인 가동과 수명 연장을 위해 아래 점검 항목을 해당 주기에 따라 "
        "반드시 수행하십시오. 점검 이상 발견 시 즉시 설비를 정지하고 담당자에게 보고하십시오.",
        body_style
    ))

    # ─── 3.1 일상 점검 항목 ───
    elements.append(Paragraph("3.1 일상 점검 항목 (매일 가동 전 실시)", h2_style))
    elements.append(Paragraph(
        "매일 설비 가동 전에 아래 항목을 반드시 점검하십시오. 이상 발견 시 가동을 중지하고 "
        "유지보수 담당자에게 통보하십시오.", body_style
    ))

    daily_data = [
        ["No", "점검 항목", "점검 방법", "기준값", "비고"],
        ["1", "주축 윤활유 레벨 확인", "육안점검", "게이지 중간 이상", "오일탱크 확인"],
        ["2", "냉각수(쿨런트) 레벨 확인", "육안점검", "탱크 1/2 이상", "부족 시 보충"],
        ["3", "공압 압력 확인", "압력계 확인", "5~7 kgf/cm²", "FRL 유닛 확인"],
        ["4", "칩 컨베이어 작동 확인", "작동점검", "정상 작동", "이상 소음 확인"],
        ["5", "비상정지 버튼 작동 확인", "작동점검", "정상 작동", "안전 장치"],
        ["6", "절삭유 농도 확인", "굴절계 측정", "3~5%", "매일 확인 권장"],
        ["7", "주축 워밍업 실시", "작동", "15분 이상", "1000rpm부터 단계적"],
    ]
    daily_table = Table(daily_data, colWidths=[12*mm, 50*mm, 30*mm, 35*mm, 30*mm])
    daily_table.setStyle(table_header_style)
    elements.append(Spacer(1, 5 * mm))
    elements.append(daily_table)
    elements.append(PageBreak())

    # ─── 3.2 월간 점검 항목 ───
    elements.append(Paragraph("3.2 월간 점검 항목 (월 1회 실시)", h2_style))
    elements.append(Paragraph(
        "매월 1회 이상 아래 항목을 점검하십시오. 교체 주기가 도래한 소모품은 "
        "적시에 교체하여 설비 성능을 유지하십시오.", body_style
    ))

    monthly_data = [
        ["No", "점검 항목", "점검 방법", "기준값", "비고"],
        ["1", "주축 윤활유 보충", "보충", "ISO VG68", "오일탱크 게이지 확인"],
        ["2", "ATC 매거진 체인 장력 확인", "측정", "처짐 10mm 이내", "조정 필요 시 서비스 요청"],
        ["3", "전기함 팬 필터 청소", "청소", "먼지 제거", "에어건 사용"],
        ["4", "이송계 볼스크류 윤활", "급유", "리튬그리스 도포", "X/Y/Z축 각각"],
        ["5", "가이드 커버 상태 확인", "육안점검", "손상 없음", "텔레스코픽 커버 포함"],
        ["6", "쿨런트 필터 교체", "교체", "-", "필터 오염도 확인"],
        ["7", "CNC 제어기 팬 필터 청소", "청소", "먼지 제거", "컨트롤러 팬"],
        ["8", "안전 인터록 작동 확인", "작동점검", "정상 작동", "도어 센서 포함"],
    ]
    monthly_table = Table(monthly_data, colWidths=[12*mm, 50*mm, 30*mm, 35*mm, 30*mm])
    monthly_table.setStyle(table_header_style)
    elements.append(Spacer(1, 5 * mm))
    elements.append(monthly_table)
    elements.append(PageBreak())

    # ─── 3.3 분기 점검 항목 ───
    elements.append(Paragraph("3.3 분기 점검 항목 (3개월마다 실시)", h2_style))
    elements.append(Paragraph("분기별로 아래 항목을 점검하십시오.", body_style))

    quarter_items = [
        "- 유압 오일 오염도 측정: NAS 7등급 이하를 유지해야 합니다. 분기 1회 오일 샘플링 후 오염도를 측정하십시오.",
        "- 냉각수 농도 확인 및 조정: 농도 3~5%를 유지하십시오. 분기 1회 굴절계로 측정합니다.",
        "- 각 축(X/Y/Z) 백래시 측정: 다이얼 게이지를 사용하여 측정하며, 0.005mm 이하를 유지해야 합니다.",
        "- 에어 유닛(FRL) 수분 배출 및 윤활유 보충: 에어 드라이어 필터 상태를 확인하고, 루브리케이터 오일을 보충하십시오.",
        "- 각 축 리미트 스위치 작동 확인: 3개월마다 각 축의 오버트래블 리미트 센서를 테스트하십시오.",
        "- 유압 호스 및 배관 상태 점검: 3개월마다 누유, 균열, 노화 여부를 육안으로 확인합니다.",
    ]
    for item in quarter_items:
        elements.append(Paragraph(item, body_style))
    elements.append(PageBreak())

    # ─── 3.4 반기 점검 항목 ───
    elements.append(Paragraph("3.4 반기 점검 항목 (6개월마다 실시)", h2_style))
    elements.append(Paragraph("반기별로 아래 항목을 정밀 점검하십시오.", body_style))

    semi_data = [
        ["No", "점검 항목", "점검 방법", "기준값", "비고"],
        ["1", "서보 모터 절연 저항 측정", "메가 측정", "1 MΩ 이상", "전기계통"],
        ["2", "볼스크류 예압 확인", "측정", "규정 토크값", "6개월마다 전문 기술자"],
        ["3", "유압 펌프 압력 테스트", "압력계 측정", "규정 압력 ±5%", "유압계통"],
        ["4", "냉각수 전량 교체", "교체", "새 쿨런트", "탱크 세척 후 교체"],
        ["5", "전기함 내부 단자 조임 확인", "토크 렌치", "규정 토크", "6개월마다"],
    ]
    semi_table = Table(semi_data, colWidths=[12*mm, 50*mm, 30*mm, 35*mm, 30*mm])
    semi_table.setStyle(table_header_style)
    elements.append(Spacer(1, 5 * mm))
    elements.append(semi_table)
    elements.append(PageBreak())

    # ─── 3.5 연간 점검 항목 ───
    elements.append(Paragraph("3.5 연간 점검 항목 (년 1회 실시)", h2_style))
    elements.append(Paragraph(
        "매년 1회 이상 아래 항목을 전문 기술자가 정밀 점검합니다. "
        "오버홀 작업은 반드시 제조사 인증 기술자가 수행해야 합니다.", body_style
    ))

    annual_items = [
        "- 주축 베어링 예압 확인: 매년 1회 전문 기술자가 주축 베어링의 예압을 측정하고 조정합니다. 주축 런아웃 0.003mm 이내를 유지해야 합니다.",
        "- 유압 오일 전량 교체: ISO VG46 유압유를 사용하며, 매년 1회 전량 교체합니다. 탱크 청소 후 신유를 충전하십시오.",
        "- 서보 드라이브 파라미터 백업: 매년 1회 모든 축의 서보 파라미터를 USB 또는 CF카드로 백업합니다.",
        "- 기계 정밀도 전체 측정: 레이저 간섭계를 이용하여 각 축의 위치 정밀도, 반복 정밀도를 측정합니다. 위치 정밀도 ±0.005mm.",
        "- 전기 배선 절연 상태 점검: 메가 테스터로 전체 배선의 절연 저항을 측정합니다. 매년 1회 수행.",
        "- ATC 시스템 오버홀: 공구 교환 장치의 전체 분해 점검 및 소모품 교체. 매년 1회 수행합니다.",
    ]
    for item in annual_items:
        elements.append(Paragraph(item, body_style))

    elements.append(Spacer(1, 10 * mm))
    elements.append(Paragraph("※ 이상의 모든 점검 기록은 설비 이력 카드에 반드시 기재하십시오.", small_style))

    # PDF 생성
    doc.build(elements)
    print(f"✅ 샘플 매뉴얼 PDF 생성 완료: {output_path}")
    return output_path


if __name__ == "__main__":
    output = sys.argv[1] if len(sys.argv) > 1 else None
    create_sample_manual(output)
