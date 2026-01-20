import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime
import os
import re

# --- PASSWORD CONFIGURATION ---
APP_PASSWORD = "RadOnc2026"

# ==========================================
# --- 1. HISTORICAL DATA ENTRY (2019-2024) ---
# ==========================================
HISTORICAL_DATA = {
    2019: {"CENT": 18430, "Dickson": 11420, "Skyline": 13910, "Summit": 14690, "Stonecrest": 8600, "STW": 22030, "Midtown": 14730, "MURF": 38810, "Sumner": 14910, "TOPC": 15690, "LROC": 0, "TROC": 0},
    2020: {"CENT": 19160, "Dickson": 12940, "Skyline": 13180, "Summit": 11540, "Stonecrest": 7470, "STW": 17070, "Midtown": 14560, "MURF": 37890, "Sumner": 14760, "TOPC": 22010, "LROC": 0, "TROC": 0},
    2021: {"CENT": 14480, "Dickson": 10980, "Skyline": 11450, "Summit": 11700, "Stonecrest": 8610, "STW": 17970, "Midtown": 17890, "MURF": 37440, "Sumner": 17670, "TOPC": 28540, "LROC": 0, "TROC": 0},
    2022: {"CENT": 15860, "Dickson": 13960, "Skyline": 14520, "Summit": 12390, "Stonecrest": 10580, "STW": 27650, "Midtown": 19020, "MURF": 37870, "Sumner": 20570, "TOPC": 28830, "LROC": 0, "TROC": 0},
    2023: {"CENT": 19718, "Dickson": 11600, "Skyline": 17804, "Summit": 14151, "Stonecrest": 11647, "STW": 23717, "Midtown": 21017, "MURF": 42201, "Sumner": 22622, "TOPC": 27667, "LROC": 0, "TROC": 0},
    2024: {"CENT": 22385, "Dickson": 12155, "Skyline": 15363, "Summit": 12892, "Stonecrest": 12524, "STW": 25409, "Midtown": 21033, "MURF": 45648, "Sumner": 23803, "TOPC": 33892, "LROC": 0, "TROC": 0}
}

def check_password():
    if "password_correct" not in st.session_state:
        st.session_state["password_correct"] = False
    
    if not st.session_state["password_correct"]:
        pwd = st.text_input("🔒 Enter Dashboard Password:", type="password")
        if pwd == APP_PASSWORD:
            st.session_state["password_correct"] = True
            st.rerun()
        return False
    return True

# --- CUSTOM CSS ---
def inject_custom_css():
    st.markdown("""
        <style>
        .stTabs [data-baseweb="tab-list"] { gap: 24px; background-color: transparent; padding-bottom: 15px; border-bottom: 1px solid #ddd; }
        .stTabs [data-baseweb="tab-list"] button { background-color: #FFFFFF; border: 1px solid #D1D5DB; border-radius: 6px; color: #4B5563; padding: 14px 30px; box-shadow: 0 1px 2px rgba(0,0,0,0.05); }
        .stTabs [data-baseweb="tab-list"] button [data-testid="stMarkdownContainer"] p { font-size: 20px !important; font-weight: 700 !important; margin: 0px; }
        .stTabs [data-baseweb="tab-list"] button[aria-selected="true"] { background-color: #1E3A8A !important; color: #FFFFFF !important; border-color: #1E3A8A; }
        .stTabs [data-baseweb="tab-highlight"] { background-color: transparent !important; }
        </style>
    """, unsafe_allow_html=True)

