"""Fixing the Fizz v3 — confidential-by-design academic diagnostic app.

No case data ships with this app. User-uploaded files are parsed using a
session-scoped in-memory cache; no external analytics or database connections.
"""
from __future__ import annotations

import io
from pathlib import Path

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from analysis import align_ftpr, ftpr_summary, load_daily, load_ftpr, mismatch_stats, summarized

st.set_page_config(
    page_title="Fixing the Fizz | DSD Decision Lab",
    page_icon="🥤", layout="wide", initial_sidebar_state="expanded"
)
BLUE = "#0071CE"
NAVY = "#123D6A"
YELLOW = "#FFC220"
PALE = "#F4F8FD"
RED = "#C45032"
GREEN = "#26855B"
GRAY = "#657487"
BASE = Path(__file__).parent
DATA = BASE / "data"

st.markdown("""
<style>
.block-container {padding-top: 1.5rem; max-width: 1530px;}
[data-testid="stSidebar"] {background: #F4F8FD;}
[data-testid="stMetric"] {background: white; border: 1px solid #E5EDF6; border-radius: 14px; padding: 16px 16px 12px; box-shadow: 0 3px 16px rgba(18,61,106,.045);}
[data-testid="stMetricLabel"] {font-size: .82rem; font-weight: 600; color: #51647b;}
[data-testid="stMetricValue"] {font-size: 1.67rem; font-weight: 700; color: #143B62;}
[data-testid="stTabs"] button[role="tab"] {font-weight: 650;}
.hero {border-radius: 17px; padding: 24px 28px; color: #fff; background: linear-gradient(108deg,#123D6A 0%,#0071CE 100%); margin-bottom: 16px;}
.hero h1 {font-size: 2rem; line-height: 1.18; margin: 0 0 7px; color: #fff;}
.hero p {margin: 0; color: #DDEEFF; font-size: .9rem;}
.hero .tag {display:inline-block; color:#15304D; background:#FFC220; border-radius:50px; font-size:.7rem; font-weight:750; padding:4px 11px; margin-bottom: 11px;}
.section-note {color:#5C6D81;font-size:.87rem;margin-bottom:8px;}
.small-rule {border-top:1px solid #E3EAF2;margin:18px 0 12px;}
</style>""", unsafe_allow_html=True)


@st.cache_data(scope="session", show_spinner="Reading sales and inventory CSV…", max_entries=1)
def cached_daily(raw: bytes) -> pd.DataFrame:
    return load_daily(io.BytesIO(raw))


@st.cache_data(scope="session", show_spinner="Reading FTPR CSV…", max_entries=1)
def cached_ftpr(raw: bytes) -> pd.DataFrame:
    return load_ftpr(io.BytesIO(raw))


def source_bytes(filename: str, label: str, widget_key: str):
    path = DATA / filename
    if path.is_file():
        st.sidebar.success(f"{label}: available from local data/")
        return path.read_bytes()
    uploaded = st.sidebar.file_uploader(label, type=["csv"], key=widget_key)
    return uploaded.getvalue() if uploaded is not None else None


def chart(fig, key: str | None = None):
    fig.update_layout(
        template="plotly_white", font=dict(family="Arial", color=NAVY, size=12),
        margin=dict(l=4, r=20, t=49, b=20),
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        title=dict(font=dict(size=15, color=NAVY)),
        legend_title_text="",
        hoverlabel=dict(bgcolor="white", font_size=12)
    )
    fig.update_xaxes(gridcolor="#EAF0F7", zerolinecolor="#EAF0F7")
    fig.update_yaxes(gridcolor="#EAF0F7", zerolinecolor="#EAF0F7")
    st.plotly_chart(fig, use_container_width=True, key=key)


def export(df, name: str, key: str):
    st.download_button(
        "↓ Export filtered table", df.to_csv(index=False).encode("utf-8"),
        file_name=name, mime="text/csv", key=key
    )


