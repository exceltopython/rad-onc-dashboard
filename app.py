import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime
import os
import re

# --- TRY IMPORTING FPDF ---
try:
    from fpdf import FPDF
except ImportError:
    FPDF = None

# --- 1. CONFIGURATION & STYLING ---
st.set_page_config(page_title="RadOnc Analytics", layout="wide", page_icon="🩺")

def inject_custom_css():
    st.markdown("""
        <style>
        /* HIDE STREAMLIT MENU, FOOTER, TOOLBAR */
        #MainMenu {visibility: hidden;}
        footer {visibility: hidden;}
        header {visibility: hidden;}
        [data-testid="stToolbar"] {visibility: hidden;}
        [data-testid="stHeader"] {visibility: hidden;}
        .stDeployButton {display: none;}

        .stTabs [data-baseweb="tab-list"] { gap: 24px; background-color: transparent; padding-bottom: 15px; border-bottom: 1px solid #ddd; }
        .stTabs [data-baseweb="tab-list"] button { background-color: #FFFFFF; border: 1px solid #D1D5DB; border-radius: 6px; color: #4B5563; padding: 14px 30px; box-shadow: 0 1px 2px rgba(0,0,0,0.05); }
        .stTabs [data-baseweb="tab-list"] button [data-testid="stMarkdownContainer"] p { font-size: 20px !important; font-weight: 700 !important; margin: 0px; }
        .stTabs [data-baseweb="tab-list"] button[aria-selected="true"] { background-color: #1E3A8A !important; color: #FFFFFF !important; border-color: #1E3A8A; }
        .stTabs [data-baseweb="tab-highlight"] { background-color: transparent !important; }
        
        /* FORCE TABLE HEADERS TO BE BLACK AND BOLD */
        div[data-testid="stDataFrame"] div[role="columnheader"] { color: #000000 !important; font-weight: 900 !important; font-size: 14px !important; }
        [data-testid="stDataFrame"] th { color: #000000 !important; font-weight: 900 !important; }
        </style>
    """, unsafe_allow_html=True)

inject_custom_css()

# --- PDF GENERATOR CLASS ---
if FPDF:
    class PDFReport(FPDF):
        def header(self):
            self.set_font('Arial', 'B', 15)
            self.cell(0, 10, 'Radiation Oncology - Monthly Performance Report', 0, 1, 'C')
            self.ln(5)

        def footer(self):
            self.set_y(-15)
            self.set_font('Arial', 'I', 8)
            self.cell(0, 10, f'Page {self.page_no()}', 0, 0, 'C')

    def create_clinic_pdf(clinic_name, month_label, total_rvu, rvu_fte, new_patients, provider_df):
        pdf = PDFReport()
        pdf.add_page()
        
        # Title Section
        pdf.set_font('Arial', 'B', 14)
        pdf.cell(0, 10, f"Scope: {clinic_name}", 0, 1, 'L')
        pdf.set_font('Arial', '', 12)
        pdf.cell(0, 10, f"Period: {month_label}", 0, 1, 'L')
        pdf.ln(5)
        
        # Executive Summary
        pdf.set_fill_color(240, 240, 240)
        pdf.set_font('Arial', 'B', 12)
        pdf.cell(0, 10, "Executive Summary", 1, 1, 'L', fill=True)
        
        pdf.set_font('Arial', '', 11)
        pdf.cell(60, 10, "Total wRVUs:", 0, 0)
        pdf.set_font('Arial', 'B', 11)
        pdf.cell(0, 10, f"{total_rvu:,.2f}", 0, 1)
        
        pdf.set_font('Arial', '', 11)
        pdf.cell(60, 10, "wRVU per FTE:", 0, 0)
        pdf.set_font('Arial', 'B', 11)
        pdf.cell(0, 10, f"{rvu_fte:,.2f}", 0, 1)

        pdf.set_font('Arial', '', 11)
        pdf.cell(60, 10, "New Patients (Approx):", 0, 0)
        pdf.set_font('Arial', 'B', 11)
        pdf.cell(0, 10, f"{new_patients:,.0f}", 0, 1)
        pdf.ln(10)
        
        # Provider Breakdown
        pdf.set_font('Arial', 'B', 12)
        pdf.cell(0, 10, "Provider Breakdown", 1, 1, 'L', fill=True)
        
        # Table Header
        pdf.set_font('Arial', 'B', 10)
        pdf.cell(90, 10, "Provider Name", 1, 0, 'C')
        pdf.cell(50, 10, "Total wRVUs", 1, 1, 'C') # End line here
        
        # Table Body
        pdf.set_font('Arial', '', 10)
        if not provider_df.empty:
            for _, row in provider_df.iterrows():
                pdf.cell(90, 10, str(row['Name']), 1, 0)
                pdf.cell(50, 10, f"{row['Total RVUs']:,.2f}", 1, 1, 'R')
        else:
            pdf.cell(0, 10, "No individual provider data found for this period.", 1, 1)
            
        return pdf.output(dest='S').encode('latin-1')

# --- PASSWORD CONFIGURATION ---
APP_PASSWORD = "RadOnc2026rj"

def check_password():
    def password_entered():
        if st.session_state["password"] == APP_PASSWORD:
            st.session_state["password_correct"] = True
            del st.session_state["password"]
        else:
            st.session_state["password_correct"] = False

    if "password_correct" not in st.session_state:
        st.text_input("🔒 Enter Dashboard Password:", type="password", on_change=password_entered, key="password")
        return False
    elif not st.session_state["password_correct"]:
        st.text_input("❌ App down for improvements. Come back soon", type="password", on_change=password_entered, key="password")
        return False
    else:
        return True

# ==========================================
# --- 2. HISTORICAL DATA ENTRY (2019-2024) ---
# ==========================================
HISTORICAL_DATA = {
    2019: {"CENT": 18430, "Dickson": 11420, "Skyline": 13910, "Summit": 14690, "Stonecrest": 8600, "STW": 22030, "Midtown": 14730, "MURF": 38810, "Sumner": 14910, "TOPC": 15690, "LROC": 0, "TROC": 0},
    2020: {"CENT": 19160, "Dickson": 12940, "Skyline": 13180, "Summit": 11540, "Stonecrest": 7470, "STW": 17070, "Midtown": 14560, "MURF": 37890, "Sumner": 14760, "TOPC": 22010, "LROC": 0, "TROC": 0},
    2021: {"CENT": 14480, "Dickson": 10980, "Skyline": 11450, "Summit": 11700, "Stonecrest": 8610, "STW": 17970, "Midtown": 17890, "MURF": 37440, "Sumner": 17670, "TOPC": 28540, "LROC": 0, "TROC": 0},
    2022: {"CENT": 15860, "Dickson": 13960, "Skyline": 14520, "Summit": 12390, "Stonecrest": 10580, "STW": 27650, "Midtown": 19020, "MURF": 37870, "Sumner": 20570, "TOPC": 28830, "LROC": 0, "TROC": 0},
    2023: {"CENT": 19718, "Dickson": 11600, "Skyline": 17804, "Summit": 14151, "Stonecrest": 11647, "STW": 23717, "Midtown": 21017, "MURF": 42201, "Sumner": 22622, "TOPC": 27667, "LROC": 0, "TROC": 0},
    2024: {"CENT": 22385, "Dickson": 12155, "Skyline": 15363, "Summit": 12892, "Stonecrest": 12524, "STW": 25409, "Midtown": 21033, "MURF": 45648, "Sumner": 23803, "TOPC": 33892, "LROC": 0, "TROC": 0}
}

