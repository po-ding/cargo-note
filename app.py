import streamlit as st
import pandas as pd
from datetime import datetime
import io

# ---------------------------------------------------------
# 1. 앱 설정 및 데이터 초기화
# ---------------------------------------------------------
st.set_page_config(page_title="운송 기록부", layout="wide")

# CSS 스타일 (인쇄 시 깔끔하게 나오도록)
st.markdown("""
    <style>
        @media print {
            .stApp > header {display: none;}
            .stSidebar {display: none;}
            .block-container {padding: 0;}
        }
        .metric-card {
            background-color: #f0f2f6;
            padding: 15px;
            border-radius: 10px;
            text-align: center;
            margin-bottom: 10px;
        }
        .metric-value { font-size: 1.5rem; font-weight: bold; }
        .metric-label { font-size: 0.9rem; color: #555; }
        .txt-red { color: #ff4b4b; font-weight: bold; }
        .txt-blue { color: #0068c9; font-weight: bold; }
        .txt-green { color: #09ab3b; font-weight: bold; }
    </style>
""", unsafe_allow_html=True)

st.title("🚛 운송 기록부 (Streamlit Ver.)")

# 데이터 저장소 (세션)
if 'data' not in st.session_state:
    st.session_state.data = []

# ---------------------------------------------------------
# 2. 사이드바: 입력 및 OCR
# ---------------------------------------------------------
with st.sidebar:
    st.header("📝 기록 입력")
    
    # OCR (베타) - 복잡한 설치 없이 간단한 이미지 업로드 UI만 구현
    # (실제 OCR은 easyocr 라이브러리가 필요하지만, 배포 속도를 위해 로직만 구성)
    with st.expander("📷 영수증 인식 (베타)"):
        uploaded_file = st.file_uploader("이미지 업로드", type=['png', 'jpg', 'jpeg'])
        if uploaded_file:
            st.info("이미지가 업로드되었습니다. (현재 버전은 수동 입력 권장)")
            # 여기에 EasyOCR 등을 붙일 수 있으나, 무료 클라우드 용량 문제로 생략
    
    with st.form("record_form", clear_on_submit=True):
        date = st.date_input("날짜", datetime.now())
        time = st.time_input("시간", datetime.now())
        type_option = st.selectbox("기록 종류", ["화물운송", "주유소", "수입", "지출", "소모품"])
        
        memo = st.text_input("내용 (상하차지, 적요)")
        
        # 금액 입력 (기본 0원)
        st.markdown("---")
        if type_option == "주유소":
            col_f1, col_f2 = st.columns(2)
            fuel_cost = col_f1.number_input("주유금액 (원)", step=1000)
            subsidy = col_f2.number_input("보조금액 (원)", step=100)
            
            col_f3, col_f4 = st.columns(2)
            liters = col_f3.number_input("주유리터 (L)", step=0.1, format="%.2f")
            unit_price = col_f4.number_input("단가 (원)", step=10)
            
            # 나머지 값 0 처리
            income = 0
            expense = 0
            distance = 0
            
            # 자동계산: 금액이 없고 리터/단가만 있을 때
            if fuel_cost == 0 and liters > 0 and unit_price > 0:
                fuel_cost = int(liters * unit_price)
                
        elif type_option == "화물운송":
            income = st.number_input("운송 수입 (원)", step=10000)
            distance = st.number_input("운행 거리 (km)", step=1.0)
            fuel_cost, subsidy, liters, unit_price, expense = 0, 0, 0, 0, 0
            
        elif type_option == "수입":
            income = st.number_input("수입 금액 (원)", step=10000)
            fuel_cost, subsidy, liters, unit_price, expense, distance = 0, 0, 0, 0, 0, 0
            
        else: # 지출, 소모품
            expense = st.number_input("지출 금액 (원)", step=1000)
            fuel_cost, subsidy, liters, unit_price, income, distance = 0, 0, 0, 0, 0, 0

        # 저장 버튼
        if st.form_submit_button("저장하기", use_container_width=True):
            record = {
                "날짜": str(date),
                "시간": str(time),
                "종류": type_option,
                "내용": memo,
                "수입": int(income),
                "지출": int(expense),
                "주유금액": int(fuel_cost),
                "보조금": int(subsidy),
                "실주유비": int(fuel_cost - subsidy),
                "리터": float(liters),
                "단가": int(unit_price),
                "거리": float(distance)
            }
            st.session_state.data.append(record)
            st.success("저장되었습니다.")

