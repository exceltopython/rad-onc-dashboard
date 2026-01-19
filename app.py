import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime

# --- PASSWORD CONFIGURATION ---
APP_PASSWORD = "RadOnc2026"

def check_password():
    """Returns `True` if the user had the correct password."""
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
        "Burke": 1.0, "Chen": 1.0, "Cohen": 1.0, "Collie": 1.0,
        "Cooper": 1.0, "Ellis": 1.0, "Escott": 1.0, "Friedmen": 1.0,
        "Gray": 1.0, "Jones": 1.0, "Lee": 1.0, "Lewis": 1.0,
        "Lipscomb": 0.6, "Lydon": 1.0, "Mayo": 1.0, "Mondschein": 1.0,
        "Nguyen": 1.0, "Osborne": 1.0, "Phillips": 1.0, "Sidrys": 1.0,
        "Sittig": 1.0, "Strickler": 1.0, "Wakefield": 1.0, "Wendt": 1.0, "Whitaker": 1.0
    }

    MARKET_AVG_INCLUSION = [
        "Chen", "Cooper", "Friedmen", "Jones", "Lee", "Nguyen", 
        "Osborne", "Phillips", "Sittig", "Strickler", "Wakefield", "Wendt"
    ]

    PROVIDER_GROUPS = {
        "Photon Sites": ["Chen", "Cooper", "Friedmen", "Jones", "Lee", "Nguyen", "Osborne", "Phillips", "Sittig", "Strickler", "Wakefield", "Wendt"],
        "APPs": ["Burke", "Ellis", "Lewis", "Lydon"],
        "Proton Center": ["Escott", "Gray", "Mondschein"]
    }

    TARGET_CATEGORIES = ["E&M OFFICE CODES", "RADIATION CODES", "SPECIAL PROCEDURES"]

    # --- HELPER: SMART HEADER DETECTION ---
    def find_date_row(df):
        """
        Scans the first 8 rows to find the one that contains date-like values.
        Returns the index of the row that looks most like a header.
        """
        best_row = 1 # Default to row 2 (index 1)
        max_valid_dates = 0
        
        # Scan first 8 rows
        for r in range(min(8, len(df))):
            try:
                # Look at columns E through P (indices 4 to 15)
                row_slice = df.iloc[r, 4:16]
                # Try converting to datetime
                valid_count = pd.to_datetime(row_slice, errors='coerce').notna().sum()
                
                # If this row has more dates than previous best, keep it
                if valid_count > max_valid_dates:
                    max_valid_dates = valid_count
                    best_row = r
            except Exception:
                continue
        
        return best_row

    # --- PROCESSING LOGIC ---
    def parse_sheet(df, sheet_name, entity_type, forced_fte=None):
        if entity_type == 'clinic':
            config = CLINIC_CONFIG.get(sheet_name, {"name": sheet_name, "fte": 1.0})
            name = config['name']
            fte = config['fte']
        else:
            name = sheet_name 
            fte = forced_fte if forced_fte else PROVIDER_CONFIG.get(sheet_name, 1.0)
        
        # Data Cleaning: Convert Col A to string for matching
        df.iloc[:, 0] = df.iloc[:, 0].astype(str).str.strip().str.upper()
        
        # Filter for the target rows (E&M, Radiation, etc)
        mask = df.iloc[:, 0].isin(TARGET_CATEGORIES)
        filtered_df = df[mask]
        data_rows = filtered_df.copy()
        
        records = []
        
        # FIND THE DATE HEADER ROW DYNAMICALLY
        header_row_idx = find_date_row(df)
        
        # Loop through columns starting at E (index 4)
        if len(df.columns) > 4:
            for col in df.columns[4:]: 
                # Grab the date from the detected header row
                header_val = df.iloc[header_row_idx, col] 
                
                # If header is empty/invalid, skip column
                if pd.isna(header_val): continue
                
                # Sum the data rows for this column
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

        for file in files:
            filename = file.name.upper()
            xls = pd.read_excel(file, sheet_name=None, header=None)
            
            # --- SCENARIO 1: PROTON (TOPC) FILE ---
            if "PROTON" in filename or "TOPC" in filename:
                proton_providers = []
                for sheet_name, df in xls.items():
                    # Skip summary tabs
                    if "PRODUCTIVITY" in sheet_name.upper() or "PROTON" in sheet_name.upper() or "COVER" in sheet_name.upper():
                        continue
                    
                    res = parse_sheet(df, sheet_name, 'provider')
                    if not res.empty:
                        provider_data.append(res)
                        proton_providers.append(res)
                
                # Create TOPC Clinic Aggregate
                if proton_providers:
                    combined_proton = pd.concat(proton_providers)
                    # Sum by Month, resetting index to avoid errors
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

            # --- SCENARIO 2: STANDARD FILES ---
            else:
                for sheet_name, df in xls.items():
                    if sheet_name in CLINIC_CONFIG:
                        res = parse_sheet(df, sheet_name, 'clinic')
                        if not res.empty: clinic_data.append(res)
                    elif sheet_name in PROVIDER_CONFIG:
                        res = parse_sheet(df, sheet_name, 'provider')
                        if not res.empty: provider_data.append(res)
                    elif "LROC" in filename and "LROC" in sheet_name.upper():
                         res = parse_sheet(df, "LROC", 'clinic')
                         if not res.empty: clinic_data.append(res)
                    elif "TROC" in filename and "TROC" in sheet_name.upper():
                         res = parse_sheet(df, "TROC", 'clinic')
                         if not res.empty: clinic_data.append(res)

        df_clinic = pd.concat(clinic_data, ignore_index=True) if clinic_data else pd.DataFrame()
        df_provider = pd.concat(provider_data, ignore_index=True) if provider_data else pd.DataFrame()

        # Date Cleaning with error handling
        for d in [df_clinic, df_provider]:
            if not d.empty:
                d['Month_Clean'] = pd.to_datetime(d['Month'], errors='coerce')
                # Drop rows where date parsing failed
                d.dropna(subset=['Month_Clean'], inplace=True)
                d.sort_values('Month_Clean', inplace=True)
                d['Month_Label'] = d['Month_Clean'].dt.strftime('%b-%y')

        return df_clinic, df_provider

    # --- PAGE LAYOUT ---
    st.set_page_config(page_title="RadOnc Analytics", layout="wide", page_icon="🩺")
    st.title("🩺 Radiation Oncology Division Analytics")

    with st.sidebar:
        st.header("Data Import")
        uploaded_files = st.file_uploader("Upload Excel Reports", type=['xlsx', 'xls'], accept_multiple_files=True)
        st.info("System recognizes PROTON, LROC, TROC, and Master files automatically.")

    if uploaded_files:
        with st.spinner("Processing files..."):
            df_clinic, df_provider = process_files(uploaded_files)

        # Check if we actually got valid data after date filtering
        if df_clinic.empty and df_provider.empty:
            st.error("⚠️ Data loaded, but no valid dates found. Please check that your Excel files have dates (e.g., 'Jan-24') in the first few rows of columns E-P.")
        else:
            tab_clinics, tab_providers = st.tabs(["🏥 Clinic Analytics", "👨‍⚕️ Provider Analytics"])

            # === TAB 1: CLINICS ===
            with tab_clinics:
                if df_clinic.empty:
                    st.warning("No Clinic data found.")
                else:
                    # Calculate Market Avg safely
                    clinic_grp = df_clinic.groupby('Month_Clean', as_index=False)[['Total RVUs', 'FTE']].sum()
                    clinic_grp['Avg RVU/FTE'] = clinic_grp['Total RVUs'] / clinic_grp['FTE']
                    
                    df_clinic = df_clinic.merge(clinic_grp[['Month_Clean', 'Avg RVU/FTE']], on='Month_Clean', how='left')

                    latest_mo = df_clinic['Month_Clean'].max()
                    latest_c = df_clinic[df_clinic['Month_Clean'] == latest_mo]
                    
                    c1, c2, c3 = st.columns(3)
                    c1.metric("Division Total RVUs", f"{latest_c['Total RVUs'].sum():,.0f}", f"{latest_mo.strftime('%b %Y')}")
                    
                    # Safe access to market value
                    mkt_vals = clinic_grp[clinic_grp['Month_Clean']==latest_mo]['Avg RVU/FTE'].values
                    mkt_display = f"{mkt_vals[0]:,.0f}" if len(mkt_vals) > 0 else "N/A"
                    c2.metric("Market Avg RVU/FTE", mkt_display)
                    
                    if not latest_c.empty:
                        top_clinic = latest_c.loc[latest_c['RVU per FTE'].idxmax()]
                        c3.metric("Top Clinic", top_clinic['Name'], f"{top_clinic['RVU per FTE']:,.0f} RVU/FTE")

                    st.markdown("#### 📊 Clinic Performance Matrix")
                    fig_scatter = px.scatter(latest_c, x="FTE", y="Total RVUs", size="RVU per FTE", color="Name", text="Name", 
                                             title=f"Volume vs Staffing ({latest_mo.strftime('%b %Y')})")
                    st.plotly_chart(fig_scatter, use_container_width=True)

                    st.markdown("#### 📈 Longitudinal Trends")
                    selected_clinics = st.multiselect("Select Clinics", df_clinic['Name'].unique(), default=df_clinic['Name'].unique())
                    fig_line = px.line(df_clinic[df_clinic['Name'].isin(selected_clinics)], x='Month_Clean', y='RVU per FTE', color='Name', markers=True)
                    fig_line.add_trace(go.Scatter(x=clinic_grp['Month_Clean'], y=clinic_grp['Avg RVU/FTE'], name='Market Avg', line=dict(color='black', width=3, dash='dot')))
                    st.plotly_chart(fig_line, use_container_width=True)

            # === TAB 2: PROVIDERS ===
            with tab_providers:
                if df_provider.empty:
                    st.warning("No Provider data found.")
                else:
                    df_included = df_provider[df_provider['ID'].isin(MARKET_AVG_INCLUSION)]
                    
                    prov_grp = df_included.groupby('Month_Clean', as_index=False)[['Total RVUs', 'FTE']].sum()
                    prov_grp['Avg RVU/FTE'] = prov_grp['Total RVUs'] / prov_grp['FTE']
                    
                    df_provider = df_provider.merge(prov_grp[['Month_Clean', 'Avg RVU/FTE']], on='Month_Clean', how='left')

                    st.sidebar.markdown("### 🔮 Scenario Planner")
                    scenario_prov = st.sidebar.selectbox("Select Provider", df_provider['Name'].unique())
                    current_fte = PROVIDER_CONFIG.get(scenario_prov, 1.0)
                    new_fte = st.sidebar.slider(f"Adjust {scenario_prov} FTE", 0.1, 2.0, float(current_fte), 0.1)
                    
                    scenario_df = df_provider.copy()
                    scenario_df.loc[scenario_df['Name'] == scenario_prov, 'RVU per FTE'] = scenario_df.loc[scenario_df['Name'] == scenario_prov, 'Total RVUs'] / new_fte

                    st.markdown("#### 👥 Provider Group Analysis")
                    group_select = st.selectbox("Select Group", ["All Providers", "Photon Sites", "APPs", "Proton Center"])
                    
                    if group_select == "Photon Sites": subset = scenario_df[scenario_df['ID'].isin(PROVIDER_GROUPS["Photon Sites"])]
                    elif group_select == "APPs": subset = scenario_df[scenario_df['ID'].isin(PROVIDER_GROUPS["APPs"])]
                    elif group_select == "Proton Center": subset = scenario_df[scenario_df['ID'].isin(PROVIDER_GROUPS["Proton Center"])]
                    else: subset = scenario_df
                    
                    if not subset.empty:
                        latest_p_mo = subset['Month_Clean'].max()
                        latest_p_data = subset[subset['Month_Clean'] == latest_p_mo].sort_values("RVU per FTE", ascending=False)
                        
                        fig_bar = px.bar(latest_p_data, x='Name', y='RVU per FTE', color='RVU per FTE', title="RVU per FTE (Latest Month)", color_continuous_scale='Viridis')
                        
                        mkt_val_p = prov_grp[prov_grp['Month_Clean'] == latest_p_mo]['Avg RVU/FTE'].values
                        if len(mkt_val_p) > 0:
                             fig_bar.add_hline(y=mkt_val_p[0], line_dash="dot", annotation_text="Market Avg", annotation_position="top right")
                        
                        st.plotly_chart(fig_bar, use_container_width=True)

                        st.markdown("#### 📅 Quarterly Performance")
                        pivot = subset.pivot_table(index="Name", columns="Month_Label", values="Total RVUs", aggfunc="sum").fillna(0)
                        pivot["Total"] = pivot.sum(axis=1)
                        st.dataframe(pivot.sort_values("Total", ascending=False).style.format("{:,.0f}").background_gradient(cmap="Blues"))
                    else:
                        st.info(f"No providers found in the '{group_select}' group.")
    else:
        st.info("👋 Ready for analysis. Please upload monthly Excel reports.")