if check_password():
    # --- CONFIGURATION ---
    CLINIC_CONFIG = {
        "CENT": {"name": "Centennial", "fte": 2.0}, "Dickson": {"name": "Horizon", "fte": 1.0}, "LROC": {"name": "LROC (Lebanon)", "fte": 1.0},
        "Skyline": {"name": "Skyline", "fte": 1.0}, "Midtown": {"name": "ST Midtown", "fte": 1.6}, "MURF": {"name": "ST Rutherford", "fte": 3.0},
        "STW": {"name": "ST West", "fte": 2.0}, "Stonecrest": {"name": "StoneCrest", "fte": 1.0}, "Summit": {"name": "Summit", "fte": 1.0},
        "Sumner": {"name": "Sumner", "fte": 1.5}, "TROC": {"name": "TROC (Tullahoma)", "fte": 0.6}, "TOPC": {"name": "TN Proton Center", "fte": 0.0}
    }
    TRISTAR_IDS = ["CENT", "Skyline", "Dickson", "Summit", "Stonecrest"]
    ASCENSION_IDS = ["STW", "Midtown", "MURF"]
    PROVIDER_CONFIG = {
        "Burke": 1.0, "Castle": 0.6, "Chen": 1.0, "Cohen": 1.0, "Collie": 1.0, "Cooper": 1.0, "Ellis": 1.0, "Escott": 1.0, "Friedman": 1.0, 
        "Gray": 1.0, "Jones": 1.0, "Lee": 1.0, "Lewis": 1.0, "Lipscomb": 0.6, "Lydon": 1.0, "Mayo": 1.0, "Mondschein": 1.0,
        "Nguyen": 1.0, "Osborne": 1.0, "Phillips": 1.0, "Sidrys": 1.0, "Sittig": 1.0, "Strickler": 1.0, "Wakefield": 1.0, "Wendt": 1.0, "Whitaker": 1.0
    }
    PROVIDER_KEYS_UPPER = {k.upper(): k for k in PROVIDER_CONFIG.keys()}
    APP_LIST = ["Burke", "Ellis", "Lewis", "Lydon"]
    TARGET_CATEGORIES = ["E&M OFFICE CODES", "RADIATION CODES", "SPECIAL PROCEDURES"]
    IGNORED_SHEETS = ["RAD PHYSICIAN WORK RVUS", "COVER", "SHEET1", "TOTALS", "PROTON PHYSICIAN WORK RVUS"]
    SERVER_DIR = "Reports"
    
    # CONSULT CPT CONFIG
    CONSULT_CPT = "77263"
    CONSULT_CONVERSION = 3.14

    # NEW: APP FOLLOW-UP CPT CONFIG
    APP_CPT_RATES = {
        "99212": 0.7,
        "99213": 1.3,
        "99214": 1.92,
        "99215": 2.8
    }

    # *** EXACT ROW NAME MAPPING FOR POS TREND SHEETS ***
    POS_ROW_MAPPING = {
        "CENTENNIAL RAD": "CENT", "DICKSON RAD": "Dickson", "MIDTOWN RAD": "Midtown",
        "MURFREESBORO RAD": "MURF", "SAINT THOMAS WEST RAD": "STW", "SKYLINE RAD": "Skyline",
        "STONECREST RAD": "Stonecrest", "SUMMIT RAD": "Summit", "SUMNER RAD": "Sumner",
        "LEBANON RAD": "LROC", "TULLAHOMA RADIATION": "TROC", "TO PROTON": "TOPC"
    }

    class LocalFile:
        def __init__(self, path):
            self.path = path
            self.name = os.path.basename(path).upper()
        
    def find_date_row(df):
        months = ["JAN", "FEB", "MAR", "APR", "MAY", "JUN", "JUL", "AUG", "SEP", "OCT", "NOV", "DEC"]
        best_row = 1; max_score = 0
        for r in range(min(10, len(df))):
            row_vals = df.iloc[r, 4:16]
            str_vals = [str(v).upper() for v in row_vals if pd.notna(v)]
            text_matches = sum(1 for v in str_vals if any(m in v for m in months))
            dt_matches = sum(1 for v in row_vals if isinstance(v, (datetime, pd.Timestamp)))
            total_score = text_matches + (dt_matches * 2) 
            if total_score > max_score: max_score = total_score; best_row = r
        return best_row

    def get_date_from_filename(filename):
        match = re.search(r'(JAN|FEB|MAR|APR|MAY|JUN|JUL|AUG|SEP|OCT|NOV|DEC)\s*(\d{2,4})', filename, re.IGNORECASE)
        if match:
            month_str = match.group(1); year_str = match.group(2)
            if len(year_str) == 2: year_str = "20" + year_str
            return pd.to_datetime(f"{month_str} {year_str}")
        return datetime.now()

    def get_target_year_from_text(text):
        # Identify year from folder or filename (e.g. DEC25 -> 2025)
        match = re.search(r'(JAN|FEB|MAR|APR|MAY|JUN|JUL|AUG|SEP|OCT|NOV|DEC)\s*(20)?(2[0-9])', text, re.IGNORECASE)
        if match:
            y = match.group(3)
            return int("20" + y)
        
        # Fallback check
        match2 = re.search(r'(20)?(2[0-9])', text)
        if match2:
            y = match2.group(2)
            return int("20" + y)
        return None

    def clean_number(val):
        if pd.isna(val): return None
        try:
            val_str = str(val).strip()
            if val_str.startswith("(") and val_str.endswith(")"): val_str = "-" + val_str[1:-1]
            val_str = val_str.replace(',', '').replace('%', '').replace('$', '')
            if val_str == "" or val_str == "-": return None
            return float(val_str)
        except: return None

    def match_provider(name_str):
        try:
            if not isinstance(name_str, str): return None
            name_str = name_str.strip()
            if not name_str: return None
            if "," in name_str: base = name_str.split(",")[0].strip()
            else: base = name_str
            parts = base.split()
            if not parts: return None
            last_name = parts[0].strip().upper()
            
            # --- FIX: NORMALIZE FRIEDMEN -> FRIEDMAN ---
            if last_name == "FRIEDMEN": last_name = "FRIEDMAN"
            # -------------------------------------------
            
            if last_name in PROVIDER_KEYS_UPPER: return PROVIDER_KEYS_UPPER[last_name]
            return None
        except: return None

    def clean_provider_name_display(name_str):
        match = match_provider(name_str)
        if match: return match
        if "," in name_str: return name_str.split(",")[0].strip().split()[0]
        return name_str.split()[0]

    def get_historical_df():
        records = []
        for year, data in HISTORICAL_DATA.items():
            for clinic_id, rvu in data.items():
                if clinic_id in CLINIC_CONFIG:
                    records.append({"ID": clinic_id, "Name": CLINIC_CONFIG[clinic_id]["name"], "Year": year, "Total RVUs": rvu, "Source": "Historical"})
        return pd.DataFrame(records)

    # --- ADVANCED NARRATIVE GENERATOR ---
    def generate_narrative(df, entity_type="Provider", metric_col="Total RVUs", unit="wRVUs", timeframe="this month"):
        if df.empty: return "No data available."
        
        latest_date = df['Month_Clean'].max()
        latest_df = df[df['Month_Clean'] == latest_date]
        
        if latest_df.empty: return "Data processed but current month is empty."
        
        total_vol = latest_df[metric_col].sum()
        provider_count = len(latest_df)
        avg_vol = total_vol / provider_count if provider_count > 0 else 0
        
        if metric_col == "Total RVUs":
            sorted_df = latest_df.sort_values('RVU per FTE', ascending=False)
            top_metric_name = "wRVU/FTE"
            top_col = 'RVU per FTE'
        else:
            sorted_df = latest_df.sort_values(metric_col, ascending=False)
            top_metric_name = unit
            top_col = metric_col

        narrative = f"""### 🤖 Automated Analysis ({latest_date.strftime('%B %Y')})
The **{entity_type}** group ({provider_count} active) generated a total of **{total_vol:,.0f} {unit}** {timeframe}.  
The group average was **{avg_vol:,.0f} {unit}** per {entity_type.lower()}.

#### 🏆 Top Performers:
"""
        if len(sorted_df) > 0:
            top_1 = sorted_df.iloc[0]
            narrative += f"* **🥇 1st Place:** **{clean_provider_name_display(top_1['Name'])}** with **{top_1[top_col]:,.0f} {top_metric_name}**\n"
        if len(sorted_df) > 1:
            top_2 = sorted_df.iloc[1]
            narrative += f"* **🥈 2nd Place:** **{clean_provider_name_display(top_2['Name'])}** with **{top_2[top_col]:,.0f}**\n"
        if len(sorted_df) > 2:
            top_3 = sorted_df.iloc[2]
            narrative += f"* **🥉 3rd Place:** **{clean_provider_name_display(top_3['Name'])}** with **{top_3[top_col]:,.0f}**\n"

        return narrative

    # --- PARSERS (WITH TARGET YEAR INTEGRATION) ---

    def parse_detailed_prov_sheet(df, filename_date, clinic_id, log, target_year=None):
        records = []
        current_provider = None
        current_values = {"E&M OFFICE CODES": 0.0, "RADIATION CODES": 0.0, "SPECIAL PROCEDURES": 0.0}
        term_counts = {k: 0 for k in current_values}
        target_terms = list(current_values.keys())
        
        date_map = {} 
        header_row_found = False
        for r in range(min(15, len(df))):
            row = df.iloc[r].values
            for c in range(len(row)):
                val = str(row[c]).strip()
                if re.match(r'(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)-\d{2}', val, re.IGNORECASE):
                    try:
                        dt = pd.to_datetime(val, format='%b-%y')
                        if target_year and dt.year != target_year: continue
                        date_map[c] = dt
                        header_row_found = True
                    except: pass
            if header_row_found: break
            
        for i in range(len(df)):
            row = df.iloc[i].values
            potential_name = None
            for c in range(min(5, len(row))):
                val = str(row[c]).strip()
                match = match_provider(val)
                if match: potential_name = match; break
            
            if potential_name:
                current_provider = potential_name
                term_counts = {k: 0 for k in target_terms}
                continue
            
            if current_provider:
                row_label = str(row[0]).upper()
                for term in target_terms:
                    if term in row_label:
                        term_counts[term] += 1
                        if term_counts[term] == 2:
                            if date_map:
                                for col_idx, dt in date_map.items():
                                    if col_idx < len(row):
                                        val = clean_number(row[col_idx])
                                        if val and val != 0:
                                            records.append({
                                                "Type": "provider", "ID": clinic_id, "Name": current_provider, "FTE": 1.0,
                                                "Month": dt, "Total RVUs": val, "RVU per FTE": val,
                                                "Clinic_Tag": clinic_id, "Quarter": f"Q{dt.quarter} {dt.year}",
                                                "Month_Label": dt.strftime('%b-%y'), "source_type": "detail",
                                                "Month_Clean": dt
                                            })
        return pd.DataFrame(records)

    def parse_app_cpt_data(df, provider_name, log, target_year=None):
        records = []
        try:
            header_row_idx = find_date_row(df)
            for cpt_code, rate in APP_CPT_RATES.items():
                cpt_row_idx = -1
                for r in range(len(df)):
                    row_val = str(df.iloc[r, 0]).strip()
                    if row_val.startswith(cpt_code):
                        cpt_row_idx = r
                        break
                
                if cpt_row_idx != -1:
                    for col in df.columns[4:]: 
                        header_val = df.iloc[header_row_idx, col]
                        valid_date = None
                        if isinstance(header_val, (datetime, pd.Timestamp)):
                             valid_date = header_val
                        elif isinstance(header_val, str):
                             if re.match(r'(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)-\d{2}', header_val.strip(), re.IGNORECASE):
                                 try: valid_date = pd.to_datetime(header_val.strip(), format='%b-%y')
                                 except: pass
                        
                        if valid_date is None: continue 
                        if target_year and valid_date.year != target_year: continue
                        
                        val = clean_number(df.iloc[cpt_row_idx, col])
                        if val is not None and val != 0:
                            count = val / rate
                            records.append({
                                "Name": provider_name, 
                                "Month": valid_date, 
                                "Count": count, 
                                "CPT Code": cpt_code,
                                "Rate": rate
                            })
        except Exception as e: pass
        return pd.DataFrame(records)

    def parse_rvu_sheet(df, sheet_name, entity_type, clinic_tag="General", forced_fte=None, target_year=None):
        if entity_type == 'clinic':
            config = CLINIC_CONFIG.get(sheet_name, {"name": sheet_name, "fte": 1.0})
            name = config['name']; fte = config['fte']
        else:
            name = sheet_name; fte = forced_fte if forced_fte else PROVIDER_CONFIG.get(sheet_name, 1.0)
        
        df.iloc[:, 0] = df.iloc[:, 0].astype(str).str.strip().str.upper()
        mask = df.iloc[:, 0].isin(TARGET_CATEGORIES); filtered_df = df[mask]; data_rows = filtered_df.copy()
        records = []; header_row_idx = find_date_row(df)
        
        if len(df.columns) > 4:
            for col in df.columns[4:]:
                header_val = df.iloc[header_row_idx, col]
                if pd.isna(header_val): continue
                
                col_dt = None
                if isinstance(header_val, (datetime, pd.Timestamp)): col_dt = header_val
                elif isinstance(header_val, str) and re.match(r'(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)-\d{2}', header_val.strip(), re.IGNORECASE):
                     try: col_dt = pd.to_datetime(header_val.strip(), format='%b-%y')
                     except: pass
                
                if col_dt and target_year and col_dt.year != target_year: continue

                col_sum = pd.to_numeric(data_rows[col], errors='coerce').sum()
                records.append({
                    "Type": entity_type, "ID": sheet_name, "Name": name, "FTE": fte,
                    "Month": col_dt if col_dt else header_val, 
                    "Total RVUs": col_sum, "RVU per FTE": col_sum / fte if fte > 0 else 0,
                    "Clinic_Tag": clinic_tag, "source_type": "standard", "Month_Clean": col_dt
                })
        return pd.DataFrame(records)

    def parse_consults_data(df, sheet_name, log, target_year=None):
        records = []
        try:
            header_row_idx = find_date_row(df)
            cpt_row_idx = -1
            for r in range(len(df)):
                row_val = str(df.iloc[r, 0]).strip()
                if CONSULT_CPT in row_val:
                    cpt_row_idx = r
                    break
            
            if cpt_row_idx != -1:
                for col in df.columns[4:]: 
                    header_val = df.iloc[header_row_idx, col]
                    
                    is_valid_date = False
                    valid_date = None
                    if isinstance(header_val, (datetime, pd.Timestamp)): 
                        is_valid_date = True; valid_date = header_val
                    elif isinstance(header_val, str):
                        if re.match(r'(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)-\d{2}', header_val.strip(), re.IGNORECASE):
                            is_valid_date = True
                            try: valid_date = pd.to_datetime(header_val.strip(), format='%b-%y')
                            except: pass
                    
                    if not is_valid_date: continue 
                    if target_year and valid_date and valid_date.year != target_year: continue
                    
                    val = clean_number(df.iloc[cpt_row_idx, col])
                    if val is not None:
                        count = val / CONSULT_CONVERSION
                        records.append({
                            "Name": sheet_name, "Month": valid_date, 
                            "Count": count, "Clinic_Tag": sheet_name
                        })
        except Exception as e: pass
        return pd.DataFrame(records)

    def parse_visits_sheet(df, filename_date, clinic_tag="General", target_year=None):
        records = []
        if target_year and filename_date.year != target_year: return pd.DataFrame(), []

        try:
            data_start_row = 4
            for i in range(data_start_row, len(df)):
                row = df.iloc[i].values
                row_str_check = " ".join([str(x).upper() for x in row[:5]])
                if "TOTAL" in row_str_check or "PAGE" in row_str_check or "DATE" in row_str_check: continue

                matched_name = None
                for c in range(min(10, len(row))): 
                    val = str(row[c]).strip()
                    matched_name = match_provider(val) 
                    if matched_name: break
                
                if not matched_name: continue

                numbers = []
                for val in row:
                    num = clean_number(val)
                    if num is not None: numbers.append(num)
                
                visits = 0; visits_diff = 0; new_patients = 0; np_diff = 0
                if len(numbers) >= 6:
                    visits = numbers[0]; visits_diff = numbers[1]; new_patients = numbers[3]; np_diff = numbers[4]
                elif len(numbers) >= 4:
                    visits = numbers[0]; visits_diff = numbers[1]; new_patients = numbers[3]
                elif len(numbers) == 3:
                    visits = numbers[0]; new_patients = numbers[2]
                elif len(numbers) == 2: 
                    visits = numbers[0]; new_patients = numbers[1]
                elif len(numbers) == 1:
                    visits = numbers[0]

                records.append({
                    "Name": matched_name, "Month_Clean": filename_date, "Total Visits": visits,
                    "Visits_Diff": visits_diff, "New Patients": new_patients, "NP_Diff": np_diff,
                    "Quarter": f"Q{filename_date.quarter} {filename_date.year}",
                    "Month_Label": filename_date.strftime('%b-%y'), "Clinic_Tag": clinic_tag
                })
        except: return pd.DataFrame()
        return pd.DataFrame(records), []

    def parse_financial_sheet(df, filename_date, tag, mode="Provider"):
        records = []
        try:
            header_row = -1; col_map = {}
            for i in range(min(15, len(df))):
                row_vals = [str(x).upper().strip() for x in df.iloc[i].values]
                if mode == "Provider":
                    if "PROVIDER" in row_vals:
                        header_row = i
                        for idx, val in enumerate(row_vals):
                            if "PROVIDER" in val: col_map['name'] = idx
                            elif "CHARGES" in val and "TOTAL" in val: col_map['charges'] = idx
                            elif "PAYMENT" in val and "TOTAL" in val: col_map['payments'] = idx
                        break
                elif mode == "Clinic":
                    if "SITE" in row_vals or "TOTAL" in row_vals:
                        header_row = i
                        for idx, val in enumerate(row_vals):
                            if "SITE" in val: col_map['name'] = idx
                            elif "CHARGES" in val: col_map['charges'] = idx
                            elif "PAYMENTS" in val: col_map['payments'] = idx
                        break
            
            if header_row == -1 or not col_map: return pd.DataFrame()

            for i in range(header_row + 1, len(df)):
                row = df.iloc[i].values
                name_val = str(row[col_map.get('name', 0)]).strip()
                
                if mode == "Clinic":
                    if tag in ["LROC", "TROC", "PROTON"] and "TOTAL" not in name_val.upper(): continue
                    if tag == "General":
                         whitelist = ["CENTENNIAL", "DICKSON", "MIDTOWN", "MURFREESBORO", "PROTON", "WEST", "SKYLINE", "STONECREST", "SUMMIT", "SUMNER", "TULLAHOMA"]
                         if not any(w in name_val.upper() for w in whitelist): continue

                charges = clean_number(row[col_map.get('charges', 1)]) or 0
                payments = clean_number(row[col_map.get('payments', 2)]) or 0
                
                if mode == "Provider":
                    clean_name = match_provider(name_val)
                    if not clean_name and "TOTAL" in name_val.upper() and tag == "PROTON":
                        pass 
                    elif not clean_name: continue
                else:
                    clean_name = name_val.replace(" Rad", "").strip()
                    if "TOTAL" in clean_name.upper(): 
                        if tag == "PROTON": clean_name = "TN Proton Center"
                        else: clean_name = tag + " Total"
                    
                    if "STONECREST" in clean_name.upper():
                         clean_name = "Stonecrest"

                records.append({
                    "Name": clean_name, "Month_Clean": filename_date,
                    "Charges": charges, "Payments": payments,
                    "Tag": tag, "Mode": mode,
                    "Quarter": f"Q{filename_date.quarter} {filename_date.year}"
                })
        except: pass
        return pd.DataFrame(records)

    def parse_pos_trend_sheet(df, filename, log, target_year=None):
        records = []
        try:
            header_row_idx = -1
            date_map = {} 
            for r in range(min(30, len(df))):
                row = df.iloc[r].values
                temp_date_map = {}
                for c in range(len(row)):
                    val = row[c]
                    if isinstance(val, (datetime, pd.Timestamp)):
                         temp_date_map[c] = val
                    else:
                        s_val = str(val).strip()
                        if re.match(r'(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)-\d{2}', s_val, re.IGNORECASE):
                            try:
                                dt = pd.to_datetime(s_val, format='%b-%y')
                                temp_date_map[c] = dt
                            except: pass
                if len(temp_date_map) >= 2:
                    header_row_idx = r
                    date_map = temp_date_map
                    break
            
            if header_row_idx != -1: 
                for i in range(header_row_idx + 1, len(df)):
                    row = df.iloc[i].values
                    c_id = None
                    for col_idx in range(3): 
                        if col_idx >= len(row): break
                        val = str(row[col_idx]).strip().upper()
                        if val and val != "NAN":
                            if val in POS_ROW_MAPPING:
                                c_id = POS_ROW_MAPPING[val]; break
                            for key, mapped_id in POS_ROW_MAPPING.items():
                                if key in val: c_id = mapped_id; break
                        if c_id: break
                    
                    if c_id:
                        for col_idx, dt in date_map.items():
                            if target_year and dt.year != target_year: continue 
                            if col_idx < len(row):
                                val = clean_number(row[col_idx])
                                if val is not None:
                                    records.append({
                                        "Clinic_Tag": c_id, "Month_Clean": dt, "New Patients": val,
                                        "Month_Label": dt.strftime('%b-%y'), "source_type": "pos_trend"
                                    })
        except Exception as e: pass
        return pd.DataFrame(records)

    def get_clinic_id_from_sheet(sheet_name):
        s_clean = sheet_name.lower().replace(" prov", "").replace(" rad", "").strip()
        for cid, cfg in CLINIC_CONFIG.items():
            if s_clean in cfg['name'].lower(): return cid
            if s_clean == cid.lower(): return cid
        if "horizon" in s_clean or "dickson" in s_clean: return "Dickson"
        if "centennial" in s_clean: return "CENT"
        if "midtown" in s_clean: return "Midtown"
        if "rutherford" in s_clean or "murfreesboro" in s_clean: return "MURF"
        if "west" in s_clean or "saint thomas" in s_clean: return "STW"
        if "lebanon" in s_clean: return "LROC"
        if "tullahoma" in s_clean: return "TROC"
        if "to proton" in s_clean: return "TOPC"
        return None

    # --- DEDUPLICATION HELPER ---
    def drop_dupes_safely(df, subset_keys):
        if df.empty: return df
        if 'Month_Clean' in df.columns:
            df['Month_Clean'] = pd.to_datetime(df['Month_Clean'], errors='coerce')
            df = df.dropna(subset=['Month_Clean'])
            # Sort descending to keep the most recent file's data
            df = df.sort_values('Month_Clean', ascending=False)
        return df.drop_duplicates(subset=subset_keys, keep='first')

    def process_files(file_objects):
        # 1. OS.WALK TO GET FILES FROM SUBFOLDERS
        all_files_to_process = []
        if isinstance(file_objects[0], LocalFile):
             for root, dirs, files in os.walk(SERVER_DIR):
                for f in sorted(files):
                    if f.endswith(".xlsx") or f.endswith(".xls"):
                        all_files_to_process.append(LocalFile(os.path.join(root, f)))
        else: all_files_to_process = file_objects

        clinic_data = []; provider_data = []; visit_data = []; financial_data = []; pos_trend_data = []; consult_data = []; app_cpt_data = []; md_cpt_data = []; md_consult_data = []
        debug_log = []; consult_log = []; prov_log = [] 

        for file_obj in all_files_to_process:
            if isinstance(file_obj, LocalFile):
                filename = file_obj.name; xls = pd.read_excel(file_obj.path, sheet_name=None, header=None)
                full_path = file_obj.path
            else:
                filename = file_obj.name.upper(); xls = pd.read_excel(file_obj, sheet_name=None, header=None)
                full_path = filename
            
            # --- GET TARGET YEAR FROM FOLDER/FILENAME ---
            target_year = get_target_year_from_text(full_path.upper())
            is_cpa = "CPA" in full_path.upper().split(os.sep) or "CPA" in filename
            if is_cpa: target_year = None # Do not filter CPA files
            
            file_date = get_date_from_filename(filename)
            file_tag = "General"
            if "LROC" in filename: file_tag = "LROC"
            elif "TROC" in filename: file_tag = "TROC"
            elif "PROTON" in filename or "TOPC" in filename: file_tag = "TOPC"

            if is_cpa:
                for sheet_name, df in xls.items():
                    if "RAD BY PROVIDER" in filename:
                        res = parse_financial_sheet(df, file_date, "RAD", mode="Provider")
                        if not res.empty: financial_data.append(res)
                    elif "PROTON" in filename and "PROVIDER" in filename:
                        res_prov = parse_financial_sheet(df, file_date, "PROTON", mode="Provider")
                        if not res_prov.empty: financial_data.append(res_prov)
                        try:
                             total_row = df[df.iloc[:, 1].astype(str).str.contains("Total", case=False, na=False)]
                             if not total_row.empty:
                                 chg = clean_number(total_row.iloc[0, 2])
                                 pay = clean_number(total_row.iloc[0, 3])
                                 financial_data.append(pd.DataFrame([{"Name": "TN Proton Center", "Month_Clean": file_date, "Charges": chg, "Payments": pay, "Tag": "PROTON", "Mode": "Clinic", "Quarter": f"Q{file_date.quarter} {file_date.year}"}]))
                        except: pass
                    elif "LROC" in filename and "PROVIDER" in filename:
                         res = parse_financial_sheet(df, file_date, "LROC", mode="Provider")
                         if not res.empty: financial_data.append(res)
                    elif "RAD CPA BY CLINIC" in filename:
                        res = parse_financial_sheet(df, file_date, "General", mode="Clinic")
                        if not res.empty: financial_data.append(res)
                    elif "LROC" in filename and "CLINIC" in filename:
                         res = parse_financial_sheet(df, file_date, "LROC", mode="Clinic")
                         if not res.empty: financial_data.append(res)
                    elif "TROC" in filename and "CLINIC" in filename:
                         res = parse_financial_sheet(df, file_date, "TROC", mode="Clinic")
                         if not res.empty: financial_data.append(res)
                continue

            if "NEW" in filename and ("PATIENT" in filename or "PT" in filename):
                for sheet_name, df in xls.items():
                    if "POS" in sheet_name.upper() and "TREND" in sheet_name.upper():
                        res = parse_pos_trend_sheet(df, filename, debug_log, target_year)
                        if not res.empty: pos_trend_data.append(res)

                visit_tag = "General"
                if "LROC" in filename: visit_tag = "LROC"
                elif "TROC" in filename: visit_tag = "TROC"
                elif "PROTON" in filename: visit_tag = "TOPC" 

                for sheet_name, df in xls.items():
                    if "PHYS YTD OV" in sheet_name.upper():
                        res, logs = parse_visits_sheet(df, file_date, clinic_tag=visit_tag, target_year=target_year)
                        if not res.empty: visit_data.append(res)
                continue 

            for sheet_name, df in xls.items():
                s_lower = sheet_name.strip().lower()
                clean_name = sheet_name.strip()
                
                match_prov = match_provider(clean_name)
                if match_prov:
                    if match_prov in APP_LIST:
                        res_cpt = parse_app_cpt_data(df, match_prov, prov_log, target_year)
                        if not res_cpt.empty: app_cpt_data.append(res_cpt)
                    else:
                        res_cpt = parse_app_cpt_data(df, match_prov, prov_log, target_year)
                        if not res_cpt.empty: md_cpt_data.append(res_cpt)
                        res_77263 = parse_consults_data(df, match_prov, consult_log, target_year)
                        if not res_77263.empty: md_consult_data.append(res_77263)

                if s_lower.endswith(" prov"):
                    c_id = get_clinic_id_from_sheet(sheet_name)
                    if c_id:
                        res = parse_detailed_prov_sheet(df, file_date, c_id, prov_log, target_year)
                        if not res.empty: provider_data.append(res)
                    elif "sumner" in s_lower:
                         res = parse_detailed_prov_sheet(df, file_date, "Sumner", prov_log, target_year)
                         if not res.empty: provider_data.append(res)
                    continue

                s_upper = sheet_name.upper()
                if any(ignored in s_upper for ignored in IGNORED_SHEETS): continue
                
                if clean_name in CLINIC_CONFIG:
                    res = parse_rvu_sheet(df, clean_name, 'clinic', clinic_tag="General", forced_fte=None, target_year=target_year)
                    if not res.empty: clinic_data.append(res)
                    pretty_name = CLINIC_CONFIG[clean_name]["name"]
                    res_consult = parse_consults_data(df, pretty_name, consult_log, target_year)
                    if not res_consult.empty: consult_data.append(res_consult)

                if "PRODUCTIVITY TREND" in s_upper: 
                    if file_tag in ["LROC", "TROC"]:
                        res = parse_rvu_sheet(df, file_tag, 'clinic', clinic_tag=file_tag, forced_fte=None, target_year=target_year)
                        if not res.empty: clinic_data.append(res)
                        pretty_name = CLINIC_CONFIG[file_tag]["name"]
                        res_consult = parse_consults_data(df, pretty_name, consult_log, target_year)
                        if not res_consult.empty: consult_data.append(res_consult)
                    continue

                if "PROTON" in s_upper and file_tag == "TOPC": continue 
                if clean_name.upper() == "FRIEDMEN": clean_name = "Friedman"
                if "PROTON POS" in s_upper: continue

                res = parse_rvu_sheet(df, clean_name, 'provider', clinic_tag=file_tag, forced_fte=None, target_year=target_year)
                if not res.empty: provider_data.append(res)

            if file_tag == "TOPC":
                proton_providers_temp = []
                for sheet_name, df in xls.items():
                    s_upper = sheet_name.upper()
                    if "PROV" in s_upper: continue
                    if any(ignored in s_upper for ignored in IGNORED_SHEETS) or "PROTON POS" in s_upper: continue
                    if "PRODUCTIVITY TREND" in s_upper: continue
                    clean_name = sheet_name.strip()
                    if clean_name.upper() == "FRIEDMEN": clean_name = "Friedman"
                    res = parse_rvu_sheet(df, clean_name, 'provider', clinic_tag="TOPC", forced_fte=None, target_year=target_year)
                    if not res.empty: proton_providers_temp.append(res)
                if proton_providers_temp:
                    combined_proton = pd.concat(proton_providers_temp)
                    topc_grp = combined_proton.groupby('Month', as_index=False)[['Total RVUs', 'FTE']].sum()
                    topc_records = []
                    for idx, row in topc_grp.iterrows():
                         topc_records.append({
                            "Type": "clinic", "ID": "TOPC", "Name": "TN Proton Center",
                            "FTE": row['FTE'], "Month": row['Month'],
                            "Total RVUs": row['Total RVUs'],
                            "RVU per FTE": row['Total RVUs'] / row['FTE'] if row['FTE'] > 0 else 0,
                            "Clinic_Tag": "TOPC", "source_type": "standard", "Month_Clean": pd.to_datetime(f"{row['Month']} {datetime.now().year}", errors='coerce')
                         })
                    clinic_data.append(pd.DataFrame(topc_records))

        # --- DEDUPLICATION LOGIC ---
        df_clinic = drop_dupes_safely(pd.concat(clinic_data, ignore_index=True), ['Name', 'Month_Clean', 'ID']) if clinic_data else pd.DataFrame()
        df_provider_raw = drop_dupes_safely(pd.concat(provider_data, ignore_index=True), ['Name', 'Month_Clean', 'Type', 'Clinic_Tag']) if provider_data else pd.DataFrame()
        df_visits = drop_dupes_safely(pd.concat(visit_data, ignore_index=True), ['Name', 'Month_Clean']) if visit_data else pd.DataFrame()
        df_financial = drop_dupes_safely(pd.concat(financial_data, ignore_index=True), ['Name', 'Month_Clean', 'Mode']) if financial_data else pd.DataFrame()
        df_pos_trend = drop_dupes_safely(pd.concat(pos_trend_data, ignore_index=True), ['Clinic_Tag', 'Month_Clean']) if pos_trend_data else pd.DataFrame()
        
        if consult_data:
            df_consults = pd.concat(consult_data, ignore_index=True)
            df_consults = drop_dupes_safely(df_consults, ['Name', 'Month_Clean'])
            df_consults['Month_Label'] = df_consults['Month_Clean'].dt.strftime('%b-%y')
        else: df_consults = pd.DataFrame(columns=['Name', 'Month', 'Count', 'Month_Label'])
        
        if md_consult_data:
            df_md_consults = pd.concat(md_consult_data, ignore_index=True)
            df_md_consults = drop_dupes_safely(df_md_consults, ['Name', 'Month_Clean'])
            df_md_consults['Month_Label'] = df_md_consults['Month_Clean'].dt.strftime('%b-%y')
        else: df_md_consults = pd.DataFrame(columns=['Name', 'Month', 'Count', 'Month_Label'])

        if app_cpt_data:
            df_app_cpt = pd.concat(app_cpt_data, ignore_index=True)
            df_app_cpt = drop_dupes_safely(df_app_cpt, ['Name', 'Month_Clean', 'CPT Code'])
            df_app_cpt['Month_Label'] = df_app_cpt['Month_Clean'].dt.strftime('%b-%y')
        else: df_app_cpt = pd.DataFrame(columns=['Name', 'Month', 'Count', 'CPT Code', 'Month_Label'])

        if md_cpt_data:
            df_md_cpt = pd.concat(md_cpt_data, ignore_index=True)
            df_md_cpt = drop_dupes_safely(df_md_cpt, ['Name', 'Month_Clean', 'CPT Code'])
            df_md_cpt['Month_Label'] = df_md_cpt['Month_Clean'].dt.strftime('%b-%y')
        else: df_md_cpt = pd.DataFrame(columns=['Name', 'Month', 'Count', 'CPT Code', 'Month_Label'])

        if not df_financial.empty:
            df_financial['Month_Label'] = df_financial['Month_Clean'].dt.strftime('%b-%y')

        if not df_pos_trend.empty:
            df_pos_trend['Month_Label'] = df_pos_trend['Month_Clean'].dt.strftime('%b-%y')
            # Add Display Name here safely for all rows to prevent KeyError
            df_pos_trend['Display_Name'] = df_pos_trend['Clinic_Tag'].apply(lambda x: CLINIC_CONFIG.get(x, {}).get('name', x))

        if not df_provider_raw.empty:
            df_provider_raw['Month_Label'] = df_provider_raw['Month_Clean'].dt.strftime('%b-%y')
            df_provider_raw['Quarter'] = df_provider_raw['Month_Clean'].apply(lambda x: f"Q{pd.Timestamp(x).quarter} {pd.Timestamp(x).year}")

        if not df_clinic.empty:
            df_clinic = df_clinic.groupby(['Name', 'ID', 'Month_Clean'], as_index=False).agg({'Total RVUs': 'sum', 'FTE': 'max', 'Clinic_Tag': 'first'})
            df_clinic['RVU per FTE'] = df_clinic.apply(lambda x: x['Total RVUs'] / x['FTE'] if x['FTE'] > 0 else 0, axis=1)
            df_clinic['Quarter'] = df_clinic['Month_Clean'].apply(lambda x: f"Q{pd.Timestamp(x).quarter} {pd.Timestamp(x).year}")
            df_clinic.sort_values('Month_Clean', inplace=True)
            df_clinic['Month_Label'] = df_clinic['Month_Clean'].dt.strftime('%b-%y')

        df_provider_global = pd.DataFrame()
        if not df_provider_raw.empty:
            df_md_clean = df_provider_raw[df_provider_raw.get('source_type', 'standard') != 'detail'].copy()
            df_provider_global = df_md_clean.groupby(['Name', 'ID', 'Month_Clean'], as_index=False).agg({'Total RVUs': 'sum', 'FTE': 'max', 'Quarter': 'first', 'Month_Label': 'first'})
            df_provider_global['RVU per FTE'] = df_provider_global.apply(lambda x: x['Total RVUs'] / x['FTE'] if x['FTE'] > 0 else 0, axis=1)
            df_provider_global.sort_values('Month_Clean', inplace=True)

        return df_clinic, df_provider_global, df_provider_raw, df_visits, df_financial, df_pos_trend, df_consults, df_app_cpt, df_md_cpt, df_md_consults

    # --- UI ---
    st.title("🩺 Radiation Oncology Division Analytics")
    st.markdown("##### by Dr. Jones")
    st.markdown("---")

    server_files = []
    if os.path.exists(SERVER_DIR):
        all_paths = []
        for root, dirs, files in os.walk(SERVER_DIR):
            for f in files:
                if f.endswith(".xlsx") or f.endswith(".xls"):
                    all_paths.append(os.path.join(root, f))
        all_paths.sort()
        for p in all_paths:
            server_files.append(LocalFile(p))

    with st.sidebar:
        st.header("Data Import")
        if server_files:
            st.success(f"✅ Loaded {len(server_files)} master files from server.")
        else:
            st.info("ℹ️ No master files found on server.")
        uploaded_files = st.file_uploader("Add Temporary Files", type=['xlsx', 'xls'], accept_multiple_files=True)
        
    all_files = server_files + (uploaded_files if uploaded_files else [])

    if all_files:
        with st.spinner("Analyzing files..."):
            df_clinic, df_md_global, df_provider_raw, df_visits, df_financial, df_pos_trend, df_consults, df_app_cpt, df_md_cpt, df_md_consults = process_files(all_files)

        if df_clinic.empty and df_md_global.empty and df_visits.empty and df_financial.empty and df_pos_trend.empty:
            st.error("No valid data found.")
        else:
            if not df_md_global.empty:
                df_apps = df_md_global[df_md_global['Name'].isin(APP_LIST)]
                valid_providers = set(PROVIDER_CONFIG.keys())
                df_mds = df_md_global[(df_md_global['Name'].isin(valid_providers)) & (~df_md_global['Name'].isin(APP_LIST))]
            else:
                df_apps = pd.DataFrame(); df_mds = pd.DataFrame()

            # --- TOP LEVEL TABS ---
            tab_c_26, tab_c_25, tab_md_26, tab_md_25, tab_app, tab_fin = st.tabs([
                "🏥 Clinic '26", "🏥 Clinic '25", "👨‍⚕️ MD '26", "👨‍⚕️ MD '25", "👩‍⚕️ APP", "💰 Financials"
            ])
            
            # --- CLINIC TAB HELPER ---
            def render_clinic_tab(target_year, df_clinic_full, df_provider_raw_full, df_pos_trend_full, df_consults_full):
                df_year = df_clinic_full[df_clinic_full['Month_Clean'].dt.year == target_year] if not df_clinic_full.empty else pd.DataFrame()
                df_prov_year = df_provider_raw_full[df_provider_raw_full['Month_Clean'].dt.year == target_year] if not df_provider_raw_full.empty else pd.DataFrame()
                df_pos_year = df_pos_trend_full[df_pos_trend_full['Month_Clean'].dt.year == target_year] if not df_pos_trend_full.empty else pd.DataFrame()
                df_cons_year = df_consults_full[df_consults_full['Month_Clean'].dt.year == target_year] if not df_consults_full.empty else pd.DataFrame()

                if df_year.empty:
                    st.info(f"No Clinic data found for {target_year}.")
                    return

                col_nav, col_main = st.columns([1, 5])
                with col_nav:
                    st.markdown(f"### 🔍 Filter ({target_year})")
                    clinic_filter = st.radio("Select View:", ["All", "TriStar", "Ascension", "LROC", "TOPC", "TROC", "Sumner"], key=f"clinic_radio_{target_year}")
                    
                    if FPDF and not df_year.empty:
                        st.markdown("---")
                        with st.expander(f"📄 Export PDF ({target_year})"):
                            avail_dates = sorted(df_year['Month_Clean'].unique(), reverse=True)
                            month_opts = [d.strftime('%b-%y') for d in avail_dates]
                            sel_month = st.selectbox("Select Period:", month_opts, key=f"sel_month_{target_year}")
                            target_date = pd.to_datetime(sel_month, format='%b-%y')
                            
                            if st.button("Generate PDF Report", key=f"btn_pdf_{target_year}"):
                                if clinic_filter == "All": pdf_view = df_year
                                elif clinic_filter == "TriStar": pdf_view = df_year[df_year['ID'].isin(TRISTAR_IDS)]
                                elif clinic_filter == "Ascension": pdf_view = df_year[df_year['ID'].isin(ASCENSION_IDS)]
                                elif clinic_filter == "LROC": pdf_view = df_year[df_year['ID'] == 'LROC']
                                elif clinic_filter == "TOPC": pdf_view = df_year[df_year['ID'] == 'TOPC']
                                elif clinic_filter == "TROC": pdf_view = df_year[df_year['ID'] == 'TROC']
                                elif clinic_filter == "Sumner": pdf_view = df_year[df_year['ID'] == 'Sumner']
                                
                                pdf_view_date = pdf_view[pdf_view['Month_Clean'] == target_date]
                                
                                if not pdf_view_date.empty:
                                    total_rvu = pdf_view_date['Total RVUs'].sum()
                                    avg_fte = pdf_view_date['FTE'].sum()
                                    rvu_fte = total_rvu / avg_fte if avg_fte > 0 else 0
                                    
                                    np_count = 0
                                    if not df_pos_year.empty:
                                        np_data = df_pos_year[(df_pos_year['Month_Clean'] == target_date)]
                                        np_count = np_data['New Patients'].sum()

                                    prov_breakdown = df_prov_year[(df_prov_year['Month_Clean'] == target_date)]
                                    if clinic_filter == "TriStar": prov_breakdown = prov_breakdown[prov_breakdown['Clinic_Tag'].isin(TRISTAR_IDS)]
                                    elif clinic_filter == "Ascension": prov_breakdown = prov_breakdown[prov_breakdown['Clinic_Tag'].isin(ASCENSION_IDS)]
                                    
                                    pdf_bytes = create_clinic_pdf(f"{clinic_filter} View", sel_month, total_rvu, rvu_fte, np_count, prov_breakdown)
                                    st.download_button("Download PDF", data=pdf_bytes, file_name=f"Report_{clinic_filter}_{sel_month}.pdf", mime='application/pdf', key=f"dl_pdf_{target_year}")

                with col_main:
                    df_view = pd.DataFrame(); view_title = clinic_filter; target_tag = None
                    if clinic_filter == "All": df_view = df_year.copy(); view_title = "All Clinics"
                    elif clinic_filter == "TriStar": df_view = df_year[df_year['ID'].isin(TRISTAR_IDS)]; view_title = "TriStar Group"
                    elif clinic_filter == "Ascension": df_view = df_year[df_year['ID'].isin(ASCENSION_IDS)]; view_title = "Ascension Group"
                    elif clinic_filter == "LROC": df_view = df_year[df_year['ID'] == 'LROC']; view_title = "LROC (Lebanon)"; target_tag = "LROC"
                    elif clinic_filter == "TOPC": df_view = df_year[df_year['ID'] == 'TOPC']; view_title = "TN Proton Center"; target_tag = "TOPC"
                    elif clinic_filter == "TROC": df_view = df_year[df_year['ID'] == 'TROC']; view_title = "TROC (Tullahoma)"; target_tag = "TROC"
                    elif clinic_filter == "Sumner": df_view = df_year[df_year['ID'] == 'Sumner']; view_title = "Sumner (Gallatin)"; target_tag = "Sumner"

                    if df_view.empty and clinic_filter not in ["TriStar", "Ascension"]:
                        st.warning(f"No data available for {view_title}.")
                    else:
                        max_date = df_view['Month_Clean'].max()
                        st.info(generate_narrative(df_view, f"{view_title} Clinic"))
                        
                        with st.container(border=True):
                            st.markdown(f"#### 📅 {view_title}: 12-Month Trend ({target_year})")
                            l12m_c = df_view.sort_values('Month_Clean')
                            if clinic_filter in ["TriStar", "Ascension", "All"]:
                                agg_trend = l12m_c.groupby('Month_Clean')[['Total RVUs']].sum().reset_index()
                                fig_trend = px.line(agg_trend, x='Month_Clean', y='Total RVUs', markers=True, title="Aggregate Trend")
                            else:
                                fig_trend = px.line(l12m_c, x='Month_Clean', y='Total RVUs', color='Name', markers=True)
                            st.plotly_chart(style_high_end_chart(fig_trend), use_container_width=True)

                        if clinic_filter in ["LROC", "TOPC", "TROC", "Sumner"]:
                            with st.container(border=True):
                                st.markdown(f"#### 📊 Quarterly wRVU Volume ({view_title})")
                                df_q_chart = df_view.copy()
                                df_q_chart['Q_Sort'] = df_q_chart['Month_Clean'].dt.to_period('Q').dt.start_time
                                q_agg = df_q_chart.groupby(['Quarter', 'Q_Sort'])[['Total RVUs']].sum().reset_index().sort_values('Q_Sort')
                                fig_q_bar = px.bar(q_agg, x='Quarter', y='Total RVUs', text_auto='.2s')
                                st.plotly_chart(style_high_end_chart(fig_q_bar), use_container_width=True)

                        if clinic_filter in ["TriStar", "Ascension", "All"]:
                            with st.container(border=True):
                                st.markdown(f"#### 📈 {view_title}: Individual Clinic Trends")
                                fig_ind = px.line(l12m_c, x='Month_Clean', y='Total RVUs', color='Name', markers=True)
                                st.plotly_chart(style_high_end_chart(fig_ind), use_container_width=True)
                                
                                if clinic_filter == "All" and not df_cons_year.empty:
                                    st.markdown("---")
                                    st.markdown("### 📝 Tx Plan Complex (CPT 77263)")
                                    sorted_m = df_cons_year.sort_values("Month_Clean")["Month_Label"].unique()
                                    piv_consult = df_cons_year.pivot_table(index="Name", columns="Month_Label", values="Count", aggfunc="sum")
                                    piv_consult = piv_consult.reindex(columns=sorted_m).fillna(0)
                                    piv_consult["Total"] = piv_consult.sum(axis=1)
                                    st.dataframe(piv_consult.sort_values("Total", ascending=False).style.format("{:,.0f}").background_gradient(cmap="Blues").set_table_styles([{'selector': 'th', 'props': [('color', 'black'), ('font-weight', 'bold')]}]), height=500)
                                
                                with st.container(border=True):
                                    st.markdown("##### 📅 Historical Data Summary")
                                    df_hist = get_historical_df()
                                    if clinic_filter == "TriStar": df_hist_view = df_hist[df_hist['ID'].isin(TRISTAR_IDS)]
                                    elif clinic_filter == "Ascension": df_hist_view = df_hist[df_hist['ID'].isin(ASCENSION_IDS)]
                                    elif clinic_filter == "All": df_hist_view = df_hist.copy()
                                    else: df_hist_view = pd.DataFrame()
                                    
                                    if not df_hist_view.empty:
                                        hist_trend = df_hist_view.groupby('Year')[['Total RVUs']].sum().reset_index()
                                        if not df_view.empty:
                                            ytd_curr = df_view['Total RVUs'].sum()
                                            if ytd_curr > 0:
                                                new_row = pd.DataFrame({"Year": [target_year], "Total RVUs": [ytd_curr]})
                                                hist_trend = pd.concat([hist_trend, new_row], ignore_index=True)
                                        hist_table_df = hist_trend.copy()
                                        hist_table_df['Year'] = hist_table_df['Year'].astype(int).astype(str)
                                        hist_table_T = hist_table_df.set_index('Year').T
                                        st.dataframe(hist_table_T.style.format("{:,.0f}"), use_container_width=True)

                                if not df_view.empty:
                                    c1, c2 = st.columns(2)
                                    with c1:
                                        with st.container(border=True):
                                            st.markdown("#### 🔢 Monthly Data")
                                            piv = df_view.pivot_table(index="Name", columns="Month_Label", values="Total RVUs", aggfunc="sum").fillna(0)
                                            sorted_months = df_view.sort_values("Month_Clean")["Month_Label"].unique()
                                            piv = piv.reindex(columns=sorted_months).fillna(0)
                                            piv["Total"] = piv.sum(axis=1)
                                            st.dataframe(piv.sort_values("Total", ascending=False).style.format("{:,.0f}").background_gradient(cmap="Reds").set_table_styles([{'selector': 'th', 'props': [('color', 'black'), ('font-weight', 'bold')]}]))
                                    with c2:
                                        with st.container(border=True):
                                            st.markdown("#### 📆 Quarterly Data")
                                            piv_q = df_view.pivot_table(index="Name", columns="Quarter", values="Total RVUs", aggfunc="sum").fillna(0)
                                            piv_q["Total"] = piv_q.sum(axis=1)
                                            st.dataframe(piv_q.sort_values("Total", ascending=False).style.format("{:,.0f}").background_gradient(cmap="Oranges").set_table_styles([{'selector': 'th', 'props': [('color', 'black'), ('font-weight', 'bold')]}]))

                        if clinic_filter == "All" and not df_pos_year.empty:
                            st.markdown("---")
                            st.markdown("### 🆕 Network-Wide New Patients")
                            max_date_np = df_pos_year['Month_Clean'].max()
                            np_latest = df_pos_year[df_pos_year['Month_Clean'] == max_date_np].copy()
                            if not np_latest.empty:
                                fig_np_net = px.bar(np_latest.sort_values('New Patients', ascending=False), x='Display_Name', y='New Patients', text_auto=True, title=f"New Patients: {max_date_np.strftime('%B %Y')}")
                                st.plotly_chart(style_high_end_chart(fig_np_net), use_container_width=True)

                                piv_np_net = df_pos_year.pivot_table(index="Month_Label", columns="Display_Name", values="New Patients", aggfunc="sum").fillna(0)
                                st.dataframe(piv_np_net.style.format("{:,.0f}").background_gradient(cmap="Greens").set_table_styles([{'selector': 'th', 'props': [('color', 'black'), ('font-weight', 'bold')]}]))

                        if clinic_filter in ["TriStar", "Ascension"]:
                            st.markdown("---")
                            st.subheader(f"🔍 Detailed Breakdown by Clinic ({view_title})")
                            target_ids = TRISTAR_IDS if clinic_filter == "TriStar" else ASCENSION_IDS
                            for c_id in target_ids:
                                c_name = CLINIC_CONFIG.get(c_id, {}).get('name', c_id)
                                clinic_prov_df = df_prov_year[(df_prov_year['Clinic_Tag'] == c_id) & (df_prov_year.get('source_type', '') == 'detail')]
                                if clinic_prov_df.empty:
                                    clinic_prov_df = df_prov_year[(df_prov_year['Clinic_Tag'] == c_id)]

                                if clinic_prov_df.empty: continue
                                st.markdown(f"### 🏥 {c_name}")
                                pie_agg_12m = clinic_prov_df.groupby('Name')[['Total RVUs']].sum().reset_index()
                                latest_q = clinic_prov_df['Quarter'].max()
                                pie_q = clinic_prov_df[clinic_prov_df['Quarter'] == latest_q]
                                pie_agg_q = pie_q.groupby('Name')[['Total RVUs']].sum().reset_index()
                                
                                if not pie_agg_12m.empty:
                                    with st.container(border=True):
                                        st.markdown(f"#### 🍰 {c_name}: Work Breakdown")
                                        cp1, cp2 = st.columns(2)
                                        with cp1:
                                            fig_p1 = px.pie(pie_agg_12m, values='Total RVUs', names='Name', hole=0.4, title=f"Full Year ({target_year})")
                                            fig_p1.update_traces(textposition='inside', textinfo='percent+label')
                                            st.plotly_chart(style_high_end_chart(fig_p1), use_container_width=True)
                                        with cp2:
                                            if not pie_agg_q.empty:
                                                fig_p2 = px.pie(pie_agg_q, values='Total RVUs', names='Name', hole=0.4, title=f"Most Recent Quarter ({latest_q})")
                                                fig_p2.update_traces(textposition='inside', textinfo='percent+label')
                                                st.plotly_chart(style_high_end_chart(fig_p2), use_container_width=True)
                                
                                with st.container(border=True):
                                    st.markdown(f"#### 🧑‍⚕️ {c_name}: Monthly Data (by Provider)")
                                    piv_p = clinic_prov_df.pivot_table(index="Name", columns="Month_Label", values="Total RVUs", aggfunc="sum").fillna(0)
                                    sorted_months_p = clinic_prov_df.sort_values("Month_Clean")["Month_Label"].unique()
                                    piv_p = piv_p.reindex(columns=sorted_months_p).fillna(0)
                                    piv_p["Total"] = piv_p.sum(axis=1)
                                    st.dataframe(piv_p.sort_values("Total", ascending=False).style.format("{:,.0f}").background_gradient(cmap="Blues").set_table_styles([{'selector': 'th', 'props': [('color', 'black'), ('font-weight', 'bold')]}]))

                                if not df_pos_year.empty:
                                    pos_df = df_pos_year[df_pos_year['Clinic_Tag'] == c_id]
                                    if not pos_df.empty:
                                        with st.container(border=True):
                                            st.markdown(f"#### 🆕 {c_name}: New Patient Trend")
                                            pos_agg = pos_df.groupby('Month_Clean')[['New Patients']].sum().reset_index().sort_values('Month_Clean')
                                            fig_pos = px.bar(pos_agg, x='Month_Clean', y='New Patients', text_auto=True)
                                            st.plotly_chart(style_high_end_chart(fig_pos), use_container_width=True)
                                            
                                            pos_piv = pos_df.pivot_table(index="Clinic_Tag", columns="Month_Label", values="New Patients", aggfunc="sum").fillna(0)
                                            sorted_m = pos_df.sort_values("Month_Clean")["Month_Label"].unique()
                                            pos_piv = pos_piv.reindex(columns=sorted_m).fillna(0)
                                            pos_piv["Total"] = pos_piv.sum(axis=1)
                                            st.dataframe(pos_piv.style.format("{:,.0f}").background_gradient(cmap="Greens").set_table_styles([{'selector': 'th', 'props': [('color', 'black'), ('font-weight', 'bold')]}]))
                        
                        if target_tag and not df_prov_year.empty:
                            pie_data_source = df_prov_year[(df_prov_year['Clinic_Tag'] == target_tag) & (df_prov_year.get('source_type', '') == 'detail')]
                            if pie_data_source.empty: pie_data_source = df_prov_year[df_prov_year['Clinic_Tag'] == target_tag]

                            if not pie_data_source.empty:
                                try:
                                    pie_agg_12m = pie_data_source.groupby('Name')[['Total RVUs']].sum().reset_index()
                                    latest_q = pie_data_source['Quarter'].max()
                                    pie_q = pie_data_source[pie_data_source['Quarter'] == latest_q]
                                    pie_agg_q = pie_q.groupby('Name')[['Total RVUs']].sum().reset_index()

                                    if not pie_agg_12m.empty:
                                        with st.container(border=True):
                                            st.markdown(f"#### 🍰 Work Breakdown: Who performed the work?")
                                            col_pie1, col_pie2 = st.columns(2)
                                            with col_pie1:
                                                if not pie_agg_12m.empty:
                                                    fig_p1 = px.pie(pie_agg_12m, values='Total RVUs', names='Name', hole=0.4, title=f"Full Year ({target_year})")
                                                    fig_p1.update_traces(textposition='inside', textinfo='percent+label')
                                                    st.plotly_chart(style_high_end_chart(fig_p1), use_container_width=True)
                                            with col_pie2:
                                                if not pie_agg_q.empty:
                                                    fig_p2 = px.pie(pie_agg_q, values='Total RVUs', names='Name', hole=0.4, title=f"Most Recent Quarter ({latest_q})")
                                                    fig_p2.update_traces(textposition='inside', textinfo='percent+label')
                                                    st.plotly_chart(style_high_end_chart(fig_p2), use_container_width=True)
                                except: st.info("Insufficient data for pie charts.")

                            with st.container(border=True):
                                st.markdown("#### 🧑‍⚕️ Monthly Data (by Provider)")
                                piv_p = pie_data_source.pivot_table(index="Name", columns="Month_Label", values="Total RVUs", aggfunc="sum").fillna(0)
                                sorted_months_p = pie_data_source.sort_values("Month_Clean")["Month_Label"].unique()
                                piv_p = piv_p.reindex(columns=sorted_months_p).fillna(0)
                                piv_p["Total"] = piv_p.sum(axis=1)
                                st.dataframe(piv_p.sort_values("Total", ascending=False).style.format("{:,.0f}").background_gradient(cmap="Blues").set_table_styles([{'selector': 'th', 'props': [('color', 'black'), ('font-weight', 'bold')]}]))

                        if target_tag in ["LROC", "TOPC", "TROC", "Sumner"] and not df_pos_year.empty:
                             pos_df = df_pos_year[df_pos_year['Clinic_Tag'] == target_tag]
                             if not pos_df.empty:
                                 with st.container(border=True):
                                     st.markdown("#### 🆕 New Patient Trend (Monthly)")
                                     pos_agg = pos_df.groupby('Month_Clean')[['New Patients']].sum().reset_index().sort_values('Month_Clean')
                                     fig_pos = px.bar(pos_agg, x='Month_Clean', y='New Patients', text_auto=True)
                                     st.plotly_chart(style_high_end_chart(fig_pos), use_container_width=True)
                                     
                                     pos_piv = pos_df.pivot_table(index="Clinic_Tag", columns="Month_Label", values="New Patients", aggfunc="sum").fillna(0)
                                     sorted_m = pos_df.sort_values("Month_Clean")["Month_Label"].unique()
                                     pos_piv = pos_piv.reindex(columns=sorted_m).fillna(0)
                                     pos_piv["Total"] = pos_piv.sum(axis=1)
                                     st.dataframe(pos_piv.style.format("{:,.0f}").background_gradient(cmap="Greens").set_table_styles([{'selector': 'th', 'props': [('color', 'black'), ('font-weight', 'bold')]}]))

            # --- RENDER HELPER FOR MD ---
            def render_md_tab(target_year, df_mds_full, df_visits_full, df_md_cons_full, df_md_cpt_full):
                df_mds_y = df_mds_full[df_mds_full['Month_Clean'].dt.year == target_year] if not df_mds_full.empty else pd.DataFrame()
                df_vis_y = df_visits_full[df_visits_full['Month_Clean'].dt.year == target_year] if not df_visits_full.empty else pd.DataFrame()
                df_cons_y = df_md_cons_full[df_md_cons_full['Month_Clean'].dt.year == target_year] if not df_md_cons_full.empty else pd.DataFrame()
                df_cpt_y = df_md_cpt_full[df_md_cpt_full['Month_Clean'].dt.year == target_year] if not df_md_cpt_full.empty else pd.DataFrame()

                if df_mds_y.empty and df_vis_y.empty:
                    st.info(f"No MD data available for {target_year}.")
                    return

                col_nav_md, col_main_md = st.columns([1, 5])
                with col_nav_md:
                    st.markdown(f"### 📊 Metric ({target_year})")
                    md_view = st.radio("Select View:", ["wRVU Productivity", "Office Visits"], key=f"md_rad_{target_year}")
                
                with col_main_md:
                    if md_view == "wRVU Productivity":
                        if df_mds_y.empty: st.info("No wRVU data found.")
                        else:
                            st.info(generate_narrative(df_mds_y, "Physician"))
                            with st.container(border=True):
                                st.markdown(f"#### 📅 Trend ({target_year})")
                                fig_trend = px.line(df_mds_y.sort_values('Month_Clean'), x='Month_Clean', y='RVU per FTE', color='Name', markers=True)
                                st.plotly_chart(style_high_end_chart(fig_trend), use_container_width=True)
                            with st.container(border=True):
                                st.markdown(f"#### 🏆 Total RVUs ({target_year})")
                                ytd_sum = df_mds_y.groupby('Name')[['Total RVUs']].sum().reset_index().sort_values('Total RVUs', ascending=False)
                                fig_ytd = px.bar(ytd_sum, x='Name', y='Total RVUs', color='Total RVUs', color_continuous_scale='Viridis', text_auto='.2s')
                                st.plotly_chart(style_high_end_chart(fig_ytd), use_container_width=True)
                            c1, c2 = st.columns(2)
                            with c1:
                                st.markdown("#### 🔢 Monthly Data")
                                piv = df_mds_y.pivot_table(index="Name", columns="Month_Label", values="Total RVUs", aggfunc="sum").fillna(0)
                                sorted_months_md = df_mds_y.sort_values("Month_Clean")["Month_Label"].unique()
                                piv = piv.reindex(columns=sorted_months_md).fillna(0)
                                piv["Total"] = piv.sum(axis=1)
                                st.dataframe(piv.sort_values("Total", ascending=False).style.format("{:,.0f}").background_gradient(cmap="Blues").set_table_styles([{'selector': 'th', 'props': [('color', 'black'), ('font-weight', 'bold')]}]))
                            with c2:
                                st.markdown("#### 📆 Quarterly Data")
                                piv_q = df_mds_y.pivot_table(index="Name", columns="Quarter", values="Total RVUs", aggfunc="sum").fillna(0)
                                piv_q["Total"] = piv_q.sum(axis=1)
                                st.dataframe(piv_q.sort_values("Total", ascending=False).style.format("{:,.0f}").background_gradient(cmap="Purples").set_table_styles([{'selector': 'th', 'props': [('color', 'black'), ('font-weight', 'bold')]}]))
                    
                    elif md_view == "Office Visits":
                        st.info("ℹ️ **This includes all HOPD and freestanding sites (including LROC, TROC, and TOPC)**")
                        if df_vis_y.empty:
                            st.warning("No Office Visit data found.")
                        else:
                            df_visits_agg = df_vis_y.groupby(['Name', 'Month_Clean'], as_index=False).agg({'Total Visits': 'sum', 'New Patients': 'sum', 'Visits_Diff': 'sum', 'NP_Diff': 'sum'})
                            latest_v_date = df_visits_agg['Month_Clean'].max()
                            latest_v_df = df_visits_agg[df_visits_agg['Month_Clean'] == latest_v_date]
                            
                            latest_v_df = latest_v_df[~latest_v_df['Name'].isin(APP_LIST)]
                            
                            st.info(generate_narrative(df_visits_agg, "Physician", metric_col="Total Visits", unit="Visits", timeframe=f"Year-to-Date ({target_year})"))
                            c_ov1, c_ov2 = st.columns(2)
                            with c_ov1:
                                with st.container(border=True):
                                    st.markdown(f"#### 🏥 Total Office Visits ({target_year})")
                                    fig_ov = px.bar(latest_v_df.sort_values('Total Visits', ascending=True), x='Total Visits', y='Name', orientation='h', text_auto=True, color='Total Visits', color_continuous_scale='Blues')
                                    fig_ov.update_layout(height=800)
                                    st.plotly_chart(style_high_end_chart(fig_ov), use_container_width=True)
                            with c_ov2:
                                with st.container(border=True):
                                    st.markdown(f"#### 🆕 New Patients ({target_year})")
                                    fig_np = px.bar(latest_v_df.sort_values('New Patients', ascending=True), x='New Patients', y='Name', orientation='h', text_auto=True, color='New Patients', color_continuous_scale='Greens')
                                    fig_np.update_layout(height=800)
                                    st.plotly_chart(style_high_end_chart(fig_np), use_container_width=True)
                            
                            st.markdown("---")
                            
                            if not df_cons_y.empty:
                                st.markdown("### 📝 MD Tx Plan Complex (CPT 77263)")
                                sorted_m_cons = df_cons_y.sort_values("Month_Clean")["Month_Label"].unique()
                                piv_md_cons = df_cons_y.pivot_table(index="Name", columns="Month_Label", values="Count", aggfunc="sum").fillna(0)
                                piv_md_cons = piv_md_cons.reindex(columns=sorted_m_cons).fillna(0)
                                piv_md_cons["Total"] = piv_md_cons.sum(axis=1)
                                st.dataframe(piv_md_cons.sort_values("Total", ascending=False).style.format("{:,.0f}").background_gradient(cmap="Blues").set_table_styles([{'selector': 'th', 'props': [('color', 'black'), ('font-weight', 'bold')]}]), height=500)
                                
                                md_77263_ytd = df_cons_y.groupby('Name')['Count'].sum().reset_index()
                                md_np_ytd = latest_v_df[['Name', 'New Patients']].copy()
                                ratio_df = pd.merge(md_77263_ytd, md_np_ytd, on='Name', how='inner')
                                ratio_df['Ratio'] = ratio_df.apply(lambda x: x['Count'] / x['New Patients'] if x['New Patients'] > 0 else 0, axis=1)
                                ratio_df['Label'] = ratio_df.apply(lambda x: f"{x['Ratio']:.2f} ({int(x['Count'])}/{int(x['New Patients'])})", axis=1)
                                ratio_df = ratio_df.sort_values('Ratio', ascending=True) 
                                
                                if not ratio_df.empty:
                                    st.markdown("---")
                                    st.markdown("### 📊 Ratio: Tx Plan (77263) / New Patients")
                                    fig_ratio = px.bar(
                                        ratio_df, x='Ratio', y='Name', orientation='h', text='Label',
                                        title="Ratio > 1.0 indicates more Tx Plans than New Patients"
                                    )
                                    fig_ratio.update_layout(height=800) 
                                    fig_ratio.update_traces(textposition='outside')
                                    st.plotly_chart(style_high_end_chart(fig_ratio), use_container_width=True)
                            
                            st.markdown("---")

                            if not df_cpt_y.empty:
                                st.markdown("### 🩺 Established Patients (99212-99215)")
                                
                                md_est_total = df_cpt_y.groupby('Name')['Count'].sum().reset_index()
                                md_est_total_sorted = md_est_total.sort_values('Count', ascending=True)

                                fig_est = px.bar(md_est_total_sorted, x='Count', y='Name', orientation='h', text_auto='.0f', 
                                                title=f"Established Patients ({target_year} YTD)", color='Count', color_continuous_scale='Viridis')
                                fig_est.update_layout(height=800)
                                st.plotly_chart(style_high_end_chart(fig_est), use_container_width=True)
                                
                                st.markdown("---")
                                
                                ytd_md = df_cpt_y.groupby(['Name', 'CPT Code'])['Count'].sum().reset_index()
                                fig_md_bar = px.bar(ytd_md, x="Name", y="Count", color="CPT Code", barmode="group", text_auto=True, title=f"YTD Follow-up Visits Breakdown ({target_year})")
                                st.plotly_chart(style_high_end_chart(fig_md_bar), use_container_width=True)
                                
                                cols = st.columns(2)
                                unique_mds = df_cpt_y['Name'].unique()
                                
                                for i, md_name in enumerate(unique_mds):
                                    with cols[i % 2]:
                                        with st.container(border=True):
                                            st.markdown(f"#### {md_name}")
                                            md_subset = df_cpt_y[df_cpt_y['Name'] == md_name]
                                            piv_md = md_subset.pivot_table(index="CPT Code", columns="Month_Label", values="Count", aggfunc="sum").fillna(0)
                                            sorted_m = md_subset.sort_values("Month_Clean")["Month_Label"].unique()
                                            piv_md = piv_md.reindex(columns=sorted_m).fillna(0)
                                            piv_md["Total"] = piv_md.sum(axis=1)
                                            st.dataframe(piv_md.style.format("{:,.0f}").background_gradient(cmap="Oranges"))

            # --- POPULATE TABS ---
            with tab_c_26: render_clinic_tab(2026, df_clinic, df_provider_raw, df_pos_trend, df_consults)
            with tab_c_25: render_clinic_tab(2025, df_clinic, df_provider_raw, df_pos_trend, df_consults)
            
            with tab_md_26: render_md_tab(2026, df_mds, df_visits, df_md_consults, df_md_cpt)
            with tab_md_25: render_md_tab(2025, df_mds, df_visits, df_md_consults, df_md_cpt)

            with tab_app:
                if df_apps.empty: st.info("No APP data found.")
                else:
                    st.info(generate_narrative(df_apps, "APP"))
                    
                    with st.container(border=True):
                        st.markdown("#### 📅 Last 12 Months Trend (RVU per FTE)")
                        fig_trend = px.line(df_apps.sort_values('Month_Clean'), x='Month_Clean', y='RVU per FTE', color='Name', markers=True)
                        st.plotly_chart(style_high_end_chart(fig_trend), use_container_width=True)
                    
                    st.markdown("---")

                    if not df_app_cpt.empty:
                        st.markdown("### 🏥 APP Independent Follow-up Visits (99212-99215)")
                        ytd_app = df_app_cpt.groupby(['Name', 'CPT Code'])['Count'].sum().reset_index()
                        fig_app_bar = px.bar(ytd_app, x="Name", y="Count", color="CPT Code", barmode="group", text_auto=True, title=f"YTD Follow-up Visits")
                        st.plotly_chart(style_high_end_chart(fig_app_bar), use_container_width=True)
                        
                        cols = st.columns(2)
                        unique_apps = df_app_cpt['Name'].unique()
                        for i, app_name in enumerate(unique_apps):
                            with cols[i % 2]:
                                with st.container(border=True):
                                    st.markdown(f"#### {app_name}")
                                    app_subset = df_app_cpt[df_app_cpt['Name'] == app_name]
                                    piv_app = app_subset.pivot_table(index="CPT Code", columns="Month_Label", values="Count", aggfunc="sum").fillna(0)
                                    sorted_m = app_subset.sort_values("Month_Clean")["Month_Label"].unique()
                                    piv_app = piv_app.reindex(columns=sorted_m).fillna(0)
                                    piv_app["Total"] = piv_app.sum(axis=1)
                                    st.dataframe(piv_app.style.format("{:,.0f}").background_gradient(cmap="Oranges"))

            with tab_fin:
                if df_financial.empty:
                    st.info("No Financial data found.")
                else:
                    fin_view = st.radio("Select Financial View:", ["CPA By Provider", "CPA By Clinic"], key="fin_radio")
                    
                    if fin_view == "CPA By Provider":
                         prov_fin = df_financial[(df_financial['Mode'] == 'Provider') & (df_financial['Name'] != "TN Proton Center")]
                         if not prov_fin.empty:
                             st.markdown("### 💰 CPA By Provider (YTD)")
                             latest_fin_date = prov_fin['Month_Clean'].max()
                             latest_prov = prov_fin[prov_fin['Month_Clean'] == latest_fin_date]
                             latest_prov = latest_prov.groupby('Name', as_index=False)[['Charges', 'Payments']].sum()
                             latest_prov['% Payments/Charges'] = latest_prov.apply(lambda x: (x['Payments'] / x['Charges']) if x['Charges'] > 0 else 0, axis=1)

                             c1, c2 = st.columns(2)
                             with c1:
                                 fig_chg = px.bar(latest_prov.sort_values('Charges', ascending=True), x='Charges', y='Name', orientation='h', title=f"Total Charges ({latest_fin_date.strftime('%b %Y')})", text_auto='$.2s')
                                 fig_chg.update_layout(height=1200)
                                 st.plotly_chart(style_high_end_chart(fig_chg), use_container_width=True)
                             with c2:
                                 fig_pay = px.bar(latest_prov.sort_values('Payments', ascending=True), x='Payments', y='Name', orientation='h', title=f"Total Payments ({latest_fin_date.strftime('%b %Y')})", text_auto='$.2s')
                                 fig_pay.update_layout(height=1200)
                                 st.plotly_chart(style_high_end_chart(fig_pay), use_container_width=True)
                             
                             # FIX: Fillna before formatting to prevent ValueError
                             latest_prov = latest_prov.fillna(0)
                             st.dataframe(latest_prov[['Name', 'Charges', 'Payments', '% Payments/Charges']].sort_values('Charges', ascending=False).style.format({'Charges': '${:,.2f}', 'Payments': '${:,.2f}', '% Payments/Charges': '{:.1%}'}).background_gradient(cmap="Greens").set_table_styles([{'selector': 'th', 'props': [('color', 'black'), ('font-weight', 'bold')]}]))
                    
                    elif fin_view == "CPA By Clinic":
                        clinic_fin = df_financial[df_financial['Mode'] == 'Clinic']
                        if not clinic_fin.empty:
                            st.markdown("### 🏥 CPA By Clinic")
                            ytd_df = clinic_fin.groupby('Name')[['Charges', 'Payments']].sum().reset_index()
                            ytd_df['% Payments/Charges'] = ytd_df.apply(lambda x: (x['Payments'] / x['Charges']) if x['Charges'] > 0 else 0, axis=1)
                            
                            total_charges = ytd_df['Charges'].sum()
                            total_payments = ytd_df['Payments'].sum()
                            total_ratio = (total_payments / total_charges) if total_charges > 0 else 0
                            
                            total_row = pd.DataFrame([{
                                "Name": "TOTAL",
                                "Charges": total_charges,
                                "Payments": total_payments,
                                "% Payments/Charges": total_ratio
                            }])
                            
                            ytd_display = pd.concat([ytd_df.sort_values('Charges', ascending=False), total_row], ignore_index=True)

                            st.markdown("#### 📆 Year to Date Charges & Payments")
                            # FIX: Fillna
                            ytd_display = ytd_display.fillna(0)
                            st.dataframe(ytd_display.style.format({'Charges': '${:,.2f}', 'Payments': '${:,.2f}', '% Payments/Charges': '{:.1%}'}).background_gradient(cmap="Greens").set_table_styles([{'selector': 'th', 'props': [('color', 'black'), ('font-weight', 'bold')]}]), height=600)

                            st.markdown("---")
                            st.markdown("#### 📅 Monthly Data Breakdown")
                            display_cols = ['Name', 'Month_Label', 'Charges', 'Payments']
                            monthly_display = clinic_fin[display_cols].sort_values(['Month_Label', 'Name'], ascending=False)
                            monthly_display['% Payments/Charges'] = monthly_display.apply(lambda x: (x['Payments'] / x['Charges']) if x['Charges'] > 0 else 0, axis=1)
                            monthly_display['Month_Sort'] = pd.to_datetime(monthly_display['Month_Label'], format='%b-%y')
                            monthly_display = monthly_display.sort_values(['Month_Sort', 'Name'], ascending=[False, True]).drop(columns=['Month_Sort'])
                            
                            # FIX: Fillna
                            monthly_display = monthly_display.fillna(0)
                            st.dataframe(monthly_display.style.format({'Charges': '${:,.2f}', 'Payments': '${:,.2f}', '% Payments/Charges': '{:.1%}'}).background_gradient(cmap="Blues").set_table_styles([{'selector': 'th', 'props': [('color', 'black'), ('font-weight', 'bold')]}]))
    else:
        st.info("👋 Ready. View Only Mode: Add files to 'Reports' folder in GitHub to update data.")
