"""Fixing the Fizz v4 | Tableau-inspired Streamlit dashboard.

Viewer uploads both CSVs anew each browser session. Data is processed by the
Streamlit server; never put source data in a public repository. Metrics are
exploratory and should not be mistaken for client-defined service targets.
"""
from __future__ import annotations

import io

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from analysis import align_ftpr, ftpr_summary, load_daily, load_ftpr, mismatch_stats, summarized
from visuals import (
    BLUE, GOLD, GRAY, NAVY, ORANGE, RED, TEAL,
    availability_matrix, metric_color, opportunity_scatter, ranked_bars,
    style_plot, style_ratings,
)

st.set_page_config(page_title='Fixing the Fizz | DSD Decision Lab v4',
                   page_icon='🥤', layout='wide', initial_sidebar_state='expanded')

st.markdown('''<style>
.block-container {max-width: 1600px; padding-top: 1.05rem; padding-bottom: 2rem;}
[data-testid="stSidebar"] {background-color:#F3F7FC;}
[data-testid="stMetric"] {border:1px solid #E3EAF4; background:#FFF; border-radius:13px; padding:13px 14px 10px; box-shadow:0 3px 12px rgba(18,61,106,.04);}
[data-testid="stMetricLabel"] {font-size:.79rem; font-weight:700; color:#576C83;}
[data-testid="stMetricValue"] {font-size:1.55rem; font-weight:750; color:#15375B;}
[data-testid="stTabs"] button[role="tab"] {font-weight:700; font-size:.94rem;}
.hero {padding:22px 27px; border-radius:15px; background:linear-gradient(110deg,#123A65,#0071CE); color:white; margin-bottom:15px;}
.hero h1 {font-size:1.95rem; line-height:1.15; color:#FFF; margin:4px 0 4px;}
.hero p {font-size:.88rem; color:#DFEEFF; margin:0;}
.pill {display:inline-block; padding:3px 9px; background:#FFC220; color:#193A63; font-weight:750; font-size:.66rem; letter-spacing:.06em; border-radius:99px;}
.legend {display:flex; flex-wrap:wrap; align-items:center; gap:12px; margin:6px 0 13px; font-size:.78rem; color:#47607A;}
.legend span {display:inline-flex; align-items:center; gap:5px;}
.dot {height:11px; width:11px; display:inline-block; border-radius:3px;}
.section-head {border-bottom:1px solid #E5EBF3; padding-bottom:7px; margin-top:9px;}
</style>''', unsafe_allow_html=True)

@st.cache_data(scope='session', show_spinner='Reading daily sales file…', max_entries=1)
def parse_daily(data: bytes) -> pd.DataFrame:
    return load_daily(io.BytesIO(data))

@st.cache_data(scope='session', show_spinner='Reading FTPR file…', max_entries=1)
def parse_ftpr(data: bytes) -> pd.DataFrame:
    return load_ftpr(io.BytesIO(data))


def percent(value):
    return f'{value:.1f}%' if pd.notna(value) else '—'


def cash(value):
    if not pd.notna(value):
        return '—'
    x = float(value)
    if abs(x) >= 1e6:
        return f'${x/1e6:,.2f}M'
    if abs(x) >= 1e3:
        return f'${x/1e3:,.1f}K'
    return f'${x:,.0f}'


def pct_coverage(frame):
    return 100*frame['instock_pct'].notna().mean() if len(frame) else np.nan


def plot(fig, key=None):
    st.plotly_chart(fig, use_container_width=True, key=key)


def save_table(table, fname, key):
    st.download_button('↓ Export filtered CSV', table.to_csv(index=False).encode('utf-8'),
                       file_name=fname, mime='text/csv', key=key,
                       help='Downloaded data may be case-restricted; handle securely.')


def table_view(frame, cols, color_metrics=None, coverage='coverage_pct', threshold=0, key=None):
    view=frame[cols].copy()
    styled=style_ratings(view, color_metrics or {},
                         coverage_col=coverage if coverage in view else None,
                         min_coverage=threshold)
    st.dataframe(styled, hide_index=True, use_container_width=True, key=key)


