"""Drive the running Streamlit app with Playwright + the system Chrome
install, upload the real supplied SAP exports, click Process Files, and
screenshot all five pages. One-off script, not part of the app."""
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent.parent
SAMPLE = ROOT / "sample_data"
SHOTS = ROOT / "screenshots"
SHOTS.mkdir(exist_ok=True)

APP_URL = "http://localhost:8765"

UPLOAD_FILES = [
    "2910Customerorders.xlsx", "2920CustomerOrders.xlsx", "2930Customerorders.xlsx",
    "OH2910.xlsx", "OH20.xlsx", "OH2930.xlsx",
    "OR2910.xlsx", "OR2920.xlsx", "OR2930.xlsx",
]

with sync_playwright() as p:
    browser = p.chromium.launch(channel="chrome", headless=True)
    page = browser.new_page(viewport={"width": 1600, "height": 2800})
    page.goto(APP_URL, wait_until="networkidle", timeout=60000)
    page.wait_for_timeout(2000)

    for i, filename in enumerate(UPLOAD_FILES):
        # Streamlit reruns the whole script (and recreates DOM nodes) after
        # every widget interaction, so the input elements must be re-located
        # fresh each time rather than reusing a locator grabbed once upfront.
        file_inputs = page.locator("input[type='file']")
        file_inputs.nth(i).set_input_files(str(SAMPLE / filename))
        page.wait_for_timeout(1500)

    page.wait_for_timeout(3000)
    page.screenshot(path=str(SHOTS / "0_home_uploaded.png"), full_page=True)

    process_btn = page.get_by_role("button", name="Process Files")
    process_btn.wait_for(state="visible", timeout=10000)
    process_btn.click()
    page.wait_for_timeout(5000)
    page.screenshot(path=str(SHOTS / "0_home_processed.png"), full_page=True)

    pages = [
        ("Ordering Dashboard", "1_ordering_dashboard"),
        ("Supplier Detail", "2_supplier_detail"),
        ("Data Quality", "3_data_quality"),
        ("Export Center", "4_export_center"),
    ]
    for link_text, shot_name in pages:
        link = page.get_by_role("link", name=link_text, exact=False)
        link.first.click()
        page.wait_for_timeout(4000)
        page.screenshot(path=str(SHOTS / f"{shot_name}.png"), full_page=False)
        print("captured", shot_name)

    browser.close()

print("done")
