"""Fixing the Fizz — McCombs consulting dashboard (read-only local prototype)."""
from __future__ import annotations
import io
from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st

from analysis import align_ftpr, ftpr_summary, load_daily, load_ftpr, mismatch_stats, summarized

st.set_page_config(page_title='Fixing the Fizz | DSD Performance', page_icon='🥤', layout='wide')
BASE = Path(__file__).parent
DATA = BASE / 'data'
DAILY_PATH = DATA / 'sparkle_case_daily_sales_instock.csv'
FTPR_PATH = DATA / 'sparkle_case_ftpr_summary.csv'

@st.cache_data(show_spinner='Loading the daily case file...', max_entries=2)
def cached_daily(raw: bytes):
    return load_daily(io.BytesIO(raw))

@st.cache_data(show_spinner='Loading the FTPR summary...', max_entries=2)
def cached_ftpr(raw: bytes):
    return load_ftpr(io.BytesIO(raw))

@st.cache_data(show_spinner='Matching FTPR to same-window weekly data...', max_entries=2)
def cached_paired(daily: pd.DataFrame, ftpr: pd.DataFrame):
    return align_ftpr(daily, ftpr)


def load_input(path: Path, caption: str, key: str):
    if path.is_file():
        st.sidebar.success(f'{caption} loaded from local data/')
        return path.read_bytes()
    uploaded = st.sidebar.file_uploader(caption, type=['csv'], key=key)
    return uploaded.getvalue() if uploaded is not None else None


def apply_filters(df: pd.DataFrame, categories, brands, stores):
    if categories:
        df = df[df['category_desc'].isin(categories)]
    if brands:
        df = df[df['brand'].isin(brands)]
    if stores:
        df = df[df['store_id'].isin(stores)]
    return df


def download_df(label, df, filename, key):
    st.download_button(label, df.to_csv(index=False).encode('utf-8'), file_name=filename,
                       mime='text/csv', key=key)


def chart(fig):
    st.plotly_chart(fig, use_container_width=True)


st.title('🥤 Fixing the Fizz')
st.caption('Retail DSD diagnostic dashboard | Deidentified & perturbed academic case data | Interactive prototype')
st.warning('AUTHORIZED PROJECT DATA ONLY. Keep source CSV files private. Obtain client/sponsor approval before external hosting or sharing.')

st.sidebar.header('Data sources')
daily_raw = load_input(DAILY_PATH, '1 · Daily sales and inventory CSV', 'daily_upload')
ftpr_raw = load_input(FTPR_PATH, '2 · FTPR summary CSV', 'ftpr_upload')
if daily_raw is None or ftpr_raw is None:
    st.info('To begin, upload **both** case CSVs in the sidebar, or put both files in a local `data/` folder. See README.md for details.')
    st.stop()

try:
    daily_full = cached_daily(daily_raw)
    ftpr_full = cached_ftpr(ftpr_raw)
except Exception as e:
    st.error(f'Could not load the files: {e}')
    st.stop()

st.sidebar.header('Shared filters')
categories = st.sidebar.multiselect('Category', sorted(daily_full['category_desc'].dropna().astype(str).unique()))
brands = st.sidebar.multiselect('Brand', sorted(daily_full['brand'].dropna().astype(str).unique()))
stores = st.sidebar.multiselect('Store', sorted(daily_full['store_id'].dropna().astype(str).unique()))

# These dimension filters affect both sources. Date filter affects ONLY the year-long daily analytics.
daily_base = apply_filters(daily_full, categories, brands, stores)
ftpr = apply_filters(ftpr_full, categories, brands, stores)

valid_dates = daily_full['date'].dropna()
dmin, dmax = valid_dates.min().date(), valid_dates.max().date()
dates = st.sidebar.date_input('Daily-sales date filter', value=(dmin, dmax), min_value=dmin, max_value=dmax)
daily = daily_base
if isinstance(dates, (tuple, list)) and len(dates) == 2:
    daily = daily[daily['date'].between(pd.Timestamp(dates[0]), pd.Timestamp(dates[1]))]

if daily.empty and ftpr.empty:
    st.warning('No data for this filter combination. Try relaxing your category, brand, or store filters.')
    st.stop()