def fmt_money(value):
    if not np.isfinite(value):
        return "—"
    if abs(value) >= 1_000_000:
        return f"${value / 1_000_000:,.2f}M"
    if abs(value) >= 1_000:
        return f"${value / 1_000:,.0f}K"
    return f"${value:,.0f}"


def fmt_pct(value):
    return f"{value:.1f}%" if pd.notna(value) else "N/A"


def coverage(df: pd.DataFrame):
    return df["instock_pct"].notna().mean() * 100 if len(df) else np.nan


def stock_figure(frame: pd.DataFrame, label: str, title: str, target: float):
    frame = frame.dropna(subset=["avg_instock"]).copy()
    frame = frame.sort_values("avg_instock", ascending=False)
    fig = px.bar(frame, x="avg_instock", y=label, orientation="h", color_discrete_sequence=[BLUE],
                 hover_data=[x for x in ["sales", "obs", "missing_instock_pct"] if x in frame.columns],
                 labels={"avg_instock": "Observed availability (%)", label: ""}, title=title)
    lower = max(0, min(75, (frame["avg_instock"].min() - 4) if len(frame) else 75))
    fig.update_xaxes(range=[lower, 102])
    fig.update_traces(texttemplate="%{x:.1f}%", textposition="outside", cliponaxis=False)
    fig.add_vline(x=target, line_color=RED, line_dash="dash", opacity=.7,
                  annotation_text=f"Reference {target:.0f}%", annotation_position="top left")
    fig.update_layout(height=max(350, min(560, 90 + 34 * len(frame))), showlegend=False)
    return fig


def priority_view(df: pd.DataFrame, grain: list[str], min_rows: int,
                  min_coverage: int, min_sales: float, target: int):
    table = summarized(df, grain)
    table["coverage_pct"] = 100 - table["missing_instock_pct"]
    table["gap_to_reference_pp"] = (target - table["avg_instock"]).clip(lower=0)
    table = table[
        (table["obs"] >= min_rows) & (table["coverage_pct"] >= min_coverage) &
        (table["sales"] >= min_sales) & (table["gap_to_reference_pp"] > 0)
    ].sort_values(["sales", "gap_to_reference_pp"], ascending=False)
    return table


st.markdown("""<div class="hero"><span class="tag">McCOMBS × RETAIL DSD · INTERACTIVE ANALYSIS</span>
<h1>🥤 Fixing the Fizz</h1>
<p>Where are sales, shelf availability, and online fulfillment diverging — and where should the team investigate next?</p>
</div>""", unsafe_allow_html=True)

st.sidebar.markdown("### Data & filters")
st.sidebar.caption("Files are uploaded to this app's running server. Keep the app private and confirm cloud-use permission with your case sponsor.")
daily_raw = source_bytes("sparkle_case_daily_sales_instock.csv", "Daily sales / inventory", "daily")
ftpr_raw = source_bytes("sparkle_case_ftpr_summary.csv", "FTPR summary", "ftpr")

if daily_raw is None or ftpr_raw is None:
    st.info("Upload both original CSV files in the sidebar to explore the dashboard. The GitHub repository contains code only, not case data.")
    st.markdown("**Included analyses:** Brand Comparison · Availability Priorities · Store Heatmap · FTPR Alignment · Synthetic Operations · Data Quality")
    st.stop()

try:
    daily_full = cached_daily(daily_raw)
    ftpr_full = cached_ftpr(ftpr_raw)
except Exception as exc:
    st.error(f"Unable to load the files. Check that you selected the original CSVs. Details: {exc}")
    st.stop()

st.sidebar.divider()
cat_options = sorted(daily_full["category_desc"].dropna().astype(str).unique().tolist())
brand_options = sorted(daily_full["brand"].dropna().astype(str).unique().tolist())
store_options = sorted(daily_full["store_id"].dropna().astype(str).unique().tolist())
sel_categories = st.sidebar.multiselect("Category", cat_options, placeholder="All categories")
sel_brands = st.sidebar.multiselect("Brand", brand_options, placeholder="All brands")
sel_stores = st.sidebar.multiselect("Store", store_options, placeholder="All stores")

