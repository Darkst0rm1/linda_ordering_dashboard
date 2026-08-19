"""Narrow-width check: upload+process, then screenshot the Ordering
Dashboard and Data Quality pages at a phone-sized viewport to look for
clipped headers, overflow, or broken layout. One-off script."""
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent.parent
SAMPLE = ROOT / "sample_data"
SHOTS = ROOT / "screenshots"

APP_URL = "http://localhost:8765"

UPLOAD_FILES = [
    "2910Customerorders.xlsx", "2920CustomerOrders.xlsx", "2930Customerorders.xlsx",
    "OH2910.xlsx", "OH20.xlsx", "OH2930.xlsx",
    "OR2910.xlsx", "OR2920.xlsx", "OR2930.xlsx",
]

with sync_playwright() as p:
    browser = p.chromium.launch(channel="chrome", headless=True)
    page = browser.new_page(viewport={"width": 390, "height": 844})  # iPhone-ish width
    page.goto(APP_URL, wait_until="networkidle", timeout=60000)
    page.wait_for_timeout(2000)

    for i, filename in enumerate(UPLOAD_FILES):
        file_inputs = page.locator("input[type='file']")
        file_inputs.nth(i).set_input_files(str(SAMPLE / filename))
        page.wait_for_timeout(1500)
    page.wait_for_timeout(2000)
    page.get_by_role("button", name="Process Files").click()
    page.wait_for_timeout(4000)

    body_width = page.evaluate("document.documentElement.scrollWidth")
    print("Home page scrollWidth:", body_width, "(viewport 390)")
    page.screenshot(path=str(SHOTS / "narrow_0_home.png"))

    page.goto(f"{APP_URL}/Ordering_Dashboard", wait_until="networkidle", timeout=60000)
    page.wait_for_timeout(4000)
    body_width = page.evaluate("document.documentElement.scrollWidth")
    print("Ordering Dashboard scrollWidth:", body_width)
    page.screenshot(path=str(SHOTS / "narrow_1_ordering_dashboard.png"), full_page=True)

    browser.close()

print("done")
