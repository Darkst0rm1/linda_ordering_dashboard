from __future__ import annotations

import pandas as pd
import plotly.express as px
import streamlit as st

from src.pipeline import run_pipeline
from src.product_master import plant_name_map, status_color_map
from src.state import init_session_state, is_processed, refresh_timestamp_display

st.set_page_config(page_title="Ordering Dashboard | Linda Ordering Dashboard", layout="wide", page_icon="📊")
init_session_state()

st.title("📊 Ordering Dashboard")

if not is_processed():
    st.info("Upload and process the nine SAP exports on the Home page first.", icon="⬅️")
    st.stop()

raw_frames, grid, report = run_pipeline()
plants = plant_name_map()
status_colors = status_color_map()

st.caption(f"Last refresh: {refresh_timestamp_display()}")

# ---- Filters ----
with st.container(border=True):
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        plant_choice = st.selectbox(
            "Plant", ["All"] + [f"{p} {plants[p]}" for p in ["2910", "2920", "2930"]]
        )
    with c2:
        suppliers = sorted(grid["Supplier"].dropna().unique())
        supplier_choice = st.multiselect("Supplier / brand", suppliers)
    with c3:
        material_search = st.text_input("Material / SAP number search")
    with c4:
        desc_search = st.text_input("Product description search")

    c5, c6 = st.columns([1, 2])
    with c5:
        action_only = st.checkbox("Show only items requiring action (Critical / At Risk / Review)")
    with c6:
        months = sorted(grid["Next_PO_Delivery_Date"].dropna().dt.to_period("M").astype(str).unique())
        month_choice = st.multiselect("Next PO delivery month", months)

filtered = grid.copy()
if plant_choice != "All":
    filtered = filtered[filtered["Plant"] == plant_choice.split(" ")[0]]
if supplier_choice:
    filtered = filtered[filtered["Supplier"].isin(supplier_choice)]
if material_search:
    filtered = filtered[filtered["Material"].astype(str).str.contains(material_search, case=False, na=False)]
if desc_search:
    filtered = filtered[filtered["Description"].astype(str).str.contains(desc_search, case=False, na=False)]
if action_only:
    filtered = filtered[filtered["Risk_Status"].isin(["Critical", "At Risk", "Review"])]
if month_choice:
    filtered = filtered[filtered["Next_PO_Delivery_Date"].dt.to_period("M").astype(str).isin(month_choice)]

# ---- KPI cards ----
k = st.columns(4)
k2 = st.columns(4)
k[0].metric("Active materials", f"{filtered[['Plant', 'Material']].drop_duplicates().shape[0]:,}")
k[1].metric("Total unrestricted on-hand", f"{filtered['Unrestricted_On_Hand'].sum():,.0f}")
k[2].metric("Total open PO quantity", f"{filtered['Open_PO_Qty'].sum():,.0f}")
k[3].metric("Total customer-order quantity", f"{filtered['Customer_Order_Qty'].sum():,.0f}")
k2[0].metric("Total confirmed customer-order quantity", f"{filtered['Confirmed_Qty'].sum():,.0f}")
k2[1].metric("Unconfirmed quantity", f"{filtered['Unconfirmed_Qty'].sum():,.0f}")
k2[2].metric("Materials at risk", f"{filtered['Risk_Status'].isin(['Critical', 'At Risk']).sum():,}")
k2[3].metric("Suggested order quantity", f"{filtered['Suggested_Order_Qty'].fillna(0).sum():,.0f}")

st.divider()

# ---- Charts ----
ch1, ch2 = st.columns(2)
with ch1:
    st.subheader("Inventory vs customer demand by plant")
    by_plant = filtered.groupby("Plant", dropna=False).agg(
        On_Hand=("Unrestricted_On_Hand", "sum"), Customer_Demand=("Customer_Order_Qty", "sum"),
    ).reset_index()
    by_plant["Plant"] = by_plant["Plant"].map(lambda p: f"{p} {plants.get(p, '')}")
    fig = px.bar(by_plant.melt(id_vars="Plant", var_name="Metric", value_name="Qty"),
                 x="Plant", y="Qty", color="Metric", barmode="group")
    st.plotly_chart(fig, use_container_width=True)

