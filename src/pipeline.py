"""Wire loaders -> aggregate -> reconciliation into one cached pipeline.

Cached by the tuple of the nine uploaded files' content hashes, so
re-running the pipeline is free until an upload actually changes.
"""
from __future__ import annotations

import pandas as pd
import streamlit as st

from src.aggregate import build_ordering_dashboard, apply_manual_overrides
from src.config import allocation_field_by_plant, safety_stock_pct
from src.product_master import target_stock_lookup
from src.reconciliation import build_reconciliation_report
from src.schemas import UPLOAD_FILE_MAP
from src.state import overrides_frame


def _combine_raw_frames(load_results: dict) -> dict[str, pd.DataFrame]:
    by_kind: dict[str, list[pd.DataFrame]] = {"customer_orders": [], "on_hand": [], "open_orders": []}
    for filename, lr in load_results.items():
        by_kind[lr.kind].append(lr.dataframe)
    return {kind: pd.concat(frames, ignore_index=True) for kind, frames in by_kind.items() if frames}


@st.cache_data(show_spinner="Building ordering dashboard...")
def _run_pipeline_cached(file_hashes: tuple[tuple[str, str], ...]):
    load_results = st.session_state["uploads"]
    raw_frames = _combine_raw_frames(load_results)

    target_stock_df = target_stock_lookup()

    dashboard_grid = build_ordering_dashboard(
        on_hand_df=raw_frames["on_hand"],
        customer_orders_df=raw_frames["customer_orders"],
        open_orders_df=raw_frames["open_orders"],
        target_stock_df=target_stock_df,
        allocation_field_by_plant=allocation_field_by_plant(),
        safety_stock_pct=safety_stock_pct(),
    )

    report = build_reconciliation_report(
        raw_frames=raw_frames,
        load_results=load_results,
        dashboard_grid=dashboard_grid,
        target_stock_df=target_stock_df,
    )

    return raw_frames, dashboard_grid, report


def run_pipeline():
    """Returns (raw_frames, dashboard_grid, reconciliation_report). Requires
    all nine uploads to already be valid in session_state.

    dashboard_grid has session-only Manual_Override/Planner_Note edits
    applied fresh on every call (cheap, and never part of the cache key --
    overrides change far more often than the uploaded files do)."""
    load_results = st.session_state["uploads"]
    file_hashes = tuple(sorted((f, lr.file_hash) for f, lr in load_results.items()))
    raw_frames, dashboard_grid, report = _run_pipeline_cached(file_hashes)

    overrides = overrides_frame()
    dashboard_grid = apply_manual_overrides(dashboard_grid, overrides, safety_stock_pct())

    return raw_frames, dashboard_grid, report