col1, col2, col3, col4, col5 = st.columns(5)
col1.metric('Sales in selected period', f"${daily['sales_amt'].sum():,.0f}" if not daily.empty else '—')
col2.metric('Units sold', f"{daily['unit_qty'].sum():,.0f}" if not daily.empty else '—')
in_stock = daily['instock_pct'].mean() if not daily.empty else float('nan')
col3.metric('Avg. observed in-stock', f'{in_stock:.1f}%' if pd.notna(in_stock) else 'N/A')
col4.metric('In-stock field coverage', f"{daily['instock_pct'].notna().mean()*100:.1f}%" if not daily.empty else '—')
col5.metric('Selected brands', str(daily['brand'].nunique() if not daily.empty else ftpr['brand'].nunique()))
st.caption('Top-line sales and in-stock figures use the daily-sales date picker; the FTPR tab uses its own fixed six-week window. Availability is an unweighted average of observed rows and excludes missing values.')

overview, brands_tab, stores_tab, ftpr_tab, ops_tab, quality_tab = st.tabs([
    'Overview', 'Brands', 'Stores & trends', 'FTPR ↔ In-stock', 'Operations (synthetic)', 'Data quality'
])

with overview:
    st.subheader('Category sales and availability')
    if not daily.empty:
        cats = summarized(daily, 'category_desc').sort_values('sales', ascending=False)
        l, r = st.columns(2)
        with l:
            fig = px.bar(cats, x='sales', y='category_desc', orientation='h',
                         labels={'sales': 'Recorded sales ($)', 'category_desc': ''},
                         hover_data=['units', 'avg_instock', 'missing_instock_pct'])
            fig.update_layout(yaxis={'categoryorder': 'total ascending'}, title='Recorded sales by category')
            chart(fig)
        with r:
            present = cats.dropna(subset=['avg_instock'])
            fig = px.bar(present, x='avg_instock', y='category_desc', orientation='h',
                         labels={'avg_instock': 'Observed in-stock (%)', 'category_desc': ''},
                         hover_data=['missing_instock_pct', 'obs'])
            fig.update_layout(yaxis={'categoryorder': 'total descending'}, title='Availability by category')
            chart(fig)
        st.dataframe(cats.round(2), use_container_width=True, hide_index=True)
        download_df('Download category summary', cats, 'category_summary.csv', 'export_cats')
    else:
        st.info('No daily observations match these filters and dates.')

with brands_tab:
    st.subheader('Brand intelligence')
    if not daily.empty:
        all_brands = summarized(daily, 'brand').sort_values('sales', ascending=False)
        options = all_brands['brand'].astype(str).tolist()
        defaults = [x for x in ('Northgate Sparkle', 'Volt') if x in options] or options[:2]
        selected = st.multiselect('Highlight brand(s)', options, default=defaults, key='brands_compare')
        chosen = all_brands[all_brands['brand'].isin(selected)] if selected else all_brands
        fig = px.scatter(chosen.dropna(subset=['avg_instock']), x='avg_instock', y='sales',
                         color='brand', size='units', size_max=48, hover_name='brand',
                         hover_data=['products', 'stores', 'missing_instock_pct'],
                         labels={'avg_instock': 'Observed in-stock (%)', 'sales': 'Recorded sales ($)'},
                         title='Sales vs. observed availability (not mix-adjusted)')
        chart(fig)
        st.dataframe(chosen.round(2), hide_index=True, use_container_width=True)
        download_df('Download brand summary', chosen, 'brand_comparison.csv', 'export_brands')
        if selected:
            split = summarized(daily[daily['brand'].isin(selected)], ['brand', 'category_desc'])
            fig = px.bar(split.dropna(subset=['avg_instock']), x='category_desc', y='avg_instock',
                         color='brand', barmode='group',
                         hover_data=['sales', 'obs', 'missing_instock_pct'],
                         labels={'category_desc': 'Category', 'avg_instock': 'Observed in-stock (%)'},
                         title='Within-category brand comparison')
            chart(fig)
            st.caption('Compare similar categories before interpreting raw brand-level gaps. Products and missingness still differ within categories.')
    else:
        st.info('No daily observations to compare.')

