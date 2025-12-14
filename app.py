import streamlit as st
import json
import os
import pandas as pd
from datetime import datetime, timedelta
import time
import base64

# OCR 기능을 위한 라이브러리 (에러 방지 처리)
try:
    from PIL import Image
    import pytesseract
except ImportError:
    Image = None
    pytesseract = None

# ==========================================
# 1. 데이터 및 로직 관리 클래스
# ==========================================

class DataManager:
    def __init__(self, filename="cargo_data_full.json"):
        self.filename = filename
        self.data = {
            "records": [],
            "centers": ["안성", "안산", "용인", "이천", "인천"],
            "locations": {},  # {center_name: {address: "", memo: ""}}
            "fares": {},      # {from-to: income}
            "distances": {},  # {from-to: distance}
            "costs": {},      # {from-to: cost}
            "expense_items": [],
            "settings": {
                "subsidy_limit": 0,
                "mileage_correction": 0
            }
        }
        self.load_data()

    def load_data(self):
        if os.path.exists(self.filename):
            try:
                with open(self.filename, 'r', encoding='utf-8') as f:
                    loaded = json.load(f)
                    # 깊은 병합 (기존 키 보존)
                    for key in self.data:
                        if key in loaded:
                            if isinstance(self.data[key], dict):
                                self.data[key].update(loaded[key])
                            elif isinstance(self.data[key], list):
                                # 리스트는 덮어쓰거나 합치기 (여기선 덮어쓰기 전략)
                                self.data[key] = loaded[key]
                            else:
                                self.data[key] = loaded[key]
            except Exception as e:
                st.error(f"데이터 로드 실패: {e}")

    def save_data(self):
        try:
            with open(self.filename, 'w', encoding='utf-8') as f:
                json.dump(self.data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            st.error(f"저장 실패: {e}")

    def update_location(self, name, address, memo):
        if name not in self.data["centers"]:
            self.data["centers"].append(name)
            self.data["centers"].sort()
        
        self.data["locations"][name] = {"address": address, "memo": memo}
        self.save_data()

    def add_record(self, record):
        # 자동 학습: 운송 구간 정보 저장
        if record['type'] in ['화물운송', '대기', '공차이동']:
            if record.get('from') and record.get('to'):
                key = f"{record['from']}-{record['to']}"
                if record.get('income', 0) > 0: self.data['fares'][key] = record['income']
                if record.get('distance', 0) > 0: self.data['distances'][key] = record['distance']
                if record.get('cost', 0) > 0: self.data['costs'][key] = record['cost']
                
            # 센터 목록 업데이트
            for loc in [record.get('from'), record.get('to')]:
                if loc and loc not in self.data['centers']:
                    self.data['centers'].append(loc)
                    self.data['centers'].sort()

        # 자동 학습: 지출 항목
        if record.get('expenseItem') and record.get('expenseItem') not in self.data['expense_items']:
            self.data['expense_items'].append(record.get('expenseItem'))
            self.data['expense_items'].sort()

        self.data["records"].append(record)
        self.save_data()

    def delete_record(self, record_id):
        self.data["records"] = [r for r in self.data["records"] if r['id'] != record_id]
        self.save_data()

    def get_statistical_date(self, date_str, time_str):
        """04시 기준 통계 날짜 계산"""
        try:
            dt = datetime.strptime(f"{date_str} {time_str}", "%Y-%m-%d %H:%M")
            if dt.hour < 4:
                dt = dt - timedelta(days=1)
            return dt.strftime("%Y-%m-%d")
        except:
            return date_str

    def calculate_duration(self, records):
        """운행 시간 계산 (웹 로직 포팅)"""
        if len(records) < 2: return "0h 0m"
        sorted_recs = sorted(records, key=lambda x: x['date'] + x['time'])
        total_minutes = 0
        for i in range(1, len(sorted_recs)):
            curr = datetime.strptime(f"{sorted_recs[i]['date']} {sorted_recs[i]['time']}", "%Y-%m-%d %H:%M")
            prev = datetime.strptime(f"{sorted_recs[i-1]['date']} {sorted_recs[i-1]['time']}", "%Y-%m-%d %H:%M")
            if sorted_recs[i-1]['type'] != '운행종료':
                diff = (curr - prev).total_seconds() / 60
                total_minutes += diff
        
        h = int(total_minutes // 60)
        m = int(total_minutes % 60)
        return f"{h}h {m}m"

# ==========================================
# 2. HTML 리포트 생성기 (프린트 기능)
# ==========================================
def generate_html_report(year, month, records, period_type="full", detailed=False):
    s_day = 16 if period_type == "second" else 1
    e_day = 15 if period_type == "first" else 31
    period_str = "1일 ~ 말일" if period_type == "full" else f"{s_day}일 ~ {e_day}일"
    
    # HTML 템플릿 (웹 코드의 스타일 차용)
    html = f"""
    <html>
    <head>
        <style>
            body {{ font-family: sans-serif; padding: 20px; }}
            table {{ width: 100%; border-collapse: collapse; font-size: 12px; margin-bottom: 20px; }}
            th, td {{ border: 1px solid #ccc; padding: 6px; text-align: center; }}
            th {{ background: #eee; }}
            .summary {{ background: #f9f9f9; padding: 15px; border: 1px solid #ddd; margin-bottom: 20px; }}
            .txt-red {{ color: #dc3545; font-weight: bold; }}
            .txt-blue {{ color: #007bff; font-weight: bold; }}
        </style>
    </head>
    <body>
        <h2>{year}년 {month}월 {period_str} 운송 기록</h2>
    """
    
    # 데이터 집계
    trans_inc = sum(r.get('income', 0) for r in records if r['type'] in ['화물운송', '대기'])
    trans_exp = sum(r.get('cost', 0) for r in records if r['type'] in ['화물운송', '대기'])
    fuel_cost = sum(r.get('cost', 0) for r in records if r['type'] == '주유소')
    fuel_sub = sum(r.get('subsidy', 0) for r in records if r['type'] == '주유소')
    gen_exp = sum(r.get('cost', 0) for r in records if r['type'] in ['지출', '소모품'])
    gen_inc = sum(r.get('income', 0) for r in records if r['type'] == '수입')
    
    total_rev = trans_inc + gen_inc
    total_spd = trans_exp + gen_exp + (fuel_cost - fuel_sub)
    profit = total_rev - total_spd

    html += f"""
        <div class="summary">
            <p><span class="txt-blue">[+] 총 수입: {total_rev:,} 원</span></p>
            <p><span class="txt-red">[-] 총 지출: {total_spd:,} 원</span> (실주유비 포함)</p>
            <hr>
            <h3>[=] 최종 순수익: {profit:,} 원</h3>
        </div>
        <h3>1. 운송 내역</h3>
        <table>
            <thead><tr><th>날짜</th><th>상차지</th><th>하차지</th><th>구분</th>
            {'<th>거리</th><th>수입</th>' if detailed else ''}
            </tr></thead>
            <tbody>
    """
    
    for r in records:
        if r['type'] not in ['화물운송', '대기', '공차이동', '운행취소']: continue
        row = f"<tr><td>{r['date'][5:]}</td><td>{r.get('from','')}</td><td>{r.get('to','')}</td><td>{r['type']}</td>"
        if detailed:
            row += f"<td>{r.get('distance','-')}</td><td>{r.get('income',0):,}</td>"
        row += "</tr>"
        html += row
        
    html += "</tbody></table></body></html>"
    return html

# ==========================================
# 3. 메인 Streamlit 앱
# ==========================================

def main():
    st.set_page_config(page_title="Cargo Note Pro", page_icon="🚛", layout="centered")
    
    if 'dm' not in st.session_state:
        st.session_state.dm = DataManager()
    
    dm = st.session_state.dm

    st.title("🚛 Cargo Note Pro")

    # 탭 구성
    tab_input, tab_view, tab_stats, tab_settings = st.tabs(["📝 기록 입력", "📋 기록 조회", "📊 통계", "⚙️ 설정/관리"])

    # ----------------------------------------------------
    # TAB 1: 기록 입력 (동적 UI 구현)
    # ----------------------------------------------------
    with tab_input:
        st.subheader("운송 및 지출 기록")
        
        # 1. 일시
        c1, c2 = st.columns(2)
        in_date = c1.date_input("날짜", datetime.now())
        in_time = c2.time_input("시간", datetime.now(), step=60)
        
        # 2. 종류
        in_type = st.selectbox("기록 종류", ["화물운송", "수입", "주유소", "소모품", "지출", "대기", "공차이동", "운행취소"])
        
        form_data = {}
        
        # 3. 동적 필드
        # A. 상하차 (화물운송, 대기, 공차이동)
        if in_type in ["화물운송", "대기", "공차이동", "운행취소"]:
            col_f, col_t = st.columns(2)
            # 상하차지 입력 + 자동완성 (selectbox + text_input 조합 대신 selectbox editable 사용불가하므로, selectbox에 '직접입력' 추가 로직)
            # 여기서는 편의상 SelectBox와 리스트 관리로 구현
            
            centers_list = [""] + dm.data['centers']
            f_center = col_f.selectbox("상차지", centers_list, key="sel_from")
            t_center = col_t.selectbox("하차지", centers_list, key="sel_to")
            
            # 주소/메모 표시
            if f_center and f_center in dm.data['locations']:
                loc = dm.data['locations'][f_center]
                col_f.caption(f"📍 {loc['address']} | 📝 {loc['memo']}")
            if t_center and t_center in dm.data['locations']:
                loc = dm.data['locations'][t_center]
                col_t.caption(f"📍 {loc['address']} | 📝 {loc['memo']}")
            
            # 자동완성 데이터 조회
            auto_dist = 0.0
            auto_income = 0.0
            auto_cost = 0.0
            if f_center and t_center:
                key = f"{f_center}-{t_center}"
                auto_dist = dm.data['distances'].get(key, 0.0)
                auto_income = dm.data['fares'].get(key, 0) / 10000.0 # 만원 단위
                auto_cost = dm.data['costs'].get(key, 0) / 10000.0
            
            form_data['distance'] = st.number_input("운행거리(km)", value=float(auto_dist), step=1.0)
            form_data['from'] = f_center
            form_data['to'] = t_center

        # B. 주유 (주유소)
        if in_type == "주유소":
            cf1, cf2 = st.columns(2)
            u_price = cf1.number_input("단가 (원/L)", min_value=0, step=10)
            liters = cf2.number_input("주유량 (L)", min_value=0.0, step=0.1)
            brand = st.selectbox("브랜드", ["S-OIL", "SK에너지", "GS칼텍스", "현대오일뱅크", "기타"])
            
            # 보조금 자동 계산 (리터당 약 345원 예시, 실제론 사용자 설정 가능하게 하면 좋음)
            # 여기선 입력받도록 함
            subsidy = st.number_input("유가보조금 (원)", value=0, help="자동으로 차감 계산됩니다.")
            
            form_data['unitPrice'] = u_price
            form_data['liters'] = liters
            form_data['brand'] = brand
            form_data['subsidy'] = subsidy
            
            # 주유비 자동계산 (화면 표시용)
            if u_price > 0 and liters > 0:
                est_cost = (u_price * liters) / 10000.0
            else:
                est_cost = 0.0
                
        # C. 내역 (수입, 지출, 소모품)
        if in_type in ["수입", "지출", "소모품"]:
            expense_list = [""] + dm.data['expense_items']
            # 새 항목 입력 가능하도록 text_input 병행
            ex_item_sel = st.selectbox("내역 선택", expense_list)
            ex_item_txt = st.text_input("내역 직접 입력 (새 항목)")
            
            final_item = ex_item_txt if ex_item_txt else ex_item_sel
            form_data['item'] = final_item
            
            if in_type == "소모품":
                form_data['mileage'] = st.number_input("교체 시점 누적 주행거리 (km)", value=0)

        # 4. 금액 (만원 단위 입력 -> 원 단위 저장)
        st.markdown("---")
        c_inc, c_exp = st.columns(2)
        
        in_income = 0.0
        in_cost = 0.0
        
        # 타입별 활성화
        if in_type in ["화물운송", "수입", "대기"]:
            in_income = c_inc.number_input("수입 금액 (만원)", value=float(auto_income) if 'auto_income' in locals() else 0.0, step=0.5)
        
        if in_type in ["주유소", "지출", "소모품", "공차이동"]:
            def_cost = float(est_cost) if 'est_cost' in locals() else (float(auto_cost) if 'auto_cost' in locals() else 0.0)
            in_cost = c_exp.number_input("지출 금액 (만원)", value=def_cost, step=0.5)

        # 5. 액션 버튼
        btn_col1, btn_col2, btn_col3 = st.columns([1, 1, 1])
        
        if btn_col1.button("💾 기록 저장", type="primary", use_container_width=True):
            new_record = {
                "id": int(datetime.now().timestamp() * 1000),
                "date": in_date.strftime("%Y-%m-%d"),
                "time": in_time.strftime("%H:%M"),
                "type": in_type,
                "income": int(in_income * 10000),
                "cost": int(in_cost * 10000),
                "distance": form_data.get('distance', 0),
                "from": form_data.get('from', ""),
                "to": form_data.get('to', ""),
                "unitPrice": form_data.get('unitPrice', 0),
                "liters": form_data.get('liters', 0),
                "subsidy": form_data.get('subsidy', 0), # 보조금 저장
                "brand": form_data.get('brand', ""),
                "expenseItem": form_data.get('item', "") if in_type != "소모품" else "",
                "supplyItem": form_data.get('item', "") if in_type == "소모품" else "",
                "mileage": form_data.get('mileage', 0)
            }
            dm.add_record(new_record)
            st.success("저장 완료!")
            time.sleep(0.5)
            st.rerun()

        if btn_col2.button("🛑 운행 종료", use_container_width=True):
             dm.add_record({
                "id": int(datetime.now().timestamp() * 1000),
                "date": in_date.strftime("%Y-%m-%d"),
                "time": in_time.strftime("%H:%M"),
                "type": "운행종료",
                "income": 0, "cost": 0, "distance": 0
            })
             st.info("운행 종료 처리됨.")
             st.rerun()

        if btn_col3.button("🔄 초기화"):
            st.rerun()

    # ----------------------------------------------------
    # TAB 2: 기록 조회 (오늘/전체)
    # ----------------------------------------------------
    with tab_view:
        st.subheader("📋 기록 조회")
        
        col_v1, col_v2 = st.columns(2)
        with col_v1:
            view_year = st.selectbox("연도", range(2023, 2030), index=2) # 2025 default
        with col_v2:
            view_month = st.selectbox("월", range(1, 13), index=datetime.now().month-1)
            
        target_ym = f"{view_year}-{view_month:02d}"
        
        # 데이터 필터링 (04시 기준)
        filtered = [r for r in dm.data['records'] if dm.get_statistical_date(r['date'], r['time']).startswith(target_ym)]
        filtered.sort(key=lambda x: x['date'] + x['time'], reverse=True)
        
        if filtered:
            # 요약 표시
            tot_inc = sum(r.get('income',0) for r in filtered)
            tot_exp = sum(r.get('cost',0) for r in filtered)
            tot_sub = sum(r.get('subsidy',0) for r in filtered)
            real_exp = tot_exp - tot_sub
            
            m1, m2, m3 = st.columns(3)
            m1.metric("총 수입", f"{tot_inc:,}원")
            m2.metric("실 지출", f"{real_exp:,}원", f"보조금 {tot_sub:,}원 차감")
            m3.metric("순수익", f"{tot_inc - real_exp:,}원")
            
            st.divider()
            
            # 테이블 데이터 생성
            table_data = []
            for r in filtered:
                desc = r['type']
                if r['type'] in ['화물운송', '대기']:
                    desc = f"{r.get('from','')} -> {r.get('to','')}"
                elif r['type'] == '주유소':
                    desc = f"{r.get('brand','')} ({r.get('liters',0)}L)"
                elif r.get('expenseItem') or r.get('supplyItem'):
                    desc = r.get('expenseItem') or r.get('supplyItem')
                    
                table_data.append({
                    "ID": r['id'],
                    "날짜": r['date'],
                    "시간": r['time'],
                    "구분": r['type'],
                    "내용": desc,
                    "거리": r.get('distance', 0),
                    "수입": f"{r.get('income',0):,}",
                    "지출": f"{r.get('cost',0):,}",
                    "보조금": f"{r.get('subsidy',0):,}" if r.get('subsidy',0)>0 else ""
                })
            
            st.dataframe(pd.DataFrame(table_data), hide_index=True, use_container_width=True)
            
            # 삭제 기능
            with st.expander("🗑️ 기록 삭제"):
                del_id = st.selectbox("삭제할 ID 선택", [d['ID'] for d in table_data])
                if st.button("선택 삭제"):
                    dm.delete_record(del_id)
                    st.success("삭제됨")
                    st.rerun()
        else:
            st.info("데이터가 없습니다.")

    # ----------------------------------------------------
    # TAB 3: 통계 (상세 분석)
    # ----------------------------------------------------
    with tab_stats:
        st.subheader("📊 데이터 분석")
        
        if filtered: # 위에서 필터링한 데이터 활용
            # 1. 월간 요약
            transport_recs = [r for r in filtered if r['type']=='화물운송']
            fuel_recs = [r for r in filtered if r['type']=='주유소']
            
            tot_dist = sum(r.get('distance',0) for r in transport_recs)
            trip_cnt = len(transport_recs)
            tot_fuel = sum(r.get('liters',0) for r in fuel_recs)
            
            # 주행거리 보정 적용
            correction = dm.data['settings'].get('mileage_correction', 0)
            final_dist = tot_dist + correction
            
            col_s1, col_s2, col_s3 = st.columns(3)
            col_s1.metric("총 운행거리", f"{final_dist:,.1f} km", f"보정 {correction}km 포함")
            col_s2.metric("운행 건수", f"{trip_cnt} 건")
            if tot_fuel > 0:
                col_s3.metric("평균 연비", f"{final_dist/tot_fuel:.2f} km/L")
            else:
                col_s3.metric("평균 연비", "0.0 km/L")
            
            # 2. 유가보조금 현황 (Progress Bar)
            st.markdown("#### ⛽ 유가보조금 / 한도 관리")
            limit = dm.data['settings'].get('subsidy_limit', 0)
            if limit > 0:
                used_pct = min(1.0, tot_fuel / limit)
                st.progress(used_pct, text=f"사용량 {tot_fuel:.1f}L / 한도 {limit}L")
                st.caption(f"잔여 한도: {limit - tot_fuel:.1f} L")
            else:
                st.warning("설정 탭에서 월 한도를 설정해주세요.")

            # 3. HTML 리포트 출력 (프린트)
            st.markdown("#### 🖨️ 운송내역서 출력")
            p_cols = st.columns(3)
            if p_cols[0].button("1~15일 내역"):
                html = generate_html_report(view_year, view_month, filtered, "first")
                b64 = base64.b64encode(html.encode()).decode()
                href = f'<a href="data:text/html;base64,{b64}" download="report_1st.html">📄 1~15일 다운로드</a>'
                st.markdown(href, unsafe_allow_html=True)
                
            if p_cols[1].button("16~말일 내역"):
                html = generate_html_report(view_year, view_month, filtered, "second")
                b64 = base64.b64encode(html.encode()).decode()
                href = f'<a href="data:text/html;base64,{b64}" download="report_2nd.html">📄 16~말일 다운로드</a>'
                st.markdown(href, unsafe_allow_html=True)

            if p_cols[2].button("전체 상세 내역"):
                html = generate_html_report(view_year, view_month, filtered, "full", detailed=True)
                b64 = base64.b64encode(html.encode()).decode()
                href = f'<a href="data:text/html;base64,{b64}" download="report_full.html">📄 월간 전체 다운로드</a>'
                st.markdown(href, unsafe_allow_html=True)
        else:
            st.write("데이터가 없습니다.")

    # ----------------------------------------------------
    # TAB 4: 설정 및 관리 (일괄적용, 센터관리, OCR, 백업)
    # ----------------------------------------------------
    with tab_settings:
        st.subheader("⚙️ 환경 설정 및 데이터 관리")
        
        st_t1, st_t2, st_t3, st_t4 = st.tabs(["기본 설정", "지역 관리", "일괄 적용/OCR", "백업/복원"])
        
        # 4-1. 기본 설정 (보조금, 거리보정)
        with st_t1:
            with st.form("settings_form"):
                new_limit = st.number_input("유가보조금 월 한도 (L)", value=dm.data['settings'].get('subsidy_limit', 0))
                new_corr = st.number_input("주행거리 보정값 (km, +/-)", value=dm.data['settings'].get('mileage_correction', 0))
                if st.form_submit_button("설정 저장"):
                    dm.data['settings']['subsidy_limit'] = new_limit
                    dm.data['settings']['mileage_correction'] = new_corr
                    dm.save_data()
                    st.success("저장되었습니다.")
        
        # 4-2. 지역 관리
        with st_t2:
            st.write("등록된 상/하차지 정보를 수정합니다.")
            sel_center = st.selectbox("지역 선택", dm.data['centers'])
            if sel_center:
                curr_info = dm.data['locations'].get(sel_center, {"address":"", "memo":""})
                new_addr = st.text_input("주소", value=curr_info.get("address",""))
                new_memo = st.text_input("메모", value=curr_info.get("memo",""))
                if st.button("정보 업데이트"):
                    dm.update_location(sel_center, new_addr, new_memo)
                    st.success(f"{sel_center} 정보 업데이트 완료")
        
        # 4-3. 일괄 적용 & OCR
        with st_t3:
            st.markdown("##### 💰 운임 일괄 적용")
            with st.expander("미정산(0원) 기록 일괄 업데이트"):
                batch_f = st.selectbox("상차지", dm.data['centers'], key="b_f")
                batch_t = st.selectbox("하차지", dm.data['centers'], key="b_t")
                batch_inc = st.number_input("적용할 금액 (만원)", step=0.5)
                if st.button("일괄 적용 실행"):
                    count = 0
                    target_inc = int(batch_inc * 10000)
                    for r in dm.data['records']:
                        if r['type'] == '화물운송' and r.get('from') == batch_f and r.get('to') == batch_t:
                            if r.get('income', 0) == 0:
                                r['income'] = target_inc
                                count += 1
                    dm.save_data()
                    st.success(f"총 {count}건 업데이트 완료!")

            st.divider()
            st.markdown("##### 📷 영수증 OCR (베타)")
            if pytesseract:
                ocr_file = st.file_uploader("영수증 이미지 업로드", type=['png', 'jpg', 'jpeg'])
                if ocr_file:
                    image = Image.open(ocr_file)
                    st.image(image, caption='업로드된 이미지', width=300)
                    if st.button("텍스트 인식 시작"):
                        try:
                            # Tesseract 경로 설정 필요시: pytesseract.pytesseract.tesseract_cmd = r'/usr/bin/tesseract'
                            text = pytesseract.image_to_string(image, lang='kor+eng')
                            st.text_area("인식 결과 (복사해서 사용하세요)", text, height=150)
                            st.info("인식된 내용을 바탕으로 입력 탭에서 기록해주세요.")
                        except Exception as e:
                            st.error(f"OCR 엔진 오류: {e} (서버에 tesseract가 설치되어 있어야 합니다)")
            else:
                st.warning("OCR 라이브러리(Tesseract)가 설치되지 않아 이 기능을 사용할 수 없습니다.")

        # 4-4. 백업/복원
        with st_t4:
            json_str = json.dumps(dm.data, ensure_ascii=False, indent=2)
            st.download_button("전체 데이터 백업 (JSON)", json_str, file_name="cargo_full_backup.json", mime="application/json")
            
            up_file = st.file_uploader("백업 파일 복원", type="json")
            if up_file and st.button("복원하기 (덮어쓰기)"):
                try:
                    up_file.seek(0)
                    content = json.loads(up_file.read().decode("utf-8"))
                    dm.data = content
                    dm.save_data()
                    st.success("복원 완료! 새로고침하세요.")
                except Exception as e:
                    st.error(f"복원 실패: {e}")

if __name__ == "__main__":
    main()