def legend(metric='availability'):
    if metric=='nil':
        bands=[('0–1% · best',BLUE),('1–2%',TEAL),('2–5%',GOLD),('5–10%',ORANGE),('10%+ · worst',RED)]
    else:
        bands=[('<70% · critical',RED),('70–80%',ORANGE),('80–90%',GOLD),('90–95%',TEAL),('95%+ · strong',BLUE)]
    parts=''.join(f'<span><i class="dot" style="background:{c}"></i>{label}</span>' for label,c in bands)
    st.markdown(f'<div class="legend">{parts}<span><i class="dot" style="background:{GRAY}"></i>Missing / low coverage</span></div>',
                unsafe_allow_html=True)


def plot_sales_bars(frame,label='category_desc',title='Recorded sales by category',limit=12):
    shown=frame.sort_values('sales',ascending=False).head(limit).sort_values('sales')
    fig=go.Figure(go.Bar(x=shown['sales'],y=shown[label].astype(str),orientation='h',
                         marker_color=BLUE,text=[cash(x) for x in shown['sales']],
                         textposition='outside',cliponaxis=False,
                         customdata=shown[['units','obs']].to_numpy(),
                         hovertemplate='<b>%{y}</b><br>Sales: $%{x:,.0f}<br>Units: %{customdata[0]:,.0f}<br>Observations: %{customdata[1]:,.0f}<extra></extra>'))
    fig.update_layout(title=title,showlegend=False)
    fig.update_xaxes(title='Recorded sales ($)',tickprefix='$')
    fig.update_yaxes(title='',automargin=True)
    return style_plot(fig,height=max(350,55+42*len(shown)))


def time_lines(frame,reference):
    by_date=frame.groupby('date',observed=True,as_index=False).agg(
        sales=('sales_amt','sum'), availability=('instock_pct','mean'),
        coverage=('instock_pct',lambda x: x.notna().mean()*100))
    c1,c2=st.columns(2,gap='large')
    with c1:
        f=go.Figure(go.Scatter(x=by_date['date'],y=by_date['sales'],mode='lines+markers',
                               line=dict(color=BLUE,width=2),marker=dict(size=7),
                               hovertemplate='%{x|%b %d, %Y}<br>Sales: $%{y:,.0f}<extra></extra>'))
        f.update_layout(title='Recorded sales on sampled dates')
        f.update_xaxes(title='Sampled date')
        f.update_yaxes(title='Recorded sales ($)',tickprefix='$')
        plot(style_plot(f,390))
    with c2:
        d=by_date.dropna(subset=['availability'])
        f=go.Figure(go.Scatter(x=d['date'],y=d['availability'],mode='lines+markers',
                               line=dict(color='#8193A5',width=2),
                               marker=dict(color=[metric_color(v) for v in d['availability']],size=10,line=dict(color='white',width=1)),
                               customdata=d['coverage'].to_numpy(),
                               hovertemplate='%{x|%b %d, %Y}<br>Availability: %{y:.1f}%<br>Coverage: %{customdata:.1f}%<extra></extra>'))
        f.add_hline(y=reference,line_dash='dot',line_color=NAVY)
        f.update_layout(title='Availability on sampled dates')
        f.update_yaxes(title='Observed in-stock (%)',range=[0,102],ticksuffix='%')
        f.update_xaxes(title='Sampled date')
        plot(style_plot(f,390))
    st.caption('These are weekly sampled observations, not continuous daily sales. Trends are descriptive, not causal.')


def reset_filters():
    for key in ['categories','brands','stores','vendors','dates']:
        st.session_state.pop(key,None)
    st.rerun()

# ---------- Header + data entry ----------
st.markdown('''<div class="hero"><span class="pill">McCOMBS × RETAIL DSD · DECISION LAB V4</span>
<h1>🥤 Fixing the Fizz</h1><p>Turn store-level availability, brand economics, and online fulfillment into clear investigation priorities.</p></div>''',
unsafe_allow_html=True)

