# Linda Ordering Dashboard

A Streamlit replacement for the manual "Linda New Ordering Spreadsheet" Excel
workflow. Upload the nine SAP exports, review the ordering dashboard, drill
into a supplier, check data-quality reconciliation, and export a clean Excel
workbook + audit report -- all in the browser, no Excel/VBA/xlwings/COM
required.

## What this is (and isn't)

The reference workbook (`Linda New Ordering Spreadsheet 08_19_2026.xlsx`)
has 51 sheets, ~38,800 formulas, and 1,952 broken (`#REF!`) formulas. This
app does **not** reproduce all 51 sheets. It translates the current, useful
ordering workflow -- the 16 named supplier sheets' product/vendor/forecast
data -- into one dashboard, and is explicit everywhere a legacy field could
not be safely translated (see **Known limitations** below and the Data
Quality page).

## Project structure

```text
app.py                     Home / Upload page
pages/
  1_Ordering_Dashboard.py
  2_Supplier_Detail.py
  3_Data_Quality.py
  4_Export_Center.py
src/
  schemas.py                Exact 31/11/28-column schemas + validation
  loaders.py                Upload parsing, caching by content hash
  normalize.py               Identifier/date/numeric normalization
  aggregate.py               Composite-key (Plant, Material) aggregation
  product_master.py          Loads config/product_master.csv + suppliers.yaml
  reconciliation.py          Data Quality checks
  excel_export.py            XlsxWriter workbook + audit report builders
  state.py                   Session-state helpers (uploads, overrides)
  pipeline.py                 Wires loaders -> aggregate -> reconciliation
  config.py                  Loads config/business_rules.yaml
config/
  business_rules.yaml         Thresholds & policy constants
  suppliers.yaml               Supplier list, colors, plant/status colors
  product_master.csv           Extracted product/vendor master (16 suppliers)
  product_master_extraction_audit.json
  reference_workbook_audit.json
tests/
scripts/                      One-off extraction scripts used to build config/
  (not part of the running app)
```

## Local setup

```bash
python -m venv .venv
source .venv/bin/activate  # or .venv\Scripts\activate on Windows
pip install -r requirements.txt
streamlit run app.py
```

Then open the URL Streamlit prints (typically http://localhost:8501),
upload the nine `.xlsx` exports on the Home page (all from sheet
`SAPUI5 Export`), and click **Process Files**.

### Development mode / sample data

`sample_data/` (git-ignored, contains real business data) holds the nine
supplied SAP exports plus the reference workbook, for local testing only.
To enable the **Load bundled sample data** button on the Home page, run
with the dev-mode flag on:

```bash
LINDA_DEV_MODE=true streamlit run app.py
```

It defaults **off** in production. On Streamlit Community Cloud, set
`dev_mode = true` in the app's Secrets instead of an environment variable --
never commit uploaded workbooks or user data to the repo.

## Testing

```bash
pytest -q
```

51 tests cover: exact schema enforcement, `OH20.xlsx` -> plant 2920 mapping,
identifier normalization, duplicate preservation, all aggregation rules
(on-hand/quality/blocked/expiry/customer-order/confirmed/unconfirmed/open-PO/
inbound/next-delivery), plant-specific Allocation Qty mapping, composite
Plant+Material joins, unmatched-material reporting, suggested-order behavior
with and without a target, reconciliation grand totals, Excel export sheet
names + no external links/PivotTables + programmatic read-back, and an
app smoke start (`streamlit.testing.v1.AppTest`) for all five pages before
any file is uploaded.

Independent reconciliation against the supplied snapshot (test fixtures
only, never hard-coded as production limits): customer orders 551/145/175,
on-hand 223/152/126, open orders 146/13/14 for plants 2910/2920/2930 --
confirmed byte-exact against the real supplied files during development
(`scripts/inspect_sap_exports.py`).

## Streamlit Community Cloud deployment

1. Push this repository to GitHub (`sample_data/` stays out of git via
   `.gitignore` -- never commit uploaded workbooks or user data).
2. In Streamlit Community Cloud, create a new app pointing at this repo,
   branch `main`, entry point `app.py`.
3. `requirements.txt` and `.streamlit/config.toml` are picked up
   automatically -- no Docker/Render/other hosting config is used or needed.
4. If you want dev mode's sample-data button available in a private
   deployment, add `dev_mode = true` under the app's Secrets. Leave it unset
   for a public/production deployment.

### Memory and upload-size notes

- Community Cloud apps typically run with ~1 GB RAM. The nine SAP exports
  are small (a few hundred to ~700 rows each); the reference workbook itself
  is never uploaded to the app -- it was only used offline to build
  `config/product_master.csv`.
- `server.maxUploadSize` is set to 50 MB in `.streamlit/config.toml`.
- Uploads are parsed to pandas DataFrames in memory and never written to
  disk; nothing is cached beyond the current session except the
  content-hash-keyed `st.cache_data` results, which live in server memory
  only.

## Known limitations (never silently invented)

- **1,952 broken (`#REF!`) formulas** exist in the reference workbook.
  None were translated into dashboard logic. See
  `config/reference_workbook_audit.json` for the per-sheet formula/error
  counts and `config/product_master_extraction_audit.json` for exactly
  which columns were used per supplier sheet.
- **No Target Stock / Safety Stock / Reorder Point column exists** in any
  of the 9 SAP exports or the 16 supplier sheets. Target Stock is each
  material's most recently populated `Forecast AS400` value (a real,
  non-broken figure); Safety Stock is a configured 20% of Target Stock
  (`config/business_rules.yaml`). When no Target Stock is available,
  Suggested Order Qty is left blank and Risk/Status is `Review`
  ("Needs planner target") -- never defaulted to zero.
- **Caputo's sheet uses a block/label layout**, not the uniform
  one-row-per-material table the other 15 supplier sheets use, so its
  per-row product master could not be safely extracted (0 rows). See the
  `_known_limitations` note in `config/product_master_extraction_audit.json`
  and the Data Quality page.
- **No case-pack/units-per-case field exists** anywhere in the source data.
  All source quantities are already expressed in cases (column names end in
  "(CS)"), so "round up to whole cases" is `math.ceil()` on the
  already-case-denominated quantity -- no separate multiplier was invented.
- **Forecast periods**: the reference workbook's month-by-month forecast
  columns are inconsistently labeled (some literal dates, some generic
  "Base Line"/"Current Month" placeholders) and mostly broken (`#REF!`).
  Supplier Detail exposes the single valid extracted baseline rather than a
  fabricated multi-period picker.
