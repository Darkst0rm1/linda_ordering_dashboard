"""Shared synthetic fixtures. These are small, hand-built DataFrames -- not
the real supplied SAP exports (which are never committed to the repo) --
used to exercise schema/aggregation/reconciliation/export logic in
isolation.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.schemas import CUSTOMER_ORDERS_COLUMNS, ON_HAND_COLUMNS, OPEN_ORDERS_COLUMNS


def _blank_row(columns: list[str], **overrides) -> dict:
    row = {c: None for c in columns}
    row.update(overrides)
    return row


@pytest.fixture
def customer_orders_df() -> pd.DataFrame:
    rows = [
        _blank_row(CUSTOMER_ORDERS_COLUMNS, Plant="2910", Material="10013700",
                   **{"Order Quantity": 10, "Confirmed Quantity (CS)": 8}),
        _blank_row(CUSTOMER_ORDERS_COLUMNS, Plant="2910", Material="10013700",
                   **{"Order Quantity": 5, "Confirmed Quantity (CS)": 5}),
        _blank_row(CUSTOMER_ORDERS_COLUMNS, Plant="2920", Material="10013700",
                   **{"Order Quantity": 20, "Confirmed Quantity (CS)": 15}),
        _blank_row(CUSTOMER_ORDERS_COLUMNS, Plant="2910", Material="10099999",
                   **{"Order Quantity": 3, "Confirmed Quantity (CS)": 3}),
    ]
    return pd.DataFrame(rows)


@pytest.fixture
def on_hand_df() -> pd.DataFrame:
    rows = [
        _blank_row(ON_HAND_COLUMNS, Plant="2910", Material="10013700",
                   **{"Unrestricted Stock": 40, "Stock in Quality Inspection": 2, "Blocked Stock": 1,
                      "Shelf Life Expiration Date": pd.Timestamp("2026-12-01")}),
        _blank_row(ON_HAND_COLUMNS, Plant="2910", Material="10013700",
                   **{"Unrestricted Stock": 10, "Stock in Quality Inspection": 0, "Blocked Stock": 0,
                      "Shelf Life Expiration Date": pd.Timestamp("2026-06-01")}),
        _blank_row(ON_HAND_COLUMNS, Plant="2920", Material="10013700",
                   **{"Unrestricted Stock": 5, "Stock in Quality Inspection": 0, "Blocked Stock": 0,
                      "Shelf Life Expiration Date": pd.NaT}),
    ]
    return pd.DataFrame(rows)


@pytest.fixture
def open_orders_df() -> pd.DataFrame:
    rows = [
        _blank_row(OPEN_ORDERS_COLUMNS, Plant="2910", Material="10013700",
                   **{"Open PO Qty": 12, "PO Quantity": 12, "PO Request Quantity": 10,
                      "Inbound Delivery Quantity": 0, "Delivery Date": pd.Timestamp("2026-09-01")}),
        _blank_row(OPEN_ORDERS_COLUMNS, Plant="2920", Material="10013700",
                   **{"Open PO Qty": 8, "PO Quantity": 8, "PO Request Quantity": 6,
                      "Inbound Delivery Quantity": 2, "Delivery Date": pd.Timestamp("2026-08-25")}),
    ]
    return pd.DataFrame(rows)


@pytest.fixture
def target_stock_df() -> pd.DataFrame:
    return pd.DataFrame([
        {"Plant": "2910", "Material": "10013700", "Supplier": "Alimentias",
         "TOL_Material": "13700", "Description": "TEST PRODUCT", "Target_Stock": 50},
        {"Plant": "2920", "Material": "10013700", "Supplier": "Alimentias",
         "TOL_Material": "13700", "Description": "TEST PRODUCT", "Target_Stock": 30},
        # 2910/10099999 intentionally has no target -> "Needs planner target"
    ])


@pytest.fixture
def allocation_field_by_plant() -> dict:
    return {"2910": "PO Quantity", "2920": "PO Request Quantity", "2930": "PO Request Quantity"}
