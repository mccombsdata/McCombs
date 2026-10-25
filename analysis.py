"""Data calculations for the Fixing the Fizz dashboard.

Daily file grain: store × item × sampled date.
FTPR file grain: store × item × six-week window.
Do not merge raw daily rows to FTPR rows: that repeats FTPR statistics.
"""
from __future__ import annotations
import io
from pathlib import Path
import numpy as np
import pandas as pd

DAILY_REQUIRED = {
    'date', 'store_id', 'item_id', 'brand', 'category_desc',
    'sales_amt', 'unit_qty', 'frac_instk_pct'
}
FTPR_REQUIRED = {
    'store_id', 'item_id', 'brand', 'category_desc',
    'ftpr_window_start', 'ftpr_window_end', 'ftpr_pct',
    'presub_pick_rate_pct', 'nil_pick_rate_pct'
}
ID_COLUMNS = ['store_id', 'item_id']

def _load(source):
    df = pd.read_csv(source, low_memory=False)
    return df

def _validate(df, required, filename):
    missing = required.difference(df.columns)
    if missing:
        raise ValueError(f'{filename} is missing columns: {", ".join(sorted(missing))}')

def load_daily(source):
    """Load a path, file buffer, or BytesIO and normalize for analysis."""
    df = _load(source)
    _validate(df, DAILY_REQUIRED, 'Daily sales file')
    df['date'] = pd.to_datetime(df['date'], errors='coerce')
    for col in ('sales_amt', 'unit_qty', 'frac_instk_pct', 'fcst_dmand_each_qty',
                'on_hand_qty', 'merchandiser_minutes_SYNTHETIC'):
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce')
    mx = df['frac_instk_pct'].max()
    df['instock_pct'] = df['frac_instk_pct'] * 100 if pd.notna(mx) and mx <= 1 else df['frac_instk_pct']
    for col in ('store_id', 'item_id', 'brand', 'category_desc', 'item_desc',
                'vendor', 'carry_status_desc', 'delivery_days_SYNTHETIC'):
        if col in df.columns:
            df[col] = df[col].astype('category')
    return df

def load_ftpr(source):
    df = _load(source)
    _validate(df, FTPR_REQUIRED, 'FTPR file')
    for col in ('ftpr_window_start', 'ftpr_window_end'):
        df[col] = pd.to_datetime(df[col], errors='coerce')
    for col in ('ftpr_pct', 'presub_pick_rate_pct', 'nil_pick_rate_pct',
                'first_tm_pick_numerator', 'first_tm_pick_denominator',
                'order_qty', 'nil_picked_qty'):
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce')
    for col in ('store_id', 'item_id', 'brand', 'category_desc', 'item_desc', 'vendor'):
        if col in df.columns:
            df[col] = df[col].astype('category')
    for col in ('ftpr_pct', 'presub_pick_rate_pct', 'nil_pick_rate_pct'):
        mx = df[col].max()
        df[col + '_display'] = df[col] * 100 if pd.notna(mx) and mx <= 1 else df[col]
    return df

def summarized(df, dimension):
    out = df.groupby(dimension, observed=True, dropna=False).agg(
        sales=('sales_amt', 'sum'),
        units=('unit_qty', 'sum'),
        avg_instock=('instock_pct', 'mean'),
        obs=('item_id', 'size'),
        available_obs=('instock_pct', 'count'),
        products=('item_id', 'nunique'),
        stores=('store_id', 'nunique'),
    ).reset_index()
    out['missing_instock_pct'] = 100 * (1 - out['available_obs'] / out['obs'])
    out['missing_instock_pct'] = out['missing_instock_pct'].round(2)
    return out

def ftpr_summary(df, dimension):
    out = df.groupby(dimension, observed=True, dropna=False).agg(
        ftpr=('ftpr_pct_display', 'mean'),
        presub=('presub_pick_rate_pct_display', 'mean'),
        nil=('nil_pick_rate_pct_display', 'mean'),
        pairs=('item_id', 'size'),
        valid_ftpr=('ftpr_pct_display', 'count'),
        orders=('order_qty', 'sum'),
    ).reset_index()
    out['ftpr_coverage_pct'] = out['valid_ftpr'] / out['pairs'] * 100
    return out

def align_ftpr(daily, ftpr):
    """FTPR one row/pair, matched to daily *aggregated* within FTPR date window.

    The date slicer in the UI MUST NOT limit this function's daily input,
    otherwise full-window FTPR would be compared with a partial window.
    """
    if ftpr[ID_COLUMNS].duplicated().any():
        raise ValueError('FTPR has duplicate store/item records. Cannot safely join.')
    start = ftpr['ftpr_window_start'].min()
    end = ftpr['ftpr_window_end'].max()
    window_daily = daily.loc[daily['date'].between(start, end)]
    grouped = window_daily.groupby(ID_COLUMNS, observed=True, dropna=False).agg(
        window_sales=('sales_amt', 'sum'),
        window_units=('unit_qty', 'sum'),
        window_instock=('instock_pct', 'mean'),
        window_instock_obs=('instock_pct', 'count'),
        window_obs=('date', 'size'),
    ).reset_index()
    aligned = ftpr.merge(grouped, how='left', on=ID_COLUMNS, validate='one_to_one', indicator=True)
    aligned['matched_daily_window'] = aligned['_merge'].eq('both')
    aligned.drop(columns='_merge', inplace=True)
    return aligned, start, end, len(window_daily)

def mismatch_stats(ftpr):
    if not {'first_tm_pick_numerator','first_tm_pick_denominator','ftpr_pct'}.issubset(ftpr.columns):
        return None
    valid = ftpr['first_tm_pick_denominator'].gt(0) & ftpr['ftpr_pct'].notna()
    if not valid.any():
        return None
    stated = ftpr.loc[valid, 'ftpr_pct_display']
    recomputed = 100 * ftpr.loc[valid, 'first_tm_pick_numerator'] / ftpr.loc[valid, 'first_tm_pick_denominator']
    return {'n': int(valid.sum()), 'pct_off_gt_1pp': float(((stated - recomputed).abs() > 1).mean() * 100)}