# Same dimensional filters apply to both datasets, but the date selector
# applies only to the annual weekly-sample dataset (NOT the fixed FTPR window).
def dimensional_filter(frame):
    if sel_categories:
        frame = frame[frame["category_desc"].isin(sel_categories)]
    if sel_brands:
        frame = frame[frame["brand"].isin(sel_brands)]
    if sel_stores:
        frame = frame[frame["store_id"].isin(sel_stores)]
    return frame

base_daily = dimensional_filter(daily_full)
ftpr = dimensional_filter(ftpr_full)
minimum = daily_full["date"].min().date()
maximum = daily_full["date"].max().date()
period = st.sidebar.date_input("Sampled sales dates", (minimum, maximum), min_value=minimum, max_value=maximum)
daily = base_daily
if isinstance(period, (tuple, list)) and len(period) == 2:
    daily = daily[daily["date"].between(pd.Timestamp(period[0]), pd.Timestamp(period[1]))]

st.sidebar.divider()
reference = st.sidebar.slider("Availability reference (%)", 80, 100, 95, 1,
                              help="Illustrative screening reference, not an official Walmart performance target.")
st.sidebar.caption("Source data: deidentified and perturbed. Financial values are illustrative; availability uses observed nonmissing rows, not demand weights.")

if daily.empty and ftpr.empty:
    st.warning("No records match the current filters. Widen the selection in the sidebar.")
    st.stop()

# Top-line KPI row: make the exact measurement period and limitations explicit.
m1, m2, m3, m4, m5 = st.columns(5, gap="small")
m1.metric("Recorded sales · sampled dates", fmt_money(daily["sales_amt"].sum()) if len(daily) else "—")
m2.metric("Units sold", f"{daily['unit_qty'].sum():,.0f}" if len(daily) else "—")
m3.metric("Observed availability", fmt_pct(daily["instock_pct"].mean()) if len(daily) else "—")
m4.metric("Availability data coverage", fmt_pct(coverage(daily)))
m5.metric("Brands in view", str(daily["brand"].nunique()) if len(daily) else "0")
st.caption("All sales figures reflect the **52 sampled observation dates**, not a continuous daily-sales series. Availability is a simple average of nonmissing product-store-date rows. FTPR has its own fixed six-week period.")

overview, brand_lab, priorities, stores_tab, ftpr_tab, ops_tab, quality_tab = st.tabs([
    "Overview", "Brand lab", "Priority finder", "Stores & trends", "Online fulfillment", "Operations", "Data quality"
])

with overview:
    st.subheader("What stands out?")
    left, right = st.columns([1.14, 1], gap="large")
    if not daily.empty:
        categories = summarized(daily, "category_desc")
        top_cats = categories.sort_values("sales", ascending=False).head(8)
        with left:
            fig = px.bar(top_cats.sort_values("sales"), x="sales", y="category_desc",
                         orientation="h", color_discrete_sequence=[BLUE],
                         labels={"sales": "Recorded sales ($)", "category_desc": ""},
                         title="Largest categories by recorded sales")
            fig.update_traces(texttemplate="$%{x:,.0f}", textposition="outside", cliponaxis=False)
            fig.update_layout(height=410)
            chart(fig)
        with right:
            present = top_cats.dropna(subset=["avg_instock"])
            chart(stock_figure(present, "category_desc", "Availability across major categories", reference))
            missing = top_cats[top_cats["avg_instock"].isna()]
            if len(missing):
                st.caption("Not charted because availability is missing: " + ", ".join(missing["category_desc"].astype(str)))
        st.markdown("<div class='small-rule'></div>", unsafe_allow_html=True)
        st.subheader("Revenue footprint vs. availability")
        st.caption("A screening view, not a lost-sales estimate. Bubble size reflects recorded units; missing availability excludes brands from the plot.")
        by_brand = summarized(daily, "brand").dropna(subset=["avg_instock"])
        by_brand = by_brand[by_brand["sales"].gt(0)]
        if len(by_brand):
            fig = px.scatter(by_brand, x="avg_instock", y="sales", size="units", size_max=48,
                             color_discrete_sequence=[BLUE], hover_name="brand",
                             hover_data=["products", "stores", "missing_instock_pct"],
                             labels={"avg_instock": "Observed in-stock (%)", "sales": "Recorded sales ($)"},
                             title="Brands with high sales and weaker availability merit investigation")
            fig.add_vline(x=reference, line_dash="dash", line_color=RED, opacity=.75)
            fig.update_layout(height=420)
            chart(fig)
    else:
        st.info("No sales rows for the selected dates. Clear the date filter to explore.")

