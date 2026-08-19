"""Data Quality & Reconciliation checks.

All reconciliation variances must be zero before the Export Center enables
its export button, per the build instructions.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

import pandas as pd

from src.schemas import COLUMNS_BY_KIND

CONFIG_DIR = Path(__file__).resolve().parent.parent / "config"

QUANTITY_FIELDS_BY_KIND = {
    "customer_orders": ["Order Quantity", "Confirmed Quantity (CS)"],
    "on_hand": ["Unrestricted Stock", "Stock in Quality Inspection", "Blocked Stock"],
    "open_orders": ["Open PO Qty", "PO Quantity", "PO Request Quantity", "Inbound Delivery Quantity"],
}


@dataclass
class ReconciliationReport:
    file_validation: dict = field(default_factory=dict)
    plant_validation: dict = field(default_factory=dict)
    duplicate_row_counts: dict = field(default_factory=dict)
    null_counts: dict = field(default_factory=dict)
    unmatched_materials_by_source: dict = field(default_factory=dict)
    materials_in_sources_not_in_master: list = field(default_factory=list)
    materials_in_master_no_activity: list = field(default_factory=list)
    source_grand_totals: dict = field(default_factory=dict)
    dashboard_grand_totals: dict = field(default_factory=dict)
    grand_total_variances: dict = field(default_factory=dict)
    reference_workbook_audit: dict = field(default_factory=dict)
    extraction_audit: dict = field(default_factory=dict)

    @property
    def all_variances_zero(self) -> bool:
        return all(abs(v) < 1e-6 for v in self.grand_total_variances.values())


def count_duplicate_rows(df: pd.DataFrame) -> int:
    """Full-row duplicate count. Duplicates are reported, never dropped --
    per the build instructions, source duplicates and row order must be
    preserved in the raw exports."""
    return int(df.duplicated(keep=False).sum())


def count_nulls(df: pd.DataFrame, kind: str) -> dict:
    cols = COLUMNS_BY_KIND[kind]
    return {c: int(df[c].isna().sum()) for c in cols if c in df.columns}


def unmatched_materials(source_df: pd.DataFrame, master_keys: set[tuple[str, str]]) -> pd.DataFrame:
    keys = source_df[["Plant", "Material"]].drop_duplicates()
    mask = ~keys.apply(lambda r: (r["Plant"], r["Material"]) in master_keys, axis=1)
    return keys[mask]


def build_reconciliation_report(
    raw_frames: dict[str, pd.DataFrame],
    load_results: dict[str, "LoadResult"],
    dashboard_grid: pd.DataFrame,
    target_stock_df: pd.DataFrame,
) -> ReconciliationReport:
    report = ReconciliationReport()

    for filename, lr in load_results.items():
        report.file_validation[filename] = {
            "status": lr.status,
            "row_count": lr.row_count,
            "error": lr.error,
        }
        report.plant_validation[filename] = {
            "expected_plant": lr.expected_plant,
            "violations": lr.plant_violations,
        }

    for kind, df in raw_frames.items():
        report.duplicate_row_counts[kind] = count_duplicate_rows(df)
        report.null_counts[kind] = count_nulls(df, kind)

    master_keys = set(zip(target_stock_df["Plant"], target_stock_df["Material"]))

    union_source_keys: set[tuple[str, str]] = set()
    for kind, df in raw_frames.items():
        unmatched = unmatched_materials(df, master_keys)
        report.unmatched_materials_by_source[kind] = unmatched.to_dict("records")
        union_source_keys |= set(zip(df["Plant"], df["Material"]))

    report.materials_in_sources_not_in_master = [
        {"Plant": p, "Material": m} for p, m in sorted(union_source_keys - master_keys)
    ]
    report.materials_in_master_no_activity = [
        {"Plant": p, "Material": m} for p, m in sorted(master_keys - union_source_keys)
    ]

    variances = {}
    source_totals = {}
    dash_totals = {}

    if "on_hand" in raw_frames:
        source_totals["Unrestricted_On_Hand"] = float(raw_frames["on_hand"]["Unrestricted Stock"].sum())
        dash_totals["Unrestricted_On_Hand"] = float(dashboard_grid["Unrestricted_On_Hand"].sum())
    if "customer_orders" in raw_frames:
        source_totals["Customer_Order_Qty"] = float(raw_frames["customer_orders"]["Order Quantity"].sum())
        dash_totals["Customer_Order_Qty"] = float(dashboard_grid["Customer_Order_Qty"].sum())
        source_totals["Confirmed_Qty"] = float(raw_frames["customer_orders"]["Confirmed Quantity (CS)"].sum())
        dash_totals["Confirmed_Qty"] = float(dashboard_grid["Confirmed_Qty"].sum())
    if "open_orders" in raw_frames:
        source_totals["Open_PO_Qty"] = float(raw_frames["open_orders"]["Open PO Qty"].sum())
        dash_totals["Open_PO_Qty"] = float(dashboard_grid["Open_PO_Qty"].sum())

    for key in source_totals:
        variances[key] = round(dash_totals[key] - source_totals[key], 6)

    report.source_grand_totals = source_totals
    report.dashboard_grand_totals = dash_totals
    report.grand_total_variances = variances

    ref_audit_path = CONFIG_DIR / "reference_workbook_audit.json"
    if ref_audit_path.exists():
        report.reference_workbook_audit = json.loads(ref_audit_path.read_text())

    extraction_audit_path = CONFIG_DIR / "product_master_extraction_audit.json"
    if extraction_audit_path.exists():
        report.extraction_audit = json.loads(extraction_audit_path.read_text())

    return report
