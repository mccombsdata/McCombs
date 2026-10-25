# Fixing the Fizz — Dashboard v4

**Tableau-inspired interactive business intelligence application for an academic, deidentified/perturbed retail DSD case.** Viewer-uploaded CSVs are **not included** in this distribution.

## Highlights

- **Metric-aware graded palette**: <70% red, 70–80% orange, 80–90% yellow, 90–95% teal, 95%+ blue for in-stock / FTPR / pre-sub pick. Values transition smoothly rather than having five discontinuous buckets. Missing or below-coverage cells gray.
- **Nil-pick has its own reverse scale** (0–1% blue, >10% red; illustrative).
- Cleaner, wider dashboard and KPI cards with sticky session-only manual uploads.
- **Global filters:** category, brand, store, vendor, sampled date; reset button; availability/reference and rate coverage controls.
- **Executive view:** category sales and rate rankings plus revenue × availability opportunity quadrant.
- **Brand comparison:** up to five brands, graded availability bars, like-category grouped bars, sortable formatted tables.
- **Store × brand heatmap:** top-selling brands by recorded sales, all sampled stores, gray low-coverage intersections; store/category drilldown.
- **Opportunity finder:** identify brand × store, product × store, and brand combinations with observed availability below an adjustable reference, sufficient sample sizes, and meaningful sales.
- **FTPR & picking:** FTPR, pre-sub, and nil-pick selections; appropriate performance colors; correct six-week store/item alignment, matched scatter, item-level drilldown.
- **Trends & synthetic operations:** sampled-date sales and availability; synthetic delivery and merchandising analysis.
- **Data quality:** rate missingness, FTPR mismatch flag, coverage badges, interpretation notes.

## Update your existing GitHub → Streamlit deployment

1. Unzip this archive.
2. Open the **same GitHub repository** already powering your Streamlit app.
3. Replace the existing root `app.py`, `analysis.py`, `requirements.txt`, and `README.md`. **Add the new `visuals.py`** to the repository root. This new file is required. Optionally update `.streamlit/config.toml`.
4. Commit the changes. Streamlit Community Cloud should automatically redeploy the existing URL.
5. Visit the app and upload **both original CSVs** again.

Do **not** upload either source CSV, an exported detail table, credentials, or sample case data to GitHub. The `.gitignore` excludes CSV and Parquet by default. A private repository / private app is preferable; consult your sponsor before processing case data in third-party cloud services.

### File structure

```
app.py
analysis.py
visuals.py
requirements.txt
README.md
.gitignore
.streamlit/config.toml
```

## Why rates are presented this way

- Row-mean observed in-stock values **exclude missing** rates and are not demand-weighted or mix-adjusted.
- The annual sales file contains **52 sampled observation dates**, not a continuous daily-sales file.
- Published FTPR, pre-sub and nil rates are displayed as **unweighted mean reported store-item rates**. Count numerators and denominators in this perturbed case do not always reconcile.
- The FTPR join first aggregates daily observations *within the FTPR window* to unique store × item pairs, then joins FTPR one-to-one. The sampled-date filter never truncates the FTPR comparison window.
- Sales × availability plots are **investigation screens**, not a calculation of lost sales, demand recovery, or confirmed targets.
- All performance thresholds in V4 are **illustrative and configurable where appropriate**, not company-provided service thresholds.
- Blank/gray heatmap cells are missing or lack sufficient coverage, **not zero**.
- Synthetic operational variables do not identify causal effects.

## Security

The web UI asks for manual CSV uploads on each new session. Parsed file content is cached **only within the user session** with `st.cache_data(scope="session")`. This does not guarantee cloud confidentiality: the app processes bytes on the hosting server and any authorized viewers can upload/export data. Get sponsor approval before cloud processing. No server-side permanent source-file storage or external API has been programmed into the app; deployments remain subject to the provider's policies, logs and retention behavior.

## Running locally (optional)

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
streamlit run app.py
```

## Dependencies

Streamlit ≥1.55, Pandas ≥2.1, Plotly ≥5.22, NumPy ≥1.26. No database or secret configuration required.