st.sidebar.title('Data & filters')
st.sidebar.caption('Upload each CSV when opening a new session. Files are processed on this app’s server; external cloud use needs sponsor approval.')
upload_daily=st.sidebar.file_uploader('1 · Daily sales and inventory',type=['csv'],key='file_daily')
upload_ftpr=st.sidebar.file_uploader('2 · FTPR summary',type=['csv'],key='file_ftpr')
if upload_daily is None or upload_ftpr is None:
    st.info('Upload both CSVs in the sidebar to open the interactive dashboard. No case datasets are embedded in this code.')
    st.caption('V4 adds red-to-blue performance grading, sortable leaderboards, brand comparisons, a store × brand heatmap, and an opportunity quadrant.')
    st.stop()
try:
    full_daily=parse_daily(upload_daily.getvalue())
    full_ftpr=parse_ftpr(upload_ftpr.getvalue())
except Exception as exc:
    st.error(f'CSV loading issue: {exc}')
    st.stop()

st.sidebar.divider()
st.sidebar.button('↺ Reset dimension & date filters',use_container_width=True,on_click=reset_filters)
category_values=sorted(full_daily['category_desc'].dropna().astype(str).unique().tolist())
brand_values=sorted(full_daily['brand'].dropna().astype(str).unique().tolist())
store_values=sorted(full_daily['store_id'].dropna().astype(str).unique().tolist())
vendor_values=sorted(full_daily['vendor'].dropna().astype(str).unique().tolist())
selected_categories=st.sidebar.multiselect('Category',category_values,key='categories',placeholder='All categories')
selected_brands=st.sidebar.multiselect('Brand',brand_values,key='brands',placeholder='All brands')
selected_stores=st.sidebar.multiselect('Store',store_values,key='stores',placeholder='All 30 stores')
selected_vendors=st.sidebar.multiselect('Vendor',vendor_values,key='vendors',placeholder='All vendors')

# Category-aligned strings are only compared on dimensions; no raw row-level FTPR joins.
def filtered(frame):
    for column,selections in [('category_desc',selected_categories),('brand',selected_brands),
                              ('store_id',selected_stores),('vendor',selected_vendors)]:
        if selections:
            frame=frame[frame[column].isin(selections)]
    return frame

all_filtered=filtered(full_daily)
ftpr=filtered(full_ftpr)
d0=full_daily['date'].min().date()
d1=full_daily['date'].max().date()
chosen_dates=st.sidebar.date_input('Sales observation dates',(d0,d1),min_value=d0,max_value=d1,key='dates')
daily=all_filtered
if isinstance(chosen_dates,(list,tuple)) and len(chosen_dates)==2:
    daily=daily[daily['date'].between(pd.Timestamp(chosen_dates[0]),pd.Timestamp(chosen_dates[1]))]

st.sidebar.divider()
reference=st.sidebar.slider('Screening reference: in-stock / FTPR',70,100,95,1,
    help='Illustrative analytical reference, NOT a client-defined service-level objective.')
min_coverage=st.sidebar.slider('Minimum rate data coverage',0,100,70,5,
    help='Cells below this coverage are shown as missing in graded charts.')
rate_sort=st.sidebar.radio('Rate leaderboard order',['Worst first','Best first'],horizontal=True)
worst_first=rate_sort=='Worst first'
st.sidebar.caption('FTPR calculations always use the full FTPR six-week window; the sales-date filter only affects sampled-date charts and summaries.')

if daily.empty and ftpr.empty:
    st.warning('No records match your filters. Reset or widen your selections.')
    st.stop()

k1,k2,k3,k4,k5=st.columns(5,gap='small')
k1.metric('Recorded sales · sampled dates',cash(daily['sales_amt'].sum()) if len(daily) else '—')
k2.metric('Units sold',f'{daily["unit_qty"].sum():,.0f}' if len(daily) else '—')
k3.metric('Observed in-stock',percent(daily['instock_pct'].mean()) if len(daily) else '—')
k4.metric('In-stock data coverage',percent(pct_coverage(daily)))
k5.metric('Brands selected',str(daily['brand'].nunique()))
st.caption('Sales reflect the 52 **sampled observation dates**, not 365 daily totals. Availability and reported FTPR averages are unweighted; missing rates are excluded. Rates and dollars are perturbed case figures.')