with stores_tab:
    st.subheader('Store explorer')
    if not daily.empty:
        stores_summary = summarized(daily, 'store_id').sort_values('avg_instock', ascending=True)
        l, r = st.columns(2)
        with l:
            chart(px.bar(stores_summary, x='store_id', y='avg_instock',
                         labels={'store_id': 'Store', 'avg_instock': 'Average observed in-stock (%)'},
                         title='Store availability ranking'))
        with r:
            chart(px.scatter(stores_summary.dropna(subset=['avg_instock']), x='avg_instock', y='sales',
                             size='units', hover_name='store_id',
                             title='Store sales vs. availability',
                             labels={'avg_instock':'Observed in-stock (%)', 'sales':'Recorded sales ($)'}))
        st.dataframe(stores_summary.round(2), use_container_width=True, hide_index=True)
        download_df('Download store summary', stores_summary, 'store_summary.csv', 'export_stores')
        st.subheader('Store × brand availability heatmap')
        sb = summarized(daily, ['store_id', 'brand'])
        top = summarized(daily, 'brand').nlargest(12, 'sales')['brand'].astype(str).tolist()
        heat = sb[sb['brand'].isin(top)].pivot(index='store_id', columns='brand', values='avg_instock')
        fig = px.imshow(heat, color_continuous_scale='RdYlGn', aspect='auto',
                        labels={'x':'Brand', 'y':'Store', 'color':'In-stock %'},
                        title='Top-selling brands, average observed availability')
        chart(fig)
        st.subheader('Weekly sampled sales trends')
        trend = daily.groupby('date', as_index=False).agg(sales=('sales_amt','sum'), instock=('instock_pct','mean'))
        chart(px.line(trend, x='date', y='sales', markers=True,
                      title='Sales on sampled observation dates (not continuous daily data)'))
    else:
        st.info('No daily observations for this date range.')

with ftpr_tab:
    st.subheader('FTPR and inventory availability: aligned six-week analysis')
    st.info('The FTPR file summarizes **Aug 9–Sep 19, 2026**. This tab deliberately ignores the daily-sales date filter, but respects category, brand, and store filters. Daily records are aggregated first to one store/product row inside the FTPR period, preventing double-counting.')
    if not ftpr.empty:
        try:
            aligned, start, end, days_rows = cached_paired(daily_base, ftpr)
            match = aligned['matched_daily_window'].mean() * 100
            ftp_mean = ftpr['ftpr_pct_display'].mean()
            presub_mean = ftpr['presub_pick_rate_pct_display'].mean()
            nil_mean = ftpr['nil_pick_rate_pct_display'].mean()
            a, b, c, d = st.columns(4)
            a.metric('Mean reported FTPR', f'{ftp_mean:.1f}%' if pd.notna(ftp_mean) else 'N/A')
            b.metric('Mean pre-substitution rate', f'{presub_mean:.1f}%' if pd.notna(presub_mean) else 'N/A')
            c.metric('Mean nil-pick rate', f'{nil_mean:.1f}%' if pd.notna(nil_mean) else 'N/A')
            d.metric('Paired observations matched', f'{match:.1f}%')
            st.caption(f'Window: {start.date()} – {end.date()}. Rates are **unweighted arithmetic means of provided store-item percentages**, not order-weighted metrics; excluded null rates remain missing.')
            l, r = st.columns(2)
            with l:
                s = ftpr_summary(ftpr, 'brand').sort_values('orders', ascending=False).head(20)
                chart(px.bar(s, y='brand', x='ftpr', orientation='h', title='Mean FTPR across leading brands',
                             hover_data=['pairs', 'orders', 'ftpr_coverage_pct'],
                             labels={'ftpr':'Reported FTPR (%)', 'brand':''}))
            with r:
                sample = aligned.dropna(subset=['window_instock','ftpr_pct_display'])
                if len(sample) > 4500:
                    sample = sample.sample(4500, random_state=11)
                if not sample.empty:
                    chart(px.scatter(sample, x='window_instock', y='ftpr_pct_display',
                                     color='category_desc', opacity=0.46,
                                     hover_data=['brand', 'store_id', 'item_id'],
                                     title='Paired availability vs. FTPR (exploratory)',
                                     labels={'window_instock':'Same-window observed in-stock (%)',
                                             'ftpr_pct_display':'Reported FTPR (%)'}))
            st.caption('Scatter visualizes at most 4,500 sampled store-item pairs for responsiveness. All summary metrics use the complete filtered records. Correlation does not establish causation.')
            st.subheader('Store-item investigation table')
            min_orders = st.slider('Minimum order quantity', min_value=0, max_value=100, value=10, step=5)
            inspect = aligned.loc[aligned['order_qty'].ge(min_orders)].copy()
            columns = [c for c in ['store_id','item_id','brand','item_desc','category_desc',
                                    'order_qty','ftpr_pct_display','nil_pick_rate_pct_display',
                                    'window_instock','window_sales','window_obs',
                                    'matched_daily_window'] if c in inspect.columns]
            inspect = inspect.sort_values('ftpr_pct_display', na_position='last')
            st.dataframe(inspect[columns].head(300).round(2), hide_index=True, use_container_width=True)
            download_df('Download aligned records', inspect[columns], 'ftpr_sales_aligned.csv','export_ftpr')
        except Exception as exc:
            st.error(f'Could not align filtered records: {exc}')
    else:
        st.info('No FTPR pairs for the selected category, brand and store filters.')