if check_password():
    inject_custom_css()
    
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

    def clean_number(val):
        if pd.isna(val): return None
        try:
            val_str = str(val).strip()
            if val_str.startswith("(") and val_str.endswith(")"): val_str = "-" + val_str[1:-1]
            val_str = val_str.replace(',', '').replace('%', '')
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

    def generate_narrative(df, entity_type="Provider", metric_col="Total RVUs", unit="wRVUs"):
        if df.empty: return "No data available."
        latest_date = df['Month_Clean'].max()
        latest_df = df[df['Month_Clean'] == latest_date]
        if latest_df.empty: return "Data processed but current month is empty."
        total_vol = latest_df[metric_col].sum()
        
        if metric_col == "Total RVUs":
            top_perf = latest_df.loc[latest_df['RVU per FTE'].idxmax()]
            top_val = top_perf['RVU per FTE']; top_metric = "wRVUs/FTE"
        else:
            top_perf = latest_df.loc[latest_df[metric_col].idxmax()]
            top_val = top_perf[metric_col]; top_metric = unit

        return f"""**🤖 Automated Analysis ({latest_date.strftime('%B %Y')}):**
        The {entity_type} group generated a total of **{total_vol:,.0f} {unit}** this month. 
        * **🏆 Top Performer:** **{clean_provider_name_display(top_perf['Name'])}** led with **{top_val:,.0f} {top_metric}**."""

    # --- PARSERS ---
    def parse_sumner_prov_sheet(df, filename_date):
        records = []
        current_provider = None
        current_values = {"E&M OFFICE CODES": 0.0, "RADIATION CODES": 0.0, "SPECIAL PROCEDURES": 0.0}
        term_counts = {k: 0 for k in current_values}
        target_terms = list(current_values.keys())
        
        for i in range(len(df)):
            row = df.iloc[i].values
            potential_name = None
            for c in range(min(5, len(row))):
                val = str(row[c]).strip()
                match = match_provider(val)
                if match: potential_name = match; break
            
            if potential_name and potential_name != current_provider:
                if current_provider:
                    total_rvu = sum(current_values.values())
                    if total_rvu > 0:
                        records.append({
                            "Type": "provider", "ID": "Sumner", "Name": current_provider, "FTE": 1.0,
                            "Month": filename_date, "Total RVUs": total_rvu, "RVU per FTE": total_rvu,
                            "Clinic_Tag": "Sumner", "Quarter": f"Q{filename_date.quarter} {filename_date.year}",
                            "Month_Label": filename_date.strftime('%b-%y'), "source_type": "sumner_detail"
                        })
                current_provider = potential_name
                term_counts = {k: 0 for k in target_terms}; current_values = {k: 0.0 for k in target_terms}
                continue 

            if current_provider:
                row_str_upper = " ".join([str(x).upper() for x in row[:5]])
                for term in target_terms:
                    if term in row_str_upper:
                        term_counts[term] += 1
                        if term_counts[term] == 2:
                            if len(row) > 19:
                                val = clean_number(row[19]) 
                                if val: current_values[term] = val
        
        if current_provider:
            total_rvu = sum(current_values.values())
            if total_rvu > 0:
                records.append({
                    "Type": "provider", "ID": "Sumner", "Name": current_provider, "FTE": 1.0,
                    "Month": filename_date, "Total RVUs": total_rvu, "RVU per FTE": total_rvu,
                    "Clinic_Tag": "Sumner", "Quarter": f"Q{filename_date.quarter} {filename_date.year}",
                    "Month_Label": filename_date.strftime('%b-%y'), "source_type": "sumner_detail"
                })
        return pd.DataFrame(records)

    def parse_rvu_sheet(df, sheet_name, entity_type, clinic_tag="General", forced_fte=None):
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
                col_sum = pd.to_numeric(data_rows[col], errors='coerce').sum()
                records.append({
                    "Type": entity_type, "ID": sheet_name, "Name": name, "FTE": fte,
                    "Month": header_val, "Total RVUs": col_sum, "RVU per FTE": col_sum / fte if fte > 0 else 0,
                    "Clinic_Tag": clinic_tag, "source_type": "standard"
                })
        return pd.DataFrame(records)

    # --- UPDATED: PARSE VISITS (NO ANCHOR, SCAN ALL) ---
    def parse_visits_sheet(df, filename_date, clinic_tag="General"):
        records = []
        try:
            # 2. SCAN EVERY ROW FROM 5 DOWNWARDS (No "Physicians Only" Check)
            for i in range(5, len(df)):
                row = df.iloc[i].values
                row_str_check = " ".join([str(x).upper() for x in row[:5]])
                
                # Skip invalid rows (Totals, Page Numbers, Dates)
                if "TOTAL" in row_str_check or "PAGE" in row_str_check or "DATE" in row_str_check: 
                    continue

                matched_name = None
                # SCAN WIDE (First 10 cols)
                for c in range(min(10, len(row))): 
                    val = str(row[c]).strip()
                    matched_name = match_provider(val) 
                    if matched_name: break
                
                if not matched_name: continue

                # Safe Extract Numbers
                numbers = []
                for val in row:
                    num = clean_number(val)
                    if num is not None:
                        numbers.append(num)
                
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
        return pd.DataFrame(records)

    def process_files(file_objects):
        clinic_data = []; provider_data = []; visit_data = []
        for file_obj in file_objects:
            if isinstance(file_obj, LocalFile):
                filename = file_obj.name; xls = pd.read_excel(file_obj.path, sheet_name=None, header=None)
            else:
                filename = file_obj.name.upper(); xls = pd.read_excel(file_obj, sheet_name=None, header=None)
            
            file_tag = "General"
            if "LROC" in filename: file_tag = "LROC"
            elif "TROC" in filename: file_tag = "TROC"
            elif "PROTON" in filename or "TOPC" in filename: file_tag = "TOPC"

            if "NEW PATIENTS" in filename or "NEW PT" in filename:
                file_date = get_date_from_filename(filename)
                visit_tag = "General"
                if "LROC" in filename: visit_tag = "LROC"
                elif "TROC" in filename: visit_tag = "TROC"

                for sheet_name, df in xls.items():
                    if "PHYS YTD OV" in sheet_name.upper():
                        res = parse_visits_sheet(df, file_date, clinic_tag=visit_tag)
                        if not res.empty: visit_data.append(res)
                continue 

            for sheet_name, df in xls.items():
                s_lower = sheet_name.strip().lower()
                if "sumner prov" in s_lower:
                    file_date = get_date_from_filename(filename)
                    res = parse_sumner_prov_sheet(df, file_date)
                    if not res.empty: provider_data.append(res)
                    continue

            if file_tag == "TOPC":
                proton_providers_temp = []
                for sheet_name, df in xls.items():
                    s_upper = sheet_name.upper()
                    if any(ignored in s_upper for ignored in IGNORED_SHEETS) or "PROTON POS" in s_upper: continue
                    if "PRODUCTIVITY TREND" in s_upper: continue 
                    clean_name = sheet_name.strip()
                    if clean_name.upper() == "FRIEDMEN": clean_name = "Friedman"
                    res = parse_rvu_sheet(df, clean_name, 'provider', clinic_tag="TOPC")
                    if not res.empty: provider_data.append(res); proton_providers_temp.append(res)
                if proton_providers_temp:
                    combined_proton = pd.concat(proton_providers_temp)
                    topc_grp = combined_proton.groupby('Month', as_index=False)[['Total RVUs', 'FTE']].sum()
                    topc_records = []
                    for idx, row in topc_grp.iterrows():
                         topc_records.append({
                            "Type": "clinic", "ID": "TOPC", "Name": "TN Proton Center", "FTE": row['FTE'], 
                            "Month": row['Month'], "Total RVUs": row['Total RVUs'], "RVU per FTE": row['Total RVUs'] / row['FTE'] if row['FTE'] > 0 else 0,
                            "Clinic_Tag": "TOPC", "source_type": "standard", 
                            "Month_Clean": pd.to_datetime(f"{row['Month']} {datetime.now().year}", errors='coerce')
                         })
                    clinic_data.append(pd.DataFrame(topc_records))
            else:
                for sheet_name, df in xls.items():
                    clean_name = sheet_name.strip(); s_lower = clean_name.lower()
                    if "sumner prov" in s_lower: continue 
                    s_upper = clean_name.upper()
                    if clean_name.upper() == "FRIEDMEN": clean_name = "Friedman"
                    is_summary_sheet = "PRODUCTIVITY TREND" in s_upper
                    
                    if (file_tag in ["LROC", "TROC"]) and is_summary_sheet:
                        res = parse_rvu_sheet(df, file_tag, 'clinic', clinic_tag=file_tag)
                        if not res.empty: clinic_data.append(res)
                        continue 
                    if clean_name in CLINIC_CONFIG:
                        res = parse_rvu_sheet(df, clean_name, 'clinic', clinic_tag="General")
                        if not res.empty: clinic_data.append(res)
                        continue
                    if is_summary_sheet: continue
                    if any(ignored in s_upper for ignored in IGNORED_SHEETS): continue
                    if clean_name.lower().endswith(" prov"): continue
                    res = parse_rvu_sheet(df, clean_name, 'provider', clinic_tag=file_tag)
                    if not res.empty: provider_data.append(res)

        df_clinic = pd.concat(clinic_data, ignore_index=True) if clinic_data else pd.DataFrame()
        df_provider_raw = pd.concat(provider_data, ignore_index=True) if provider_data else pd.DataFrame()
        df_visits = pd.concat(visit_data, ignore_index=True) if visit_data else pd.DataFrame()

        # GLOBAL DATE & QUARTER CALCULATION (CRITICAL FOR KEYERROR)
        if not df_clinic.empty:
             if 'Month_Clean' not in df_clinic.columns:
                 df_clinic['Month_Clean'] = pd.to_datetime(df_clinic['Month'], format='%b-%y', errors='coerce')
             df_clinic.dropna(subset=['Month_Clean'], inplace=True)
             df_clinic['Month_Label'] = df_clinic['Month_Clean'].dt.strftime('%b-%y')
             df_clinic['Quarter'] = df_clinic['Month_Clean'].apply(lambda x: f"Q{pd.Timestamp(x).quarter} {pd.Timestamp(x).year}")

        if not df_provider_raw.empty:
            if 'Month_Clean' not in df_provider_raw.columns:
                df_provider_raw['Month_Clean'] = pd.to_datetime(df_provider_raw['Month'], format='%b-%y', errors='coerce')
            mask = df_provider_raw['Month_Clean'].isna()
            if mask.any(): df_provider_raw.loc[mask, 'Month_Clean'] = pd.to_datetime(df_provider_raw.loc[mask, 'Month'], errors='coerce')
            df_provider_raw.dropna(subset=['Month_Clean'], inplace=True)
            df_provider_raw['Month_Label'] = df_provider_raw['Month_Clean'].dt.strftime('%b-%y')
            df_provider_raw['Quarter'] = df_provider_raw['Month_Clean'].apply(lambda x: f"Q{pd.Timestamp(x).quarter} {pd.Timestamp(x).year}")

        df_provider_global = pd.DataFrame()
        if not df_provider_raw.empty:
            df_md_clean = df_provider_raw[df_provider_raw.get('source_type', 'standard') != 'sumner_detail'].copy()
            df_provider_global = df_md_clean.groupby(['Name', 'ID', 'Month_Clean'], as_index=False).agg({
                'Total RVUs': 'sum', 'FTE': 'max', 'Month': 'first', 'Quarter': 'first', 'Month_Label': 'first'
            })
            df_provider_global['RVU per FTE'] = df_provider_global.apply(lambda x: x['Total RVUs'] / x['FTE'] if x['FTE'] > 0 else 0, axis=1)
            df_provider_global.sort_values('Month_Clean', inplace=True)

        return df_clinic, df_provider_global, df_provider_raw, df_visits

    # --- MAIN UI ---
    st.set_page_config(page_title="RadOnc Analytics", layout="wide", page_icon="🩺")
    st.title("🩺 Radiation Oncology Division Analytics")
    st.markdown("##### by Dr. Jones")
    st.markdown("---")

    server_files = []
    if os.path.exists(SERVER_DIR):
        for f in os.listdir(SERVER_DIR):
            if f.endswith(".xlsx") or f.endswith(".xls"):
                server_files.append(LocalFile(os.path.join(SERVER_DIR, f)))

    with st.sidebar:
        st.header("Data Import")
        if server_files: st.success(f"✅ Loaded {len(server_files)} master files.")
        else: st.info("ℹ️ No master files found.")
        uploaded_files = st.file_uploader("Add Temporary Files", type=['xlsx', 'xls'], accept_multiple_files=True)
    
    all_files = server_files + (uploaded_files if uploaded_files else [])

    if all_files:
        with st.spinner("Analyzing files..."):
            df_clinic, df_md_global, df_provider_raw, df_visits = process_files(all_files)

        if df_clinic.empty and df_md_global.empty and df_visits.empty:
            st.error("No valid data found.")
        else:
            if not df_md_global.empty:
                df_apps = df_md_global[df_md_global['Name'].isin(APP_LIST)]
                df_mds = df_md_global[~df_md_global['Name'].isin(APP_LIST)]
            else:
                df_apps = pd.DataFrame(); df_mds = pd.DataFrame()

            tab_c, tab_md, tab_app = st.tabs(["🏥 Clinic Analytics", "👨‍⚕️ MD Analytics", "👩‍⚕️ APP Analytics"])

            with tab_c:
                col_nav, col_main = st.columns([1, 5])
                with col_nav:
                    st.markdown("### 🔍 Filter")
                    clinic_filter = st.radio("Select View:", ["All", "TriStar", "Ascension", "LROC", "TOPC", "TROC", "Sumner"], key="clinic_radio")
                with col_main:
                    df_view = pd.DataFrame(); view_title = clinic_filter; target_tag = None
                    if clinic_filter == "All": df_view = df_clinic.copy(); view_title = "All Clinics"
                    elif clinic_filter == "TriStar": df_view = df_clinic[df_clinic['ID'].isin(TRISTAR_IDS)]; view_title = "TriStar Group"
                    elif clinic_filter == "Ascension": df_view = df_clinic[df_clinic['ID'].isin(ASCENSION_IDS)]; view_title = "Ascension Group"
                    elif clinic_filter == "LROC": df_view = df_clinic[df_clinic['ID'] == 'LROC']; view_title = "LROC (Lebanon)"; target_tag = "LROC"
                    elif clinic_filter == "TOPC": df_view = df_clinic[df_clinic['ID'] == 'TOPC']; view_title = "TN Proton Center"; target_tag = "TOPC"
                    elif clinic_filter == "TROC": df_view = df_clinic[df_clinic['ID'] == 'TROC']; view_title = "TROC (Tullahoma)"; target_tag = "TROC"
                    elif clinic_filter == "Sumner": df_view = df_clinic[df_clinic['ID'] == 'Sumner']; view_title = "Sumner (Gallatin)"; target_tag = "Sumner"

                    if df_view.empty and clinic_filter not in ["TriStar", "Ascension"]:
                        st.warning(f"No data available for {view_title}.")
                    else:
                        max_date = df_view['Month_Clean'].max()
                        st.info(generate_narrative(df_view, f"{view_title} Clinic"))
                        
                        with st.container(border=True):
                            st.markdown(f"#### 📅 {view_title}: 12-Month Trend")
                            min_date = max_date - pd.DateOffset(months=11)
                            l12m_c = df_view[df_view['Month_Clean'] >= min_date].sort_values('Month_Clean')
                            if clinic_filter in ["TriStar", "Ascension", "All"]:
                                agg_trend = l12m_c.groupby('Month_Clean')[['Total RVUs']].sum().reset_index()
                                fig_trend = px.line(agg_trend, x='Month_Clean', y='Total RVUs', markers=True, title="Aggregate Trend")
                            else:
                                fig_trend = px.line(l12m_c, x='Month_Clean', y='Total RVUs', color='Name', markers=True)
                            st.plotly_chart(fig_trend, use_container_width=True)

                        if clinic_filter in ["TriStar", "Ascension", "All"]:
                            with st.container(border=True):
                                st.markdown(f"#### 📈 {view_title}: Individual Clinic Trends")
                                fig_ind = px.line(l12m_c, x='Month_Clean', y='Total RVUs', color='Name', markers=True)
                                st.plotly_chart(fig_ind, use_container_width=True)

                        if clinic_filter in ["TriStar", "Ascension", "All", "LROC", "TOPC", "TROC", "Sumner"]:
                            with st.container(border=True):
                                st.markdown(f"#### 📈 Long-Term History ({view_title})")
                                df_hist = get_historical_df()
                                if clinic_filter == "TriStar": df_hist_view = df_hist[df_hist['ID'].isin(TRISTAR_IDS)]
                                elif clinic_filter == "Ascension": df_hist_view = df_hist[df_hist['ID'].isin(ASCENSION_IDS)]
                                elif clinic_filter == "All": df_hist_view = df_hist.copy()
                                elif clinic_filter == "Sumner": df_hist_view = df_hist[df_hist['ID'] == 'Sumner']
                                else: target_id = 'LROC' if 'LROC' in clinic_filter else ('TOPC' if 'Proton' in view_title else 'TROC'); df_hist_view = df_hist[df_hist['ID'] == target_id]
                                
                                if not df_hist_view.empty:
                                    hist_trend = df_hist_view.groupby('Year')[['Total RVUs']].sum().reset_index()
                                    if not df_view.empty:
                                        current_year = max_date.year
                                        ytd_curr = df_view[df_view['Month_Clean'].dt.year == current_year]['Total RVUs'].sum()
                                        if ytd_curr > 0:
                                            new_row = pd.DataFrame({"Year": [current_year], "Total RVUs": [ytd_curr]})
                                            hist_trend = pd.concat([hist_trend, new_row], ignore_index=True)
                                    fig_long = px.bar(hist_trend, x='Year', y='Total RVUs', text_auto='.2s')
                                    st.plotly_chart(fig_long, use_container_width=True)
                                    
                                    if clinic_filter in ["TriStar", "Ascension"]:
                                        st.markdown("---"); st.markdown("##### 🏥 Individual Clinic History")
                                        target_ids = TRISTAR_IDS if clinic_filter == "TriStar" else ASCENSION_IDS
                                        cols = st.columns(2)
                                        for idx, c_id in enumerate(target_ids):
                                            c_name = CLINIC_CONFIG.get(c_id, {}).get('name', c_id)
                                            c_hist = df_hist[df_hist['ID'] == c_id]
                                            c_hist_grp = c_hist.groupby('Year')[['Total RVUs']].sum().reset_index()
                                            if not df_view.empty:
                                                c_current = df_view[df_view['ID'] == c_id]
                                                current_year = max_date.year
                                                ytd_c = c_current[c_current['Month_Clean'].dt.year == current_year]['Total RVUs'].sum()
                                                if ytd_c > 0:
                                                    new_r = pd.DataFrame({"Year": [current_year], "Total RVUs": [ytd_c]})
                                                    c_hist_grp = pd.concat([c_hist_grp, new_r], ignore_index=True)
                                            if not c_hist_grp.empty:
                                                fig_c = px.bar(c_hist_grp, x='Year', y='Total RVUs', text_auto='.2s', title=c_name)
                                                fig_c.update_layout(height=350)
                                                with cols[idx % 2]: st.plotly_chart(fig_c, use_container_width=True)

                        if target_tag and not df_provider_raw.empty:
                            pie_data_source = df_provider_raw
                            if target_tag == 'Sumner': pie_data_source = df_provider_raw[df_provider_raw.get('source_type', '') == 'sumner_detail']
                            elif target_tag: pie_data_source = df_provider_raw[df_provider_raw['Clinic_Tag'] == target_tag]

                            if not pie_data_source.empty:
                                try:
                                    min_pie_date = max_date - pd.DateOffset(months=11)
                                    pie_12m = pie_data_source[pie_data_source['Month_Clean'] >= min_pie_date]
                                    pie_agg_12m = pie_12m.groupby('Name')[['Total RVUs']].sum().reset_index()
                                    latest_q = pie_data_source['Quarter'].max()
                                    pie_q = pie_data_source[pie_data_source['Quarter'] == latest_q]
                                    pie_agg_q = pie_q.groupby('Name')[['Total RVUs']].sum().reset_index()

                                    if not pie_agg_12m.empty:
                                        with st.container(border=True):
                                            st.markdown(f"#### 🍰 Work Breakdown: Who performed the work?")
                                            col_pie1, col_pie2 = st.columns(2)
                                            with col_pie1:
                                                fig_p1 = px.pie(pie_agg_12m, values='Total RVUs', names='Name', hole=0.4, title="Last 12 Months")
                                                st.plotly_chart(fig_p1, use_container_width=True)
                                            with col_pie2:
                                                if not pie_agg_q.empty:
                                                    fig_p2 = px.pie(pie_agg_q, values='Total RVUs', names='Name', hole=0.4, title=f"Most Recent Quarter ({latest_q})")
                                                    st.plotly_chart(fig_p2, use_container_width=True)
                                except: st.info("Insufficient data for pie charts.")

                        if not df_view.empty:
                            c1, c2 = st.columns(2)
                            with c1:
                                st.markdown("#### 🔢 Monthly Data")
                                piv = df_view.pivot_table(index="Name", columns="Month_Label", values="Total RVUs", aggfunc="sum").fillna(0)
                                piv["Total"] = piv.sum(axis=1)
                                st.dataframe(piv.sort_values("Total", ascending=False).style.format("{:,.0f}").background_gradient(cmap="Reds"))
                            with c2:
                                st.markdown("#### 📆 Quarterly Data")
                                piv_q = df_view.pivot_table(index="Name", columns="Quarter", values="Total RVUs", aggfunc="sum").fillna(0)
                                piv_q["Total"] = piv_q.sum(axis=1)
                                st.dataframe(piv_q.sort_values("Total", ascending=False).style.format("{:,.0f}").background_gradient(cmap="Oranges"))
                        
                        if target_tag in ["LROC", "TROC"] and not df_visits.empty:
                            clinic_visits = df_visits[df_visits['Clinic_Tag'] == target_tag]
                            if not clinic_visits.empty:
                                with st.container(border=True):
                                    st.markdown("### 🏥 Office Visits & New Patients (New Data Source)")
                                    latest_v_date = clinic_visits['Month_Clean'].max()
                                    latest_v_df = clinic_visits[clinic_visits['Month_Clean'] == latest_v_date]
                                    c_v1, c_v2 = st.columns(2)
                                    with c_v1:
                                        fig_ov = px.bar(latest_v_df.sort_values('Total Visits', ascending=True), x='Total Visits', y='Name', orientation='h', text_auto=True, color='Total Visits', color_continuous_scale='Blues', title=f"Total Office Visits ({latest_v_date.strftime('%b %Y')})")
                                        st.plotly_chart(fig_ov, use_container_width=True)
                                    with c_v2:
                                        fig_np = px.bar(latest_v_df.sort_values('New Patients', ascending=True), x='New Patients', y='Name', orientation='h', text_auto=True, color='New Patients', color_continuous_scale='Greens', title=f"New Patients ({latest_v_date.strftime('%b %Y')})")
                                        st.plotly_chart(fig_np, use_container_width=True)

            with tab_md:
                col_nav_md, col_main_md = st.columns([1, 5])
                with col_nav_md:
                    st.markdown("### 📊 Metric")
                    md_view = st.radio("Select View:", ["wRVU Productivity", "Office Visits"], key="md_radio")
                
                with col_main_md:
                    if md_view == "wRVU Productivity":
                        if df_mds.empty: st.info("No wRVU data found.")
                        else:
                            st.info(generate_narrative(df_mds, "Physician"))
                            with st.container(border=True):
                                st.markdown("#### 📅 Last 12 Months Trend (RVU per FTE)")
                                fig_trend = px.line(df_mds.sort_values('Month_Clean'), x='Month_Clean', y='RVU per FTE', color='Name', markers=True)
                                st.plotly_chart(fig_trend, use_container_width=True)
                            with st.container(border=True):
                                st.markdown(f"#### 🏆 Year-to-Date Total RVUs ({df_mds['Month_Clean'].max().year})")
                                ytd_sum = df_mds[df_mds['Month_Clean'].dt.year == df_mds['Month_Clean'].max().year].groupby('Name')[['Total RVUs']].sum().reset_index().sort_values('Total RVUs', ascending=False)
                                fig_ytd = px.bar(ytd_sum, x='Name', y='Total RVUs', color='Total RVUs', color_continuous_scale='Viridis', text_auto='.2s')
                                st.plotly_chart(fig_ytd, use_container_width=True)
                            c1, c2 = st.columns(2)
                            with c1:
                                st.markdown("#### 🔢 Monthly Data")
                                piv = df_mds.pivot_table(index="Name", columns="Month_Label", values="Total RVUs", aggfunc="sum").fillna(0)
                                piv["Total"] = piv.sum(axis=1)
                                st.dataframe(piv.sort_values("Total", ascending=False).style.format("{:,.0f}").background_gradient(cmap="Blues"))
                            with c2:
                                st.markdown("#### 📆 Quarterly Data")
                                piv_q = df_mds.pivot_table(index="Name", columns="Quarter", values="Total RVUs", aggfunc="sum").fillna(0)
                                piv_q["Total"] = piv_q.sum(axis=1)
                                st.dataframe(piv_q.sort_values("Total", ascending=False).style.format("{:,.0f}").background_gradient(cmap="Purples"))
                    
                    elif md_view == "Office Visits":
                        st.warning("⚠️ **Currently only displaying the non-TO Photon Sites**")
                        if df_visits.empty:
                            st.warning("No Office Visit data found.")
                        else:
                            df_visits_agg = df_visits.groupby(['Name', 'Month_Clean'], as_index=False).agg({'Total Visits': 'sum', 'New Patients': 'sum', 'Visits_Diff': 'sum', 'NP_Diff': 'sum'})
                            latest_v_date = df_visits_agg['Month_Clean'].max()
                            latest_v_df = df_visits_agg[df_visits_agg['Month_Clean'] == latest_v_date]
                            
                            st.info(generate_narrative(df_visits_agg, "Physician", metric_col="Total Visits", unit="Visits"))
                            c_ov1, c_ov2 = st.columns(2)
                            with c_ov1:
                                with st.container(border=True):
                                    st.markdown(f"#### 🏥 Total Office Visits ({latest_v_date.year} YTD)")
                                    fig_ov = px.bar(latest_v_df.sort_values('Total Visits', ascending=True), x='Total Visits', y='Name', orientation='h', text_auto=True, color='Total Visits', color_continuous_scale='Blues')
                                    fig_ov.update_layout(height=800)
                                    st.plotly_chart(fig_ov, use_container_width=True)
                                with st.container(border=True):
                                    st.markdown(f"#### 📉 YoY Change: Office Visits")
                                    fig_diff_ov = px.bar(latest_v_df.sort_values('Visits_Diff', ascending=True), x='Visits_Diff', y='Name', orientation='h', text_auto=True, color='Visits_Diff', color_continuous_scale='RdBu')
                                    fig_diff_ov.update_layout(height=800)
                                    st.plotly_chart(fig_diff_ov, use_container_width=True)
                            with c_ov2:
                                with st.container(border=True):
                                    st.markdown(f"#### 🆕 New Patients ({latest_v_date.year} YTD)")
                                    fig_np = px.bar(latest_v_df.sort_values('New Patients', ascending=True), x='New Patients', y='Name', orientation='h', text_auto=True, color='New Patients', color_continuous_scale='Greens')
                                    fig_np.update_layout(height=800)
                                    st.plotly_chart(fig_np, use_container_width=True)
                                with st.container(border=True):
                                    st.markdown(f"#### 📉 YoY Change: New Patients")
                                    fig_diff_np = px.bar(latest_v_df.sort_values('NP_Diff', ascending=True), x='NP_Diff', y='Name', orientation='h', text_auto=True, color='NP_Diff', color_continuous_scale='RdBu')
                                    fig_diff_np.update_layout(height=800)
                                    st.plotly_chart(fig_diff_np, use_container_width=True)

            with tab_app:
                if df_apps.empty: st.info("No APP data found.")
                else:
                    st.info(generate_narrative(df_apps, "APP"))
                    with st.container(border=True):
                        st.markdown("#### 📅 Last 12 Months Trend (RVU per FTE)")
                        fig_trend = px.line(df_apps.sort_values('Month_Clean'), x='Month_Clean', y='RVU per FTE', color='Name', markers=True)
                        st.plotly_chart(fig_trend, use_container_width=True)
                    c1, c2 = st.columns(2)
                    with c1:
                        st.markdown("#### 🔢 Monthly Data")
                        piv = df_apps.pivot_table(index="Name", columns="Month_Label", values="Total RVUs", aggfunc="sum").fillna(0)
                        piv["Total"] = piv.sum(axis=1)
                        st.dataframe(piv.sort_values("Total", ascending=False).style.format("{:,.0f}").background_gradient(cmap="Greens"))
                    with c2:
                        st.markdown("#### 📆 Quarterly Data")
                        piv_q = df_apps.pivot_table(index="Name", columns="Quarter", values="Total RVUs", aggfunc="sum").fillna(0)
                        piv_q["Total"] = piv_q.sum(axis=1)
                        st.dataframe(piv_q.sort_values("Total", ascending=False).style.format("{:,.0f}").background_gradient(cmap="Oranges"))
    else:
        st.info("👋 Ready. View Only Mode: Add files to 'Reports' folder in GitHub to update data.")