with brand_lab:
    st.subheader("Compare brands on like-for-like categories")
    st.caption("The top-line averages are not mix-adjusted. The category breakdown below highlights differences and flags missing observations.")
    if not daily.empty:
        all_brands = summarized(daily, "brand").sort_values("sales", ascending=False)
        options = all_brands["brand"].astype(str).tolist()
        suggested = [name for name in ["Northgate Sparkle", "Volt"] if name in options]
        if len(suggested) < 2:
            suggested = options[:2]
        chosen = st.multiselect("Brands to compare (up to 5)", options,
                                default=suggested, max_selections=5, key="brand_compare")
        if chosen:
            table = all_brands[all_brands["brand"].isin(chosen)]
            st.dataframe(table[["brand", "sales", "units", "avg_instock", "missing_instock_pct", "products", "stores"]]
                         .round(2), use_container_width=True, hide_index=True)
            export(table, "brand_comparison.csv", "brand_export")
            category_table = summarized(daily[daily["brand"].isin(chosen)], ["category_desc", "brand"])
            category_table["coverage_pct"] = 100 - category_table["missing_instock_pct"]
            lowobs = st.slider("Minimum observations per brand-category", 0, 1000, 100, step=50,
                               key="brand_minobs")
            category_table = category_table[category_table["obs"] >= lowobs]
            visible = category_table.dropna(subset=["avg_instock"])
            if not visible.empty:
                fig = px.bar(visible, x="category_desc", y="avg_instock", color="brand",
                             barmode="group", hover_data=["obs", "coverage_pct", "sales"],
                             labels={"category_desc": "Category", "avg_instock": "Observed in-stock (%)"},
                             title="Within-category availability comparison")
                fig.add_hline(y=reference, line_dash="dash", line_color=RED, opacity=.7)
                fig.update_layout(height=470)
                chart(fig)
                st.dataframe(category_table[["category_desc", "brand", "sales", "avg_instock", "coverage_pct", "obs"]]
                             .round(2), use_container_width=True, hide_index=True)
                export(category_table, "brand_by_category.csv", "brand_category_export")
            else:
                st.info("These brands have no comparable categories with observed availability in the selected date range.")
            st.caption("Each bar is an unweighted row average. Category-level controls reduce, but do not eliminate, product-mix differences.")
        else:
            st.info("Select brands above to compare.")
    else:
        st.info("No daily records match this selection.")

