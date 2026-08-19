"""Shared session-state management. All multipage files should import from
here rather than re-initializing state, to avoid duplicate initialization.

Manual overrides and planner notes are stored only in st.session_state for
the duration of a session (no persistent database is configured), per the
build instructions.
"""
from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

import streamlit as st

from src.schemas import REQUIRED_UPLOADS

TIMEZONE = ZoneInfo("America/Toronto")

UPLOADS_KEY = "uploads"  # dict[filename] -> LoadResult
PROCESSED_KEY = "processed"  # bool
REFRESH_TS_KEY = "refresh_timestamp"
OVERRIDES_KEY = "manual_overrides"  # dict[(plant, material)] -> {"override": float, "note": str}
DEV_MODE_KEY = "dev_mode"


def init_session_state() -> None:
    if UPLOADS_KEY not in st.session_state:
        st.session_state[UPLOADS_KEY] = {}
    if PROCESSED_KEY not in st.session_state:
        st.session_state[PROCESSED_KEY] = False
    if REFRESH_TS_KEY not in st.session_state:
        st.session_state[REFRESH_TS_KEY] = None
    if OVERRIDES_KEY not in st.session_state:
        st.session_state[OVERRIDES_KEY] = {}
    if DEV_MODE_KEY not in st.session_state:
        st.session_state[DEV_MODE_KEY] = False


def all_uploads_valid() -> bool:
    uploads = st.session_state.get(UPLOADS_KEY, {})
    if len(uploads) != len(REQUIRED_UPLOADS):
        return False
    return all(uploads.get(f) is not None and uploads[f].status == "Valid" for f in REQUIRED_UPLOADS)


def mark_processed() -> None:
    st.session_state[PROCESSED_KEY] = True
    st.session_state[REFRESH_TS_KEY] = datetime.now(TIMEZONE)


def is_processed() -> bool:
    return bool(st.session_state.get(PROCESSED_KEY, False))


def refresh_timestamp_display() -> str:
    ts = st.session_state.get(REFRESH_TS_KEY)
    if ts is None:
        return "Not yet processed"
    return ts.strftime("%Y-%m-%d %H:%M:%S %Z")


def get_override(plant: str, material: str) -> float:
    return st.session_state[OVERRIDES_KEY].get((plant, material), {}).get("override", 0.0)


def get_note(plant: str, material: str) -> str:
    return st.session_state[OVERRIDES_KEY].get((plant, material), {}).get("note", "")


def set_override(plant: str, material: str, override: float, note: str) -> None:
    st.session_state[OVERRIDES_KEY][(plant, material)] = {"override": override, "note": note}


def overrides_frame():
    import pandas as pd
    rows = [
        {"Plant": p, "Material": m, "Manual_Override": v["override"], "Planner_Note": v["note"]}
        for (p, m), v in st.session_state.get(OVERRIDES_KEY, {}).items()
    ]
    return pd.DataFrame(rows, columns=["Plant", "Material", "Manual_Override", "Planner_Note"])
