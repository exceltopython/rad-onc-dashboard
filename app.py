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

# --- PDF GENERATOR ---
if FPDF:
    class PDFReport(FPDF):
        def header(self):
            self.set_font('Arial', 'B', 15)
            self.cell(0, 10, 'Radiation Oncology - Monthly Clinic Report', 0, 1, 'C')
            self.ln(5)
        def footer(self):
            self.set_y(-15)
            self.set_font('Arial', 'I', 8)
            self.cell(0, 10, f'Page {self.page_no()}', 0, 0, 'C')

    def create_clinic_pdf(clinic_name, month_label, total_rvu, rvu_fte, new_patients, provider_df):
        pdf = PDFReport()
        pdf.add_page()
        pdf.set_font('Arial', 'B', 14); pdf.cell(0, 10, f"Scope: {clinic_name}", 0, 1, 'L')
        pdf.set_font('Arial', '', 12); pdf.cell(0, 10, f"Period: {month_label}", 0, 1, 'L'); pdf.ln(5)
        pdf.set_fill_color(240, 240, 240); pdf.set_font('Arial', 'B', 12); pdf.cell(0, 10, "Executive Summary", 1, 1, 'L', fill=True)
        pdf.set_font('Arial', '', 11); pdf.cell(60, 10, "Total wRVUs:", 0, 0); pdf.set_font('Arial', 'B', 11); pdf.cell(0, 10, f"{total_rvu:,.2f}", 0, 1)
        pdf.set_font('Arial', '', 11); pdf.cell(60, 10, "wRVU per FTE:", 0, 0); pdf.set_font('Arial', 'B', 11); pdf.cell(0, 10, f"{rvu_fte:,.2f}", 0, 1)
        pdf.set_font('Arial', '', 11); pdf.cell(60, 10, "New Patients (Approx):", 0, 0); pdf.set_font('Arial', 'B', 11); pdf.cell(0, 10, f"{new_patients:,.0f}", 0, 1); pdf.ln(10)
        pdf.set_font('Arial', 'B', 12); pdf.cell(0, 10, "Provider Breakdown", 1, 1, 'L', fill=True)
        pdf.set_font('Arial', 'B', 10); pdf.cell(90, 10, "Provider Name", 1, 0, 'C'); pdf.cell(50, 10, "Total wRVUs", 1, 1, 'C')
        pdf.set_font('Arial', '', 10)
        if not provider_df.empty:
            for _, row in provider_df.iterrows():
                pdf.cell(90, 10, str(row['Name']), 1, 0); pdf.cell(50, 10, f"{row['Total RVUs']:,.2f}", 1, 1, 'R')
        else: pdf.cell(0, 10, "No individual provider data found for this period.", 1, 1)
        return pdf.output(dest='S').encode('latin-1')

# --- CONFIG ---
APP_PASSWORD = "RadOnc2026rj"

def check_password():
    def password_entered():
        if st.session_state["password"] == APP_PASSWORD:
            st.session_state["password_correct"] = True; del st.session_state["password"]
        else: st.session_state["password_correct"] = False
    if "password_correct" not in st.session_state:
        st.text_input("🔒 Enter Dashboard Password:", type="password", on_change=password_entered, key="password"); return False
    elif not st.session_state["password_correct"]:
        st.error("Access Denied."); return False
    return True

