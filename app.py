import streamlit as st
import json
import os
import pandas as pd
from datetime import datetime, timedelta
import time

# ==========================================
# 0. 스타일 설정 (CSS) - UI 개선
# ==========================================
def apply_custom_css():
    st.markdown("""
    <style>
        .block-container { padding-top: 1rem; padding-bottom: 5rem; }
        h1 { font-size: 1.8rem; color: #333; }
        h3 { font-size: 1.2rem; border-bottom: 2px solid #eee; padding-bottom: 0.5rem; margin-top: 1rem; }
        .metric-card {
            background-color: #f8f9fa; border: 1px solid #eee; border-radius: 8px;
            padding: 15px; text-align: center; box-shadow: 0 2px 4px rgba(0,0,0,0.05);
        }
        .stTabs [data-baseweb="tab-list"] { gap: 10px; }
        .stTabs [data-baseweb="tab"] {
            height: 50px; white-space: pre-wrap; background-color: #f1f1f1; border-radius: 5px;
            color: #555; font-weight: bold;
        }
        .stTabs [aria-selected="true"] {
            background-color: #007bff; color: white;
        }
        /* 입력 폼 강조 */
        [data-testid="stForm"] { background-color: #ffffff; border: 1px solid #ddd; padding: 20px; border-radius: 10px; }
    </style>
    """, unsafe_allow_html=True)

# ==========================================
# 1. 데이터 관리 클래스 (로직 강화)
# ==========================================
class DataManager:
    def __init__(self, filename="cargo_data_final.json"):
        self.filename = filename
        self.data = {
            "records": [],
            "centers": ["안성", "안산", "용인", "이천", "인천"],
            "locations": {}, 
            "fares": {},      
            "distances": {},  
            "expense_items": [],
            "settings": {"subsidy_limit": 0, "mileage_correction": 0}
        }
        self.load_data()

    def load_data(self):
        if os.path.exists(self.filename):
            try:
                with open(self.filename, 'r', encoding='utf-8') as f:
                    loaded = json.load(f)
                    for key in self.data:
                        if key in loaded:
                            if isinstance(self.data[key], dict): self.data[key].update(loaded[key])
                            elif isinstance(self.data[key], list): self.data[key] = loaded[key]
                            else: self.data[key] = loaded[key]
            except: pass

    def save_data(self):
        with open(self.filename, 'w', encoding='utf-8') as f:
            json.dump(self.data, f, ensure_ascii=False, indent=2)

    def add_record(self, record):
        # 자동 학습 로직
        if record['type'] in ['화물운송', '대기', '공차이동']:
            if record.get('from') and record.get('from') not in self.data['centers']:
                self.data['centers'].append(record.get('from'))
            if record.get('to') and record.get('to') not in self.data['centers']:
                self.data['centers'].append(record.get('to'))
            
            key = f"{record.get('from')}-{record.get('to')}"
            if record.get('income', 0) > 0: self.data['fares'][key] = record['income']
            if record.get('distance', 0) > 0: self.data['distances'][key] = record['distance']
            
        self.data['centers'].sort()
        self.data['records'].append(record)
        self.save_data()

    def add_center(self, name, address, memo):
        if name not in self.data['centers']:
            self.data['centers'].append(name)
            self.data['centers'].sort()
        self.data['locations'][name] = {"address": address, "memo": memo}
        self.save_data()

    def delete_record(self, record_id):
        self.data["records"] = [r for r in self.data["records"] if r['id'] != record_id]
        self.save_data()

    def get_stat_date(self, d, t):
        """04시 기준 날짜 계산"""
        dt = datetime.strptime(f"{d} {t}", "%Y-%m-%d %H:%M")
        if dt.hour < 4: dt -= timedelta(days=1)
        return dt.strftime("%Y-%m-%d")

