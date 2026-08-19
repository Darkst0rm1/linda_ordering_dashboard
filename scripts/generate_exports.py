"""Drive the running app to actually build+download the Excel export and
audit report from the real supplied data (required deliverable). One-off
script, not part of the app."""
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent.parent
SAMPLE = ROOT / "sample_data"
OUT = ROOT / "deliverables"
OUT.mkdir(exist_ok=True)

APP_URL = "http://localhost:8765"

UPLOAD_FILES = [
    "2910Customerorders.xlsx", "2920CustomerOrders.xlsx", "2930Customerorders.xlsx",
    "OH2910.xlsx", "OH20.xlsx", "OH2930.xlsx",
    "OR2910.xlsx", "OR2920.xlsx", "OR2930.xlsx",
]

with sync_playwright() as p:
    browser = p.chromium.launch(channel="chrome", headless=True)
    page = browser.new_page(viewport={"width": 1600, "height": 1200}, accept_downloads=True)
    page.goto(APP_URL, wait_until="networkidle", timeout=60000)
    page.wait_for_timeout(2000)

    for i, filename in enumerate(UPLOAD_FILES):
        file_inputs = page.locator("input[type='file']")
        file_inputs.nth(i).set_input_files(str(SAMPLE / filename))
        page.wait_for_timeout(1500)

    page.wait_for_timeout(2000)
    page.get_by_role("button", name="Process Files").click()
    page.wait_for_timeout(4000)

    page.get_by_role("link", name="Export Center", exact=False).first.click()
    page.wait_for_timeout(3000)

    page.get_by_role("button", name="Build Excel workbook").click()
    page.wait_for_timeout(6000)

    with page.expect_download(timeout=30000) as dl_info:
        page.get_by_role("button", name="Download Linda_Ordering_Dashboard").click()
    dl = dl_info.value
    dl.save_as(str(OUT / dl.suggested_filename))
    print("saved", dl.suggested_filename)

    with page.expect_download(timeout=30000) as dl_info2:
        page.get_by_role("button", name="Download Linda_Ordering_Audit").click()
    dl2 = dl_info2.value
    dl2.save_as(str(OUT / dl2.suggested_filename))
    print("saved", dl2.suggested_filename)

    browser.close()

print("done")