HISTORICAL_DATA = {
    2019: {"CENT": 18430, "Dickson": 11420, "Skyline": 13910, "Summit": 14690, "Stonecrest": 8600, "STW": 22030, "Midtown": 14730, "MURF": 38810, "Sumner": 14910, "TOPC": 15690, "LROC": 0, "TROC": 0},
    2020: {"CENT": 19160, "Dickson": 12940, "Skyline": 13180, "Summit": 11540, "Stonecrest": 7470, "STW": 17070, "Midtown": 14560, "MURF": 37890, "Sumner": 14760, "TOPC": 22010, "LROC": 0, "TROC": 0},
    2021: {"CENT": 14480, "Dickson": 10980, "Skyline": 11450, "Summit": 11700, "Stonecrest": 8610, "STW": 17970, "Midtown": 17890, "MURF": 37440, "Sumner": 17670, "TOPC": 28540, "LROC": 0, "TROC": 0},
    2022: {"CENT": 15860, "Dickson": 13960, "Skyline": 14520, "Summit": 12390, "Stonecrest": 10580, "STW": 27650, "Midtown": 19020, "MURF": 37870, "Sumner": 20570, "TOPC": 28830, "LROC": 0, "TROC": 0},
    2023: {"CENT": 19718, "Dickson": 11600, "Skyline": 17804, "Summit": 14151, "Stonecrest": 11647, "STW": 23717, "Midtown": 21017, "MURF": 42201, "Sumner": 22622, "TOPC": 27667, "LROC": 0, "TROC": 0},
    2024: {"CENT": 22385, "Dickson": 12155, "Skyline": 15363, "Summit": 12892, "Stonecrest": 12524, "STW": 25409, "Midtown": 21033, "MURF": 45648, "Sumner": 23803, "TOPC": 33892, "LROC": 0, "TROC": 0}
}

