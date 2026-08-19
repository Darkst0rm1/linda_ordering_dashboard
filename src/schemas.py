"""Exact column schemas for the nine SAP exports, and header validation.

Every input uses sheet "SAPUI5 Export". Headers must match exactly -- same
names, same order, no renames, no missing/extra columns -- per the build
instructions.
"""
from __future__ import annotations

from dataclasses import dataclass, field

SHEET_NAME = "SAPUI5 Export"

CUSTOMER_ORDERS_COLUMNS: list[str] = [
    "Plant", "Sales Order", "Sales Order Type Desc.", "Sold To Name", "Material",
    "TOL Material Description", "Order Quantity", "Confirmed Quantity (CS)",
    "Reason for Rejection Desc.", "Picked Quantity (CS)", "Picked Quantity (KG)",
    "Invoice Quantity (CS)", "Invoice Quantity (KG)", "Item Net Amount",
    "Outbound Delivery #", "Outbound Delivery Status", "BBD / Shelf Life",
    "Item Net Amount (Confirmed)", "Requested Delivery Date", "Ship to Arrive Date",
    "Appointment Confirmation", "Shipped Date", "Vendor", "Vendor Name",
    "Material Group Description", "Purchasing Group", "Purchasing Group Name",
    "BDM Description", "CDM Name", "Credit Check Status", "Credit Check Status Desc.",
]

ON_HAND_COLUMNS: list[str] = [
    "Material", "Material Description", "Plant", "Plant Name", "Storage Location",
    "Stock in Quality Inspection", "Unrestricted Stock", "Batch", "Blocked Stock",
    "Production Date", "Shelf Life Expiration Date",
]

OPEN_ORDERS_COLUMNS: list[str] = [
    "Material", "PO Number", "Open PO Qty", "PO Quantity", "PO Request Quantity",
    "PO Received Qty", "Inbound Delivery Quantity", "Company Code", "Vendor",
    "Vendor Name", "Supplier", "Supplier Name", "Delivery Date", "Est PU Date",
    "Plant", "SLOC", "Material Description", "Material Group", "Delivery Completed",
    "Created On Date", "Appt. Plant", "Gross Weight", "Appt. Date", "Appt. Time",
    "Delivery Date Derived Field", "Delivery Priority Text", "Inbound Delivery Status",
    "STO/CD Pro #",
]

DATASET_KINDS = ("customer_orders", "on_hand", "open_orders")
PLANTS = ("2910", "2920", "2930")

# Upload -> (dataset kind, plant)
UPLOAD_FILE_MAP: dict[str, tuple[str, str]] = {
    "2910Customerorders.xlsx": ("customer_orders", "2910"),
    "2920CustomerOrders.xlsx": ("customer_orders", "2920"),
    "2930Customerorders.xlsx": ("customer_orders", "2930"),
    "OH2910.xlsx": ("on_hand", "2910"),
    "OH20.xlsx": ("on_hand", "2920"),  # plant 2920 on-hand data
    "OH2930.xlsx": ("on_hand", "2930"),
    "OR2910.xlsx": ("open_orders", "2910"),
    "OR2920.xlsx": ("open_orders", "2920"),
    "OR2930.xlsx": ("open_orders", "2930"),
}

REQUIRED_UPLOADS = list(UPLOAD_FILE_MAP.keys())

COLUMNS_BY_KIND: dict[str, list[str]] = {
    "customer_orders": CUSTOMER_ORDERS_COLUMNS,
    "on_hand": ON_HAND_COLUMNS,
    "open_orders": OPEN_ORDERS_COLUMNS,
}


@dataclass
class SchemaValidationResult:
    ok: bool
    expected_columns: list[str] = field(default_factory=list)
    received_columns: list[str] = field(default_factory=list)
    missing_columns: list[str] = field(default_factory=list)
    extra_columns: list[str] = field(default_factory=list)
    reordered: bool = False
    message: str = ""


def validate_columns(kind: str, received_columns: list[str]) -> SchemaValidationResult:
    """Reject missing, duplicated, renamed, or reordered headers.

    Returns a friendly, structured result showing expected vs received so
    the UI can render a clear diff instead of a raw exception.
    """
    expected = COLUMNS_BY_KIND[kind]
    received = list(received_columns)

    missing = [c for c in expected if c not in received]
    extra = [c for c in received if c not in expected]
    duplicated = [c for c in set(received) if received.count(c) > 1]

    if missing or extra or duplicated:
        parts = []
        if missing:
            parts.append(f"missing columns: {missing}")
        if extra:
            parts.append(f"unexpected columns: {extra}")
        if duplicated:
            parts.append(f"duplicated columns: {duplicated}")
        return SchemaValidationResult(
            ok=False,
            expected_columns=expected,
            received_columns=received,
            missing_columns=missing,
            extra_columns=extra,
            message="Schema mismatch -- " + "; ".join(parts),
        )

    if received != expected:
        return SchemaValidationResult(
            ok=False,
            expected_columns=expected,
            received_columns=received,
            reordered=True,
            message="Columns present but reordered relative to the expected schema.",
        )

    return SchemaValidationResult(
        ok=True,
        expected_columns=expected,
        received_columns=received,
        message="Schema OK.",
    )
