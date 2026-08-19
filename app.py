"""Linda Ordering Dashboard -- Home / Upload page.

Replaces the manual "Linda New Ordering Spreadsheet" Excel workflow with an
interactive Streamlit dashboard. See README.md for local run and deployment
instructions.
"""
from __future__ import annotations

import os
from pathlib import Path

import streamlit as st

from src.loaders import load_upload, STATUS_MISSING, STATUS_VALID, STATUS_ERROR, STATUS_VALIDATING
from src.schemas import REQUIRED_UPLOADS, UPLOAD_FILE_MAP
from src.state import (
    init_session_state, all_uploads_valid, mark_processed, is_processed,
    refresh_timestamp_display, UPLOADS_KEY, DEV_MODE_KEY,
)

st.set_page_config(page_title="Linda Ordering Dashboard", layout="wide", page_icon="📦")
init_session_state()

def _secrets_dev_mode() -> bool:
    try:
        return bool(st.secrets.get("dev_mode", False))
    except Exception:
        # no secrets.toml configured at all -- treat as dev_mode off, never
        # let a missing secrets file crash the app
        return False


DEV_MODE_ENABLED = os.environ.get("LINDA_DEV_MODE", "").lower() in ("1", "true", "yes") or _secrets_dev_mode()

GROUPS = {
    "Customer Orders": [f for f, (k, _) in UPLOAD_FILE_MAP.items() if k == "customer_orders"],
    "On Hand": [f for f, (k, _) in UPLOAD_FILE_MAP.items() if k == "on_hand"],
    "Open Orders": [f for f, (k, _) in UPLOAD_FILE_MAP.items() if k == "open_orders"],
}

STATUS_BADGE = {
    STATUS_MISSING: ("⬜", "Missing"),
    STATUS_VALIDATING: ("🟡", "Validating"),
    STATUS_VALID: ("🟢", "Valid"),
    STATUS_ERROR: ("🔴", "Error"),
}

st.title("📦 Linda Ordering Dashboard")
st.caption(
    "Upload the nine SAP exports below, then click **Process Files**. "
    f"Last refresh: {refresh_timestamp_display()}"
)

if DEV_MODE_ENABLED:
    st.info("Development mode is ON (LINDA_DEV_MODE). Bundled sample data is available below.", icon="🛠️")
    sample_dir = Path(__file__).parent / "sample_data"
    if sample_dir.exists() and st.button("Load bundled sample data"):
        for filename in REQUIRED_UPLOADS:
            path = sample_dir / filename
            if path.exists():
                result = load_upload(filename, path.read_bytes())
                st.session_state[UPLOADS_KEY][filename] = result
        st.rerun()

st.divider()

for group_name, filenames in GROUPS.items():
    st.subheader(group_name)
    cols = st.columns(len(filenames))
    for col, filename in zip(cols, filenames):
        with col:
            uploaded = st.file_uploader(filename, type=["xlsx"], key=f"uploader_{filename}")
            if uploaded is not None:
                result = load_upload(filename, uploaded.getvalue())
                st.session_state[UPLOADS_KEY][filename] = result
            current = st.session_state[UPLOADS_KEY].get(filename)
            status = current.status if current else STATUS_MISSING
            icon, label = STATUS_BADGE[status]
            st.markdown(f"{icon} **{label}**")
            if current:
                if current.status == STATUS_VALID:
                    st.caption(f"{current.row_count:,} rows")
                elif current.error:
                    st.error(current.error, icon="⚠️")

st.divider()

ready = all_uploads_valid()
if not ready:
    missing_or_bad = [
        f for f in REQUIRED_UPLOADS
        if st.session_state[UPLOADS_KEY].get(f) is None or st.session_state[UPLOADS_KEY][f].status != STATUS_VALID
    ]
    st.warning(f"{len(missing_or_bad)} of 9 required file(s) still need a valid upload before processing.")

if st.button("Process Files", type="primary", disabled=not ready, use_container_width=False):
    mark_processed()
    st.success("Files processed. Use the sidebar to open Ordering Dashboard, Supplier Detail, Data Quality, or Export Center.")

if is_processed():
    st.success(f"✅ Processing complete -- refreshed {refresh_timestamp_display()}")
