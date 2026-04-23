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
            self.cell(0, 10, 'Radiation Oncology - Monthly Performance Report', 0, 1, 'C')
            self.ln(5)

        def footer(self):
            self.set_y(-15)
            self.set_font('Arial', 'I', 8)
            self.cell(0, 10, f'Page {self.page_no()}', 0, 0, 'C')

    def create_clinic_pdf(clinic_name, month_label, total_rvu, rvu_fte, new_patients, provider_df):
        pdf = PDFReport()
        pdf.add_page()
        pdf.set_font('Arial', 'B', 14)
        pdf.cell(0, 10, f"Scope: {clinic_name}", 0, 1, 'L')
        pdf.set_font('Arial', '', 12)
        pdf.cell(0, 10, f"Period: {month_label}", 0, 1, 'L')
        pdf.ln(5)
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
        pdf.set_font('Arial', 'B', 12)
        pdf.cell(0, 10, "Provider Breakdown", 1, 1, 'L', fill=True)
        pdf.set_font('Arial', 'B', 10)
        pdf.cell(90, 10, "Provider Name", 1, 0, 'C')
        pdf.cell(50, 10, "Total wRVUs", 1, 1, 'C')
        pdf.set_font('Arial', '', 10)
        if not provider_df.empty:
            for _, row in provider_df.iterrows():
                pdf.cell(90, 10, str(row['Name']), 1, 0)
                pdf.cell(50, 10, f"{row['Total RVUs']:,.2f}", 1, 1, 'R')
        else:
            pdf.cell(0, 10, "No individual provider data found for this period.", 1, 1)
        return pdf.output(dest='S').encode('latin-1')

# --- PASSWORD ---
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
        st.text_input("❌ Incorrect password. Try again:", type="password", on_change=password_entered, key="password")
        return False
    return True