with priorities:
    st.subheader("Priority finder")
    st.markdown("Identify product-store or brand-store combinations with **meaningful recorded sales**, **adequate data coverage**, and **availability below the screening reference**.")
    st.caption("This is a diagnostic shortlist—not a ranking of lost revenue. The availability reference is adjustable and not a stated Walmart SLA.")
    a, b, c = st.columns(3)
    grain_name = a.selectbox("Investigate by", ["Brand × store", "Product × store", "Brand"], index=0)
    min_rows = b.number_input("Min. sampled rows per group", 1, 52, 10)
    min_cov = c.slider("Minimum availability coverage (%)", 0, 100, 75, 5)
    min_sales = st.slider("Minimum recorded sales ($)", 0, 100_000, 3_000, 1_000)
    grainer = {"Brand × store": ["brand", "store_id"],
               "Product × store": ["brand", "store_id", "item_id"], "Brand": ["brand"]}
    if not daily.empty:
        top = priority_view(daily, grainer[grain_name], min_rows, min_cov, min_sales, reference)
        st.metric("Screening candidates", f"{len(top):,}")
        if not top.empty:
            label_col = " | ".join(grainer[grain_name])
            top["entity"] = top[grainer[grain_name]].astype(str).agg(" / ".join, axis=1)
            scatter = px.scatter(top.head(500), x="avg_instock", y="sales", size="obs", size_max=40,
                                 hover_name="entity", color="gap_to_reference_pp",
                                 color_continuous_scale=[[0, "#A9D7F8"], [1, "#0A63AC"]],
                                 hover_data=["coverage_pct", "obs", "products"],
                                 title=f"{grain_name}: lower availability × larger sales footprint",
                                 labels={"avg_instock": "Observed in-stock (%)", "sales": "Recorded sales ($)",
                                         "gap_to_reference_pp": "Gap (pp)"})
            scatter.add_vline(x=reference, line_dash="dash", line_color=RED)
            chart(scatter)
            st.dataframe(top[grainer[grain_name] + ["sales", "units", "avg_instock", "gap_to_reference_pp", "coverage_pct", "obs"]]
                         .head(250).round(2), hide_index=True, use_container_width=True)
            export(top.drop(columns="entity"), "availability_priority_candidates.csv", "priority_export")
        else:
            st.info("No candidates satisfy the minimum observations, data-coverage, and recorded-sales thresholds. Relax one of the filters.")
    else:
        st.info("No sales rows in view.")

with stores_tab:
    st.subheader("Store performance explorer")
    if not daily.empty:
        store_summary = summarized(daily, "store_id").sort_values("avg_instock")
        left, right = st.columns(2, gap="large")
        with left:
            chart(stock_figure(store_summary, "store_id", "Availability by store", reference))
        with right:
            valid = store_summary.dropna(subset=["avg_instock"])
            fig = px.scatter(valid, x="avg_instock", y="sales", hover_name="store_id",
                             size="units", size_max=45, color_discrete_sequence=[BLUE],
                             labels={"avg_instock": "Availability (%)", "sales": "Recorded sales ($)"},
                             title="Sales footprint by store")
            fig.add_vline(x=reference, line_dash="dash", line_color=RED)
            fig.update_layout(height=410)
            chart(fig)
        st.dataframe(store_summary.round(2), hide_index=True, use_container_width=True)
        export(store_summary, "store_summary.csv", "store_export")
        st.subheader("Store × brand availability matrix")
        all_brand = summarized(daily, "brand").sort_values("sales", ascending=False)
        max_brands = st.slider("Number of high-selling brands", 5, min(25, len(all_brand)), min(12, len(all_brand))) if len(all_brand) >= 5 else len(all_brand)
        leading = all_brand["brand"].astype(str).head(max_brands)
        sb = summarized(daily[daily["brand"].isin(leading)], ["store_id", "brand"])
        if len(sb):
            matrix = sb.pivot(index="store_id", columns="brand", values="avg_instock")
            matrix = matrix.reindex(columns=leading.tolist())
            fig = px.imshow(matrix, aspect="auto", color_continuous_scale="Blues", zmin=70, zmax=100,
                            labels={"x": "Brand", "y": "Store", "color": "Observed %"},
                            title="Where are brand availability gaps concentrated?")
            fig.update_layout(height=590)
            chart(fig)
            st.caption("Blank cells denote missing availability. Heatmap reflects observed data only and is not demand weighted.")
        st.subheader("Trend by sampled observation date")
        by_date = daily.groupby("date", as_index=False, observed=True).agg(
            sales=("sales_amt", "sum"), availability=("instock_pct", "mean"))
        l, r = st.columns(2)
        with l:
            chart(px.line(by_date, x="date", y="sales", markers=True, color_discrete_sequence=[BLUE],
                          title="Recorded sales on sampled dates", labels={"date": "Sampled date", "sales": "Recorded sales ($)"}))
        with r:
            fig = px.line(by_date.dropna(subset=["availability"]), x="date", y="availability",
                          markers=True, color_discrete_sequence=[GREEN],
                          title="Observed in-stock availability over time", labels={"date": "Sampled date", "availability": "Observed in-stock (%)"})
            fig.add_hline(y=reference, line_dash="dash", line_color=RED)
            chart(fig)
    else:
        st.info("No daily records match this selection.")

