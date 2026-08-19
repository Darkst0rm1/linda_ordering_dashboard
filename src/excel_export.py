"""Build the Export Center's .xlsx workbook with XlsxWriter.

Hard requirements from the build instructions:
 - a new, clean workbook (never edits the reference workbook)
 - opens without repair warnings
 - formatted Excel Tables + static values for source-backed summaries
 - formulas only where simple, portable, auditable
 - no PivotTables, no external links
 - freeze panes, autofilters, sensible/capped widths, wrapped headers,
   conditional formatting, date formats, integer formats, consistent
   supplier colors
"""
from __future__ import annotations

import io
from datetime import datetime

import pandas as pd
import xlsxwriter

from src.product_master import load_suppliers_config

MAX_COL_WIDTH = 40
MIN_COL_WIDTH = 10

DASHBOARD_COLUMNS = [
    "Supplier", "Plant", "Material", "TOL_Material", "Description",
    "Target_Stock", "Customer_Order_Qty", "Confirmed_Qty", "Unconfirmed_Qty",
    "Unrestricted_On_Hand", "Open_PO_Qty", "Allocation_Qty", "Inbound_Delivery_Qty",
    "Available_Plus_Incoming", "Projected_Balance", "Suggested_Order_Qty",
    "Risk_Status", "Next_PO_Delivery_Date", "Earliest_Expiry_Date",
]

DASHBOARD_HEADER_LABELS = {
    "Material": "SAP Material",
    "TOL_Material": "TOL Material",
    "Target_Stock": "Target Stock (Forecast Baseline)",
    "Customer_Order_Qty": "Customer Order Qty",
    "Confirmed_Qty": "Confirmed Qty",
    "Unconfirmed_Qty": "Unconfirmed Qty",
    "Unrestricted_On_Hand": "Unrestricted On Hand",
    "Open_PO_Qty": "Open PO Qty",
    "Allocation_Qty": "Allocation Qty (plant policy)",
    "Inbound_Delivery_Qty": "Inbound Delivery Qty",
    "Available_Plus_Incoming": "Available + Incoming",
    "Projected_Balance": "Projected Balance",
    "Suggested_Order_Qty": "Suggested Order Qty",
    "Risk_Status": "Risk / Status",
    "Next_PO_Delivery_Date": "Next PO Delivery Date",
    "Earliest_Expiry_Date": "Earliest Expiry Date",
}

DATE_COLUMNS = {"Next_PO_Delivery_Date", "Earliest_Expiry_Date"}
INT_COLUMNS = {
    "Target_Stock", "Customer_Order_Qty", "Confirmed_Qty", "Unconfirmed_Qty",
    "Unrestricted_On_Hand", "Open_PO_Qty", "Allocation_Qty", "Inbound_Delivery_Qty",
    "Available_Plus_Incoming", "Projected_Balance", "Suggested_Order_Qty",
}

STATUS_COLORS = {
    "Critical": "#DC2626", "At Risk": "#D97706", "Review": "#2563EB", "Covered": "#16A34A",
}


def _safe_sheet_name(name: str) -> str:
    return name[:31]


def _col_width(series: pd.Series, header: str) -> float:
    try:
        max_len = max([len(header)] + [len(str(v)) for v in series.dropna().astype(str).head(200)])
    except Exception:
        max_len = len(header)
    return min(max(max_len + 2, MIN_COL_WIDTH), MAX_COL_WIDTH)


