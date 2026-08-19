"""Composite-key (Plant, Material) aggregation of the three SAP dataset
kinds into the ordering dashboard grid.

Every rule here is taken verbatim from the build instructions' "Exact
aggregation rules" section. Never join on Material alone when combining
plants.
"""
from __future__ import annotations

import math

import numpy as np
import pandas as pd

KEY = ["Plant", "Material"]


def aggregate_on_hand(df: pd.DataFrame) -> pd.DataFrame:
    g = df.groupby(KEY, dropna=False)
    out = g.agg(
        Unrestricted_On_Hand=("Unrestricted Stock", "sum"),
        Quality_Inspection_Qty=("Stock in Quality Inspection", "sum"),
        Blocked_Stock_Qty=("Blocked Stock", "sum"),
        Earliest_Expiry_Date=("Shelf Life Expiration Date", "min"),
    ).reset_index()
    return out


def aggregate_customer_orders(df: pd.DataFrame) -> pd.DataFrame:
    g = df.groupby(KEY, dropna=False)
    out = g.agg(
        Customer_Order_Qty=("Order Quantity", "sum"),
        Confirmed_Qty=("Confirmed Quantity (CS)", "sum"),
    ).reset_index()
    out["Unconfirmed_Qty"] = (out["Customer_Order_Qty"] - out["Confirmed_Qty"]).clip(lower=0)
    return out


def aggregate_open_orders(df: pd.DataFrame, allocation_field_by_plant: dict[str, str]) -> pd.DataFrame:
    g = df.groupby(KEY, dropna=False)
    out = g.agg(
        Open_PO_Qty=("Open PO Qty", "sum"),
        PO_Request_Qty=("PO Request Quantity", "sum"),
        Inbound_Delivery_Qty=("Inbound Delivery Quantity", "sum"),
        Next_PO_Delivery_Date=("Delivery Date", "min"),
    ).reset_index()

    # plant-specific Allocation Qty: sum the plant's configured source field
    # by (Plant, Material) directly off the raw rows, so it stays traceable
    # to a single named SAP column per plant rather than a blended average.
    alloc_frames = []
    for plant, field_name in allocation_field_by_plant.items():
        subset = df[df["Plant"] == plant]
        if subset.empty:
            continue
        alloc = subset.groupby(KEY, dropna=False)[field_name].sum().reset_index()
        alloc = alloc.rename(columns={field_name: "Allocation_Qty"})
        alloc_frames.append(alloc)
    allocation = pd.concat(alloc_frames, ignore_index=True) if alloc_frames else pd.DataFrame(columns=KEY + ["Allocation_Qty"])

    out = out.merge(allocation, on=KEY, how="left")
    return out


def build_ordering_dashboard(
    on_hand_df: pd.DataFrame,
    customer_orders_df: pd.DataFrame,
    open_orders_df: pd.DataFrame,
    target_stock_df: pd.DataFrame,
    allocation_field_by_plant: dict[str, str],
    safety_stock_pct: float,
) -> pd.DataFrame:
    """Build the full ordering-dashboard grid.

    target_stock_df must have columns: Plant, Material, Supplier,
    TOL_Material, Description, Target_Stock (see
    src/product_master.py:target_stock_lookup).
    """
    on_hand_agg = aggregate_on_hand(on_hand_df)
    co_agg = aggregate_customer_orders(customer_orders_df)
    oo_agg = aggregate_open_orders(open_orders_df, allocation_field_by_plant)

    # grid rows = union of every (Plant, Material) seen in any of the three
    # SAP sources -- this is a *current activity* dashboard, not a full
    # product-master dump. Materials in the master with no current SAP
    # activity are reported separately (Data Quality page).
    keys = pd.concat([
        on_hand_agg[KEY], co_agg[KEY], oo_agg[KEY],
    ], ignore_index=True).drop_duplicates()

    grid = keys.merge(on_hand_agg, on=KEY, how="left")
    grid = grid.merge(co_agg, on=KEY, how="left")
    grid = grid.merge(oo_agg, on=KEY, how="left")
    grid = grid.merge(
        target_stock_df[["Plant", "Material", "Supplier", "TOL_Material", "Description", "Target_Stock"]],
        on=KEY, how="left",
    )

    qty_cols = [
        "Unrestricted_On_Hand", "Quality_Inspection_Qty", "Blocked_Stock_Qty",
        "Customer_Order_Qty", "Confirmed_Qty", "Unconfirmed_Qty",
        "Open_PO_Qty", "PO_Request_Qty", "Inbound_Delivery_Qty", "Allocation_Qty",
    ]
    for c in qty_cols:
        grid[c] = pd.to_numeric(grid[c], errors="coerce").fillna(0)

    grid["Available_Plus_Incoming"] = grid["Unrestricted_On_Hand"] + grid["Open_PO_Qty"]
    grid["Projected_Balance"] = grid["Available_Plus_Incoming"] - grid["Customer_Order_Qty"]

    grid["Manual_Override"] = 0.0
    grid["Planner_Note"] = ""
    grid = recompute_suggested_and_risk(grid, safety_stock_pct)

    return grid


def recompute_suggested_and_risk(grid: pd.DataFrame, safety_stock_pct: float) -> pd.DataFrame:
    """(Re)computes Suggested_Order_Qty, Safety_Stock, and Risk_Status from
    Target_Stock / Available_Plus_Incoming / Unconfirmed_Qty / Manual_Override.
    Split out from build_ordering_dashboard so Supplier Detail can re-run it
    cheaply after a planner edits Manual_Override, without re-aggregating the
    whole pipeline."""
    grid = grid.copy()
    grid["Has_Target"] = grid["Target_Stock"].notna()

    def _suggested(row):
        if not row["Has_Target"]:
            return np.nan
        raw = (
            row["Target_Stock"] - row["Available_Plus_Incoming"]
            + row["Unconfirmed_Qty"] + row["Manual_Override"]
        )
        raw = max(raw, 0)
        return math.ceil(raw) if raw > 0 else 0.0

    grid["Suggested_Order_Qty"] = grid.apply(_suggested, axis=1)

    grid["Safety_Stock"] = np.where(
        grid["Has_Target"], grid["Target_Stock"] * safety_stock_pct, np.nan
    )

    def _risk(row):
        unmatched = pd.isna(row["Supplier"])
        if unmatched or not row["Has_Target"]:
            return "Review"
        if row["Projected_Balance"] < 0:
            return "Critical"
        if row["Projected_Balance"] < row["Safety_Stock"]:
            return "At Risk"
        return "Covered"

    grid["Risk_Status"] = grid.apply(_risk, axis=1)
    return grid


def apply_manual_overrides(grid: pd.DataFrame, overrides_df: pd.DataFrame, safety_stock_pct: float) -> pd.DataFrame:
    """Merge session-only planner overrides/notes into the grid and
    recompute the fields that depend on Manual_Override."""
    if overrides_df.empty:
        return grid
    grid = grid.merge(
        overrides_df.rename(columns={"Manual_Override": "Manual_Override_new", "Planner_Note": "Planner_Note_new"}),
        on=["Plant", "Material"], how="left",
    )
    grid["Manual_Override"] = grid["Manual_Override_new"].combine_first(grid["Manual_Override"])
    grid["Planner_Note"] = grid["Planner_Note_new"].combine_first(grid["Planner_Note"])
    grid = grid.drop(columns=["Manual_Override_new", "Planner_Note_new"])
    return recompute_suggested_and_risk(grid, safety_stock_pct)