with ftpr_tab:
    st.subheader("Online picking vs. shelf availability")
    st.caption("FTPR is summarized over its fixed 2026-08-09 → 2026-09-19 window. We aggregate sampled sales/in-stock observations to one store-item row before matching. The sales date filter does not affect these comparisons.")
    if not ftpr.empty:
        try:
            paired, window_start, window_end, n_window_rows = align_ftpr(base_daily, ftpr)
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Mean reported FTPR", fmt_pct(ftpr["ftpr_pct_display"].mean()))
            c2.metric("Mean pre-sub pick", fmt_pct(ftpr["presub_pick_rate_pct_display"].mean()))
            c3.metric("Mean nil-pick", fmt_pct(ftpr["nil_pick_rate_pct_display"].mean()))
            c4.metric("Matched store-items", fmt_pct(100 * paired["matched_daily_window"].mean()))
            st.caption("Rates above are unweighted averages of *published* store-item percentages; counts and rates can disagree in the perturbed case data.")
            left, right = st.columns(2, gap="large")
            with left:
                ftbrands = ftpr_summary(ftpr, "brand").sort_values("orders", ascending=False).head(15)
                fig = px.bar(ftbrands.sort_values("ftpr"), x="ftpr", y="brand", orientation="h",
                             color_discrete_sequence=[BLUE], title="FTPR for high-order-volume brands",
                             hover_data=["pairs", "orders", "ftpr_coverage_pct"],
                             labels={"ftpr": "Mean reported FTPR (%)", "brand": ""})
                fig.update_layout(height=525)
                chart(fig)
            with right:
                good = paired.dropna(subset=["window_instock", "ftpr_pct_display"])
                if len(good) > 4000:
                    good = good.sample(4000, random_state=17)
                if len(good):
                    fig = px.scatter(good, x="window_instock", y="ftpr_pct_display", color="category_desc",
                                     opacity=.4, hover_data=["brand", "store_id", "item_id", "order_qty"],
                                     title="Same-window availability vs. reported FTPR",
                                     labels={"window_instock": "Observed in-stock (%)", "ftpr_pct_display": "Reported FTPR (%)"})
                    fig.update_layout(height=525)
                    chart(fig)
                else:
                    st.info("No matched observations contain both FTPR and in-stock metrics.")
            st.subheader("Investigate individual store-item pairs")
            min_orders = st.slider("Minimum reported order quantity", 0, 250, 10, 5)
            inspect = paired[paired["order_qty"].ge(min_orders)].copy()
            names = [c for c in ["store_id", "item_id", "brand", "item_desc", "category_desc", "order_qty",
                                   "ftpr_pct_display", "nil_pick_rate_pct_display", "window_instock",
                                   "window_sales", "window_obs", "matched_daily_window"] if c in inspect]
            inspect = inspect.sort_values("ftpr_pct_display", na_position="last")
            st.dataframe(inspect[names].head(350).round(2), hide_index=True, use_container_width=True)
            export(inspect[names], "ftpr_window_aligned.csv", "ftpr_export")
            st.caption("The scatter is sampled for readability; the summary metrics and downloadable table use the full filtered dataset. Association does not establish causation.")
        except Exception as exc:
            st.error(f"FTPR alignment issue: {exc}")
    else:
        st.info("No FTPR observations match your filters.")

