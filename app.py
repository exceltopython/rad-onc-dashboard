import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime
import os
import re

# --- PASSWORD CONFIGURATION ---
APP_PASSWORD = "RadOnc2026"

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
        st.text_input("❌ Password incorrect. Try again:", type="password", on_change=password_entered, key="password")
        return False
    else:
        return True

if check_password():
    # --- CONFIGURATION ---
    CLINIC_CONFIG = {
        "CENT": {"name": "Centennial", "fte": 2.0},
        "Dickson": {"name": "Horizon", "fte": 1.0},
        "LROC": {"name": "LROC", "fte": 1.0},
        "Skyline": {"name": "Skyline", "fte": 1.0},
        "Midtown": {"name": "ST Midtown", "fte": 1.6},
        "MURF": {"name": "ST Rutherford", "fte": 3.0},
        "STW": {"name": "ST West", "fte": 2.0},
        "Stonecrest": {"name": "StoneCrest", "fte": 1.0},
        "Summit": {"name": "Summit", "fte": 1.0},
        "Sumner": {"name": "Sumner", "fte": 1.5},
        "TROC": {"name": "TROC", "fte": 0.6},
        "TOPC": {"name": "TN Proton Center", "fte": 0.0}
    }

    PROVIDER_CONFIG = {
        "Burke": 1.0, "Castle": 0.6, "Chen": 1.0, "Cohen": 1.0, "Collie": 1.0,
        "Cooper": 1.0, "Ellis": 1.0, "Escott": 1.0, "Friedman": 1.0, 
        "Gray": 1.0, "Jones": 1.0, "Lee": 1.0, "Lewis": 1.0,
        "Lipscomb": 0.6, "Lydon": 1.0, "Mayo": 1.0, "Mondschein": 1.0,
        "Nguyen": 1.0, "Osborne": 1.0, "Phillips": 1.0, "Sidrys": 1.0,
        "Sittig": 1.0, "Strickler": 1.0, "Wakefield": 1.0, "Wendt": 1.0, "Whitaker": 1.0
    }

    APP_LIST = ["Burke", "Ellis", "Lewis", "Lydon"]
    
    TARGET_CATEGORIES = ["E&M OFFICE CODES", "RADIATION CODES", "SPECIAL PROCEDURES"]
    IGNORED_SHEETS = ["RAD PHYSICIAN WORK RVUS", "COVER", "SHEET1", "TOTALS", "PROTON PHYSICIAN WORK RVUS"]
    SERVER_DIR = "Reports"

    # --- HELPER CLASSES ---
    class LocalFile:
        def __init__(self, path):
            self.path = path
            self.name = os.path.basename(path).upper()
        
    # --- HELPER: ROBUST MONTH FINDER ---
    def find_date_row(df):
        months = ["JAN", "FEB", "MAR", "APR", "MAY", "JUN", "JUL", "AUG", "SEP", "OCT", "NOV", "DEC"]
        best_row = 1 
        max_score = 0
        for r in range(min(10, len(df))):
            row_vals = df.iloc[r, 4:16]
            str_vals = [str(v).upper() for v in row_vals if pd.notna(v)]
            text_matches = sum(1 for v in str_vals if any(m in v for m in months))
            dt_matches = sum(1 for v in row_vals if isinstance(v, (datetime, pd.Timestamp)))
            total_score = text_matches + (dt_matches * 2) 
            if total_score > max_score:
                max_score = total_score
                best_row = r
        return best_row

    # --- HELPER: DATE FROM FILENAME ---
    def get_date_from_filename(filename):
        match = re.search(r'(JAN|FEB|MAR|APR|MAY|JUN|JUL|AUG|SEP|OCT|NOV|DEC)\s*(\d{2,4})', filename, re.IGNORECASE)
        if match:
            month_str = match.group(1)
            year_str = match.group(2)
            if len(year_str) == 2: year_str = "20" + year_str
            return pd.to_datetime(f"{month_str} {year_str}")
        return datetime.now()

    # --- HELPER: CLEAN NAMES ---
    def clean_provider_name(name_str):
        if not isinstance(name_str, str): return str(name_str)
        # CRASH FIX: Return empty if string is empty or whitespace
        if not name_str.strip(): return ""
        
        if "," in name_str:
            return name_str.split(",")[0].strip()
        
        # CRASH FIX: Safety check before splitting by space
        parts = name_str.split()
        if not parts: return ""
        return parts[0].strip()

    # --- HELPER: INSIGHT GENERATOR ---
    def generate_narrative(df, entity_type="Provider", metric_col="Total RVUs", unit="wRVUs"):
        if df.empty: return "No data available."
        
        latest_date = df['Month_Clean'].max()
        latest_df = df[df['Month_Clean'] == latest_date]
        
        if latest_df.empty: return "Data processed but current month is empty."
        
        total_vol = latest_df[metric_col].sum()
        
        if metric_col == "Total RVUs":
            top_perf = latest_df.loc[latest_df['RVU per FTE'].idxmax()]
            top_val = top_perf['RVU per FTE']
            top_metric = "wRVUs/FTE"
        else:
            top_perf = latest_df.loc[latest_df[metric_col].idxmax()]
            top_val = top_perf[metric_col]
            top_metric = unit

        prev_date = latest_date - pd.DateOffset(months=1)
        prev_df = df[df['Month_Clean'] == prev_date]
        
        trend_text = ""
        if not prev_df.empty:
            prev_total = prev_df[metric_col].sum()
            growth = ((total_vol - prev_total) / prev_total) * 100 if prev_total > 0 else 0
            direction = "increased" if growth > 0 else "decreased"
            trend_text = f"Total volume **{direction} by {abs(growth):.1f}%** compared to last month."
        
        narrative = f"""
        **🤖 Automated Analysis ({latest_date.strftime('%B %Y')}):**
        
        The {entity_type} group generated a total of **{total_vol:,.0f} {unit}** this month. {trend_text}
        
        * **🏆 Top Performer:** **{clean_provider_name(top_perf['Name'])}** led with **{top_val:,.0f} {top_metric}**.
        """
        return narrative

    # --- PARSING LOGIC ---
    def parse_rvu_sheet(df, sheet_name, entity_type, clinic_tag="General", forced_fte=None):
        if entity_type == 'clinic':
            config = CLINIC_CONFIG.get(sheet_name, {"name": sheet_name, "fte": 1.0})
            name = config['name']
            fte = config['fte']
        else:
            name = sheet_name 
            fte = forced_fte if forced_fte else PROVIDER_CONFIG.get(sheet_name, 1.0)
        
        df.iloc[:, 0] = df.iloc[:, 0].astype(str).str.strip().str.upper()
        mask = df.iloc[:, 0].isin(TARGET_CATEGORIES)
        filtered_df = df[mask]
        data_rows = filtered_df.copy()
        
        records = []
        header_row_idx = find_date_row(df)
        
        if len(df.columns) > 4:
            for col in df.columns[4:]:
                header_val = df.iloc[header_row_idx, col]
                if pd.isna(header_val): continue
                col_sum = pd.to_numeric(data_rows[col], errors='coerce').sum()
                records.append({
                    "Type": entity_type,
                    "ID": sheet_name,
                    "Name": name,
                    "FTE": fte,
                    "Month": header_val,
                    "Total RVUs": col_sum,
                    "RVU per FTE": col_sum / fte if fte > 0 else 0,
                    "Clinic_Tag": clinic_tag
                })
        return pd.DataFrame(records)

    def parse_visits_sheet(df, filename_date):
        records = []
        
        year_target = str(filename_date.year) 
        ov_col_idx = None
        np_col_idx = None
        data_start_row = -1
        
        # 1. Header Scan
        for i in range(min(15, len(df))):
            row_vals = [str(v).strip() for v in df.iloc[i].values]
            
            # Identify columns matching Target Year
            year_indices = [idx for idx, val in enumerate(row_vals) if year_target in val]
            
            if len(year_indices) >= 1:
                ov_col_idx = year_indices[0] # First occurrence = Office Visits
                if len(year_indices) >= 2:
                    np_col_idx = year_indices[1] # Second occurrence = New Patients
                
                data_start_row = i + 1 
                break

        # Fallback if dynamic search fails
        if ov_col_idx is None: ov_col_idx = 3 # Col D
        if np_col_idx is None: np_col_idx = 10 # Col K
        
        # 2. Row Scan
        scan_start = 0 if data_start_row == -1 else data_start_row
        
        for i in range(scan_start, len(df)):
            row = df.iloc[i]
            if len(row) <= max(ov_col_idx, np_col_idx): continue
            
            # Name is Column B (index 1)
            prov_name_raw = str(row[1]).strip()
            
            # CRASH FIX: Explicit check for empty strings
            if not prov_name_raw or prov_name_raw.lower() in ['nan', 'physician', 'amount', 'none']: 
                continue
                
            if "Total" in prov_name_raw: 
                break 
                
            clean_name = clean_provider_name(prov_name_raw)
            if not clean_name or clean_name not in PROVIDER_CONFIG: continue

            try:
                ov_val = pd.to_numeric(row[ov_col_idx], errors='coerce')
                visits = ov_val if pd.notna(ov_val) else 0
                
                np_val = pd.to_numeric(row[np_col_idx], errors='coerce')
                new_patients = np_val if pd.notna(np_val) else 0
            except:
                visits = 0
                new_patients = 0

            records.append({
                "Name": clean_name,
                "Month_Clean": filename_date,
                "Total Visits": visits,
                "New Patients": new_patients,
                "Quarter": f"Q{filename_date.quarter} {filename_date.year}",
                "Month_Label": filename_date.strftime('%b-%y')
            })
            
        return pd.DataFrame(records)

    def process_files(file_objects):
        clinic_data = []
        provider_data = []
        visit_data = []
        debug_log = []

        for file_obj in file_objects:
            if isinstance(file_obj, LocalFile):
                filename = file_obj.name
                xls = pd.read_excel(file_obj.path, sheet_name=None, header=None)
            else:
                filename = file_obj.name.upper()
                xls = pd.read_excel(file_obj, sheet_name=None, header=None)
            
            file_tag = "General"
            if "LROC" in filename: file_tag = "LROC"
            elif "TROC" in filename: file_tag = "TROC"
            elif "PROTON" in filename or "TOPC" in filename: file_tag = "TOPC"

            # --- VISIT DATA DETECTION ---
            if "NEW PATIENTS" in filename or "NEW PT" in filename:
                file_date = get_date_from_filename(filename)
                found_sheet = False
                for sheet_name, df in xls.items():
                    if "PHYS YTD OV" in sheet_name.upper():
                        res = parse_visits_sheet(df, file_date)
                        if not res.empty: 
                            visit_data.append(res)
                            found_sheet = True
                if not found_sheet:
                    debug_log.append(f"Found 'New Patients' file {filename} but could not find/parse 'PHYS YTD OV' sheet.")
                continue 

            # --- STANDARD RVU PROCESSING ---
            if file_tag == "TOPC":
                proton_providers_temp = []
                for sheet_name, df in xls.items():
                    s_upper = sheet_name.upper()
                    if any(ignored in s_upper for ignored in IGNORED_SHEETS) or "PROTON POS" in s_upper: continue
                    if "PRODUCTIVITY TREND" in s_upper: continue 
                    clean_name = sheet_name.strip()
                    if clean_name.upper() == "FRIEDMEN": clean_name = "Friedman"
                    res = parse_rvu_sheet(df, clean_name, 'provider', clinic_tag="TOPC")
                    if not res.empty:
                        provider_data.append(res) 
                        proton_providers_temp.append(res)
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
                            "Clinic_Tag": "TOPC"
                         })
                    clinic_data.append(pd.DataFrame(topc_records))
            else:
                for sheet_name, df in xls.items():
                    clean_name = sheet_name.strip()
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
            df_provider_raw['Month_Clean'] = pd.to_datetime(df_provider_raw['Month'], format='%b-%y', errors='coerce')
            mask = df_provider_raw['Month_Clean'].isna()
            if mask.any(): df_provider_raw.loc[mask, 'Month_Clean'] = pd.to_datetime(df_provider_raw.loc[mask, 'Month'], errors='coerce')
            df_provider_raw.dropna(subset=['Month_Clean'], inplace=True)
            df_provider_raw['Month_Label'] = df_provider_raw['Month_Clean'].dt.strftime('%b-%y')
            df_provider_raw['Quarter'] = df_provider_raw['Month_Clean'].apply(lambda x: f"Q{pd.Timestamp(x).quarter} {pd.Timestamp(x).year}")
            
            df_provider_global = df_provider_raw.groupby(['Name', 'ID', 'Month_Clean'], as_index=False).agg({
                'Total RVUs': 'sum', 'FTE': 'max', 'Month': 'first', 'Quarter': 'first', 'Month_Label': 'first'
            })
            df_provider_global['RVU per FTE'] = df_provider_global.apply(lambda x: x['Total RVUs'] / x['FTE'] if x['FTE'] > 0 else 0, axis=1)
            df_provider_global.sort_values('Month_Clean', inplace=True)

        return df_clinic, df_provider_global, df_provider_raw, df_visits, debug_log

    # --- UI ---
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
        if server_files:
            st.success(f"✅ Loaded {len(server_files)} master files from server.")
        else:
            st.info("ℹ️ No master files found on server.")
        uploaded_files = st.file_uploader("Add Temporary Files", type=['xlsx', 'xls'], accept_multiple_files=True)
    
    all_files = server_files + (uploaded_files if uploaded_files else [])

    if all_files:
        with st.spinner("Analyzing files..."):
            df_clinic, df_md_global, df_provider_raw, df_visits, debug_log = process_files(all_files)

        if df_clinic.empty and df_md_global.empty and df_visits.empty:
            st.error("No valid data found.")
            if debug_log:
                with st.expander("Debug Log"):
                    for msg in debug_log: st.write(msg)
        else:
            if not df_md_global.empty:
                df_apps = df_md_global[df_md_global['Name'].isin(APP_LIST)]
                df_mds = df_md_global[~df_md_global['Name'].isin(APP_LIST)]
            else:
                df_apps = pd.DataFrame()
                df_mds = pd.DataFrame()

            tab_c, tab_md, tab_app = st.tabs(["🏥 Clinic Analytics", "👨‍⚕️ MD Analytics", "👩‍⚕️ APP Analytics"])

            with tab_c:
                if df_clinic.empty:
                    st.info("No Clinic data found.")
                else:
                    col_nav, col_main = st.columns([1, 5])
                    with col_nav:
                        st.markdown("### 🔍 Filter")
                        clinic_filter = st.radio("Select View:", ["All", "LROC", "TOPC", "TROC"], key="clinic_radio")
                    with col_main:
                        if clinic_filter == "All":
                            df_view = df_clinic.copy()
                            view_title = "All Clinics"
                            target_tag = None
                        else:
                            df_view = df_clinic[df_clinic['ID'] == clinic_filter]
                            target_tag = clinic_filter
                            if clinic_filter == "LROC": view_title = "LROC (LaVergne)"
                            elif clinic_filter == "TOPC": view_title = "TN Proton Center"
                            elif clinic_filter == "TROC": view_title = "TROC (Franklin)"

                        if df_view.empty:
                            st.warning(f"No data available for {view_title}.")
                        else:
                            max_date = df_view['Month_Clean'].max()
                            st.info(generate_narrative(df_view, f"{view_title} Clinic"))
                            
                            with st.container(border=True):
                                st.markdown(f"#### 📅 {view_title}: 12-Month Trend")
                                min_date = max_date - pd.DateOffset(months=11)
                                l12m_c = df_view[df_view['Month_Clean'] >= min_date].sort_values('Month_Clean')
                                fig_trend = px.line(l12m_c, x='Month_Clean', y='Total RVUs', color='Name', markers=True)
                                fig_trend.update_layout(font=dict(size=14))
                                fig_trend.update_yaxes(rangemode="tozero")
                                st.plotly_chart(fig_trend, use_container_width=True)

                            if target_tag and not df_provider_raw.empty:
                                clinic_prov_df = df_provider_raw[df_provider_raw['Clinic_Tag'] == target_tag]
                                if not clinic_prov_df.empty:
                                    min_pie_date = max_date - pd.DateOffset(months=11)
                                    pie_df = clinic_prov_df[clinic_prov_df['Month_Clean'] >= min_pie_date]
                                    pie_agg = pie_df.groupby('Name')[['Total RVUs']].sum().reset_index()
                                    if not pie_agg.empty:
                                        with st.container(border=True):
                                            st.markdown(f"#### 🍰 Work Breakdown: Who performed the work? (Last 12 Months)")
                                            fig_pie = px.pie(pie_agg, values='Total RVUs', names='Name', hole=0.4)
                                            fig_pie.update_traces(textposition='inside', textinfo='percent+label')
                                            fig_pie.update_layout(font=dict(size=14))
                                            st.plotly_chart(fig_pie, use_container_width=True)

            with tab_md:
                col_nav_md, col_main_md = st.columns([1, 5])
                with col_nav_md:
                    st.markdown("### 📊 Metric")
                    md_view = st.radio("Select View:", ["wRVU Productivity", "Office Visits"], key="md_radio")
                
                with col_main_md:
                    if md_view == "wRVU Productivity":
                        if df_mds.empty: st.info("No wRVU data found.")
                        else:
                            max_date = df_mds['Month_Clean'].max()
                            st.info(generate_narrative(df_mds, "Physician"))
                            with st.container(border=True):
                                st.markdown("#### 📅 Last 12 Months Trend (RVU per FTE)")
                                min_date = max_date - pd.DateOffset(months=11)
                                l12m_df = df_mds[df_mds['Month_Clean'] >= min_date].sort_values('Month_Clean')
                                fig_trend = px.line(l12m_df, x='Month_Clean', y='RVU per FTE', color='Name', markers=True)
                                fig_trend.update_layout(font=dict(size=14))
                                st.plotly_chart(fig_trend, use_container_width=True)
                            with st.container(border=True):
                                st.markdown(f"#### 🏆 Year-to-Date Total RVUs ({max_date.year})")
                                ytd_df = df_mds[df_mds['Month_Clean'].dt.year == max_date.year]
                                ytd_sum = ytd_df.groupby('Name')[['Total RVUs']].sum().reset_index().sort_values('Total RVUs', ascending=False)
                                fig_ytd = px.bar(ytd_sum, x='Name', y='Total RVUs', color='Total RVUs', color_continuous_scale='Viridis', text_auto='.2s')
                                fig_ytd.update_layout(font=dict(size=14))
                                st.plotly_chart(fig_ytd, use_container_width=True)
                    
                    elif md_view == "Office Visits":
                        if df_visits.empty:
                            st.warning("No Office Visit data found. Please upload a file containing 'New Patients' in the filename.")
                            if debug_log:
                                with st.expander("Troubleshooting"):
                                    for l in debug_log: st.write(l)
                        else:
                            latest_v_date = df_visits['Month_Clean'].max()
                            latest_v_df = df_visits[df_visits['Month_Clean'] == latest_v_date]
                            st.info(generate_narrative(df_visits, "Physician", metric_col="Total Visits", unit="Visits"))
                            c_ov1, c_ov2 = st.columns(2)
                            with c_ov1:
                                with st.container(border=True):
                                    st.markdown(f"#### 🏥 Total Office Visits ({latest_v_date.year} YTD)")
                                    fig_ov = px.bar(latest_v_df.sort_values('Total Visits', ascending=True), 
                                                    x='Total Visits', y='Name', orientation='h', text_auto=True,
                                                    color='Total Visits', color_continuous_scale='Blues')
                                    fig_ov.update_layout(font=dict(size=14))
                                    st.plotly_chart(fig_ov, use_container_width=True)
                            with c_ov2:
                                with st.container(border=True):
                                    st.markdown(f"#### 🆕 New Patients ({latest_v_date.year} YTD)")
                                    fig_np = px.bar(latest_v_df.sort_values('New Patients', ascending=True), 
                                                    x='New Patients', y='Name', orientation='h', text_auto=True,
                                                    color='New Patients', color_continuous_scale='Greens')
                                    fig_np.update_layout(font=dict(size=14))
                                    st.plotly_chart(fig_np, use_container_width=True)

            with tab_app:
                if df_apps.empty:
                    st.info("No APP data found.")
                else:
                    max_date = df_apps['Month_Clean'].max()
                    st.info(generate_narrative(df_apps, "APP"))
                    with st.container(border=True):
                        st.markdown("#### 📅 Last 12 Months Trend (RVU per FTE)")
                        min_date = max_date - pd.DateOffset(months=11)
                        l12m_df = df_apps[df_apps['Month_Clean'] >= min_date].sort_values('Month_Clean')
                        fig_trend = px.line(l12m_df, x='Month_Clean', y='RVU per FTE', color='Name', markers=True)
                        fig_trend.update_layout(font=dict(size=14))
                        st.plotly_chart(fig_trend, use_container_width=True)
    else:
        st.info("👋 Ready. View Only Mode: Add files to 'Reports' folder in GitHub to update data.")
