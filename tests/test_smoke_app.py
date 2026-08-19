"""App smoke start: the app must start with no uploaded files and no
exceptions, per the build instructions."""
from pathlib import Path

from streamlit.testing.v1 import AppTest

ROOT = Path(__file__).resolve().parent.parent


def test_home_page_starts_without_exception():
    at = AppTest.from_file(str(ROOT / "app.py"))
    at.run(timeout=30)
    assert not at.exception


def test_ordering_dashboard_starts_without_exception_before_processing():
    at = AppTest.from_file(str(ROOT / "pages" / "1_Ordering_Dashboard.py"))
    at.run(timeout=30)
    assert not at.exception


def test_supplier_detail_starts_without_exception_before_processing():
    at = AppTest.from_file(str(ROOT / "pages" / "2_Supplier_Detail.py"))
    at.run(timeout=30)
    assert not at.exception


def test_data_quality_starts_without_exception_before_processing():
    at = AppTest.from_file(str(ROOT / "pages" / "3_Data_Quality.py"))
    at.run(timeout=30)
    assert not at.exception


def test_export_center_starts_without_exception_before_processing():
    at = AppTest.from_file(str(ROOT / "pages" / "4_Export_Center.py"))
    at.run(timeout=30)
    assert not at.exception