with ops_tab:
    st.subheader("Operational hypothesis testing · synthetic variables")
    st.info("Delivery schedules and merchandising minutes in the case are synthetic. Treat the relationships below as exploratory, not as operational facts or causal explanations.")
    if not daily.empty:
        left, right = st.columns(2, gap="large")
        with left:
            if "delivery_days_SYNTHETIC" in daily:
                days = daily["delivery_days_SYNTHETIC"].astype("string")
                v = daily[["instock_pct", "sales_amt"]].copy()
                v["n_delivery_days"] = days.map(lambda x: len(x.split(",")) if pd.notna(x) and x.strip() else np.nan)
                t = v.groupby("n_delivery_days", as_index=False).agg(
                    availability=("instock_pct", "mean"), obs=("instock_pct", "count"))
                if len(t.dropna(subset=["availability"])):
                    fig = px.bar(t.dropna(subset=["availability"]), x="n_delivery_days", y="availability",
                                 color_discrete_sequence=[BLUE], hover_data=["obs"],
                                 labels={"n_delivery_days": "Synthetic delivery days / week", "availability": "Observed in-stock (%)"},
                                 title="Availability vs. simulated delivery frequency")
                    chart(fig)
        with right:
            if "merchandiser_minutes_SYNTHETIC" in daily:
                v = daily[["instock_pct", "merchandiser_minutes_SYNTHETIC"]].dropna().copy()
                if len(v):
                    v["minutes_group"] = pd.cut(v["merchandiser_minutes_SYNTHETIC"],
                                                bins=[-1, 30, 60, 90, 120, np.inf],
                                                labels=["0–30", "31–60", "61–90", "91–120", "120+"])
                    t = v.groupby("minutes_group", as_index=False, observed=True).agg(
                        availability=("instock_pct", "mean"), obs=("instock_pct", "size"))
                    chart(px.bar(t, x="minutes_group", y="availability", hover_data=["obs"],
                                 color_discrete_sequence=[BLUE],
                                 labels={"minutes_group": "Synthetic merchandising minutes", "availability": "Observed in-stock (%)"},
                                 title="Availability vs. simulated merchandising time"))
        st.caption("Grouping does not adjust for demand, category mix, item selection, store characteristics or measurement quality.")
    else:
        st.info("No daily observations for these filters.")

with quality_tab:
    st.subheader("Can we trust these comparisons?")
    if not daily.empty:
        q = summarized(daily, "category_desc")
        q = q.sort_values("missing_instock_pct", ascending=False)
        st.dataframe(q[["category_desc", "obs", "available_obs", "missing_instock_pct", "sales"]]
                     .round(2), use_container_width=True, hide_index=True)
        fig = px.bar(q.sort_values("missing_instock_pct"), x="missing_instock_pct", y="category_desc",
                     orientation="h", color_discrete_sequence=[BLUE],
                     labels={"missing_instock_pct": "Missing observed in-stock (%)", "category_desc": ""},
                     title="In-stock coverage varies sharply by product category")
        chart(fig)
        st.metric("Missing sales values", fmt_pct(100 * daily["sales_amt"].isna().mean()))
    mismatches = mismatch_stats(ftpr) if len(ftpr) else None
    if mismatches is not None:
        st.warning(f"Reported FTPR disagrees with numerator ÷ denominator by over 1 pp in "
                   f"{mismatches['pct_off_gt_1pp']:.1f}% of {mismatches['n']:,} comparable store-item rows. "
                   "The dashboard reports provided rates; reconstructed counts are not treated as authoritative.")
    st.markdown("""**Interpretation guide**
- Case data is deidentified and perturbed; reported sales are not actual Walmart financial results.
- Store × item × sampled weekly-date grain means trend lines reflect sampled observations, **not continuous daily sales**.
- Reported in-stock averages exclude missing data and are not demand weighted or mix adjusted.
- Some categories, notably CSD SINGLES, have 100% missing in-stock metrics.
- FTPR uses a separate six-week period, and synthetic operational fields are hypothesis generators only.
- Availability screening thresholds and priority filters are **exploratory**, not estimates of sales uplift or confirmed targets.
""")

st.divider()
st.caption("Fixing the Fizz · Academic consulting prototype · Source files are not bundled with this app · Dashboard code is read-only")
