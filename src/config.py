"""Load config/business_rules.yaml -- the single source for thresholds and
policy constants referenced throughout the app."""
from __future__ import annotations

from pathlib import Path

import streamlit as st
import yaml

CONFIG_DIR = Path(__file__).resolve().parent.parent / "config"
BUSINESS_RULES_YAML = CONFIG_DIR / "business_rules.yaml"


@st.cache_data(show_spinner=False)
def load_business_rules() -> dict:
    with BUSINESS_RULES_YAML.open(encoding="utf-8") as f:
        return yaml.safe_load(f)


def allocation_field_by_plant() -> dict[str, str]:
    return load_business_rules()["allocation_qty_field_by_plant"]


def safety_stock_pct() -> float:
    return load_business_rules()["safety_stock"]["percent_of_target_stock"]
