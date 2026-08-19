from src.schemas import (
    validate_columns, CUSTOMER_ORDERS_COLUMNS, ON_HAND_COLUMNS, OPEN_ORDERS_COLUMNS,
    UPLOAD_FILE_MAP,
)


def test_customer_orders_schema_exact_31_columns():
    assert len(CUSTOMER_ORDERS_COLUMNS) == 31


def test_on_hand_schema_exact_11_columns():
    assert len(ON_HAND_COLUMNS) == 11


def test_open_orders_schema_exact_28_columns():
    assert len(OPEN_ORDERS_COLUMNS) == 28


def test_valid_schema_passes():
    result = validate_columns("on_hand", ON_HAND_COLUMNS)
    assert result.ok
    assert not result.missing_columns
    assert not result.extra_columns


def test_missing_column_rejected():
    cols = ON_HAND_COLUMNS[:-1]  # drop last column
    result = validate_columns("on_hand", cols)
    assert not result.ok
    assert "Shelf Life Expiration Date" in result.missing_columns


def test_extra_column_rejected():
    cols = ON_HAND_COLUMNS + ["Some New Column"]
    result = validate_columns("on_hand", cols)
    assert not result.ok
    assert "Some New Column" in result.extra_columns


def test_renamed_column_rejected():
    cols = list(ON_HAND_COLUMNS)
    cols[0] = "Material Number"  # renamed from "Material"
    result = validate_columns("on_hand", cols)
    assert not result.ok
    assert "Material" in result.missing_columns
    assert "Material Number" in result.extra_columns


def test_reordered_columns_rejected():
    cols = list(reversed(ON_HAND_COLUMNS))
    result = validate_columns("on_hand", cols)
    assert not result.ok
    assert result.reordered


def test_duplicated_column_rejected():
    cols = list(ON_HAND_COLUMNS) + [ON_HAND_COLUMNS[0]]
    result = validate_columns("on_hand", cols)
    assert not result.ok


def test_oh20_maps_to_plant_2920():
    kind, plant = UPLOAD_FILE_MAP["OH20.xlsx"]
    assert kind == "on_hand"
    assert plant == "2920"


def test_all_nine_uploads_mapped():
    assert len(UPLOAD_FILE_MAP) == 9
    kinds = [k for k, _ in UPLOAD_FILE_MAP.values()]
    assert kinds.count("customer_orders") == 3
    assert kinds.count("on_hand") == 3
    assert kinds.count("open_orders") == 3
