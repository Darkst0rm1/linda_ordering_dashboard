"""Identifier and value normalization shared by every loader.

Rules from the build instructions:
 - treat SAP identifiers as strings
 - strip whitespace
 - strip a trailing ".0" only when caused by Excel numeric coercion
 - preserve source duplicates and source row order in raw exports
"""
from __future__ import annotations

import re

import pandas as pd

_TRAILING_DOT_ZERO = re.compile(r"^\d+\.0$")


def normalize_identifier(value) -> str | None:
    """Normalize a SAP identifier (Material, Vendor, PO Number, ...) to a
    trimmed string, stripping a trailing '.0' only when the whole value is
    numeric (i.e. Excel coerced an identifier column to float)."""
    if value is None:
        return None
    if isinstance(value, float) and pd.isna(value):
        return None
    s = str(value).strip()
    if not s or s.lower() == "nan":
        return None
    if _TRAILING_DOT_ZERO.match(s):
        s = s[:-2]
    return s


def normalize_identifier_series(series: pd.Series) -> pd.Series:
    return series.map(normalize_identifier)


def normalize_plant(value) -> str | None:
    return normalize_identifier(value)


def to_numeric(series: pd.Series) -> pd.Series:
    """Coerce a quantity/amount column to numeric, treating non-numeric
    entries as missing (never silently dropping rows)."""
    return pd.to_numeric(series, errors="coerce")


def to_datetime(series: pd.Series) -> pd.Series:
    return pd.to_datetime(series, errors="coerce")