def _write_table(workbook, sheet_name, df: pd.DataFrame, formats, header_labels=None,
                  date_cols=(), int_cols=(), status_col=None, freeze=(1, 0)):
    header_labels = header_labels or {}
    ws = workbook.add_worksheet(_safe_sheet_name(sheet_name))
    n_rows, n_cols = df.shape

    if n_rows == 0:
        ws.write(0, 0, "(no rows)")
        return ws

    for c, col in enumerate(df.columns):
        ws.write(0, c, header_labels.get(col, col), formats["header"])
        ws.set_column(c, c, _col_width(df[col], header_labels.get(col, col)))

    for r in range(n_rows):
        for c, col in enumerate(df.columns):
            val = df.iloc[r, c]
            if pd.isna(val):
                ws.write_blank(r + 1, c, None)
                continue
            if col in date_cols:
                if isinstance(val, (pd.Timestamp, datetime)):
                    ws.write_datetime(r + 1, c, val, formats["date"])
                else:
                    ws.write(r + 1, c, val)
            elif col in int_cols:
                ws.write_number(r + 1, c, float(val), formats["integer"])
            else:
                ws.write(r + 1, c, val)

    ws.add_table(0, 0, n_rows, n_cols - 1, {
        "columns": [{"header": header_labels.get(c, c)} for c in df.columns],
        "style": "Table Style Medium 2",
        "autofilter": True,
    })
    ws.freeze_panes(*freeze)

    if status_col and status_col in df.columns:
        status_idx = list(df.columns).index(status_col)
        for status, color in STATUS_COLORS.items():
            ws.conditional_format(1, status_idx, n_rows, status_idx, {
                "type": "text", "criteria": "containing", "value": status,
                "format": workbook.add_format({"bg_color": color, "font_color": "#FFFFFF"}),
            })
    return ws


def _base_formats(workbook):
    return {
        "header": workbook.add_format({
            "bold": True, "text_wrap": True, "valign": "top",
            "bg_color": "#1F2937", "font_color": "#FFFFFF", "border": 1,
        }),
        "date": workbook.add_format({"num_format": "yyyy-mm-dd"}),
        "integer": workbook.add_format({"num_format": "#,##0"}),
        "title": workbook.add_format({"bold": True, "font_size": 16}),
        "subtitle": workbook.add_format({"italic": True, "font_color": "#6B7280"}),
        "kpi_label": workbook.add_format({"bold": True, "bg_color": "#F3F4F6", "border": 1}),
        "kpi_value": workbook.add_format({"num_format": "#,##0", "border": 1}),
        "wrap": workbook.add_format({"text_wrap": True, "valign": "top"}),
    }


def _write_executive_summary(workbook, formats, dashboard_grid: pd.DataFrame, refresh_ts_str: str, reconciliation_ok: bool):
    ws = workbook.add_worksheet(_safe_sheet_name("Executive Summary"))
    ws.set_column(0, 0, 32)
    ws.set_column(1, 1, 20)
    ws.write(0, 0, "Linda Ordering Dashboard -- Executive Summary", formats["title"])
    ws.write(1, 0, f"Refreshed: {refresh_ts_str} (America/Toronto)", formats["subtitle"])
    ws.write(2, 0, f"Reconciliation status: {'PASS -- all variances zero' if reconciliation_ok else 'FAIL -- see Reconciliation sheet'}", formats["subtitle"])

    kpis = [
        ("Active materials", dashboard_grid[["Plant", "Material"]].drop_duplicates().shape[0]),
        ("Total unrestricted on-hand", dashboard_grid["Unrestricted_On_Hand"].sum()),
        ("Total open PO quantity", dashboard_grid["Open_PO_Qty"].sum()),
        ("Total customer-order quantity", dashboard_grid["Customer_Order_Qty"].sum()),
        ("Total confirmed customer-order quantity", dashboard_grid["Confirmed_Qty"].sum()),
        ("Unconfirmed quantity", dashboard_grid["Unconfirmed_Qty"].sum()),
        ("Materials at risk (Critical + At Risk)", int(dashboard_grid["Risk_Status"].isin(["Critical", "At Risk"]).sum())),
        ("Suggested order quantity (total)", dashboard_grid["Suggested_Order_Qty"].fillna(0).sum()),
    ]
    r = 4
    ws.write(r, 0, "KPI", formats["header"])
    ws.write(r, 1, "Value", formats["header"])
    for label, value in kpis:
        r += 1
        ws.write(r, 0, label, formats["kpi_label"])
        ws.write_number(r, 1, float(value), formats["kpi_value"])

    r += 3
    ws.write(r, 0, "Materials by Risk / Status", formats["header"])
    r += 1
    for status, count in dashboard_grid["Risk_Status"].value_counts().items():
        ws.write(r, 0, status)
        ws.write_number(r, 1, int(count))
        r += 1


