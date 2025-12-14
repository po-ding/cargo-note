import streamlit as st
import pandas as pd
from datetime import datetime

# 1. 앱 설정
st.set_page_config(page_title="운송 기록부", layout="wide")
st.title("🚛 운송 기록부 (Python Ver.)")

# 2. 데이터 저장소 (임시 - 새로고침하면 초기화됨, 추후 구글시트 연동 가능)
if 'data' not in st.session_state:
    st.session_state.data = []

# 3. 입력 화면 (사이드바)
with st.sidebar:
    st.header("📝 기록 입력")
    with st.form("record_form", clear_on_submit=True):
        date = st.date_input("날짜", datetime.now())
        time = st.time_input("시간", datetime.now())
        type_option = st.selectbox("기록 종류", ["화물운송", "주유소", "수입", "지출"])
        
        # 공통 입력
        memo = st.text_input("내용 (상하차지, 적요)")
        
        # 종류별 추가 입력창 (한꺼번에 보여주되 값은 0으로 처리)
        st.caption("👇 해당되는 항목만 입력하세요")
        income = st.number_input("수입 금액 (원)", value=0, step=1000)
        expense = st.number_input("지출 금액 (원)", value=0, step=1000)
        
        st.divider()
        st.caption("⛽ 주유소 선택 시 입력")
        fuel_cost = st.number_input("주유 금액 (원)", value=0, step=1000)
        subsidy = st.number_input("보조금액 (원)", value=0, step=1000)
        liters = st.number_input("주유 리터 (L)", value=0.0, step=0.1)
        distance = st.number_input("운행 거리 (km)", value=0.0, step=0.1)

        submitted = st.form_submit_button("저장하기", use_container_width=True)

        if submitted:
            # 데이터 저장 로직
            record = {
                "날짜": str(date),
                "시간": str(time),
                "종류": type_option,
                "내용": memo,
                "수입": income,
                "지출": expense,
                "주유금액": fuel_cost,
                "보조금": subsidy,
                "실주유비": fuel_cost - subsidy, # 자동 계산
                "리터": liters,
                "거리": distance
            }
            st.session_state.data.append(record)
            st.success("저장 완료!")

# 4. 데이터 조회 및 통계 화면
if st.session_state.data:
    # 데이터프레임 변환
    df = pd.DataFrame(st.session_state.data)
    
    # [통계 계산]
    total_income = df['수입'].sum() # 운송수입 + 기타수입
    total_expense = df['지출'].sum() # 일반지출
    
    total_fuel_cost = df['주유금액'].sum()
    total_subsidy = df['보조금'].sum()
    total_fuel_net = total_fuel_cost - total_subsidy # 실주유비
    
    total_liters = df['리터'].sum()
    total_distance = df['거리'].sum()

    # 최종 순수익 = 총수입 - (일반지출 + 실주유비)
    final_profit = total_income - (total_expense + total_fuel_net)

    # [상단 요약 카드]
    st.subheader("📊 실시간 요약")
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("총 수입", f"{total_income:,} 원", delta="운송+기타")
    col2.metric("총 지출 (일반)", f"{total_expense:,} 원", delta_color="inverse")
    col3.metric("실 주유비", f"{total_fuel_net:,} 원", delta=f"-{total_subsidy:,}원 보조됨", delta_color="inverse")
    col4.metric("최종 순수익", f"{final_profit:,} 원", delta="수입 - (지출+주유)")

    # [상세 내역 테이블] - 탭으로 분리
    st.divider()
    tab1, tab2, tab3, tab4 = st.tabs(["1.운송/전체", "2.주유내역", "3.지출내역", "4.수입내역"])
    
    with tab1:
        st.dataframe(df, use_container_width=True)
    
    with tab2:
        fuel_df = df[df['종류'] == '주유소'][['날짜','내용','주유금액','보조금','실주유비','리터']]
        st.dataframe(fuel_df, use_container_width=True)
        st.info(f"총 주유: {total_fuel_cost:,}원 | 총 보조금: {total_subsidy:,}원 | 총 리터: {total_liters:.1f}L")

    with tab3:
        exp_df = df[(df['종류'] == '지출') | (df['종류'] == '소모품')][['날짜','내용','지출']]
        st.dataframe(exp_df, use_container_width=True)

    with tab4:
        inc_df = df[(df['종류'] == '수입') | (df['종류'] == '화물운송')][['날짜','내용','수입']]
        st.dataframe(inc_df, use_container_width=True)

else:
    st.info("👈 왼쪽 사이드바에서 운송 기록을 입력해주세요.")