# ---------------------------------------------------------
# 3. 메인 화면: 통계 및 조회
# ---------------------------------------------------------

if st.session_state.data:
    df = pd.DataFrame(st.session_state.data)
    
    # [계산 로직] 요청하신 공식 적용
    # 1. 총 수입 (운송 + 기타수입)
    total_income = df['수입'].sum()
    
    # 2. 총 지출 (운송비용 + 일반지출 + 소모품) - 데이터 구조상 '지출' 컬럼에 포함됨
    total_expense = df['지출'].sum()
    
    # 3. 주유 관련
    total_fuel_cost = df['주유금액'].sum()
    total_subsidy = df['보조금'].sum()
    total_fuel_net = total_fuel_cost - total_subsidy # 실주유비
    total_liters = df['리터'].sum()
    total_distance = df['거리'].sum()
    
    # 4. 최종 순수익 = 총수입 - (일반지출 + 실주유비)
    final_profit = total_income - (total_expense + total_fuel_net)

    # [상단 요약 카드]
    st.subheader("📊 실시간 요약")
    
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("총 수입", f"{total_income:,} 원", "운송+기타")
    c2.metric("일반 지출", f"{total_expense:,} 원", "식대/소모품 등", delta_color="inverse")
    c3.metric("실 주유비", f"{total_fuel_net:,} 원", f"보조금 -{total_subsidy:,}원", delta_color="inverse")
    c4.metric("최종 순수익", f"{final_profit:,} 원", "수입 - (지출+주유)")

    st.markdown("---")

    # ---------------------------------------------------------
    # 4. 출력용 뷰 (4단 분리)
    # ---------------------------------------------------------
    st.subheader("🖨️ 운송내역 출력 (상세)")
    
    tab_all, tab_print = st.tabs(["전체 보기", "출력용 화면"])
    
    with tab_all:
        st.dataframe(df, use_container_width=True)
    
    with tab_print:
        st.markdown("##### ※ 아래 내용을 복사하거나 브라우저 인쇄 기능을 사용하세요.")
        
        # 1. 운송 내역
        st.markdown("#### 1. 운송 내역")
        df_trans = df[df['종류'].isin(['화물운송', '대기', '운행취소'])].copy()
        if not df_trans.empty:
            st.table(df_trans[['날짜', '내용', '거리', '수입']].assign(
                수입=df_trans['수입'].apply(lambda x: f"{x:,}"),
                거리=df_trans['거리'].apply(lambda x: f"{x} km")
            ))
        else:
            st.caption("내역 없음")

        # 2. 주유 내역
        st.markdown("#### 2. 주유 및 정비 내역")
        df_fuel = df[df['종류'] == '주유소'].copy()
        if not df_fuel.empty:
            st.table(df_fuel[['날짜', '내용', '리터', '단가', '주유금액', '보조금', '실주유비']].assign(
                주유금액=df_fuel['주유금액'].apply(lambda x: f"{x:,}"),
                보조금=df_fuel['보조금'].apply(lambda x: f"{x:,}"),
                실주유비=df_fuel['실주유비'].apply(lambda x: f"{x:,}"),
                리터=df_fuel['리터'].apply(lambda x: f"{x:.2f} L"),
                단가=df_fuel['단가'].apply(lambda x: f"{x:,} 원")
            ))
        else:
            st.caption("내역 없음")

        # 3. 지출 내역
        st.markdown("#### 3. 지출 내역")
        df_exp = df[df['종류'].isin(['지출', '소모품'])].copy()
        if not df_exp.empty:
            st.table(df_exp[['날짜', '내용', '지출']].assign(
                지출=df_exp['지출'].apply(lambda x: f"{x:,}")
            ))
        else:
            st.caption("내역 없음")

        # 4. 수입 내역
        st.markdown("#### 4. 수입 내역 (기타)")
        df_inc = df[df['종류'] == '수입'].copy()
        if not df_inc.empty:
            st.table(df_inc[['날짜', '내용', '수입']].assign(
                수입=df_inc['수입'].apply(lambda x: f"{x:,}")
            ))
        else:
            st.caption("내역 없음")

else:
    st.info("👈 왼쪽 사이드바에서 데이터를 입력해주세요.")