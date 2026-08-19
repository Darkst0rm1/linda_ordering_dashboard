"""Load the extracted supplier/product master and supplier display config.

config/product_master.csv and config/suppliers.yaml are version-controlled
extraction outputs from the reference workbook (see
scripts/build_product_master.py and config/product_master_extraction_audit.json
for provenance). They are reference/master inputs, kept separate from the
nine refreshable SAP datasets, per the build instructions.
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd
import streamlit as st
import yaml

CONFIG_DIR = Path(__file__).resolve().parent.parent / "config"
PRODUCT_MASTER_CSV = CONFIG_DIR / "product_master.csv"
SUPPLIERS_YAML = CONFIG_DIR / "suppliers.yaml"


@st.cache_data(show_spinner=False)
def load_product_master() -> pd.DataFrame:
    df = pd.read_csv(PRODUCT_MASTER_CSV, dtype={"Plant": str, "Material": str, "TOL_Material": str})
    # a blank CSV cell becomes NaN (float) even under dtype=str -- a
    # (Plant, Material) row with either missing is not a usable composite
    # key, so drop it here rather than let a float/str mix reach set/sort
    # operations downstream in reconciliation.
    df = df.dropna(subset=["Plant", "Material"]).copy()
    df["Plant"] = df["Plant"].astype(str)
    df["Material"] = df["Material"].astype(str)
    df["Latest_Forecast_Qty"] = pd.to_numeric(df["Latest_Forecast_Qty"], errors="coerce")
    # a (Plant, Material) can legitimately appear on more than one supplier
    # sheet only if it's a genuine duplicate row within that sheet; keep the
    # row with the most recently populated forecast when collapsing to one
    # target per key, but surface the rest via duplicate reporting upstream.
    return df


@st.cache_data(show_spinner=False)
def load_suppliers_config() -> dict:
    with SUPPLIERS_YAML.open(encoding="utf-8") as f:
        return yaml.safe_load(f)


def supplier_color_map() -> dict[str, str]:
    cfg = load_suppliers_config()
    return {s["display_name"]: s["color"] for s in cfg["suppliers"]}


def plant_color_map() -> dict[str, str]:
    cfg = load_suppliers_config()
    return cfg["plant_colors"]


def status_color_map() -> dict[str, str]:
    cfg = load_suppliers_config()
    return cfg["status_colors"]


def plant_name_map() -> dict[str, str]:
    cfg = load_suppliers_config()
    return cfg["plants"]


def target_stock_lookup() -> pd.DataFrame:
    """One row per (Plant, Material) with Supplier, TOL_Material,
    Description, and Target_Stock (= Latest_Forecast_Qty). When the same
    (Plant, Material) appears more than once (rare, but possible if two
    supplier sheets both listed it), the row with the highest
    Latest_Forecast_Qty wins and the rest are reported as duplicates
    upstream in reconciliation -- never silently summed or averaged."""
    df = load_product_master()
    df = df.sort_values("Latest_Forecast_Qty", ascending=False, na_position="last")
    deduped = df.drop_duplicates(subset=["Plant", "Material"], keep="first")
    return deduped.rename(columns={"Latest_Forecast_Qty": "Target_Stock"})