with ops_tab:
    st.subheader('Operational diagnostics — synthetic fields')
    st.warning('Delivery-day and merchandising fields are simulated (_SYNTHETIC). These charts support hypothesis generation only; they do not prove operational root causes or causal uplift.')
    if not daily.empty:
        if 'delivery_days_SYNTHETIC' in daily.columns:
            days = daily['delivery_days_SYNTHETIC'].astype('string')
            tmp = daily[['instock_pct', 'sales_amt']].copy()
            tmp['deliveries_per_week_synthetic'] = days.map(lambda v: len(v.split(',')) if pd.notna(v) and v.strip() else None)
            dp = tmp.groupby('deliveries_per_week_synthetic', dropna=False).agg(
                avg_instock=('instock_pct','mean'), sales=('sales_amt','sum'), rows=('sales_amt','size')).reset_index()
            chart(px.bar(dp.dropna(subset=['deliveries_per_week_synthetic']),
                         x='deliveries_per_week_synthetic', y='avg_instock',
                         labels={'deliveries_per_week_synthetic':'Listed synthetic delivery days/week',
                                 'avg_instock':'Observed in-stock (%)'},
                         title='Availability vs. listed delivery days'))
        if 'merchandiser_minutes_SYNTHETIC' in daily.columns:
            tmp = daily[['instock_pct','merchandiser_minutes_SYNTHETIC']].dropna().copy()
            if len(tmp):
                tmp['minutes_bin'] = pd.cut(tmp['merchandiser_minutes_SYNTHETIC'], bins=[-1,30,60,90,120,100000],
                                            labels=['0–30','31–60','61–90','91–120','120+'])
                bt = tmp.groupby('minutes_bin', observed=True).agg(avg_instock=('instock_pct','mean'),
                                                                    obs=('instock_pct','size')).reset_index()
                chart(px.bar(bt, x='minutes_bin', y='avg_instock', hover_data=['obs'],
                             labels={'minutes_bin':'Synthetic merchandising minutes',
                                     'avg_instock':'Observed in-stock (%)'},
                             title='Availability vs. synthetic merchandising time'))
    else:
        st.info('No daily records available for operations charts.')

with quality_tab:
    st.subheader('Coverage, missingness, and reconciliation')
    if not daily.empty:
        q = summarized(daily, 'category_desc').sort_values('missing_instock_pct',ascending=False)
        st.dataframe(q[['category_desc','obs','available_obs','missing_instock_pct','sales']].round(2),
                     use_container_width=True, hide_index=True)
        chart(px.bar(q, x='category_desc', y='missing_instock_pct',
                     title='Missing in-stock percentages by category',
                     labels={'category_desc':'Category', 'missing_instock_pct':'Missing in-stock values (%)'}))
        st.caption(f"Missing sales: {daily['sales_amt'].isna().mean()*100:.2f}% of filtered sampled rows.")
    mismatches = mismatch_stats(ftpr)
    if mismatches:
        st.warning(f"In {mismatches['pct_off_gt_1pp']:.1f}% of {mismatches['n']:,} valid FTPR rows, the provided rate differs by more than 1 percentage point from the numerator/denominator ratio. Because case figures are perturbed, this dashboard uses the published per-row rate rather than presenting reconstructed counts as exact.")
    st.markdown('**Important interpretive limits**: Observed availability is not weighted by sales or demand; CSD SINGLES has no valid in-stock field in the supplied file; FTPR uses a different time grain and period; all financial numbers are synthetic/perturbed and are not real Walmart financials.')

st.divider()
st.caption('Fixing the Fizz · Read-only analysis prototype · No automatic cloud uploads or external data connections.')