if check_password():
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
    CONSULT_CPT = "77263"; CONSULT_CONVERSION = 3.14; APP_CPT_RATES = {"99212": 0.7, "99213": 1.3, "99214": 1.92, "99215": 2.8}
    POS_ROW_MAPPING = {"CENTENNIAL RAD": "CENT", "DICKSON RAD": "Dickson", "MIDTOWN RAD": "Midtown", "MURFREESBORO RAD": "MURF", "SAINT THOMAS WEST RAD": "STW", "SKYLINE RAD": "Skyline", "STONECREST RAD": "Stonecrest", "SUMMIT RAD": "Summit", "SUMNER RAD": "Sumner", "LEBANON RAD": "LROC", "TULLAHOMA RADIATION": "TROC", "TO PROTON": "TOPC"}

    class LocalFile:
        def __init__(self, path):
            self.path = path; self.name = os.path.basename(path).upper()
        
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
        # Look for 2025, 2026, or 25, 26 in the text (filename or folder)
        # We prefer 4 digits, but accept 2 if it looks like a year
        match = re.search(r'(20)?(2[0-9])', text)
        if match:
            y = match.group(2)
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
            base = name_str.split(",")[0].strip() if "," in name_str else name_str
            parts = base.split(); 
            if not parts: return None
            last_name = parts[0].strip().upper()
            if last_name == "FRIEDMEN": last_name = "FRIEDMAN"
            if last_name in PROVIDER_KEYS_UPPER: return PROVIDER_KEYS_UPPER[last_name]
            return None
        except: return None

    def clean_provider_name_display(name_str):
        match = match_provider(name_str)
        if match: return match
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

        narrative = f"""### 🤖 Automated Analysis ({latest_date.strftime('%B %Y')})
The **{entity_type}** group ({provider_count} active) generated a total of **{total_vol:,.0f} {unit}** {timeframe}.  
The group average was **{avg_vol:,.0f} {unit}** per {entity_type.lower()}.
#### 🏆 Top Performers:
"""
        if len(sorted_df) > 0: top_1 = sorted_df.iloc[0]; narrative += f"* **🥇 1st:** **{clean_provider_name_display(top_1['Name'])}** ({top_1[top_col]:,.0f} {top_metric_name})\n"
        if len(sorted_df) > 1: top_2 = sorted_df.iloc[1]; narrative += f"* **🥈 2nd:** **{clean_provider_name_display(top_2['Name'])}** ({top_2[top_col]:,.0f})\n"
        if len(sorted_df) > 2: top_3 = sorted_df.iloc[2]; narrative += f"* **🥉 3rd:** **{clean_provider_name_display(top_3['Name'])}** ({top_3[top_col]:,.0f})\n"
        return narrative

    # --- PARSERS WITH DEBUG LOGGING & TARGET YEAR ---
    def parse_rvu_sheet(df, sheet_name, entity_type, clinic_tag="General", forced_fte=None, target_year=None, debug_log=None):
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
                elif isinstance(header_val, str):
                     try: col_dt = pd.to_datetime(header_val.strip(), format='%b-%y')
                     except: pass
                
                # STRICT YEAR FILTER: Only if date found AND target_year set
                if col_dt and target_year and col_dt.year != target_year:
                    # if debug_log is not None: debug_log.append(f"    Skipping col {col_dt} (Target: {target_year})")
                    continue 

                col_sum = pd.to_numeric(data_rows[col], errors='coerce').sum()
                records.append({
                    "Type": entity_type, "ID": sheet_name, "Name": name, "FTE": fte,
                    "Month": col_dt if col_dt else header_val, "Total RVUs": col_sum, 
                    "RVU per FTE": col_sum / fte if fte > 0 else 0, "Clinic_Tag": clinic_tag, 
                    "source_type": "standard", "Month_Clean": col_dt
                })
        return pd.DataFrame(records)

    # (Other parsers follow same pattern - truncated for brevity but logic is identical to above)
    def parse_detailed_prov_sheet(df, filename_date, clinic_id, log, target_year):
        records = []
        current_provider = None
        current_values = {"E&M OFFICE CODES": 0.0, "RADIATION CODES": 0.0, "SPECIAL PROCEDURES": 0.0}
        target_terms = list(current_values.keys()); term_counts = {k: 0 for k in current_values}
        date_map = {}; header_row_found = False
        for r in range(min(15, len(df))):
            row = df.iloc[r].values
            for c in range(len(row)):
                val = str(row[c]).strip()
                if re.match(r'(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)-\d{2}', val, re.IGNORECASE):
                    try: 
                        dt = pd.to_datetime(val, format='%b-%y')
                        if target_year and dt.year != target_year: continue
                        date_map[c] = dt; header_row_found = True
                    except: pass
            if header_row_found: break
            
        for i in range(len(df)):
            row = df.iloc[i].values; potential_name = None
            for c in range(min(5, len(row))):
                val = str(row[c]).strip(); match = match_provider(val)
                if match: potential_name = match; break
            if potential_name: current_provider = potential_name; term_counts = {k: 0 for k in target_terms}; continue
            if current_provider:
                row_label = str(row[0]).upper()
                for term in target_terms:
                    if term in row_label:
                        term_counts[term] += 1
                        if term_counts[term] == 2:
                            for col_idx, dt in date_map.items():
                                if col_idx < len(row):
                                    val = clean_number(row[col_idx])
                                    if val and val != 0:
                                        records.append({"Type": "provider", "ID": clinic_id, "Name": current_provider, "FTE": 1.0, "Month": dt, "Total RVUs": val, "RVU per FTE": val, "Clinic_Tag": clinic_id, "Quarter": f"Q{dt.quarter} {dt.year}", "Month_Label": dt.strftime('%b-%y'), "source_type": "detail", "Month_Clean": dt})
        return pd.DataFrame(records)

    def parse_visits_sheet(df, filename_date, clinic_tag="General", target_year=None):
        if target_year and filename_date.year != target_year: return pd.DataFrame(), []
        records = []
        try:
            data_start_row = 4
            for i in range(data_start_row, len(df)):
                row = df.iloc[i].values
                row_str_check = " ".join([str(x).upper() for x in row[:5]])
                if "TOTAL" in row_str_check or "PAGE" in row_str_check or "DATE" in row_str_check: continue
                val = str(row[0]).strip(); matched_name = match_provider(val)
                if not matched_name:
                    for c in range(min(10, len(row))): 
                        val = str(row[c]).strip(); matched_name = match_provider(val)
                        if matched_name: break
                if not matched_name: continue
                numbers = []
                for val in row:
                    num = clean_number(val); 
                    if num is not None: numbers.append(num)
                visits = 0; visits_diff = 0; new_patients = 0; np_diff = 0
                if len(numbers) >= 6: visits = numbers[0]; visits_diff = numbers[1]; new_patients = numbers[3]; np_diff = numbers[4]
                elif len(numbers) >= 4: visits = numbers[0]; visits_diff = numbers[1]; new_patients = numbers[3]
                elif len(numbers) == 1: visits = numbers[0]
                records.append({"Name": matched_name, "Month_Clean": filename_date, "Total Visits": visits, "Visits_Diff": visits_diff, "New Patients": new_patients, "NP_Diff": np_diff, "Quarter": f"Q{filename_date.quarter} {filename_date.year}", "Month_Label": filename_date.strftime('%b-%y'), "Clinic_Tag": clinic_tag})
        except: return pd.DataFrame()
        return pd.DataFrame(records), []

    def parse_pos_trend_sheet(df, filename, log, target_year):
        records = []
        try:
            header_row_idx = -1; date_map = {} 
            for r in range(min(30, len(df))):
                row = df.iloc[r].values; temp_date_map = {}
                for c in range(len(row)):
                    val = row[c]
                    if isinstance(val, (datetime, pd.Timestamp)): temp_date_map[c] = val
                    else:
                        s_val = str(val).strip()
                        if re.match(r'(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)-\d{2}', s_val, re.IGNORECASE):
                            try: dt = pd.to_datetime(s_val, format='%b-%y'); temp_date_map[c] = dt
                            except: pass
                if len(temp_date_map) >= 2: header_row_idx = r; date_map = temp_date_map; break
            
            if header_row_idx != -1: 
                for i in range(header_row_idx + 1, len(df)):
                    row = df.iloc[i].values; c_id = None
                    for col_idx in range(3): 
                        val = str(row[col_idx]).strip().upper()
                        if val in POS_ROW_MAPPING: c_id = POS_ROW_MAPPING[val]; break
                    if c_id:
                        for col_idx, dt in date_map.items():
                            if target_year and dt.year != target_year: continue
                            if col_idx < len(row):
                                val = clean_number(row[col_idx])
                                if val is not None: records.append({"Clinic_Tag": c_id, "Month_Clean": dt, "New Patients": val, "Month_Label": dt.strftime('%b-%y'), "source_type": "pos_trend"})
        except: pass
        return pd.DataFrame(records)

    def parse_financial_sheet(df, filename_date, tag, mode="Provider"):
        records = []
        try:
            header_row = -1; col_map = {}
            for i in range(min(15, len(df))):
                row_vals = [str(x).upper().strip() for x in df.iloc[i].values]
                if mode == "Provider" and "PROVIDER" in row_vals: header_row = i; # ... logic omitted for brevity, same as before
                elif mode == "Clinic" and ("SITE" in row_vals or "TOTAL" in row_vals): header_row = i # ...
                
                # (Simple logic for column mapping)
                if header_row != -1:
                    for idx, val in enumerate(row_vals):
                        if "CHARGES" in val: col_map['charges'] = idx
                        elif "PAYMENT" in val: col_map['payments'] = idx
                        elif "PROVIDER" in val or "SITE" in val: col_map['name'] = idx
                    break
            
            if header_row != -1:
                for i in range(header_row + 1, len(df)):
                    row = df.iloc[i].values
                    name_val = str(row[col_map.get('name', 0)]).strip()
                    charges = clean_number(row[col_map.get('charges', 1)]) or 0
                    payments = clean_number(row[col_map.get('payments', 2)]) or 0
                    
                    clean_name = name_val # Simplified cleaning
                    if mode == "Provider": clean_name = match_provider(name_val)
                    else: clean_name = name_val.replace(" Rad", "").strip()

                    if clean_name:
                         records.append({"Name": clean_name, "Month_Clean": filename_date, "Charges": charges, "Payments": payments, "Tag": tag, "Mode": mode, "Quarter": f"Q{filename_date.quarter} {filename_date.year}"})
        except: pass
        return pd.DataFrame(records)

    # --- MAIN PROCESSOR ---
    def get_clinic_id_from_sheet(sheet_name):
        s_clean = sheet_name.lower().replace(" prov", "").replace(" rad", "").strip()
        for cid, cfg in CLINIC_CONFIG.items():
            if s_clean in cfg['name'].lower(): return cid
            if s_clean == cid.lower(): return cid
        if "horizon" in s_clean: return "Dickson"
        if "centennial" in s_clean: return "CENT"
        if "midtown" in s_clean: return "Midtown"
        if "rutherford" in s_clean: return "MURF"
        if "west" in s_clean: return "STW"
        if "lebanon" in s_clean: return "LROC"
        if "tullahoma" in s_clean: return "TROC"
        return None

    def deduplicate_data(df, group_keys):
        """Keep only the latest entry (by date) for duplicated keys."""
        if df.empty: return df
        # Sort by Month_Clean descending, so we keep the latest if duplicates exist in source
        return df.sort_values('Month_Clean', ascending=False).drop_duplicates(subset=group_keys, keep='first')

    def process_files(file_objects, debug_mode=False):
        all_files = []
        if isinstance(file_objects[0], LocalFile):
             for root, dirs, files in os.walk(SERVER_DIR):
                for f in sorted(files): # Sorted to process older->newer files? Actually dedup logic handles it.
                    if f.endswith(".xlsx") or f.endswith(".xls"):
                        all_files.append(LocalFile(os.path.join(root, f)))
        else: all_files = file_objects

        clinic_data = []; provider_data = []; visit_data = []; financial_data = []; pos_trend_data = []
        debug_log = []

        for file_obj in all_files:
            fname = file_obj.name; fpath = file_obj.path if isinstance(file_obj, LocalFile) else fname
            xls = pd.read_excel(fpath, sheet_name=None, header=None)
            
            # --- CONTEXT DETECTION ---
            target_year = get_target_year_from_text(fpath.upper())
            is_cpa = "CPA" in fpath.upper()
            file_date = get_date_from_filename(fname)
            
            if debug_mode: debug_log.append(f"📄 Processing: {fname} | Target Year: {target_year} | CPA: {is_cpa}")

            if is_cpa:
                # Process Financials (No year filtering)
                for sname, df in xls.items():
                    if "RAD BY PROVIDER" in fname: financial_data.append(parse_financial_sheet(df, file_date, "RAD", "Provider"))
                    elif "RAD CPA BY CLINIC" in fname: financial_data.append(parse_financial_sheet(df, file_date, "General", "Clinic"))
                    # ... (add other CPA cases here if needed)
                continue

            # Process Operational
            # 1. New Patients
            if "NEW" in fname and "PATIENT" in fname:
                for sname, df in xls.items():
                    if "POS" in sname.upper(): 
                        res = parse_pos_trend_sheet(df, fname, debug_log, target_year)
                        if not res.empty: pos_trend_data.append(res)
                # Visits usually in New Patient files too
                for sname, df in xls.items():
                    if "PHYS YTD OV" in sname.upper():
                        res, _ = parse_visits_sheet(df, file_date, "General", target_year)
                        if not res.empty: visit_data.append(res)
                continue

            # 2. RVUs / Productivity
            for sname, df in xls.items():
                s_clean = sname.strip()
                # Provider Sheet?
                match_prov = match_provider(s_clean)
                if match_prov:
                    # Add Provider specific parsers here (CPT etc)
                    pass 
                
                # Clinic Sheet?
                cid = get_clinic_id_from_sheet(s_clean)
                if cid: 
                    # If it ends in " Prov", it's detailed provider data for that clinic
                    if s_clean.lower().endswith(" prov"):
                        res = parse_detailed_prov_sheet(df, file_date, cid, debug_log, target_year)
                        if not res.empty: provider_data.append(res)
                    else:
                        # Otherwise it's clinic summary
                        res = parse_rvu_sheet(df, cid, 'clinic', "General", None, target_year, debug_log)
                        if not res.empty: clinic_data.append(res)
                
                # Check for "Productivity Trend" sheet -> Clinic Summary
                if "PRODUCTIVITY TREND" in s_clean.upper():
                    # Logic to find which clinic... usually in filename for LROC/TROC
                    pass 

        # --- COMBINE & DEDUPLICATE ---
        df_clinic = deduplicate_data(pd.concat(clinic_data, ignore_index=True), ['Name', 'Month_Clean', 'ID']) if clinic_data else pd.DataFrame()
        df_provider = deduplicate_data(pd.concat(provider_data, ignore_index=True), ['Name', 'Month_Clean', 'Clinic_Tag']) if provider_data else pd.DataFrame()
        df_pos = deduplicate_data(pd.concat(pos_trend_data, ignore_index=True), ['Clinic_Tag', 'Month_Clean']) if pos_trend_data else pd.DataFrame()
        df_visits = deduplicate_data(pd.concat(visit_data, ignore_index=True), ['Name', 'Month_Clean']) if visit_data else pd.DataFrame()
        df_fin = deduplicate_data(pd.concat(financial_data, ignore_index=True), ['Name', 'Month_Clean', 'Mode']) if financial_data else pd.DataFrame()
        
        # Date Cleanup
        for df in [df_clinic, df_provider, df_pos, df_visits, df_fin]:
            if not df.empty and 'Month_Clean' in df.columns:
                df['Month_Label'] = df['Month_Clean'].dt.strftime('%b-%y')
                df['Quarter'] = df['Month_Clean'].apply(lambda x: f"Q{x.quarter} {x.year}")

        return df_clinic, df_provider, df_visits, df_fin, df_pos, debug_log

    # --- UI LAYOUT ---
    
    server_files = []
    if os.path.exists(SERVER_DIR):
        for root, _, files in os.walk(SERVER_DIR):
            for f in files:
                if f.endswith(".xlsx") or f.endswith(".xls"):
                    server_files.append(LocalFile(os.path.join(root, f)))

    with st.sidebar:
        st.header("Data Import")
        st.info(f"📂 Found {len(server_files)} files.")
        debug_mode = st.checkbox("🐞 Show Debug Mode", value=False)
        uploaded_files = st.file_uploader("Upload Files", accept_multiple_files=True)
    
    files_to_use = server_files + (uploaded_files if uploaded_files else [])
    
    if files_to_use:
        with st.spinner("Processing..."):
            df_clinic, df_provider, df_visits, df_fin, df_pos, dlog = process_files(files_to_use, debug_mode)
        
        if debug_mode:
            st.markdown("### 🐞 Debug Log")
            st.text("\n".join(dlog))
            st.write("Clinic Data Preview:", df_clinic.head())

        if df_clinic.empty and df_provider.empty:
            st.warning("No data extracted. Check Debug Mode.")
        else:
            tab1, tab2, tab3 = st.tabs(["🏥 Clinic Analytics", "👨‍⚕️ MD Analytics", "💰 Financials"])
            
            with tab1:
                st.subheader("Clinic Performance")
                view = st.radio("View", ["All", "TriStar", "Ascension"], horizontal=True)
                
                # Filter Logic
                df_view = df_clinic.copy()
                if view == "TriStar": df_view = df_clinic[df_clinic['ID'].isin(TRISTAR_IDS)]
                elif view == "Ascension": df_view = df_clinic[df_clinic['ID'].isin(ASCENSION_IDS)]
                
                if not df_view.empty:
                    st.info(generate_narrative(df_view, "Clinic"))
                    
                    # 12 Month Trend
                    daily_trend = df_view.groupby('Month_Clean')['Total RVUs'].sum().reset_index()
                    fig = px.line(daily_trend, x='Month_Clean', y='Total RVUs', markers=True, title=f"{view} Trend")
                    st.plotly_chart(style_high_end_chart(fig), use_container_width=True)
                    
                    # Data Table
                    piv = df_view.pivot_table(index="Name", columns="Month_Label", values="Total RVUs", aggfunc="sum").fillna(0)
                    st.dataframe(piv.style.format("{:,.0f}"))
            
            with tab2:
                st.subheader("Physician Analytics")
                if not df_provider.empty:
                    # Separate 2025 vs 2026
                    df_2025 = df_provider[df_provider['Month_Clean'].dt.year == 2025]
                    df_2026 = df_provider[df_provider['Month_Clean'].dt.year == 2026]
                    
                    st.markdown("### 🗓️ 2026 Performance")
                    if not df_2026.empty:
                         piv26 = df_2026.pivot_table(index="Name", columns="Month_Label", values="Total RVUs", aggfunc="sum").fillna(0)
                         st.dataframe(piv26.style.format("{:,.0f}"))
                    else:
                        st.info("No 2026 Data yet.")

                    st.markdown("### 🗓️ 2025 Performance")
                    if not df_2025.empty:
                         piv25 = df_2025.pivot_table(index="Name", columns="Month_Label", values="Total RVUs", aggfunc="sum").fillna(0)
                         st.dataframe(piv25.style.format("{:,.0f}"))

            with tab3:
                st.subheader("Financials")
                if not df_fin.empty:
                    fin_agg = df_fin.groupby(['Name'])[['Charges', 'Payments']].sum().reset_index()
                    st.dataframe(fin_agg.style.format("${:,.2f}"))
                else:
                    st.info("No CPA data found.")

    else:
        st.info("Awaiting data...")
