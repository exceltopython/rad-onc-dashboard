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
        div[data-testid="stDataFrame"] div[role="columnheader"] { color: #000000 !important; font-weight: 900 !important; font-size: 14px !important; }
        [data-testid="stDataFrame"] th { color: #000000 !important; font-weight: 900 !important; }
        </style>
    """, unsafe_allow_html=True)

inject_custom_css()

def style_high_end_chart(fig):
    fig.update_layout(
        font={'family': "Inter, sans-serif", 'color': '#334155'},
        paper_bgcolor='rgba(0,0,0,0)', 
        plot_bgcolor='rgba(0,0,0,0)', 
        margin=dict(t=50, l=20, r=20, b=40),
        xaxis=dict(showgrid=False, showline=True, linecolor='#cbd5e1'),
        yaxis=dict(showgrid=True, gridcolor='#f1f5f9'),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
    )
    return fig

# --- 2. PASSWORD CONFIGURATION ---
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
    return st.session_state.get("password_correct", False)

# --- 3. HISTORICAL DATA ENTRY (2019-2025) ---
HISTORICAL_DATA = {
    2019: {"CENT": 18430, "Dickson": 11420, "Skyline": 13910, "Summit": 14690, "Stonecrest": 8600, "STW": 22030, "Midtown": 14730, "MURF": 38810, "Sumner": 14910, "TOPC": 15690, "LROC": 0, "TROC": 0},
    2020: {"CENT": 19160, "Dickson": 12940, "Skyline": 13180, "Summit": 11540, "Stonecrest": 7470, "STW": 17070, "Midtown": 14560, "MURF": 37890, "Sumner": 14760, "TOPC": 22010, "LROC": 0, "TROC": 0},
    2021: {"CENT": 14480, "Dickson": 10980, "Skyline": 11450, "Summit": 11700, "Stonecrest": 8610, "STW": 17970, "Midtown": 17890, "MURF": 37440, "Sumner": 17670, "TOPC": 28540, "LROC": 0, "TROC": 0},
    2022: {"CENT": 15860, "Dickson": 13960, "Skyline": 14520, "Summit": 12390, "Stonecrest": 10580, "STW": 27650, "Midtown": 19020, "MURF": 37870, "Sumner": 20570, "TOPC": 28830, "LROC": 0, "TROC": 0},
    2023: {"CENT": 19718, "Dickson": 11600, "Skyline": 17804, "Summit": 14151, "Stonecrest": 11647, "STW": 23717, "Midtown": 21017, "MURF": 42201, "Sumner": 22622, "TOPC": 27667, "LROC": 0, "TROC": 0},
    2024: {"CENT": 22385, "Dickson": 12155, "Skyline": 15363, "Summit": 12892, "Stonecrest": 12524, "STW": 25409, "Midtown": 21033, "MURF": 45648, "Sumner": 23803, "TOPC": 33892, "LROC": 0, "TROC": 0},
    2025: {"CENT": 22236, "Dickson": 12954, "Skyline": 13931, "Summit": 9225, "Stonecrest": 11873, "STW": 22024, "Midtown": 19172, "MURF": 43857, "Sumner": 24169, "TOPC": 37515, "LROC": 14528, "TROC": 9042}
}

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
APP_LIST = ["Burke", "Ellis", "Lewis", "Lydon"]
TARGET_CATEGORIES = ["E&M OFFICE CODES", "RADIATION CODES", "SPECIAL PROCEDURES"]
IGNORED_SHEETS = ["RAD PHYSICIAN WORK RVUS", "COVER", "SHEET1", "TOTALS", "PROTON PHYSICIAN WORK RVUS"]

# --- 4. DATA HELPERS ---

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

def clean_number(val):
    if pd.isna(val): return 0.0
    try:
        val_str = str(val).strip().replace(',', '').replace('%', '').replace('$', '')
        if val_str.startswith("(") and val_str.endswith(")"): val_str = "-" + val_str[1:-1]
        if val_str in ["", "-", "NaN"]: return 0.0
        return float(val_str)
    except: return 0.0

def match_provider(name_str):
    if not isinstance(name_str, str) or not name_str.strip(): return None
    base = name_str.split(",")[0].strip().split()[0].upper()
    if base == "FRIEDMEN": base = "FRIEDMAN"
    for key in PROVIDER_CONFIG:
        if key.upper() == base: return key
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
    if valid_subset:
        df = df.drop_duplicates(subset=valid_subset, keep='first')
    if not df.empty and 'Month_Clean' in df.columns:
        df['Month_Label'] = df['Month_Clean'].dt.strftime('%b-%y')
        df['Quarter'] = df['Month_Clean'].apply(lambda x: f"Q{x.quarter} {x.year}")
    return df

# --- 5. PARSERS ---

def find_date_row(df):
    months = ["JAN", "FEB", "MAR", "APR", "MAY", "JUN", "JUL", "AUG", "SEP", "OCT", "NOV", "DEC"]
    best_row = 1; max_score = 0
    for r in range(min(15, len(df))):
        row_vals = [str(v).upper() for v in df.iloc[r, 4:16] if pd.notna(v)]
        score = sum(1 for v in row_vals if any(m in v for m in months))
        if score > max_score: max_score = score; best_row = r
    return best_row

def parse_rvu_sheet(df, sheet_name, entity_type, target_year=None):
    if entity_type == 'clinic':
        cfg = CLINIC_CONFIG.get(sheet_name, {"name": sheet_name, "fte": 1.0})
        name, fte = cfg['name'], cfg['fte']
    else:
        name, fte = sheet_name, PROVIDER_CONFIG.get(sheet_name, 1.0)
    
    df.iloc[:, 0] = df.iloc[:, 0].astype(str).str.strip().str.upper()
    data_rows = df[df.iloc[:, 0].isin(TARGET_CATEGORIES)].copy()
    records = []; header_idx = find_date_row(df)
    
    if len(df.columns) > 4:
        for col in df.columns[4:]:
            dt = standardize_date(df.iloc[header_idx, col])
            if pd.isna(dt) or (target_year and dt.year != target_year): continue
            col_sum = pd.to_numeric(data_rows[col], errors='coerce').sum()
            records.append({
                "Type": entity_type, "ID": sheet_name, "Name": name, "FTE": fte,
                "Month_Clean": dt, "Total RVUs": col_sum, "RVU per FTE": col_sum / fte if fte > 0 else 0
            })
    return pd.DataFrame(records)

def process_files(file_objects):
    clinic_data, provider_data = [], []
    for f in file_objects:
        fname = f.name.upper()
        year_match = re.search(r'202[4-6]', fname)
        target_year = int(year_match.group(0)) if year_match else None
        xls = pd.read_excel(f, sheet_name=None, header=None)
        for sname, df in xls.items():
            if any(ig in sname.upper() for ig in IGNORED_SHEETS): continue
            if sname in CLINIC_CONFIG:
                res = parse_rvu_sheet(df, sname, 'clinic', target_year=target_year)
                if not res.empty: clinic_data.append(res)
            p_match = match_provider(sname)
            if p_match:
                res = parse_rvu_sheet(df, p_match, 'provider', target_year=target_year)
                if not res.empty: provider_data.append(res)
                
    return safe_dedup_and_format(clinic_data, ['Name', 'Month_Clean', 'ID']), \
           safe_dedup_and_format(provider_data, ['Name', 'Month_Clean'])

# --- 6. UI ---

if check_password():
    st.title("🩺 Radiation Oncology Division Analytics")
    st.markdown("##### by Dr. Jones")
    st.markdown("---")

    uploaded = st.sidebar.file_uploader("Upload Productivity Excel Files", type=['xlsx'], accept_multiple_files=True)
    
    if uploaded:
        with st.spinner("Analyzing files..."):
            df_clinic, df_provider = process_files(uploaded)

        tab_c26, tab_c25, tab_md26, tab_md25 = st.tabs(["🏥 Clinic 2026", "🏥 Clinic 2025", "👨‍⚕️ MD 2026", "👨‍⚕️ MD 2025"])

        def render_hist_summary(df_current, current_year, filter_ids=None):
            # Get hardcoded historical data
            records = []
            for y, data in HISTORICAL_DATA.items():
                for cid, rvu in data.items():
                    if cid in CLINIC_CONFIG:
                        records.append({"ID": cid, "Year": y, "Total RVUs": rvu})
            df_hist = pd.DataFrame(records)
            
            if filter_ids: df_hist = df_hist[df_hist['ID'].isin(filter_ids)]
            
            # Aggregate historical by year
            hist_agg = df_hist.groupby('Year')[['Total RVUs']].sum().reset_index()
            
            # Merge with calculated YTD from current data if applicable
            if not df_current.empty:
                ytd_val = df_current[df_current['Month_Clean'].dt.year == current_year]['Total RVUs'].sum()
                if ytd_val > 0:
                    # If the year is already in hist_agg, update it, otherwise append
                    if current_year in hist_agg['Year'].values:
                        hist_agg.loc[hist_agg['Year'] == current_year, 'Total RVUs'] += ytd_val
                    else:
                        hist_agg = pd.concat([hist_agg, pd.DataFrame({"Year": [current_year], "Total RVUs": [ytd_val]})])

            hist_agg['Year'] = hist_agg['Year'].astype(str)
            # CRITICAL FIX: Ensure Year is unique before Transpose
            hist_final = hist_agg.groupby('Year').sum().T
            st.dataframe(hist_final.style.format("{:,.0f}"), use_container_width=True)

        with tab_c26:
            df_c26 = df_clinic[df_clinic['Month_Clean'].dt.year == 2026]
            c_filter = st.selectbox("View Group:", ["All", "TriStar", "Ascension"], key="f26")
            f_ids = TRISTAR_IDS if c_filter == "TriStar" else (ASCENSION_IDS if c_filter == "Ascension" else None)
            
            with st.container(border=True):
                st.markdown("##### 📅 Historical Data Summary")
                render_hist_summary(df_clinic, 2026, f_ids)
            
            if not df_c26.empty:
                st.plotly_chart(style_high_end_chart(px.line(df_c26.sort_values('Month_Clean'), x='Month_Clean', y='Total RVUs', color='Name', markers=True)), use_container_width=True)

        with tab_c25:
            df_c25 = df_clinic[df_clinic['Month_Clean'].dt.year == 2025]
            with st.container(border=True):
                st.markdown("##### 📅 Historical Data Summary")
                render_hist_summary(df_clinic, 2025)
            
            if not df_c25.empty:
                st.plotly_chart(style_high_end_chart(px.line(df_c25.sort_values('Month_Clean'), x='Month_Clean', y='Total RVUs', color='Name', markers=True)), use_container_width=True)

        with tab_md26:
            df_p26 = df_provider[df_provider['Month_Clean'].dt.year == 2026]
            if not df_p26.empty:
                st.plotly_chart(style_high_end_chart(px.bar(df_p26.groupby('Name')['Total RVUs'].sum().reset_index().sort_values('Total RVUs'), x='Total RVUs', y='Name', orientation='h', text_auto='.2s')), use_container_width=True)

        with tab_md25:
            df_p25 = df_provider[df_provider['Month_Clean'].dt.year == 2025]
            if not df_p25.empty:
                st.plotly_chart(style_high_end_chart(px.bar(df_p25.groupby('Name')['Total RVUs'].sum().reset_index().sort_values('Total RVUs'), x='Total RVUs', y='Name', orientation='h', text_auto='.2s')), use_container_width=True)
    else:
        st.info("👋 Upload productivity files to begin.")
else:
    st.warning("Locked. Please check password.")
