from __future__ import annotations

import pandas as pd
import streamlit as st

from src.pipeline import run_pipeline
from src.product_master import plant_name_map, supplier_color_map
from src.state import init_session_state, is_processed, set_override, get_override, get_note

st.set_page_config(page_title="Supplier Detail | Linda Ordering Dashboard", layout="wide", page_icon="🏷️")
init_session_state()

st.title("🏷️ Supplier Detail")

if not is_processed():
    st.info("Upload and process the nine SAP exports on the Home page first.", icon="⬅️")
    st.stop()

raw_frames, grid, report = run_pipeline()
plants = plant_name_map()
colors = supplier_color_map()

suppliers = sorted(grid["Supplier"].dropna().unique())
if not suppliers:
    st.warning("No supplier matched any uploaded material yet -- check Data Quality for unmatched materials.")
    st.stop()

supplier = st.selectbox("Supplier", suppliers)
color = colors.get(supplier, "#374151")
st.markdown(
    f'<div style="border-left: 6px solid {color}; padding-left: 12px;">'
    f'<h3 style="margin:0;color:{color}">{supplier}</h3></div>',
    unsafe_allow_html=True,
)

subset = grid[grid["Supplier"] == supplier].copy()

st.caption(
    "Forecast periods: this supplier's Target Stock is the single most-recently-populated "
    "'Forecast AS400' baseline extracted per material (see Data Quality page for provenance). "
    "The source workbook has no clean multi-period forecast to select from -- broken (#REF!) "
    "month-by-month columns were excluded rather than translated."
)
plant_filter = st.multiselect("Plant", sorted(subset["Plant"].unique()), default=sorted(subset["Plant"].unique()))
subset = subset[subset["Plant"].isin(plant_filter)]

st.divider()

tabs = st.tabs([
    "Product identification", "Demand / forecast", "Customer orders", "On hand",
    "Open purchase orders", "Projected position", "Recommendation",
])

id_cols = ["Plant", "Material", "TOL_Material", "Description"]
with tabs[0]:
    st.dataframe(subset[id_cols].rename(columns={
        "Material": "SAP Material", "TOL_Material": "TOL Material", "Description": "Product",
    }), use_container_width=True, hide_index=True)

with tabs[1]:
    st.dataframe(subset[id_cols[:2] + ["Target_Stock", "Safety_Stock"]].rename(columns={
        "Material": "SAP Material", "Target_Stock": "Forecast / Target Stock", "Safety_Stock": "Safety Stock",
    }), use_container_width=True, hide_index=True)

with tabs[2]:
    st.dataframe(subset[id_cols[:2] + ["Customer_Order_Qty", "Confirmed_Qty", "Unconfirmed_Qty"]].rename(columns={
        "Material": "SAP Material", "Customer_Order_Qty": "Customer Order Qty",
        "Confirmed_Qty": "Confirmed Qty", "Unconfirmed_Qty": "Unconfirmed Qty",
    }), use_container_width=True, hide_index=True)

with tabs[3]:
    st.dataframe(subset[id_cols[:2] + ["Unrestricted_On_Hand", "Quality_Inspection_Qty", "Blocked_Stock_Qty", "Earliest_Expiry_Date"]].rename(columns={
        "Material": "SAP Material", "Unrestricted_On_Hand": "Unrestricted On Hand",
        "Quality_Inspection_Qty": "Quality Inspection Qty", "Blocked_Stock_Qty": "Blocked Stock Qty",
        "Earliest_Expiry_Date": "Earliest Expiry Date",
    }), use_container_width=True, hide_index=True)

with tabs[4]:
    st.dataframe(subset[id_cols[:2] + ["Open_PO_Qty", "Allocation_Qty", "Inbound_Delivery_Qty", "Next_PO_Delivery_Date"]].rename(columns={
        "Material": "SAP Material", "Open_PO_Qty": "Open PO Qty", "Allocation_Qty": "Allocation Qty (plant policy)",
        "Inbound_Delivery_Qty": "Inbound Delivery Qty", "Next_PO_Delivery_Date": "Next PO Delivery Date",
    }), use_container_width=True, hide_index=True)

with tabs[5]:
    st.dataframe(subset[id_cols[:2] + ["Available_Plus_Incoming", "Projected_Balance"]].rename(columns={
        "Material": "SAP Material", "Available_Plus_Incoming": "Available + Incoming",
        "Projected_Balance": "Projected Balance",
    }), use_container_width=True, hide_index=True)

with tabs[6]:
    st.caption(
        "Manual Override and Planner Note are editable and stored for this session only "
        "(no persistent database is configured). Overrides are clearly labeled and included in exports."
    )
    rec = subset[id_cols[:2] + ["Suggested_Order_Qty", "Risk_Status"]].copy()
    rec["Manual_Override"] = [get_override(p, m) for p, m in zip(subset["Plant"], subset["Material"])]
    rec["Planner_Note"] = [get_note(p, m) for p, m in zip(subset["Plant"], subset["Material"])]
    rec = rec.rename(columns={
        "Material": "SAP Material", "Suggested_Order_Qty": "Suggested Order Qty", "Risk_Status": "Risk/Status",
    })

    edited = st.data_editor(
        rec,
        use_container_width=True,
        hide_index=True,
        disabled=["Plant", "SAP Material", "Suggested Order Qty", "Risk/Status"],
        column_config={
            "Manual_Override": st.column_config.NumberColumn("Manual Override", help="Session-only adjustment applied to Suggested Order Qty"),
            "Planner_Note": st.column_config.TextColumn("Planner Note"),
        },
        key=f"editor_{supplier}",
    )

    if st.button("Save overrides", type="primary"):
        for _, row in edited.iterrows():
            set_override(row["Plant"], row["SAP Material"], float(row["Manual_Override"] or 0), row["Planner_Note"] or "")
        st.success("Overrides saved for this session.")
        st.rerun()
