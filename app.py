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
        pdf.set_font('Arial', 'B', 11); pdf.cell(0, 10, f"{total_rvu:,.2f}", 0, 1)
        pdf.set_font('Arial', '', 11); pdf.cell(60, 10, "wRVU per FTE:", 0, 0)
        pdf.set_font('Arial', 'B', 11); pdf.cell(0, 10, f"{rvu_fte:,.2f}", 0, 1)
        pdf.ln(10)
        pdf.set_font('Arial', 'B', 12); pdf.cell(0, 10, "Provider Breakdown", 1, 1, 'L', fill=True)
        pdf.set_font('Arial', 'B', 10); pdf.cell(90, 10, "Provider Name", 1, 0, 'C'); pdf.cell(50, 10, "Total wRVUs", 1, 1, 'C')
        pdf.set_font('Arial', '', 10)
        if not provider_df.empty:
            for _, row in provider_df.iterrows():
                pdf.cell(90, 10, str(row['Name']), 1, 0)
                pdf.cell(50, 10, f"{row['Total RVUs']:,.2f}", 1, 1, 'R')
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
        st.text_input("❌ Access Denied", type="password", on_change=password_entered, key="password")
        return False
    return True

# --- 2. DATA SOURCE CONFIG ---
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
    CONSULT_CPT = "77263"
    CONSULT_CONVERSION = 3.14
    APP_CPT_RATES = {"99212": 0.7, "99213": 1.3, "99214": 1.92, "99215": 2.8}
    POS_ROW_MAPPING = {"CENTENNIAL RAD": "CENT", "DICKSON RAD": "Dickson", "MIDTOWN RAD": "Midtown", "MURFREESBORO RAD": "MURF", "SAINT THOMAS WEST RAD": "STW", "SKYLINE RAD": "Skyline", "STONECREST RAD": "Stonecrest", "SUMMIT RAD": "Summit", "SUMNER RAD": "Sumner", "LEBANON RAD": "LROC", "TULLAHOMA RADIATION": "TROC", "TO PROTON": "TOPC"}

    class LocalFile:
        def __init__(self, path):
            self.path = path
            self.name = os.path.basename(path).upper()

    def standardize_date(x):
        if pd.isna(x): return pd.NaT
        if isinstance(x, (datetime, pd.Timestamp)): return pd.Timestamp(year=x.year, month=x.month, day=1)
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
            return float(val_str) if val_str not in ["", "-"] else 0.0
        except: return 0.0

    def match_provider(name_str):
        if not isinstance(name_str, str) or not name_str.strip(): return None
        parts = name_str.split(",")[0].strip().split()
        if not parts: return None
        last_name = parts[0].upper()
        if last_name == "FRIEDMEN": last_name = "FRIEDMAN"
        return PROVIDER_KEYS_UPPER.get(last_name)

    def get_historical_df():
        records = []
        for year, data in HISTORICAL_DATA.items():
            for clinic_id, rvu in data.items():
                if clinic_id in CLINIC_CONFIG:
                    records.append({"ID": clinic_id, "Name": CLINIC_CONFIG[clinic_id]["name"], "Year": year, "Total RVUs": rvu})
        return pd.DataFrame(records)

    def safe_dedup_and_format(df_list, subset_cols):
        if not df_list: return pd.DataFrame()
        df = pd.concat(df_list, ignore_index=True)
        if 'Month_Clean' in df.columns:
            df['Month_Clean'] = df['Month_Clean'].apply(standardize_date)
            df = df.dropna(subset=['Month_Clean'])
            sort_by = ['Month_Clean']
            if 'Total RVUs' in df.columns: sort_by.append('Total RVUs')
            df = df.sort_values(sort_by, ascending=[False, False])
        valid_subset = [c for c in subset_cols if c in df.columns]
        if valid_subset: df = df.drop_duplicates(subset=valid_subset, keep='first')
        if not df.empty and 'Month_Clean' in df.columns:
            df['Month_Label'] = df['Month_Clean'].dt.strftime('%b-%y')
            df['Quarter'] = df['Month_Clean'].apply(lambda x: f"Q{x.quarter} {x.year}")
        return df

    # --- RESTORED PARSERS ---
    def find_date_row(df):
        months = ["JAN", "FEB", "MAR", "APR", "MAY", "JUN", "JUL", "AUG", "SEP", "OCT", "NOV", "DEC"]
        best_row = 1; max_score = 0
        for r in range(min(10, len(df))):
            row_vals = [str(v).upper() for v in df.iloc[r, 4:16] if pd.notna(v)]
            score = sum(1 for v in row_vals if any(m in v for m in months))
            if score > max_score: max_score = score; best_row = r
        return best_row

    def parse_rvu_sheet(df, sname, entity_type, clinic_tag="General", target_year=None):
        if entity_type == 'clinic':
            cfg = CLINIC_CONFIG.get(sname, {"name": sname, "fte": 1.0})
            name, fte = cfg['name'], cfg['fte']
        else:
            name, fte = sname, PROVIDER_CONFIG.get(sname, 1.0)
        df.iloc[:, 0] = df.iloc[:, 0].astype(str).str.strip().str.upper()
        data_rows = df[df.iloc[:, 0].isin(TARGET_CATEGORIES)]
        recs = []; header_idx = find_date_row(df)
        for col in range(4, len(df.columns)):
            dt = standardize_date(df.iloc[header_idx, col])
            if pd.isna(dt) or (target_year and dt.year != target_year): continue
            val = pd.to_numeric(data_rows.iloc[:, col], errors='coerce').sum()
            recs.append({"Type": entity_type, "ID": sname, "Name": name, "FTE": fte, "Month_Clean": dt, "Total RVUs": val, "Clinic_Tag": clinic_tag})
        return pd.DataFrame(recs)

    def parse_financial_sheet(df, file_date, tag, mode="Provider"):
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
        if header_row == -1: return pd.DataFrame()
        recs = []
        for i in range(header_row + 1, len(df)):
            row = df.iloc[i].values
            p_name = match_provider(str(row[col_map.get('name', 0)]))
            if p_name:
                recs.append({"Name": p_name, "Month_Clean": standardize_date(file_date), "Charges": clean_number(row[col_map.get('charges', 1)]), "Payments": clean_number(row[col_map.get('payments', 2)]), "Mode": mode, "Tag": tag})
        return pd.DataFrame(recs)

    def process_files(file_objects):
        clinic_data, provider_data, fin_data, pos_data = [], [], [], []
        for f_obj in file_objects:
            path_or_buf = f_obj if hasattr(f_obj, 'read') else f_obj.path
            fname = f_obj.name.upper()
            xls = pd.read_excel(path_or_buf, sheet_name=None, header=None)
            target_year = int(re.search(r'202[4-6]', fname).group(0)) if re.search(r'202[4-6]', fname) else None
            
            for sname, df in xls.items():
                s_up = sname.upper()
                if "RAD BY PROVIDER" in fname:
                    res = parse_financial_sheet(df, datetime.now(), "RAD", "Provider")
                    if not res.empty: fin_data.append(res)
                if sname in CLINIC_CONFIG:
                    res = parse_rvu_sheet(df, sname, 'clinic', target_year=target_year)
                    if not res.empty: clinic_data.append(res)
                p_match = match_provider(sname)
                if p_match:
                    res = parse_rvu_sheet(df, p_match, 'provider', target_year=target_year)
                    if not res.empty: provider_data.append(res)
        
        return safe_dedup_and_format(clinic_data, ['ID', 'Month_Clean']), \
               safe_dedup_and_format(provider_data, ['Name', 'Month_Clean']), \
               safe_dedup_and_format(fin_data, ['Name', 'Month_Clean']), \
               pd.DataFrame()

    # --- 3. UI ASSEMBLY ---
    st.title("🩺 Radiation Oncology Division Analytics")
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
        df_c, df_p, df_f, df_pos = process_files(all_f)
        tab_c26, tab_c25, tab_md, tab_fin = st.tabs(["🏥 Clinic 2026", "🏥 Clinic 2025", "👨‍⚕️ MD Analytics", "💰 Financials"])

        def render_historical_table(df_curr, yr, filter_ids=None):
            hist = get_historical_df()
            if filter_ids: hist = hist[hist['ID'].isin(filter_ids)]
            agg = hist.groupby('Year')[['Total RVUs']].sum().reset_index()
            ytd = df_curr[df_curr['Month_Clean'].dt.year == yr]['Total RVUs'].sum()
            if yr in agg['Year'].values: agg.loc[agg['Year'] == yr, 'Total RVUs'] = ytd
            else: agg = pd.concat([agg, pd.DataFrame([{"Year": yr, "Total RVUs": ytd}])])
            agg['Year'] = agg['Year'].astype(str)
            # COLLAPSE DUPLICATES BEFORE FLIP
            st.dataframe(agg.groupby('Year').sum().T.style.format("{:,.0f}"), use_container_width=True)

        with tab_c26:
            c_filter = st.radio("View:", ["All", "TriStar", "Ascension"], key="r26", horizontal=True)
            f_ids = TRISTAR_IDS if c_filter == "TriStar" else (ASCENSION_IDS if c_filter == "Ascension" else None)
            render_historical_table(df_c, 2026, f_ids)
            curr_c = df_c[df_c['Month_Clean'].dt.year == 2026]
            if f_ids: curr_c = curr_c[curr_c['ID'].isin(f_ids)]
            if not curr_c.empty:
                st.plotly_chart(style_high_end_chart(px.line(curr_c.sort_values('Month_Clean'), x='Month_Clean', y='Total RVUs', color='Name', markers=True)), use_container_width=True)
                piv = curr_c.pivot_table(index="Name", columns="Month_Label", values="Total RVUs", aggfunc="sum").fillna(0)
                st.dataframe(piv.style.format("{:,.0f}").background_gradient(cmap="Blues"), use_container_width=True)

        with tab_c25:
            render_historical_table(df_c, 2025)
            curr_c25 = df_c[df_c['Month_Clean'].dt.year == 2025]
            if not curr_c25.empty:
                st.plotly_chart(style_high_end_chart(px.line(curr_c25.sort_values('Month_Clean'), x='Month_Clean', y='Total RVUs', color='Name', markers=True)), use_container_width=True)

        with tab_md:
            df_p26 = df_p[df_p['Month_Clean'].dt.year == 2026]
            if not df_p26.empty:
                st.plotly_chart(style_high_end_chart(px.bar(df_p26.groupby('Name')['Total RVUs'].sum().reset_index().sort_values('Total RVUs'), x='Total RVUs', y='Name', orientation='h', text_auto='.2s')), use_container_width=True)

        with tab_fin:
            if not df_f.empty:
                latest_f = df_f[df_f['Month_Clean'] == df_f['Month_Clean'].max()]
                st.dataframe(latest_f.style.format({'Charges': '${:,.0f}', 'Payments': '${:,.0f}'}).background_gradient(cmap="Greens"), use_container_width=True)
    else:
        st.info("👋 Upload files or check 'Reports' folder.")
