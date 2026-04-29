import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime
import os
import re
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.colors as mcolors

def _lc(name, lo=0.05, hi=0.45):
    """Truncate a colormap to the light portion so backgrounds never get dark enough to need white text."""
    return mcolors.LinearSegmentedColormap.from_list(
        f'{name}_light', plt.get_cmap(name)(np.linspace(lo, hi, 256)))

# Light colormap palette — used in all background_gradient calls
_LC = {
    'Blues':    _lc('Blues',    0.05, 0.45),
    'Greens':   _lc('Greens',   0.05, 0.45),
    'Reds':     _lc('Reds',     0.05, 0.45),
    'Oranges':  _lc('Oranges',  0.05, 0.45),
    'Purples':  _lc('Purples',  0.05, 0.45),
    'RdYlGn':   _lc('RdYlGn',   0.12, 0.88),
    'RdYlGn_r': _lc('RdYlGn_r', 0.12, 0.88),
}

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
        /* --- Hide Streamlit chrome --- */
        #MainMenu, footer, header,
        [data-testid="stToolbar"], [data-testid="stHeader"], .stDeployButton
            { visibility: hidden !important; display: none !important; }

        /* --- Global font --- */
        html, body, [class*="css"] { font-family: 'Inter', sans-serif; }

        /* --- Tab bar --- */
        .stTabs [data-baseweb="tab-list"] {
            gap: 10px; background: transparent; padding-bottom: 12px;
            border-bottom: 2px solid #1E3A8A;
        }
        .stTabs [data-baseweb="tab-list"] button {
            background: #f8fafc; border: 1px solid #cbd5e1; border-radius: 8px;
            color: #475569; padding: 10px 22px;
        }
        .stTabs [data-baseweb="tab-list"] button [data-testid="stMarkdownContainer"] p {
            font-size: 15px !important; font-weight: 600 !important; margin: 0;
        }
        .stTabs [data-baseweb="tab-list"] button[aria-selected="true"] {
            background: #1E3A8A !important; color: #FFFFFF !important;
            border-color: #1E3A8A; box-shadow: 0 4px 14px rgba(30,58,138,0.28);
        }
        .stTabs [data-baseweb="tab-highlight"] { background: transparent !important; }

        /* --- Data tables --- */
        div.rtable table { border-collapse: collapse; width: 100%; font-family: Inter, sans-serif; }
        div.rtable th {
            background: linear-gradient(135deg, #1e3a8a 0%, #1d4ed8 100%) !important;
            font-weight: 700 !important; color: #ffffff !important;
            font-size: 15px !important; padding: 6px 14px !important;
            border: 1px solid #1e40af !important; text-align: left !important;
            letter-spacing: 0.25px;
        }
        div.rtable td { border: 1px solid #e2e8f0 !important; color: #1e293b; }
        div.rtable tr:hover td { background-color: #eff6ff !important; }
        div.rtable tr:nth-child(even) td { background-color: #f8fafc !important; }

        /* --- Section header accent bar --- */
        .sec-hdr {
            border-left: 4px solid #1E3A8A; padding: 5px 0 5px 14px;
            margin: 20px 0 10px 0;
        }
        .sec-hdr h4 { color: #0f172a; font-size: 17px; font-weight: 700; margin: 0; }
        .sec-hdr p  { color: #64748b; font-size: 12px; margin: 3px 0 0 0; }

        /* --- Insight callout box --- */
        .insight-box {
            background: linear-gradient(135deg, #eff6ff 0%, #f0fdf4 100%);
            border: 1px solid #bfdbfe; border-left: 5px solid #2563eb;
            border-radius: 8px; padding: 14px 18px; margin: 8px 0 14px 0;
        }
        .insight-box .ib-title {
            color: #1e40af; font-weight: 700; font-size: 12px;
            text-transform: uppercase; letter-spacing: 0.6px; margin-bottom: 6px;
        }
        .insight-box .ib-body { color: #1e293b; font-size: 14px; line-height: 1.65; }

        /* --- Metric card polish --- */
        [data-testid="metric-container"] {
            background: #ffffff; border: 1px solid #e2e8f0;
            border-top: 3px solid #1E3A8A; border-radius: 10px;
            padding: 14px 16px; box-shadow: 0 2px 8px rgba(0,0,0,0.05);
        }

        /* --- Container card shadow --- */
        [data-testid="stVerticalBlockBorderWrapper"] {
            border-radius: 10px !important;
            box-shadow: 0 1px 6px rgba(0,0,0,0.06) !important;
        }

        /* --- Sidebar --- */
        [data-testid="stSidebar"] { background-color: #f8fafc; width: 220px !important; min-width: 220px !important; }
        [data-testid="stSidebar"] > div:first-child { width: 220px !important; min-width: 220px !important; }
        </style>
    """, unsafe_allow_html=True)

inject_custom_css()

def render_table(styled_df, height=None):
    # color: #1e293b overrides any grey text pandas chose for gradient cells;
    # safe because _LC colormaps never produce backgrounds dark enough to need white text.
    s = styled_df.set_properties(**{'font-size': '15px', 'padding': '5px 14px', 'color': '#1e293b'})
    # Apply trend-arrow colours after the baseline so they win the cascade.
    if 'Trend' in styled_df.data.columns:
        s = s.map(
            lambda v: ('color: #16a34a; font-weight: 700' if v == '▲'
                  else 'color: #dc2626; font-weight: 700' if v == '▼'
                  else 'color: #64748b'),
            subset=['Trend'],
        )
    # Hide index when it's just 0,1,2… (meaningless); keep named index (pivot table labels)
    show_idx = not isinstance(styled_df.data.index, pd.RangeIndex)
    html = s.to_html(index=show_idx)
    h_style = f"max-height:{height}px; overflow-y:auto; " if height else ""
    st.markdown(
        f'<div class="rtable" style="{h_style}overflow-x:auto;">{html}</div>',
        unsafe_allow_html=True,
    )

def render_section_header(title, subtitle=None, icon=""):
    sub_html = f'<p>{subtitle}</p>' if subtitle else ""
    st.markdown(
        f'<div class="sec-hdr"><h4>{icon} {title}</h4>{sub_html}</div>',
        unsafe_allow_html=True,
    )

def render_insight_box(title, body):
    st.markdown(
        f'<div class="insight-box">'
        f'<div class="ib-title">{title}</div>'
        f'<div class="ib-body">{body}</div>'
        f'</div>',
        unsafe_allow_html=True,
    )

# Brand color sequence used consistently across all charts
PALETTE = ['#1E3A8A','#0ea5e9','#f97316','#16a34a','#7c3aed','#ec4899','#14b8a6','#f59e0b','#6366f1','#84cc16']

def style_high_end_chart(fig):
    fig.update_layout(
        font={'family': "Inter, sans-serif", 'color': '#334155', 'size': 13},
        title=dict(text='', font=dict(family="Inter, sans-serif", size=17, color='#0f172a')),
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(0,0,0,0)',
        margin=dict(t=64, l=48, r=36, b=56),
        xaxis=dict(showgrid=False, showline=True, linecolor='#e2e8f0', linewidth=1.5,
                   tickfont=dict(color='#64748b', size=12),
                   title_font=dict(size=13, color='#475569')),
        yaxis=dict(showgrid=True, gridcolor='#f1f5f9', gridwidth=1, showline=False,
                   tickfont=dict(color='#64748b', size=12),
                   title_font=dict(size=13, color='#475569')),
        legend=dict(
            orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1,
            font=dict(size=12), bgcolor='rgba(255,255,255,0.9)',
            bordercolor='#e2e8f0', borderwidth=1,
        ),
        hoverlabel=dict(bgcolor="white", font_size=13, font_family="Inter",
                        bordercolor='#cbd5e1'),
        colorway=PALETTE,
    )
    fig.update_xaxes(zeroline=False)
    fig.update_yaxes(zeroline=False)
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
APP_PASSWORD = "test2026"

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
    # Number of linear accelerators (LINACs) per site — used for per-machine productivity benchmarks.
    # TOPC is intentionally excluded (proton therapy, not LINAC-based).
    LINAC_CONFIG = {
        "CENT": 2, "Midtown": 2, "STW": 2, "MURF": 2,
        "Sumner": 1, "Dickson": 1, "Skyline": 1, "Summit": 1,
        "LROC": 1, "TROC": 1, "Stonecrest": 1,
    }

    PROVIDER_CONFIG = {
        "Burke": 1.0, "Castle": 0.6, "Chen": 1.0, "Cohen": 1.0,
        "Cooper": 1.0, "Ellis": 1.0, "Escott": 1.0, "Friedman": 1.0,
        "Gray": 1.0, "Jones": 1.0, "Lee": 1.0, "Lewis": 1.0, "Lipscomb": 0.6,
        "Lydon": 1.0, "Mayo": 1.0, "Mondschein": 1.0, "Nguyen": 1.0,
        "Osborne": 1.0, "Phillips": 1.0, "Sittig": 1.0,
        "Strickler": 1.0, "Wakefield": 1.0, "Wendt": 1.0, "Whitaker": 1.0,
    }
    # Physicians who left mid-year: labeled "(Ret.)" in tables, excluded from
    # trend/heatmap/distribution charts where partial data distorts the view.
    RETIRED_PROVIDERS = {"Wendt"}
    PROVIDER_KEYS_UPPER = {k.upper(): k for k in PROVIDER_CONFIG.keys()}
    APP_LIST = ["Burke", "Ellis", "Lewis", "Lydon"]

    TARGET_CATEGORIES = ["E&M OFFICE CODES", "RADIATION CODES", "SPECIAL PROCEDURES"]
    IGNORED_SHEETS   = ["RAD PHYSICIAN WORK RVUS", "COVER", "SHEET1", "TOTALS", "PROTON PHYSICIAN WORK RVUS",
                        "LROC PHYSICIAN WORK RVUS", "TROC PHYSICIAN WORK RVUS",
                        "LROC POS WORK RVUS", "TROC POS WORK RVUS"]
    SERVER_DIR       = "Reports"
    # Approximate MGMA Radiation Oncology physician benchmarks (annual wRVUs)
    MGMA_BENCHMARKS  = {"25th": 6500, "50th": 9000, "75th": 11500}

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
                # Exception: bare "Trend" sheet in LROC/TROC 2026 files is the productivity data
                if "TREND" in s_upper and "PRODUCTIVITY TREND" not in s_upper:
                    if not (s_upper == "TREND" and file_tag in ["LROC", "TROC"]):
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

                if "PRODUCTIVITY TREND" in s_upper or (s_upper == "TREND" and file_tag in ["LROC", "TROC"]):
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
                    grp = comb.groupby('Month_Clean', as_index=False)[['Total RVUs']].sum()
                    # Use the configured clinic FTE (2.5), not the sum of individual provider FTEs.
                    topc_fte = CLINIC_CONFIG.get("TOPC", {}).get("fte", 2.5)
                    topc_records = []
                    for _, row in grp.iterrows():
                        topc_records.append({
                            "Type": "clinic", "ID": "TOPC", "Name": "TN Proton Center",
                            "FTE": topc_fte, "Month_Clean": row['Month_Clean'],
                            "Total RVUs": row['Total RVUs'],
                            "RVU per FTE": row['Total RVUs'] / topc_fte,
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
            # Always use the canonical configured FTE — overrides any summed/wrong values
            # that may have come from individual provider roll-ups (e.g. TOPC).
            clinic_fte_map = {cid: cfg['fte'] for cid, cfg in CLINIC_CONFIG.items()}
            df_clinic['FTE'] = df_clinic['ID'].map(clinic_fte_map).fillna(df_clinic['FTE'])
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
        render_table(table.style.format("{:,.0f}"))

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
            render_table(ht.set_index('Year').T.style.format("{:,.0f}"))

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

    # ==========================================
    # EXECUTIVE SUMMARY RENDERER
    # ==========================================
    def render_executive_summary(year, df_clinic_all, df_mds_all, df_visits_all, df_financial):
        prior_year = year - 1
        df_cur  = df_clinic_all[df_clinic_all['Month_Clean'].dt.year == year].copy()  if not df_clinic_all.empty else pd.DataFrame()
        df_pri  = df_clinic_all[df_clinic_all['Month_Clean'].dt.year == prior_year].copy() if not df_clinic_all.empty else pd.DataFrame()
        df_mc   = df_mds_all[df_mds_all['Month_Clean'].dt.year == year].copy()        if not df_mds_all.empty   else pd.DataFrame()
        df_mp   = df_mds_all[df_mds_all['Month_Clean'].dt.year == prior_year].copy()  if not df_mds_all.empty   else pd.DataFrame()
        df_vc   = df_visits_all[df_visits_all['Month_Clean'].dt.year == year].copy()  if not df_visits_all.empty else pd.DataFrame()

        cur_months = set(df_cur['Month_Clean'].dt.month.unique()) if not df_cur.empty else set()
        df_pri_cmp = df_pri[df_pri['Month_Clean'].dt.month.isin(cur_months)] if not df_pri.empty else pd.DataFrame()
        df_mp_cmp  = df_mp[df_mp['Month_Clean'].dt.month.isin(cur_months)]   if not df_mp.empty  else pd.DataFrame()

        ytd_rvu   = df_cur['Total RVUs'].sum() if not df_cur.empty else 0
        pri_rvu   = df_pri_cmp['Total RVUs'].sum() if not df_pri_cmp.empty else 0
        yoy_pct   = (ytd_rvu - pri_rvu) / pri_rvu * 100 if pri_rvu > 0 else 0
        md_ytd    = df_mc['Total RVUs'].sum()  if not df_mc.empty else 0
        md_pri    = df_mp_cmp['Total RVUs'].sum() if not df_mp_cmp.empty else 0
        md_yoy    = (md_ytd - md_pri) / md_pri * 100 if md_pri > 0 else 0
        np_ytd    = df_vc['New Patients'].sum() if not df_vc.empty else 0
        n_months  = df_cur['Month_Clean'].dt.month.nunique() if not df_cur.empty else 0
        projected = ytd_rvu / n_months * 12 if n_months > 0 else 0
        n_mds     = df_mc['Name'].nunique()     if not df_mc.empty else 0
        n_sites   = df_cur['Name'].nunique()    if not df_cur.empty else 0

        # Derived efficiency KPIs
        fte_map_exec = {cid: cfg['fte'] for cid, cfg in CLINIC_CONFIG.items()}
        total_fte     = sum(fte_map_exec.values())
        net_rvu_fte   = ytd_rvu / total_fte if total_fte > 0 else 0
        app_ytd       = df_mds_all[
            (df_mds_all['Month_Clean'].dt.year == year) &
            (df_mds_all['Name'].isin(APP_LIST))
        ]['Total RVUs'].sum() if not df_mds_all.empty else 0
        app_pct       = app_ytd / ytd_rvu * 100 if ytd_rvu > 0 else 0
        md_pct        = md_ytd  / ytd_rvu * 100 if ytd_rvu > 0 else 0

        # Automated insight generation
        top_clinic    = df_cur.groupby('Name')['Total RVUs'].sum().idxmax() if not df_cur.empty else "—"
        top_fte_site  = (df_cur.groupby(['ID','Name'])['Total RVUs'].sum().reset_index()
                         .assign(FTE=lambda d: d['ID'].map(fte_map_exec).fillna(1.0))
                         .assign(wRVU_FTE=lambda d: d['Total RVUs'] / d['FTE'])
                         .sort_values('wRVU_FTE', ascending=False)['Name'].iloc[0]
                         if not df_cur.empty else "—")

        # Page header
        latest_lbl = df_cur['Month_Clean'].max().strftime('%B %Y') if not df_cur.empty else ""
        st.markdown(
            f"<h2 style='color:#0f172a;margin-bottom:2px;'>🩺 Radiation Oncology Division — {year} Executive Summary</h2>"
            f"<p style='color:#64748b;font-size:14px;margin-top:0;'>Data through <b>{latest_lbl}</b> &nbsp;·&nbsp; {n_months}-month YTD &nbsp;·&nbsp; {n_sites} active sites &nbsp;·&nbsp; {n_mds} active physicians</p>",
            unsafe_allow_html=True,
        )
        st.markdown("---")

        # ---- ROW 1: Volume KPIs ----
        render_section_header("Volume Metrics", "Year-to-date wRVU production across the network", "📊")
        k1, k2, k3, k4 = st.columns(4)
        with k1:
            st.metric("Network wRVUs YTD", f"{ytd_rvu:,.0f}",
                      delta=f"{yoy_pct:+.1f}% vs {prior_year}" if pri_rvu > 0 else None)
        with k2:
            st.metric(f"Projected {year} Annual", f"{projected:,.0f}",
                      help=f"Linear extrapolation from {n_months}-month YTD pace")
        with k3:
            st.metric("MD wRVUs YTD", f"{md_ytd:,.0f}",
                      delta=f"{md_yoy:+.1f}% vs {prior_year}" if md_pri > 0 else None,
                      help="Physician-attributed wRVUs only")
        with k4:
            st.metric("APP wRVUs YTD", f"{app_ytd:,.0f}",
                      help=f"Advanced Practice Provider contribution ({app_pct:.1f}% of network total)")

        # ---- ROW 2: Efficiency & Access KPIs ----
        render_section_header("Efficiency & Access Metrics", "Productivity intensity and patient access indicators", "⚡")
        k5, k6, k7, k8 = st.columns(4)
        with k5:
            st.metric("Network wRVU/FTE YTD", f"{net_rvu_fte:,.0f}",
                      help=f"Total network wRVUs ÷ {total_fte:.1f} aggregate FTE")
        with k6:
            st.metric("New Patients YTD", f"{np_ytd:,.0f}")
        with k7:
            st.metric("Active Physicians", str(n_mds))
        with k8:
            st.metric("Active Sites", str(n_sites))

        # ---- Automated Key Insights ----
        if ytd_rvu > 0:
            insight_lines = []
            if yoy_pct > 2:
                insight_lines.append(f"Network volume is <b>+{yoy_pct:.1f}% above {prior_year}</b> on a same-period basis, tracking favorably toward the projected annual total of {projected:,.0f} wRVUs.")
            elif yoy_pct < -2:
                insight_lines.append(f"Network volume is <b>{yoy_pct:.1f}% below {prior_year}</b> on a same-period basis — projected annual run rate of {projected:,.0f} wRVUs warrants monitoring.")
            else:
                insight_lines.append(f"Network volume is <b>approximately flat vs {prior_year}</b> ({yoy_pct:+.1f}%), with a projected annual run rate of {projected:,.0f} wRVUs.")
            if top_clinic != "—":
                insight_lines.append(f"Highest absolute volume: <b>{top_clinic}</b>. Highest efficiency (wRVU/FTE): <b>{top_fte_site}</b>.")
            render_insight_box("Key Network Insights", " &nbsp;·&nbsp; ".join(insight_lines))

        st.markdown("---")

        # ---- YoY Monthly Volume Chart ----
        if not df_cur.empty and not df_pri_cmp.empty:
            with st.container(border=True):
                render_section_header(f"Network wRVU Volume: {year} vs {prior_year}",
                                      "Monthly comparison — current year (dark blue) vs prior year (grey)", "📈")
                _MN = {1:'Jan',2:'Feb',3:'Mar',4:'Apr',5:'May',6:'Jun',
                       7:'Jul',8:'Aug',9:'Sep',10:'Oct',11:'Nov',12:'Dec'}
                nc = df_cur.groupby(df_cur['Month_Clean'].dt.month)['Total RVUs'].sum().reset_index()
                nc.columns = ['m','Total RVUs']; nc['Year'] = str(year)
                np2 = df_pri_cmp.groupby(df_pri_cmp['Month_Clean'].dt.month)['Total RVUs'].sum().reset_index()
                np2.columns = ['m','Total RVUs']; np2['Year'] = str(prior_year)
                yoy_df = pd.concat([nc, np2]).sort_values('m')
                yoy_df['Month'] = yoy_df['m'].map(_MN)
                fig_yoy = px.bar(yoy_df, x='Month', y='Total RVUs', color='Year', barmode='group',
                                 text_auto='.2s',
                                 color_discrete_map={str(year):'#1E3A8A', str(prior_year):'#94a3b8'},
                                 labels={'Total RVUs':'wRVUs'})
                st.plotly_chart(style_high_end_chart(fig_yoy), use_container_width=True,
                                key=f"exec_yoy_{year}")

        # ---- Multi-Year Trend (CAGR) ----
        with st.container(border=True):
            render_section_header("Multi-Year Network Volume Trend",
                                  "Historical annual wRVUs with compound annual growth rate (CAGR)", "📉")
            hist_years = sorted(HISTORICAL_DATA.keys())
            hist_totals = []
            for hy in hist_years:
                total_hy = sum(HISTORICAL_DATA[hy].values())
                hist_totals.append({'Year': str(hy), 'Total RVUs': total_hy, 'Type': 'Historical'})
            hist_df = pd.DataFrame(hist_totals)
            # Append current YTD projected
            if projected > 0:
                proj_row = pd.DataFrame([{'Year': f"{year} (proj)", 'Total RVUs': projected, 'Type': 'Projected'}])
                hist_df = pd.concat([hist_df, proj_row], ignore_index=True)
            # Compute CAGR
            first_val = hist_df[hist_df['Type']=='Historical']['Total RVUs'].iloc[0]
            last_hist  = hist_df[hist_df['Type']=='Historical']['Total RVUs'].iloc[-1]
            n_yr       = len(hist_df[hist_df['Type']=='Historical']) - 1
            cagr       = (last_hist / first_val) ** (1 / n_yr) - 1 if n_yr > 0 and first_val > 0 else 0
            fig_hist = px.bar(hist_df, x='Year', y='Total RVUs',
                              color='Type', text_auto='.3s',
                              color_discrete_map={'Historical':'#1E3A8A','Projected':'#93c5fd'},
                              labels={'Total RVUs':'Annual wRVUs'})
            fig_hist.update_layout(showlegend=True)
            st.plotly_chart(style_high_end_chart(fig_hist), use_container_width=True,
                            key=f"exec_hist_{year}")
            st.caption(f"CAGR ({hist_years[0]}–{hist_years[-1]}): **{cagr:+.1%}** per year. Projected {year} based on {n_months}-month YTD linear extrapolation.")

        # ---- Clinic Performance Scorecard ----
        if not df_cur.empty:
            with st.container(border=True):
                render_section_header("Clinic Performance Scorecard",
                                      "Year-to-date wRVU volume and efficiency by site — sorted by total volume", "🏆")
                fte_map = {cid: cfg['fte'] for cid, cfg in CLINIC_CONFIG.items()}
                sc = df_cur.groupby(['ID','Name'])['Total RVUs'].sum().reset_index()
                sc['FTE'] = sc['ID'].map(fte_map).fillna(1.0)
                sc['wRVU/FTE'] = sc['Total RVUs'] / sc['FTE']
                sc['% of Network'] = sc['Total RVUs'] / sc['Total RVUs'].sum()
                sc['LINACs'] = sc['ID'].map(LINAC_CONFIG)
                sc['wRVU/LINAC'] = sc['Total RVUs'] / sc['LINACs']   # NaN for TOPC (proton, no LINAC)
                if not df_pri_cmp.empty:
                    ps = df_pri_cmp.groupby('ID')['Total RVUs'].sum().reset_index().rename(columns={'Total RVUs':'Prior RVUs'})
                    sc = sc.merge(ps, on='ID', how='left').fillna({'Prior RVUs': 0})
                    sc['YoY Δ']  = sc.apply(lambda r: (r['Total RVUs']-r['Prior RVUs'])/r['Prior RVUs'] if r['Prior RVUs']>0 else 0, axis=1)
                    sc['Trend']  = sc['YoY Δ'].apply(lambda x: '▲' if x>0.02 else ('▼' if x<-0.02 else '→'))
                    disp_cols = ['Name','Total RVUs','% of Network','FTE','wRVU/FTE','wRVU/LINAC','Prior RVUs','YoY Δ','Trend']
                    fmt_sc = {'Total RVUs':'{:,.0f}','% of Network':'{:.1%}','FTE':'{:.1f}',
                              'wRVU/FTE':'{:,.0f}','wRVU/LINAC':'{:,.0f}','Prior RVUs':'{:,.0f}','YoY Δ':'{:+.1%}'}
                else:
                    disp_cols = ['Name','Total RVUs','% of Network','FTE','wRVU/FTE','wRVU/LINAC']
                    fmt_sc = {'Total RVUs':'{:,.0f}','% of Network':'{:.1%}','FTE':'{:.1f}',
                              'wRVU/FTE':'{:,.0f}','wRVU/LINAC':'{:,.0f}'}
                sc = sc.sort_values('Total RVUs', ascending=False)
                sc_disp = sc[disp_cols].copy()
                sc_disp['% of Network'] = (sc_disp['% of Network'] * 100).round(1)
                if 'YoY Δ' in sc_disp.columns:
                    sc_disp['YoY Δ'] = (sc_disp['YoY Δ'] * 100).round(1)
                col_cfg = {
                    "Total RVUs":    st.column_config.NumberColumn("Total RVUs",    format="%,.0f"),
                    "% of Network":  st.column_config.NumberColumn("% of Network",  format="%.1f %%"),
                    "FTE":           st.column_config.NumberColumn("FTE",           format="%.1f"),
                    "wRVU/FTE":      st.column_config.NumberColumn("wRVU/FTE",      format="%,.0f"),
                    "wRVU/LINAC":    st.column_config.NumberColumn("wRVU/LINAC",    format="%,.0f"),
                    "Prior RVUs":    st.column_config.NumberColumn("Prior RVUs",    format="%,.0f"),
                    "YoY Δ":         st.column_config.NumberColumn("YoY Δ",         format="%+.1f %%"),
                }
                sc_styled = sc_disp.style
                if 'Trend' in sc_disp.columns:
                    sc_styled = sc_styled.map(
                        lambda v: ('color: #16a34a; font-weight: bold' if v == '▲'
                              else 'color: #dc2626; font-weight: bold' if v == '▼'
                              else 'color: #94a3b8'),
                        subset=['Trend'],
                    )
                sc_height = (len(sc_disp) + 1) * 36 + 4  # header row + data rows + border
                st.dataframe(sc_styled, hide_index=True, use_container_width=True,
                             height=sc_height, column_config=col_cfg)
                st.caption("Click any column header to sort. wRVU/FTE = efficiency metric; higher values indicate greater productivity intensity relative to physician effort.")

        # ---- Physician Productivity Scorecard ----
        if not df_mc.empty:
            with st.container(border=True):
                render_section_header("Physician Productivity Scorecard",
                                      f"Individual physician wRVU production benchmarked against MGMA Radiation Oncology norms ({n_months}-month YTD)", "👨‍⚕️")
                msc = df_mc.groupby('Name').agg({'Total RVUs':'sum','FTE':'max'}).reset_index()
                msc['wRVU/FTE'] = msc['Total RVUs'] / msc['FTE']
                mgma_50_ytd = MGMA_BENCHMARKS['50th'] / 12 * n_months if n_months > 0 else MGMA_BENCHMARKS['50th']
                mgma_25_ytd = MGMA_BENCHMARKS['25th'] / 12 * n_months if n_months > 0 else MGMA_BENCHMARKS['25th']
                mgma_75_ytd = MGMA_BENCHMARKS['75th'] / 12 * n_months if n_months > 0 else MGMA_BENCHMARKS['75th']
                msc['vs MGMA 50th'] = msc['Total RVUs'] / mgma_50_ytd - 1
                msc['Productivity Tier'] = msc['Total RVUs'].apply(
                    lambda x: '🥇 Elite (>75th)' if x > mgma_75_ytd
                    else ('✅ Above Avg (50–75th)' if x > mgma_50_ytd
                    else ('⚠️ Average (25–50th)' if x > mgma_25_ytd
                    else '🔴 Below Avg (<25th)')))
                if not df_mp_cmp.empty:
                    pm = df_mp_cmp.groupby('Name')['Total RVUs'].sum().reset_index().rename(columns={'Total RVUs':'Prior RVUs'})
                    msc = msc.merge(pm, on='Name', how='left').fillna({'Prior RVUs':0})
                    msc['YoY Δ'] = msc.apply(lambda r: (r['Total RVUs']-r['Prior RVUs'])/r['Prior RVUs'] if r['Prior RVUs']>0 else 0, axis=1)
                    msc['Trend'] = msc['YoY Δ'].apply(lambda x: '▲' if x>0.02 else ('▼' if x<-0.02 else '→'))
                    m_cols = ['Name','Total RVUs','wRVU/FTE','vs MGMA 50th','Productivity Tier','Prior RVUs','YoY Δ','Trend']
                    fmt_m = {'Total RVUs':'{:,.0f}','wRVU/FTE':'{:,.0f}','vs MGMA 50th':'{:+.1%}',
                             'Prior RVUs':'{:,.0f}','YoY Δ':'{:+.1%}'}
                else:
                    m_cols = ['Name','Total RVUs','wRVU/FTE','vs MGMA 50th','Productivity Tier']
                    fmt_m = {'Total RVUs':'{:,.0f}','wRVU/FTE':'{:,.0f}','vs MGMA 50th':'{:+.1%}'}
                msc = msc.sort_values('Total RVUs', ascending=False)
                render_table(msc[m_cols].style.format(fmt_m)
                             .background_gradient(subset=['vs MGMA 50th'], cmap=_LC['RdYlGn']))
                elite_n = (msc['Total RVUs'] > mgma_75_ytd).sum()
                above_n = ((msc['Total RVUs'] > mgma_50_ytd) & (msc['Total RVUs'] <= mgma_75_ytd)).sum()
                st.caption(
                    f"MGMA benchmarks scaled to {n_months}-month YTD — 25th: {mgma_25_ytd:,.0f} | 50th: {mgma_50_ytd:,.0f} | 75th: {mgma_75_ytd:,.0f} wRVUs. "
                    f"**{elite_n}** physician(s) above 75th percentile; **{above_n}** between 50th–75th. "
                    f"Approximate Radiation Oncology MGMA benchmarks."
                )

        # ---- Year-End Projection by Clinic ----
        if not df_cur.empty and 0 < n_months < 12:
            with st.container(border=True):
                render_section_header(f"{year} Year-End Projection by Site",
                                      f"Linear extrapolation from {n_months}-month YTD pace — compared against prior full year", "🎯")
                fte_map2 = {cid: cfg['fte'] for cid, cfg in CLINIC_CONFIG.items()}
                proj_rows = []
                for (cid, cname), grp in df_cur.groupby(['ID','Name']):
                    ytd_c  = grp['Total RVUs'].sum()
                    proj_c = ytd_c / n_months * 12
                    fte_c  = fte_map2.get(cid, 1.0)
                    prior_full = df_pri[df_pri['ID']==cid]['Total RVUs'].sum() if not df_pri.empty else 0
                    proj_rows.append({'Clinic':cname, 'YTD':ytd_c, 'Projected Annual':proj_c,
                                      'Proj/FTE':proj_c/fte_c,
                                      'Prior Year':prior_full,
                                      'Δ vs Prior':( proj_c-prior_full)/prior_full if prior_full>0 else 0})
                proj_df = pd.DataFrame(proj_rows).sort_values('Projected Annual', ascending=False)
                fig_proj = px.bar(
                    proj_df.melt(id_vars='Clinic', value_vars=['YTD','Projected Annual']),
                    x='Clinic', y='value', color='variable', barmode='group', text_auto='.2s',
                    color_discrete_sequence=['#1E3A8A','#93c5fd'],
                    labels={'value':'wRVUs','variable':''})
                st.plotly_chart(style_high_end_chart(fig_proj), use_container_width=True,
                                key=f"exec_proj_{year}")
                fmt_p = {'YTD':'{:,.0f}','Projected Annual':'{:,.0f}','Proj/FTE':'{:,.0f}',
                         'Prior Year':'{:,.0f}','Δ vs Prior':'{:+.1%}'}
                render_table(proj_df.style.format(fmt_p)
                             .background_gradient(subset=['Projected Annual','Δ vs Prior'], cmap=_LC['Greens']))
                st.caption("Δ vs Prior compares projected annual pace against the full prior calendar year — positive values indicate growth trajectory.")

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

            # --- Network peer comparison (LROC / TROC / TOPC) ---
            if clinic_filter in ["LROC", "TROC", "TOPC"] and not df_clinic_yr.empty:
                st.markdown("---")
                with st.container(border=True):
                    render_section_header(
                        f"{view_title}: Network Peer Comparison",
                        f"How {view_title} ranks against all network centers on productivity and patient volume — YTD {year}",
                        "🔍"
                    )
                    _fte_map = {cid: cfg['fte'] for cid, cfg in CLINIC_CONFIG.items()}
                    net_ytd = (df_clinic_yr.groupby('ID')
                               .agg(Total_RVUs=('Total RVUs', 'sum'), Name=('Name', 'first'))
                               .reset_index())
                    net_ytd['FTE']      = net_ytd['ID'].map(_fte_map).fillna(1.0)
                    net_ytd['wRVU_FTE'] = net_ytd['Total_RVUs'] / net_ytd['FTE']
                    net_avg_fte = net_ytd['Total_RVUs'].sum() / net_ytd['FTE'].sum()

                    tgt_row     = net_ytd[net_ytd['ID'] == clinic_filter].iloc[0]
                    fte_rank    = int(net_ytd['wRVU_FTE'].rank(ascending=False)[net_ytd['ID'] == clinic_filter].iloc[0])
                    vol_rank    = int(net_ytd['Total_RVUs'].rank(ascending=False)[net_ytd['ID'] == clinic_filter].iloc[0])
                    n_ctr       = len(net_ytd)
                    pct_vs_avg  = (tgt_row['wRVU_FTE'] / net_avg_fte - 1) * 100

                    mc1, mc2, mc3 = st.columns(3)
                    with mc1:
                        st.metric("wRVU/FTE Rank", f"#{fte_rank} of {n_ctr} Centers")
                    with mc2:
                        st.metric("Total wRVU Rank", f"#{vol_rank} of {n_ctr} Centers",
                                  f"{tgt_row['Total_RVUs']:,.0f} wRVUs YTD")
                    with mc3:
                        st.metric("vs. Network Avg wRVU/FTE",
                                  f"{tgt_row['wRVU_FTE']:,.0f}",
                                  f"{pct_vs_avg:+.1f}% (avg: {net_avg_fte:,.0f})")

                    # wRVU/FTE horizontal bar — target in brand blue, others muted
                    net_plot   = net_ytd.sort_values('wRVU_FTE', ascending=True)
                    bar_colors = ['#1E3A8A' if i == clinic_filter else '#cbd5e1' for i in net_plot['ID']]
                    fig_fte_cmp = go.Figure(go.Bar(
                        x=net_plot['wRVU_FTE'], y=net_plot['Name'],
                        orientation='h', marker_color=bar_colors,
                        text=[f"{v:,.0f}" for v in net_plot['wRVU_FTE']],
                        textposition='outside', cliponaxis=False,
                        hovertemplate='<b>%{y}</b><br>wRVU/FTE: %{x:,.0f}<extra></extra>',
                    ))
                    fig_fte_cmp.add_vline(x=net_avg_fte, line_dash='dash', line_color='#f97316', line_width=2,
                                          annotation_text=f"Network Avg  {net_avg_fte:,.0f}",
                                          annotation_position="top right")
                    fig_fte_cmp.update_layout(
                        title=f"YTD wRVU/FTE — {view_title} vs. All Centers ({year})",
                        xaxis_title="wRVU per FTE (YTD)", yaxis_title="",
                        height=max(320, len(net_plot) * 36 + 80),
                    )
                    st.plotly_chart(style_high_end_chart(fig_fte_cmp), use_container_width=True,
                                    key=f"net_fte_{tab_key_suffix}")

                    # New patients/FTE comparison (if visit data available)
                    if not df_pos_trend.empty:
                        df_pos_cmp = df_pos_trend[df_pos_trend['Month_Clean'].dt.year == year].copy()
                        if not df_pos_cmp.empty:
                            np_ytd = (df_pos_cmp.groupby('Clinic_Tag')
                                      .agg(New_Patients=('New Patients', 'sum'))
                                      .reset_index())
                            np_ytd['Name'] = np_ytd['Clinic_Tag'].apply(
                                lambda x: CLINIC_CONFIG.get(x, {}).get('name', x))
                            np_ytd['FTE']       = np_ytd['Clinic_Tag'].map(_fte_map).fillna(1.0)
                            np_ytd['NP_per_FTE'] = np_ytd['New_Patients'] / np_ytd['FTE']
                            np_avg  = np_ytd['New_Patients'].sum() / np_ytd['FTE'].sum()
                            np_plot = np_ytd.sort_values('NP_per_FTE', ascending=True)
                            np_colors = ['#16a34a' if i == clinic_filter else '#cbd5e1'
                                         for i in np_plot['Clinic_Tag']]

                            fig_np_cmp = go.Figure(go.Bar(
                                x=np_plot['NP_per_FTE'], y=np_plot['Name'],
                                orientation='h', marker_color=np_colors,
                                text=[f"{v:.1f}" for v in np_plot['NP_per_FTE']],
                                textposition='outside', cliponaxis=False,
                                hovertemplate='<b>%{y}</b><br>New Patients/FTE: %{x:.1f}<extra></extra>',
                            ))
                            fig_np_cmp.add_vline(x=np_avg, line_dash='dash', line_color='#f97316', line_width=2,
                                                 annotation_text=f"Network Avg  {np_avg:.1f}",
                                                 annotation_position="top right")
                            fig_np_cmp.update_layout(
                                title=f"YTD New Patients/FTE — {view_title} vs. All Centers ({year})",
                                xaxis_title="New Patients per FTE (YTD)", yaxis_title="",
                                height=max(320, len(np_plot) * 36 + 80),
                            )
                            st.plotly_chart(style_high_end_chart(fig_np_cmp), use_container_width=True,
                                            key=f"net_np_{tab_key_suffix}")

                            if clinic_filter in np_ytd['Clinic_Tag'].values:
                                tgt_np     = np_ytd[np_ytd['Clinic_Tag'] == clinic_filter].iloc[0]
                                np_rank    = int(np_ytd['NP_per_FTE'].rank(ascending=False)[np_ytd['Clinic_Tag'] == clinic_filter].iloc[0])
                                pct_np_avg = (tgt_np['NP_per_FTE'] / np_avg - 1) * 100 if np_avg > 0 else 0
                                nc1, nc2 = st.columns(2)
                                with nc1:
                                    st.metric("New Patient/FTE Rank", f"#{np_rank} of {len(np_ytd)} Centers")
                                with nc2:
                                    st.metric("vs. Network Avg New Patients/FTE",
                                              f"{tgt_np['NP_per_FTE']:.1f}",
                                              f"{pct_np_avg:+.1f}% (avg: {np_avg:.1f})")

                    # wRVU/LINAC comparison (LINAC centers only — excludes TOPC)
                    linac_cmp = net_ytd[net_ytd['ID'].isin(LINAC_CONFIG)].copy()
                    linac_cmp['LINACs']     = linac_cmp['ID'].map(LINAC_CONFIG)
                    linac_cmp['wRVU_LINAC'] = linac_cmp['Total_RVUs'] / linac_cmp['LINACs']
                    linac_avg = linac_cmp['Total_RVUs'].sum() / linac_cmp['LINACs'].sum()
                    linac_plot = linac_cmp.sort_values('wRVU_LINAC', ascending=True)
                    linac_colors = ['#7c3aed' if i == clinic_filter else '#cbd5e1'
                                    for i in linac_plot['ID']]
                    fig_linac = go.Figure(go.Bar(
                        x=linac_plot['wRVU_LINAC'], y=linac_plot['Name'],
                        orientation='h', marker_color=linac_colors,
                        text=[f"{v:,.0f}" for v in linac_plot['wRVU_LINAC']],
                        textposition='outside', cliponaxis=False,
                        customdata=linac_plot['LINACs'].values,
                        hovertemplate='<b>%{y}</b><br>wRVU/LINAC: %{x:,.0f}<br>LINACs: %{customdata}<extra></extra>',
                    ))
                    fig_linac.add_vline(x=linac_avg, line_dash='dash', line_color='#f97316', line_width=2,
                                        annotation_text=f"LINAC Avg  {linac_avg:,.0f}",
                                        annotation_position="top right")
                    fig_linac.update_layout(
                        title=f"YTD wRVU/LINAC — {view_title} vs. LINAC Centers ({year})",
                        xaxis_title="wRVU per LINAC (YTD)", yaxis_title="",
                        height=max(300, len(linac_plot) * 36 + 80),
                    )
                    st.plotly_chart(style_high_end_chart(fig_linac), use_container_width=True,
                                    key=f"net_linac_{tab_key_suffix}")
                    if clinic_filter in LINAC_CONFIG:
                        tgt_linac = linac_cmp[linac_cmp['ID'] == clinic_filter].iloc[0]
                        linac_rank = int(linac_cmp['wRVU_LINAC'].rank(ascending=False)[linac_cmp['ID'] == clinic_filter].iloc[0])
                        pct_linac_avg = (tgt_linac['wRVU_LINAC'] / linac_avg - 1) * 100
                        lc1, lc2, lc3 = st.columns(3)
                        with lc1:
                            st.metric("wRVU/LINAC Rank", f"#{linac_rank} of {len(linac_cmp)} LINAC Centers")
                        with lc2:
                            st.metric("wRVU/LINAC", f"{tgt_linac['wRVU_LINAC']:,.0f}",
                                      f"{pct_linac_avg:+.1f}% vs avg ({linac_avg:,.0f})")
                        with lc3:
                            st.metric("LINACs at This Site", int(tgt_linac['LINACs']))

                    # Summary comparison table (sortable — all centers + LINAC column where applicable)
                    net_tbl = net_ytd[['Name','ID','Total_RVUs','FTE','wRVU_FTE']].copy()
                    net_tbl['wRVU/FTE Rank']    = net_tbl['wRVU_FTE'].rank(ascending=False).astype(int)
                    net_tbl['vs. Avg wRVU/FTE'] = (net_tbl['wRVU_FTE'] / net_avg_fte - 1) * 100
                    net_tbl['LINACs']           = net_tbl['ID'].map(LINAC_CONFIG)
                    net_tbl['wRVU/LINAC']       = net_tbl['Total_RVUs'] / net_tbl['LINACs']
                    net_tbl['wRVU/LINAC Rank']  = net_tbl['wRVU/LINAC'].rank(ascending=False)
                    net_tbl = net_tbl.sort_values('wRVU_FTE', ascending=False)
                    net_tbl_disp = (net_tbl[['Name','Total_RVUs','FTE','wRVU_FTE',
                                             'vs. Avg wRVU/FTE','LINACs','wRVU/LINAC',
                                             'wRVU/FTE Rank','wRVU/LINAC Rank']]
                                    .rename(columns={'Total_RVUs':'Total wRVUs','wRVU_FTE':'wRVU/FTE'}))
                    tbl_styled = (net_tbl_disp.style
                                  .background_gradient(subset=['wRVU/FTE'],          cmap=_LC['Blues'])
                                  .background_gradient(subset=['vs. Avg wRVU/FTE'],  cmap=_LC['RdYlGn'])
                                  .background_gradient(subset=['wRVU/LINAC'],        cmap=_LC['Purples']))
                    tbl_col_cfg = {
                        "Total wRVUs":       st.column_config.NumberColumn("Total wRVUs",       format="%,.0f"),
                        "FTE":               st.column_config.NumberColumn("FTE",               format="%.1f"),
                        "wRVU/FTE":          st.column_config.NumberColumn("wRVU/FTE",          format="%,.0f"),
                        "vs. Avg wRVU/FTE":  st.column_config.NumberColumn("vs. Avg wRVU/FTE",  format="%+.1f %%"),
                        "LINACs":            st.column_config.NumberColumn("LINACs",            format="%.0f"),
                        "wRVU/LINAC":        st.column_config.NumberColumn("wRVU/LINAC",        format="%,.0f"),
                        "wRVU/FTE Rank":     st.column_config.NumberColumn("wRVU/FTE Rank",     format="%d"),
                        "wRVU/LINAC Rank":   st.column_config.NumberColumn("wRVU/LINAC Rank",   format="%d"),
                    }
                    st.dataframe(tbl_styled, hide_index=True, use_container_width=True,
                                 height=(len(net_tbl_disp) + 1) * 36 + 4,
                                 column_config=tbl_col_cfg)
                    st.caption("Click any column header to sort.")

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
                            render_table(piv.sort_values("Total", ascending=False).style
                                         .format("{:,.0f}").background_gradient(cmap=_LC['Blues']))

                    # Historical summary
                    with st.container(border=True):
                        st.markdown("##### 📅 Historical Data Summary")
                        render_historical_summary(clinic_filter, year, df_view, TRISTAR_IDS, ASCENSION_IDS)

                    # Monthly & quarterly pivot tables
                    if not df_view.empty:
                        with st.container(border=True):
                            st.markdown("#### 🔢 Monthly Data")
                            piv_m = df_view.pivot_table(index="Name", columns="Month_Label", values="Total RVUs", aggfunc="sum").fillna(0)
                            sorted_m2 = df_view.sort_values("Month_Clean")["Month_Label"].unique()
                            piv_m = piv_m.reindex(columns=sorted_m2).fillna(0)
                            piv_m["Total"] = piv_m.sum(axis=1)
                            render_table(piv_m.sort_values("Total", ascending=False).style
                                         .format("{:,.0f}").background_gradient(cmap=_LC['Reds']))
                        with st.container(border=True):
                            st.markdown("#### 📆 Quarterly Data")
                            piv_q = df_view.pivot_table(index="Name", columns="Quarter", values="Total RVUs", aggfunc="sum").fillna(0)
                            piv_q["Total"] = piv_q.sum(axis=1)
                            render_table(piv_q.sort_values("Total", ascending=False).style
                                         .format("{:,.0f}").background_gradient(cmap=_LC['Oranges']))

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
                    render_table(piv_np.style.format("{:,.0f}").background_gradient(cmap=_LC['Greens']))

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
                                         color='RVU per FTE', color_continuous_scale=[[0,'#bfdbfe'],[1,'#1E3A8A']],
                                         title=f"wRVU per FTE: {max_dt_fte.strftime('%B %Y')}")
                        fig_fte.update_layout(coloraxis_showscale=False)
                        st.plotly_chart(style_high_end_chart(fig_fte), use_container_width=True,
                                        key=f"fte_{tab_key_suffix}")
                        div_avg = df_fte_latest['Total RVUs'].sum() / df_fte_latest['FTE'].sum() if df_fte_latest['FTE'].sum() > 0 else 0
                        st.caption(f"**Division Average:** {div_avg:,.0f} wRVU/FTE")

            # --- wRVU/LINAC efficiency (All view, LINAC centers only) ---
            if clinic_filter == "All" and not df_clinic_yr.empty:
                with st.container(border=True):
                    render_section_header(f"LINAC Productivity: wRVU per Machine ({year})",
                                          "YTD wRVU output normalized by number of linear accelerators — excludes TN Proton Center (proton therapy)", "⚙️")
                    linac_ytd = (df_clinic_yr[df_clinic_yr['ID'].isin(LINAC_CONFIG)]
                                 .groupby(['ID','Name'])['Total RVUs'].sum().reset_index())
                    linac_ytd['LINACs']     = linac_ytd['ID'].map(LINAC_CONFIG)
                    linac_ytd['wRVU/LINAC'] = linac_ytd['Total RVUs'] / linac_ytd['LINACs']
                    linac_net_avg = linac_ytd['Total RVUs'].sum() / linac_ytd['LINACs'].sum()
                    linac_ytd_plot = linac_ytd.sort_values('wRVU/LINAC', ascending=False)
                    fig_linac_all = px.bar(linac_ytd_plot, x='Name', y='wRVU/LINAC',
                                           text_auto='.2s',
                                           color='wRVU/LINAC',
                                           color_continuous_scale=[[0,'#ede9fe'],[1,'#7c3aed']],
                                           title=f"YTD wRVU per LINAC by Center — {year}")
                    fig_linac_all.add_hline(y=linac_net_avg, line_dash='dash', line_color='#f97316', line_width=2,
                                            annotation_text=f"Network Avg  {linac_net_avg:,.0f}",
                                            annotation_position="top right")
                    fig_linac_all.update_layout(coloraxis_showscale=False)
                    fig_linac_all.update_traces(textposition='outside', cliponaxis=False)
                    st.plotly_chart(style_high_end_chart(fig_linac_all), use_container_width=True,
                                    key=f"linac_all_{tab_key_suffix}")
                    st.caption(f"**Network LINAC Average:** {linac_net_avg:,.0f} wRVU/LINAC YTD &nbsp;·&nbsp; "
                               f"Centers with 2 LINACs: Centennial, ST Midtown, ST West, ST Rutherford")

            # --- FIX #4: Dynamic quarterly comparison (All view) ---
            if clinic_filter == "All" and not df_clinic_yr.empty:
                target_q = get_most_recent_quarter(df_clinic_yr)   # Was hardcoded "Q1 2026"
                if target_q:
                    df_q_data = df_clinic_yr[df_clinic_yr['Quarter'] == target_q].copy()
                    if not df_q_data.empty:
                        st.markdown("---")
                        with st.container(border=True):
                            st.markdown(f"#### 📊 Total wRVU Volume: {target_q}")
                            df_q_sum = df_q_data.groupby('ID').agg(
                                {'Total RVUs': 'sum', 'Name': 'first'}
                            ).reset_index()
                            fig_qv = px.bar(df_q_sum.sort_values('Total RVUs', ascending=False),
                                            x='Name', y='Total RVUs', text_auto='.2s',
                                            color='Total RVUs', color_continuous_scale=[[0,'#bfdbfe'],[1,'#1E3A8A']],
                                            title=f"Total Center Volume ({target_q})")
                            fig_qv.update_layout(coloraxis_showscale=False)
                            st.plotly_chart(style_high_end_chart(fig_qv), use_container_width=True,
                                            key=f"qvol_{tab_key_suffix}")
                        with st.container(border=True):
                            st.markdown(f"#### 🩺 Efficiency: wRVU per FTE: {target_q}")
                            df_q_eff = df_q_data.groupby('ID').agg(
                                {'Total RVUs': 'sum', 'Name': 'first'}
                            ).reset_index()
                            _fte_map = {cid: cfg['fte'] for cid, cfg in CLINIC_CONFIG.items()}
                            df_q_eff['FTE'] = df_q_eff['ID'].map(_fte_map).fillna(1.0)
                            df_q_eff['RVU per FTE'] = df_q_eff.apply(
                                lambda x: x['Total RVUs'] / x['FTE'] if x['FTE'] > 0 else 0, axis=1)
                            fig_qe = px.bar(df_q_eff.sort_values('RVU per FTE', ascending=False),
                                            x='Name', y='RVU per FTE', text_auto='.0f',
                                            color='RVU per FTE', color_continuous_scale=[[0,'#bfdbfe'],[1,'#1E3A8A']],
                                            title=f"Quarterly wRVU per FTE ({target_q})")
                            fig_qe.update_layout(coloraxis_showscale=False)
                            st.plotly_chart(style_high_end_chart(fig_qe), use_container_width=True,
                                            key=f"qeff_{tab_key_suffix}")

            # ==========================================
            # ADVANCED ANALYTICS (multi-clinic views)
            # ==========================================
            if clinic_filter in ["All", "TriStar", "Ascension"] and not df_view.empty:
                prior_year   = year - 1
                df_pri_all   = df_clinic_all[df_clinic_all['Month_Clean'].dt.year == prior_year].copy() if not df_clinic_all.empty else pd.DataFrame()
                if   clinic_filter == "TriStar":   df_vp = df_pri_all[df_pri_all['ID'].isin(TRISTAR_IDS)]
                elif clinic_filter == "Ascension": df_vp = df_pri_all[df_pri_all['ID'].isin(ASCENSION_IDS)]
                else:                              df_vp = df_pri_all.copy()
                cur_m_set = set(df_view['Month_Clean'].dt.month.unique())
                df_vp_cmp = df_vp[df_vp['Month_Clean'].dt.month.isin(cur_m_set)] if not df_vp.empty else pd.DataFrame()
                n_m_adv   = df_view['Month_Clean'].dt.month.nunique()

                st.markdown("---")
                render_section_header("Advanced Analytics",
                                      "Statistical, comparative, and concentration analysis", "📐")

                # Pareto / concentration analysis --------------------------------
                with st.container(border=True):
                    render_section_header("Volume Concentration Analysis (Pareto)",
                                          "How many sites generate 80% of total wRVU volume?", "📊")
                    par = df_view.groupby('Name')['Total RVUs'].sum().reset_index()
                    par = par.sort_values('Total RVUs', ascending=False).reset_index(drop=True)
                    par['Cumulative %'] = par['Total RVUs'].cumsum() / par['Total RVUs'].sum() * 100
                    par['Rank'] = par.index + 1
                    fig_par = go.Figure()
                    fig_par.add_trace(go.Bar(
                        x=par['Name'], y=par['Total RVUs'],
                        name='wRVUs', marker_color='#1E3A8A', text=par['Total RVUs'].apply(lambda v: f"{v:,.0f}"),
                        textposition='outside'))
                    fig_par.add_trace(go.Scatter(
                        x=par['Name'], y=par['Cumulative %'],
                        name='Cumulative %', yaxis='y2', mode='lines+markers',
                        line=dict(color='#f97316', width=2), marker=dict(size=7)))
                    fig_par.update_layout(
                        yaxis=dict(title='wRVUs'),
                        yaxis2=dict(title='Cumulative %', overlaying='y', side='right',
                                    tickformat='.0f', range=[0,110]),
                        title=f"Pareto Chart: wRVU Volume by Clinic ({year} YTD)",
                        legend=dict(orientation="h", y=1.08))
                    st.plotly_chart(style_high_end_chart(fig_par), use_container_width=True,
                                    key=f"adv_pareto_{tab_key_suffix}_{clinic_filter}")
                    sites_80 = int((par['Cumulative %'] <= 80).sum()) + 1
                    total_sites = len(par)
                    st.caption(
                        f"**{sites_80} of {total_sites} sites** ({sites_80/total_sites:.0%}) account for ≥80% of total wRVU volume "
                        f"— a {'concentrated' if sites_80/total_sites < 0.5 else 'distributed'} production profile."
                    )

                # YoY monthly comparison ----------------------------------------
                if not df_vp_cmp.empty:
                    with st.container(border=True):
                        render_section_header(f"Year-over-Year: {year} vs {prior_year}",
                                              "Monthly and site-level comparison on matched periods", "📅")
                        _MN = {1:'Jan',2:'Feb',3:'Mar',4:'Apr',5:'May',6:'Jun',
                               7:'Jul',8:'Aug',9:'Sep',10:'Oct',11:'Nov',12:'Dec'}
                        nc2 = df_view.groupby(df_view['Month_Clean'].dt.month)['Total RVUs'].sum().reset_index()
                        nc2.columns = ['m','Total RVUs']; nc2['Year'] = str(year)
                        np3 = df_vp_cmp.groupby(df_vp_cmp['Month_Clean'].dt.month)['Total RVUs'].sum().reset_index()
                        np3.columns = ['m','Total RVUs']; np3['Year'] = str(prior_year)
                        yoy_c = pd.concat([nc2, np3]).sort_values('m')
                        yoy_c['Month'] = yoy_c['m'].map(_MN)
                        fig_yoyc = px.bar(yoy_c, x='Month', y='Total RVUs', color='Year', barmode='group',
                                          text_auto='.2s',
                                          color_discrete_map={str(year):'#1E3A8A', str(prior_year):'#94a3b8'},
                                          labels={'Total RVUs':'wRVUs'})
                        st.plotly_chart(style_high_end_chart(fig_yoyc), use_container_width=True,
                                        key=f"adv_yoy_{tab_key_suffix}_{clinic_filter}")
                        ytd_c2  = df_view.groupby(['ID','Name'])['Total RVUs'].sum().reset_index()
                        ytd_p2  = df_vp_cmp.groupby('ID')['Total RVUs'].sum().reset_index().rename(columns={'Total RVUs':'Prior RVUs'})
                        ytd_cmp = ytd_c2.merge(ytd_p2, on='ID', how='left').fillna({'Prior RVUs':0})
                        ytd_cmp['YoY Δ'] = ytd_cmp.apply(lambda r: (r['Total RVUs']-r['Prior RVUs'])/r['Prior RVUs'] if r['Prior RVUs']>0 else 0, axis=1)
                        ytd_cmp['Trend']  = ytd_cmp['YoY Δ'].apply(lambda x: '▲' if x>0.02 else ('▼' if x<-0.02 else '→'))
                        ytd_cmp = ytd_cmp.sort_values('Total RVUs', ascending=False)
                        render_table(ytd_cmp[['Name','Total RVUs','Prior RVUs','YoY Δ','Trend']]
                                     .style.format({'Total RVUs':'{:,.0f}','Prior RVUs':'{:,.0f}','YoY Δ':'{:+.1%}'})
                                     .background_gradient(subset=['YoY Δ'], cmap=_LC['RdYlGn']))

                # Heatmap -------------------------------------------------------
                with st.container(border=True):
                    render_section_header(f"wRVU Heatmap: Clinic × Month ({year})",
                                          "Color intensity reveals seasonal patterns and outlier months — red = low, green = high", "🌡️")
                    piv_h = df_view.pivot_table(index='Name', columns='Month_Label', values='Total RVUs', aggfunc='sum').fillna(0)
                    piv_h = piv_h.reindex(columns=df_view.sort_values('Month_Clean')['Month_Label'].unique()).fillna(0)
                    fig_heat = px.imshow(piv_h, text_auto='.0f', aspect='auto',
                                         color_continuous_scale='RdYlGn',
                                         labels=dict(x='Month', y='Clinic', color='wRVUs'))
                    fig_heat.update_layout(height=max(320, len(piv_h)*60))
                    st.plotly_chart(style_high_end_chart(fig_heat), use_container_width=True,
                                    key=f"adv_heat_{tab_key_suffix}_{clinic_filter}")

                # Statistical summary -------------------------------------------
                with st.container(border=True):
                    render_section_header("Statistical Summary by Clinic",
                                          "Descriptive statistics for monthly wRVU distribution per site", "📊")
                    grp_s = df_view.groupby('Name')['Total RVUs']
                    stat_df = pd.DataFrame({
                        'Monthly Mean': grp_s.mean(), 'Std Dev': grp_s.std().fillna(0),
                        'Min Month': grp_s.min(), 'Max Month': grp_s.max(), 'YTD Total': grp_s.sum(),
                    }).reset_index()
                    stat_df['CV (%)'] = (stat_df['Std Dev'] / stat_df['Monthly Mean'] * 100).round(1).fillna(0)
                    stat_df['Peak/Trough Ratio'] = stat_df.apply(
                        lambda r: r['Max Month'] / r['Min Month'] if r['Min Month'] > 0 else 0, axis=1)
                    stat_df = stat_df.sort_values('YTD Total', ascending=False)
                    fmt_s = {'Monthly Mean':'{:,.0f}','Std Dev':'{:,.0f}','Min Month':'{:,.0f}',
                             'Max Month':'{:,.0f}','YTD Total':'{:,.0f}','CV (%)':'{:.1f}%',
                             'Peak/Trough Ratio':'{:.2f}'}
                    render_table(stat_df.style.format(fmt_s)
                                 .background_gradient(subset=['YTD Total'], cmap=_LC['Blues'])
                                 .background_gradient(subset=['CV (%)'], cmap=_LC['RdYlGn_r']))
                    st.caption(
                        "**CV** (Coefficient of Variation) = Std Dev ÷ Mean — lower CV indicates more consistent monthly volume. "
                        "**Peak/Trough Ratio** = best month ÷ worst month — values near 1.0 indicate stable year-round demand."
                    )

                # Year-end projection -------------------------------------------
                if 0 < n_m_adv < 12:
                    with st.container(border=True):
                        st.markdown(f"#### 🎯 Year-End Projection ({year}, linear extrapolation from YTD)")
                        pr2 = []
                        for (cid, cname), grp in df_view.groupby(['ID','Name']):
                            ytd_c = grp['Total RVUs'].sum()
                            proj  = ytd_c / n_m_adv * 12
                            fte_c = CLINIC_CONFIG.get(cid, {}).get('fte', 1.0)
                            prior = df_vp[df_vp['ID']==cid]['Total RVUs'].sum() if not df_vp.empty else 0
                            pr2.append({'Clinic':cname,'YTD wRVUs':ytd_c,'Projected Annual':proj,
                                        'Proj wRVU/FTE':proj/fte_c,'Prior Year Total':prior,
                                        'Δ vs Prior':( proj-prior)/prior if prior>0 else 0})
                        if pr2:
                            prj = pd.DataFrame(pr2).sort_values('Projected Annual', ascending=False)
                            fig_prj = px.bar(
                                prj.melt(id_vars='Clinic', value_vars=['YTD wRVUs','Projected Annual']),
                                x='Clinic', y='value', color='variable', barmode='group', text_auto='.2s',
                                color_discrete_sequence=['#1E3A8A','#93c5fd'],
                                labels={'value':'wRVUs','variable':''})
                            st.plotly_chart(style_high_end_chart(fig_prj), use_container_width=True,
                                            key=f"adv_proj_{tab_key_suffix}_{clinic_filter}")
                            fmt_pr = {'YTD wRVUs':'{:,.0f}','Projected Annual':'{:,.0f}',
                                      'Proj wRVU/FTE':'{:,.0f}','Prior Year Total':'{:,.0f}','Δ vs Prior':'{:+.1%}'}
                            render_table(prj.style.format(fmt_pr)
                                         .background_gradient(subset=['Projected Annual','Δ vs Prior'], cmap=_LC['Greens']))

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
                        render_table(piv_p.sort_values("Total", ascending=False).style
                                     .format("{:,.0f}").background_gradient(cmap=_LC['Blues']))
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
                                render_table(pos_piv.style.format("{:,.0f}").background_gradient(cmap=_LC['Greens']))

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
                        render_table(piv_p.sort_values("Total", ascending=False).style
                                     .format("{:,.0f}").background_gradient(cmap=_LC['Blues']))

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
            if not df_mds_yr.empty:
                df_mds_yr['Name'] = df_mds_yr['Name'].apply(
                    lambda n: f"{n} (Ret.)" if n in RETIRED_PROVIDERS else n)
            df_mds_yr_active = df_mds_yr[~df_mds_yr['Name'].str.endswith('(Ret.)')].copy()

            if md_view == "wRVU Productivity":
                if df_mds_yr.empty:
                    st.info(f"No Physician productivity data found for {year}.")
                else:
                    st.info(generate_narrative(df_mds_yr, "Physician"))
                    with st.container(border=True):
                        render_section_header(f"{year} Physician Productivity Trend",
                                              "Monthly wRVU/FTE with 3-month rolling average (dashed) — smooths short-term variability to reveal the underlying trend", "📈")
                        fig_t = go.Figure()
                        color_cycle = PALETTE
                        for i, (name, grp) in enumerate(df_mds_yr_active.sort_values('Month_Clean').groupby('Name')):
                            grp = grp.sort_values('Month_Clean')
                            col = color_cycle[i % len(color_cycle)]
                            fig_t.add_trace(go.Scatter(
                                x=grp['Month_Clean'], y=grp['RVU per FTE'],
                                mode='lines+markers', name=name,
                                line=dict(color=col, width=2.5),
                                marker=dict(size=7, color=col),
                                hovertemplate=f'<b>{name}</b><br>%{{x|%b %Y}}: %{{y:,.0f}} wRVU/FTE<extra></extra>',
                            ))
                            if len(grp) >= 3:
                                rolling = grp['RVU per FTE'].rolling(3, min_periods=2).mean()
                                fig_t.add_trace(go.Scatter(
                                    x=grp['Month_Clean'], y=rolling,
                                    mode='lines', name=f'{name} trend',
                                    line=dict(color=col, width=1.5, dash='dot'),
                                    showlegend=False, opacity=0.55,
                                    hovertemplate=f'<b>{name} (3mo avg)</b><br>%{{x|%b %Y}}: %{{y:,.0f}}<extra></extra>',
                                ))
                        fig_t.update_layout(title=f"Monthly wRVU/FTE by Physician — {year}")
                        st.plotly_chart(style_high_end_chart(fig_t), use_container_width=True,
                                        key=f"md_trend_{tab_key_suffix}")
                    with st.container(border=True):
                        st.markdown("#### 🔢 Monthly Data")
                        piv = df_mds_yr.pivot_table(index="Name", columns="Month_Label", values="Total RVUs", aggfunc="sum").fillna(0)
                        sorted_m = df_mds_yr.sort_values("Month_Clean")["Month_Label"].unique()
                        piv = piv.reindex(columns=sorted_m).fillna(0)
                        piv["Total"] = piv.sum(axis=1)
                        render_table(piv.sort_values("Total", ascending=False).style
                                     .format("{:,.0f}").background_gradient(cmap=_LC['Blues']))
                    with st.container(border=True):
                        st.markdown("#### 🏆 YTD Total RVUs")
                        ytd_s = df_mds_yr.groupby('Name')[['Total RVUs']].sum().reset_index().sort_values('Total RVUs', ascending=False)
                        fig_ytd = px.bar(ytd_s, x='Name', y='Total RVUs', color='Total RVUs',
                                         color_continuous_scale=[[0,'#bfdbfe'],[1,'#1E3A8A']],
                                         text_auto='.2s',
                                         title=f"YTD wRVU Production by Physician — {year}")
                        fig_ytd.update_layout(coloraxis_showscale=False)
                        fig_ytd.update_traces(textfont_size=12, textposition='outside', cliponaxis=False)
                        st.plotly_chart(style_high_end_chart(fig_ytd), use_container_width=True,
                                        key=f"md_ytd_{tab_key_suffix}")

                    # MGMA benchmarking -----------------------------------------
                    with st.container(border=True):
                        n_md_m   = df_mds_yr['Month_Clean'].dt.month.nunique()
                        render_section_header("MGMA Benchmark Comparison",
                                              f"Individual physician wRVUs vs national Radiation Oncology MGMA percentile norms ({n_md_m}-month YTD)", "🎯")
                        MGMA_EXCLUDE = {"Cohen"}
                        ytd_mgma = (df_mds_yr.groupby('Name')[['Total RVUs']].sum().reset_index()
                                    .loc[lambda d: ~d['Name'].isin(MGMA_EXCLUDE) & ~d['Name'].str.endswith('(Ret.)')]
                                    .sort_values('Total RVUs', ascending=False))
                        ref_25   = MGMA_BENCHMARKS['25th'] / 12 * n_md_m
                        ref_50   = MGMA_BENCHMARKS['50th'] / 12 * n_md_m
                        ref_75   = MGMA_BENCHMARKS['75th'] / 12 * n_md_m
                        ytd_mgma['pct_vs_50'] = (ytd_mgma['Total RVUs'] / ref_50 - 1) * 100
                        div_df = ytd_mgma.sort_values('pct_vs_50')
                        bar_colors = ['#16a34a' if v >= 0 else '#dc2626' for v in div_df['pct_vs_50']]
                        fig_mgma = go.Figure(go.Bar(
                            x=div_df['pct_vs_50'],
                            y=div_df['Name'],
                            orientation='h',
                            marker_color=bar_colors,
                            text=[f"{v:+.1f}%" for v in div_df['pct_vs_50']],
                            textposition='outside',
                            cliponaxis=False,
                            customdata=div_df['Total RVUs'].values,
                            hovertemplate='<b>%{y}</b><br>vs MGMA 50th: %{x:+.1f}%<br>wRVUs: %{customdata:,.0f}<extra></extra>',
                        ))
                        fig_mgma.add_vline(x=0, line_color='#334155', line_width=2)
                        fig_mgma.add_vline(x=(ref_75/ref_50-1)*100, line_dash='dot', line_color='#7c3aed',
                                           annotation_text="75th pct", annotation_position="top")
                        fig_mgma.add_vline(x=(ref_25/ref_50-1)*100, line_dash='dot', line_color='#f97316',
                                           annotation_text="25th pct", annotation_position="top")
                        fig_mgma.update_layout(
                            title=f"Physician wRVU Performance vs MGMA 50th Percentile ({n_md_m}-mo YTD)",
                            xaxis_title="% Above / Below MGMA 50th Percentile",
                            yaxis_title="",
                            height=max(340, len(div_df) * 42 + 90),
                        )
                        st.plotly_chart(style_high_end_chart(fig_mgma), use_container_width=True,
                                        key=f"md_mgma_{tab_key_suffix}")
                        ytd_mgma['vs 25th'] = ytd_mgma['Total RVUs'] / ref_25 - 1
                        ytd_mgma['vs 50th'] = ytd_mgma['Total RVUs'] / ref_50 - 1
                        ytd_mgma['vs 75th'] = ytd_mgma['Total RVUs'] / ref_75 - 1
                        ytd_mgma['Productivity Tier'] = ytd_mgma['Total RVUs'].apply(
                            lambda x: '🥇 Elite (>75th)' if x > ref_75
                            else ('✅ Above Avg (50–75th)' if x > ref_50
                            else ('⚠️ Average (25–50th)' if x > ref_25
                            else '🔴 Below Avg (<25th)')))
                        render_table(ytd_mgma[['Name','Total RVUs','vs 25th','vs 50th','vs 75th','Productivity Tier']]
                                     .style.format({'Total RVUs':'{:,.0f}','vs 25th':'{:+.1%}',
                                                    'vs 50th':'{:+.1%}','vs 75th':'{:+.1%}'})
                                     .background_gradient(subset=['vs 50th'], cmap=_LC['RdYlGn']))
                        elite_md  = (ytd_mgma['Total RVUs'] > ref_75).sum()
                        below_md  = (ytd_mgma['Total RVUs'] < ref_25).sum()
                        st.caption(
                            f"Benchmarks scaled to {n_md_m}-month YTD — 25th: **{ref_25:,.0f}** | 50th: **{ref_50:,.0f}** | 75th: **{ref_75:,.0f}** wRVUs. "
                            f"**{elite_md}** physician(s) above the 75th percentile; **{below_md}** below the 25th. "
                            f"Source: Approximate MGMA Radiation Oncology physician benchmarks."
                        )

                    # Physician × Month heatmap ---------------------------------
                    with st.container(border=True):
                        render_section_header("Physician Productivity Heatmap",
                                              "Monthly wRVU by physician — identifies seasonal dips, leave patterns, and outlier months", "🌡️")
                        piv_mh = df_mds_yr_active.pivot_table(index='Name', columns='Month_Label', values='Total RVUs', aggfunc='sum').fillna(0)
                        piv_mh = piv_mh.reindex(columns=df_mds_yr_active.sort_values('Month_Clean')['Month_Label'].unique()).fillna(0)
                        fig_mheat = px.imshow(piv_mh, text_auto='.0f', aspect='auto',
                                              color_continuous_scale='Blues',
                                              labels=dict(x='Month', y='Physician', color='wRVUs'))
                        fig_mheat.update_layout(height=max(200, len(piv_mh)*30))
                        st.plotly_chart(style_high_end_chart(fig_mheat), use_container_width=True,
                                        key=f"md_heat_{tab_key_suffix}")

                    # Year-over-year physician comparison -----------------------
                    _prior_y    = year - 1
                    _df_mds_pri = df_mds[df_mds['Month_Clean'].dt.year == _prior_y].copy() if not df_mds.empty else pd.DataFrame()
                    if not _df_mds_pri.empty:
                        _cur_m = set(df_mds_yr['Month_Clean'].dt.month.unique())
                        _df_mds_pri_cmp = _df_mds_pri[_df_mds_pri['Month_Clean'].dt.month.isin(_cur_m)]
                        if not _df_mds_pri_cmp.empty:
                            with st.container(border=True):
                                st.markdown(f"#### 📅 Year-over-Year: Physician wRVUs ({year} vs {_prior_y})")
                                yc = df_mds_yr.groupby('Name')['Total RVUs'].sum().reset_index(); yc['Year'] = str(year)
                                yp = _df_mds_pri_cmp.groupby('Name')['Total RVUs'].sum().reset_index(); yp['Year'] = str(_prior_y)
                                fig_yoym = px.bar(pd.concat([yc, yp]), x='Name', y='Total RVUs',
                                                  color='Year', barmode='group', text_auto='.2s',
                                                  color_discrete_map={str(year):'#1E3A8A', str(_prior_y):'#94a3b8'},
                                                  labels={'Total RVUs':'wRVUs'})
                                st.plotly_chart(style_high_end_chart(fig_yoym), use_container_width=True,
                                                key=f"md_yoy_{tab_key_suffix}")

                    # Monthly distribution box plot -----------------------------
                    with st.container(border=True):
                        render_section_header("Monthly wRVU Distribution by Physician",
                                              "Box-and-whisker plot of monthly production — reveals variability and outliers at the individual level", "📦")
                        fig_box = px.box(df_mds_yr_active.sort_values('Name'), x='Name', y='Total RVUs',
                                         color='Name', points='all',
                                         labels={'Total RVUs':'Monthly wRVUs', 'Name':'Physician'})
                        fig_box.update_layout(showlegend=False, height=480)
                        st.plotly_chart(style_high_end_chart(fig_box), use_container_width=True,
                                        key=f"md_box_{tab_key_suffix}")
                        st.caption(
                            "Box spans IQR (Q1–Q3); center line = median; whiskers = 1.5× IQR; dots = individual months. "
                            "A **narrow box** indicates consistent monthly production; a **wide box** signals high variability — "
                            "potentially driven by leave, schedule changes, or case mix shifts."
                        )

                    # Statistical summary table ---------------------------------
                    with st.container(border=True):
                        render_section_header("Physician Statistical Summary",
                                              "Descriptive statistics for monthly wRVU output — quantifies production consistency", "📊")
                        md_grp  = df_mds_yr_active.groupby('Name')['Total RVUs']
                        md_stat = pd.DataFrame({
                            'Monthly Mean': md_grp.mean(), 'Std Dev': md_grp.std().fillna(0),
                            'Min Month': md_grp.min(), 'Max Month': md_grp.max(), 'YTD Total': md_grp.sum(),
                        }).reset_index()
                        md_stat['CV (%)'] = (md_stat['Std Dev'] / md_stat['Monthly Mean'] * 100).round(1).fillna(0)
                        md_stat['Peak/Trough'] = md_stat.apply(
                            lambda r: r['Max Month'] / r['Min Month'] if r['Min Month'] > 0 else 0, axis=1)
                        md_stat = md_stat.sort_values('YTD Total', ascending=False)
                        fmt_ms  = {'Monthly Mean':'{:,.0f}','Std Dev':'{:,.0f}','Min Month':'{:,.0f}',
                                   'Max Month':'{:,.0f}','YTD Total':'{:,.0f}','CV (%)':'{:.1f}%',
                                   'Peak/Trough':'{:.2f}'}
                        render_table(md_stat.style.format(fmt_ms)
                                     .background_gradient(subset=['YTD Total'], cmap=_LC['Purples'])
                                     .background_gradient(subset=['CV (%)'], cmap=_LC['RdYlGn_r']))
                        st.caption(
                            "**CV** = Std Dev ÷ Mean × 100 — lower values indicate more predictable monthly output. "
                            "**Peak/Trough** = best month ÷ worst month — values near 1.0 indicate stable scheduling year-round."
                        )

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
                    with st.container(border=True):
                        st.markdown(f"#### 🏥 Total Office Visits ({year} YTD)")
                        fig_ov = px.bar(lv_df.sort_values('Total Visits', ascending=True),
                                        x='Total Visits', y='Name', orientation='h', text_auto=True,
                                        color='Total Visits', color_continuous_scale='Blues')
                        fig_ov.update_layout(height=500)
                        st.plotly_chart(style_high_end_chart(fig_ov), use_container_width=True,
                                        key=f"vis_ov_{tab_key_suffix}")
                    with st.container(border=True):
                        st.markdown(f"#### 🆕 New Patients ({year} YTD)")
                        fig_np = px.bar(lv_df.sort_values('New Patients', ascending=True),
                                        x='New Patients', y='Name', orientation='h', text_auto=True,
                                        color='New Patients', color_continuous_scale='Greens')
                        fig_np.update_layout(height=500)
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

                    with st.container(border=True):
                        st.markdown("#### 🔢 Monthly Count by Provider")
                        piv_77470 = df_77470_yr.pivot_table(
                            index="Name", columns="Month_Label", values="Count", aggfunc="sum"
                        ).fillna(0)
                        piv_77470 = piv_77470.reindex(columns=sorted_m).fillna(0)
                        piv_77470["Total"] = piv_77470.sum(axis=1)
                        render_table(
                            piv_77470.sort_values("Total", ascending=False).style
                            .format("{:,.1f}").background_gradient(cmap=_LC['Purples'])
                        )
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
                render_table(piv_77.sort_values("Total", ascending=False).style
                             .format("{:,.0f}").background_gradient(cmap=_LC['Blues']))

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
    st.markdown(
        """
        <div style="padding:18px 0 6px 0;">
          <h1 style="color:#0f172a;margin:0;font-size:2rem;font-weight:800;letter-spacing:-0.5px;">
            🩺 Radiation Oncology Division Analytics
          </h1>
          <p style="color:#64748b;margin:4px 0 0 0;font-size:14px;">
            Physician productivity &nbsp;·&nbsp; Clinical operations &nbsp;·&nbsp; Revenue cycle performance
            &nbsp;&nbsp;|&nbsp;&nbsp; <span style="color:#1E3A8A;font-weight:600;">by Dr. Jones</span>
          </p>
        </div>
        """,
        unsafe_allow_html=True,
    )
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

            tab_exec, tab_c26, tab_c25, tab_md26, tab_md25, tab_app, tab_fin = st.tabs([
                "📊 Executive Summary",
                "🏥 Clinic Analytics - 2026",
                "🏥 Clinic Analytics - 2025",
                "👨‍⚕️ MD Analytics - 2026",
                "👨‍⚕️ MD Analytics - 2025",
                "👩‍⚕️ APP Analytics",
                "💰 Financials",
            ])

            with tab_exec:
                render_executive_summary(2026, df_clinic, df_mds, df_visits, df_financial)

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
                    # APP header with KPIs
                    app_yrs = sorted(df_apps['Month_Clean'].dt.year.unique())
                    app_cur_yr = max(app_yrs)
                    app_pri_yr = app_cur_yr - 1
                    df_app_cur = df_apps[df_apps['Month_Clean'].dt.year == app_cur_yr]
                    df_app_pri = df_apps[df_apps['Month_Clean'].dt.year == app_pri_yr]
                    app_cur_m  = set(df_app_cur['Month_Clean'].dt.month.unique())
                    df_app_pri_cmp = df_app_pri[df_app_pri['Month_Clean'].dt.month.isin(app_cur_m)] if not df_app_pri.empty else pd.DataFrame()

                    app_ytd_total  = df_app_cur['Total RVUs'].sum()
                    app_pri_total  = df_app_pri_cmp['Total RVUs'].sum() if not df_app_pri_cmp.empty else 0
                    app_yoy        = (app_ytd_total - app_pri_total) / app_pri_total * 100 if app_pri_total > 0 else 0
                    net_total_ytd  = df_clinic[df_clinic['Month_Clean'].dt.year == app_cur_yr]['Total RVUs'].sum() if not df_clinic.empty else 0
                    app_net_pct    = app_ytd_total / net_total_ytd * 100 if net_total_ytd > 0 else 0
                    n_app_months   = df_app_cur['Month_Clean'].dt.month.nunique()

                    st.markdown(
                        f"<h2 style='color:#0f172a;margin-bottom:2px;'>👩‍⚕️ Advanced Practice Provider Analytics</h2>"
                        f"<p style='color:#64748b;font-size:14px;margin-top:0;'>Year-to-date performance, E&M visit activity, and network contribution — {app_cur_yr}</p>",
                        unsafe_allow_html=True,
                    )
                    st.markdown("---")

                    # KPI row
                    a1, a2, a3, a4 = st.columns(4)
                    with a1:
                        st.metric("APP wRVUs YTD", f"{app_ytd_total:,.0f}",
                                  delta=f"{app_yoy:+.1f}% vs {app_pri_yr}" if app_pri_total > 0 else None)
                    with a2:
                        st.metric("% of Network Total", f"{app_net_pct:.1f}%",
                                  help="APP wRVUs as share of total clinic network wRVUs")
                    with a3:
                        st.metric("Active APPs", str(df_app_cur['Name'].nunique()))
                    with a4:
                        app_proj = app_ytd_total / n_app_months * 12 if n_app_months > 0 else 0
                        st.metric(f"Projected {app_cur_yr} Annual", f"{app_proj:,.0f}",
                                  help=f"Linear extrapolation from {n_app_months}-month YTD")

                    # Insight
                    if app_ytd_total > 0:
                        top_app = df_app_cur.groupby('Name')['Total RVUs'].sum().idxmax()
                        render_insight_box(
                            "APP Contribution Summary",
                            f"APPs collectively generated <b>{app_ytd_total:,.0f} wRVUs</b> YTD ({app_cur_yr}), "
                            f"representing <b>{app_net_pct:.1f}%</b> of total network volume. "
                            f"YoY change: <b>{app_yoy:+.1f}%</b> vs same period {app_pri_yr}. "
                            f"Top APP producer: <b>{top_app}</b>."
                        )

                    st.info(generate_narrative(df_apps, "APP"))

                    # wRVU Trend
                    with st.container(border=True):
                        render_section_header("wRVU/FTE Trend — All APPs",
                                              "Monthly productivity trend by provider — normalized for FTE", "📅")
                        fig_t = px.line(df_apps.sort_values('Month_Clean'), x='Month_Clean',
                                        y='RVU per FTE', color='Name', markers=True,
                                        labels={'Month_Clean':'Month', 'RVU per FTE':'wRVU / FTE'})
                        st.plotly_chart(style_high_end_chart(fig_t), use_container_width=True,
                                        key="app_trend_fte")

                    # YTD total wRVU bar
                    with st.container(border=True):
                        render_section_header(f"APP YTD wRVU Comparison ({app_cur_yr})",
                                              "Absolute production compared across APP providers", "🏆")
                        app_ytd_bar = df_app_cur.groupby('Name')['Total RVUs'].sum().reset_index().sort_values('Total RVUs', ascending=False)
                        if not df_app_pri_cmp.empty:
                            app_pri_bar = df_app_pri_cmp.groupby('Name')['Total RVUs'].sum().reset_index()
                            app_pri_bar.columns = ['Name', 'Prior RVUs']
                            app_ytd_bar = app_ytd_bar.merge(app_pri_bar, on='Name', how='left').fillna({'Prior RVUs': 0})
                            app_bar_melt = app_ytd_bar.melt(id_vars='Name', value_vars=['Total RVUs', 'Prior RVUs'])
                            fig_ayb = px.bar(app_bar_melt, x='Name', y='value', color='variable',
                                             barmode='group', text_auto='.2s',
                                             color_discrete_map={'Total RVUs':'#1E3A8A','Prior RVUs':'#94a3b8'},
                                             labels={'value':'wRVUs','variable':''})
                        else:
                            fig_ayb = px.bar(app_ytd_bar, x='Name', y='Total RVUs', text_auto='.2s',
                                             color='Total RVUs', color_continuous_scale='Blues')
                        st.plotly_chart(style_high_end_chart(fig_ayb), use_container_width=True, key="app_ytd_bar")

                    st.markdown("---")
                    if not df_app_cpt.empty:
                        render_section_header("APP Independent Follow-up Visits (CPT 99212–99215)",
                                              "E&M visit volume by code level — reflects clinical complexity and panel management activity", "🏥")
                        with st.container(border=True):
                            ytd_app = df_app_cpt.groupby(['Name', 'CPT Code'])['Count'].sum().reset_index()
                            fig_ab = px.bar(ytd_app, x="Name", y="Count", color="CPT Code",
                                            barmode="group", text_auto=True, title="YTD Follow-up Visits by CPT Code")
                            st.plotly_chart(style_high_end_chart(fig_ab), use_container_width=True,
                                            key="app_cpt_bar")
                            st.caption(
                                "Higher-complexity codes (99214, 99215) reflect patients with more complex, active management needs. "
                                "A shift toward higher codes over time may indicate increasing panel acuity."
                            )
                        cols = st.columns(2)
                        for i, app_name in enumerate(df_app_cpt['Name'].unique()):
                            with cols[i % 2]:
                                with st.container(border=True):
                                    render_section_header(app_name, "Monthly E&M visit volume by CPT code")
                                    sub = df_app_cpt[df_app_cpt['Name'] == app_name]
                                    piv_a = sub.pivot_table(index="CPT Code", columns="Month_Label", values="Count", aggfunc="sum").fillna(0)
                                    sorted_ma = sub.sort_values("Month_Clean")["Month_Label"].unique()
                                    piv_a = piv_a.reindex(columns=sorted_ma).fillna(0)
                                    piv_a["Total"] = piv_a.sum(axis=1)
                                    render_table(piv_a.style.format("{:,.0f}").background_gradient(cmap=_LC['Oranges']))

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
                            render_table(lp[['Name','Charges','Payments','% Payments/Charges']].sort_values('Charges', ascending=False).style
                                         .format(fmt).background_gradient(cmap=_LC['Greens']))
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
                            render_table(ytd_disp.style.format(fmt).background_gradient(cmap=_LC['Greens']))
                            st.markdown("---")
                            st.markdown("#### 📅 Monthly Data Breakdown")
                            md_disp = cf[['Name','Month_Label','Charges','Payments']].copy()
                            md_disp['% Payments/Charges'] = md_disp.apply(lambda x: x['Payments'] / x['Charges'] if x['Charges'] > 0 else 0, axis=1)
                            md_disp['Month_Sort'] = pd.to_datetime(md_disp['Month_Label'], format='%b-%y')
                            md_disp = md_disp.sort_values(['Month_Sort','Name'], ascending=[False, True]).drop(columns=['Month_Sort'])
                            render_table(md_disp.style.format(fmt).background_gradient(cmap=_LC['Blues']))

                    # ---- Advanced Financial Analytics (both views) ----
                    st.markdown("---")
                    render_section_header("Advanced Financial Analytics",
                                          "Revenue cycle performance, collection rate trends, and efficiency metrics", "📐")

                    # Collection rate trend
                    cf_all = df_financial[df_financial['Mode'] == 'Clinic']
                    if not cf_all.empty:
                        with st.container(border=True):
                            render_section_header("Payment Collection Rate Trend",
                                                  "Monthly payment-to-charge ratio — sustained rates below average may indicate payer mix, coding, or billing cycle issues", "📈")
                            cf_mo = cf_all.groupby('Month_Label')[['Charges','Payments']].sum().reset_index()
                            cf_mo['Month_Sort'] = pd.to_datetime(cf_mo['Month_Label'], format='%b-%y', errors='coerce')
                            cf_mo = cf_mo.dropna(subset=['Month_Sort']).sort_values('Month_Sort')
                            cf_mo['Collection Rate'] = cf_mo['Payments'] / cf_mo['Charges']
                            fig_cr = px.line(cf_mo, x='Month_Label', y='Collection Rate', markers=True,
                                             title='Monthly Payment Collection Rate',
                                             labels={'Month_Label':'Month','Collection Rate':'Collection Rate'})
                            fig_cr.update_yaxes(tickformat='.1%')
                            fig_cr.add_hline(y=cf_mo['Collection Rate'].mean(), line_dash='dash',
                                             line_color='#64748b',
                                             annotation_text=f"Avg {cf_mo['Collection Rate'].mean():.1%}",
                                             annotation_position="right")
                            st.plotly_chart(style_high_end_chart(fig_cr), use_container_width=True,
                                            key="fin_coll_trend")

                        # Charges vs Payments waterfall / grouped bar by clinic
                        with st.container(border=True):
                            render_section_header("Charges vs Payments by Clinic (YTD)",
                                                  "Gap between charges and payments reflects contractual adjustments, write-offs, and payer mix", "🏦")
                            ytd_cp = cf_all.groupby('Name')[['Charges','Payments']].sum().reset_index()
                            ytd_cp = ytd_cp.sort_values('Charges', ascending=False)
                            ytd_cp_melt = ytd_cp.melt(id_vars='Name', value_vars=['Charges','Payments'])
                            fig_cpb = px.bar(ytd_cp_melt, x='Name', y='value', color='variable',
                                             barmode='group', text_auto='$.2s',
                                             color_discrete_map={'Charges':'#1E3A8A','Payments':'#22c55e'},
                                             labels={'value':'Amount ($)','variable':''})
                            st.plotly_chart(style_high_end_chart(fig_cpb), use_container_width=True,
                                            key="fin_cpbar")

                        # Collection rate heatmap: Clinic × Month
                        with st.container(border=True):
                            render_section_header("Collection Rate Heatmap: Clinic × Month",
                                                  "Identifies which sites and months show anomalous collection performance", "🌡️")
                            try:
                                cf_piv = cf_all.copy()
                                cf_piv['Collection Rate'] = cf_piv['Payments'] / cf_piv['Charges']
                                piv_cr = cf_piv.pivot_table(index='Name', columns='Month_Label',
                                                             values='Collection Rate', aggfunc='mean').fillna(0)
                                ms_cr = cf_piv.copy()
                                ms_cr['Month_Sort'] = pd.to_datetime(ms_cr['Month_Label'], format='%b-%y', errors='coerce')
                                sorted_cr_m = ms_cr.dropna(subset=['Month_Sort']).sort_values('Month_Sort')['Month_Label'].unique()
                                piv_cr = piv_cr.reindex(columns=sorted_cr_m).fillna(0)
                                fig_crh = px.imshow(piv_cr, text_auto='.1%', aspect='auto',
                                                    color_continuous_scale='RdYlGn',
                                                    zmin=0.2, zmax=1.0,
                                                    labels=dict(x='Month', y='Clinic', color='Collection Rate'))
                                fig_crh.update_layout(height=max(300, len(piv_cr)*55))
                                st.plotly_chart(style_high_end_chart(fig_crh), use_container_width=True,
                                                key="fin_crheat")
                            except Exception:
                                pass

                    # Revenue efficiency: provider-level payments per wRVU
                    prov_fin_adv = df_financial[(df_financial['Mode'] == 'Provider') & (df_financial['Name'] != "TN Proton Center")]
                    if not prov_fin_adv.empty and not df_md_global.empty:
                        with st.container(border=True):
                            render_section_header("Revenue Efficiency: Payments per wRVU by Physician",
                                                  "Normalizes revenue performance by clinical workload — higher $/wRVU reflects better payer mix or contract rates", "💡")
                            try:
                                fin_ytd = prov_fin_adv.groupby('Name')[['Charges','Payments']].sum().reset_index()
                                rvu_ytd = df_md_global.groupby('Name')['Total RVUs'].sum().reset_index()
                                rev_eff = fin_ytd.merge(rvu_ytd, on='Name', how='inner')
                                rev_eff = rev_eff[rev_eff['Total RVUs'] > 0]
                                rev_eff['$/wRVU (Charges)']  = rev_eff['Charges']  / rev_eff['Total RVUs']
                                rev_eff['$/wRVU (Payments)'] = rev_eff['Payments'] / rev_eff['Total RVUs']
                                rev_eff = rev_eff.sort_values('$/wRVU (Payments)', ascending=False)
                                fig_eff = px.bar(rev_eff, x='Name', y=['$/wRVU (Charges)','$/wRVU (Payments)'],
                                                 barmode='group', text_auto='$.0f',
                                                 color_discrete_sequence=['#1E3A8A','#22c55e'],
                                                 labels={'value':'$ per wRVU','variable':''})
                                st.plotly_chart(style_high_end_chart(fig_eff), use_container_width=True,
                                                key="fin_reveff")
                                fmt_re = {'Charges':'${:,.0f}','Payments':'${:,.0f}','Total RVUs':'{:,.0f}',
                                          '$/wRVU (Charges)':'${:,.2f}','$/wRVU (Payments)':'${:,.2f}'}
                                render_table(rev_eff[['Name','Total RVUs','Charges','Payments',
                                                       '$/wRVU (Charges)','$/wRVU (Payments)']]
                                             .style.format(fmt_re)
                                             .background_gradient(subset=['$/wRVU (Payments)'], cmap=_LC['Greens']))
                                st.caption("Higher $/wRVU reflects better payer mix or contract rates for that physician's patient population.")
                            except Exception:
                                pass

    else:
        st.info("👋 Ready. Add files to the 'Reports' folder in GitHub to load data.")
