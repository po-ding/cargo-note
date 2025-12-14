import streamlit as st
import json
import os
import pandas as pd
from datetime import datetime, timedelta
import time
import base64

# OCR 라이브러리 (에러 방지용 예외처리)
try:
    from PIL import Image
    import pytesseract
except ImportError:
    Image = None
    pytesseract = None

# ==========================================
# 0. 안전한 형변환 함수 (TypeError 방지 핵심)
# ==========================================
def safe_int(value):
    """None이나 문자열을 안전하게 정수로 변환"""
    try:
        if value is None: return 0
        return int(float(value))
    except:
        return 0

def safe_float(value):
    """None이나 문자열을 안전하게 실수로 변환"""
    try:
        if value is None: return 0.0
        return float(value)
    except:
        return 0.0

# ==========================================
# 1. UI/UX 스타일 설정
# ==========================================
def apply_custom_css():
    st.markdown("""
    <style>
        .block-container { padding-top: 1rem; padding-bottom: 3rem; }
        .stTabs [data-baseweb="tab-list"] { gap: 5px; flex-wrap: wrap; }
        .stTabs [data-baseweb="tab"] {
            height: 45px; white-space: nowrap; background-color: #f8f9fa;
            border-radius: 5px; color: #495057; font-size: 14px; padding: 0 15px; border: 1px solid #dee2e6;
        }
        .stTabs [aria-selected="true"] {
            background-color: #007bff !important; color: white !important; border-color: #007bff !important;
        }
        div[data-testid="metric-container"] {
            background-color: #f8f9fa; border: 1px solid #e9ecef; padding: 10px; border-radius: 8px; text-align: center;
        }
    </style>
    """, unsafe_allow_html=True)

