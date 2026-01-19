import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime

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

    # KNOWN PROVIDERS (Updated to "Friedman")
    PROVIDER_CONFIG = {
        "Burke": 1.0, "Castle": 0.6, "Chen": 1.0, "Cohen": 1.0, "Collie": 1.0,
        "Cooper": 1.0, "Ellis": 1.0, "Escott": 1.0, "Friedman": 1.0, # Corrected Spelling
        "Gray": 1.0, "Jones": 1.0, "Lee": 1.0, "Lewis": 1.0,
        "Lipscomb": 0.6, "Lydon": 1.0, "Mayo": 1.0, "Mondschein": 1.0,
        "Nguyen": 1.0, "Osborne": 1.0, "Phillips": 1.0, "Sidrys": 1.0,
        "Sittig": 1.0, "Strickler": 1.0, "Wakefield": 1.0, "Wendt": 1.0, "Whitaker": 1.0
    }

    MARKET_AVG_INCLUSION = [
        "Castle", "Chen", "Cooper", "Friedman", "Jones", "Lee", "Nguyen", 
        "Osborne", "Phillips", "Sittig", "Strickler", "Wakefield", "Wendt"
    ]

    # DEFINING THE GROUPS
    APP_LIST = ["Burke", "Ellis", "Lewis", "Lydon"]
    
    TARGET_CATEGORIES = ["E&M OFFICE CODES", "RADIATION CODES", "SPECIAL PROCEDURES"]
    
    IGNORED_SHEETS = ["PRODUCTIVITY TREND", "RAD PHYSICIAN WORK RVUS", "COVER", "SHEET1", "TOTALS", "PROTON PHYSICIAN WORK RVUS"]

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

    def process_files(files):
        clinic_data = []
        provider_data = []
        debug_log = []

        for file in files:
            filename = file.name.upper()
            xls = pd.read_excel(file, sheet_name=None, header=None)
            
            # 1. PROTON FILE
            if "PROTON" in filename or "TOPC" in filename:
                proton_providers_temp = []
                for sheet_name, df in xls.items():
                    s_upper = sheet_name.upper()
                    if any(ignored in s_upper for ignored in IGNORED_SHEETS) or "PROTON POS" in s_upper:
                        continue
                    
                    clean_name = sheet_name.strip()
                    
                    # --- AUTO-CORRECT MISSPELLING ---
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
                    
                    # --- AUTO-CORRECT MISSPELLING ---
                    if clean_name.upper() == "FRIEDMEN": clean_name = "Friedman"
                    s_upper = clean_name.upper() # Update uppercase check too
                    
                    if clean_name in CLINIC_CONFIG or ("LROC" in s_upper and "LROC" in filename) or ("TROC" in s_upper and "TROC" in filename):
                        res = parse_sheet(df, clean_name, 'clinic')
                        if not res.empty: clinic_data.append(res)
                        continue

                    if any(ignored in s_upper for ignored in IGNORED_SHEETS):
                        continue

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
            df_clinic.sort_values('Month_Clean', inplace=True)
            df_clinic['Month_Label'] = df_clinic['Month_Clean'].dt.strftime('%b-%y')

        if not df_provider.empty:
            df_provider['Month_Clean'] = pd.to_datetime(df_provider['Month'], format='%b-%y', errors='coerce')
            mask = df_provider['Month_Clean'].isna()
            if mask.any():
                df_provider.loc[mask, 'Month_Clean'] = pd.to_datetime(df_provider.loc[mask, 'Month'], errors='coerce')
            df_provider.dropna(subset=['Month_Clean'], inplace=True)
            
            # GLOBAL AGGREGATION
            df_provider = df_provider.groupby(['Name', 'ID', 'Month_Clean'], as_index=False).agg({
                'Total RVUs': 'sum',
                'FTE': 'max', 
                'Month': 'first'
            })
            df_provider['RVU per FTE'] = df_provider.apply(lambda x: x['Total RVUs'] / x['FTE'] if x['FTE'] > 0 else 0, axis=1)
            
            # ADD QUARTER COLUMN
            df_provider['Quarter'] = df_provider['Month_Clean'].apply(lambda x: f"Q{pd.Timestamp(x).quarter} {pd.Timestamp(x).year}")
            
            df_provider.sort_values('Month_Clean', inplace=True)
            df_provider['Month_Label'] = df_provider['Month_Clean'].dt.strftime('%b-%y')

        return df_clinic, df_provider, debug_log

    # --- UI ---
    st.set_page_config(page_title="RadOnc Analytics", layout="wide", page_icon="🩺")
    st.title("🩺 Radiation Oncology Division Analytics")

    with st.sidebar:
        st.header("Data Import")
        uploaded_files = st.file_uploader("Upload Excel Reports", type=['xlsx', 'xls'], accept_multiple_files=True)

    if uploaded_files:
        with st.spinner("Analyzing files..."):
            df_clinic, df_provider, debug_log = process_files(uploaded_files)

        if df_clinic.empty and df_provider.empty:
            st.error("No valid data found.")
            with st.expander("🕵️ Debugging Details"):
                for line in debug_log:
                    st.write(line)
        else:
            # --- SPLIT DATA INTO MDs AND APPs ---
            if not df_provider.empty:
                df_apps = df_provider[df_provider['Name'].isin(APP_LIST)]
                df_mds = df_provider[~df_provider['Name'].isin(APP_LIST)]
            else:
                df_apps = pd.DataFrame()
                df_mds = pd.DataFrame()

            # --- NEW TAB STRUCTURE ---
            tab_c, tab_md, tab_app = st.tabs(["🏥 Clinic Analytics", "👨‍⚕️ MD Analytics", "👩‍⚕️ APP Analytics"])

            # 1. CLINICS
            with tab_c:
                if df_clinic.empty:
                    st.info("No Clinic data found.")
                else:
                    clinic_grp = df_clinic.groupby('Month_Clean', as_index=False)[['Total RVUs', 'FTE']].sum()
                    clinic_grp['Avg RVU/FTE'] = clinic_grp['Total RVUs'] / clinic_grp['FTE']
                    df_clinic = df_clinic.merge(clinic_grp[['Month_Clean', 'Avg RVU/FTE']], on='Month_Clean', how='left')

                    latest = df_clinic['Month_Clean'].max()
                    c1, c2 = st.columns(2)
                    latest_val = df_clinic[df_clinic['Month_Clean'] == latest]['Total RVUs'].sum()
                    c1.metric("Total Division Volume", f"{latest_val:,.0f}", f"{latest.strftime('%b %Y')}")
                    
                    st.markdown("#### 📈 Clinic Trends")
                    sel_c = st.multiselect("Select Clinics", df_clinic['Name'].unique(), default=df_clinic['Name'].unique())
                    fig2 = px.line(df_clinic[df_clinic['Name'].isin(sel_c)], x='Month_Clean', y='RVU per FTE', color='Name', markers=True)
                    st.plotly_chart(fig2, use_container_width=True)

            # 2. MD ANALYTICS
            with tab_md:
                if df_mds.empty:
                    st.info("No MD data found.")
                else:
                    st.markdown("### Physician Performance")
                    
                    max_date = df_mds['Month_Clean'].max()
                    min_date = max_date - pd.DateOffset(months=11)
                    l12m_df = df_mds[df_mds['Month_Clean'] >= min_date].sort_values('Month_Clean')
                    
                    st.markdown("#### 📅 Last 12 Months Trend (RVU per FTE)")
                    fig_trend = px.line(l12m_df, x='Month_Clean', y='RVU per FTE', color='Name', markers=True)
                    st.plotly_chart(fig_trend, use_container_width=True)

                    st.markdown(f"#### 🏆 Year-to-Date Total RVUs ({max_date.year})")
                    ytd_df = df_mds[df_mds['Month_Clean'].dt.year == max_date.year]
                    ytd_sum = ytd_df.groupby('Name')[['Total RVUs']].sum().reset_index().sort_values('Total RVUs', ascending=False)
                    fig_ytd = px.bar(ytd_sum, x='Name', y='Total RVUs', color='Total RVUs', color_continuous_scale='Viridis', text_auto='.2s')
                    st.plotly_chart(fig_ytd, use_container_width=True)

                    # MONTHLY TABLE
                    st.markdown("#### 🔢 MD Monthly Data")
                    piv = df_mds.pivot_table(index="Name", columns="Month_Label", values="Total RVUs", aggfunc="sum").fillna(0)
                    sorted_months = df_mds[['Month_Clean', 'Month_Label']].drop_duplicates().sort_values('Month_Clean')['Month_Label'].tolist()
                    existing_cols = [m for m in sorted_months if m in piv.columns]
                    piv = piv[existing_cols]
                    piv["Total"] = piv.sum(axis=1)
                    st.dataframe(piv.sort_values("Total", ascending=False).style.format("{:,.0f}").background_gradient(cmap="Blues"))

                    # QUARTERLY TABLE
                    st.markdown("#### 📆 MD Quarterly Data")
                    piv_q = df_mds.pivot_table(index="Name", columns="Quarter", values="Total RVUs", aggfunc="sum").fillna(0)
                    # Sort quarters chronologically
                    sorted_quarters = df_mds[['Month_Clean', 'Quarter']].drop_duplicates().sort_values('Month_Clean')['Quarter'].unique().tolist()
                    existing_q_cols = [q for q in sorted_quarters if q in piv_q.columns]
                    piv_q = piv_q[existing_q_cols]
                    
                    piv_q["Total"] = piv_q.sum(axis=1)
                    st.dataframe(piv_q.sort_values("Total", ascending=False).style.format("{:,.0f}").background_gradient(cmap="Purples"))

            # 3. APP ANALYTICS
            with tab_app:
                if df_apps.empty:
                    st.info("No APP data found.")
                else:
                    st.markdown("### APP Performance")
                    
                    max_date = df_apps['Month_Clean'].max()
                    min_date = max_date - pd.DateOffset(months=11)
                    l12m_df = df_apps[df_apps['Month_Clean'] >= min_date].sort_values('Month_Clean')
                    
                    st.markdown("#### 📅 Last 12 Months Trend (RVU per FTE)")
                    fig_trend = px.line(l12m_df, x='Month_Clean', y='RVU per FTE', color='Name', markers=True)
                    st.plotly_chart(fig_trend, use_container_width=True)

                    st.markdown(f"#### 🏆 Year-to-Date Total RVUs ({max_date.year})")
                    ytd_df = df_apps[df_apps['Month_Clean'].dt.year == max_date.year]
                    ytd_sum = ytd_df.groupby('Name')[['Total RVUs']].sum().reset_index().sort_values('Total RVUs', ascending=False)
                    fig_ytd = px.bar(ytd_sum, x='Name', y='Total RVUs', color='Total RVUs', color_continuous_scale='Teal', text_auto='.2s')
                    st.plotly_chart(fig_ytd, use_container_width=True)

                    # MONTHLY TABLE
                    st.markdown("#### 🔢 APP Monthly Data")
                    piv = df_apps.pivot_table(index="Name", columns="Month_Label", values="Total RVUs", aggfunc="sum").fillna(0)
                    sorted_months = df_apps[['Month_Clean', 'Month_Label']].drop_duplicates().sort_values('Month_Clean')['Month_Label'].tolist()
                    existing_cols = [m for m in sorted_months if m in piv.columns]
                    piv = piv[existing_cols]
                    piv["Total"] = piv.sum(axis=1)
                    st.dataframe(piv.sort_values("Total", ascending=False).style.format("{:,.0f}").background_gradient(cmap="Greens"))

                    # QUARTERLY TABLE
                    st.markdown("#### 📆 APP Quarterly Data")
                    piv_q = df_apps.pivot_table(index="Name", columns="Quarter", values="Total RVUs", aggfunc="sum").fillna(0)
                    sorted_quarters = df_apps[['Month_Clean', 'Quarter']].drop_duplicates().sort_values('Month_Clean')['Quarter'].unique().tolist()
                    existing_q_cols = [q for q in sorted_quarters if q in piv_q.columns]
                    piv_q = piv_q[existing_q_cols]
                    
                    piv_q["Total"] = piv_q.sum(axis=1)
                    st.dataframe(piv_q.sort_values("Total", ascending=False).style.format("{:,.0f}").background_gradient(cmap="Oranges"))

    else:
        st.info("👋 Ready. Upload files containing 'Physicians', 'POS', 'PROTON', 'LROC', or 'TROC'.")
