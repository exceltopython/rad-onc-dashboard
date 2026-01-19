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

    # KNOWN PROVIDERS (Used for specific FTEs)
    PROVIDER_CONFIG = {
        "Burke": 1.0, "Castle": 0.6, "Chen": 1.0, "Cohen": 1.0, "Collie": 1.0,
        "Cooper": 1.0, "Ellis": 1.0, "Escott": 1.0, "Friedmen": 1.0,
        "Gray": 1.0, "Jones": 1.0, "Lee": 1.0, "Lewis": 1.0,
        "Lipscomb": 0.6, "Lydon": 1.0, "Mayo": 1.0, "Mondschein": 1.0,
        "Nguyen": 1.0, "Osborne": 1.0, "Phillips": 1.0, "Sidrys": 1.0,
        "Sittig": 1.0, "Strickler": 1.0, "Wakefield": 1.0, "Wendt": 1.0, "Whitaker": 1.0
    }

    MARKET_AVG_INCLUSION = [
        "Castle", "Chen", "Cooper", "Friedmen", "Jones", "Lee", "Nguyen", 
        "Osborne", "Phillips", "Sittig", "Strickler", "Wakefield", "Wendt"
    ]

    PROVIDER_GROUPS = {
        "Photon Sites": ["Castle", "Chen", "Cooper", "Friedmen", "Jones", "Lee", "Nguyen", "Osborne", "Phillips", "Sittig", "Strickler", "Wakefield", "Wendt"],
        "APPs": ["Burke", "Ellis", "Lewis", "Lydon"],
        "Proton Center": ["Escott", "Gray", "Mondschein"]
    }

    TARGET_CATEGORIES = ["E&M OFFICE CODES", "RADIATION CODES", "SPECIAL PROCEDURES"]
    
    # IGNORE THESE SHEETS IN AUTO-DETECT MODE
    IGNORED_SHEETS = ["PRODUCTIVITY TREND", "RAD PHYSICIAN WORK RVUS", "COVER", "SHEET1", "TOTALS", "PROTON PHYSICIAN WORK RVUS"]

    # --- HELPER: ROBUST MONTH FINDER ---
    def find_date_row(df):
        months = ["JAN", "FEB", "MAR", "APR", "MAY", "JUN", "JUL", "AUG", "SEP", "OCT", "NOV", "DEC"]
        best_row = 1 # Default to Row 2
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
                proton_providers = []
                for sheet_name, df in xls.items():
                    s_upper = sheet_name.upper()
                    if any(ignored in s_upper for ignored in IGNORED_SHEETS) or "PROTON POS" in s_upper:
                        continue
                    
                    clean_name = sheet_name.strip()
                    res = parse_sheet(df, clean_name, 'provider')
                    if not res.empty:
                        provider_data.append(res)
                        proton_providers.append(res)
                
                if proton_providers:
                    combined_proton = pd.concat(proton_providers)
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

            # 2. PHYSICIAN FILE
            elif "PHYSICIAN" in filename:
                for sheet_name, df in xls.items():
                    clean_name = sheet_name.strip()
                    s_upper = clean_name.upper()
                    
                    is_summary = any(ignored in s_upper for ignored in IGNORED_SHEETS)
                    if is_summary:
                         debug_log.append(f"Skipped summary sheet: {clean_name}")
                         continue

                    # Assume it is a provider
                    res = parse_sheet(df, clean_name, 'provider')
                    if not res.empty: 
                        provider_data.append(res)
                    else:
                        debug_log.append(f"Sheet '{clean_name}' processed but no data found.")

            # 3. CLINIC/POS FILE
            elif "POS" in filename or "LROC" in filename or "TROC" in filename:
                for sheet_name, df in xls.items():
                    clean_name = sheet_name.strip()
                    if clean_name in CLINIC_CONFIG:
                        res = parse_sheet(df, clean_name, 'clinic')
                        if not res.empty: clinic_data.append(res)
                    elif "LROC" in filename and "LROC" in clean_name.upper():
                         res = parse_sheet(df, "LROC", 'clinic')
                         if not res.empty: clinic_data.append(res)
                    elif "TROC" in filename and "TROC" in clean_name.upper():
                         res = parse_sheet(df, "TROC", 'clinic')
                         if not res.empty: clinic_data.append(res)
            
            else:
                 debug_log.append(f"File '{filename}' did not match recognized patterns.")

        df_clinic = pd.concat(clinic_data, ignore_index=True) if clinic_data else pd.DataFrame()
        df_provider = pd.concat(provider_data, ignore_index=True) if provider_data else pd.DataFrame()

        # Date Cleaning - NEW LOGIC TO FORCE 'Jan-25' RECOGNITION
        for d in [df_clinic, df_provider]:
            if not d.empty:
                # Attempt 1: Strict format for "Jan-25" type strings
                d['Month_Clean'] = pd.to_datetime(d['Month'], format='%b-%y', errors='coerce')
                
                # Attempt 2: If strict failed (NaT), try general parser
                mask = d['Month_Clean'].isna()
                if mask.any():
                    d.loc[mask, 'Month_Clean'] = pd.to_datetime(d.loc[mask, 'Month'], errors='coerce')

                # Check for failure
                if d['Month_Clean'].isna().all():
                    debug_log.append("CRITICAL: Date conversion failed. The dates might be in an unusual format.")
                
                d.dropna(subset=['Month_Clean'], inplace=True)
                d.sort_values('Month_Clean', inplace=True)
                d['Month_Label'] = d['Month_Clean'].dt.strftime('%b-%y')

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
            with st.expander("🕵️ Debugging Details (Why was my file rejected?)"):
                for line in debug_log:
                    st.write(line)
        else:
            tab_c, tab_p = st.tabs(["🏥 Clinic Analytics", "👨‍⚕️ Provider Analytics"])

            # CLINICS
            with tab_c:
                if df_clinic.empty:
                    st.info("No Clinic (POS) data found.")
                else:
                    clinic_grp = df_clinic.groupby('Month_Clean', as_index=False)[['Total RVUs', 'FTE']].sum()
                    clinic_grp['Avg RVU/FTE'] = clinic_grp['Total RVUs'] / clinic_grp['FTE']
                    df_clinic = df_clinic.merge(clinic_grp[['Month_Clean', 'Avg RVU/FTE']], on='Month_Clean', how='left')

                    latest = df_clinic['Month_Clean'].max()
                    latest_c = df_clinic[df_clinic['Month_Clean'] == latest]
                    
                    c1, c2, c3 = st.columns(3)
                    c1.metric("Division Total RVUs", f"{latest_c['Total RVUs'].sum():,.0f}", f"{latest.strftime('%b %Y')}")
                    
                    mkt = clinic_grp[clinic_grp['Month_Clean']==latest]['Avg RVU/FTE'].values
                    c2.metric("Market Avg RVU/FTE", f"{mkt[0]:,.0f}" if len(mkt)>0 else "N/A")
                    
                    if not latest_c.empty:
                        top = latest_c.loc[latest_c['RVU per FTE'].idxmax()]
                        c3.metric("Top Clinic", top['Name'], f"{top['RVU per FTE']:,.0f}")

                    st.markdown("#### 📊 Clinic Matrix")
                    fig = px.scatter(latest_c, x="FTE", y="Total RVUs", size="RVU per FTE", color="Name", text="Name", title=f"Volume vs Staffing ({latest.strftime('%b %Y')})")
                    st.plotly_chart(fig, use_container_width=True)

                    st.markdown("#### 📈 Trends")
                    sel_c = st.multiselect("Select Clinics", df_clinic['Name'].unique(), default=df_clinic['Name'].unique())
                    fig2 = px.line(df_clinic[df_clinic['Name'].isin(sel_c)], x='Month_Clean', y='RVU per FTE', color='Name', markers=True)
                    st.plotly_chart(fig2, use_container_width=True)

            # PROVIDERS
            with tab_p:
                if df_provider.empty:
                    st.info("No Physician data found.")
                else:
                    df_incl = df_provider[df_provider['ID'].isin(MARKET_AVG_INCLUSION)]
                    prov_grp = df_incl.groupby('Month_Clean', as_index=False)[['Total RVUs', 'FTE']].sum()
                    prov_grp['Avg RVU/FTE'] = prov_grp['Total RVUs'] / prov_grp['FTE']
                    df_provider = df_provider.merge(prov_grp[['Month_Clean', 'Avg RVU/FTE']], on='Month_Clean', how='left')

                    st.sidebar.markdown("### 🔮 Scenario Planner")
                    scen_p = st.sidebar.selectbox("Select Provider", df_provider['Name'].unique())
                    curr_fte = PROVIDER_CONFIG.get(scen_p, 1.0)
                    new_fte = st.sidebar.slider(f"Adjust {scen_p} FTE", 0.1, 2.0, float(curr_fte), 0.1)
                    
                    scen_df = df_provider.copy()
                    scen_df.loc[scen_df['Name'] == scen_p, 'RVU per FTE'] = scen_df.loc[scen_df['Name'] == scen_p, 'Total RVUs'] / new_fte

                    st.markdown("#### 👥 Group Analysis")
                    grp = st.selectbox("Select Group", ["All Providers", "Photon Sites", "APPs", "Proton Center"])
                    if grp == "Photon Sites": sub = scen_df[scen_df['ID'].isin(PROVIDER_GROUPS["Photon Sites"])]
                    elif grp == "APPs": sub = scen_df[scen_df['ID'].isin(PROVIDER_GROUPS["APPs"])]
                    elif grp == "Proton Center": sub = scen_df[scen_df['ID'].isin(PROVIDER_GROUPS["Proton Center"])]
                    else: sub = scen_df

                    if not sub.empty:
                        latest_p = sub['Month_Clean'].max()
                        latest_p_dat = sub[sub['Month_Clean'] == latest_p].sort_values("RVU per FTE", ascending=False)
                        
                        fig3 = px.bar(latest_p_dat, x='Name', y='RVU per FTE', color='RVU per FTE', title="Latest Month RVU/FTE", color_continuous_scale='Viridis')
                        st.plotly_chart(fig3, use_container_width=True)

                        st.markdown("#### 📅 Quarterly Table")
                        piv = sub.pivot_table(index="Name", columns="Month_Label", values="Total RVUs", aggfunc="sum").fillna(0)
                        piv["Total"] = piv.sum(axis=1)
                        # Requires matplotlib in requirements.txt
                        st.dataframe(piv.sort_values("Total", ascending=False).style.format("{:,.0f}").background_gradient(cmap="Blues"))
    else:
        st.info("👋 Ready. Upload files containing 'Physicians', 'POS', 'PROTON', 'LROC', or 'TROC'.")
