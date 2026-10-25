# Fixing the Fizz · v3

An interactive Streamlit dashboard for the deidentified and perturbed Walmart / McCombs retail DSD case. It uses the **two CSVs uploaded by the dashboard viewer**; no private case data or credentials are packaged in this repository.

## What's new in v3

- Cleaner blue/white executive view, polished KPI tiles and consistent chart design.
- Overview focuses on the *recorded sales footprint* and observed in-stock availability instead of stacking uncontextualized charts.
- Brand comparison by **category**, with sample-count thresholds, coverage metrics, and spreadsheet export.
- **Priority Finder**: shortlist brand × store, product × store, or brand groups with a combination of recorded sales, availability below an illustrative reference (default 95%), enough sampled observations, and sufficient valid availability data.
- Improved store explorer with heatmap and trends on **sampled dates**.
- Six-week online-picking view still correctly aligns store × item aggregated daily rows to each FTPR store × item record; does not accidentally apply the year-long sales-date filter to FTPR.
- Dedicated data-quality section explaining missing CSD SINGLES availability and discrepancies between published FTPR and its numerator/denominator.
- **Session-scoped cached data** via Streamlit 1.55+ instead of default global caching. This reduces cross-session sharing of cached uploads, but **does not make public cloud hosting safe or authorized**.

## Update your existing GitHub / Streamlit deployment

You do **not** need to create another Streamlit app or install anything on your Mac.

1. Unzip this download.
2. Open the GitHub repository connected to your working Streamlit app.
3. Replace **`app.py`**, **`analysis.py`**, **`requirements.txt`**, and optionally **`README.md`** with the copies from this folder; commit changes. The included `.streamlit/config.toml` changes only the colors and upload limit, and is optional.
4. Streamlit Community Cloud automatically redeploys after it detects a GitHub commit. Because `requirements.txt` changed, allow it to install the new Streamlit version.
5. Refresh the app, then re-upload the original CSVs through the sidebar.

**Do NOT upload** `sparkle_case_daily_sales_instock.csv`, `sparkle_case_ftpr_summary.csv`, or any other private data to GitHub. `.gitignore` is a safety net, not a guarantee: review what you're committing. Keep your repository *and the Streamlit app* private, if the sponsor approves cloud use.

### Data inputs

- `sparkle_case_daily_sales_instock.csv` — store × item × sampled weekly date, ~479k rows.
- `sparkle_case_ftpr_summary.csv` — store × item × six-week FTPR window, ~10.9k rows.

For offline use with sponsor-authorized local data, put the CSVs in a `data/` folder beside `app.py`; `.gitignore` excludes that folder. On a shared Streamlit Cloud deployment, do *not* bundle real case data into `data/`.

## Reading the dashboard correctly

- **Recorded sales**: sums of the case's observed **sampled dates**. This is *not* a full-year daily sales total, and the source numbers have been perturbed.
- **Average availability**: unweighted average of nonmissing `frac_instk_pct`, converted to a displayed percentage. It is not sales-weighted, demand-weighted, or assortment/mix-adjusted.
- **Coverage**: share of records where in-stock is populated. CSD SINGLES has no availability values in the supplied data.
- **Availability reference**: default 95% is a hypothetical screening threshold, **not a confirmed Walmart target**. The Priority Finder flags candidates for inspection; it does **not** calculate lost sales.
- **FTPR**: mean of *published, reported* store-item rates across the FTPR period (2026-08-09 through 2026-09-19). These rates are not order-weighted; rate and count fields do not always reconcile due to data perturbation.
- **FTPR alignment**: aggregate weekly observations from the FTPR period to store-item first; then do a one-to-one join to FTPR. Don't merge raw weekly rows directly or you will double count FTPR records.
- **SYNTHETIC** delivery and merchandising fields are simulated and cannot establish root cause or causality.

## Security model

The Streamlit file uploader transfers browser-uploaded CSVs to the server, so data is processed **wherever the app is hosted**. In Streamlit Cloud that's a third-party cloud provider. Session-scoped caches limit cross-session availability of cached data, but are not a substitute for authorization, authentication, data classification, a client-approved hosting location, retention controls, or access logs. Upload case data to a hosted instance only after sponsor/client approval. A public GitHub repo is appropriate for code **only** if the project permits public code sharing. Avoid embedding any data samples from the case in public code, screenshots, or bug reports.

## Local development

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
streamlit run app.py
```

For Streamlit documentation: https://docs.streamlit.io/
