"""Reusable, metric-aware visual encoding for Fixing the Fizz.

Thresholds are user-requested exploratory bands, *not* client approved SLAs.
Never grade missing values as poor performance. Never use high-is-good
FTPR bands for nil-pick rate, where low is good.
"""
from __future__ import annotations

import math
import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.colors import hex_to_rgb

NAVY = '#15375B'
BLUE = '#2268C5'
TEAL = '#61AEC0'
GOLD = '#E8C163'
ORANGE = '#EA925A'
RED = '#D54C4C'
GRAY = '#A6B1C0'
GRID = '#E9EFF7'

# Metric in percentage units (0–100). Red below 70; blue at 95+.
HIGH_GOOD = [(0,RED),(69.999,RED),(80,ORANGE),(90,GOLD),(93,TEAL),(95,BLUE),(100,BLUE)]
# Inverted severity for nil-pick: 0–1% best, >10% critical.
NIL_LOW_GOOD = [(0,BLUE),(1,BLUE),(2,TEAL),(5,GOLD),(10,ORANGE),(15,RED),(100,RED)]


def _mix(a, b, t):
    x, y = hex_to_rgb(a), hex_to_rgb(b)
    rgb = [int(round(v + (w - v) * t)) for v,w in zip(x,y)]
    return '#'+''.join(f'{v:02X}' for v in rgb)


def metric_color(value, metric='availability', coverage=None, min_coverage=0):
    """Stable color for both bars and table cells; missing is neutral gray."""
    if pd.isna(value) or (coverage is not None and (pd.isna(coverage) or coverage < min_coverage)):
        return GRAY
    knots = NIL_LOW_GOOD if metric == 'nil' else HIGH_GOOD
    value = float(np.clip(value, 0, 100))
    for (a, ca), (b, cb) in zip(knots[:-1], knots[1:]):
        if value <= b:
            return _mix(ca, cb, (value-a)/(b-a)) if b > a else cb
    return knots[-1][1]


def heat_scale(metric='availability'):
    knots = NIL_LOW_GOOD if metric == 'nil' else HIGH_GOOD
    return [[value/100., color] for value, color in knots]


def tinted(color, ratio=.77):
    """Light table backgrounds so dark text remains legible."""
    return _mix(color, '#FFFFFF', ratio)


def style_ratings(frame, cols: dict[str,str], coverage_col=None, min_coverage=0):
    """A sortable Streamlit table with safe per-cell conditional formatting."""
    result = frame.copy()
    styler = result.style
    for col, metric in cols.items():
        if col not in result.columns:
            continue
        cov = result[coverage_col] if coverage_col and coverage_col in result else None
        def _paint(v, cov=cov, metric=metric):
            return [f'background-color: {tinted(metric_color(value, metric, cov.iloc[i] if cov is not None else None, min_coverage))}; color: #1B2E46' for i, value in enumerate(v)]
        styler = styler.apply(_paint, axis=0, subset=[col])
    return styler


def style_plot(fig: go.Figure, height=440):
    fig.update_layout(
        template='plotly_white', height=height,
        font=dict(family='Arial, sans-serif', size=12, color=NAVY),
        paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
        margin=dict(l=10,r=22,t=47,b=16),
        title=dict(font=dict(size=16,color=NAVY)),
        hoverlabel=dict(bgcolor='white',font_size=12),
        legend_title_text='',
    )
    fig.update_xaxes(gridcolor=GRID,zerolinecolor=GRID)
    fig.update_yaxes(gridcolor=GRID,zerolinecolor=GRID)
    return fig


def ranked_bars(frame, label, metric, title, ascending=True, metric_type='availability',
                reference=None, min_coverage=0, max_items=20, extra_hover=None):
    """Consistent horizontal metric bars, individually colored by performance."""
    frame = frame.copy()
    if 'coverage_pct' not in frame and 'missing_instock_pct' in frame:
        frame['coverage_pct'] = 100-frame['missing_instock_pct']
    keep = frame.dropna(subset=[metric]).copy()
    if 'coverage_pct' in keep:
        keep = keep[keep['coverage_pct'] >= min_coverage]
    keep = keep.sort_values(metric, ascending=ascending).head(max_items)
    fig=go.Figure()
    if keep.empty:
        return style_plot(fig),keep
    # y in ascending vertical order: bottom is first list member.
    rows=keep.iloc[::-1]
    labels=rows[label].astype(str).tolist()
    values=rows[metric].tolist()
    colors=[metric_color(v,metric_type) for v in values]
    custom=np.array([
        [float(row.get('sales',row.get('orders',np.nan))),float(row.get('coverage_pct',np.nan)),float(row.get('obs', row.get('pairs',np.nan)))]
        for _,row in rows.iterrows()
    ])
    first_label = 'Recorded sales: $' if 'sales' in rows.columns else 'Orders: '
    first_value = '%{customdata[0]:,.0f}'
    hover=(f'<b>%{{y}}</b><br>{"Nil-pick" if metric_type=="nil" else "Performance"}: %{{x:.1f}}%'
           f'<br>{first_label}{first_value}'
           '<br>Coverage: %{customdata[1]:.1f}%'
           '<br>Observations: %{customdata[2]:,.0f}<extra></extra>')
    fig.add_bar(x=values,y=labels,orientation='h',marker_color=colors,
                text=[f'{v:.1f}%' for v in values],textposition='outside',
                cliponaxis=False,customdata=custom,hovertemplate=hover)
    fig.update_layout(title=title,showlegend=False,uniformtext_minsize=9)
    fig.update_xaxes(title='Rate (%)',range=[0,105],ticksuffix='%')
    fig.update_yaxes(title='',automargin=True)
    if reference is not None:
        fig.add_vline(x=reference,line_color=NAVY,line_dash='dot',opacity=.65)
    return style_plot(fig,height=max(330,min(690,100+32*len(rows)))),keep


