import math

import pandas as pd

from src.aggregate import (
    aggregate_on_hand, aggregate_customer_orders, aggregate_open_orders,
    build_ordering_dashboard, apply_manual_overrides,
)


def test_on_hand_sums_unrestricted_stock_by_plant_material(on_hand_df):
    out = aggregate_on_hand(on_hand_df)
    row = out[(out["Plant"] == "2910") & (out["Material"] == "10013700")].iloc[0]
    assert row["Unrestricted_On_Hand"] == 50  # 40 + 10


def test_on_hand_sums_quality_inspection_by_plant_material(on_hand_df):
    out = aggregate_on_hand(on_hand_df)
    row = out[(out["Plant"] == "2910") & (out["Material"] == "10013700")].iloc[0]
    assert row["Quality_Inspection_Qty"] == 2


def test_on_hand_sums_blocked_stock_by_plant_material(on_hand_df):
    out = aggregate_on_hand(on_hand_df)
    row = out[(out["Plant"] == "2910") & (out["Material"] == "10013700")].iloc[0]
    assert row["Blocked_Stock_Qty"] == 1


def test_earliest_expiry_is_min_non_null(on_hand_df):
    out = aggregate_on_hand(on_hand_df)
    row = out[(out["Plant"] == "2910") & (out["Material"] == "10013700")].iloc[0]
    assert row["Earliest_Expiry_Date"] == pd.Timestamp("2026-06-01")


def test_composite_key_never_merges_across_plants(on_hand_df):
    out = aggregate_on_hand(on_hand_df)
    row_2920 = out[(out["Plant"] == "2920") & (out["Material"] == "10013700")].iloc[0]
    assert row_2920["Unrestricted_On_Hand"] == 5  # not summed with plant 2910's 50


def test_customer_order_qty_summed_by_plant_material(customer_orders_df):
    out = aggregate_customer_orders(customer_orders_df)
    row = out[(out["Plant"] == "2910") & (out["Material"] == "10013700")].iloc[0]
    assert row["Customer_Order_Qty"] == 15  # 10 + 5


def test_confirmed_qty_summed_by_plant_material(customer_orders_df):
    out = aggregate_customer_orders(customer_orders_df)
    row = out[(out["Plant"] == "2910") & (out["Material"] == "10013700")].iloc[0]
    assert row["Confirmed_Qty"] == 13  # 8 + 5


def test_unconfirmed_qty_is_max_zero(customer_orders_df):
    out = aggregate_customer_orders(customer_orders_df)
    row = out[(out["Plant"] == "2910") & (out["Material"] == "10013700")].iloc[0]
    assert row["Unconfirmed_Qty"] == 2  # 15 - 13

    # fully-confirmed-or-over-confirmed rows never go negative
    row2 = out[(out["Plant"] == "2910") & (out["Material"] == "10099999")].iloc[0]
    assert row2["Unconfirmed_Qty"] == 0


def test_open_po_qty_summed_by_plant_material(open_orders_df):
    out = aggregate_open_orders(open_orders_df, {"2910": "PO Quantity", "2920": "PO Request Quantity"})
    row = out[(out["Plant"] == "2910") & (out["Material"] == "10013700")].iloc[0]
    assert row["Open_PO_Qty"] == 12


def test_inbound_delivery_qty_summed(open_orders_df):
    out = aggregate_open_orders(open_orders_df, {"2910": "PO Quantity", "2920": "PO Request Quantity"})
    row = out[(out["Plant"] == "2920") & (out["Material"] == "10013700")].iloc[0]
    assert row["Inbound_Delivery_Qty"] == 2


def test_next_po_delivery_date_is_min(open_orders_df):
    out = aggregate_open_orders(open_orders_df, {"2910": "PO Quantity", "2920": "PO Request Quantity"})
    row = out[(out["Plant"] == "2910") & (out["Material"] == "10013700")].iloc[0]
    assert row["Next_PO_Delivery_Date"] == pd.Timestamp("2026-09-01")


def test_allocation_qty_uses_po_quantity_for_plant_2910(open_orders_df):
    out = aggregate_open_orders(open_orders_df, {"2910": "PO Quantity", "2920": "PO Request Quantity"})
    row = out[(out["Plant"] == "2910") & (out["Material"] == "10013700")].iloc[0]
    assert row["Allocation_Qty"] == 12  # PO Quantity, not PO Request Quantity


def test_allocation_qty_uses_po_request_quantity_for_plant_2920(open_orders_df):
    out = aggregate_open_orders(open_orders_df, {"2910": "PO Quantity", "2920": "PO Request Quantity"})
    row = out[(out["Plant"] == "2920") & (out["Material"] == "10013700")].iloc[0]
    assert row["Allocation_Qty"] == 6  # PO Request Quantity, not PO Quantity (8)


