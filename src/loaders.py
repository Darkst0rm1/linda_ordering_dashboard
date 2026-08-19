"""Load and validate the nine SAP export uploads.

Every input uses sheet "SAPUI5 Export". Results are cached by file content
hash (never by the uploaded file object itself, which is not hashable in a
stable way across reruns).
"""
from __future__ import annotations

import hashlib
import io
from dataclasses import dataclass, field

import pandas as pd
import streamlit as st

from src.schemas import SHEET_NAME, UPLOAD_FILE_MAP, COLUMNS_BY_KIND, validate_columns
from src.normalize import normalize_identifier_series, normalize_plant

STATUS_MISSING = "Missing"
STATUS_VALIDATING = "Validating"
STATUS_VALID = "Valid"
STATUS_ERROR = "Error"

IDENTIFIER_COLUMNS_BY_KIND = {
    "customer_orders": {"Plant", "Sales Order", "Material", "Vendor", "Outbound Delivery #"},
    "on_hand": {"Plant", "Material", "Batch"},
    "open_orders": {"Plant", "Material", "PO Number", "Vendor", "Supplier"},
}

DATE_COLUMNS_BY_KIND = {
    "customer_orders": [
        "BBD / Shelf Life", "Requested Delivery Date", "Ship to Arrive Date", "Shipped Date",
    ],
    "on_hand": ["Production Date", "Shelf Life Expiration Date"],
    "open_orders": [
        "Delivery Date", "Est PU Date", "Created On Date", "Appt. Date",
        "Delivery Date Derived Field",
    ],
}

NUMERIC_COLUMNS_BY_KIND = {
    "customer_orders": [
        "Order Quantity", "Confirmed Quantity (CS)", "Picked Quantity (CS)",
        "Picked Quantity (KG)", "Invoice Quantity (CS)", "Invoice Quantity (KG)",
        "Item Net Amount", "Item Net Amount (Confirmed)",
    ],
    "on_hand": ["Stock in Quality Inspection", "Unrestricted Stock", "Blocked Stock"],
    "open_orders": [
        "Open PO Qty", "PO Quantity", "PO Request Quantity", "PO Received Qty",
        "Inbound Delivery Quantity", "Gross Weight",
    ],
}


@dataclass
class LoadResult:
    filename: str
    kind: str
    expected_plant: str
    status: str
    row_count: int = 0
    dataframe: pd.DataFrame | None = None
    schema_message: str = ""
    plant_violations: list[str] = field(default_factory=list)
    error: str | None = None
    file_hash: str = ""


def hash_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


@st.cache_data(show_spinner=False)
def _parse_sap_export(file_bytes: bytes, filename: str) -> dict:
    """Cached by content hash (file_bytes) + filename. Returns a plain dict
    (not a dataclass) because st.cache_data needs a hashable/serializable
    return shape; the caller reassembles a LoadResult."""
    kind, expected_plant = UPLOAD_FILE_MAP[filename]

    try:
        raw = pd.read_excel(io.BytesIO(file_bytes), sheet_name=SHEET_NAME, dtype=object)
    except ValueError as exc:
        return {"error": f"Could not read sheet '{SHEET_NAME}': {exc}"}
    except Exception as exc:  # pragma: no cover - defensive
        return {"error": f"Could not read workbook: {exc}"}

    received_columns = [str(c) for c in raw.columns]
    validation = validate_columns(kind, received_columns)
    if not validation.ok:
        return {
            "error": validation.message,
            "expected_columns": validation.expected_columns,
            "received_columns": validation.received_columns,
        }

    df = raw.copy()

    for col in df.columns:
        if col in IDENTIFIER_COLUMNS_BY_KIND.get(kind, set()):
            df[col] = normalize_identifier_series(df[col])

    for col in DATE_COLUMNS_BY_KIND.get(kind, []):
        if col in df.columns:
            df[col] = pd.to_datetime(df[col], errors="coerce")

    for col in NUMERIC_COLUMNS_BY_KIND.get(kind, []):
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    plant_col = "Plant"
    plant_values = df[plant_col].map(normalize_plant)
    violations = sorted(set(v for v in plant_values.dropna().unique() if v != expected_plant))

    return {
        "dataframe": df,
        "row_count": len(df),
        "plant_violations": violations,
    }


def load_upload(filename: str, file_bytes: bytes) -> LoadResult:
    kind, expected_plant = UPLOAD_FILE_MAP[filename]
    file_hash = hash_bytes(file_bytes)

    result = _parse_sap_export(file_bytes, filename)

    if "error" in result:
        return LoadResult(
            filename=filename,
            kind=kind,
            expected_plant=expected_plant,
            status=STATUS_ERROR,
            error=result["error"],
            file_hash=file_hash,
        )

    status = STATUS_VALID
    if result["plant_violations"]:
        status = STATUS_ERROR

    return LoadResult(
        filename=filename,
        kind=kind,
        expected_plant=expected_plant,
        status=status,
        row_count=result["row_count"],
        dataframe=result["dataframe"],
        plant_violations=result["plant_violations"],
        file_hash=file_hash,
        error=(
            f"Plant column contains unexpected value(s) {result['plant_violations']} "
            f"for a file mapped to plant {expected_plant}."
            if result["plant_violations"] else None
        ),
    )