def opportunity_scatter(frame, label, reference=95, min_coverage=70, title='Availability × sales footprint'):
    view=frame.dropna(subset=['avg_instock','sales']).copy()
    if 'coverage_pct' not in view:
        view['coverage_pct']=100-view['missing_instock_pct']
    view=view[view['coverage_pct']>=min_coverage]
    view=view[view['sales']>0]
    fig=go.Figure()
    if view.empty:
        return style_plot(fig),view
    max_units=max(float(view['units'].max()),1.0)
    area=14+35*np.sqrt(view['units'].fillna(0).clip(lower=0)/max_units)
    fig.add_scatter(
        x=view['avg_instock'],y=view['sales'],mode='markers',
        marker=dict(color=[metric_color(v) for v in view['avg_instock']],
                    size=area,line=dict(color='#FFFFFF',width=1.2),opacity=.85),
        customdata=np.column_stack([view[label].astype(str).to_numpy(),
                                   view['coverage_pct'].to_numpy(),view['units'].to_numpy()]),
        hovertemplate='<b>%{customdata[0]}</b><br>In-stock: %{x:.1f}%'
                      '<br>Recorded sales: $%{y:,.0f}<br>Data coverage: %{customdata[1]:.1f}%'
                      '<br>Units: %{customdata[2]:,.0f}<extra></extra>',
        showlegend=False
    )
    fig.add_vline(x=reference,line_dash='dash',line_color=NAVY,opacity=.65,
                  annotation_text=f'{reference}% reference')
    mid=float(view['sales'].median())
    fig.add_hline(y=mid,line_dash='dot',line_color='#93A4B7',opacity=.6,
                  annotation_text='Median sales')
    fig.update_layout(title=title)
    fig.update_xaxes(title='Observed in-stock (%)',range=[0,102],ticksuffix='%')
    fig.update_yaxes(title='Recorded sales ($)',tickprefix='$')
    return style_plot(fig,520),view


def availability_matrix(summary, brands, min_coverage=70, metric='avg_instock'):
    """Grays out low-coverage and missing brand-store intersections; no fake zeros."""
    sb=summary.copy()
    sb['coverage_pct']=100-sb['missing_instock_pct']
    sb=sb[sb['brand'].astype(str).isin(brands)]
    stores=sorted(sb['store_id'].astype(str).unique().tolist())
    brands=list(brands)
    vals=sb.assign(store_id=sb['store_id'].astype(str),brand=sb['brand'].astype(str))
    availability=vals.pivot(index='store_id',columns='brand',values=metric).reindex(index=stores,columns=brands)
    cov=vals.pivot(index='store_id',columns='brand',values='coverage_pct').reindex(index=stores,columns=brands)
    availability=availability.mask(cov.lt(min_coverage))
    z=availability.to_numpy(dtype=float)
    fig=go.Figure(data=go.Heatmap(
        z=z,x=brands,y=stores,zmin=0,zmax=100,colorscale=heat_scale(),
        customdata=cov.to_numpy(dtype=float),
        hovertemplate='Store: %{y}<br>Brand: %{x}<br>Observed availability: %{z:.1f}%'
                      '<br>Coverage: %{customdata:.1f}%<extra></extra>',
        colorbar=dict(title='In-stock %',thickness=13,len=.79,
                      tickvals=[0,70,80,90,95,100]),
        xgap=2,ygap=2,
    ))
    fig.update_layout(title='Brand × store availability heatmap',
                      plot_bgcolor='#EDF0F4',height=max(480,30*len(stores)+120))
    fig.update_xaxes(side='top',tickangle=-40,automargin=True)
    fig.update_yaxes(autorange='reversed',automargin=True)
    fig=style_plot(fig,height=max(480,30*len(stores)+120))
    fig.update_layout(plot_bgcolor='#EDF0F4')  # muted blanks, never red
    return fig,availability
