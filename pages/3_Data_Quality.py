from __future__ import annotations

import pandas as pd
import streamlit as st

from src.pipeline import run_pipeline
from src.state import init_session_state, is_processed

st.set_page_config(page_title="Data Quality & Reconciliation | Linda Ordering Dashboard", layout="wide", page_icon="🔍")
init_session_state()

st.title("🔍 Data Quality & Reconciliation")

if not is_processed():
    st.info("Upload and process the nine SAP exports on the Home page first.", icon="⬅️")
    st.stop()

raw_frames, grid, report = run_pipeline()

if report.all_variances_zero:
    st.success("✅ All reconciliation variances are zero. Export Center is unlocked.")
else:
    st.error("❌ One or more reconciliation variances are non-zero. Export Center is locked until this is resolved.")

st.divider()

st.subheader("File / schema validation")
fv_rows = [{"File": f, **v} for f, v in report.file_validation.items()]
st.dataframe(pd.DataFrame(fv_rows), use_container_width=True, hide_index=True)

st.subheader("Plant-value validation")
pv_rows = [
    {"File": f, "Expected plant": v["expected_plant"], "Unexpected plant values found": ", ".join(v["violations"]) or "(none)"}
    for f, v in report.plant_validation.items()
]
st.dataframe(pd.DataFrame(pv_rows), use_container_width=True, hide_index=True)

st.divider()

c1, c2 = st.columns(2)
with c1:
    st.subheader("Duplicate row counts")
    st.caption("Preserved, not deleted -- see feedback: always surface duplicates for review rather than silently dropping them.")
    st.dataframe(pd.DataFrame([{"Dataset": k, "Duplicate rows": v} for k, v in report.duplicate_row_counts.items()]),
                 use_container_width=True, hide_index=True)

with c2:
    st.subheader("Null / invalid-type counts")
    for kind, counts in report.null_counts.items():
        nonzero = {k: v for k, v in counts.items() if v > 0}
        if nonzero:
            st.markdown(f"**{kind}**")
            st.dataframe(pd.DataFrame([{"Column": k, "Null / invalid count": v} for k, v in nonzero.items()]),
                         use_container_width=True, hide_index=True)
    if not any(any(v > 0 for v in c.values()) for c in report.null_counts.values()):
        st.caption("No nulls or invalid types detected in required columns.")

st.divider()

st.subheader("Unmatched materials")
t1, t2, t3 = st.tabs(["By source (in SAP, not in product master)", "Combined (any source, not in master)", "In master, no current SAP activity"])
with t1:
    for kind, materials in report.unmatched_materials_by_source.items():
        st.markdown(f"**{kind}** -- {len(materials)} unmatched")
        if materials:
            st.dataframe(pd.DataFrame(materials), use_container_width=True, hide_index=True)
with t2:
    st.dataframe(pd.DataFrame(report.materials_in_sources_not_in_master), use_container_width=True, hide_index=True)
with t3:
    st.dataframe(pd.DataFrame(report.materials_in_master_no_activity), use_container_width=True, hide_index=True)

st.divider()

st.subheader("Source grand totals vs. dashboard grand totals")
totals_rows = [
    {
        "Metric": k,
        "Source total": report.source_grand_totals[k],
        "Dashboard total": report.dashboard_grand_totals[k],
        "Variance": v,
    }
    for k, v in report.grand_total_variances.items()
]
totals_df = pd.DataFrame(totals_rows)
st.dataframe(
    totals_df, use_container_width=True, hide_index=True,
    column_config={
        "Source total": st.column_config.NumberColumn(format="%.0f"),
        "Dashboard total": st.column_config.NumberColumn(format="%.0f"),
        "Variance": st.column_config.NumberColumn(format="%.2f"),
    },
)

st.divider()

st.subheader("Reference workbook formula / reference extraction warnings")
ref_audit = report.reference_workbook_audit
if ref_audit:
    m1, m2, m3 = st.columns(3)
    m1.metric("Sheets surveyed", ref_audit.get("total_sheets"))
    m2.metric("Total formulas", f"{ref_audit.get('total_formulas', 0):,}")
    m3.metric("#REF! error formulas (excluded)", f"{ref_audit.get('total_ref_error_formulas', 0):,}")
    st.caption(ref_audit.get("note", ""))
    st.dataframe(
        pd.DataFrame([{"Supplier sheet": k, **v} for k, v in ref_audit.get("supplier_sheets", {}).items()]),
        use_container_width=True, hide_index=True,
    )

extraction_audit = report.extraction_audit
known_limitations = extraction_audit.get("_known_limitations") if extraction_audit else None
if known_limitations:
    st.warning("**Known extraction limitations**")
    for sheet, note in known_limitations.items():
        st.markdown(f"- **{sheet}**: {note}")
