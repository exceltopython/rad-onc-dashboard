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

# --- HELPER: CHART STYLING ---
def style_high_end_chart(fig):
    fig.update_layout(
        font={'family': "Inter, sans-serif", 'color': '#334155'},
        title_font={'family': "Inter, sans-serif", 'size': 18, 'color': '#0f172a'},
        paper_bgcolor='rgba(0,0,0,0)', 
        plot_bgcolor='rgba(0,0,0,0)', 
        margin=dict(t=50, l=20, r=20, b=40),
        xaxis=dict(showgrid=False, showline=True, linecolor='#cbd5e1', tickfont=dict(color='#64748b')),
        yaxis=dict(showgrid=True, gridcolor='#f1f5f9', showline=False, tickfont=dict(color='#64748b')),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        hoverlabel=dict(bgcolor="white", font_size=12, font_family="Inter")
    )
    return fig

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
        pdf.cell(50, 10, "Total wRVUs", 1, 1, 'C') 
        
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
# --- 2. HISTORICAL DATA ENTRY (2019-2025) ---
# ==========================================
HISTORICAL_DATA = {
    2019: {"CENT": 18430, "Dickson": 11420, "Skyline": 13910, "Summit": 14690, "Stonecrest": 8600, "STW": 22030, "Midtown": 14730, "MURF": 38810, "Sumner": 14910, "TOPC": 15690, "LROC": 0, "TROC": 0},
    2020: {"CENT": 19160, "Dickson": 12940, "Skyline": 13180, "Summit": 11540, "Stonecrest": 7470, "STW": 17070, "Midtown": 14560, "MURF": 37890, "Sumner": 14760, "TOPC": 22010, "LROC": 0, "TROC": 0},
    2021: {"CENT": 14480, "Dickson": 10980, "Skyline": 11450, "Summit": 11700, "Stonecrest": 8610, "STW": 17970, "Midtown": 17890, "MURF": 37440, "Sumner": 17670, "TOPC": 28540, "LROC": 0, "TROC": 0},
    2022: {"CENT": 15860, "Dickson": 13960, "Skyline": 14520, "Summit": 12390, "Stonecrest": 10580, "STW": 27650, "Midtown": 19020, "MURF": 37870, "Sumner": 20570, "TOPC": 28830, "LROC": 0, "TROC": 0},
    2023: {"CENT": 19718, "Dickson": 11600, "Skyline": 17804, "Summit": 14151, "Stonecrest": 11647, "STW": 23717, "Midtown": 21017, "MURF": 42201, "Sumner": 22622, "TOPC": 27667, "LROC": 0, "TROC": 0},
    2024: {"CENT": 22385, "Dickson": 12155, "Skyline": 15363, "Summit": 12892, "Stonecrest": 12524, "STW": 25409, "Midtown": 21033, "MURF": 45648, "Sumner": 23803, "TOPC": 33892, "LROC": 0, "TROC": 0},
    2025: {"CENT": 22236, "Dickson": 12954, "Skyline": 13931, "Summit": 9225, "Stonecrest": 11873, "STW": 22024, "Midtown": 19172, "MURF": 43857, "Sumner": 24169, "TOPC": 37515, "LROC": 14528, "TROC": 9042}
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

    # APP FOLLOW-UP CPT CONFIG
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

    def standardize_date(x):
        if pd.isna(x): return pd.NaT
        if isinstance(x, (datetime, pd.Timestamp)):
            return pd.Timestamp(year=x.year, month=x.month, day=1)
        if isinstance(x, str):
            try: return pd.to_datetime(x.strip(), format='%b-%y').replace(day=1)
            except: 
                try: return pd.to_datetime(x.strip()).replace(day=1)
                except: return pd.NaT
        return pd.NaT
        
    def get_target_year_from_text(text):
        match = re.search(r'(JAN|FEB|MAR|APR|MAY|JUN|JUL|AUG|SEP|OCT|NOV|DEC)\s*(20)?(2[0-9])', text, re.IGNORECASE)
        if match:
            y = match.group(3)
            return int("20" + y[-2:])
        match2 = re.search(r'(20)?(2[0-9])', text)
        if match2:
            return int("20" + match2.group(2))
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
            if last_name == "FRIEDMEN": last_name = "FRIEDMAN"
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
            top_metric_name = "wRVU/FTE"; top_col = 'RVU per FTE'
        else:
            sorted_df = latest_df.sort_values(metric_col, ascending=False)
            top_metric_name = unit; top_col = metric_col
        narrative = f"### 🤖 Automated Analysis ({latest_date.strftime('%B %Y')})\nThe **{entity_type}** group ({provider_count} active) generated a total of **{total_vol:,.0f} {unit}** {timeframe}. The group average was **{avg_vol:,.0f} {unit}** per {entity_type.lower()}.\n\n#### 🏆 Top Performers:\n"
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

    # --- PARSERS ---

    def parse_detailed_prov_sheet(df, filename_date, clinic_id, log, target_year=None):
        records = []; current_provider = None; target_terms = ["E&M OFFICE CODES", "RADIATION CODES", "SPECIAL PROCEDURES"]
        term_counts = {k: 0 for k in target_terms}
        date_map = {}; header_row_found = False
        for r in range(min(15, len(df))):
            row = df.iloc[r].values
            for c in range(len(row)):
                val = str(row[c]).strip()
                if re.match(r'(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)-\d{2}', val, re.IGNORECASE):
                    dt_clean = standardize_date(val)
                    if pd.notna(dt_clean):
                        if target_year and dt_clean.year != target_year: continue 
                        date_map[c] = dt_clean; header_row_found = True
            if header_row_found: break
        for i in range(len(df)):
            row = df.iloc[i].values; potential_name = None
            for c in range(min(5, len(row))):
                val = str(row[c]).strip(); match = match_provider(val)
                if match: potential_name = match; break
            if potential_name:
                current_provider = potential_name; term_counts = {k: 0 for k in target_terms}; continue
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
                                            records.append({"Type": "provider", "ID": clinic_id, "Name": current_provider, "FTE": 1.0, "Month_Clean": dt, "Total RVUs": val, "RVU per FTE": val, "Clinic_Tag": clinic_id, "source_type": "detail"})
                            else:
                                if len(row) > 19:
                                    val = clean_number(row[19])
                                    if val:
                                        file_dt_clean = standardize_date(filename_date)
                                        if target_year and pd.notna(file_dt_clean) and file_dt_clean.year != target_year: continue
                                        records.append({"Type": "provider", "ID": clinic_id, "Name": current_provider, "FTE": 1.0, "Month_Clean": file_dt_clean, "Total RVUs": val, "RVU per FTE": val, "Clinic_Tag": clinic_id, "source_type": "detail"})
        return pd.DataFrame(records)

    def parse_app_cpt_data(df, provider_name, log, target_year=None):
        records = []
        try:
            header_row_idx = find_date_row(df)
            for cpt_code, rate in APP_CPT_RATES.items():
                cpt_row_idx = -1
                for r in range(len(df)):
                    row_val = str(df.iloc[r, 0]).strip()
                    if row_val.startswith(cpt_code): cpt_row_idx = r; break
                if cpt_row_idx != -1:
                    for col in df.columns[4:]: 
                        dt_clean = standardize_date(df.iloc[header_row_idx, col])
                        if pd.isna(dt_clean) or (target_year and dt_clean.year != target_year): continue 
                        val = clean_number(df.iloc[cpt_row_idx, col])
                        if val is not None and val != 0:
                            records.append({"Name": provider_name, "Month_Clean": dt_clean, "Count": val / rate, "CPT Code": cpt_code, "Rate": rate})
        except: pass
        return pd.DataFrame(records)

    def parse_rvu_sheet(df, sheet_name, entity_type, clinic_tag="General", forced_fte=None, target_year=None):
        if entity_type == 'clinic':
            config = CLINIC_CONFIG.get(sheet_name, {"name": sheet_name, "fte": 1.0})
            name = config['name']; fte = config['fte']
        else:
            name = sheet_name; fte = forced_fte if forced_fte else PROVIDER_CONFIG.get(sheet_name, 1.0)
        df.iloc[:, 0] = df.iloc[:, 0].astype(str).str.strip().str.upper()
        mask = df.iloc[:, 0].isin(TARGET_CATEGORIES); data_rows = df[mask].copy()
        records = []; header_row_idx = find_date_row(df)
        if len(df.columns) > 4:
            for col in df.columns[4:]:
                dt_clean = standardize_date(df.iloc[header_row_idx, col])
                if pd.isna(dt_clean) or (target_year and dt_clean.year != target_year): continue 
                col_sum = pd.to_numeric(data_rows[col], errors='coerce').sum()
                records.append({"Type": entity_type, "ID": sheet_name, "Name": name, "FTE": fte, "Month_Clean": dt_clean, "Total RVUs": col_sum, "RVU per FTE": col_sum / fte if fte > 0 else 0, "Clinic_Tag": clinic_tag, "source_type": "standard"})
        return pd.DataFrame(records)

    def parse_consults_data(df, sheet_name, log, target_year=None):
        records = []
        try:
            header_row_idx = find_date_row(df); rvu_section_start = 0
            for r in range(len(df)):
                val = str(df.iloc[r, 0]).upper()
                if "WORK RVU" in val or "WRVU" in val: rvu_section_start = r; break
            cpt_row_idx = -1
            for r in range(rvu_section_start, len(df)):
                if CONSULT_CPT in str(df.iloc[r, 0]).strip(): cpt_row_idx = r; break
            if cpt_row_idx != -1:
                for col in df.columns[4:]: 
                    dt_clean = standardize_date(df.iloc[header_row_idx, col])
                    if pd.isna(dt_clean) or (target_year and dt_clean.year != target_year): continue
                    val = clean_number(df.iloc[cpt_row_idx, col])
                    if val is not None:
                        records.append({"Name": sheet_name, "Month_Clean": dt_clean, "Count": val / CONSULT_CONVERSION, "Clinic_Tag": sheet_name})
        except: pass
        return pd.DataFrame(records)
    def parse_visits_sheet(df, filename_date, clinic_tag="General", target_year=None):
        records = []; file_dt = standardize_date(filename_date)
        if target_year and pd.notna(file_dt) and file_dt.year != target_year: return pd.DataFrame(), []
        try:
            for i in range(4, len(df)):
                row = df.iloc[i].values
                row_str_check = " ".join([str(x).upper() for x in row[:5]])
                if any(x in row_str_check for x in ["TOTAL", "PAGE", "DATE"]): continue
                matched_name = None
                for c in range(min(10, len(row))): 
                    val = str(row[c]).strip(); matched_name = match_provider(val) 
                    if matched_name: break
                if not matched_name: continue
                numbers = [clean_number(val) for val in row if clean_number(val) is not None]
                visits = 0; new_patients = 0; np_diff = 0
                if len(numbers) >= 6: visits = numbers[0]; new_patients = numbers[3]; np_diff = numbers[4]
                elif len(numbers) >= 4: visits = numbers[0]; new_patients = numbers[3]
                elif len(numbers) == 3: visits = numbers[0]; new_patients = numbers[2]
                elif len(numbers) == 2: visits = numbers[0]; new_patients = numbers[1]
                elif len(numbers) == 1: visits = numbers[0]
                records.append({"Name": matched_name, "Month_Clean": file_dt, "Total Visits": visits, "New Patients": new_patients, "NP_Diff": np_diff, "Clinic_Tag": clinic_tag})
        except: return pd.DataFrame(), []
        return pd.DataFrame(records), []

    def parse_financial_sheet(df, filename_date, tag, mode="Provider"):
        records = []
        try:
            header_row = -1; col_map = {}
            for i in range(min(15, len(df))):
                row_vals = [str(x).upper().strip() for x in df.iloc[i].values]
                if mode == "Provider" and "PROVIDER" in row_vals:
                    header_row = i
                    for idx, val in enumerate(row_vals):
                        if "PROVIDER" in val: col_map['name'] = idx
                        elif "CHARGES" in val: col_map['charges'] = idx
                        elif "PAYMENT" in val: col_map['payments'] = idx
                    break
                elif mode == "Clinic" and ("SITE" in row_vals or "TOTAL" in row_vals):
                    header_row = i
                    for idx, val in enumerate(row_vals):
                        if "SITE" in val: col_map['name'] = idx
                        elif "CHARGES" in val: col_map['charges'] = idx
                        elif "PAYMENTS" in val: col_map['payments'] = idx
                    break
            if header_row == -1 or not col_map: return pd.DataFrame()
            file_dt = standardize_date(filename_date)
            for i in range(header_row + 1, len(df)):
                row = df.iloc[i].values; name_val = str(row[col_map.get('name', 0)]).strip()
                if mode == "Clinic":
                    if tag in ["LROC", "TROC", "PROTON"] and "TOTAL" not in name_val.upper(): continue
                    whitelist = ["CENTENNIAL", "DICKSON", "MIDTOWN", "MURFREESBORO", "PROTON", "WEST", "SKYLINE", "STONECREST", "SUMMIT", "SUMNER", "TULLAHOMA"]
                    if tag == "General" and not any(w in name_val.upper() for w in whitelist): continue
                charges = clean_number(row[col_map.get('charges', 1)]) or 0
                payments = clean_number(row[col_map.get('payments', 2)]) or 0
                if mode == "Provider":
                    clean_name = match_provider(name_val)
                    if not clean_name: continue
                else:
                    clean_name = name_val.replace(" Rad", "").strip()
                    if "TOTAL" in clean_name.upper(): clean_name = "TN Proton Center" if tag == "PROTON" else tag + " Total"
                records.append({"Name": clean_name, "Month_Clean": file_dt, "Charges": charges, "Payments": payments, "Tag": tag, "Mode": mode})
        except: pass
        return pd.DataFrame(records)

    def parse_pos_trend_sheet(df, filename, log, target_year=None):
        records = []
        try:
            header_row_idx = -1; date_map = {} 
            for r in range(min(30, len(df))):
                temp_date_map = {}
                for c in range(len(df.columns)):
                    dt_clean = standardize_date(df.iloc[r, c])
                    if pd.notna(dt_clean): temp_date_map[c] = dt_clean
                if len(temp_date_map) >= 2: header_row_idx = r; date_map = temp_date_map; break
            if header_row_idx == -1: return pd.DataFrame()
            for i in range(header_row_idx + 1, len(df)):
                row = df.iloc[i].values; c_id = None
                for col_idx in range(3):
                    val = str(row[col_idx]).strip().upper()
                    if val in POS_ROW_MAPPING: c_id = POS_ROW_MAPPING[val]; break
                    for key, mapped_id in POS_ROW_MAPPING.items():
                        if key in val: c_id = mapped_id; break
                if c_id:
                    for col_idx, dt in date_map.items():
                        if target_year and dt.year != target_year: continue
                        val = clean_number(row[col_idx])
                        if val is not None: records.append({"Clinic_Tag": c_id, "Month_Clean": dt, "New Patients": val, "source_type": "pos_trend"})
        except: pass
        return pd.DataFrame(records)

    def get_clinic_id_from_sheet(sheet_name):
        s_clean = sheet_name.lower().replace(" prov", "").replace(" rad", "").strip()
        for cid, cfg in CLINIC_CONFIG.items():
            if s_clean in cfg['name'].lower() or s_clean == cid.lower(): return cid
        return None

    def safe_dedup_and_format(df_list, subset_cols):
        if not df_list: return pd.DataFrame()
        df = pd.concat(df_list, ignore_index=True)
        if 'Month_Clean' in df.columns:
            df['Month_Clean'] = df['Month_Clean'].apply(standardize_date)
            df = df.dropna(subset=['Month_Clean'])
            sort_cols = ['Month_Clean']
            if 'Total RVUs' in df.columns: sort_cols.append('Total RVUs')
            df = df.sort_values(sort_cols, ascending=[False, False])
        valid_subset = [c for c in subset_cols if c in df.columns]
        if valid_subset: df = df.drop_duplicates(subset=valid_subset, keep='first')
        if not df.empty and 'Month_Clean' in df.columns:
            df['Month_Label'] = df['Month_Clean'].dt.strftime('%b-%y')
            if 'Quarter' not in df.columns: df['Quarter'] = df['Month_Clean'].apply(lambda x: f"Q{x.quarter} {x.year}")
        return df

    def process_files(file_objects):
        clinic_data = []; provider_data = []; visit_data = []; financial_data = []; pos_trend_data = []; consult_data = []; app_cpt_data = []; md_cpt_data = []; md_consult_data = []
        debug_log = []; consult_log = []; prov_log = [] 
        for file_obj in file_objects:
            fname = file_obj.name.upper(); path_or_buf = file_obj if hasattr(file_obj, 'read') else file_obj.path
            xls = pd.read_excel(path_or_buf, sheet_name=None, header=None)
            target_year = get_target_year_from_text(fname); is_cpa = "CPA" in fname
            file_date = get_date_from_filename(fname); file_tag = "General"
            if "LROC" in fname: file_tag = "LROC"
            elif "TROC" in fname: file_tag = "TROC"
            elif "PROTON" in fname: file_tag = "TOPC"
            if is_cpa:
                for sname, df in xls.items():
                    if "RAD BY PROVIDER" in fname: financial_data.append(parse_financial_sheet(df, file_date, "RAD", "Provider"))
                    elif "RAD CPA BY CLINIC" in fname: financial_data.append(parse_financial_sheet(df, file_date, "General", "Clinic"))
                continue
            if "NEW" in fname and ("PATIENT" in fname or "PT" in fname):
                for sname, df in xls.items():
                    if "POS" in sname.upper() and "TREND" in sname.upper(): pos_trend_data.append(parse_pos_trend_sheet(df, fname, debug_log, target_year))
                    if "PHYS YTD OV" in sname.upper():
                        res, _ = parse_visits_sheet(df, file_date, file_tag, target_year)
                        visit_data.append(res)
                continue
            for sname, df in xls.items():
                s_up = sname.upper(); match_prov = match_provider(sname)
                if any(ig in s_up for ig in IGNORED_SHEETS) or ("TREND" in s_up and "PRODUCTIVITY" not in s_up): continue
                if match_prov:
                    app_cpt_data.append(parse_app_cpt_data(df, match_prov, prov_log, target_year))
                    md_consult_data.append(parse_consults_data(df, match_prov, consult_log, target_year))
                if s_up.endswith(" PROV"): provider_data.append(parse_detailed_prov_sheet(df, file_date, get_clinic_id_from_sheet(sname) or "General", prov_log, target_year))
                if sname in CLINIC_CONFIG:
                    clinic_data.append(parse_rvu_sheet(df, sname, 'clinic', target_year=target_year))
                    consult_data.append(parse_consults_data(df, CLINIC_CONFIG[sname]["name"], consult_log, target_year))
                res = parse_rvu_sheet(df, sname, 'provider', clinic_tag=file_tag, target_year=target_year)
                if not res.empty: provider_data.append(res)
        return safe_dedup_and_format(clinic_data, ['Name', 'Month_Clean', 'ID']), \
               safe_dedup_and_format(provider_data, ['Name', 'Month_Clean', 'Clinic_Tag']), \
               safe_dedup_and_format(visit_data, ['Name', 'Month_Clean', 'Clinic_Tag']), \
               safe_dedup_and_format(financial_data, ['Name', 'Month_Clean', 'Mode']), \
               safe_dedup_and_format(pos_trend_data, ['Clinic_Tag', 'Month_Clean']), \
               safe_dedup_and_format(consult_data, ['Name', 'Month_Clean', 'Clinic_Tag']), \
               safe_dedup_and_format(app_cpt_data, ['Name', 'Month_Clean', 'CPT Code']), \
               safe_dedup_and_format(md_consult_data, ['Name', 'Month_Clean'])
        server_files = []
    if os.path.exists(SERVER_DIR):
        for root, _, files in os.walk(SERVER_DIR):
            for f in files:
                if f.endswith((".xlsx", ".xls")): server_files.append(LocalFile(os.path.join(root, f)))
    with st.sidebar:
        st.header("Data Import")
        if server_files: st.success(f"✅ Loaded {len(server_files)} master files.")
        uploaded = st.file_uploader("Add Temporary Files", type=['xlsx'], accept_multiple_files=True)
    all_f = server_files + (uploaded if uploaded else [])
    if all_f:
        with st.spinner("Analyzing files..."):
            df_c, df_p_raw, df_v, df_f, df_pos, df_cons, df_app, df_md_cons = process_files(all_f)
        
        # Tabs logic
        t_c26, t_c25, t_md26, t_md25, t_fin = st.tabs(["🏥 Clinic 2026", "🏥 Clinic 2025", "👨‍⚕️ MD 2026", "👨‍⚕️ MD 2025", "💰 Financials"])

        def render_hist_summary(df_curr, yr, filter_ids=None):
            h_raw = get_historical_df()
            if filter_ids: h_raw = h_raw[h_raw['ID'].isin(filter_ids)]
            agg = h_raw.groupby('Year')[['Total RVUs']].sum().reset_index()
            if not df_curr.empty:
                ytd = df_curr[df_curr['Month_Clean'].dt.year == yr]['Total RVUs'].sum()
                if yr in agg['Year'].values: agg.loc[agg['Year'] == yr, 'Total RVUs'] = ytd
                else: agg = pd.concat([agg, pd.DataFrame([{"Year": yr, "Total RVUs": ytd}])])
            agg['Year'] = agg['Year'].astype(str)
            # UNIQUE FIX: Collapse any duplicates before Transpose to stop crash
            final_h = agg.groupby('Year').sum().T
            st.dataframe(final_h.style.format("{:,.0f}"), use_container_width=True)

        with t_c26:
            c_filter = st.radio("Select View:", ["All", "TriStar", "Ascension"], key="r26")
            f_ids = TRISTAR_IDS if c_filter == "TriStar" else (ASCENSION_IDS if c_filter == "Ascension" else None)
            st.markdown("##### 📅 Historical Data Summary")
            render_hist_summary(df_c, 2026, f_ids)
            curr_c = df_c[df_c['Month_Clean'].dt.year == 2026]
            if f_ids: curr_c = curr_c[curr_c['ID'].isin(f_ids)]
            if not curr_c.empty:
                st.plotly_chart(style_high_end_chart(px.line(curr_c.sort_values('Month_Clean'), x='Month_Clean', y='Total RVUs', color='Name', markers=True)))
                # Monthly Tables
                piv_26 = curr_c.pivot_table(index="Name", columns="Month_Label", values="Total RVUs", aggfunc="sum").fillna(0)
                st.dataframe(piv_26.style.format("{:,.0f}").background_gradient(cmap="Blues"), use_container_width=True)
            
            # Pie Chart Fallback logic
            st.markdown("### 🍰 detailed Breakdown")
            pie_data = df_p_raw[(df_p_raw['Month_Clean'].dt.year == 2026)]
            if not pie_data.empty:
                fig_p = px.pie(pie_data.groupby('Name')['Total RVUs'].sum().reset_index(), values='Total RVUs', names='Name', hole=0.4)
                st.plotly_chart(style_high_end_chart(fig_p), use_container_width=True)

        with t_c25:
            st.markdown("##### 📅 Historical Data Summary")
            render_hist_summary(df_c, 2025)
            curr_c25 = df_c[df_c['Month_Clean'].dt.year == 2025]
            if not curr_c25.empty:
                st.plotly_chart(style_high_end_chart(px.line(curr_c25.sort_values('Month_Clean'), x='Month_Clean', y='Total RVUs', color='Name', markers=True)))

        with t_md26:
            curr_p26 = df_p_raw[df_p_raw['Month_Clean'].dt.year == 2026]
            if not curr_p26.empty:
                p_agg = curr_p26.groupby('Name')['Total RVUs'].sum().reset_index().sort_values('Total RVUs', ascending=False)
                st.plotly_chart(style_high_end_chart(px.bar(p_agg, x='Total RVUs', y='Name', orientation='h', text_auto='.2s')))
                if not df_md_cons.empty:
                    st.markdown("### 📝 Tx Plan Complex (CPT 77263)")
                    cons_piv = df_md_cons[df_md_cons['Month_Clean'].dt.year == 2026].pivot_table(index="Name", columns="Month_Label", values="Count", aggfunc="sum").fillna(0)
                    st.dataframe(cons_piv.style.format("{:,.1f}").background_gradient(cmap="Purples"), use_container_width=True)

        with t_fin:
            if not df_f.empty:
                st.markdown("### 💰 CPA Financials")
                st.dataframe(df_f[df_f['Month_Clean'] == df_f['Month_Clean'].max()].style.format({'Charges': '${:,.0f}', 'Payments': '${:,.0f}'}))
    else: st.info("👋 Upload files or check GitHub folder.")