st.markdown('**Performance legend** · Higher is better for in-stock, FTPR, and pre-substitution pick rate. Thresholds are exploratory, not official Walmart targets.')
legend()

# ---------- Views ----------
views=st.tabs(['Executive overview','Brand comparison','Store × brand heatmap',
               'Opportunity finder','FTPR & picking','Trends & operations','Data quality'])

with views[0]:
    st.subheader('Executive overview')
    if len(daily):
        by_category=summarized(daily,'category_desc')
        by_category['coverage_pct']=100-by_category['missing_instock_pct']
        left,right=st.columns([1.1,1],gap='large')
        with left:
            plot(plot_sales_bars(by_category))
        with right:
            graph,used=ranked_bars(by_category,'category_desc','avg_instock',
                'Availability by category',ascending=worst_first,
                min_coverage=min_coverage,reference=reference,max_items=12)
            plot(graph)
            if len(used)<len(by_category):
                st.caption(f'{len(by_category)-len(used)} categories excluded from graded chart due to missing rates or coverage filter.')
        st.markdown('#### Opportunity quadrant')
        st.caption('Top-left = greater recorded sales and lower observed availability. This identifies **investigation candidates**, not lost revenue.')
        by_brand=summarized(daily,'brand')
        by_brand['coverage_pct']=100-by_brand['missing_instock_pct']
        fig,observed=opportunity_scatter(by_brand,'brand',reference,min_coverage,
                    title='Brand sales footprint vs. observed availability')
        if len(observed):
            plot(fig)
            st.caption('Bubble area corresponds to units sold. Gray/insufficient data are excluded; vertical guide is the adjustable screening reference, horizontal guide is median sales.')
        else:
            st.info('No sufficiently observed brand rates for this filter. Reduce the coverage requirement.')
        save_table(by_brand,'v4_brand_overview.csv','overview_export')
    else:
        st.info('No sampled daily observations selected.')

with views[1]:
    st.subheader('Brand comparison explorer')
    st.caption('Compare up to five brands, then drill down within shared categories. Bars encode performance, not brand identity.')
    if len(daily):
        brands=summarized(daily,'brand').sort_values('sales',ascending=False)
        options=brands['brand'].astype(str).tolist()
        defaults=[b for b in ['Northgate Sparkle','Volt'] if b in options]
        defaults=list(dict.fromkeys(defaults+options))[:2]
        compared=st.multiselect('Brands for head-to-head comparison',options,default=defaults,
                                max_selections=5,key='compare_brands')
        if compared:
            chosen=brands[brands['brand'].astype(str).isin(compared)].copy()
            chosen['coverage_pct']=100-chosen['missing_instock_pct']
            fig,used=ranked_bars(chosen,'brand','avg_instock','Observed brand availability',
                ascending=worst_first,reference=reference,min_coverage=min_coverage,max_items=5)
            plot(fig)
            cols=['brand','sales','units','avg_instock','coverage_pct','obs','products','stores']
            table_view(chosen,cols,{'avg_instock':'availability'},threshold=min_coverage)
            save_table(chosen,'v4_brand_compare.csv','compare_export')
            st.markdown('#### Product category drilldown')
            cat=summarized(daily[daily['brand'].isin(compared)],['category_desc','brand'])
            cat['coverage_pct']=100-cat['missing_instock_pct']
            cat_min=st.number_input('Minimum observed rows per brand-category',min_value=0,max_value=10000,value=100,step=50,key='cat_obs')
            cat=cat[cat['obs']>=cat_min]
            valid=cat[cat['coverage_pct'].ge(min_coverage) & cat['avg_instock'].notna()].copy()
            if len(valid):
                fig=go.Figure()
                for b in compared:
                    rows=valid[valid['brand'].astype(str).eq(b)].sort_values('category_desc')
                    if len(rows):
                        fig.add_bar(name=b,x=rows['category_desc'].astype(str),y=rows['avg_instock'],
                            marker_color=[metric_color(x) for x in rows['avg_instock']],
                            customdata=np.stack([rows['coverage_pct'],rows['obs'],rows['sales']],axis=1),
                            hovertemplate=f'<b>{b}</b><br>Category: %{{x}}<br>Availability: %{{y:.1f}}%'
                                          '<br>Coverage: %{customdata[0]:.1f}%<br>Observations: %{customdata[1]:,.0f}'
                                          '<br>Recorded sales: $%{customdata[2]:,.0f}<extra></extra>')
                fig.add_hline(y=reference,line_dash='dot',line_color=NAVY)
                fig.update_layout(barmode='group',title='Availability within product categories')
                fig.update_xaxes(title='Product category',tickangle=-20)
                fig.update_yaxes(range=[0,104],title='Observed in-stock (%)',ticksuffix='%')
                plot(style_plot(fig,490))
                table_view(cat,['category_desc','brand','sales','avg_instock','coverage_pct','obs'],
                    {'avg_instock':'availability'},threshold=min_coverage)
                save_table(cat,'v4_brand_categories.csv','categories_export')
            else:
                st.info('No brand-category cells meet current observation and coverage thresholds.')
            st.caption('Within-category grouping reduces, but does not eliminate, differences in item and assortment mix.')
        else:
            st.info('Choose a brand above.')
    else:
        st.info('No daily records for this selection.')