with ch2:
    st.subheader("Open PO quantity by expected delivery month")
    po_by_month = filtered.dropna(subset=["Next_PO_Delivery_Date"]).copy()
    if po_by_month.empty:
        st.caption("No open POs with a delivery date in the current filter.")
    else:
        po_by_month["Month"] = po_by_month["Next_PO_Delivery_Date"].dt.to_period("M").astype(str)
        agg = po_by_month.groupby("Month")["Open_PO_Qty"].sum().reset_index().sort_values("Month")
        fig = px.bar(agg, x="Month", y="Open_PO_Qty")
        st.plotly_chart(fig, use_container_width=True)

ch3, ch4 = st.columns(2)
with ch3:
    st.subheader("Top materials at risk")
    at_risk = filtered[filtered["Risk_Status"].isin(["Critical", "At Risk"])].copy()
    at_risk = at_risk.sort_values("Projected_Balance").head(10)
    if at_risk.empty:
        st.caption("No materials currently at risk in this filter.")
    else:
        fig = px.bar(at_risk, x="Projected_Balance", y="Description", color="Risk_Status",
                     color_discrete_map=status_colors, orientation="h")
        st.plotly_chart(fig, use_container_width=True)

with ch4:
    st.subheader("Suggested orders by supplier")
    by_supplier = filtered.groupby("Supplier", dropna=False)["Suggested_Order_Qty"].sum().reset_index()
    by_supplier = by_supplier[by_supplier["Suggested_Order_Qty"] > 0].sort_values("Suggested_Order_Qty", ascending=False)
    if by_supplier.empty:
        st.caption("No suggested orders in this filter.")
    else:
        fig = px.bar(by_supplier, x="Supplier", y="Suggested_Order_Qty")
        st.plotly_chart(fig, use_container_width=True)

st.divider()

# ---- Main grid ----
st.subheader("Ordering grid")

display_cols = {
    "Supplier": "Supplier/brand", "Plant": "Plant", "Material": "SAP Material",
    "TOL_Material": "TOL Material", "Description": "Product", "Target_Stock": "Forecast (Target Stock)",
    "Customer_Order_Qty": "Customer Order Qty", "Confirmed_Qty": "Confirmed Qty",
    "Unconfirmed_Qty": "Unconfirmed Qty", "Unrestricted_On_Hand": "Unrestricted On Hand",
    "Open_PO_Qty": "Open PO Qty", "Inbound_Delivery_Qty": "Inbound Delivery Qty",
    "Available_Plus_Incoming": "Available + Incoming", "Projected_Balance": "Projected Balance",
    "Suggested_Order_Qty": "Suggested Order Qty", "Risk_Status": "Risk/Status",
    "Next_PO_Delivery_Date": "Next PO Delivery Date", "Earliest_Expiry_Date": "Earliest Expiry Date",
}
grid_display = filtered[list(display_cols.keys())].rename(columns=display_cols)
grid_display["Plant"] = grid_display["Plant"].map(lambda p: f"{p} {plants.get(p, '')}")

st.dataframe(
    grid_display,
    use_container_width=True,
    height=480,
    hide_index=True,
    column_config={
        "Customer Order Qty": st.column_config.NumberColumn(format="%d"),
        "Confirmed Qty": st.column_config.NumberColumn(format="%d"),
        "Unconfirmed Qty": st.column_config.NumberColumn(format="%d"),
        "Unrestricted On Hand": st.column_config.NumberColumn(format="%d"),
        "Open PO Qty": st.column_config.NumberColumn(format="%d"),
        "Inbound Delivery Qty": st.column_config.NumberColumn(format="%d"),
        "Available + Incoming": st.column_config.NumberColumn(format="%d"),
        "Projected Balance": st.column_config.NumberColumn(format="%d"),
        "Suggested Order Qty": st.column_config.NumberColumn(format="%d"),
        "Forecast (Target Stock)": st.column_config.NumberColumn(format="%d"),
        "Next PO Delivery Date": st.column_config.DateColumn(format="YYYY-MM-DD"),
        "Earliest Expiry Date": st.column_config.DateColumn(format="YYYY-MM-DD"),
    },
)

st.download_button(
    "⬇ Download filtered view as CSV",
    data=grid_display.to_csv(index=False).encode("utf-8"),
    file_name="linda_ordering_dashboard_filtered.csv",
    mime="text/csv",
)
