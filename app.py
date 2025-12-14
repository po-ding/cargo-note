import streamlit as st
import json
import os
import pandas as pd
from datetime import datetime, timedelta

# ==========================================
# 유틸리티 및 데이터 관리 클래스 (로직 동일)
# ==========================================

class DataManager:
    def __init__(self, filename="cargo_data.json"):
        self.filename = filename
        self.data = {
            "records": [],
            "centers": ["안성", "안산", "용인", "이천", "인천"],
            "locations": {},
            "expense_items": []
        }
        self.load_data()

    def load_data(self):
        if os.path.exists(self.filename):
            try:
                with open(self.filename, 'r', encoding='utf-8') as f:
                    loaded = json.load(f)
                    self.data.update(loaded)
                    if "records" not in self.data:
                        self.data["records"] = []
            except Exception as e:
                st.error(f"데이터 로드 실패: {e}")

    def save_data(self):
        try:
            with open(self.filename, 'w', encoding='utf-8') as f:
                json.dump(self.data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            st.error(f"저장 실패: {e}")

    def add_record(self, record):
        self.data["records"].append(record)
        
        # 자동 데이터 학습
        if record['type'] in ['화물운송', '대기']:
            if record.get('from') and record.get('from') not in self.data['centers']:
                self.data['centers'].append(record.get('from'))
            if record.get('to') and record.get('to') not in self.data['centers']:
                self.data['centers'].append(record.get('to'))
        
        if record.get('expenseItem') and record.get('expenseItem') not in self.data['expense_items']:
            self.data['expense_items'].append(record.get('expenseItem'))
            
        self.data['centers'].sort()
        self.save_data()

    def delete_record(self, record_id):
        self.data["records"] = [r for r in self.data["records"] if r['id'] != record_id]
        self.save_data()

    def get_statistical_date(self, date_str, time_str):
        """04시 기준으로 날짜를 계산"""
        try:
            dt = datetime.strptime(f"{date_str} {time_str}", "%Y-%m-%d %H:%M")
            if dt.hour < 4:
                dt = dt - timedelta(days=1)
            return dt.strftime("%Y-%m-%d")
        except:
            return date_str

# ==========================================
# 메인 Streamlit UI
# ==========================================

def main():
    st.set_page_config(page_title="화물 운송 기록부", page_icon="🚚")
    st.title("🚚 화물 운송 기록부 (Cargo Note)")

    # 데이터 매니저 초기화
    if 'dm' not in st.session_state:
        st.session_state.dm = DataManager()
    
    dm = st.session_state.dm

    # 탭 구성
    tab1, tab2, tab3, tab4 = st.tabs(["📝 기록 입력", "📋 기록 조회", "📊 통계", "⚙️ 설정"])

    # ----------------------------------------------------
    # 1. 입력 탭
    # ----------------------------------------------------
    with tab1:
        st.header("새로운 기록 입력")
        
        col1, col2 = st.columns(2)
        with col1:
            input_date = st.date_input("날짜", datetime.now())
        with col2:
            input_time = st.time_input("시간", datetime.now())

        record_type = st.selectbox("기록 종류", ["화물운송", "수입", "주유소", "소모품", "지출", "대기", "공차이동"])

        # 동적 입력 폼
        form_data = {}
        
        # 상하차 정보
        if record_type in ["화물운송", "대기", "공차이동"]:
            c1, c2 = st.columns(2)
            with c1:
                form_data['from'] = st.selectbox("상차지", [""] + dm.data['centers'], index=0)
            with c2:
                form_data['to'] = st.selectbox("하차지", [""] + dm.data['centers'], index=0)
            form_data['distance'] = st.number_input("운행 거리 (km)", min_value=0.0, step=0.1)

        # 주유 정보
        if record_type == "주유소":
            c1, c2 = st.columns(2)
            with c1:
                form_data['unitPrice'] = st.number_input("단가 (원/L)", min_value=0)
            with c2:
                form_data['liters'] = st.number_input("주유량 (L)", min_value=0.0, step=0.1)
            form_data['brand'] = st.selectbox("주유소 브랜드", ["S-OIL", "SK에너지", "GS칼텍스", "현대오일뱅크", "기타"])

        # 내역 입력 (지출/수입 등)
        if record_type in ["수입", "지출", "소모품"]:
            form_data['item'] = st.text_input("내역 (적요)", placeholder="예: 식대, 엔진오일 등")

        # 금액 정보
        st.subheader("금액 정보 (단위: 만원)")
        col_inc, col_exp = st.columns(2)
        
        income_input = 0.0
        cost_input = 0.0

        if record_type in ["화물운송", "수입", "대기"]:
            with col_inc:
                income_input = st.number_input("수입 금액", min_value=0.0, step=0.1, format="%.2f")
        
        if record_type in ["주유소", "지출", "소모품", "공차이동"]:
            with col_exp:
                # 주유비 자동 계산 힌트
                auto_cost = 0.0
                if record_type == "주유소" and form_data.get('unitPrice') and form_data.get('liters'):
                    auto_cost = (form_data['unitPrice'] * form_data['liters']) / 10000
                
                cost_input = st.number_input("지출 금액", min_value=0.0, step=0.1, value=auto_cost, format="%.2f")

        # 버튼 액션
        col_btn1, col_btn2 = st.columns(2)
        if col_btn1.button("💾 기록 저장", type="primary", use_container_width=True):
            # 저장 로직
            final_record = {
                "id": int(datetime.now().timestamp() * 1000),
                "date": input_date.strftime("%Y-%m-%d"),
                "time": input_time.strftime("%H:%M"),
                "type": record_type,
                "income": int(income_input * 10000),
                "cost": int(cost_input * 10000),
                "distance": form_data.get('distance', 0),
                "from": form_data.get('from', ""),
                "to": form_data.get('to', ""),
                "liters": form_data.get('liters', 0),
                "unitPrice": form_data.get('unitPrice', 0),
                "brand": form_data.get('brand', ""),
                "expenseItem": form_data.get('item', "") if record_type in ["지출", "수입"] else "",
                "supplyItem": form_data.get('item', "") if record_type == "소모품" else ""
            }
            dm.add_record(final_record)
            st.success("저장되었습니다!")
            st.rerun()

        if col_btn2.button("🛑 운행 종료", use_container_width=True):
            dm.add_record({
                "id": int(datetime.now().timestamp() * 1000),
                "date": datetime.now().strftime("%Y-%m-%d"),
                "time": datetime.now().strftime("%H:%M"),
                "type": "운행종료",
                "income": 0, "cost": 0, "distance": 0
            })
            st.info("운행 종료 기록됨.")
            st.rerun()

    # ----------------------------------------------------
    # 2. 조회 탭
    # ----------------------------------------------------
    with tab2:
        st.header("기록 조회")
        
        # 필터
        col_f1, col_f2 = st.columns(2)
        current_year = datetime.now().year
        current_month = datetime.now().month
        
        with col_f1:
            sel_year = st.selectbox("년도", range(2023, 2030), index=range(2023, 2030).index(current_year))
        with col_f2:
            sel_month = st.selectbox("월", range(1, 13), index=current_month-1)

        filter_prefix = f"{sel_year}-{sel_month:02d}"
        
        # 데이터 필터링
        all_records = dm.data.get("records", [])
        filtered_records = [
            r for r in all_records 
            if dm.get_statistical_date(r['date'], r['time']).startswith(filter_prefix)
        ]
        
        if filtered_records:
            # 표시용 데이터프레임 변환
            display_data = []
            for r in filtered_records:
                detail = ""
                if r['type'] in ['화물운송', '대기']:
                    detail = f"{r.get('from','')} → {r.get('to','')}"
                elif r['type'] == '주유소':
                    detail = f"{r.get('brand','')} ({r.get('liters',0)}L)"
                else:
                    detail = r.get('expenseItem') or r.get('supplyItem') or ""
                
                display_data.append({
                    "ID": r['id'],
                    "날짜": r['date'],
                    "시간": r['time'],
                    "구분": r['type'],
                    "내용": detail,
                    "거리(km)": r.get('distance', 0),
                    "수입(원)": f"{r.get('income', 0):,}",
                    "지출(원)": f"{r.get('cost', 0):,}"
                })
            
            df = pd.DataFrame(display_data)
            # 시간순 정렬
            df = df.sort_values(by=["날짜", "시간"], ascending=False)
            st.dataframe(df, hide_index=True, use_container_width=True)

            # 삭제 기능
            st.divider()
            st.subheader("기록 삭제")
            del_id = st.selectbox("삭제할 항목 선택 (내용 확인)", options=df["ID"], format_func=lambda x: f"ID: {x}")
            if st.button("선택한 항목 삭제"):
                dm.delete_record(del_id)
                st.warning("삭제되었습니다.")
                st.rerun()
        else:
            st.info("해당 기간의 기록이 없습니다.")

    # ----------------------------------------------------
    # 3. 통계 탭
    # ----------------------------------------------------
    with tab3:
        st.header(f"{sel_year}년 {sel_month}월 통계 요약")
        
        if filtered_records:
            total_income = sum(r.get('income', 0) for r in filtered_records)
            total_cost = sum(r.get('cost', 0) for r in filtered_records)
            net_profit = total_income - total_cost
            
            transport_recs = [r for r in filtered_records if r['type'] == '화물운송']
            total_dist = sum(r.get('distance', 0) for r in transport_recs)
            trip_count = len(transport_recs)
            
            fuel_recs = [r for r in filtered_records if r['type'] == '주유소']
            total_fuel = sum(r.get('liters', 0) for r in fuel_recs)

            # 메트릭 표시
            m1, m2, m3 = st.columns(3)
            m1.metric("총 수입", f"{total_income:,} 원")
            m2.metric("총 지출", f"{total_cost:,} 원")
            m3.metric("순수익", f"{net_profit:,} 원", delta_color="normal")
            
            st.divider()
            
            m4, m5, m6 = st.columns(3)
            m4.metric("운행 건수", f"{trip_count} 건")
            m5.metric("총 운행 거리", f"{total_dist:.1f} km")
            m6.metric("총 주유량", f"{total_fuel:.1f} L")
            
            # 연비 계산 (단순)
            if total_fuel > 0:
                st.info(f"💡 이번 달 평균 연비 (추정): {total_dist / total_fuel:.2f} km/L")
        else:
            st.info("통계 데이터가 없습니다. 조회 탭에서 날짜를 확인하세요.")

    # ----------------------------------------------------
    # 4. 설정 탭
    # ----------------------------------------------------
    with tab4:
        st.header("데이터 관리")
        
        # JSON 다운로드
        json_str = json.dumps(dm.data, ensure_ascii=False, indent=2)
        st.download_button(
            label="📥 전체 데이터 백업 (JSON 다운로드)",
            data=json_str,
            file_name=f"cargo_backup_{datetime.now().strftime('%Y%m%d')}.json",
            mime="application/json"
        )
        
        st.divider()
        
        # JSON 업로드
        st.subheader("데이터 복원")
        uploaded_file = st.file_uploader("백업 파일(.json) 업로드", type="json")
        if uploaded_file is not None:
            if st.button("데이터 덮어쓰기 (복원)"):
                try:
                    loaded_data = json.load(uploaded_file)
                    dm.data = loaded_data
                    dm.save_data()
                    st.success("데이터가 복원되었습니다!")
                    st.rerun()
                except Exception as e:
                    st.error(f"파일 형식 오류: {e}")

if __name__ == "__main__":
    main()