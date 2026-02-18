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
        .stTabs [data-baseweb="tab-list"] button [data-testid="stMarkdownContainer"] p { font-size: 16px !important; font-weight: 700 !important; margin: 0px; }
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
    """Applies a high-end, minimalist aesthetic to Plotly charts."""
    fig.update_layout(
        font={'family': "Inter, sans-serif", 'color': '#334155'},
        title_font={'family': "Inter, sans-serif", 'size': 18, 'color': '#0f172a'},
        paper_bgcolor='rgba(0,0,0,0)', 
        plot_bgcolor='rgba(0,0,0,0)', 
        margin=dict(t=50, l=20, r=20, b=40),
        xaxis=dict(
            showgrid=False, 
            showline=True, 
            linecolor='#cbd5e1', 
            tickfont=dict(color='#64748b')
        ),
        yaxis=dict(
            showgrid=True, 
            gridcolor='#f1f5f9', 
            showline=False, 
            tickfont=dict(color='#64748b')
        ),
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="right",
            x=1
        ),
        hoverlabel=dict(
            bgcolor="white",
            font_size=12,
            font_family="Inter"
        )
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

    # --- HELPER: GET TARGET YEAR FROM FOLDER ---
    def get_target_year_from_text(text):
        match = re.search(r'(JAN|FEB|MAR|APR|MAY|JUN|JUL|AUG|SEP|OCT|NOV|DEC)\s*(20)?(2[0-9])', text, re.IGNORECASE)
        if match:
            y = match.group(3)
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

    # --- PARSERS WITH YEAR FILTER ---

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
                        if target_year and dt.year != target_year: continue # Filter
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
                            else:
                                # Standard Fallback
                                pass
        return pd.DataFrame(records)

    # --- NEW: PARSER FOR FOLLOW-UP CODES (99212-99215) ---
    def parse_app_cpt_data(df, provider_name, log, target_year=None):
        records = []
        try:
            header_row_idx = find_date_row(df)
            
            # Iterate through each specific CPT code we care about
            for cpt_code, rate in APP_CPT_RATES.items():
                cpt_row_idx = -1
                for r in range(len(df)):
                    row_val = str(df.iloc[r, 0]).strip()
                    # Simple string check for the code at start of row
                    if row_val.startswith(cpt_code):
                        cpt_row_idx = r
                        break
                
                if cpt_row_idx != -1:
                    # Extract monthly data
                    for col in df.columns[4:]: 
                        header_val = df.iloc[header_row_idx, col]
                        
                        # DATE CHECK (Flexible)
                        valid_date = None
                        if isinstance(header_val, (datetime, pd.Timestamp)):
                             valid_date = header_val
                        elif isinstance(header_val, str):
                             if re.match(r'(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)-\d{2}', header_val.strip(), re.IGNORECASE):
                                 try: valid_date = pd.to_datetime(header_val.strip(), format='%b-%y')
                                 except: pass
                        
                        if valid_date is None: continue 
                        if target_year and valid_date.year != target_year: continue # Filter
                        
                        val = clean_number(df.iloc[cpt_row_idx, col])
                        if val is not None and val != 0:
                            # Convert wRVU to Count
                            count = val / rate
                            records.append({
                                "Name": provider_name, 
                                "Month": valid_date, 
                                "Count": count, 
                                "CPT Code": cpt_code,
                                "Rate": rate
                            })
        except Exception as e:
            log.append(f"    ❌ Error parsing APP CPT for {provider_name}: {str(e)}")
        
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
                
                if col_dt and target_year and col_dt.year != target_year: continue # Filter
                
                col_sum = pd.to_numeric(data_rows[col], errors='coerce').sum()
                records.append({
                    "Type": entity_type, "ID": sheet_name, "Name": name, "FTE": fte,
                    "Month": col_dt if col_dt else header_val, 
                    "Total RVUs": col_sum, "RVU per FTE": col_sum / fte if fte > 0 else 0,
                    "Clinic_Tag": clinic_tag, "source_type": "standard",
                    "Month_Clean": col_dt
                })
        return pd.DataFrame(records)

    # --- SPECIFIC PARSER FOR CPT 77263 CONSULTS (FIXED DATE CHECK) ---
    def parse_consults_data(df, sheet_name, log, target_year=None):
        records = []
        try:
            header_row_idx = find_date_row(df)
            cpt_row_idx = -1
            for r in range(len(df)):
                row_val = str(df.iloc[r, 0]).strip()
                if CONSULT_CPT in row_val:
                    cpt_row_idx = r
                    log.append(f"    ✅ Found {CONSULT_CPT} in row {r} for {sheet_name}")
                    break
            
            if cpt_row_idx != -1:
                for col in df.columns[4:]: 
                    header_val = df.iloc[header_row_idx, col]
                    
                    is_valid_date = False
                    valid_date = None
                    if isinstance(header_val, (datetime, pd.Timestamp)): 
                         is_valid_date = True
                         valid_date = header_val
                    elif isinstance(header_val, str):
                        if re.match(r'(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)-\d{2}', header_val.strip(), re.IGNORECASE):
                            is_valid_date = True
                            try: valid_date = pd.to_datetime(header_val.strip(), format='%b-%y')
                            except: pass
                    
                    if not is_valid_date: continue 
                    if target_year and valid_date and valid_date.year != target_year: continue # Filter
                    
                    val = clean_number(df.iloc[cpt_row_idx, col])
                    if val is not None:
                        count = val / CONSULT_CONVERSION
                        records.append({
                            "Name": sheet_name, "Month": header_val, 
                            "Count": count, "Clinic_Tag": sheet_name
                        })
            else:
                log.append(f"    ❌ {CONSULT_CPT} NOT found in column A for {sheet_name}")

        except Exception as e:
            log.append(f"    ❌ Error parsing {sheet_name}: {str(e)}")
            
        return pd.DataFrame(records)

    def parse_visits_sheet(df, filename_date, clinic_tag="General", target_year=None):
        records = []
        # Filter: if target year set, skip file mismatch
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
                    log.append(f"  ✅ Found header at Row {r} (Dates detected: {len(date_map)})")
                    break
            
            if header_row_idx == -1: 
                log.append(f"  ❌ Could NOT find date headers in {filename}")
                return pd.DataFrame()

            for i in range(header_row_idx + 1, len(df)):
                row = df.iloc[i].values
                c_id = None
                site_name_found = ""
                for col_idx in range(3): 
                    if col_idx >= len(row): break
                    val = str(row[col_idx]).strip().upper()
                    if val and val != "NAN":
                        if val in POS_ROW_MAPPING:
                            c_id = POS_ROW_MAPPING[val]
                            site_name_found = val
                            break
                        for key, mapped_id in POS_ROW_MAPPING.items():
                            if key in val:
                                c_id = mapped_id
                                site_name_found = val
                                break
                    if c_id: break
                
                if c_id:
                    for col_idx, dt in date_map.items():
                        if target_year and dt.year != target_year: continue # Filter
                        if col_idx < len(row):
                            val = clean_number(row[col_idx])
                            if val is not None:
                                records.append({
                                    "Clinic_Tag": c_id, "Month_Clean": dt, "New Patients": val,
                                    "Month_Label": dt.strftime('%b-%y'), "source_type": "pos_trend"
                                })

        except Exception as e: 
            log.append(f"  ❌ Error parsing {filename}: {str(e)}")
            
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

    def process_files(file_objects):
        clinic_data = []; provider_data = []; visit_data = []; financial_data = []; pos_trend_data = []; consult_data = []; app_cpt_data = []; md_cpt_data = []; md_consult_data = []
        debug_log = []
        consult_log = [] 
        prov_log = [] 
        
        # --- RECURSIVE LOAD USING OS.WALK ---
        all_files_to_process = []
        if isinstance(file_objects[0], LocalFile):
             for root, dirs, files in os.walk(SERVER_DIR):
                for f in sorted(files):
                    if f.endswith(".xlsx") or f.endswith(".xls"):
                        all_files_to_process.append(LocalFile(os.path.join(root, f)))
        else:
             all_files_to_process = file_objects

        for file_obj in all_files_to_process:
            if isinstance(file_obj, LocalFile):
                filename = file_obj.name; xls = pd.read_excel(file_obj.path, sheet_name=None, header=None)
                full_path = file_obj.path
            else:
                filename = file_obj.name.upper(); xls = pd.read_excel(file_obj, sheet_name=None, header=None)
                full_path = filename
            
            # --- FOLDER-BASED YEAR FILTER ---
            target_year = get_target_year_from_text(full_path.upper())
            is_cpa = "CPA" in full_path.upper().split(os.sep) or "CPA" in filename
            
            # Ignore target year for CPA
            if is_cpa: target_year = None
            
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
                                 financial_data.append(pd.DataFrame([{
                                     "Name": "TN Proton Center", "Month_Clean": file_date,
                                     "Charges": chg, "Payments": pay, "Tag": "PROTON", "Mode": "Clinic",
                                     "Quarter": f"Q{file_date.quarter} {file_date.year}"
                                 }]))
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
                debug_log.append(f"📂 Processing New Patient File: {filename}")
                found_pos = False
                for sheet_name, df in xls.items():
                    if "POS" in sheet_name.upper() and "TREND" in sheet_name.upper():
                        found_pos = True
                        res = parse_pos_trend_sheet(df, filename, debug_log, target_year)
                        if not res.empty: 
                            pos_trend_data.append(res)
                            debug_log.append(f"  ✅ Extracted {len(res)} records from {sheet_name}")
                        else:
                            debug_log.append(f"  ⚠️ No records extracted from {sheet_name}")

                if not found_pos:
                     debug_log.append(f"  ❌ No 'POS ... Trend' sheet found in {filename}")

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
                
                # --- CHECK FOR PROVIDER SHEETS FOR DETAILED CPT ---
                match_prov = match_provider(clean_name)
                if match_prov:
                    # 1. Parse for APP CPTs
                    if match_prov in APP_LIST:
                        res_cpt = parse_app_cpt_data(df, match_prov, prov_log, target_year)
                        if not res_cpt.empty: app_cpt_data.append(res_cpt)
                    # 2. Parse for MD CPTs & 77263
                    else:
                        # Follow-up Visits (99212-99215)
                        res_cpt = parse_app_cpt_data(df, match_prov, prov_log, target_year)
                        if not res_cpt.empty: md_cpt_data.append(res_cpt)
                        
                        # NEW: Tx Plan (77263) for MDs
                        res_77263 = parse_consults_data(df, match_prov, consult_log, target_year)
                        if not res_77263.empty: md_consult_data.append(res_77263)

                
                if s_lower.endswith(" prov"):
                    file_date = get_date_from_filename(filename)
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
                    consult_log.append(f"Checking {clean_name} for 77263...")
                    res_consult = parse_consults_data(df, pretty_name, consult_log, target_year)
                    if not res_consult.empty:
                        consult_data.append(res_consult)
                    # Fall through to allow provider extraction if present!

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
                if not res.empty: 
                    provider_data.append(res)
                    prov_log.append(f"  ✅ Extracted provider data for {clean_name} ({len(res)} rows)")

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

        df_clinic = pd.concat(clinic_data, ignore_index=True) if clinic_data else pd.DataFrame()
        df_provider_raw = pd.concat(provider_data, ignore_index=True) if provider_data else pd.DataFrame()
        df_visits = pd.concat(visit_data, ignore_index=True) if visit_data else pd.DataFrame()
        df_financial = pd.concat(financial_data, ignore_index=True) if financial_data else pd.DataFrame()
        
        if pos_trend_data:
            df_pos_trend = pd.concat(pos_trend_data, ignore_index=True)
        else:
            df_pos_trend = pd.DataFrame(columns=['Clinic_Tag', 'Month_Clean', 'New Patients', 'Month_Label', 'source_type'])

        if consult_data:
            df_consults = pd.concat(consult_data, ignore_index=True)
            def parse_date_safe(x):
                if isinstance(x, (datetime, pd.Timestamp)): return x
                if isinstance(x, str):
                    try: return pd.to_datetime(x, format='%b-%y')
                    except: return pd.NaT
                return pd.NaT
            df_consults['Month_Clean'] = df_consults['Month'].apply(parse_date_safe)
            df_consults.dropna(subset=['Month_Clean'], inplace=True)
            df_consults['Month_Label'] = df_consults['Month_Clean'].dt.strftime('%b-%y')
        else:
             df_consults = pd.DataFrame(columns=['Name', 'Month', 'Count', 'Month_Label'])
        
        if md_consult_data:
            df_md_consults = pd.concat(md_consult_data, ignore_index=True)
            def parse_date_safe(x):
                if isinstance(x, (datetime, pd.Timestamp)): return x
                if isinstance(x, str):
                    try: return pd.to_datetime(x, format='%b-%y')
                    except: return pd.NaT
                return pd.NaT
            df_md_consults['Month_Clean'] = df_md_consults['Month'].apply(parse_date_safe)
            df_md_consults.dropna(subset=['Month_Clean'], inplace=True)
            df_md_consults['Month_Label'] = df_md_consults['Month_Clean'].dt.strftime('%b-%y')
        else:
             df_md_consults = pd.DataFrame(columns=['Name', 'Month', 'Count', 'Month_Label'])

        if app_cpt_data:
            df_app_cpt = pd.concat(app_cpt_data, ignore_index=True)
            def parse_date_safe(x):
                if isinstance(x, (datetime, pd.Timestamp)): return x
                if isinstance(x, str):
                    try: return pd.to_datetime(x, format='%b-%y')
                    except: return pd.NaT
                return pd.NaT
            df_app_cpt['Month_Clean'] = df_app_cpt['Month'].apply(parse_date_safe)
            df_app_cpt.dropna(subset=['Month_Clean'], inplace=True)
            df_app_cpt['Month_Label'] = df_app_cpt['Month_Clean'].dt.strftime('%b-%y')
        else:
            df_app_cpt = pd.DataFrame(columns=['Name', 'Month', 'Count', 'CPT Code', 'Month_Label'])

        if md_cpt_data:
            df_md_cpt = pd.concat(md_cpt_data, ignore_index=True)
            def parse_date_safe(x):
                if isinstance(x, (datetime, pd.Timestamp)): return x
                if isinstance(x, str):
                    try: return pd.to_datetime(x, format='%b-%y')
                    except: return pd.NaT
                return pd.NaT
            df_md_cpt['Month_Clean'] = df_md_cpt['Month'].apply(parse_date_safe)
            df_md_cpt.dropna(subset=['Month_Clean'], inplace=True)
            df_md_cpt['Month_Label'] = df_md_cpt['Month_Clean'].dt.strftime('%b-%y')
        else:
            df_md_cpt = pd.DataFrame(columns=['Name', 'Month', 'Count', 'CPT Code', 'Month_Label'])


        if not df_financial.empty:
            df_financial['Month_Clean'] = pd.to_datetime(df_financial['Month_Clean'], errors='coerce')
            df_financial.dropna(subset=['Month_Clean'], inplace=True)
            df_financial['Month_Label'] = df_financial['Month_Clean'].dt.strftime('%b-%y')

        if not df_provider_raw.empty:
            def parse_date_safe(x):
                if isinstance(x, (datetime, pd.Timestamp)): return x
                if isinstance(x, str):
                    try: return pd.to_datetime(x, format='%b-%y')
                    except: return pd.NaT
                return pd.NaT
            df_provider_raw['Month_Clean'] = df_provider_raw['Month'].apply(parse_date_safe)
            df_provider_raw.dropna(subset=['Month_Clean'], inplace=True)
            df_provider_raw['Month_Label'] = df_provider_raw['Month_Clean'].dt.strftime('%b-%y')
            df_provider_raw['Quarter'] = df_provider_raw['Month_Clean'].apply(lambda x: f"Q{pd.Timestamp(x).quarter} {pd.Timestamp(x).year}")

        if not df_clinic.empty:
            df_clinic['Month_Clean'] = pd.to_datetime(df_clinic['Month'], format='%b-%y', errors='coerce')
            mask = df_clinic['Month_Clean'].isna()
            if mask.any(): df_clinic.loc[mask, 'Month_Clean'] = pd.to_datetime(df_clinic.loc[mask, 'Month'], errors='coerce')
            df_clinic.dropna(subset=['Month_Clean'], inplace=True)
            df_clinic = df_clinic.groupby(['Name', 'ID', 'Month_Clean'], as_index=False).agg({
                'Total RVUs': 'sum', 'FTE': 'max', 'Month': 'first', 'Clinic_Tag': 'first'
            })
            df_clinic['RVU per FTE'] = df_clinic.apply(lambda x: x['Total RVUs'] / x['FTE'] if x['FTE'] > 0 else 0, axis=1)
            df_clinic['Quarter'] = df_clinic['Month_Clean'].apply(lambda x: f"Q{pd.Timestamp(x).quarter} {pd.Timestamp(x).year}")
            df_clinic.sort_values('Month_Clean', inplace=True)
            df_clinic['Month_Label'] = df_clinic['Month_Clean'].dt.strftime('%b-%y')

        df_provider_global = pd.DataFrame()
        if not df_provider_raw.empty:
            df_md_clean = df_provider_raw[df_provider_raw.get('source_type', 'standard') != 'detail'].copy()
            df_provider_global = df_md_clean.groupby(['Name', 'ID', 'Month_Clean'], as_index=False).agg({
                'Total RVUs': 'sum', 'FTE': 'max', 'Month': 'first', 'Quarter': 'first', 'Month_Label': 'first'
            })
            df_provider_global['RVU per FTE'] = df_provider_global.apply(lambda x: x['Total RVUs'] / x['FTE'] if x['FTE'] > 0 else 0, axis=1)
            df_provider_global.sort_values('Month_Clean', inplace=True)

        return df_clinic, df_provider_global, df_provider_raw, df_visits, df_financial, df_pos_trend, df_consults, df_app_cpt, df_md_cpt, df_md_consults, debug_log, consult_log, prov_log

    # --- UI ---
    st.title("🩺 Radiation Oncology Division Analytics")
    st.markdown("##### by Dr. Jones")
    st.markdown("---")

    server_files = []
    if os.path.exists(SERVER_DIR):
        for root, dirs, files in os.walk(SERVER_DIR):
            for f in sorted(files):
                if f.endswith(".xlsx") or f.endswith(".xls"):
                    server_files.append(LocalFile(os.path.join(root, f)))

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
            df_clinic, df_md_global, df_provider_raw, df_visits, df_financial, df_pos_trend, df_consults, df_app_cpt, df_md_cpt, df_md_consults, debug_log, consult_log, prov_log = process_files(all_files)
        
        with st.sidebar:
             with st.expander("🐞 Debug: MD/APP Data"):
                if prov_log:
                    for line in prov_log: st.write(line)
                else:
                    st.write("No provider data extracted.")

        if df_clinic.empty and df_md_global.empty and df_visits.empty and df_financial.empty and df_pos_trend.empty:
            st.error("No valid data found.")
        else:
            if not df_md_global.empty:
                df_apps = df_md_global[df_md_global['Name'].isin(APP_LIST)]
                valid_providers = set(PROVIDER_CONFIG.keys())
                df_mds = df_md_global[(df_md_global['Name'].isin(valid_providers)) & (~df_md_global['Name'].isin(APP_LIST))]
            else:
                df_apps = pd.DataFrame(); df_mds = pd.DataFrame()

            # --- SPLIT TABS ---
            tab_c_26, tab_c_25, tab_md_26, tab_md_25, tab_fin = st.tabs([
                "🏥 Clinic Analytics (2026)", 
                "🏥 Clinic Analytics (2025)",
                "👨‍⚕️ MD Analytics (2026)", 
                "👨‍⚕️ MD Analytics (2025)",
                "💰 Financials"
            ])
            
            # --- HELPER: RENDER CLINIC TAB ---
            def render_clinic_tab(df_full, year):
                df_year = df_full[df_full['Month_Clean'].dt.year == year] if not df_full.empty else pd.DataFrame()
                if df_year.empty:
                     st.info(f"No data available for {year}.")
                     return
                
                c1, c2 = st.columns([1,5])
                with c1:
                     view = st.radio(f"Select View ({year}):", ["All", "TriStar", "Ascension", "LROC", "TOPC", "TROC", "Sumner"], key=f"c_rad_{year}")
                
                with c2:
                     df_view = df_year.copy()
                     if view == "TriStar": df_view = df_view[df_view['ID'].isin(TRISTAR_IDS)]
                     elif view == "Ascension": df_view = df_view[df_view['ID'].isin(ASCENSION_IDS)]
                     elif view == "LROC": df_view = df_view[df_view['ID'] == 'LROC']
                     elif view == "TOPC": df_view = df_view[df_view['ID'] == 'TOPC']
                     elif view == "TROC": df_view = df_view[df_view['ID'] == 'TROC']
                     elif view == "Sumner": df_view = df_view[df_view['ID'] == 'Sumner']
                     
                     if not df_view.empty:
                         st.info(generate_narrative(df_view, "Clinic"))
                         
                         with st.container(border=True):
                             st.markdown(f"#### 📈 12-Month Trend ({year})")
                             fig = px.line(df_view.sort_values('Month_Clean'), x='Month_Clean', y='Total RVUs', color='Name', markers=True)
                             fig.update_layout(style_high_end_chart(fig).layout)
                             st.plotly_chart(fig, use_container_width=True)
                         
                         c1, c2 = st.columns(2)
                         with c1:
                             st.markdown(f"#### 🔢 Monthly Data ({year})")
                             piv = df_view.pivot_table(index="Name", columns="Month_Label", values="Total RVUs", aggfunc="sum").fillna(0)
                             sorted_m = df_view.sort_values("Month_Clean")["Month_Label"].unique()
                             piv = piv.reindex(columns=sorted_m).fillna(0)
                             piv["Total"] = piv.sum(axis=1)
                             st.dataframe(piv.style.format("{:,.0f}").background_gradient(cmap="Reds"))
                         with c2:
                             st.markdown(f"#### 📆 Quarterly Data ({year})")
                             piv_q = df_view.pivot_table(index="Name", columns="Quarter", values="Total RVUs", aggfunc="sum").fillna(0)
                             piv_q["Total"] = piv_q.sum(axis=1)
                             st.dataframe(piv_q.style.format("{:,.0f}").background_gradient(cmap="Oranges"))
                         
                         # PDF Export Button (Only in 2026/Current tab usually, but added here)
                         if FPDF:
                            with st.expander(f"📄 Export PDF ({year})"):
                                opts = sorted(df_view['Month_Clean'].unique(), reverse=True)
                                s_date = st.selectbox("Month", [d.strftime('%b-%y') for d in opts], key=f"pdf_{year}")
                                if st.button(f"Generate {s_date} PDF", key=f"btn_{year}"):
                                    t_date = pd.to_datetime(s_date, format='%b-%y')
                                    # Filter Logic
                                    if view == "All": pdf_view = df_clinic
                                    elif view == "TriStar": pdf_view = df_clinic[df_clinic['ID'].isin(TRISTAR_IDS)]
                                    elif view == "Ascension": pdf_view = df_clinic[df_clinic['ID'].isin(ASCENSION_IDS)]
                                    else: pdf_view = df_clinic # Fallback
                                    
                                    pdf_view_date = pdf_view[pdf_view['Month_Clean'] == t_date]
                                    
                                    if not pdf_view_date.empty:
                                        total_rvu = pdf_view_date['Total RVUs'].sum()
                                        avg_fte = pdf_view_date['FTE'].sum()
                                        rvu_fte = total_rvu / avg_fte if avg_fte > 0 else 0
                                        
                                        # Get New Patients (Approx)
                                        np_count = 0
                                        if not df_pos_trend.empty:
                                            np_data = df_pos_trend[(df_pos_trend['Month_Clean'] == t_date)]
                                            np_count = np_data['New Patients'].sum()

                                        # Get Provider Breakdown
                                        prov_breakdown = df_provider_raw[(df_provider_raw['Month_Clean'] == t_date)]
                                        
                                        pdf_bytes = create_clinic_pdf(f"{view} View", s_date, total_rvu, rvu_fte, np_count, prov_breakdown)
                                        st.download_button(f"Download {s_date} PDF", data=pdf_bytes, file_name=f"Report_{view}_{s_date}.pdf", mime='application/pdf')

            
            # --- HELPER: RENDER MD TAB ---
            def render_md_tab(df_full, year):
                df_year = df_full[df_full['Month_Clean'].dt.year == year] if not df_full.empty else pd.DataFrame()
                if df_year.empty:
                     st.info(f"No data available for {year}.")
                     return
                
                st.info(generate_narrative(df_year, "Physician"))
                
                with st.container(border=True):
                    st.markdown(f"#### 📅 Physician Productivity Trend ({year})")
                    fig = px.line(df_year.sort_values('Month_Clean'), x='Month_Clean', y='RVU per FTE', color='Name', markers=True)
                    st.plotly_chart(style_high_end_chart(fig), use_container_width=True)
                
                c1, c2 = st.columns(2)
                with c1:
                    piv = df_year.pivot_table(index="Name", columns="Month_Label", values="Total RVUs", aggfunc="sum").fillna(0)
                    sorted_m = df_year.sort_values("Month_Clean")["Month_Label"].unique()
                    piv = piv.reindex(columns=sorted_m).fillna(0)
                    piv["Total"] = piv.sum(axis=1)
                    st.dataframe(piv.sort_values("Total", ascending=False).style.format("{:,.0f}").background_gradient(cmap="Blues"))
                with c2:
                    piv_q = df_year.pivot_table(index="Name", columns="Quarter", values="Total RVUs", aggfunc="sum").fillna(0)
                    piv_q["Total"] = piv_q.sum(axis=1)
                    st.dataframe(piv_q.sort_values("Total", ascending=False).style.format("{:,.0f}").background_gradient(cmap="Purples"))

            # --- RENDER CONTENT ---
            with tab_c_26: render_clinic_tab(df_clinic, 2026)
            with tab_c_25: render_clinic_tab(df_clinic, 2025)
            with tab_md_26: render_md_tab(df_mds, 2026)
            with tab_md_25: render_md_tab(df_mds, 2025)
            
            with tab_fin:
                 if not df_financial.empty:
                     fin_agg = df_financial.groupby(['Name'])[['Charges', 'Payments']].sum().reset_index()
                     # ValueError Fix: Fill NaN with 0 before formatting
                     fin_agg = fin_agg.fillna(0)
                     st.dataframe(fin_agg.style.format({'Charges': '${:,.2f}', 'Payments': '${:,.2f}'}))
                 else:
                     st.info("No Financial data found.")

    else:
        st.info("👋 Ready. View Only Mode: Add files to 'Reports' folder in GitHub to update data.")