# ==========================================
# 2. 데이터 관리 클래스
# ==========================================
class DataManager:
    def __init__(self, filename="cargo_data_final_v3.json"):
        self.filename = filename
        self.data = {
            "records": [],
            "centers": ["안성", "안산", "용인", "이천", "인천"],
            "locations": {}, 
            "fares": {},      
            "distances": {},
            "costs": {},
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
        if record['type'] in ['화물운송', '대기', '공차이동']:
            f, t = record.get('from'), record.get('to')
            if f and f not in self.data['centers']: self.data['centers'].append(f)
            if t and t not in self.data['centers']: self.data['centers'].append(t)
            
            if f and t:
                key = f"{f}-{t}"
                if safe_int(record.get('income')) > 0: self.data['fares'][key] = safe_int(record['income'])
                if safe_float(record.get('distance')) > 0: self.data['distances'][key] = safe_float(record['distance'])

        if record.get('expenseItem') and record.get('expenseItem') not in self.data['expense_items']:
            self.data['expense_items'].append(record.get('expenseItem'))
            self.data['expense_items'].sort()
            
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
        try:
            dt = datetime.strptime(f"{d} {t}", "%Y-%m-%d %H:%M")
            if dt.hour < 4: dt -= timedelta(days=1)
            return dt.strftime("%Y-%m-%d")
        except: return str(d)

# ==========================================
# 3. 리포트 생성 함수
# ==========================================
def generate_html_report(year, month, records, period_type="full", detailed=False):
    s_day = 16 if period_type == "second" else 1
    e_day = 15 if period_type == "first" else 31
    period_str = "1일 ~ 말일" if period_type == "full" else f"{s_day}일 ~ {e_day}일"
    
    html = f"""
    <html><head><style>
        body {{ font-family: sans-serif; padding: 20px; }}
        table {{ width: 100%; border-collapse: collapse; font-size: 12px; margin-bottom: 20px; }}
        th, td {{ border: 1px solid #ccc; padding: 6px; text-align: center; }}
        th {{ background: #eee; }}
        .inc {{ color: blue; }} .exp {{ color: red; }}
    </style></head><body>
        <h2>{year}년 {month}월 {period_str} 운송 기록</h2>
        <table><thead><tr><th>날짜</th><th>내용</th><th>구분</th>{'<th>금액</th>' if detailed else ''}</tr></thead><tbody>
    """
    for r in records:
        if r['type'] == '운행종료': continue
        desc = r.get('expenseItem') or r.get('supplyItem')
        if r['type'] in ['화물운송', '대기']: desc = f"{r.get('from')} -> {r.get('to')}"
        elif r['type'] == '주유소': desc = f"{r.get('brand')} ({safe_float(r.get('liters'))}L)"
        
        row = f"<tr><td>{r['date']} {r['time']}</td><td>{desc}</td><td>{r['type']}</td>"
        if detailed:
            inc = safe_int(r.get('income'))
            cost = safe_int(r.get('cost'))
            val = ""
            if inc: val += f"<span class='inc'>+{inc:,}</span> "
            if cost: val += f"<span class='exp'>-{cost:,}</span>"
            row += f"<td>{val}</td>"
        row += "</tr>"
        html += row
    html += "</tbody></table></body></html>"
    return html

# ==========================================
# 4. 메인 앱
# ==========================================
def main():
    st.set_page_config(page_title="Cargo Note", page_icon="🚛", layout="centered")
    apply_custom_css()

    if 'dm' not in st.session_state: st.session_state.dm = DataManager()
    dm = st.session_state.dm

    st.markdown("### 🚛 Cargo Note Pro")

    # --- 상단 대시보드 (안전 계산 적용) ---
    now = datetime.now()
    cur_ym = now.strftime("%Y-%m")
    m_recs = [r for r in dm.data['records'] if dm.get_stat_date(r['date'], r['time']).startswith(cur_ym)]
    
    # Safe calc
    inc = sum(safe_int(r.get('income')) for r in m_recs)
    exp = sum(safe_int(r.get('cost')) for r in m_recs)
    
    with st.expander(f"📊 {now.month}월 현황 요약 (펼치기)", expanded=False):
        c1, c2, c3 = st.columns(3)
        c1.metric("수입", f"{inc:,}")
        c2.metric("지출", f"{exp:,}")
        c3.metric("순익", f"{inc-exp:,}")

    # --- 입력 폼 ---
    with st.expander("📝 기록 입력", expanded=True):
        with st.form("main_form", clear_on_submit=True):
            fc1, fc2 = st.columns(2)
            i_date = fc1.date_input("날짜", datetime.now())
            i_time = fc2.time_input("시간", datetime.now(), step=60)
            i_type = st.selectbox("종류", ["화물운송", "수입", "주유소", "소모품", "지출", "대기", "공차이동", "운행취소"])
            
            f_data = {}
            i_inc = 0.0
            i_cst = 0.0

            if i_type in ["화물운송", "대기", "공차이동"]:
                cen_list = [""] + dm.data['centers']
                c_f = st.selectbox("상차", cen_list, key="c_f")
                c_t = st.selectbox("하차", cen_list, key="c_t")
                
                k = f"{c_f}-{c_t}"
                # Safe casting for None values from JSON
                def_dist = safe_float(dm.data['distances'].get(k))
                def_inc = safe_int(dm.data['fares'].get(k)) / 10000.0
                
                dist = st.number_input("거리(km)", value=def_dist)
                f_data.update({"from": c_f, "to": c_t, "distance": dist})
                
                if i_type != "공차이동":
                    i_inc = st.number_input("수입(만원)", value=def_inc, step=1.0)
                
                if c_f in dm.data['locations']: st.caption(f"[상] {dm.data['locations'][c_f].get('address')}")
                if c_t in dm.data['locations']: st.caption(f"[하] {dm.data['locations'][c_t].get('address')}")

            elif i_type == "주유소":
                pc1, pc2 = st.columns(2)
                u_p = pc1.number_input("단가", step=10)
                lit = pc2.number_input("리터", step=1.0)
                brd = st.selectbox("브랜드", ["S-OIL", "SK에너지", "GS칼텍스", "현대오일뱅크", "기타"])
                sub = st.number_input("보조금(원)", value=0)
                f_data.update({"unitPrice": u_p, "liters": lit, "brand": brd, "subsidy": sub})
                i_cst = st.number_input("지출(만원)", value=(u_p*lit)/10000.0, step=1.0)

            else:
                txt = st.text_input("내역")
                f_data["item"] = txt
                if i_type == "수입": i_inc = st.number_input("수입(만원)", step=1.0)
                else: i_cst = st.number_input("지출(만원)", step=1.0)

            if st.form_submit_button("저장하기", type="primary", use_container_width=True):
                new_r = {
                    "id": int(datetime.now().timestamp()*1000),
                    "date": i_date.strftime("%Y-%m-%d"),
                    "time": i_time.strftime("%H:%M"),
                    "type": i_type,
                    "income": int(i_inc*10000), "cost": int(i_cst*10000),
                    **f_data
                }
                if "item" in f_data:
                    if i_type == "소모품": new_r["supplyItem"] = f_data["item"]
                    else: new_r["expenseItem"] = f_data["item"]
                
                dm.add_record(new_r)
                st.toast("저장 완료!")
                time.sleep(0.5)
                st.rerun()

    # --- 탭 구성 ---
    st.markdown("---")
    tabs = st.tabs(["오늘", "일별", "주별", "월별", "📊 통계/출력", "⚙️ 설정/복원"])

    # 1. 오늘
    with tabs[0]:
        if 'v_date' not in st.session_state: st.session_state.v_date = datetime.now()
        
        nc1, nc2, nc3 = st.columns([1, 2, 1])
        if nc1.button("◀"): 
            st.session_state.v_date -= timedelta(days=1)
            st.rerun()
        with nc2:
            st.markdown(f"<h4 style='text-align:center; margin:0'>{st.session_state.v_date.strftime('%Y-%m-%d')}</h4>", unsafe_allow_html=True)
        if nc3.button("▶"): 
            st.session_state.v_date += timedelta(days=1)
            st.rerun()

        t_str = st.session_state.v_date.strftime("%Y-%m-%d")
        d_recs = [r for r in dm.data['records'] if dm.get_stat_date(r['date'], r['time']) == t_str]
        d_recs.sort(key=lambda x: x['time'])
        
        if d_recs:
            for r in d_recs:
                with st.container():
                    info = r['type']
                    if r['type'] in ['화물운송', '대기']: info += f" ({r.get('from')}→{r.get('to')})"
                    elif r.get('expenseItem'): info += f" ({r.get('expenseItem')})"
                    
                    c1, c2 = st.columns([4, 1])
                    c1.text(f"{r['time']} | {info}")
                    if c2.button("삭제", key=f"d{r['id']}"):
                        dm.delete_record(r['id'])
                        st.rerun()
        else: st.info("기록이 없습니다.")

    # 2. 일별
    with tabs[1]:
        sy = st.selectbox("년", range(2023, 2030), index=2, key="dy")
        sm = st.selectbox("월", range(1, 13), index=datetime.now().month-1, key="dm")
        target = [r for r in dm.data['records'] if dm.get_stat_date(r['date'], r['time']).startswith(f"{sy}-{sm:02d}")]
        
        daily = {}
        for r in target:
            d = dm.get_stat_date(r['date'], r['time'])
            if d not in daily: daily[d] = {'inc':0, 'exp':0}
            daily[d]['inc'] += safe_int(r.get('income'))
            daily[d]['exp'] += safe_int(r.get('cost'))
        
        if daily:
            rows = [{"날짜":k, "수입":f"{v['inc']:,}", "지출":f"{v['exp']:,}", "합계":f"{v['inc']-v['exp']:,}"} for k,v in sorted(daily.items(), reverse=True)]
            st.dataframe(pd.DataFrame(rows), hide_index=True, use_container_width=True)
        else: st.write("데이터 없음")

    # 3. 주별
    with tabs[2]:
        if target:
            weeks = {}
            for r in target:
                try:
                    dt = datetime.strptime(dm.get_stat_date(r['date'], r['time']), "%Y-%m-%d")
                    wk = f"{(dt.day-1)//7 + 1}주차"
                    if wk not in weeks: weeks[wk] = {'inc':0, 'exp':0}
                    weeks[wk]['inc'] += safe_int(r.get('income'))
                    weeks[wk]['exp'] += safe_int(r.get('cost'))
                except: continue
            w_rows = [{"주차":k, "수입":f"{v['inc']:,}", "지출":f"{v['exp']:,}", "합계":f"{v['inc']-v['exp']:,}"} for k,v in sorted(weeks.items())]
            st.dataframe(pd.DataFrame(w_rows), hide_index=True, use_container_width=True)
        else: st.write("데이터 없음")

    # 4. 월별
    with tabs[3]:
        my = st.selectbox("년도", range(2023, 2030), index=2, key="my")
        monthly = {}
        for r in dm.data['records']:
            if r['date'].startswith(str(my)):
                m = r['date'][:7]
                if m not in monthly: monthly[m] = {'inc':0, 'exp':0}
                monthly[m]['inc'] += safe_int(r.get('income'))
                monthly[m]['exp'] += safe_int(r.get('cost'))
        m_rows = [{"월":k, "수입":f"{v['inc']:,}", "지출":f"{v['exp']:,}", "합계":f"{v['inc']-v['exp']:,}"} for k,v in sorted(monthly.items(), reverse=True)]
        st.dataframe(pd.DataFrame(m_rows), hide_index=True, use_container_width=True)

    # 5. 통계/출력
    with tabs[4]:
        st.subheader("🖨️ 운송내역서 출력")
        py = st.selectbox("출력 년도", range(2023, 2030), index=2, key="py")
        pm = st.selectbox("출력 월", range(1, 13), index=datetime.now().month-1, key="pm")
        
        tgt_recs = [r for r in dm.data['records'] if dm.get_stat_date(r['date'], r['time']).startswith(f"{py}-{pm:02d}")]
        
        b1, b2, b3 = st.columns(3)
        if b1.button("1~15일"):
            h = generate_html_report(py, pm, tgt_recs, "first")
            st.markdown(f'<a href="data:text/html;base64,{base64.b64encode(h.encode()).decode()}" download="report_1st.html">📥 다운로드</a>', unsafe_allow_html=True)
        if b2.button("16~말일"):
            h = generate_html_report(py, pm, tgt_recs, "second")
            st.markdown(f'<a href="data:text/html;base64,{base64.b64encode(h.encode()).decode()}" download="report_2nd.html">📥 다운로드</a>', unsafe_allow_html=True)
        if b3.button("전체"):
            h = generate_html_report(py, pm, tgt_recs, "full", detailed=True)
            st.markdown(f'<a href="data:text/html;base64,{base64.b64encode(h.encode()).decode()}" download="report_full.html">📥 다운로드</a>', unsafe_allow_html=True)
            
        st.divider()
        st.subheader("⛽ 유가보조금 & 거리")
        f_recs = [r for r in tgt_recs if r['type']=='주유소']
        tot_lit = sum(safe_float(r.get('liters')) for r in f_recs)
        limit = safe_float(dm.data['settings'].get('subsidy_limit'))
        
        if limit > 0: st.progress(min(1.0, tot_lit/limit), text=f"사용 {tot_lit:.1f}L / 한도 {limit}L")
        else: st.warning("한도 미설정")
            
        corr = safe_float(dm.data['settings'].get('mileage_correction'))
        dist_sum = sum(safe_float(r.get('distance')) for r in tgt_recs if r['type']=='화물운송')
        st.metric("총 운행거리 (보정포함)", f"{dist_sum + corr:.1f} km")

    # 6. 설정/복원
    with tabs[5]:
        st.subheader("⚙️ 설정 & 데이터 관리")
        
        with st.expander("📍 지역 관리"):
            n_name = st.text_input("새 지역명")
            n_addr = st.text_input("주소")
            if st.button("추가"):
                dm.add_center(n_name, n_addr, "")
                st.success("완료")
                st.rerun()

        with st.expander("🛠️ 기본값 설정"):
            nl = st.number_input("보조금 한도(L)", value=safe_float(dm.data['settings'].get('subsidy_limit')))
            nc = st.number_input("거리 보정(km)", value=safe_float(dm.data['settings'].get('mileage_correction')))
            if st.button("설정 저장"):
                dm.data['settings'].update({"subsidy_limit": nl, "mileage_correction": nc})
                dm.save_data()
                st.success("저장됨")

        st.divider()
        st.markdown("##### 💾 백업 및 복원")
        js = json.dumps(dm.data, ensure_ascii=False, indent=2)
        st.download_button("📂 백업(다운로드)", js, "cargo_backup.json", "application/json")
        
        up_file = st.file_uploader("📂 복원(파일선택)", type=["json"])
        if up_file and st.button("⚠️ 데이터 덮어쓰기"):
            try:
                up_file.seek(0)
                loaded = json.loads(up_file.read().decode('utf-8'))
                dm.data = loaded
                dm.save_data()
                st.success("복원 완료!")
                time.sleep(1)
                st.rerun()
            except Exception as e:
                st.error(f"실패: {e}")

if __name__ == "__main__":
    main()