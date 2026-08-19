from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

import streamlit as st

from src.excel_export import build_export_workbook, build_audit_report_text
from src.pipeline import run_pipeline
from src.state import init_session_state, is_processed, refresh_timestamp_display

st.set_page_config(page_title="Export Center | Linda Ordering Dashboard", layout="wide", page_icon="📤")
init_session_state()

st.title("📤 Export Center")

if not is_processed():
    st.info("Upload and process the nine SAP exports on the Home page first.", icon="⬅️")
    st.stop()

raw_frames, grid, report = run_pipeline()

today_str = datetime.now(ZoneInfo("America/Toronto")).strftime("%Y-%m-%d")

if not report.all_variances_zero:
    st.error(
        "❌ Reconciliation variances are non-zero. Resolve them on the Data Quality & "
        "Reconciliation page before exporting.",
        icon="🚫",
    )
    st.stop()

st.success("✅ Reconciliation passed -- exports are unlocked.")

st.subheader("1. Full Excel workbook")
st.caption(
    "A new, clean workbook built with XlsxWriter: Executive Summary, Ordering Dashboard, "
    "one sheet per supplier, Reconciliation, Unmatched Materials, the nine raw source sheets, "
    "and a Data Dictionary. No PivotTables, no external links."
)
if st.button("Build Excel workbook", type="primary"):
    with st.spinner("Building workbook..."):
        xlsx_bytes = build_export_workbook(grid, raw_frames, report, refresh_timestamp_display())
    st.session_state["_export_xlsx"] = xlsx_bytes

if "_export_xlsx" in st.session_state:
    st.download_button(
        f"⬇ Download Linda_Ordering_Dashboard_{today_str}.xlsx",
        data=st.session_state["_export_xlsx"],
        file_name=f"Linda_Ordering_Dashboard_{today_str}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )

st.divider()

st.subheader("2. Audit report (.txt)")
audit_text = build_audit_report_text(report, refresh_timestamp_display())
st.text_area("Preview", audit_text, height=240)
st.download_button(
    f"⬇ Download Linda_Ordering_Audit_{today_str}.txt",
    data=audit_text.encode("utf-8"),
    file_name=f"Linda_Ordering_Audit_{today_str}.txt",
    mime="text/plain",
)

st.divider()

st.subheader("3. Filtered dashboard CSV")
st.caption("Downloads the full current dashboard grid. Filter on the Ordering Dashboard page and use the download button there for a filtered subset.")
st.download_button(
    "⬇ Download full dashboard CSV",
    data=grid.to_csv(index=False).encode("utf-8"),
    file_name=f"Linda_Ordering_Dashboard_{today_str}.csv",
    mime="text/csv",
)