with views[2]:
    st.subheader('Store × brand heatmap')
    st.caption('Every colored cell represents a measured in-stock rate. Gray cells indicate missing or insufficiently covered data.')
    if len(daily):
        ordered=summarized(daily,'brand').sort_values('sales',ascending=False)
        names=ordered['brand'].astype(str).tolist()
        n=st.slider('Number of brands (top-selling)',min_value=1,max_value=min(25,len(names)),
                    value=min(12,len(names)),key='heat_brand_count')
        selected=names[:n]
        store_brand=summarized(daily[daily['brand'].isin(selected)],['store_id','brand'])
        store_order=st.selectbox('Order stores by',['Store ID','Lowest availability first','Highest availability first'],key='heat_order')
        fig,matrix=availability_matrix(store_brand,selected,min_coverage)
        if store_order!='Store ID':
            rows=summarized(daily,'store_id').dropna(subset=['avg_instock'])
            rows=rows.sort_values('avg_instock',ascending=store_order=='Lowest availability first')
            order=rows['store_id'].astype(str).tolist()
            fig.update_yaxes(categoryorder='array',categoryarray=list(reversed(order)))
        plot(fig)
        st.caption('Hover cells to see observed rates and coverage. The colorbar is fixed at 0–100% so colors mean the same thing across filters.')
        st.markdown('#### Drill into a specific store')
        store_pick=st.selectbox('Store',sorted(daily['store_id'].astype(str).unique()),key='heat_store_select')
        one=summarized(daily[daily['store_id'].astype(str).eq(store_pick)],['brand','category_desc'])
        one['coverage_pct']=100-one['missing_instock_pct']
        one=one.sort_values('sales',ascending=False)
        table_view(one.head(100),['brand','category_desc','sales','units','avg_instock','coverage_pct','obs'],
                   {'avg_instock':'availability'},threshold=min_coverage)
        save_table(one,'v4_selected_store_breakdown.csv','heat_store_export')
    else:
        st.info('No daily records for this selection.')

