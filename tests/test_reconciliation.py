import pandas as pd

from src.aggregate import build_ordering_dashboard
from src.loaders import LoadResult
from src.reconciliation import build_reconciliation_report, count_duplicate_rows, unmatched_materials


def test_duplicate_rows_are_counted_not_removed():
    df = pd.DataFrame([
        {"a": 1, "b": 2}, {"a": 1, "b": 2}, {"a": 3, "b": 4},
    ])
    assert count_duplicate_rows(df) == 2
    assert len(df) == 3  # never mutated/dropped


def test_unmatched_materials_detects_source_only_keys():
    source = pd.DataFrame([
        {"Plant": "2910", "Material": "A"},
        {"Plant": "2910", "Material": "B"},
    ])
    master_keys = {("2910", "A")}
    out = unmatched_materials(source, master_keys)
    assert list(out["Material"]) == ["B"]


def test_reconciliation_report_zero_variance_when_grid_built_from_same_frames(
    on_hand_df, customer_orders_df, open_orders_df, target_stock_df, allocation_field_by_plant,
):
    grid = build_ordering_dashboard(
        on_hand_df, customer_orders_df, open_orders_df, target_stock_df,
        allocation_field_by_plant, safety_stock_pct=0.20,
    )
    raw_frames = {
        "on_hand": on_hand_df, "customer_orders": customer_orders_df, "open_orders": open_orders_df,
    }
    load_results = {
        "OH2910.xlsx": LoadResult(filename="OH2910.xlsx", kind="on_hand", expected_plant="2910", status="Valid", row_count=len(on_hand_df)),
    }
    report = build_reconciliation_report(raw_frames, load_results, grid, target_stock_df)
    assert report.all_variances_zero


def test_reconciliation_report_nonzero_variance_detected(
    on_hand_df, customer_orders_df, open_orders_df, target_stock_df, allocation_field_by_plant,
):
    grid = build_ordering_dashboard(
        on_hand_df, customer_orders_df, open_orders_df, target_stock_df,
        allocation_field_by_plant, safety_stock_pct=0.20,
    )
    grid.loc[0, "Unrestricted_On_Hand"] += 1000  # deliberately corrupt the grid total
    raw_frames = {
        "on_hand": on_hand_df, "customer_orders": customer_orders_df, "open_orders": open_orders_df,
    }
    report = build_reconciliation_report(raw_frames, {}, grid, target_stock_df)
    assert not report.all_variances_zero


def test_materials_in_master_with_no_activity_reported(
    on_hand_df, customer_orders_df, open_orders_df, allocation_field_by_plant,
):
    target = pd.DataFrame([
        {"Plant": "2910", "Material": "10013700", "Supplier": "Alimentias",
         "TOL_Material": "13700", "Description": "TEST", "Target_Stock": 50},
        {"Plant": "2930", "Material": "NEVER-SEEN", "Supplier": "Alimentias",
         "TOL_Material": "99999", "Description": "UNUSED", "Target_Stock": 10},
    ])
    grid = build_ordering_dashboard(
        on_hand_df, customer_orders_df, open_orders_df, target,
        allocation_field_by_plant, safety_stock_pct=0.20,
    )
    raw_frames = {
        "on_hand": on_hand_df, "customer_orders": customer_orders_df, "open_orders": open_orders_df,
    }
    report = build_reconciliation_report(raw_frames, {}, grid, target)
    keys = [(m["Plant"], m["Material"]) for m in report.materials_in_master_no_activity]
    assert ("2930", "NEVER-SEEN") in keys
