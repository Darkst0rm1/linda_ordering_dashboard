from src.normalize import normalize_identifier
from src.schemas import UPLOAD_FILE_MAP


def test_oh20_is_plant_2920_not_plant_20():
    """OH20.xlsx is plant 2920 on-hand data, not a literal plant '20' --
    this is the single most error-prone mapping in the build instructions."""
    kind, plant = UPLOAD_FILE_MAP["OH20.xlsx"]
    assert plant == "2920"
    assert kind == "on_hand"


def test_identifier_strips_trailing_dot_zero_from_excel_coercion():
    assert normalize_identifier("10013700.0") == "10013700"
    assert normalize_identifier(10013700.0) == "10013700"


def test_identifier_strips_whitespace():
    assert normalize_identifier("  10013700  ") == "10013700"


def test_identifier_preserves_non_numeric_ids_untouched():
    assert normalize_identifier("PO-2026-001") == "PO-2026-001"


def test_identifier_none_and_nan_become_none():
    import math
    assert normalize_identifier(None) is None
    assert normalize_identifier(math.nan) is None


def test_all_plants_present_in_mapping():
    plants = {p for _, p in UPLOAD_FILE_MAP.values()}
    assert plants == {"2910", "2920", "2930"}