def _write_reconciliation(workbook, formats, report):
    ws = workbook.add_worksheet(_safe_sheet_name("Reconciliation"))
    ws.set_column(0, 0, 34)
    ws.set_column(1, 3, 18)
    r = 0
    ws.write(r, 0, "Grand Total Reconciliation", formats["title"])
    r += 2
    ws.write(r, 0, "Metric", formats["header"])
    ws.write(r, 1, "Source total", formats["header"])
    ws.write(r, 2, "Dashboard total", formats["header"])
    ws.write(r, 3, "Variance", formats["header"])
    for key, variance in report.grand_total_variances.items():
        r += 1
        ws.write(r, 0, key)
        ws.write_number(r, 1, report.source_grand_totals[key])
        ws.write_number(r, 2, report.dashboard_grand_totals[key])
        ws.write_number(r, 3, variance)

    r += 3
    ws.write(r, 0, "Duplicate row counts (rows preserved, not deleted)", formats["header"])
    for kind, count in report.duplicate_row_counts.items():
        r += 1
        ws.write(r, 0, kind)
        ws.write_number(r, 1, count)

    r += 3
    ws.write(r, 0, "File / schema validation", formats["header"])
    for filename, info in report.file_validation.items():
        r += 1
        ws.write(r, 0, filename)
        ws.write(r, 1, info["status"])
        ws.write(r, 2, info.get("error") or "")


def _write_unmatched_materials(workbook, formats, report):
    rows = []
    for kind, materials in report.unmatched_materials_by_source.items():
        for m in materials:
            rows.append({"Source": kind, "Plant": m["Plant"], "Material": m["Material"], "Reason": "In SAP source, not in product master"})
    for m in report.materials_in_master_no_activity:
        rows.append({"Source": "product_master", "Plant": m["Plant"], "Material": m["Material"], "Reason": "In product master, no current SAP activity"})
    df = pd.DataFrame(rows, columns=["Source", "Plant", "Material", "Reason"])
    _write_table(workbook, "Unmatched Materials", df, formats)


def _write_data_dictionary(workbook, formats):
    entries = [
        ("Target_Stock", "Most recently populated 'Forecast AS400' value for this Plant+Material in the reference workbook's supplier sheet. Blank when no product-master match exists -- Risk/Status is then 'Review' ('Needs planner target')."),
        ("Allocation_Qty", "Plant-specific open-order allocation quantity: PO Quantity for plant 2910; PO Request Quantity for plants 2920 and 2930 (business_rules.yaml)."),
        ("Available_Plus_Incoming", "Unrestricted On Hand + Open PO Qty."),
        ("Projected_Balance", "Available + Incoming - Customer Order Qty."),
        ("Suggested_Order_Qty", "max(Target Stock - Available - Incoming + Unconfirmed Demand + Manual Override, 0), rounded up to a whole case. Blank when Target Stock is unavailable."),
        ("Risk_Status", "Critical: Projected Balance < 0. At Risk: 0 <= Projected Balance < Safety Stock. Review: missing target or unmatched material. Covered: Projected Balance >= Safety Stock."),
        ("Safety Stock", "20% of Target Stock (config/business_rules.yaml: safety_stock.percent_of_target_stock) -- no safety-stock field exists in any supplied source."),
        ("Manual Override", "Planner-entered adjustment from the Supplier Detail page, session-only (not persisted to a database)."),
        ("#REF! formulas", "1,952 broken formulas exist in the reference workbook. None were translated into dashboard logic -- see config/reference_workbook_audit.json and config/product_master_extraction_audit.json."),
    ]
    df = pd.DataFrame(entries, columns=["Field", "Definition"])
    ws = _write_table(workbook, "Data Dictionary", df, formats)
    ws.set_column(0, 0, 24)
    ws.set_column(1, 1, 90)


