import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime
import os

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
    
    IGNORED_SHEETS = ["PRODUCTIVITY TREND", "RAD PHYSICIAN WORK RVUS", "COVER", "SHEET1", "TOTALS", "PROTON PHYSICIAN WORK RVUS"]
    
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

    # --- HELPER: INSIGHT GENERATOR ---
    def generate_narrative(df, entity_type="Provider"):
        if df.empty: return "No data available."
        
        latest_date = df['Month_Clean'].max()
        latest_df = df[df['Month_Clean'] == latest_date]
        total_vol = latest_df['Total RVUs'].sum()
        avg_vol = latest_df['RVU per FTE'].mean()
        
        # Safe check for empty latest data
        if latest_df.empty: return "Data processed but current month is empty."
        
        top_perf = latest_df.loc[latest_df['RVU per FTE'].idxmax()]
        
        prev_date = latest_date - pd.DateOffset(months=1)
        prev_df = df[df['Month_Clean'] == prev_date]
        
        trend_text = ""
        if not prev_df.empty:
            prev_total = prev_df['Total RVUs'].sum()
            growth = ((total_vol - prev_total) / prev_total) * 100 if prev_total > 0 else 0
            direction = "increased" if growth > 0 else "decreased"
            trend_text = f"Total volume **{direction} by {abs(growth):.1f}%** compared to last month."
        
        narrative = f"""
        **🤖 Automated Analysis ({latest_date.strftime('%B %Y')}):**
        
        The {entity_type} group generated a total of **{total_vol:,.0f} wRVUs** this month. {trend_text}
        
        * **🏆 Top Performer:** **{top_perf['Name']}** led with **{top_perf['RVU per FTE']:,.0f} wRVUs/FTE**.
        * **📊 Group Average:** The average productivity was **{avg_vol:,.0f} wRVUs/FTE**.
        """
        return narrative

    # --- PARSING LOGIC ---
    def parse_sheet(df, sheet_name, entity_type, forced_fte=None):
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
                    "RVU per FTE": col_sum / fte if fte > 0 else 0
                })
        return pd.DataFrame(records)

    def process_files(file_objects):
        clinic_data = []
        provider_data = []
        debug_log = []

        for file_obj in file_objects:
            if isinstance(file_obj, LocalFile):
                filename = file_obj.name
                xls = pd.read_excel(file_obj.path, sheet_name=None, header=None)
            else:
                filename = file_obj.name.upper()
                xls = pd.read_excel(file_obj, sheet_name=None, header=None)
            
            # 1. PROTON FILE
            if "PROTON" in filename or "TOPC" in filename:
                proton_providers_temp = []
                for sheet_name, df in xls.items():
                    s_upper = sheet_name.upper()
                    if any(ignored in s_upper for ignored in IGNORED_SHEETS) or "PROTON POS" in s_upper:
                        continue
                    
                    clean_name = sheet_name.strip()
                    if clean_name.upper() == "FRIEDMEN": clean_name = "Friedman"
                    
                    res = parse_sheet(df, clean_name, 'provider')
                    if not res.empty:
                        provider_data.append(res) 
                        proton_providers_temp.append(res)
                
                if proton_providers_temp:
                    combined_proton = pd.concat(proton_providers_temp)
                    topc_grp = combined_proton.groupby('Month', as_index=False)[['Total RVUs', 'FTE']].sum()
                    topc_records = []
                    for idx, row in topc_grp.iterrows():
                         topc_records.append({
                            "Type": "clinic",
                            "ID": "TOPC",
                            "Name": "TN Proton Center",
                            "FTE": row['FTE'],
                            "Month": row['Month'],
                            "Total RVUs": row['Total RVUs'],
                            "RVU per FTE": row['Total RVUs'] / row['FTE'] if row['FTE'] > 0 else 0
                         })
                    clinic_data.append(pd.DataFrame(topc_records))

            # 2. OTHER FILES
            else:
                for sheet_name, df in xls.items():
                    clean_name = sheet_name.strip()
                    s_upper = clean_name.upper()
                    
                    if clean_name.upper() == "FRIEDMEN": 
                        clean_name = "Friedman"
                        s_upper = "FRIEDMAN"

                    is_lroc = "LROC" in filename and ("LROC" in s_upper or "POS" in s_upper)
                    is_troc = "TROC" in filename and ("TROC" in s_upper or "POS" in s_upper)
                    
                    if clean_name in CLINIC_CONFIG or is_lroc or is_troc:
                        clinic_id = clean_name
                        if is_lroc: clinic_id = "LROC"
                        if is_troc: clinic_id = "TROC"
                        res = parse_sheet(df, clinic_id, 'clinic')
                        if not res.empty: clinic_data.append(res)
                        continue

                    if any(ignored in s_upper for ignored in IGNORED_SHEETS): continue
                    if clean_name.lower().endswith(" prov"): continue

                    res = parse_sheet(df, clean_name, 'provider')
                    if not res.empty:
                        provider_data.append(res)
                        debug_log.append(f"Found provider data for {clean_name} in file {filename}")

        df_clinic = pd.concat(clinic_data, ignore_index=True) if clinic_data else pd.DataFrame()
        df_provider = pd.concat(provider_data, ignore_index=True) if provider_data else pd.DataFrame()

        # DATA CLEANING
        if not df_clinic.empty:
            df_clinic['Month_Clean'] = pd.to_datetime(df_clinic['Month'], format='%b-%y', errors='coerce')
            mask = df_clinic['Month_Clean'].isna()
            if mask.any():
                df_clinic.loc[mask, 'Month_Clean'] = pd.to_datetime(df_clinic.loc[mask, 'Month'], errors='coerce')
            df_clinic.dropna(subset=['Month_Clean'], inplace=True)
            
            df_clinic = df_clinic.groupby(['Name', 'ID', 'Month_Clean'], as_index=False).agg({
                'Total RVUs': 'sum', 'FTE': 'max', 'Month': 'first'
            })
            df_clinic['RVU per FTE'] = df_clinic.apply(lambda x: x['Total RVUs'] / x['FTE'] if x['FTE'] > 0 else 0, axis=1)
            df_clinic['Quarter'] = df_clinic['Month_Clean'].apply(lambda x: f"Q{pd.Timestamp(x).quarter} {pd.Timestamp(x).year}")
            df_clinic.sort_values('Month_Clean', inplace=True)
            df_clinic['Month_Label'] = df_clinic['Month_Clean'].dt.strftime('%b-%y')

        if not df_provider.empty:
            df_provider['Month_Clean'] = pd.to_datetime(df_provider['Month'], format='%b-%y', errors='coerce')
            mask = df_provider['Month_Clean'].isna()
            if mask.any():
                df_provider.loc[mask, 'Month_Clean'] = pd.to_datetime(df_provider.loc[mask, 'Month'], errors='coerce')
            df_provider.dropna(subset=['Month_Clean'], inplace=True)
            
            df_provider = df_provider.groupby(['Name', 'ID', 'Month_Clean'], as_index=False).agg({
                'Total RVUs': 'sum', 'FTE': 'max', 'Month': 'first'
            })
            df_provider['RVU per FTE'] = df_provider.apply(lambda x: x['Total RVUs'] / x['FTE'] if x['FTE'] > 0 else 0, axis=1)
            df_provider['Quarter'] = df_provider['Month_Clean'].apply(lambda x: f"Q{pd.Timestamp(x).quarter} {pd.Timestamp(x).year}")
            df_provider.sort_values('Month_Clean', inplace=True)
            df_provider['Month_Label'] = df_provider['Month_Clean'].dt.strftime('%b-%y')

        return df_clinic, df_provider, debug_log

    # --- UI ---
    st.set_page_config(page_title="RadOnc Analytics", layout="wide", page_icon="🩺")
    
    # 1. UPDATED TITLE WITH SUBTITLE
    st.title("🩺 Radiation Oncology Division Analytics")
    st.markdown("##### by Dr. Jones")
    st.markdown("---")

    # LOAD SERVER FILES
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

        uploaded_files = st.file_uploader("Add Temporary Files (Session Only)", type=['xlsx', 'xls'], accept_multiple_files=True)
    
    all_files = server_files + (uploaded_files if uploaded_files else [])

    if all_files:
        with st.spinner("Analyzing files..."):
            df_clinic, df_provider, debug_log = process_files(all_files)

        if df_clinic.empty and df_provider.empty:
            st.error("No valid data found.")
        else:
            if not df_provider.empty:
                df_apps = df_provider[df_provider['Name'].isin(APP_LIST)]
                df_mds = df_provider[~df_provider['Name'].isin(APP_LIST)]
            else:
                df_apps = pd.DataFrame()
                df_mds = pd.DataFrame()

            tab_c, tab_md, tab_app = st.tabs(["🏥 Clinic Analytics", "👨‍⚕️ MD Analytics", "👩‍⚕️ APP Analytics"])

            # --- 1. CLINICS (With Left Tabs) ---
            with tab_c:
                if df_clinic.empty:
                    st.info("No Clinic data found.")
                else:
                    # Create Layout: Left Nav (col_nav) and Main Content (col_main)
                    col_nav, col_main = st.columns([1, 5])
                    
                    with col_nav:
                        st.markdown("### 🔍 Filter")
                        # The "Tab on the Left" simulation
                        clinic_filter = st.radio(
                            "Select View:",
                            ["All", "LROC", "TOPC", "TROC"],
                            key="clinic_radio"
                        )

                    with col_main:
                        # APPLY FILTER LOGIC
                        if clinic_filter == "All":
                            df_view = df_clinic.copy()
                            view_title = "All Clinics"
                        elif clinic_filter == "LROC":
                            df_view = df_clinic[df_clinic['ID'] == 'LROC']
                            view_title = "LROC (LaVergne)"
                        elif clinic_filter == "TOPC":
                            df_view = df_clinic[df_clinic['ID'] == 'TOPC']
                            view_title = "TN Proton Center"
                        elif clinic_filter == "TROC":
                            df_view = df_clinic[df_clinic['ID'] == 'TROC']
                            view_title = "TROC (Franklin)"

                        if df_view.empty:
                            st.warning(f"No data available for {view_title}.")
                        else:
                            max_date = df_view['Month_Clean'].max()
                            
                            # NARRATIVE
                            st.info(generate_narrative(df_view, f"{view_title} Clinic"))
                            
                            # 1. TRENDS
                            with st.container(border=True):
                                st.markdown(f"#### 📅 {view_title}: 12-Month Trend")
                                min_date = max_date - pd.DateOffset(months=11)
                                l12m_c = df_view[df_view['Month_Clean'] >= min_date].sort_values('Month_Clean')
                                fig_trend = px.line(l12m_c, x='Month_Clean', y='Total RVUs', color='Name', markers=True)
                                fig_trend.update_layout(font=dict(size=14))
                                st.plotly_chart(fig_trend, use_container_width=True)

                            # 2. YTD
                            with st.container(border=True):
                                st.markdown(f"#### 🏆 {view_title}: YTD Total ({max_date.year})")
                                ytd_c = df_view[df_view['Month_Clean'].dt.year == max_date.year]
                                # If filtered to 1 clinic, groupby might return 1 bar, which is fine
                                ytd_sum = ytd_c.groupby('Name')[['Total RVUs']].sum().reset_index().sort_values('Total RVUs', ascending=False)
                                fig_ytd = px.bar(ytd_sum, x='Name', y='Total RVUs', color='Total RVUs', color_continuous_scale='Magma', text_auto='.2s')
                                fig_ytd.update_layout(font=dict(size=14))
                                st.plotly_chart(fig_ytd, use_container_width=True)

                            # 3. QUARTERLY
                            with st.container(border=True):
                                q_chart_df = df_view.groupby(['Name', 'Quarter'])[['Total RVUs']].sum().reset_index()
                                latest_q_label = f"Q{max_date.quarter} {max_date.year}"
                                latest_q_data = q_chart_df[q_chart_df['Quarter'] == latest_q_label]
                                total_per_clinic = latest_q_data.groupby('Name')['Total RVUs'].sum().sort_values(ascending=False).index.tolist()
                                
                                fig_q = px.bar(latest_q_data, x='Name', y='Total RVUs',
                                            title=f"Most Recent Quarter ({latest_q_label})",
                                            category_orders={"Name": total_per_clinic},
                                            text_auto='.2s', color_discrete_sequence=['#C0392B'])
                                fig_q.update_layout(font=dict(size=14))
                                st.plotly_chart(fig_q, use_container_width=True)

                            # 4. TABLES
                            c1, c2 = st.columns(2)
                            with c1:
                                with st.container(border=True):
                                    st.markdown("#### 🔢 Monthly Data")
                                    piv = df_view.pivot_table(index="Name", columns="Month_Label", values="Total RVUs", aggfunc="sum").fillna(0)
                                    piv["Total"] = piv.sum(axis=1)
                                    st.dataframe(piv.sort_values("Total", ascending=False).style.format("{:,.0f}").background_gradient(cmap="Reds"))
                            
                            with c2:
                                with st.container(border=True):
                                    st.markdown("#### 📆 Quarterly Data")
                                    piv_q = df_view.pivot_table(index="Name", columns="Quarter", values="Total RVUs", aggfunc="sum").fillna(0)
                                    piv_q["Total"] = piv_q.sum(axis=1)
                                    st.dataframe(piv_q.sort_values("Total", ascending=False).style.format("{:,.0f}").background_gradient(cmap="Oranges"))

            # --- 2. MD ANALYTICS ---
            with tab_md:
                if df_mds.empty:
                    st.info("No MD data found.")
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

                    with st.container(border=True):
                        q_chart_df = df_mds.groupby(['Name', 'Quarter'])[['Total RVUs']].sum().reset_index()
                        latest_q_label = f"Q{max_date.quarter} {max_date.year}"
                        latest_q_data = q_chart_df[q_chart_df['Quarter'] == latest_q_label]
                        total_per_prov = latest_q_data.groupby('Name')['Total RVUs'].sum().sort_values(ascending=False).index.tolist()
                        fig_q = px.bar(latest_q_data, x='Name', y='Total RVUs',
                                    title=f"Most Recent Quarter Leaders ({latest_q_label})",
                                    category_orders={"Name": total_per_prov},
                                    text_auto='.2s', color_discrete_sequence=['#2E86C1'])
                        fig_q.update_layout(font=dict(size=14))
                        st.plotly_chart(fig_q, use_container_width=True)

                    c1, c2 = st.columns(2)
                    with c1:
                        with st.container(border=True):
                            st.markdown("#### 🔢 Monthly Data")
                            piv = df_mds.pivot_table(index="Name", columns="Month_Label", values="Total RVUs", aggfunc="sum").fillna(0)
                            piv["Total"] = piv.sum(axis=1)
                            st.dataframe(piv.sort_values("Total", ascending=False).style.format("{:,.0f}").background_gradient(cmap="Blues"))
                    with c2:
                        with st.container(border=True):
                            st.markdown("#### 📆 Quarterly Data")
                            piv_q = df_mds.pivot_table(index="Name", columns="Quarter", values="Total RVUs", aggfunc="sum").fillna(0)
                            piv_q["Total"] = piv_q.sum(axis=1)
                            st.dataframe(piv_q.sort_values("Total", ascending=False).style.format("{:,.0f}").background_gradient(cmap="Purples"))

            # --- 3. APP ANALYTICS ---
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

                    with st.container(border=True):
                        st.markdown(f"#### 🏆 Year-to-Date Total RVUs ({max_date.year})")
                        ytd_df = df_apps[df_apps['Month_Clean'].dt.year == max_date.year]
                        ytd_sum = ytd_df.groupby('Name')[['Total RVUs']].sum().reset_index().sort_values('Total RVUs', ascending=False)
                        fig_ytd = px.bar(ytd_sum, x='Name', y='Total RVUs', color='Total RVUs', color_continuous_scale='Teal', text_auto='.2s')
                        fig_ytd.update_layout(font=dict(size=14))
                        st.plotly_chart(fig_ytd, use_container_width=True)

                    with st.container(border=True):
                        q_chart_df = df_apps.groupby(['Name', 'Quarter'])[['Total RVUs']].sum().reset_index()
                        latest_q_label = f"Q{max_date.quarter} {max_date.year}"
                        latest_q_data = q_chart_df[q_chart_df['Quarter'] == latest_q_label]
                        total_per_prov = latest_q_data.groupby('Name')['Total RVUs'].sum().sort_values(ascending=False).index.tolist()
                        fig_q = px.bar(latest_q_data, x='Name', y='Total RVUs',
                                    title=f"Most Recent Quarter Leaders ({latest_q_label})",
                                    category_orders={"Name": total_per_prov},
                                    text_auto='.2s', color_discrete_sequence=['#27AE60'])
                        fig_q.update_layout(font=dict(size=14))
                        st.plotly_chart(fig_q, use_container_width=True)

                    c1, c2 = st.columns(2)
                    with c1:
                        with st.container(border=True):
                            st.markdown("#### 🔢 Monthly Data")
                            piv = df_apps.pivot_table(index="Name", columns="Month_Label", values="Total RVUs", aggfunc="sum").fillna(0)
                            piv["Total"] = piv.sum(axis=1)
                            st.dataframe(piv.sort_values("Total", ascending=False).style.format("{:,.0f}").background_gradient(cmap="Greens"))
                    with c2:
                        with st.container(border=True):
                            st.markdown("#### 📆 Quarterly Data")
                            piv_q = df_apps.pivot_table(index="Name", columns="Quarter", values="Total RVUs", aggfunc="sum").fillna(0)
                            piv_q["Total"] = piv_q.sum(axis=1)
                            st.dataframe(piv_q.sort_values("Total", ascending=False).style.format("{:,.0f}").background_gradient(cmap="Oranges"))
    else:
        st.info("👋 Ready. View Only Mode: Add files to 'reports' folder in GitHub to update data.")
