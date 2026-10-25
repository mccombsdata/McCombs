# Fixing the Fizz — Interactive dashboard (v2)

Streamlit prototype integrating the **weekly-item-store sales/inventory file** and the **six-week FTPR summary** for the deidentified Walmart/McCombs class project.

## Run on your computer (recommended initially)

1. Install [Python 3.10+](https://www.python.org/downloads/) if necessary.
2. Unzip this folder. Open a Terminal in the project folder.
3. Install dependencies:

   ```bash
   python3 -m pip install -r requirements.txt
   ```

4. Start the app:

   ```bash
   python3 -m streamlit run app.py
   ```

5. Upload each CSV through the dashboard's sidebar:
   - `sparkle_case_daily_sales_instock.csv`
   - `sparkle_case_ftpr_summary.csv`

Alternatively, create a local `data/` folder beside `app.py` and place **both** CSVs inside it. The app will load them automatically. The `data/` directory is ignored by Git and is not packaged with this code.

If `pip install` reports that Python is externally managed, create a virtual environment first:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
streamlit run app.py
```

## What it includes

- Executive overview: sales, units, availability, covered categories.
- Brand intelligence: revenue and availability scatter, side-by-side category comparison and table.
- Store explorer: store rankings, brand/store in-stock heatmap, weekly trends.
- FTPR + inventory: six-week FTPR metrics and paired product-store availability *correctly matched at the same grain and time window*.
- Operations: exploratory synthetic delivery and merchandising diagnostics.
- Data quality: missingness by category, pair match rate and discrepancies between provided FTPR rates and component counts.
- CSV export of several summary tables.

### Data and analytical limitations

- Daily source is **52 sampled weekly dates**, not continuous daily transactions.
- Daily in-stock availability is a **simple row average of observed non-missing values**. It is not demand weighted, mix adjusted or a lost-sales calculation.
- All `CSD SINGLES` in-stock percentages are missing. Do not assume zero availability.
- FTPR summary refers only to **2026-08-09 to 2026-09-19**. Although users can filter the full-year sales tabs by date, the **FTPR tab deliberately ignores the date picker** and aligns daily data to the full six-week FTPR window for valid side-by-side diagnostics.
- FTPR is summarized as the **unweighted mean of the reported store-item FTPR percentages** to avoid mixing inconsistent numerators and percentages in perturbed case data; it is *not* an order-weighted pick rate. The Data Quality tab reports a metric reconciliation check.
- We aggregate daily data to a single record per **store × item** *before* joining it to FTPR. Never join raw daily rows to FTPR without first aggregating.
- Operational fields labeled `SYNTHETIC` are simulated. Correlations are not evidence of causation.
- Case sales, inventory and rate figures are deidentified/perturbed; they are **not actual Walmart financial results**.

## Collaboration and client sharing

1. Use a private GitHub repository to collaborate **on code only**. `.gitignore` excludes local CSVs and `data/`.
2. Keep a version-controlled README documenting data definitions, sources, and limitations.
3. Confirm with the case sponsor/client whether cloud hosting and external sharing are authorized.
4. Streamlit Community Cloud may work for an approved private prototype; for controlled enterprise client delivery, prefer an organization-approved host with SSO, permissions, and access logs.
5. Do not assume a private GitHub repository makes a Streamlit app private. Separately configure viewer authorization. Avoid embedding confidential data in source code, release archives, commits or shared links.
6. This is a read-only analytics dashboard. Collaborative source editing is provided through GitHub; live multi-user editing/annotations would require additional application features and a shared database.

## Project files

- `app.py` — Streamlit UI.
- `analysis.py` — CSV loading, aggregations, six-week period alignment, quality metrics.
- `requirements.txt` — Python dependencies.
- `.gitignore` — prevents accidental commits of private data.
- `.streamlit/config.toml` — Streamlit appearance.

## Troubleshooting

- `ModuleNotFoundError: streamlit`: run the install command again inside the same Python environment.
- `File not found`: upload in the sidebar or place exact CSV filenames under `data/`.
- Slow initial load: 113 MB is manageable, but processing the first read may take several seconds. Subsequent dashboard interactions use Streamlit's cache.
- Sharing: do not upload or commit data to a public repo; obtain explicit authorization before any third-party hosting.