# --- HISTORICAL DATA ---
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

    # ==========================================
    # CONFIGURATION
    # ==========================================
    CLINIC_CONFIG = {
        "CENT":       {"name": "Centennial",        "fte": 2.2},
        "Dickson":    {"name": "Horizon",            "fte": 1.0},
        "LROC":       {"name": "LROC (Lebanon)",     "fte": 1.2},
        "Skyline":    {"name": "Skyline",            "fte": 1.0},
        "Midtown":    {"name": "ST Midtown",         "fte": 1.8},
        "MURF":       {"name": "ST Rutherford",      "fte": 2.0},
        "STW":        {"name": "ST West",            "fte": 1.8},
        "Stonecrest": {"name": "StoneCrest",         "fte": 1.0},
        "Summit":     {"name": "Summit",             "fte": 1.0},
        "Sumner":     {"name": "Sumner",             "fte": 1.5},
        "TROC":       {"name": "TROC (Tullahoma)",   "fte": 0.6},
        "TOPC":       {"name": "TN Proton Center",   "fte": 2.5},
    }
    TRISTAR_IDS   = ["CENT", "Skyline", "Dickson", "Summit", "Stonecrest"]
    ASCENSION_IDS = ["STW", "Midtown", "MURF"]

    PROVIDER_CONFIG = {
        "Burke": 1.0, "Castle": 0.6, "Chen": 1.0, "Cohen": 1.0, "Collie": 1.0,
        "Cooper": 1.0, "Ellis": 1.0, "Escott": 1.0, "Friedman": 1.0,
        "Gray": 1.0, "Jones": 1.0, "Lee": 1.0, "Lewis": 1.0, "Lipscomb": 0.6,
        "Lydon": 1.0, "Mayo": 1.0, "Mondschein": 1.0, "Nguyen": 1.0,
        "Osborne": 1.0, "Phillips": 1.0, "Sidrys": 1.0, "Sittig": 1.0,
        "Strickler": 1.0, "Wakefield": 1.0, "Wendt": 1.0, "Whitaker": 1.0,
    }
    PROVIDER_KEYS_UPPER = {k.upper(): k for k in PROVIDER_CONFIG.keys()}
    APP_LIST = ["Burke", "Ellis", "Lewis", "Lydon"]

    TARGET_CATEGORIES = ["E&M OFFICE CODES", "RADIATION CODES", "SPECIAL PROCEDURES"]
    IGNORED_SHEETS   = ["RAD PHYSICIAN WORK RVUS", "COVER", "SHEET1", "TOTALS", "PROTON PHYSICIAN WORK RVUS"]
    SERVER_DIR       = "Reports"

    # CPT conversion rates for follow-up visit counting
    APP_CPT_RATES = {"99212": 0.7, "99213": 1.3, "99214": 1.92, "99215": 2.8}

    # Conversion factors for 77263 (wRVU value → procedure count)
    CONSULT_CONV = {2026: 3.06, "default": 3.14}

    # 2026 PC wRVU value for 77470 (Special Treatment Procedure) → procedure count
    CPT_77470_WRVU = 2.03

    POS_ROW_MAPPING = {
        "CENTENNIAL RAD":     "CENT",
        "DICKSON RAD":        "Dickson",
        "MIDTOWN RAD":        "Midtown",
        "MURFREESBORO RAD":   "MURF",
        "SAINT THOMAS WEST RAD": "STW",
        "SKYLINE RAD":        "Skyline",
        "STONECREST RAD":     "Stonecrest",
        "SUMMIT RAD":         "Summit",
        "SUMNER RAD":         "Sumner",
        "LEBANON RAD":        "LROC",
        "TULLAHOMA RADIATION":"TROC",
        "TO PROTON":          "TOPC",
    }

    class LocalFile:
        def __init__(self, path):
            self.path = path
            self.name = os.path.basename(path).upper()

    # ==========================================
    # UTILITY FUNCTIONS
    # ==========================================

    def standardize_date(x):
        """Normalize any date value to the 1st of its month as a Timestamp."""
        if pd.isna(x):
            return pd.NaT
        if isinstance(x, (datetime, pd.Timestamp)):
            return pd.Timestamp(year=x.year, month=x.month, day=1)
        if isinstance(x, str):
            x = x.strip()
            for fmt in ('%b-%y', '%b-%Y', '%B %Y', '%Y-%m-%d'):
                try:
                    return pd.Timestamp(pd.to_datetime(x, format=fmt)).replace(day=1)
                except Exception:
                    pass
            try:
                return pd.Timestamp(pd.to_datetime(x)).replace(day=1)
            except Exception:
                pass
        return pd.NaT

    def get_date_from_filename(filename):
        match = re.search(r'(JAN|FEB|MAR|APR|MAY|JUN|JUL|AUG|SEP|OCT|NOV|DEC)\s*(\d{2,4})', filename, re.IGNORECASE)
        if match:
            month_str, year_str = match.group(1), match.group(2)
            if len(year_str) == 2:
                year_str = "20" + year_str
            return pd.to_datetime(f"{month_str} {year_str}")
        return datetime.now()

    def get_target_year_from_text(text):
        """Extract the reporting year from a folder path or filename."""
        # Prefer month+year patterns first (most specific)
        match = re.search(r'(JAN|FEB|MAR|APR|MAY|JUN|JUL|AUG|SEP|OCT|NOV|DEC)\s*(20)?(\d{2})\b', text, re.IGNORECASE)
        if match:
            return int("20" + match.group(3)[-2:])
        # Fall back to bare 4-digit year
        match2 = re.search(r'\b(20[2-9]\d)\b', text)
        if match2:
            return int(match2.group(1))
        return None

    def clean_number(val):
        if pd.isna(val):
            return None
        try:
            s = str(val).strip()
            if s.startswith("(") and s.endswith(")"):
                s = "-" + s[1:-1]
            s = s.replace(',', '').replace('%', '').replace('$', '')
            if s in ("", "-"):
                return None
            return float(s)
        except Exception:
            return None

    def match_provider(name_str):
        """Return canonical provider last name if recognizable, else None."""
        try:
            if not isinstance(name_str, str):
                return None
            name_str = name_str.strip()
            if not name_str:
                return None
            # "Last, First" format
            base = name_str.split(",")[0].strip() if "," in name_str else name_str
            parts = base.split()
            if not parts:
                return None
            last = parts[0].upper()
            if last == "FRIEDMEN":
                last = "FRIEDMAN"
            return PROVIDER_KEYS_UPPER.get(last)
        except Exception:
            return None

    def clean_provider_name_display(name_str):
        m = match_provider(name_str)
        if m:
            return m
        base = name_str.split(",")[0].strip() if "," in name_str else name_str
        return base.split()[0] if base.split() else name_str

    def get_historical_df():
        records = []
        for year, data in HISTORICAL_DATA.items():
            for clinic_id, rvu in data.items():
                if clinic_id in CLINIC_CONFIG:
                    records.append({
                        "ID": clinic_id,
                        "Name": CLINIC_CONFIG[clinic_id]["name"],
                        "Year": int(year),
                        "Total RVUs": float(rvu),
                    })
        return pd.DataFrame(records)

    def get_consult_conv(target_year):
        return CONSULT_CONV.get(target_year, CONSULT_CONV["default"])

    # ==========================================
    # FIND DATE HEADER ROW  (FIX #1)
    # Returns the INTEGER row *position* (for iloc) of the best date header.
    # ==========================================
    def find_date_row(df):
        months = ["JAN","FEB","MAR","APR","MAY","JUN","JUL","AUG","SEP","OCT","NOV","DEC"]
        best_pos, max_score = 1, 0
        for r in range(min(10, len(df))):
            row_vals = df.iloc[r, 4:16]
            str_vals  = [str(v).upper() for v in row_vals if pd.notna(v)]
            text_hits = sum(1 for v in str_vals if any(m in v for m in months))
            dt_hits   = sum(1 for v in row_vals if isinstance(v, (datetime, pd.Timestamp)))
            score     = text_hits + dt_hits * 2
            if score > max_score:
                max_score = score
                best_pos  = r
        return best_pos   # positional index, safe for iloc

    # ==========================================
    # PARSERS
    # ==========================================

    def parse_rvu_sheet(df, sheet_name, entity_type, clinic_tag="General", forced_fte=None, target_year=None):
        """
        Parse a standard RVU sheet (clinic or provider).
        FIX #1 applied: uses iloc with positional column index via enumerate.
        """
        if entity_type == 'clinic':
            cfg  = CLINIC_CONFIG.get(sheet_name, {"name": sheet_name, "fte": 1.0})
            name = cfg['name']
            fte  = cfg['fte']
        else:
            name = sheet_name
            fte  = forced_fte if forced_fte else PROVIDER_CONFIG.get(sheet_name, 1.0)

        df = df.copy()
        df.iloc[:, 0] = df.iloc[:, 0].astype(str).str.strip().str.upper()
        mask      = df.iloc[:, 0].isin(TARGET_CATEGORIES)
        data_rows = df[mask].copy()

        header_pos = find_date_row(df)   # positional row index
        records    = []
        ncols      = len(df.columns)

        # FIX #1: iterate by positional column index (not label)
        for col_pos in range(4, ncols):
            dt_clean = standardize_date(df.iloc[header_pos, col_pos])
            if pd.isna(dt_clean):
                continue
            if target_year and dt_clean.year != target_year:
                continue
            col_sum = pd.to_numeric(data_rows.iloc[:, col_pos], errors='coerce').sum()
            records.append({
                "Type":       entity_type,
                "ID":         sheet_name,
                "Name":       name,
                "FTE":        fte,
                "Month_Clean": dt_clean,
                "Total RVUs": col_sum,
                "RVU per FTE": col_sum / fte if fte > 0 else 0,
                "Clinic_Tag": clinic_tag,
                "source_type": "standard",
            })
        return pd.DataFrame(records)

    def parse_app_cpt_data(df, provider_name, log, target_year=None):
        """
        Parse follow-up CPT codes (99212-99215) from a provider sheet.
        FIX #1 applied: positional column indexing via iloc.
        """
        records    = []
        header_pos = find_date_row(df)
        ncols      = len(df.columns)

        for cpt_code, rate in APP_CPT_RATES.items():
            cpt_row_pos = -1
            for r in range(len(df)):
                if str(df.iloc[r, 0]).strip().startswith(cpt_code):
                    cpt_row_pos = r
                    break
            if cpt_row_pos == -1:
                continue

            # FIX #1: iterate positionally
            for col_pos in range(4, ncols):
                dt_clean = standardize_date(df.iloc[header_pos, col_pos])
                if pd.isna(dt_clean):
                    continue
                if target_year and dt_clean.year != target_year:
                    continue
                val = clean_number(df.iloc[cpt_row_pos, col_pos])
                if val is not None and val != 0:
                    records.append({
                        "Name":        provider_name,
                        "Month_Clean": dt_clean,
                        "Count":       val / rate,
                        "CPT Code":    cpt_code,
                        "Rate":        rate,
                    })
        return pd.DataFrame(records)

    def parse_consults_data(df, sheet_name, log, target_year=None):
        """
        Parse CPT 77263 (Tx Plan Complex) from a sheet.
        The raw cell value is a wRVU amount; divide by conversion factor to get count.
        FIX #1: positional column indexing.
        """
        records = []
        try:
            conv = get_consult_conv(target_year)

            # Find the 77263 row
            col0 = df.iloc[:, 0].astype(str).str.strip()
            cpt_matches = df.index[col0.str.contains("77263", na=False)].tolist()
            if not cpt_matches:
                return pd.DataFrame()
            cpt_row_pos = cpt_matches[0]

            # Find date header row (checking rows 0 and 1)
            header_pos = 1
            for r_idx in [0, 1]:
                sample = df.iloc[r_idx, 4:10].astype(str).str.upper().tolist()
                if any(re.search(r'[A-Z]{3}-\d{2}', v) for v in sample):
                    header_pos = r_idx
                    break

            ncols = len(df.columns)
            for col_pos in range(4, ncols):
                header_val = str(df.iloc[header_pos, col_pos]).strip()
                if not re.search(r'^[A-Za-z]{3}-\d{2}$', header_val):
                    continue
                dt_clean = standardize_date(header_val)
                if pd.isna(dt_clean):
                    continue
                if target_year and dt_clean.year != target_year:
                    continue
                raw_val = clean_number(df.iloc[cpt_row_pos, col_pos])
                if raw_val is not None and raw_val > 0:
                    records.append({
                        "Name":        sheet_name,
                        "Month_Clean": dt_clean,
                        "Count":       raw_val / conv,
                    })
        except Exception as e:
            log.append(f"Error parsing 77263 for {sheet_name}: {e}")
        return pd.DataFrame(records)

    def parse_77470_data(df, sheet_name, log, target_year=None):
        """Parse CPT 77470 from a provider sheet; divide raw wRVU by CPT_77470_WRVU to get count."""
        SKIP_KEYWORDS = ["YTD", "12 MONTH", "12M", "AVG", "AVERAGE"]
        records = []
        try:
            col0 = df.iloc[:, 0].astype(str).str.strip()
            cpt_matches = df.index[col0.str.contains("77470", na=False)].tolist()
            if not cpt_matches:
                return pd.DataFrame()
            cpt_row_pos = cpt_matches[0]

            # Detect date header row — handles both string ("Jan-26") and
            # datetime objects (Excel date cells read as datetime by xlrd).
            header_pos = 1
            for r_idx in [0, 1]:
                raw_row = df.iloc[r_idx, 2:14].tolist()
                has_text_dt = any(re.search(r'[A-Za-z]{3}-\d{2}', str(v)) for v in raw_row)
                has_obj_dt  = any(isinstance(v, (datetime, pd.Timestamp)) for v in raw_row)
                if has_text_dt or has_obj_dt:
                    header_pos = r_idx
                    break

            # Walk every column; use standardize_date to handle string OR
            # datetime header values uniformly.
            ncols = len(df.columns)
            for col_pos in range(2, ncols):
                raw_hdr = df.iloc[header_pos, col_pos]
                hdr_str = str(raw_hdr).strip().upper()
                if any(kw in hdr_str for kw in SKIP_KEYWORDS):
                    continue
                dt_clean = standardize_date(raw_hdr)
                if pd.isna(dt_clean):
                    continue
                if target_year and dt_clean.year != target_year:
                    continue
                raw_val = clean_number(df.iloc[cpt_row_pos, col_pos])
                if raw_val is not None and raw_val > 0:
                    records.append({
                        "Name":        sheet_name,
                        "Month_Clean": dt_clean,
                        "Count":       raw_val / CPT_77470_WRVU,
                    })
        except Exception as e:
            log.append(f"Error parsing 77470 for {sheet_name}: {e}")
        return pd.DataFrame(records)

    def parse_detailed_prov_sheet(df, filename_date, clinic_id, log, target_year=None):
        """
        Parse a '*Prov' clinic sheet.

        Confirmed sheet structure (from TNONC_MAR26_ME_RAD_POS_Work_RVUS.xls):
          Row 1 : Clinic name (e.g. "Dickson Rad") in col A — SKIP
          Row 2 : blank
          Row 3 : Provider name (e.g. "Cohen MD, Brad R") in col C;
                  date headers start at col B:
                  [Mar-25 | 2025 YTD | Apr-25 | May-25 | ... | Mar-26 | 12 Month | % | AVG | 2026 YTD]
          Row 4 : "E&M OFFICE CODES"  ← section HEADER (no values) — SKIP
          Rows 5-6: individual CPT lines
          Row 7 : "E&M OFFICE CODES"  ← SUBTOTAL row  ← USE THIS
          Row 8 : "RADIATION CODES"   ← section HEADER — SKIP
          Rows 9-21: individual CPT lines
          Row 22: "RADIATION CODES"   ← SUBTOTAL row  ← USE THIS
          Row 23: "SPECIAL PROCEDURES" header — SKIP  (may be absent for some providers)
          ...
          Row N : "SPECIAL PROCEDURES" SUBTOTAL ← USE THIS (if present)
          Row N+1: blank / next provider header

        Strategy:
          1. Scan first ~5 rows for the date header row (contains "Mar-25", "Apr-25" etc).
             Build date_map: col_pos → Timestamp, skipping YTD/cumulative columns
             (identified by containing "YTD", "12 Month", "%", "AVG" in their header cell).
          2. Walk all rows:
             - Provider name detected in any of cols 0-4 → start new provider section.
             - Category label row seen for the SECOND time for this provider
               → this is the SUBTOTAL row → accumulate its values into monthly_accum.
             - First occurrence of category label → section header, skip.
          3. When a new provider starts (or EOF), flush accumulated monthly totals
             as individual records (one per month column with non-zero value).
        """
        records = []
        TARGET_TERMS = ["E&M OFFICE CODES", "RADIATION CODES", "SPECIAL PROCEDURES"]

        # ── Step 1: Find the date header row and build date_map ──────────────
        # Columns to SKIP even if they parse as dates (cumulative / summary cols)
        SKIP_KEYWORDS = ["YTD", "12 MONTH", "12M", "AVG", "AVERAGE"]

        date_map    = {}   # col_pos → Timestamp  (monthly actuals only)
        header_row  = -1

        for r in range(min(10, len(df))):
            row = df.iloc[r].values
            tmp = {}
            for c_pos in range(len(row)):
                cell = str(row[c_pos]).strip()
                # Skip blank / NaN
                if not cell or cell.upper() == "NAN":
                    continue
                # Skip summary columns by keyword
                if any(kw in cell.upper() for kw in SKIP_KEYWORDS):
                    continue
                # Check for Mon-YY pattern
                if re.match(r'^(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)-\d{2}$',
                            cell, re.IGNORECASE):
                    dt = standardize_date(cell)
                    if pd.notna(dt):
                        if target_year and dt.year != target_year:
                            continue
                        tmp[c_pos] = dt
            if len(tmp) >= 2:          # need at least 2 month columns to be confident
                date_map   = tmp
                header_row = r
                break

        if not date_map:
            # Fallback: use filename date and column 19
            file_dt = standardize_date(filename_date)
            if target_year and pd.notna(file_dt) and file_dt.year != target_year:
                return pd.DataFrame()
            date_map = {19: file_dt}

        # ── Step 2: Walk rows ────────────────────────────────────────────────
        current_provider = None
        term_counts  = {t: 0 for t in TARGET_TERMS}   # how many times each label seen
        monthly_accum = {c: 0.0 for c in date_map}

        def flush_provider():
            if current_provider is None:
                return
            for col_pos, dt in date_map.items():
                total = monthly_accum.get(col_pos, 0.0)
                if total != 0.0:
                    records.append({
                        "Type":        "provider",
                        "ID":          clinic_id,
                        "Name":        current_provider,
                        "FTE":         1.0,
                        "Month_Clean": dt,
                        "Total RVUs":  total,
                        "RVU per FTE": total,
                        "Clinic_Tag":  clinic_id,
                        "source_type": "detail",
                    })

        for i in range(len(df)):
            row       = df.iloc[i].values
            row_label = str(row[0]).upper().strip()

            if i == header_row:
                # The date-header row often doubles as the first "E&M OFFICE CODES"
                # label for the first provider.  Count the label so the subtotal row
                # (the second occurrence) is captured correctly; don't extract values.
                if current_provider is not None:
                    for term in TARGET_TERMS:
                        if term in row_label:
                            term_counts[term] += 1
                            break
                continue

            # ── Provider name detection: check cols 0-4 ──────────────────────
            potential_name = None
            for c in range(min(5, len(row))):
                m = match_provider(str(row[c]).strip())
                if m:
                    potential_name = m
                    break

            if potential_name:
                flush_provider()
                current_provider = potential_name
                term_counts   = {t: 0 for t in TARGET_TERMS}
                monthly_accum = {c: 0.0 for c in date_map}
                continue

            if current_provider is None:
                continue

            # ── Category label detection ──────────────────────────────────────
            matched_term = None
            for term in TARGET_TERMS:
                if term in row_label:
                    matched_term = term
                    break

            if matched_term is None:
                continue

            term_counts[matched_term] += 1

            if term_counts[matched_term] == 2:
                # SECOND occurrence = SUBTOTAL row → these are the monthly actuals
                for col_pos in date_map:
                    if col_pos < len(row):
                        val = clean_number(row[col_pos])
                        if val is not None:
                            monthly_accum[col_pos] += val
            # FIRST occurrence = section header row (no values) → skip
            # 3rd+ occurrence = shouldn't happen but skip anyway

        flush_provider()
        return pd.DataFrame(records)

    def parse_visits_sheet(df, filename_date, clinic_tag="General", target_year=None):
        records = []
        file_dt = standardize_date(filename_date)
        if target_year and pd.notna(file_dt) and file_dt.year != target_year:
            return pd.DataFrame()
        try:
            for i in range(4, len(df)):
                row = df.iloc[i].values
                row_check = " ".join(str(x).upper() for x in row[:5])
                if any(kw in row_check for kw in ("TOTAL", "PAGE", "DATE")):
                    continue
                matched_name = None
                for c in range(min(10, len(row))):
                    matched_name = match_provider(str(row[c]).strip())
                    if matched_name:
                        break
                if not matched_name:
                    continue
                numbers = [n for n in (clean_number(v) for v in row) if n is not None]
                visits = visits_diff = new_patients = np_diff = 0
                if len(numbers) >= 6:
                    visits, visits_diff, _, new_patients, np_diff = numbers[:5]
                elif len(numbers) >= 4:
                    visits, visits_diff, _, new_patients = numbers[:4]
                elif len(numbers) == 3:
                    visits, _, new_patients = numbers
                elif len(numbers) == 2:
                    visits, new_patients = numbers
                elif len(numbers) == 1:
                    visits = numbers[0]
                records.append({
                    "Name":         matched_name,
                    "Month_Clean":  file_dt,
                    "Total Visits": visits,
                    "Visits_Diff":  visits_diff,
                    "New Patients": new_patients,
                    "NP_Diff":      np_diff,
                    "Clinic_Tag":   clinic_tag,
                })
        except Exception:
            return pd.DataFrame()
        return pd.DataFrame(records)

    def parse_financial_sheet(df, filename_date, tag, mode="Provider"):
        records = []
        try:
            header_row, col_map = -1, {}
            for i in range(min(15, len(df))):
                row_vals = [str(x).upper().strip() for x in df.iloc[i].values]
                if mode == "Provider" and "PROVIDER" in row_vals:
                    header_row = i
                    for idx, val in enumerate(row_vals):
                        if "PROVIDER" in val:       col_map['name']     = idx
                        elif "CHARGES" in val and "TOTAL" in val:  col_map['charges'] = idx
                        elif "PAYMENT" in val and "TOTAL" in val:  col_map['payments'] = idx
                    break
                elif mode == "Clinic" and ("SITE" in row_vals or "TOTAL" in row_vals):
                    header_row = i
                    for idx, val in enumerate(row_vals):
                        if "SITE" in val:      col_map['name']     = idx
                        elif "CHARGES" in val: col_map['charges']  = idx
                        elif "PAYMENTS" in val: col_map['payments'] = idx
                    break
            if header_row == -1 or not col_map:
                return pd.DataFrame()
            file_dt = standardize_date(filename_date)
            for i in range(header_row + 1, len(df)):
                row       = df.iloc[i].values
                name_val  = str(row[col_map.get('name', 0)]).strip()
                if mode == "Clinic":
                    if tag in ["LROC", "TROC", "PROTON"] and "TOTAL" not in name_val.upper():
                        continue
                    if tag == "General":
                        whitelist = ["CENTENNIAL","DICKSON","MIDTOWN","MURFREESBORO","PROTON","WEST","SKYLINE","STONECREST","SUMMIT","SUMNER","TULLAHOMA"]
                        if not any(w in name_val.upper() for w in whitelist):
                            continue
                charges  = clean_number(row[col_map.get('charges',  1)]) or 0
                payments = clean_number(row[col_map.get('payments', 2)]) or 0
                if mode == "Provider":
                    clean_name = match_provider(name_val)
                    if not clean_name and "TOTAL" in name_val.upper() and tag == "PROTON":
                        pass
                    elif not clean_name:
                        continue
                else:
                    clean_name = name_val.replace(" Rad", "").strip()
                    if "TOTAL" in clean_name.upper():
                        clean_name = "TN Proton Center" if tag == "PROTON" else f"{tag} Total"
                    if "STONECREST" in clean_name.upper():
                        clean_name = "Stonecrest"
                records.append({
                    "Name":        clean_name,
                    "Month_Clean": file_dt,
                    "Charges":     charges,
                    "Payments":    payments,
                    "Tag":         tag,
                    "Mode":        mode,
                })
        except Exception:
            pass
        return pd.DataFrame(records)

    def parse_pos_trend_sheet(df, filename, log, target_year=None):
        records = []
        try:
            header_row_pos, date_map = -1, {}
            for r in range(min(30, len(df))):
                tmp = {}
                for c in range(len(df.columns)):
                    dt = standardize_date(df.iloc[r, c])
                    if pd.notna(dt):
                        tmp[c] = dt
                if len(tmp) >= 2:
                    header_row_pos = r
                    date_map       = tmp
                    break
            if header_row_pos == -1:
                return pd.DataFrame()
            for i in range(header_row_pos + 1, len(df)):
                row  = df.iloc[i].values
                c_id = None
                for col_idx in range(3):
                    if col_idx >= len(row):
                        break
                    val = str(row[col_idx]).strip().upper()
                    if not val or val == "NAN":
                        continue
                    if val in POS_ROW_MAPPING:
                        c_id = POS_ROW_MAPPING[val]
                        break
                    for key, mapped_id in POS_ROW_MAPPING.items():
                        if key in val:
                            c_id = mapped_id
                            break
                    if c_id:
                        break
                if c_id:
                    for col_pos, dt in date_map.items():
                        if target_year and dt.year != target_year:
                            continue
                        if col_pos < len(row):
                            val = clean_number(row[col_pos])
                            if val is not None:
                                records.append({
                                    "Clinic_Tag":  c_id,
                                    "Month_Clean": dt,
                                    "New Patients": val,
                                    "source_type": "pos_trend",
                                })
        except Exception as e:
            log.append(f"POS trend error: {e}")
        return pd.DataFrame(records)

    def get_clinic_id_from_sheet(sheet_name):
        s = sheet_name.lower().replace(" prov", "").replace(" rad", "").strip()
        for cid, cfg in CLINIC_CONFIG.items():
            if s in cfg['name'].lower() or s == cid.lower():
                return cid
        mapping = {
            "horizon": "Dickson", "dickson": "Dickson",
            "centennial": "CENT",
            "midtown": "Midtown",
            "rutherford": "MURF", "murfreesboro": "MURF",
            "west": "STW", "saint thomas": "STW",
            "lebanon": "LROC",
            "tullahoma": "TROC",
            "to proton": "TOPC",
        }
        for key, cid in mapping.items():
            if key in s:
                return cid
        return None

    # ==========================================
    # DEDUPLICATION HELPER
    # ==========================================
    def safe_dedup_and_format(df_list, subset_cols):
        if not df_list:
            return pd.DataFrame()
        df = pd.concat(df_list, ignore_index=True)
        if 'Month_Clean' in df.columns:
            df['Month_Clean'] = df['Month_Clean'].apply(standardize_date)
            df = df.dropna(subset=['Month_Clean'])
            df = df.sort_values('Month_Clean', ascending=False)
        valid_subset = [c for c in subset_cols if c in df.columns]
        if valid_subset:
            df = df.drop_duplicates(subset=valid_subset, keep='first')
        if not df.empty and 'Month_Clean' in df.columns:
            df['Month_Label'] = df['Month_Clean'].dt.strftime('%b-%y')
            if 'Quarter' not in df.columns:
                df['Quarter'] = df['Month_Clean'].apply(lambda x: f"Q{x.quarter} {x.year}")
        return df

    # ==========================================
    # FILE PROCESSING
    # ==========================================
    def process_files(file_objects):
        # Walk server folder if using LocalFile objects
        if file_objects and isinstance(file_objects[0], LocalFile):
            all_paths = sorted([
                os.path.join(root, f)
                for root, _, files in os.walk(SERVER_DIR)
                for f in files if f.endswith((".xlsx", ".xls"))
            ])
            all_files_to_process = [LocalFile(p) for p in all_paths]
        else:
            all_files_to_process = file_objects

        clinic_data = []; provider_data = []; visit_data = []
        financial_data = []; pos_trend_data = []; consult_data = []
        app_cpt_data = []; md_cpt_data = []; md_consult_data = []; md_77470_data = []
        debug_log = []; consult_log = []; prov_log = []

        for file_obj in all_files_to_process:
            if isinstance(file_obj, LocalFile):
                filename  = file_obj.name
                full_path = file_obj.path
                xls       = pd.read_excel(file_obj.path, sheet_name=None, header=None)
            else:
                filename  = file_obj.name.upper()
                full_path = filename
                xls       = pd.read_excel(file_obj, sheet_name=None, header=None)

            target_year = get_target_year_from_text(full_path)
            is_cpa = ("CPA" in full_path.upper().split(os.sep)) or ("CPA" in filename)
            if is_cpa:
                target_year = None

            file_date = get_date_from_filename(filename)
            file_tag  = "General"
            if "LROC"  in filename: file_tag = "LROC"
            elif "TROC" in filename: file_tag = "TROC"
            elif "PROTON" in filename or "TOPC" in filename: file_tag = "TOPC"

            # --- CPA FILES ---
            if is_cpa:
                for sheet_name, df in xls.items():
                    if "RAD BY PROVIDER" in filename:
                        res = parse_financial_sheet(df, file_date, "RAD", mode="Provider")
                        if not res.empty: financial_data.append(res)
                    elif "PROTON" in filename and "PROVIDER" in filename:
                        res = parse_financial_sheet(df, file_date, "PROTON", mode="Provider")
                        if not res.empty: financial_data.append(res)
                        try:
                            total_row = df[df.iloc[:, 1].astype(str).str.contains("Total", case=False, na=False)]
                            if not total_row.empty:
                                chg = clean_number(total_row.iloc[0, 2])
                                pay = clean_number(total_row.iloc[0, 3])
                                financial_data.append(pd.DataFrame([{
                                    "Name": "TN Proton Center", "Month_Clean": standardize_date(file_date),
                                    "Charges": chg, "Payments": pay, "Tag": "PROTON", "Mode": "Clinic"
                                }]))
                        except Exception:
                            pass
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

            # --- NEW PATIENT FILES ---
            if "NEW" in filename and ("PATIENT" in filename or "PT" in filename):
                file_date = get_date_from_filename(filename)
                debug_log.append(f"📂 New Patient File: {filename}")
                found_pos = False
                for sheet_name, df in xls.items():
                    if "POS" in sheet_name.upper() and "TREND" in sheet_name.upper():
                        found_pos = True
                        res = parse_pos_trend_sheet(df, filename, debug_log, target_year)
                        if not res.empty:
                            pos_trend_data.append(res)
                visit_tag = "LROC" if "LROC" in filename else ("TROC" if "TROC" in filename else ("TOPC" if "PROTON" in filename else "General"))
                for sheet_name, df in xls.items():
                    if "PHYS YTD OV" in sheet_name.upper():
                        res = parse_visits_sheet(df, file_date, clinic_tag=visit_tag, target_year=target_year)
                        if not res.empty: visit_data.append(res)
                continue

            # --- STANDARD RVU/PROVIDER FILES ---
            for sheet_name, df in xls.items():
                s_upper = sheet_name.upper()
                s_lower = sheet_name.strip().lower()
                clean_name = sheet_name.strip()

                # Skip trend sheets that aren't productivity trends
                if "TREND" in s_upper and "PRODUCTIVITY TREND" not in s_upper:
                    continue

                # Check if the sheet name is itself a provider name
                match_prov = match_provider(clean_name)
                if match_prov:
                    if match_prov in APP_LIST:
                        res = parse_app_cpt_data(df, match_prov, prov_log, target_year)
                        if not res.empty: app_cpt_data.append(res)
                    else:
                        res_cpt = parse_app_cpt_data(df, match_prov, prov_log, target_year)
                        if not res_cpt.empty: md_cpt_data.append(res_cpt)
                        res_77263 = parse_consults_data(df, match_prov, consult_log, target_year)
                        if not res_77263.empty: md_consult_data.append(res_77263)
                        res_77470 = parse_77470_data(df, match_prov, consult_log, target_year)
                        if not res_77470.empty: md_77470_data.append(res_77470)

                # Clinic-level detail sheets (e.g. "Centennial Prov")
                if s_lower.endswith(" prov"):
                    c_id = get_clinic_id_from_sheet(sheet_name)
                    if c_id:
                        res = parse_detailed_prov_sheet(df, file_date, c_id, prov_log, target_year)
                        if not res.empty: provider_data.append(res)
                    elif "sumner" in s_lower:
                        res = parse_detailed_prov_sheet(df, file_date, "Sumner", prov_log, target_year)
                        if not res.empty: provider_data.append(res)
                    continue

                if any(ign in s_upper for ign in IGNORED_SHEETS):
                    continue

                # Clinic-level sheets (sheet name matches a clinic ID)
                if clean_name in CLINIC_CONFIG:
                    res = parse_rvu_sheet(df, clean_name, 'clinic', clinic_tag="General", target_year=target_year)
                    if not res.empty: clinic_data.append(res)
                    pretty_name = CLINIC_CONFIG[clean_name]["name"]
                    res_consult = parse_consults_data(df, pretty_name, consult_log, target_year)
                    if not res_consult.empty: consult_data.append(res_consult)
                    # Fall through to also extract any provider rows below

                if "PRODUCTIVITY TREND" in s_upper:
                    if file_tag in ["LROC", "TROC"]:
                        res = parse_rvu_sheet(df, file_tag, 'clinic', clinic_tag=file_tag, target_year=target_year)
                        if not res.empty: clinic_data.append(res)
                        pretty_name = CLINIC_CONFIG[file_tag]["name"]
                        res_consult = parse_consults_data(df, pretty_name, consult_log, target_year)
                        if not res_consult.empty: consult_data.append(res_consult)
                    continue

                if "PROTON" in s_upper and file_tag == "TOPC":
                    continue
                if "PROTON POS" in s_upper:
                    continue
                if clean_name.upper() == "FRIEDMEN":
                    clean_name = "Friedman"

                # Provider-level sheets
                res = parse_rvu_sheet(df, clean_name, 'provider', clinic_tag=file_tag, target_year=target_year)
                if not res.empty:
                    provider_data.append(res)
                    prov_log.append(f"  ✅ {clean_name} ({len(res)} rows)")

            # Build TOPC clinic roll-up from individual proton provider sheets
            if file_tag == "TOPC":
                proton_prov_temp = []
                for sheet_name, df in xls.items():
                    s_upper = sheet_name.upper()
                    if "PROV" in s_upper: continue
                    if any(ign in s_upper for ign in IGNORED_SHEETS): continue
                    if "PROTON POS" in s_upper or "TREND" in s_upper: continue
                    cn = sheet_name.strip()
                    if cn.upper() == "FRIEDMEN": cn = "Friedman"
                    res = parse_rvu_sheet(df, cn, 'provider', clinic_tag="TOPC", target_year=target_year)
                    if not res.empty: proton_prov_temp.append(res)
                if proton_prov_temp:
                    comb = pd.concat(proton_prov_temp)
                    comb['Month_Clean'] = pd.to_datetime(comb['Month_Clean'], errors='coerce')
                    grp = comb.groupby('Month_Clean', as_index=False)[['Total RVUs', 'FTE']].sum()
                    topc_records = []
                    for _, row in grp.iterrows():
                        topc_records.append({
                            "Type": "clinic", "ID": "TOPC", "Name": "TN Proton Center",
                            "FTE": row['FTE'], "Month_Clean": row['Month_Clean'],
                            "Total RVUs": row['Total RVUs'],
                            "RVU per FTE": row['Total RVUs'] / row['FTE'] if row['FTE'] > 0 else 0,
                            "Clinic_Tag": "TOPC", "source_type": "standard",
                        })
                    clinic_data.append(pd.DataFrame(topc_records))

        # --- DEDICATED 77470 SCAN ---
        # Explicitly walk every sheet in every file, scan column 0 for the
        # "77470" row, then read across for the relevant month columns.
        scan_77470_log = []
        for file_obj_77 in all_files_to_process:
            if isinstance(file_obj_77, LocalFile):
                fn_77 = file_obj_77.name
                fp_77 = file_obj_77.path
                yr_77 = get_target_year_from_text(fp_77)
            else:
                fn_77 = file_obj_77.name.upper()
                fp_77 = file_obj_77
                yr_77 = get_target_year_from_text(fn_77)
            if ("CPA" in fn_77) or ("NEW" in fn_77 and ("PATIENT" in fn_77 or "PT" in fn_77)):
                continue
            try:
                xls_77 = pd.read_excel(fp_77, sheet_name=None, header=None)
            except Exception as e_77:
                scan_77470_log.append(f"READ_FAIL {fn_77}: {e_77}")
                continue
            for sn_77, sdf_77 in xls_77.items():
                su_77 = sn_77.upper()
                if "TREND" in su_77 and "PRODUCTIVITY TREND" not in su_77:
                    continue
                if any(ign in su_77 for ign in IGNORED_SHEETS):
                    continue
                prov_77 = match_provider(sn_77.strip())
                if not prov_77 or prov_77 in APP_LIST:
                    continue
                r_77 = parse_77470_data(sdf_77, prov_77, consult_log, yr_77)
                if not r_77.empty:
                    md_77470_data.append(r_77)
                    scan_77470_log.append(f"OK {fn_77}|{sn_77}: {len(r_77)} records yr={yr_77}")
                else:
                    scan_77470_log.append(f"EMPTY {fn_77}|{sn_77} yr={yr_77}")

        # --- DEDUPLICATION ---
        df_clinic    = safe_dedup_and_format(clinic_data,    ['Name', 'Month_Clean', 'ID'])
        df_visits    = safe_dedup_and_format(visit_data,     ['Name', 'Month_Clean', 'Clinic_Tag'])
        df_financial = safe_dedup_and_format(financial_data, ['Name', 'Month_Clean', 'Mode'])
        df_pos_trend = safe_dedup_and_format(pos_trend_data, ['Clinic_Tag', 'Month_Clean'])

        # Provider dedup: detail records (from *Prov sheets) contain per-month
        # values extracted from the date header, so each month is a separate row.
        # We keep the LAST-written value per Name+Month+Clinic_Tag+source_type
        # (ascending sort means later files overwrite earlier ones for the same month).
        if provider_data:
            all_prov = pd.concat(provider_data, ignore_index=True)
            all_prov['Month_Clean'] = all_prov['Month_Clean'].apply(standardize_date)
            all_prov = all_prov.dropna(subset=['Month_Clean'])
            all_prov['Month_Label'] = all_prov['Month_Clean'].dt.strftime('%b-%y')
            if 'Quarter' not in all_prov.columns:
                all_prov['Quarter'] = all_prov['Month_Clean'].apply(
                    lambda x: f"Q{x.quarter} {x.year}")
            if 'source_type' not in all_prov.columns:
                all_prov['source_type'] = 'standard'
            # Sort ascending so later files (e.g. MAR26) come last and win
            all_prov = all_prov.sort_values('Month_Clean', ascending=True)
            all_prov = all_prov.drop_duplicates(
                subset=['Name', 'Month_Clean', 'Clinic_Tag', 'source_type'], keep='last')
            df_provider_raw = all_prov
        else:
            df_provider_raw = pd.DataFrame()

        # 77263: keep last record per Name+Month to prevent multi-file double-counting
        def dedup_consults(data_list):
            if not data_list:
                return pd.DataFrame()
            raw = pd.concat(data_list, ignore_index=True)
            raw = raw.drop_duplicates(subset=['Name', 'Month_Clean'], keep='last')
            raw['Month_Label'] = raw['Month_Clean'].dt.strftime('%b-%y')
            raw['Quarter']     = raw['Month_Clean'].apply(lambda x: f"Q{x.quarter} {x.year}")
            return raw

        df_consults     = dedup_consults(consult_data)
        df_md_consults  = dedup_consults(md_consult_data)
        df_md_77470     = dedup_consults(md_77470_data)
        df_app_cpt      = safe_dedup_and_format(app_cpt_data, ['Name', 'Month_Clean', 'CPT Code'])
        df_md_cpt       = safe_dedup_and_format(md_cpt_data,  ['Name', 'Month_Clean', 'CPT Code'])

        if not df_pos_trend.empty:
            df_pos_trend['Display_Name'] = df_pos_trend['Clinic_Tag'].apply(
                lambda x: CLINIC_CONFIG.get(x, {}).get('name', x))

        if not df_clinic.empty:
            df_clinic = df_clinic.groupby(
                ['Name', 'ID', 'Month_Clean', 'Month_Label', 'Quarter'], as_index=False
            ).agg({'Total RVUs': 'sum', 'FTE': 'max', 'Clinic_Tag': 'first'})
            df_clinic['RVU per FTE'] = df_clinic.apply(
                lambda x: x['Total RVUs'] / x['FTE'] if x['FTE'] > 0 else 0, axis=1)
            df_clinic.sort_values('Month_Clean', inplace=True)

        df_provider_global = pd.DataFrame()
        if not df_provider_raw.empty:
            # FIX #2: proper column existence check before filtering on source_type
            if 'source_type' in df_provider_raw.columns:
                df_md_clean = df_provider_raw[df_provider_raw['source_type'] != 'detail'].copy()
            else:
                df_md_clean = df_provider_raw.copy()
            df_provider_global = df_md_clean.groupby(
                ['Name', 'ID', 'Month_Clean', 'Quarter', 'Month_Label'], as_index=False
            ).agg({'Total RVUs': 'sum', 'FTE': 'max'})
            df_provider_global['RVU per FTE'] = df_provider_global.apply(
                lambda x: x['Total RVUs'] / x['FTE'] if x['FTE'] > 0 else 0, axis=1)
            df_provider_global.sort_values('Month_Clean', inplace=True)

        return (df_clinic, df_provider_global, df_provider_raw, df_visits, df_financial,
                df_pos_trend, df_consults, df_app_cpt, df_md_cpt, df_md_consults, df_md_77470,
                debug_log, consult_log, prov_log, scan_77470_log)

    # ==========================================
    # NARRATIVE GENERATOR
    # FIX #3: guarded column access, no KeyError on missing RVU per FTE
    # ==========================================
    def generate_narrative(df, entity_type="Provider", metric_col="Total RVUs", unit="wRVUs", timeframe="this month"):
        if df.empty or metric_col not in df.columns:
            return "No data available."
        latest_date = df['Month_Clean'].max()
        latest_df   = df[df['Month_Clean'] == latest_date]
        if latest_df.empty:
            return "Data processed but current month is empty."
        total_vol      = latest_df[metric_col].sum()
        provider_count = len(latest_df)
        avg_vol        = total_vol / provider_count if provider_count > 0 else 0

        use_rvu_per_fte = (metric_col == "Total RVUs") and ('RVU per FTE' in latest_df.columns)
        if use_rvu_per_fte:
            sorted_df       = latest_df.sort_values('RVU per FTE', ascending=False)
            top_metric_name = "wRVU/FTE"
            top_col         = 'RVU per FTE'
        else:
            sorted_df       = latest_df.sort_values(metric_col, ascending=False)
            top_metric_name = unit
            top_col         = metric_col

        narrative = (
            f"### 🤖 Automated Analysis ({latest_date.strftime('%B %Y')})\n"
            f"The **{entity_type}** group ({provider_count} active) generated a total of "
            f"**{total_vol:,.0f} {unit}** {timeframe}.  \n"
            f"The group average was **{avg_vol:,.0f} {unit}** per {entity_type.lower()}.\n\n"
            f"#### 🏆 Top Performers:\n"
        )
        medals = ["🥇 1st", "🥈 2nd", "🥉 3rd"]
        for i, medal in enumerate(medals):
            if i < len(sorted_df):
                row = sorted_df.iloc[i]
                narrative += f"* **{medal} Place:** **{clean_provider_name_display(row['Name'])}** with **{row[top_col]:,.0f} {top_metric_name}**\n"
        return narrative

    # ==========================================
    # UI HELPERS  (shared across year tabs)
    # ==========================================

    def render_historical_summary(clinic_filter, current_year, df_view_current, target_ids_tristar, target_ids_ascension):
        """Render the Historical Data Summary table inside a tab."""
        df_h = get_historical_df()
        if clinic_filter == "TriStar":        df_h_view = df_h[df_h['ID'].isin(target_ids_tristar)]
        elif clinic_filter == "Ascension":    df_h_view = df_h[df_h['ID'].isin(target_ids_ascension)]
        elif clinic_filter == "All":          df_h_view = df_h.copy()
        else:                                 df_h_view = pd.DataFrame()
        if df_h_view.empty:
            return
        h_trend = df_h_view.groupby('Year')[['Total RVUs']].sum().reset_index()
        ytd_val = float(df_view_current['Total RVUs'].sum()) if not df_view_current.empty else 0.0
        curr_df = pd.DataFrame({"Year": [current_year], "Total RVUs": [ytd_val]})
        final   = pd.concat([h_trend, curr_df], ignore_index=True)
        final['Year'] = final['Year'].astype(int).astype(str)
        table   = final.groupby('Year').sum().T
        st.dataframe(table.style.format("{:,.0f}"), use_container_width=True)

    def render_long_term_history(clinic_filter, current_year, df_view_current, view_title,
                                  target_ids_tristar, target_ids_ascension, clinic_filter_id_map):
        """Render the long-term bar chart + per-clinic subcharts."""
        df_hist = get_historical_df()
        if clinic_filter == "TriStar":     df_hist_view = df_hist[df_hist['ID'].isin(target_ids_tristar)]
        elif clinic_filter == "Ascension": df_hist_view = df_hist[df_hist['ID'].isin(target_ids_ascension)]
        elif clinic_filter == "All":       df_hist_view = df_hist.copy()
        elif clinic_filter == "Sumner":    df_hist_view = df_hist[df_hist['ID'] == 'Sumner']
        else:
            target_id = clinic_filter_id_map.get(clinic_filter, clinic_filter)
            df_hist_view = df_hist[df_hist['ID'] == target_id]

        if df_hist_view.empty:
            return

        hist_trend = df_hist_view.groupby('Year')[['Total RVUs']].sum().reset_index()
        if not df_view_current.empty:
            ytd = df_view_current['Total RVUs'].sum()
            if ytd > 0:
                hist_trend = pd.concat([hist_trend, pd.DataFrame({"Year": [current_year], "Total RVUs": [ytd]})], ignore_index=True)

        fig_long = px.bar(hist_trend, x='Year', y='Total RVUs', text_auto='.2s')
        st.plotly_chart(style_high_end_chart(fig_long), use_container_width=True)

        if clinic_filter not in ["TriStar", "Ascension", "All"]:
            ht = hist_trend.copy()
            ht['Year'] = ht['Year'].astype(int).astype(str)
            st.dataframe(ht.set_index('Year').T.style.format("{:,.0f}"), use_container_width=True)

        if clinic_filter in ["TriStar", "Ascension"]:
            st.markdown("---"); st.markdown("##### 🏥 Individual Clinic History")
            target_ids = target_ids_tristar if clinic_filter == "TriStar" else target_ids_ascension
            cols = st.columns(2)
            for idx, c_id in enumerate(target_ids):
                c_name  = CLINIC_CONFIG.get(c_id, {}).get('name', c_id)
                c_hist  = df_hist[df_hist['ID'] == c_id].groupby('Year')[['Total RVUs']].sum().reset_index()
                if not df_view_current.empty:
                    ytd_c = df_view_current[df_view_current['ID'] == c_id]['Total RVUs'].sum()
                    if ytd_c > 0:
                        c_hist = pd.concat([c_hist, pd.DataFrame({"Year": [current_year], "Total RVUs": [ytd_c]})], ignore_index=True)
                if not c_hist.empty:
                    fig_c = px.bar(c_hist, x='Year', y='Total RVUs', text_auto='.2s', title=c_name)
                    with cols[idx % 2]:
                        st.plotly_chart(style_high_end_chart(fig_c), use_container_width=True)

    def get_most_recent_quarter(df):
        """Return the most recent quarter label present in df, or None."""
        if df.empty or 'Quarter' not in df.columns:
            return None
        # Sort quarters by the start date of each quarter period
        quarters = df['Quarter'].unique()
        def q_sort_key(q):
            try:
                parts = q.split()   # e.g. ["Q1", "2026"]
                return int(parts[1]) * 10 + int(parts[0][1])
            except Exception:
                return 0
        return max(quarters, key=q_sort_key)

    # ==========================================
    # CLINIC TAB RENDERER  (shared for 2025 & 2026)
    # FIX #4: Q hardcode replaced with dynamic get_most_recent_quarter()
    # FIX #5: source_type filter uses proper column check
    # ==========================================
    def render_clinic_tab(year, df_clinic_all, df_provider_raw, df_pos_trend, df_consults, tab_key_suffix):
        df_clinic_yr = df_clinic_all[df_clinic_all['Month_Clean'].dt.year == year].copy() if not df_clinic_all.empty else pd.DataFrame()

        if df_clinic_yr.empty:
            st.info(f"No Clinic data found for {year}.")
            return

        col_nav, col_main = st.columns([1, 5])

        # Mapping from filter label → clinic ID (for single-clinic views)
        filter_id_map = {
            "LROC": "LROC", "TOPC": "TOPC", "TROC": "TROC", "Sumner": "Sumner"
        }

        with col_nav:
            st.markdown("### 🔍 Filter")
            clinic_filter = st.radio(
                "Select View:",
                ["All", "TriStar", "Ascension", "LROC", "TOPC", "TROC", "Sumner"],
                key=f"clinic_radio_{tab_key_suffix}"
            )

            if FPDF:
                st.markdown("---")
                with st.expander(f"📄 Export PDF ({year})"):
                    avail_dates = sorted(df_clinic_yr['Month_Clean'].unique(), reverse=True)
                    month_opts  = [d.strftime('%b-%y') for d in avail_dates]
                    sel_month   = st.selectbox("Select Period:", month_opts, key=f"sel_month_{tab_key_suffix}")
                    target_date = pd.to_datetime(sel_month, format='%b-%y')
                    if st.button("Generate PDF Report", key=f"btn_pdf_{tab_key_suffix}"):
                        if clinic_filter == "All":         pdf_view = df_clinic_yr
                        elif clinic_filter == "TriStar":   pdf_view = df_clinic_yr[df_clinic_yr['ID'].isin(TRISTAR_IDS)]
                        elif clinic_filter == "Ascension": pdf_view = df_clinic_yr[df_clinic_yr['ID'].isin(ASCENSION_IDS)]
                        else: pdf_view = df_clinic_yr[df_clinic_yr['ID'] == filter_id_map.get(clinic_filter, clinic_filter)]

                        pdf_slice = pdf_view[pdf_view['Month_Clean'] == target_date]
                        if not pdf_slice.empty:
                            total_rvu = pdf_slice['Total RVUs'].sum()
                            avg_fte   = pdf_slice['FTE'].sum()
                            rvu_fte   = total_rvu / avg_fte if avg_fte > 0 else 0
                            np_count  = 0
                            if not df_pos_trend.empty:
                                np_count = df_pos_trend[df_pos_trend['Month_Clean'] == target_date]['New Patients'].sum()
                            prov_bd   = df_provider_raw[df_provider_raw['Month_Clean'] == target_date]
                            if clinic_filter == "TriStar":   prov_bd = prov_bd[prov_bd['Clinic_Tag'].isin(TRISTAR_IDS)]
                            elif clinic_filter == "Ascension": prov_bd = prov_bd[prov_bd['Clinic_Tag'].isin(ASCENSION_IDS)]
                            pdf_bytes = create_clinic_pdf(f"{clinic_filter} View", sel_month, total_rvu, rvu_fte, np_count, prov_bd)
                            st.download_button("Download PDF", data=pdf_bytes,
                                               file_name=f"Report_{clinic_filter}_{sel_month}.pdf",
                                               mime='application/pdf', key=f"dl_pdf_{tab_key_suffix}")

        with col_main:
            # Determine filtered view
            if clinic_filter == "All":
                df_view     = df_clinic_yr.copy()
                view_title  = "All Clinics"
                target_tag  = None
            elif clinic_filter == "TriStar":
                df_view     = df_clinic_yr[df_clinic_yr['ID'].isin(TRISTAR_IDS)]
                view_title  = "TriStar Group"
                target_tag  = None
            elif clinic_filter == "Ascension":
                df_view     = df_clinic_yr[df_clinic_yr['ID'].isin(ASCENSION_IDS)]
                view_title  = "Ascension Group"
                target_tag  = None
            elif clinic_filter == "LROC":
                df_view = df_clinic_yr[df_clinic_yr['ID'] == 'LROC']; view_title = "LROC (Lebanon)";       target_tag = "LROC"
            elif clinic_filter == "TOPC":
                df_view = df_clinic_yr[df_clinic_yr['ID'] == 'TOPC']; view_title = "TN Proton Center";     target_tag = "TOPC"
            elif clinic_filter == "TROC":
                df_view = df_clinic_yr[df_clinic_yr['ID'] == 'TROC']; view_title = "TROC (Tullahoma)";     target_tag = "TROC"
            elif clinic_filter == "Sumner":
                df_view = df_clinic_yr[df_clinic_yr['ID'] == 'Sumner']; view_title = "Sumner (Gallatin)";  target_tag = "Sumner"
            else:
                df_view = pd.DataFrame(); view_title = clinic_filter; target_tag = None

            if df_view.empty and clinic_filter not in ["TriStar", "Ascension"]:
                st.warning(f"No data available for {view_title}.")
                return

            st.info(generate_narrative(df_view, f"{view_title} Clinic"))

            # --- Trend chart ---
            with st.container(border=True):
                st.markdown(f"#### 📅 {view_title}: {year} Trend")
                df_sorted = df_view.sort_values('Month_Clean')
                if clinic_filter in ["TriStar", "Ascension", "All"]:
                    agg = df_sorted.groupby('Month_Clean')[['Total RVUs']].sum().reset_index()
                    fig_trend = px.line(agg, x='Month_Clean', y='Total RVUs', markers=True, title="Aggregate Trend")
                else:
                    fig_trend = px.line(df_sorted, x='Month_Clean', y='Total RVUs', color='Name', markers=True)
                st.plotly_chart(style_high_end_chart(fig_trend), use_container_width=True,
                                key=f"trend_{tab_key_suffix}_{clinic_filter}")

            # --- Quarterly bar (single clinics) ---
            if clinic_filter in ["LROC", "TOPC", "TROC", "Sumner"] and not df_view.empty:
                with st.container(border=True):
                    st.markdown(f"#### 📊 Quarterly wRVU Volume ({view_title})")
                    dq = df_view.copy()
                    dq['Q_Sort'] = dq['Month_Clean'].dt.to_period('Q').dt.start_time
                    q_agg = dq.groupby(['Quarter', 'Q_Sort'])[['Total RVUs']].sum().reset_index().sort_values('Q_Sort')
                    if len(q_agg) >= 2:
                        last_q, prior_q = q_agg.iloc[-1], q_agg.iloc[-2]
                        pct = ((last_q['Total RVUs'] - prior_q['Total RVUs']) / prior_q['Total RVUs']) * 100
                        st.metric(f"Change: {prior_q['Quarter']} → {last_q['Quarter']}",
                                  f"{last_q['Total RVUs']:,.0f}", f"{pct:+.1f}%")
                    fig_q = px.bar(q_agg, x='Quarter', y='Total RVUs', text_auto='.2s')
                    st.plotly_chart(style_high_end_chart(fig_q), use_container_width=True,
                                    key=f"qbar_{tab_key_suffix}_{clinic_filter}")

            # --- Individual clinic trends + tables (TriStar/Ascension/All) ---
            if clinic_filter in ["TriStar", "Ascension", "All"]:
                with st.container(border=True):
                    st.markdown(f"#### 📈 {view_title}: Individual Clinic Trends")
                    fig_ind = px.line(df_sorted, x='Month_Clean', y='Total RVUs', color='Name', markers=True)
                    st.plotly_chart(style_high_end_chart(fig_ind), use_container_width=True,
                                    key=f"ind_{tab_key_suffix}_{clinic_filter}")

                    # 77263 table
                    if clinic_filter == "All" and not df_consults.empty:
                        df_cons_yr = df_consults[df_consults['Month_Clean'].dt.year == year]
                        if not df_cons_yr.empty:
                            st.markdown("---")
                            st.markdown("### 📝 Tx Plan Complex (CPT 77263)")
                            sorted_m = df_cons_yr.sort_values("Month_Clean")["Month_Label"].unique()
                            piv = df_cons_yr.pivot_table(index="Name", columns="Month_Label", values="Count", aggfunc="sum")
                            piv = piv.reindex(columns=sorted_m).fillna(0)
                            piv["Total"] = piv.sum(axis=1)
                            st.dataframe(piv.sort_values("Total", ascending=False).style
                                         .format("{:,.0f}").background_gradient(cmap="Blues"), height=500)

                    # Historical summary
                    with st.container(border=True):
                        st.markdown("##### 📅 Historical Data Summary")
                        render_historical_summary(clinic_filter, year, df_view, TRISTAR_IDS, ASCENSION_IDS)

                    # Monthly & quarterly pivot tables
                    if not df_view.empty:
                        c1, c2 = st.columns(2)
                        with c1:
                            with st.container(border=True):
                                st.markdown("#### 🔢 Monthly Data")
                                piv_m = df_view.pivot_table(index="Name", columns="Month_Label", values="Total RVUs", aggfunc="sum").fillna(0)
                                sorted_m2 = df_view.sort_values("Month_Clean")["Month_Label"].unique()
                                piv_m = piv_m.reindex(columns=sorted_m2).fillna(0)
                                piv_m["Total"] = piv_m.sum(axis=1)
                                st.dataframe(piv_m.sort_values("Total", ascending=False).style
                                             .format("{:,.0f}").background_gradient(cmap="Reds"))
                        with c2:
                            with st.container(border=True):
                                st.markdown("#### 📆 Quarterly Data")
                                piv_q = df_view.pivot_table(index="Name", columns="Quarter", values="Total RVUs", aggfunc="sum").fillna(0)
                                piv_q["Total"] = piv_q.sum(axis=1)
                                st.dataframe(piv_q.sort_values("Total", ascending=False).style
                                             .format("{:,.0f}").background_gradient(cmap="Oranges"))

            # --- Long-term history chart ---
            with st.container(border=True):
                st.markdown(f"#### 📈 Long-Term History ({view_title})")
                render_long_term_history(
                    clinic_filter, year, df_view, view_title,
                    TRISTAR_IDS, ASCENSION_IDS,
                    {"LROC": "LROC", "TOPC": "TOPC", "TROC": "TROC", "Sumner": "Sumner"}
                )

            # --- Network-wide new patients (All view) ---
            if clinic_filter == "All":
                df_pos_yr = df_pos_trend[df_pos_trend['Month_Clean'].dt.year == year].copy() if not df_pos_trend.empty else pd.DataFrame()
                if not df_pos_yr.empty:
                    st.markdown("---")
                    st.markdown("### 🆕 Network-Wide New Patients")
                    max_dt = df_pos_yr['Month_Clean'].max()
                    np_latest = df_pos_yr[df_pos_yr['Month_Clean'] == max_dt].copy()
                    np_latest['Display_Name'] = np_latest['Clinic_Tag'].apply(lambda x: CLINIC_CONFIG.get(x, {}).get('name', x))
                    df_pos_yr['Display_Name']  = df_pos_yr['Clinic_Tag'].apply(lambda x: CLINIC_CONFIG.get(x, {}).get('name', x))
                    fig_np = px.bar(np_latest.sort_values('New Patients', ascending=False),
                                    x='Display_Name', y='New Patients', text_auto=True,
                                    title=f"New Patients: {max_dt.strftime('%B %Y')}")
                    st.plotly_chart(style_high_end_chart(fig_np), use_container_width=True,
                                    key=f"np_net_{tab_key_suffix}")
                    piv_np = df_pos_yr.pivot_table(index="Display_Name", columns="Month_Label", values="New Patients", aggfunc="sum").fillna(0)
                    st.dataframe(piv_np.style.format("{:,.0f}").background_gradient(cmap="Greens"))

            # --- wRVU/FTE efficiency (All view) ---
            if clinic_filter == "All" and not df_clinic_yr.empty:
                st.markdown("---")
                with st.container(border=True):
                    st.markdown(f"### 🩺 Efficiency: wRVU per FTE by Center ({year})")
                    max_dt_fte = df_clinic_yr['Month_Clean'].max()
                    df_fte_latest = df_clinic_yr[df_clinic_yr['Month_Clean'] == max_dt_fte]
                    if not df_fte_latest.empty:
                        fig_fte = px.bar(df_fte_latest.sort_values('RVU per FTE', ascending=False),
                                         x='Name', y='RVU per FTE', text_auto='.0f',
                                         color='RVU per FTE', color_continuous_scale='Portland',
                                         title=f"wRVU per FTE: {max_dt_fte.strftime('%B %Y')}")
                        st.plotly_chart(style_high_end_chart(fig_fte), use_container_width=True,
                                        key=f"fte_{tab_key_suffix}")
                        div_avg = df_fte_latest['Total RVUs'].sum() / df_fte_latest['FTE'].sum() if df_fte_latest['FTE'].sum() > 0 else 0
                        st.caption(f"**Division Average:** {div_avg:,.0f} wRVU/FTE")

            # --- FIX #4: Dynamic quarterly comparison (All view) ---
            if clinic_filter == "All" and not df_clinic_yr.empty:
                target_q = get_most_recent_quarter(df_clinic_yr)   # Was hardcoded "Q1 2026"
                if target_q:
                    df_q_data = df_clinic_yr[df_clinic_yr['Quarter'] == target_q].copy()
                    if not df_q_data.empty:
                        st.markdown("---")
                        cq1, cq2 = st.columns(2)
                        with cq1:
                            with st.container(border=True):
                                st.markdown(f"#### 📊 Total wRVU Volume: {target_q}")
                                # FIX: no more hardcoded /2 hack — source_type filter handles TOPC dedup
                                df_q_sum = df_q_data.groupby('ID').agg(
                                    {'Total RVUs': 'sum', 'Name': 'first'}
                                ).reset_index()
                                fig_qv = px.bar(df_q_sum.sort_values('Total RVUs', ascending=False),
                                                x='Name', y='Total RVUs', text_auto='.2s',
                                                color='Total RVUs', color_continuous_scale='Blues',
                                                title=f"Total Center Volume ({target_q})")
                                st.plotly_chart(style_high_end_chart(fig_qv), use_container_width=True,
                                                key=f"qvol_{tab_key_suffix}")
                        with cq2:
                            with st.container(border=True):
                                st.markdown(f"#### 🩺 Efficiency: wRVU per FTE: {target_q}")
                                df_q_eff = df_q_data.groupby('Name').agg(
                                    {'Total RVUs': 'sum', 'FTE': 'max'}
                                ).reset_index()
                                df_q_eff['RVU per FTE'] = df_q_eff.apply(
                                    lambda x: x['Total RVUs'] / x['FTE'] if x['FTE'] > 0 else 0, axis=1)
                                fig_qe = px.bar(df_q_eff.sort_values('RVU per FTE', ascending=False),
                                                x='Name', y='RVU per FTE', text_auto='.0f',
                                                color='RVU per FTE', color_continuous_scale='Portland',
                                                title=f"Quarterly wRVU per FTE ({target_q})")
                                st.plotly_chart(style_high_end_chart(fig_qe), use_container_width=True,
                                                key=f"qeff_{tab_key_suffix}")

            # --- Detailed per-clinic breakdown (TriStar / Ascension) ---
            if clinic_filter in ["TriStar", "Ascension"]:
                st.markdown("---")
                st.subheader(f"🔍 Detailed Breakdown by Clinic ({view_title})")
                target_ids = TRISTAR_IDS if clinic_filter == "TriStar" else ASCENSION_IDS
                df_prov_yr = df_provider_raw[df_provider_raw['Month_Clean'].dt.year == year].copy() if not df_provider_raw.empty else pd.DataFrame()
                for c_id in target_ids:
                    c_name = CLINIC_CONFIG.get(c_id, {}).get('name', c_id)
                    # FIX #5: proper source_type column check
                    if not df_prov_yr.empty and 'source_type' in df_prov_yr.columns:
                        cpdf = df_prov_yr[(df_prov_yr['Clinic_Tag'] == c_id) & (df_prov_yr['source_type'] == 'detail')]
                        if cpdf.empty:
                            cpdf = df_prov_yr[df_prov_yr['Clinic_Tag'] == c_id]
                    elif not df_prov_yr.empty:
                        cpdf = df_prov_yr[df_prov_yr['Clinic_Tag'] == c_id]
                    else:
                        cpdf = pd.DataFrame()
                    if cpdf.empty:
                        continue
                    st.markdown(f"### 🏥 {c_name}")
                    pie_ytd = cpdf.groupby('Name')[['Total RVUs']].sum().reset_index()
                    pie_ytd = pie_ytd[pie_ytd['Total RVUs'] > 0]
                    latest_q = get_most_recent_quarter(cpdf)
                    pie_q    = cpdf[cpdf['Quarter'] == latest_q].groupby('Name')[['Total RVUs']].sum().reset_index() if latest_q else pd.DataFrame()
                    if not pie_q.empty:
                        pie_q = pie_q[pie_q['Total RVUs'] > 0]
                    if not pie_ytd.empty:
                        with st.container(border=True):
                            st.markdown(f"#### 🍰 {c_name}: Work Breakdown")
                            cp1, cp2 = st.columns(2)
                            with cp1:
                                fig_p1 = px.pie(pie_ytd, values='Total RVUs', names='Name', hole=0.4, title=f"{year} Total")
                                fig_p1.update_traces(textposition='inside', textinfo='percent+label')
                                st.plotly_chart(style_high_end_chart(fig_p1), use_container_width=True,
                                                key=f"pie_ytd_{tab_key_suffix}_{c_id}")
                            with cp2:
                                if not pie_q.empty:
                                    fig_p2 = px.pie(pie_q, values='Total RVUs', names='Name', hole=0.4, title=f"Most Recent Quarter ({latest_q})")
                                    fig_p2.update_traces(textposition='inside', textinfo='percent+label')
                                    st.plotly_chart(style_high_end_chart(fig_p2), use_container_width=True,
                                                    key=f"pie_q_{tab_key_suffix}_{c_id}")
                    with st.container(border=True):
                        st.markdown(f"#### 🧑‍⚕️ {c_name}: Monthly Data (by Provider)")
                        piv_p = cpdf.pivot_table(index="Name", columns="Month_Label", values="Total RVUs", aggfunc="sum").fillna(0)
                        sorted_m = cpdf.sort_values("Month_Clean")["Month_Label"].unique()
                        piv_p = piv_p.reindex(columns=sorted_m).fillna(0)
                        piv_p["Total"] = piv_p.sum(axis=1)
                        st.dataframe(piv_p.sort_values("Total", ascending=False).style
                                     .format("{:,.0f}").background_gradient(cmap="Blues"))
                    # POS trend for this clinic
                    if not df_pos_trend.empty:
                        df_pos_yr2 = df_pos_trend[df_pos_trend['Month_Clean'].dt.year == year]
                        pos_df = df_pos_yr2[df_pos_yr2['Clinic_Tag'] == c_id]
                        if not pos_df.empty:
                            with st.container(border=True):
                                st.markdown(f"#### 🆕 {c_name}: New Patient Trend")
                                pos_agg = pos_df.groupby('Month_Clean')[['New Patients']].sum().reset_index().sort_values('Month_Clean')
                                fig_pos = px.bar(pos_agg, x='Month_Clean', y='New Patients', text_auto=True)
                                st.plotly_chart(style_high_end_chart(fig_pos), use_container_width=True,
                                                key=f"pos_{tab_key_suffix}_{c_id}")
                                pos_piv = pos_df.pivot_table(index="Clinic_Tag", columns="Month_Label", values="New Patients", aggfunc="sum").fillna(0)
                                sorted_mp = pos_df.sort_values("Month_Clean")["Month_Label"].unique()
                                pos_piv = pos_piv.reindex(columns=sorted_mp).fillna(0)
                                pos_piv["Total"] = pos_piv.sum(axis=1)
                                st.dataframe(pos_piv.style.format("{:,.0f}").background_gradient(cmap="Greens"))

            # --- Single-clinic pie + provider table ---
            if target_tag and not df_provider_raw.empty:
                df_prov_yr = df_provider_raw[df_provider_raw['Month_Clean'].dt.year == year].copy()
                # FIX #5: proper source_type check
                if 'source_type' in df_prov_yr.columns:
                    pie_src = df_prov_yr[(df_prov_yr['Clinic_Tag'] == target_tag) & (df_prov_yr['source_type'] == 'detail')]
                    if pie_src.empty:
                        pie_src = df_prov_yr[df_prov_yr['Clinic_Tag'] == target_tag]
                else:
                    pie_src = df_prov_yr[df_prov_yr['Clinic_Tag'] == target_tag]

                if not pie_src.empty:
                    try:
                        pie_ytd = pie_src.groupby('Name')[['Total RVUs']].sum().reset_index()
                        pie_ytd = pie_ytd[pie_ytd['Total RVUs'] > 0]
                        latest_q = get_most_recent_quarter(pie_src)
                        pie_q    = pie_src[pie_src['Quarter'] == latest_q].groupby('Name')[['Total RVUs']].sum().reset_index() if latest_q else pd.DataFrame()
                        if not pie_q.empty:
                            pie_q = pie_q[pie_q['Total RVUs'] > 0]
                        if not pie_ytd.empty:
                            with st.container(border=True):
                                st.markdown("#### 🍰 Work Breakdown: Who performed the work?")
                                cp1, cp2 = st.columns(2)
                                with cp1:
                                    fig_p1 = px.pie(pie_ytd, values='Total RVUs', names='Name', hole=0.4, title=f"{year} Total")
                                    fig_p1.update_traces(textposition='inside', textinfo='percent+label')
                                    st.plotly_chart(style_high_end_chart(fig_p1), use_container_width=True,
                                                    key=f"pie_src_ytd_{tab_key_suffix}_{target_tag}")
                                with cp2:
                                    if not pie_q.empty:
                                        fig_p2 = px.pie(pie_q, values='Total RVUs', names='Name', hole=0.4, title=f"Most Recent Quarter ({latest_q})")
                                        fig_p2.update_traces(textposition='inside', textinfo='percent+label')
                                        st.plotly_chart(style_high_end_chart(fig_p2), use_container_width=True,
                                                        key=f"pie_src_q_{tab_key_suffix}_{target_tag}")
                    except Exception:
                        st.info("Insufficient data for pie charts.")

                    with st.container(border=True):
                        st.markdown("#### 🧑‍⚕️ Monthly Data (by Provider)")
                        piv_p = pie_src.pivot_table(index="Name", columns="Month_Label", values="Total RVUs", aggfunc="sum").fillna(0)
                        sorted_m = pie_src.sort_values("Month_Clean")["Month_Label"].unique()
                        piv_p = piv_p.reindex(columns=sorted_m).fillna(0)
                        piv_p["Total"] = piv_p.sum(axis=1)
                        st.dataframe(piv_p.sort_values("Total", ascending=False).style
                                     .format("{:,.0f}").background_gradient(cmap="Blues"))

            # --- Visits (LROC / TROC / TOPC) ---
            if target_tag in ["LROC", "TROC", "TOPC"] and not df_visits.empty:
                df_vis_yr = df_visits[df_visits['Month_Clean'].dt.year == year]
                cli_vis   = df_vis_yr[df_vis_yr['Clinic_Tag'] == target_tag]
                if not cli_vis.empty:
                    with st.container(border=True):
                        st.markdown("### 🏥 Office Visits & New Patients")
                        lv = cli_vis['Month_Clean'].max()
                        lv_df = cli_vis[cli_vis['Month_Clean'] == lv]
                        cv1, cv2 = st.columns(2)
                        with cv1:
                            fig_ov = px.bar(lv_df.sort_values('Total Visits', ascending=True),
                                            x='Total Visits', y='Name', orientation='h', text_auto=True,
                                            color='Total Visits', color_continuous_scale='Blues',
                                            title=f"YTD Total Office Visits ({lv.strftime('%b %Y')})")
                            fig_ov.update_layout(height=800)
                            st.plotly_chart(style_high_end_chart(fig_ov), use_container_width=True,
                                            key=f"ov_{tab_key_suffix}_{target_tag}")
                        with cv2:
                            fig_np = px.bar(lv_df.sort_values('New Patients', ascending=True),
                                            x='New Patients', y='Name', orientation='h', text_auto=True,
                                            color='New Patients', color_continuous_scale='Greens',
                                            title=f"YTD New Patients ({lv.strftime('%b %Y')})")
                            fig_np.update_layout(height=800)
                            st.plotly_chart(style_high_end_chart(fig_np), use_container_width=True,
                                            key=f"np_{tab_key_suffix}_{target_tag}")
                    with st.container(border=True):
                        st.markdown("#### 📉 YoY Change: New Patients")
                        fig_diff = px.bar(lv_df.sort_values('NP_Diff', ascending=True),
                                          x='NP_Diff', y='Name', orientation='h', text_auto=True,
                                          color='NP_Diff', color_continuous_scale='RdBu')
                        fig_diff.update_layout(height=800)
                        st.plotly_chart(style_high_end_chart(fig_diff), use_container_width=True,
                                        key=f"npdiff_{tab_key_suffix}_{target_tag}")

    # ==========================================
    # MD TAB RENDERER  (shared for 2025 & 2026)
    # ==========================================
    def render_md_tab(year, df_mds, df_visits, df_md_consults, df_md_77470, tab_key_suffix, scan_77470_log=None):
        col_nav, col_main = st.columns([1, 5])
        with col_nav:
            st.markdown(f"### 📊 Metric ({year})")
            md_view = st.radio("Select View:", ["wRVU Productivity", "Office Visits", "77470 Special Procedures"],
                               key=f"md_radio_{tab_key_suffix}")
        with col_main:
            df_mds_yr = df_mds[df_mds['Month_Clean'].dt.year == year].copy() if not df_mds.empty else pd.DataFrame()

            if md_view == "wRVU Productivity":
                if df_mds_yr.empty:
                    st.info(f"No Physician productivity data found for {year}.")
                else:
                    st.info(generate_narrative(df_mds_yr, "Physician"))
                    with st.container(border=True):
                        st.markdown(f"#### 📈 {year} Trend (RVU per FTE)")
                        fig_t = px.line(df_mds_yr.sort_values('Month_Clean'), x='Month_Clean',
                                        y='RVU per FTE', color='Name', markers=True)
                        st.plotly_chart(style_high_end_chart(fig_t), use_container_width=True,
                                        key=f"md_trend_{tab_key_suffix}")
                    c1, c2 = st.columns(2)
                    with c1:
                        with st.container(border=True):
                            st.markdown("#### 🔢 Monthly Data")
                            piv = df_mds_yr.pivot_table(index="Name", columns="Month_Label", values="Total RVUs", aggfunc="sum").fillna(0)
                            sorted_m = df_mds_yr.sort_values("Month_Clean")["Month_Label"].unique()
                            piv = piv.reindex(columns=sorted_m).fillna(0)
                            piv["Total"] = piv.sum(axis=1)
                            st.dataframe(piv.sort_values("Total", ascending=False).style
                                         .format("{:,.0f}").background_gradient(cmap="Blues"), height=400)
                    with c2:
                        with st.container(border=True):
                            st.markdown("#### 🏆 YTD Total RVUs")
                            ytd_s = df_mds_yr.groupby('Name')[['Total RVUs']].sum().reset_index().sort_values('Total RVUs', ascending=False)
                            fig_ytd = px.bar(ytd_s, x='Name', y='Total RVUs', color='Total RVUs',
                                             color_continuous_scale='Viridis', text_auto='.2s')
                            st.plotly_chart(style_high_end_chart(fig_ytd), use_container_width=True,
                                            key=f"md_ytd_{tab_key_suffix}")

            elif md_view == "Office Visits":
                df_vis_yr = df_visits[df_visits['Month_Clean'].dt.year == year].copy() if not df_visits.empty else pd.DataFrame()
                st.info("ℹ️ **Includes all HOPD and freestanding sites (LROC, TROC, TOPC)**")
                if df_vis_yr.empty:
                    st.warning(f"No Office Visit data found for {year}.")
                else:
                    df_vis_agg = df_vis_yr.groupby(['Name', 'Month_Clean'], as_index=False).agg(
                        {'Total Visits': 'sum', 'New Patients': 'sum', 'Visits_Diff': 'sum', 'NP_Diff': 'sum'})
                    lv = df_vis_agg['Month_Clean'].max()
                    lv_df = df_vis_agg[df_vis_agg['Month_Clean'] == lv]
                    lv_df = lv_df[~lv_df['Name'].isin(APP_LIST)]
                    c1, c2 = st.columns(2)
                    with c1:
                        with st.container(border=True):
                            st.markdown(f"#### 🏥 Total Office Visits ({year} YTD)")
                            fig_ov = px.bar(lv_df.sort_values('Total Visits', ascending=True),
                                            x='Total Visits', y='Name', orientation='h', text_auto=True,
                                            color='Total Visits', color_continuous_scale='Blues')
                            st.plotly_chart(style_high_end_chart(fig_ov), use_container_width=True,
                                            key=f"vis_ov_{tab_key_suffix}")
                    with c2:
                        with st.container(border=True):
                            st.markdown(f"#### 🆕 New Patients ({year} YTD)")
                            fig_np = px.bar(lv_df.sort_values('New Patients', ascending=True),
                                            x='New Patients', y='Name', orientation='h', text_auto=True,
                                            color='New Patients', color_continuous_scale='Greens')
                            st.plotly_chart(style_high_end_chart(fig_np), use_container_width=True,
                                            key=f"vis_np_{tab_key_suffix}")

            elif md_view == "77470 Special Procedures":
                df_77470_yr = df_md_77470[df_md_77470['Month_Clean'].dt.year == year].copy() if not df_md_77470.empty else pd.DataFrame()
                st.markdown(f"### 🔬 CPT 77470 — Special Treatment Procedure ({year})")
                st.info(f"Estimated procedure counts derived from wRVU amounts ÷ {CPT_77470_WRVU} (2026 PC wRVU value for 77470).")
                if df_77470_yr.empty:
                    st.warning(f"No CPT 77470 data found for {year}. (Total records in dataset: {len(df_md_77470)})")
                    with st.expander("77470 Scan Debug Log"):
                        errs = [e for e in consult_log if "77470" in e]
                        lines = (scan_77470_log or []) + errs
                        st.code("\n".join(lines[:100]) if lines else "(no log entries)")
                else:
                    sorted_m = df_77470_yr.sort_values("Month_Clean")["Month_Label"].unique()

                    with st.container(border=True):
                        st.markdown("#### 📅 Monthly Trend")
                        fig_t = px.line(
                            df_77470_yr.sort_values("Month_Clean"),
                            x="Month_Clean", y="Count", color="Name", markers=True,
                            labels={"Count": "Estimated Procedures", "Month_Clean": "Month"},
                        )
                        st.plotly_chart(style_high_end_chart(fig_t), use_container_width=True,
                                        key=f"md_77470_trend_{tab_key_suffix}")

                    c1, c2 = st.columns(2)
                    with c1:
                        with st.container(border=True):
                            st.markdown("#### 🔢 Monthly Count by Provider")
                            piv_77470 = df_77470_yr.pivot_table(
                                index="Name", columns="Month_Label", values="Count", aggfunc="sum"
                            ).fillna(0)
                            piv_77470 = piv_77470.reindex(columns=sorted_m).fillna(0)
                            piv_77470["Total"] = piv_77470.sum(axis=1)
                            st.dataframe(
                                piv_77470.sort_values("Total", ascending=False).style
                                .format("{:,.1f}").background_gradient(cmap="Purples"),
                                height=450, use_container_width=True,
                                key=f"md_77470_tbl_{tab_key_suffix}",
                            )
                    with c2:
                        with st.container(border=True):
                            st.markdown(f"#### 🏆 {year} YTD Total")
                            ytd_77470 = df_77470_yr.groupby("Name")["Count"].sum().reset_index()
                            ytd_77470 = ytd_77470.sort_values("Count", ascending=False)
                            fig_ytd = px.bar(
                                ytd_77470, x="Name", y="Count", text_auto=".1f",
                                color="Count", color_continuous_scale="Purples",
                                labels={"Count": "Estimated Procedures"},
                            )
                            st.plotly_chart(style_high_end_chart(fig_ytd), use_container_width=True,
                                            key=f"md_77470_ytd_{tab_key_suffix}")

            # 77263 table — always shown at the bottom of the MD tab
            st.markdown("---")
            df_77_yr = df_md_consults[df_md_consults['Month_Clean'].dt.year == year].copy() if not df_md_consults.empty else pd.DataFrame()
            if not df_77_yr.empty:
                st.markdown(f"### 📝 MD Tx Plan Complex (CPT 77263) — {year}")
                sorted_m = df_77_yr.sort_values("Month_Clean")["Month_Label"].unique()
                piv_77 = df_77_yr.pivot_table(index="Name", columns="Month_Label", values="Count", aggfunc="sum").fillna(0)
                piv_77 = piv_77.reindex(columns=sorted_m).fillna(0)
                piv_77["Total"] = piv_77.sum(axis=1)
                st.dataframe(piv_77.sort_values("Total", ascending=False).style
                             .format("{:,.0f}").background_gradient(cmap="Blues"),
                             height=500, use_container_width=True, key=f"md_77_{tab_key_suffix}")

                # 77263 / New Patients ratio (2025 only — needs visit data)
                if year == 2025 and not df_visits.empty:
                    df_vis_yr2 = df_visits[df_visits['Month_Clean'].dt.year == year]
                    df_vis_agg2 = df_vis_yr2.groupby(['Name', 'Month_Clean'], as_index=False).agg({'Total Visits': 'sum', 'New Patients': 'sum'})
                    lv2 = df_vis_agg2['Month_Clean'].max()
                    lv_df2 = df_vis_agg2[df_vis_agg2['Month_Clean'] == lv2]
                    lv_df2 = lv_df2[~lv_df2['Name'].isin(APP_LIST)]
                    md_ytd = df_77_yr.groupby('Name')['Count'].sum().reset_index()
                    ratio_df = pd.merge(md_ytd, lv_df2[['Name', 'New Patients']], on='Name', how='inner')
                    ratio_df['Ratio'] = ratio_df.apply(lambda x: x['Count'] / x['New Patients'] if x['New Patients'] > 0 else 0, axis=1)
                    ratio_df['Label'] = ratio_df.apply(lambda x: f"{x['Ratio']:.2f} ({int(x['Count'])}/{int(x['New Patients'])})", axis=1)
                    if not ratio_df.empty:
                        st.markdown("---")
                        st.markdown("### 📊 Ratio: Tx Plan (77263) / New Patients (YTD)")
                        fig_ratio = px.bar(ratio_df.sort_values('Ratio', ascending=True),
                                           x='Ratio', y='Name', orientation='h', text='Label',
                                           title="Ratio > 1.0 = more Tx Plans than New Patients")
                        fig_ratio.update_traces(textposition='outside')
                        st.plotly_chart(style_high_end_chart(fig_ratio), use_container_width=True,
                                        key=f"ratio_{tab_key_suffix}")

    # ==========================================
    # MAIN UI
    # ==========================================
    st.title("🩺 Radiation Oncology Division Analytics")
    st.markdown("##### by Dr. Jones")
    st.markdown("---")

    # Load server files
    server_files = []
    if os.path.exists(SERVER_DIR):
        all_paths = sorted([
            os.path.join(root, f)
            for root, _, files in os.walk(SERVER_DIR)
            for f in files if f.endswith((".xlsx", ".xls"))
        ])
        server_files = [LocalFile(p) for p in all_paths]

    with st.sidebar:
        st.header("Data Import")
        if server_files:
            st.success(f"✅ Loaded {len(server_files)} master files from server.")
        else:
            st.info("ℹ️ No master files found on server.")
        uploaded_files = st.file_uploader("Add Temporary Files", type=['xlsx', 'xls'], accept_multiple_files=True)

    all_files = server_files + (list(uploaded_files) if uploaded_files else [])

    if all_files:
        with st.spinner("Analyzing files..."):
            (df_clinic, df_md_global, df_provider_raw, df_visits, df_financial,
             df_pos_trend, df_consults, df_app_cpt, df_md_cpt, df_md_consults, df_md_77470,
             debug_log, consult_log, prov_log, scan_77470_log) = process_files(all_files)

        if df_clinic.empty and df_md_global.empty:
            st.error("No valid data found. Check that your files are in the Reports folder.")
        else:
            valid_providers = set(PROVIDER_CONFIG.keys())
            if not df_md_global.empty:
                df_apps = df_md_global[df_md_global['Name'].isin(APP_LIST)]
                df_mds  = df_md_global[(df_md_global['Name'].isin(valid_providers)) & (~df_md_global['Name'].isin(APP_LIST))]
            else:
                df_apps = pd.DataFrame()
                df_mds  = pd.DataFrame()

            tab_c26, tab_c25, tab_md26, tab_md25, tab_app, tab_fin = st.tabs([
                "🏥 Clinic Analytics - 2026",
                "🏥 Clinic Analytics - 2025",
                "👨‍⚕️ MD Analytics - 2026",
                "👨‍⚕️ MD Analytics - 2025",
                "👩‍⚕️ APP Analytics",
                "💰 Financials",
            ])

            with tab_c26:
                render_clinic_tab(2026, df_clinic, df_provider_raw, df_pos_trend, df_consults, "26")

            with tab_c25:
                render_clinic_tab(2025, df_clinic, df_provider_raw, df_pos_trend, df_consults, "25")

            with tab_md26:
                render_md_tab(2026, df_mds, df_visits, df_md_consults, df_md_77470, "26", scan_77470_log)

            with tab_md25:
                render_md_tab(2025, df_mds, df_visits, df_md_consults, df_md_77470, "25", scan_77470_log)

            with tab_app:
                if df_apps.empty:
                    st.info("No APP data found.")
                else:
                    st.info(generate_narrative(df_apps, "APP"))
                    with st.container(border=True):
                        st.markdown("#### 📅 Last 12 Months Trend (RVU per FTE)")
                        fig_t = px.line(df_apps.sort_values('Month_Clean'), x='Month_Clean',
                                        y='RVU per FTE', color='Name', markers=True)
                        st.plotly_chart(style_high_end_chart(fig_t), use_container_width=True)
                    st.markdown("---")
                    if not df_app_cpt.empty:
                        st.markdown("### 🏥 APP Independent Follow-up Visits (99212-99215)")
                        ytd_app = df_app_cpt.groupby(['Name', 'CPT Code'])['Count'].sum().reset_index()
                        fig_ab = px.bar(ytd_app, x="Name", y="Count", color="CPT Code",
                                        barmode="group", text_auto=True, title="YTD Follow-up Visits")
                        st.plotly_chart(style_high_end_chart(fig_ab), use_container_width=True)
                        cols = st.columns(2)
                        for i, app_name in enumerate(df_app_cpt['Name'].unique()):
                            with cols[i % 2]:
                                with st.container(border=True):
                                    st.markdown(f"#### {app_name}")
                                    sub = df_app_cpt[df_app_cpt['Name'] == app_name]
                                    piv_a = sub.pivot_table(index="CPT Code", columns="Month_Label", values="Count", aggfunc="sum").fillna(0)
                                    sorted_ma = sub.sort_values("Month_Clean")["Month_Label"].unique()
                                    piv_a = piv_a.reindex(columns=sorted_ma).fillna(0)
                                    piv_a["Total"] = piv_a.sum(axis=1)
                                    st.dataframe(piv_a.style.format("{:,.0f}").background_gradient(cmap="Oranges"))

            with tab_fin:
                if df_financial.empty:
                    st.info("No Financial data found.")
                else:
                    fin_view = st.radio("Select Financial View:", ["CPA By Provider", "CPA By Clinic"], key="fin_radio")
                    if fin_view == "CPA By Provider":
                        prov_fin = df_financial[(df_financial['Mode'] == 'Provider') & (df_financial['Name'] != "TN Proton Center")]
                        if not prov_fin.empty:
                            st.markdown("### 💰 CPA By Provider (YTD)")
                            lfd = prov_fin['Month_Clean'].max()
                            lp  = prov_fin[prov_fin['Month_Clean'] == lfd].groupby('Name', as_index=False)[['Charges','Payments']].sum()
                            lp['% Payments/Charges'] = lp.apply(lambda x: x['Payments'] / x['Charges'] if x['Charges'] > 0 else 0, axis=1)
                            c1, c2 = st.columns(2)
                            with c1:
                                fig_chg = px.bar(lp.sort_values('Charges', ascending=True), x='Charges', y='Name',
                                                 orientation='h', title=f"Total Charges ({lfd.strftime('%b %Y')})", text_auto='$.2s')
                                st.plotly_chart(style_high_end_chart(fig_chg), use_container_width=True)
                            with c2:
                                fig_pay = px.bar(lp.sort_values('Payments', ascending=True), x='Payments', y='Name',
                                                 orientation='h', title=f"Total Payments ({lfd.strftime('%b %Y')})", text_auto='$.2s')
                                st.plotly_chart(style_high_end_chart(fig_pay), use_container_width=True)
                            fmt = {'Charges': '${:,.2f}', 'Payments': '${:,.2f}', '% Payments/Charges': '{:.1%}'}
                            st.dataframe(lp[['Name','Charges','Payments','% Payments/Charges']].sort_values('Charges', ascending=False).style
                                         .format(fmt).background_gradient(cmap="Greens"))
                    elif fin_view == "CPA By Clinic":
                        cf = df_financial[df_financial['Mode'] == 'Clinic']
                        if not cf.empty:
                            st.markdown("### 🏥 CPA By Clinic")
                            ytd = cf.groupby('Name')[['Charges','Payments']].sum().reset_index()
                            ytd['% Payments/Charges'] = ytd.apply(lambda x: x['Payments'] / x['Charges'] if x['Charges'] > 0 else 0, axis=1)
                            total_row = pd.DataFrame([{"Name": "TOTAL", "Charges": ytd['Charges'].sum(),
                                                        "Payments": ytd['Payments'].sum(),
                                                        "% Payments/Charges": ytd['Payments'].sum() / ytd['Charges'].sum() if ytd['Charges'].sum() > 0 else 0}])
                            ytd_disp = pd.concat([ytd.sort_values('Charges', ascending=False), total_row], ignore_index=True)
                            fmt = {'Charges': '${:,.2f}', 'Payments': '${:,.2f}', '% Payments/Charges': '{:.1%}'}
                            st.markdown("#### 📆 Year to Date Charges & Payments")
                            st.dataframe(ytd_disp.style.format(fmt).background_gradient(cmap="Greens"), height=600)
                            st.markdown("---")
                            st.markdown("#### 📅 Monthly Data Breakdown")
                            md_disp = cf[['Name','Month_Label','Charges','Payments']].copy()
                            md_disp['% Payments/Charges'] = md_disp.apply(lambda x: x['Payments'] / x['Charges'] if x['Charges'] > 0 else 0, axis=1)
                            md_disp['Month_Sort'] = pd.to_datetime(md_disp['Month_Label'], format='%b-%y')
                            md_disp = md_disp.sort_values(['Month_Sort','Name'], ascending=[False, True]).drop(columns=['Month_Sort'])
                            st.dataframe(md_disp.style.format(fmt).background_gradient(cmap="Blues"))

    else:
        st.info("👋 Ready. Add files to the 'Reports' folder in GitHub to load data.")