with views[3]:
    st.subheader('Opportunity finder')
    st.caption('Prioritizes investigation using recorded sales, rate coverage, and gap to a user-selected reference. **This is not a lost-sales estimate.**')
    if len(daily):
        a,b,c=st.columns(3)
        grain=a.selectbox('Rank by',['Brand × store','Product × store','Brand'],key='opp_grain')
        min_rows=b.number_input('Minimum sampled rows',min_value=1,max_value=500,value=10,step=5,key='opp_rows')
        min_sales=c.number_input('Minimum recorded sales ($)',min_value=0,max_value=1000000,value=3000,step=500,key='opp_sales')
        dims={'Brand × store':['brand','store_id'],
              'Product × store':['brand','store_id','item_id'],
              'Brand':['brand']}[grain]
        short=summarized(daily,dims)
        short['coverage_pct']=100-short['missing_instock_pct']
        short['gap_pp']=(reference-short['avg_instock']).clip(lower=0)
        short=short[(short['coverage_pct']>=min_coverage) & (short['obs']>=min_rows)
                    & (short['sales']>=min_sales) & (short['gap_pp']>0)].copy()
        if len(short):
            short['entity']=short[dims].astype(str).agg(' / '.join,axis=1)
        short=short.sort_values(['sales','gap_pp'],ascending=[False,False])
        st.metric('Candidate groups to investigate',f'{len(short):,}')
        if len(short):
            fig,seen=opportunity_scatter(short.head(500),'entity',reference,min_coverage,
                      title=f'{grain}: observed availability vs. sales footprint')
            plot(fig)
            st.caption('500 highest-sales candidates shown in chart for legibility; all qualifying records are available below and by CSV export.')
            shown=short[dims+['sales','units','avg_instock','gap_pp','coverage_pct','obs']]
            table_view(shown.head(300),shown.columns.tolist(),{'avg_instock':'availability'},threshold=min_coverage)
            save_table(shown,'v4_opportunity_candidates.csv','opportunity_export')
        else:
            st.info('No candidates meet current criteria. Lower sales/minimum-row filters or change the reference.')
    else:
        st.info('No daily records for this selection.')