# ==========================================
# 2. 메인 앱
# ==========================================
def main():
    st.set_page_config(page_title="Cargo Note", page_icon="🚛", layout="centered")
    apply_custom_css() # CSS 적용

    if 'dm' not in st.session_state:
        st.session_state.dm = DataManager()
    dm = st.session_state.dm

    # --- 상단 헤더 ---
    c1, c2 = st.columns([3, 1])
    c1.markdown("# 🚛 Cargo<span style='color:#007bff'>Note</span>", unsafe_allow_html=True)
    if c2.button("🔄 새로고침"): st.rerun()

    # --- 데이터 요약 섹션 (Dashboard) ---
    # 현재 월 기준 요약 (HTML 버전의 상단 요약 기능 복구)
    now = datetime.now()
    cur_ym = now.strftime("%Y-%m")
    month_recs = [r for r in dm.data['records'] if dm.get_stat_date(r['date'], r['time']).startswith(cur_ym)]
    
    inc = sum(r.get('income', 0) for r in month_recs)
    exp = sum(r.get('cost', 0) for r in month_recs)
    dist = sum(r.get('distance', 0) for r in month_recs if r['type']=='화물운송')
    
    with st.expander(f"📊 {now.month}월 데이터 요약 (클릭하여 펼치기)", expanded=False):
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("총 수입", f"{inc:,}", "만원 단위 자동변환됨" if False else None)
        m2.metric("총 지출", f"{exp:,}")
        m3.metric("순수익", f"{inc-exp:,}", delta_color="normal")
        m4.metric("운행거리", f"{dist:.1f} km")

    # ==========================================
    # [입력 폼] - 항상 상단에 위치
    # ==========================================
    with st.expander("📝 새 기록 입력하기", expanded=True):
        with st.form("entry_form", clear_on_submit=True):
            f_c1, f_c2 = st.columns(2)
            in_date = f_c1.date_input("날짜", datetime.now())
            in_time = f_c2.time_input("시간", datetime.now(), step=60)
            
            in_type = st.selectbox("기록 종류", ["화물운송", "수입", "주유소", "소모품", "지출", "대기", "공차이동"])
            
            # 동적 필드 관리
            form_data = {}
            
            if in_type in ["화물운송", "대기", "공차이동"]:
                # 자동완성 데이터 로드
                centers = [""] + dm.data['centers']
                c_from = st.selectbox("상차지", centers, key="f_from")
                c_to = st.selectbox("하차지", centers, key="f_to")
                
                # 주소 표시 (원본 기능 복구)
                loc_info = []
                if c_from in dm.data['locations']: loc_info.append(f"[상] {dm.data['locations'][c_from].get('address','')}")
                if c_to in dm.data['locations']: loc_info.append(f"[하] {dm.data['locations'][c_to].get('address','')}")
                if loc_info: st.caption(" / ".join(loc_info))
                
                # 거리/금액 자동 채우기
                auto_dist = 0.0
                auto_inc = 0.0
                if c_from and c_to:
                    key = f"{c_from}-{c_to}"
                    auto_dist = dm.data['distances'].get(key, 0.0)
                    auto_inc = dm.data['fares'].get(key, 0) / 10000.0
                
                dist = st.number_input("거리(km)", value=float(auto_dist))
                form_data.update({"from": c_from, "to": c_to, "distance": dist})
                
                # 수입 입력
                in_income = st.number_input("수입 (만원)", value=float(auto_inc), step=1.0)
                in_cost = 0.0

            elif in_type == "주유소":
                uc1, uc2 = st.columns(2)
                u_price = uc1.number_input("단가", step=10)
                liters = uc2.number_input("주유량(L)", step=1.0)
                brand = st.selectbox("브랜드", ["S-OIL", "SK에너지", "GS칼텍스", "현대오일뱅크", "기타"])
                form_data.update({"unitPrice": u_price, "liters": liters, "brand": brand})
                
                in_income = 0.0
                calc_cost = (u_price * liters) / 10000.0
                in_cost = st.number_input("지출 (만원)", value=calc_cost, step=1.0)
            
            else: # 지출, 수입, 소모품
                item = st.text_input("내역 (적요)")
                form_data["item"] = item
                
                ic1, ic2 = st.columns(2)
                if in_type == "수입":
                    in_income = ic1.number_input("수입 (만원)", step=1.0)
                    in_cost = 0.0
                else:
                    in_income = 0.0
                    in_cost = ic2.number_input("지출 (만원)", step=1.0)

            # 저장 버튼
            submitted = st.form_submit_button("💾 기록 저장", type="primary", use_container_width=True)
            if submitted:
                new_rec = {
                    "id": int(datetime.now().timestamp() * 1000),
                    "date": in_date.strftime("%Y-%m-%d"),
                    "time": in_time.strftime("%H:%M"),
                    "type": in_type,
                    "income": int(in_income * 10000),
                    "cost": int(in_cost * 10000),
                    **form_data
                }
                # 키 이름 통일
                if "item" in form_data:
                    if in_type == "소모품": new_rec["supplyItem"] = form_data["item"]
                    else: new_rec["expenseItem"] = form_data["item"]
                
                dm.add_record(new_rec)
                st.toast("저장되었습니다!")
                time.sleep(0.5)
                st.rerun()

    # ==========================================
    # [뷰 섹션] - 탭 구조 복원 (오늘/일별/주별/월별)
    # ==========================================
    st.markdown("### 📋 기록 조회")
    
    # 탭 메뉴 구성
    tabs = st.tabs(["오늘", "일별", "주별", "월별", "⚙️ 설정/지역관리"])

    # --- TAB 1: 오늘 (Today) ---
    with tabs[0]:
        # 오늘 날짜 (04시 기준)
        today_stat = dm.get_stat_date(datetime.now().strftime("%Y-%m-%d"), datetime.now().strftime("%H:%M"))
        
        # 날짜 이동 버튼
        col_nav1, col_nav2, col_nav3 = st.columns([1, 2, 1])
        if 'view_date' not in st.session_state: st.session_state.view_date = datetime.strptime(today_stat, "%Y-%m-%d")
        
        if col_nav1.button("◀ 전일"): 
            st.session_state.view_date -= timedelta(days=1)
            st.rerun()
        with col_nav2:
            display_date = st.date_input("조회일", st.session_state.view_date, label_visibility="collapsed")
            if display_date != st.session_state.view_date.date():
                st.session_state.view_date = datetime.combine(display_date, datetime.min.time())
                st.rerun()
        if col_nav3.button("익일 ▶"): 
            st.session_state.view_date += timedelta(days=1)
            st.rerun()

        target_date_str = st.session_state.view_date.strftime("%Y-%m-%d")
        day_recs = [r for r in dm.data['records'] if dm.get_stat_date(r['date'], r['time']) == target_date_str]
        day_recs.sort(key=lambda x: x['time'])

        if day_recs:
            # 오늘의 요약
            d_inc = sum(r.get('income',0) for r in day_recs)
            d_exp = sum(r.get('cost',0) for r in day_recs)
            st.info(f"📅 {target_date_str} | 수입: {d_inc:,}원 | 지출: {d_exp:,}원 | 정산: {d_inc-d_exp:,}원")
            
            # 테이블 표시
            df_day = []
            for r in day_recs:
                detail = r['type']
                if r['type'] in ['화물운송', '대기']: detail = f"{r.get('from')} → {r.get('to')}"
                elif r['type'] == '주유소': detail = f"{r.get('brand')} ({r.get('liters')}L)"
                elif 'expenseItem' in r: detail = r.get('expenseItem')
                
                df_day.append({
                    "시간": r['time'],
                    "구분": r['type'],
                    "내용": detail,
                    "금액": f"{r.get('income',0) - r.get('cost',0):,}",
                    "ID": r['id']
                })
            st.dataframe(pd.DataFrame(df_day).drop(columns=["ID"]), hide_index=True, use_container_width=True)
            
            # 삭제
            del_target = st.selectbox("삭제할 항목", df_day, format_func=lambda x: f"{x['시간']} | {x['구분']} | {x['내용']}")
            if st.button("선택 항목 삭제"):
                dm.delete_record(del_target['ID'])
                st.rerun()
        else:
            st.warning(f"{target_date_str} 기록이 없습니다.")

    # --- TAB 2: 일별 (Daily) ---
    with tabs[1]:
        d_year = st.selectbox("년도", range(2023, 2030), index=2, key="d_y")
        d_month = st.selectbox("월", range(1, 13), index=datetime.now().month-1, key="d_m")
        target_ym = f"{d_year}-{d_month:02d}"
        
        # 일별 집계
        daily_stats = {}
        target_recs = [r for r in dm.data['records'] if dm.get_stat_date(r['date'], r['time']).startswith(target_ym)]
        
        for r in target_recs:
            s_date = dm.get_stat_date(r['date'], r['time'])
            if s_date not in daily_stats: daily_stats[s_date] = {'inc':0, 'exp':0, 'dist':0}
            daily_stats[s_date]['inc'] += r.get('income', 0)
            daily_stats[s_date]['exp'] += r.get('cost', 0)
            if r['type'] == '화물운송': daily_stats[s_date]['dist'] += r.get('distance', 0)
            
        if daily_stats:
            rows = []
            for d in sorted(daily_stats.keys(), reverse=True):
                day_d = daily_stats[d]
                rows.append({
                    "일자": d,
                    "수입": f"{day_d['inc']:,}",
                    "지출": f"{day_d['exp']:,}",
                    "정산": f"{day_d['inc']-day_d['exp']:,}",
                    "거리": f"{day_d['dist']:.1f}"
                })
            st.dataframe(pd.DataFrame(rows), hide_index=True, use_container_width=True)
        else:
            st.write("데이터 없음")

    # --- TAB 3: 주별 (Weekly) ---
    with tabs[2]:
        # 월별 데이터를 주차별로 그룹화
        if not target_recs:
            st.write("해당 월의 데이터가 없습니다.")
        else:
            weekly_data = {}
            for r in target_recs:
                s_date = datetime.strptime(dm.get_stat_date(r['date'], r['time']), "%Y-%m-%d")
                # 주차 계산 (대략적)
                week_num = (s_date.day - 1) // 7 + 1
                if week_num > 4: week_num = 4 # 5주차는 4주차에 포함하거나 별도 처리 (여기선 편의상 4주차로)
                
                k = f"{week_num}주차"
                if k not in weekly_data: weekly_data[k] = {'inc':0, 'exp':0, 'cnt':0}
                weekly_data[k]['inc'] += r.get('income', 0)
                weekly_data[k]['exp'] += r.get('cost', 0)
                if r['type'] == '화물운송': weekly_data[k]['cnt'] += 1
            
            w_rows = []
            for w in sorted(weekly_data.keys()):
                wd = weekly_data[w]
                w_rows.append({
                    "주차": w,
                    "수입": f"{wd['inc']:,}",
                    "지출": f"{wd['exp']:,}",
                    "정산": f"{wd['inc']-wd['exp']:,}",
                    "운행수": f"{wd['cnt']}건"
                })
            st.dataframe(pd.DataFrame(w_rows), hide_index=True, use_container_width=True)

    # --- TAB 4: 월별 (Monthly) ---
    with tabs[3]:
        m_year = st.selectbox("조회 년도", range(2023, 2030), index=2, key="m_y")
        m_recs = [r for r in dm.data['records'] if r['date'].startswith(str(m_year))]
        
        monthly_stats = {}
        for r in m_recs:
            ym = dm.get_stat_date(r['date'], r['time'])[:7] # YYYY-MM
            if ym not in monthly_stats: monthly_stats[ym] = {'inc':0, 'exp':0}
            monthly_stats[ym]['inc'] += r.get('income', 0)
            monthly_stats[ym]['exp'] += r.get('cost', 0)
            
        if monthly_stats:
            m_rows = []
            for m in sorted(monthly_stats.keys(), reverse=True):
                md = monthly_stats[m]
                m_rows.append({
                    "월": m,
                    "수입": f"{md['inc']:,}",
                    "지출": f"{md['exp']:,}",
                    "순익": f"{md['inc']-md['exp']:,}"
                })
            st.dataframe(pd.DataFrame(m_rows), hide_index=True, use_container_width=True)
        else:
            st.write("기록 없음")

    # --- TAB 5: 설정 및 지역 관리 (Add Center 기능 복구) ---
    with tabs[4]:
        st.subheader("⚙️ 설정 및 지역 관리")
        
        # 1. 새 지역 추가 (문제 해결됨)
        with st.expander("➕ 새 지역/거래처 추가", expanded=False):
            with st.form("add_center_form"):
                new_name = st.text_input("지역명 (예: 김포센터)")
                new_addr = st.text_input("주소")
                new_memo = st.text_input("메모 (출입방법 등)")
                
                if st.form_submit_button("추가하기"):
                    if new_name:
                        dm.add_center(new_name, new_addr, new_memo)
                        st.success(f"'{new_name}' 추가 완료! 입력 탭에서 바로 확인 가능합니다.")
                        time.sleep(1)
                        st.rerun()
                    else:
                        st.error("지역명을 입력해주세요.")

        # 2. 기존 지역 관리
        with st.expander("📝 등록된 지역 수정"):
            target_cen = st.selectbox("수정할 지역 선택", dm.data['centers'])
            if target_cen:
                info = dm.data['locations'].get(target_cen, {})
                mod_addr = st.text_input("주소 수정", value=info.get('address', ''))
                mod_memo = st.text_input("메모 수정", value=info.get('memo', ''))
                if st.button("수정 저장"):
                    dm.add_center(target_cen, mod_addr, mod_memo)
                    st.success("수정됨")

        # 3. 데이터 백업
        st.divider()
        json_str = json.dumps(dm.data, ensure_ascii=False, indent=2)
        st.download_button("📂 전체 데이터 백업 (JSON)", json_str, "cargo_backup.json")
        
        # 데이터 초기화
        if st.button("⚠️ 데이터 전체 초기화 (주의)"):
            if os.path.exists(dm.filename):
                os.remove(dm.filename)
                st.session_state.clear()
                st.rerun()

if __name__ == "__main__":
    main()