def build_export_workbook(
    dashboard_grid: pd.DataFrame,
    raw_frames: dict[str, pd.DataFrame],
    reconciliation_report,
    refresh_ts_str: str,
) -> bytes:
    suppliers_cfg = load_suppliers_config()
    supplier_order = [s["display_name"] for s in suppliers_cfg["suppliers"]]

    buf = io.BytesIO()
    workbook = xlsxwriter.Workbook(buf, {"in_memory": True})
    formats = _base_formats(workbook)

    _write_executive_summary(workbook, formats, dashboard_grid, refresh_ts_str, reconciliation_report.all_variances_zero)

    dash_export = dashboard_grid[[c for c in DASHBOARD_COLUMNS if c in dashboard_grid.columns]]
    _write_table(workbook, "Ordering Dashboard", dash_export, formats,
                 header_labels=DASHBOARD_HEADER_LABELS, date_cols=DATE_COLUMNS,
                 int_cols=INT_COLUMNS, status_col="Risk_Status")

    for supplier in supplier_order:
        subset = dash_export[dash_export["Supplier"] == supplier]
        _write_table(workbook, supplier, subset, formats,
                     header_labels=DASHBOARD_HEADER_LABELS, date_cols=DATE_COLUMNS,
                     int_cols=INT_COLUMNS, status_col="Risk_Status")

    _write_reconciliation(workbook, formats, reconciliation_report)
    _write_unmatched_materials(workbook, formats, reconciliation_report)

    plant_names = {"2910": "2910", "2920": "2920", "2930": "2930"}
    kind_labels = {"customer_orders": "Customer Orders", "on_hand": "On Hand", "open_orders": "Open Orders"}
    for kind, label in kind_labels.items():
        df = raw_frames.get(kind)
        if df is None:
            continue
        for plant in ["2910", "2920", "2930"]:
            subset = df[df["Plant"] == plant]
            date_cols = {c for c in subset.columns if "Date" in c or "BBD" in c}
            _write_table(workbook, f"{label} {plant}", subset, formats, date_cols=date_cols)

    _write_data_dictionary(workbook, formats)

    workbook.close()
    return buf.getvalue()


def build_audit_report_text(reconciliation_report, refresh_ts_str: str) -> str:
    lines = [
        "LINDA ORDERING DASHBOARD -- AUDIT REPORT",
        f"Refreshed: {refresh_ts_str} (America/Toronto)",
        f"Reconciliation: {'PASS' if reconciliation_report.all_variances_zero else 'FAIL'}",
        "",
        "-- Grand total variances --",
    ]
    for key, variance in reconciliation_report.grand_total_variances.items():
        lines.append(f"  {key}: source={reconciliation_report.source_grand_totals[key]:,.2f} "
                      f"dashboard={reconciliation_report.dashboard_grand_totals[key]:,.2f} "
                      f"variance={variance:,.2f}")

    lines += ["", "-- Duplicate row counts (preserved, not deleted) --"]
    for kind, count in reconciliation_report.duplicate_row_counts.items():
        lines.append(f"  {kind}: {count}")

    lines += ["", "-- File / schema validation --"]
    for filename, info in reconciliation_report.file_validation.items():
        lines.append(f"  {filename}: {info['status']}" + (f" -- {info['error']}" if info.get("error") else ""))

    lines += ["", "-- Unmatched materials --"]
    for kind, materials in reconciliation_report.unmatched_materials_by_source.items():
        lines.append(f"  {kind}: {len(materials)} material(s) in source not in product master")
    lines.append(f"  product_master: {len(reconciliation_report.materials_in_master_no_activity)} material(s) with no current SAP activity")

    ref_audit = reconciliation_report.reference_workbook_audit
    if ref_audit:
        lines += [
            "", "-- Reference workbook audit --",
            f"  Sheets: {ref_audit.get('total_sheets')}",
            f"  Formulas: {ref_audit.get('total_formulas')}",
            f"  #REF! error formulas (never translated into dashboard logic): {ref_audit.get('total_ref_error_formulas')}",
        ]

    return "\n".join(lines)