with views[4]:
    st.subheader('FTPR & online order-picking performance')
    st.caption('FTPR period is fixed to the ~six-week window. Sales-date slicer does **not** change these reported rates or paired same-window calculations.')
    if len(ftpr):
        aligned,start,end,n_obs=align_ftpr(all_filtered,ftpr)
        a,b,c,d=st.columns(4)
        a.metric('Mean reported FTPR',percent(ftpr['ftpr_pct_display'].mean()))
        b.metric('Mean reported pre-sub rate',percent(ftpr['presub_pick_rate_pct_display'].mean()))
        c.metric('Mean reported nil-pick',percent(ftpr['nil_pick_rate_pct_display'].mean()))
        d.metric('Matched store-item pairs',percent(aligned['matched_daily_window'].mean()*100))
        st.caption(f'Same-window pairing: {start:%b %d, %Y} – {end:%b %d, %Y}. Reported rates are unweighted means of store-item percentages; some count-based reconstructions differ.')
        metric_name=st.selectbox('Explore picking metric',['FTPR · higher is better','Pre-sub pick · higher is better','Nil-pick · lower is better'],key='pick_metric')
        fmetric={'FTPR · higher is better':'ftpr','Pre-sub pick · higher is better':'presub',
                 'Nil-pick · lower is better':'nil'}[metric_name]
        if fmetric=='nil':
            legend('nil')
        summary=ftpr_summary(ftpr,'brand').sort_values('orders',ascending=False)
        # ftpr_summary has FTPR coverage; nil and presub may have different missingness.
        rawcol={'ftpr':'ftpr_pct_display','presub':'presub_pick_rate_pct_display',
                'nil':'nil_pick_rate_pct_display'}[fmetric]
        cov_rates=ftpr.groupby('brand',observed=True)[rawcol].agg(lambda x: 100*x.notna().mean()).rename('coverage_pct').reset_index()
        summary=summary.merge(cov_rates,on='brand',validate='one_to_one')
        take=summary.nlargest(min(15,len(summary)),'orders')
        fig,kept=ranked_bars(take,'brand',fmetric,
               f'{metric_name} · top order-volume brands',
               ascending=(not worst_first) if fmetric=='nil' else worst_first,
               metric_type=fmetric,min_coverage=min_coverage,
               reference=reference if fmetric!='nil' else None,max_items=15)
        plot(fig)
        st.caption('Nil-pick uses a separate reversed scale: 0–1% blue (best), 10%+ red (worst). These are exploratory ranges, not Walmart thresholds.') if fmetric=='nil' else None
        cols=['brand','orders','pairs','ftpr','presub','nil','coverage_pct']
        table_view(summary.sort_values('orders',ascending=False),cols,
            {'ftpr':'ftpr','presub':'presub','nil':'nil'},threshold=0)
        save_table(summary,'v4_ftpr_brand_summary.csv','pick_summary_export')
        st.markdown('#### Does lower availability coincide with lower FTPR?')
        paired=aligned.dropna(subset=['window_instock','ftpr_pct_display']).copy()
        if len(paired):
            if len(paired)>4500:
                paired=paired.sample(4500,random_state=42)
            fig=go.Figure(go.Scattergl(
                x=paired['window_instock'],y=paired['ftpr_pct_display'],mode='markers',
                marker=dict(color=[metric_color(v,'ftpr') for v in paired['ftpr_pct_display']],
                            size=6,opacity=.40),
                customdata=np.stack([paired['store_id'].astype(str),paired['item_id'].astype(str),paired['brand'].astype(str)],axis=1),
                hovertemplate='Store: %{customdata[0]}<br>Item: %{customdata[1]}<br>Brand: %{customdata[2]}'
                              '<br>In-stock: %{x:.1f}%<br>Reported FTPR: %{y:.1f}%<extra></extra>'))
            fig.add_vline(x=reference,line_dash='dot',line_color=NAVY)
            fig.add_hline(y=reference,line_dash='dot',line_color=NAVY)
            fig.update_layout(title='Matched store-item data · same six-week window')
            fig.update_xaxes(title='Observed same-window in-stock (%)',range=[0,102],ticksuffix='%')
            fig.update_yaxes(title='Reported FTPR (%)',range=[0,102],ticksuffix='%')
            plot(style_plot(fig,510))
        else:
            st.info('No matched pairs with both reported FTPR and in-stock values.')
        st.markdown('#### Store-item investigation table')
        min_orders=st.slider('Minimum recorded order quantity',0,250,10,5,key='min_orders')
        eligible=aligned[aligned['order_qty'].ge(min_orders)].copy()
        eligible['coverage_pct']=np.where(eligible['window_obs'].gt(0),100*eligible['window_instock_obs']/eligible['window_obs'],np.nan)
        cols=[c for c in ['store_id','item_id','brand','category_desc','order_qty','ftpr_pct_display',
                            'nil_pick_rate_pct_display','window_instock','coverage_pct','window_sales',
                            'matched_daily_window'] if c in eligible]
        view=eligible[cols].sort_values('ftpr_pct_display',na_position='last')
        table_view(view.head(400),cols,
              {'ftpr_pct_display':'ftpr','nil_pick_rate_pct_display':'nil','window_instock':'availability'},
              coverage='coverage_pct',threshold=0)
        save_table(view,'v4_ftpr_store_items.csv','pick_pair_export')
        st.caption('Scatter is sampled for readability; tables use the full filtered data. Association is not proof of cause or sales recovery.')
    else:
        st.info('No FTPR rows match current dimensions.')