def test_available_plus_incoming_and_projected_balance(
    on_hand_df, customer_orders_df, open_orders_df, target_stock_df, allocation_field_by_plant,
):
    grid = build_ordering_dashboard(
        on_hand_df, customer_orders_df, open_orders_df, target_stock_df,
        allocation_field_by_plant, safety_stock_pct=0.20,
    )
    row = grid[(grid["Plant"] == "2910") & (grid["Material"] == "10013700")].iloc[0]
    assert row["Available_Plus_Incoming"] == 62  # 50 on-hand + 12 open PO
    assert row["Projected_Balance"] == 47  # 62 - 15 customer order qty


def test_suggested_order_qty_when_target_present(
    on_hand_df, customer_orders_df, open_orders_df, target_stock_df, allocation_field_by_plant,
):
    grid = build_ordering_dashboard(
        on_hand_df, customer_orders_df, open_orders_df, target_stock_df,
        allocation_field_by_plant, safety_stock_pct=0.20,
    )
    row = grid[(grid["Plant"] == "2910") & (grid["Material"] == "10013700")].iloc[0]
    # max(50 target - 62 available+incoming + 2 unconfirmed + 0 override, 0) = 0
    assert row["Suggested_Order_Qty"] == 0
    assert row["Risk_Status"] == "Covered"  # projected balance 47 >= safety stock 10


def test_suggested_order_qty_blank_when_target_missing(
    on_hand_df, customer_orders_df, open_orders_df, target_stock_df, allocation_field_by_plant,
):
    grid = build_ordering_dashboard(
        on_hand_df, customer_orders_df, open_orders_df, target_stock_df,
        allocation_field_by_plant, safety_stock_pct=0.20,
    )
    row = grid[(grid["Plant"] == "2910") & (grid["Material"] == "10099999")].iloc[0]
    assert math.isnan(row["Suggested_Order_Qty"])
    assert row["Risk_Status"] == "Review"


def test_suggested_order_qty_rounds_up_to_whole_case(
    on_hand_df, customer_orders_df, open_orders_df, allocation_field_by_plant,
):
    target = pd.DataFrame([
        {"Plant": "2910", "Material": "10013700", "Supplier": "Alimentias",
         "TOL_Material": "13700", "Description": "TEST", "Target_Stock": 65.4},
    ])
    grid = build_ordering_dashboard(
        on_hand_df, customer_orders_df, open_orders_df, target,
        allocation_field_by_plant, safety_stock_pct=0.20,
    )
    row = grid[(grid["Plant"] == "2910") & (grid["Material"] == "10013700")].iloc[0]
    # max(65.4 - 62 + 2 + 0, 0) = 5.4 -> ceil -> 6
    assert row["Suggested_Order_Qty"] == 6


def test_critical_status_when_projected_balance_negative(
    on_hand_df, customer_orders_df, open_orders_df, allocation_field_by_plant,
):
    huge_orders = customer_orders_df.copy()
    huge_orders.loc[huge_orders["Material"] == "10013700", "Order Quantity"] = 9999
    target = pd.DataFrame([
        {"Plant": "2910", "Material": "10013700", "Supplier": "Alimentias",
         "TOL_Material": "13700", "Description": "TEST", "Target_Stock": 10},
    ])
    grid = build_ordering_dashboard(
        on_hand_df, huge_orders, open_orders_df, target,
        allocation_field_by_plant, safety_stock_pct=0.20,
    )
    row = grid[(grid["Plant"] == "2910") & (grid["Material"] == "10013700")].iloc[0]
    assert row["Risk_Status"] == "Critical"


def test_manual_override_reduces_suggested_order_qty(
    on_hand_df, customer_orders_df, open_orders_df, allocation_field_by_plant,
):
    target = pd.DataFrame([
        {"Plant": "2910", "Material": "10013700", "Supplier": "Alimentias",
         "TOL_Material": "13700", "Description": "TEST", "Target_Stock": 100},
    ])
    grid = build_ordering_dashboard(
        on_hand_df, customer_orders_df, open_orders_df, target,
        allocation_field_by_plant, safety_stock_pct=0.20,
    )
    baseline = grid[(grid["Plant"] == "2910") & (grid["Material"] == "10013700")].iloc[0]["Suggested_Order_Qty"]

    overrides = pd.DataFrame([{"Plant": "2910", "Material": "10013700", "Manual_Override": -20, "Planner_Note": "test"}])
    adjusted = apply_manual_overrides(grid, overrides, safety_stock_pct=0.20)
    row = adjusted[(adjusted["Plant"] == "2910") & (adjusted["Material"] == "10013700")].iloc[0]

    assert row["Suggested_Order_Qty"] == baseline - 20
    assert row["Planner_Note"] == "test"
