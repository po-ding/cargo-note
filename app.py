import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import json
import os
from datetime import datetime, timedelta

# ==========================================
# 유틸리티 및 데이터 관리 클래스
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
                    # 기존 키 유지하며 병합
                    self.data.update(loaded)
                    # records가 없으면 빈 리스트 초기화
                    if "records" not in self.data:
                        self.data["records"] = []
            except Exception as e:
                print(f"데이터 로드 실패: {e}")

    def save_data(self):
        try:
            with open(self.filename, 'w', encoding='utf-8') as f:
                json.dump(self.data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            messagebox.showerror("오류", f"저장 실패: {e}")

    def add_record(self, record):
        self.data["records"].append(record)
        
        # 자동 데이터 학습 (지역, 지출항목 등)
        if record['type'] in ['화물운송', '대기']:
            if record.get('from') and record.get('from') not in self.data['centers']:
                self.data['centers'].append(record.get('from'))
            if record.get('to') and record.get('to') not in self.data['centers']:
                self.data['centers'].append(record.get('to'))
        
        if record.get('expenseItem') and record.get('expenseItem') not in self.data['expense_items']:
            self.data['expense_items'].append(record.get('expenseItem'))
            
        self.data['centers'].sort()
        self.save_data()

    def get_statistical_date(self, date_str, time_str):
        """04시 기준으로 날짜를 계산 (JS 로직과 동일)"""
        dt = datetime.strptime(f"{date_str} {time_str}", "%Y-%m-%d %H:%M")
        if dt.hour < 4:
            dt = dt - timedelta(days=1)
        return dt.strftime("%Y-%m-%d")

# ==========================================
# 메인 GUI 애플리케이션
# ==========================================

class CargoApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("화물 운송 기록부 (Cargo Note)")
        self.geometry("600x800")
        self.data_manager = DataManager()
        
        # 스타일 설정
        style = ttk.Style()
        style.theme_use('clam')
        
        # 메인 탭 구성
        self.notebook = ttk.Notebook(self)
        self.notebook.pack(fill='both', expand=True, padx=10, pady=10)

        self.tab_input = ttk.Frame(self.notebook)
        self.tab_view = ttk.Frame(self.notebook)
        self.tab_stats = ttk.Frame(self.notebook)
        self.tab_settings = ttk.Frame(self.notebook)

        self.notebook.add(self.tab_input, text='📝 기록 입력')
        self.notebook.add(self.tab_view, text='📋 기록 조회')
        self.notebook.add(self.tab_stats, text='📊 통계')
        self.notebook.add(self.tab_settings, text='⚙️ 설정')

        self.setup_input_tab()
        self.setup_view_tab()
        self.setup_stats_tab()
        self.setup_settings_tab()
        
        # 초기화
        self.reset_form()
        self.refresh_ui_data()

    # ----------------------------------------------------
    # 1. 입력 탭 (Input Tab)
    # ----------------------------------------------------
    def setup_input_tab(self):
        container = ttk.Frame(self.tab_input)
        container.pack(fill='both', expand=True, padx=10, pady=10)
        
        # --- 날짜/시간 ---
        lf_datetime = ttk.LabelFrame(container, text="기록 일시")
        lf_datetime.pack(fill='x', pady=5)
        
        frame_dt = ttk.Frame(lf_datetime)
        frame_dt.pack(fill='x', padx=5, pady=5)
        
        self.entry_date = ttk.Entry(frame_dt)
        self.entry_date.pack(side='left', fill='x', expand=True, padx=2)
        self.entry_time = ttk.Entry(frame_dt)
        self.entry_time.pack(side='left', fill='x', expand=True, padx=2)
        
        # --- 기록 종류 ---
        lf_type = ttk.LabelFrame(container, text="기록 종류")
        lf_type.pack(fill='x', pady=5)
        
        self.combo_type = ttk.Combobox(lf_type, values=["화물운송", "수입", "주유소", "소모품", "지출", "대기", "공차이동"], state="readonly")
        self.combo_type.pack(fill='x', padx=5, pady=5)
        self.combo_type.bind("<<ComboboxSelected>>", self.toggle_input_fields)
        
        # --- 동적 필드 컨테이너 ---
        self.dynamic_frame = ttk.Frame(container)
        self.dynamic_frame.pack(fill='x', pady=5)
        
        # (A) 상하차 정보 (화물운송)
        self.frame_transport = ttk.LabelFrame(self.dynamic_frame, text="상/하차 정보")
        
        f_loc = ttk.Frame(self.frame_transport)
        f_loc.pack(fill='x', padx=5, pady=5)
        self.combo_from = ttk.Combobox(f_loc, values=self.data_manager.data['centers'])
        self.combo_from.pack(side='left', fill='x', expand=True, padx=2)
        self.combo_from.set("상차지")
        
        self.combo_to = ttk.Combobox(f_loc, values=self.data_manager.data['centers'])
        self.combo_to.pack(side='left', fill='x', expand=True, padx=2)
        self.combo_to.set("하차지")
        
        self.entry_distance = ttk.Entry(self.frame_transport)
        self.entry_distance.pack(fill='x', padx=5, pady=5)
        self.entry_distance.insert(0, "0")
        
        # (B) 주유 정보
        self.frame_fuel = ttk.LabelFrame(self.dynamic_frame, text="주유 정보")
        f_fuel = ttk.Frame(self.frame_fuel)
        f_fuel.pack(fill='x', padx=5, pady=5)
        self.entry_fuel_price = ttk.Entry(f_fuel)
        self.entry_fuel_price.pack(side='left', fill='x', expand=True, padx=2)
        self.entry_fuel_liters = ttk.Entry(f_fuel)
        self.entry_fuel_liters.pack(side='left', fill='x', expand=True, padx=2)
        
        self.combo_brand = ttk.Combobox(self.frame_fuel, values=["S-OIL", "SK에너지", "GS칼텍스", "현대오일뱅크", "기타"])
        self.combo_brand.pack(fill='x', padx=5, pady=5)
        
        # (C) 내역 입력 (지출/수입/소모품)
        self.frame_expense = ttk.LabelFrame(self.dynamic_frame, text="내역 입력")
        self.entry_item = ttk.Entry(self.frame_expense)
        self.entry_item.pack(fill='x', padx=5, pady=5)
        
        # (D) 금액 정보
        self.frame_cost = ttk.LabelFrame(container, text="금액 정보 (단위: 만원)")
        self.frame_cost.pack(fill='x', pady=5)
        
        self.lbl_income = ttk.Label(self.frame_cost, text="수입 금액:")
        self.lbl_income.pack(anchor='w', padx=5)
        self.entry_income = ttk.Entry(self.frame_cost)
        self.entry_income.pack(fill='x', padx=5, pady=2)
        
        self.lbl_cost = ttk.Label(self.frame_cost, text="지출 금액:")
        self.lbl_cost.pack(anchor='w', padx=5)
        self.entry_cost = ttk.Entry(self.frame_cost)
        self.entry_cost.pack(fill='x', padx=5, pady=2)

        # --- 버튼 ---
        btn_frame = ttk.Frame(container)
        btn_frame.pack(fill='x', pady=10)
        
        ttk.Button(btn_frame, text="운행 시작 / 저장", command=self.save_record).pack(side='left', fill='x', expand=True, padx=2)
        ttk.Button(btn_frame, text="운행 종료", command=self.end_trip).pack(side='left', fill='x', expand=True, padx=2)

    def toggle_input_fields(self, event=None):
        rtype = self.combo_type.get()
        
        # 모든 프레임 숨기기
        self.frame_transport.pack_forget()
        self.frame_fuel.pack_forget()
        self.frame_expense.pack_forget()
        
        # 금액 필드 초기화
        self.lbl_income.pack(anchor='w', padx=5)
        self.entry_income.pack(fill='x', padx=5, pady=2)
        self.lbl_cost.pack(anchor='w', padx=5)
        self.entry_cost.pack(fill='x', padx=5, pady=2)

        if rtype == "화물운송":
            self.frame_transport.pack(fill='x', pady=5)
            self.entry_cost.pack_forget() # 지출 숨김
            self.lbl_cost.pack_forget()
        elif rtype == "수입":
            self.frame_expense.config(text="수입 내역")
            self.frame_expense.pack(fill='x', pady=5)
            self.entry_cost.pack_forget()
            self.lbl_cost.pack_forget()
        elif rtype == "지출":
            self.frame_expense.config(text="지출 내역")
            self.frame_expense.pack(fill='x', pady=5)
            self.entry_income.pack_forget()
            self.lbl_income.pack_forget()
        elif rtype == "주유소":
            self.frame_fuel.pack(fill='x', pady=5)
            self.entry_income.pack_forget()
            self.lbl_income.pack_forget()
        elif rtype == "소모품":
            self.frame_expense.config(text="소모품 내역")
            self.frame_expense.pack(fill='x', pady=5)
            self.entry_income.pack_forget()
            self.lbl_income.pack_forget()
        else:
            # 대기 등
            self.frame_transport.pack(fill='x', pady=5)

    def reset_form(self):
        now = datetime.now()
        self.entry_date.delete(0, tk.END)
        self.entry_date.insert(0, now.strftime("%Y-%m-%d"))
        
        self.entry_time.delete(0, tk.END)
        self.entry_time.insert(0, now.strftime("%H:%M"))
        
        self.combo_type.current(0)
        self.entry_distance.delete(0, tk.END); self.entry_distance.insert(0, "0")
        self.entry_income.delete(0, tk.END)
        self.entry_cost.delete(0, tk.END)
        self.entry_fuel_price.delete(0, tk.END)
        self.entry_fuel_liters.delete(0, tk.END)
        self.entry_item.delete(0, tk.END)
        
        self.toggle_input_fields()

    def save_record(self):
        try:
            # 데이터 수집
            rtype = self.combo_type.get()
            
            # 숫자 변환 헬퍼
            def get_float(entry):
                val = entry.get().strip()
                return float(val) if val else 0.0

            # 금액 단위는 '만원' -> 저장시 '원' 단위 변환 (JS 코드 로직 준수)
            income_won = int(get_float(self.entry_income) * 10000)
            cost_won = int(get_float(self.entry_cost) * 10000)
            
            # 주유비 자동 계산
            if rtype == "주유소":
                u_price = get_float(self.entry_fuel_price)
                liters = get_float(self.entry_fuel_liters)
                if cost_won == 0 and u_price > 0 and liters > 0:
                    cost_won = int(u_price * liters)

            record = {
                "id": int(datetime.now().timestamp() * 1000),
                "date": self.entry_date.get(),
                "time": self.entry_time.get(),
                "type": rtype,
                "from": self.combo_from.get() if rtype in ["화물운송", "대기", "공차이동"] else "",
                "to": self.combo_to.get() if rtype in ["화물운송", "대기", "공차이동"] else "",
                "distance": get_float(self.entry_distance),
                "income": income_won,
                "cost": cost_won,
                "expenseItem": self.entry_item.get(),
                "supplyItem": self.entry_item.get() if rtype == "소모품" else "",
                "unitPrice": get_float(self.entry_fuel_price),
                "liters": get_float(self.entry_fuel_liters),
                "brand": self.combo_brand.get()
            }
            
            self.data_manager.add_record(record)
            messagebox.showinfo("성공", "기록이 저장되었습니다.")
            self.reset_form()
            self.refresh_ui_data()
            
        except Exception as e:
            messagebox.showerror("오류", f"저장 중 오류 발생: {e}")

    def end_trip(self):
        now = datetime.now()
        record = {
            "id": int(now.timestamp() * 1000),
            "date": now.strftime("%Y-%m-%d"),
            "time": now.strftime("%H:%M"),
            "type": "운행종료",
            "income": 0, "cost": 0, "distance": 0
        }
        self.data_manager.add_record(record)
        messagebox.showinfo("알림", "운행이 종료되었습니다.")
        self.refresh_ui_data()

    # ----------------------------------------------------
    # 2. 조회 탭 (View Tab)
    # ----------------------------------------------------
    def setup_view_tab(self):
        # 상단 필터
        f_filter = ttk.Frame(self.tab_view)
        f_filter.pack(fill='x', padx=5, pady=5)
        
        ttk.Label(f_filter, text="조회 연월:").pack(side='left')
        self.view_year = ttk.Combobox(f_filter, width=6, values=[str(y) for y in range(2023, 2030)])
        self.view_year.set(datetime.now().year)
        self.view_year.pack(side='left', padx=2)
        
        self.view_month = ttk.Combobox(f_filter, width=4, values=[f"{m:02d}" for m in range(1, 13)])
        self.view_month.set(f"{datetime.now().month:02d}")
        self.view_month.pack(side='left', padx=2)
        
        ttk.Button(f_filter, text="조회", command=self.load_table_data).pack(side='left', padx=5)
        ttk.Button(f_filter, text="삭제", command=self.delete_selected_record).pack(side='right', padx=5)

        # 트리뷰 (테이블)
        columns = ('date', 'time', 'type', 'detail', 'distance', 'income', 'cost')
        self.tree = ttk.Treeview(self.tab_view, columns=columns, show='headings')
        
        self.tree.heading('date', text='날짜')
        self.tree.heading('time', text='시간')
        self.tree.heading('type', text='구분')
        self.tree.heading('detail', text='내용 (상/하차/적요)')
        self.tree.heading('distance', text='거리')
        self.tree.heading('income', text='수입')
        self.tree.heading('cost', text='지출')
        
        self.tree.column('date', width=80)
        self.tree.column('time', width=60)
        self.tree.column('type', width=70)
        self.tree.column('detail', width=150)
        self.tree.column('distance', width=50)
        self.tree.column('income', width=80)
        self.tree.column('cost', width=80)
        
        self.tree.pack(fill='both', expand=True, padx=5, pady=5)
        
        # 스크롤바
        scrollbar = ttk.Scrollbar(self.tab_view, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscroll=scrollbar.set)
        scrollbar.pack(side='right', fill='y')

    def load_table_data(self):
        # 트리뷰 초기화
        for item in self.tree.get_children():
            self.tree.delete(item)
            
        year = self.view_year.get()
        month = self.view_month.get()
        target_prefix = f"{year}-{month}"
        
        records = self.data_manager.data.get("records", [])
        # 통계 날짜 기준으로 필터링
        filtered = [r for r in records if self.data_manager.get_statistical_date(r['date'], r['time']).startswith(target_prefix)]
        
        # 정렬
        filtered.sort(key=lambda x: x['date'] + x['time'])
        
        for r in filtered:
            # 상세 내용 조합
            detail = ""
            if r['type'] in ['화물운송', '대기']:
                detail = f"{r.get('from','')} → {r.get('to','')}"
            elif r['type'] == '주유소':
                detail = f"{r.get('brand','')} ({r.get('liters',0)}L)"
            else:
                detail = r.get('expenseItem') or r.get('supplyItem') or ""
            
            # 금액 포맷팅 (원 단위 -> 콤마)
            inc_str = f"{r.get('income',0):,}" if r.get('income',0) > 0 else ""
            cost_str = f"{r.get('cost',0):,}" if r.get('cost',0) > 0 else ""
            
            self.tree.insert('', 'end', values=(
                r['date'], r['time'], r['type'], detail,
                r.get('distance',0), inc_str, cost_str
            ), tags=(str(r['id']),))

    def delete_selected_record(self):
        selected = self.tree.selection()
        if not selected:
            messagebox.showwarning("경고", "삭제할 항목을 선택하세요.")
            return
        
        if messagebox.askyesno("확인", "정말 삭제하시겠습니까?"):
            item = self.tree.item(selected[0])
            rec_id = int(item['tags'][0])
            
            self.data_manager.data["records"] = [r for r in self.data_manager.data["records"] if r['id'] != rec_id]
            self.data_manager.save_data()
            self.load_table_data()
            self.update_stats()

    # ----------------------------------------------------
    # 3. 통계 탭 (Stats Tab)
    # ----------------------------------------------------
    def setup_stats_tab(self):
        self.lbl_stats_title = ttk.Label(self.tab_stats, text="이번 달 통계", font=("Arial", 14, "bold"))
        self.lbl_stats_title.pack(pady=10)
        
        self.frame_summary = ttk.Frame(self.tab_stats)
        self.frame_summary.pack(pady=10)
        
        self.stats_labels = {}
        keys = ["총 수입", "총 지출", "순수익", "운행 건수", "총 거리", "총 주유량"]
        for i, key in enumerate(keys):
            lbl_k = ttk.Label(self.frame_summary, text=key, font=("Arial", 10))
            lbl_k.grid(row=i//2, column=(i%2)*2, padx=20, pady=5, sticky='e')
            
            lbl_v = ttk.Label(self.frame_summary, text="0", font=("Arial", 12, "bold"))
            lbl_v.grid(row=i//2, column=(i%2)*2+1, padx=20, pady=5, sticky='w')
            self.stats_labels[key] = lbl_v
            
        ttk.Button(self.tab_stats, text="새로고침", command=self.update_stats).pack(pady=20)

    def update_stats(self):
        # 현재 선택된 조회 탭의 연/월 기준
        year = self.view_year.get()
        month = self.view_month.get()
        target_prefix = f"{year}-{month}"
        
        records = self.data_manager.data.get("records", [])
        target_records = [r for r in records if self.data_manager.get_statistical_date(r['date'], r['time']).startswith(target_prefix)]
        
        total_income = sum(r.get('income', 0) for r in target_records)
        total_cost = sum(r.get('cost', 0) for r in target_records)
        total_dist = sum(r.get('distance', 0) for r in target_records if r['type'] == '화물운송')
        trip_count = len([r for r in target_records if r['type'] == '화물운송'])
        total_fuel = sum(r.get('liters', 0) for r in target_records if r['type'] == '주유소')
        
        self.lbl_stats_title.config(text=f"{year}년 {month}월 요약")
        self.stats_labels["총 수입"].config(text=f"{total_income:,} 원", foreground="blue")
        self.stats_labels["총 지출"].config(text=f"{total_cost:,} 원", foreground="red")
        self.stats_labels["순수익"].config(text=f"{total_income - total_cost:,} 원")
        self.stats_labels["운행 건수"].config(text=f"{trip_count} 건")
        self.stats_labels["총 거리"].config(text=f"{total_dist:.1f} km")
        self.stats_labels["총 주유량"].config(text=f"{total_fuel:.1f} L")

    # ----------------------------------------------------
    # 4. 설정 탭 (Settings Tab)
    # ----------------------------------------------------
    def setup_settings_tab(self):
        container = ttk.Frame(self.tab_settings)
        container.pack(fill='both', padx=20, pady=20)
        
        ttk.Label(container, text="데이터 관리", font=("Arial", 12, "bold")).pack(anchor='w', pady=10)
        
        btn_export = ttk.Button(container, text="JSON 백업 저장", command=self.export_json)
        btn_export.pack(fill='x', pady=5)
        
        btn_import = ttk.Button(container, text="JSON 복원 (덮어쓰기)", command=self.import_json)
        btn_import.pack(fill='x', pady=5)
        
        ttk.Label(container, text="* 원본 index.html에서 저장한 JSON 파일과 호환됩니다.", foreground="gray").pack(pady=10)

    def export_json(self):
        f = filedialog.asksaveasfilename(defaultextension=".json", filetypes=[("JSON Files", "*.json")])
        if f:
            with open(f, 'w', encoding='utf-8') as outfile:
                json.dump(self.data_manager.data, outfile, ensure_ascii=False, indent=2)
            messagebox.showinfo("성공", "백업이 완료되었습니다.")

    def import_json(self):
        f = filedialog.askopenfilename(filetypes=[("JSON Files", "*.json")])
        if f:
            if messagebox.askyesno("경고", "기존 데이터가 모두 덮어씌워집니다. 진행하시겠습니까?"):
                with open(f, 'r', encoding='utf-8') as infile:
                    self.data_manager.data = json.load(infile)
                self.data_manager.save_data()
                self.refresh_ui_data()
                messagebox.showinfo("성공", "데이터가 복원되었습니다.")

    def refresh_ui_data(self):
        """데이터 변경 시 UI 갱신"""
        # 콤보박스 값 갱신
        self.combo_from['values'] = self.data_manager.data['centers']
        self.combo_to['values'] = self.data_manager.data['centers']
        self.load_table_data()
        self.update_stats()

if __name__ == "__main__":
    app = CargoApp()
    app.mainloop()