with views[5]:
    st.subheader('Trends & synthetic operations')
    if len(daily):
        time_lines(daily,reference)
        st.markdown('#### Hypothesis generation · simulated operational fields')
        st.warning('Delivery days and merchandising minutes are synthetic. These plots do not establish operational reality or causation.')
        left,right=st.columns(2,gap='large')
        with left:
            if 'delivery_days_SYNTHETIC' in daily:
                v=daily[['instock_pct','delivery_days_SYNTHETIC']].copy()
                days=v['delivery_days_SYNTHETIC'].astype('string')
                v['delivery_days']=days.map(lambda x:len(x.split(',')) if pd.notna(x) and x.strip() else np.nan)
                roll=v.groupby('delivery_days',dropna=True).agg(avg_instock=('instock_pct','mean'),
                    obs=('instock_pct','count'),all_rows=('instock_pct','size')).reset_index()
                roll['coverage_pct']=100*roll['obs']/roll['all_rows']
                p,used=ranked_bars(roll.rename(columns={'delivery_days':'group'}),'group','avg_instock',
                                'Availability by simulated delivery days',ascending=worst_first,
                                reference=reference,min_coverage=min_coverage)
                plot(p)
        with right:
            if 'merchandiser_minutes_SYNTHETIC' in daily:
                v=daily[['instock_pct','merchandiser_minutes_SYNTHETIC']].copy()
                v['minutes_group']=pd.cut(v['merchandiser_minutes_SYNTHETIC'],
                                          bins=[-1,30,60,90,120,np.inf],
                                          labels=['0–30','31–60','61–90','91–120','120+'])
                roll=v.groupby('minutes_group',observed=True).agg(avg_instock=('instock_pct','mean'),
                    obs=('instock_pct','count'),all_rows=('instock_pct','size')).reset_index()
                roll['coverage_pct']=100*roll['obs']/roll['all_rows']
                p,used=ranked_bars(roll.rename(columns={'minutes_group':'group'}),'group','avg_instock',
                                'Availability by simulated merchandising minutes',ascending=worst_first,
                                reference=reference,min_coverage=min_coverage)
                plot(p)
    else:
        st.info('No sampled daily rows available.')

with views[6]:
    st.subheader('Data quality & measurement notes')
    if len(daily):
        q=summarized(daily,'category_desc')
        q['coverage_pct']=100-q['missing_instock_pct']
        st.metric('Missing sampled in-stock observations',percent(100-pct_coverage(daily)))
        st.metric('Missing sampled sales observations',percent(100*daily['sales_amt'].isna().mean()))
        q=q.sort_values('coverage_pct')
        fig=go.Figure(go.Bar(x=q['coverage_pct'],y=q['category_desc'].astype(str),orientation='h',
                 marker_color=[metric_color(x) for x in q['coverage_pct']],
                 text=[f'{x:.1f}%' for x in q['coverage_pct']],textposition='outside',cliponaxis=False))
        fig.update_layout(title='In-stock field coverage by category')
        fig.update_xaxes(title='Observed values present (%)',range=[0,104],ticksuffix='%')
        fig.update_yaxes(title='',automargin=True)
        plot(style_plot(fig,430))
        table_view(q,['category_desc','obs','available_obs','missing_instock_pct','coverage_pct','sales'],
                   {'coverage_pct':'availability'})
    mismatch=mismatch_stats(ftpr) if len(ftpr) else None
    if mismatch:
        st.warning(f'In {mismatch["pct_off_gt_1pp"]:.1f}% of the {mismatch["n"]:,} FTPR rows with comparable valid counts, the published FTPR and numerator ÷ denominator differ by over one percentage point. Reported FTPR is retained rather than overwritten.')
    st.markdown('''**Interpretation guardrails**
- A gray graded cell means the rate is missing or its coverage fails the sidebar threshold. It does *not* mean 0% in-stock.
- Recorded sales cover sampled dates and deidentified, perturbed case data. Do not describe these as actual full-year financials.
- In-stock and reported FTPR averages are unweighted; cross-brand mix and missingness can bias comparisons.
- The red / orange / gold / teal / blue bands are exploration aids, **not approved Walmart service levels**.
- FTPR uses its separate six-week window; a single store-item FTPR rate must never be repeated across raw weekly rows when calculating means.
- Nil-pick is **lower-is-better**, so it receives a deliberately reversed grading system.
- Operational fields marked `SYNTHETIC` are simulated and should not be interpreted causally.
- Uploaded data is processed on Streamlit Cloud when hosted there, even if uploads are temporary. Keep app access controlled and seek sponsor approval.
''')

st.divider()
st.caption('Fixing the Fizz · V4 academic diagnostic prototype · source CSVs intentionally excluded from GitHub · no persistent data database')
