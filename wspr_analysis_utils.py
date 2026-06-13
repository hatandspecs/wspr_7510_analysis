import pandas as pd
import numpy as np
from datetime import datetime
import requests

# Standard amateur HF band ranges (MHz)
BAND_RANGES = {
    '80m': (3.5, 4.0),
    '40m': (7.0, 7.3),
    '30m': (10.1, 10.15),
    '20m': (14.0, 14.35),
    '17m': (18.068, 18.168),
    '15m': (21.0, 21.45),
    '12m': (24.89, 24.99),
    '10m': (28.0, 29.7),
}


def load_tsv(filepath, time_col='Time'):
    df = pd.read_csv(filepath, sep='\t', parse_dates=[time_col])
    return df


def download_spots_from_wspr_rocks(call_sign, start_utc=None, end_utc=None):
    """Download spots from the wspr.live ClickHouse HTTP API for a call sign and optional UTC range.

    Queries https://db1.wspr.live/ using ClickHouse SQL (FORMAT JSONEachRow) and
    normalizes the response to match the TSV schema used by the rest of this project.

    Column mapping from wspr.live → DataFrame:
        tx_sign   → TX
        rx_sign   → RX
        tx_loc    → txGrid
        rx_loc    → rxGrid
        frequency (Hz, int) → MHz (float, divided by 1 000 000)
        power (dBm, int)    → Watts (float, converted via 10**((dBm-30)/10))
        snr       → SNR
        drift     → drift
        distance  → k
        azimuth   → az
        time      → Time
        version   → version

    Raises RuntimeError with response details if the HTTP request fails.
    Returns a pandas DataFrame ready for the standard pipeline.
    """
    import json as _json

    base = 'https://db1.wspr.live/'

    conditions = [f"(tx_sign = '{call_sign}' OR rx_sign = '{call_sign}')"]
    if start_utc is not None:
        ts = pd.to_datetime(start_utc).strftime('%Y-%m-%d %H:%M:%S')
        conditions.append(f"time >= '{ts}'")
    if end_utc is not None:
        ts = pd.to_datetime(end_utc).strftime('%Y-%m-%d %H:%M:%S')
        conditions.append(f"time <= '{ts}'")

    where = ' AND '.join(conditions)
    query = (
        f"SELECT tx_sign, rx_sign, tx_loc, rx_loc, frequency, power, snr, "
        f"drift, distance, azimuth, time, version "
        f"FROM wspr.rx WHERE {where} ORDER BY time FORMAT JSONEachRow"
    )

    resp = requests.get(base, params={'query': query}, timeout=60)
    if not resp.ok:
        raise RuntimeError(
            f'wspr.live API returned HTTP {resp.status_code}: {resp.text[:500]}'
        )

    lines = [ln for ln in resp.text.strip().split('\n') if ln.strip()]
    if not lines:
        return pd.DataFrame()

    df = pd.DataFrame([_json.loads(ln) for ln in lines])

    df = df.rename(columns={
        'tx_sign': 'TX',
        'rx_sign': 'RX',
        'tx_loc':  'txGrid',
        'rx_loc':  'rxGrid',
        'snr':     'SNR',
        'drift':   'drift',
        'distance': 'k',
        'azimuth': 'az',
        'time':    'Time',
        'version': 'version',
    })

    # frequency is stored as integer Hz; convert to float MHz
    if 'frequency' in df.columns:
        df['MHz'] = df['frequency'].astype(float) / 1_000_000
        df = df.drop(columns=['frequency'])

    # power is stored as integer dBm; convert to watts
    if 'power' in df.columns:
        df['Watts'] = (10 ** ((df['power'].astype(float) - 30) / 10)).round(4)
        df = df.drop(columns=['power'])

    if 'Time' in df.columns:
        df['Time'] = pd.to_datetime(df['Time'], utc=True).dt.tz_localize(None)

    return df


def discover_bands_from_dataset(df, mhz_col='MHz'):
    """Discover which standard amateur bands are present in the dataset.

    Returns a sorted list of band names present in the DataFrame.
    """
    if mhz_col not in df.columns:
        return []
    freqs = pd.to_numeric(df[mhz_col], errors='coerce').dropna()
    present = []
    for band, (lo, hi) in BAND_RANGES.items():
        if ((freqs >= lo) & (freqs <= hi)).any():
            present.append(band)
    # Keep canonical order
    order = list(BAND_RANGES.keys())
    present_sorted = [b for b in order if b in present]
    return present_sorted


def get_band_for_mhz(mhz):
    try:
        mhz = float(mhz)
    except Exception:
        return 'Other'
    for band, (lo, hi) in BAND_RANGES.items():
        if lo <= mhz <= hi:
            return band
    return 'Other'


def assign_band_column(df, mhz_col='MHz', band_col='Band'):
    df = df.copy()
    if mhz_col in df.columns:
        df[band_col] = pd.to_numeric(df[mhz_col], errors='coerce').apply(get_band_for_mhz)
    else:
        df[band_col] = 'Other'
    return df


def prepare_dataframe(df, time_col='Time'):
    df = df.copy()
    if time_col in df.columns:
        df[time_col] = pd.to_datetime(df[time_col])
    # prefixes
    if 'rxGrid' in df.columns:
        df['rxPrefix'] = df['rxGrid'].fillna('').str[:4]
    else:
        df['rxPrefix'] = ''
    if 'txGrid' in df.columns:
        df['txPrefix'] = df['txGrid'].fillna('').str[:4]
    else:
        df['txPrefix'] = ''
    # time bin
    if time_col in df.columns:
        df['TimeBin'] = df[time_col].dt.floor('15min')
    # azimuth radians
    if 'az' in df.columns:
        df['az_rad'] = np.radians(df['az'].astype(float))
    return df


def filter_by_time(df, start_utc=None, end_utc=None, time_col='Time'):
    df = df.copy()
    if start_utc is not None:
        start = pd.to_datetime(start_utc)
        df = df[df[time_col] >= start]
    if end_utc is not None:
        end = pd.to_datetime(end_utc)
        df = df[df[time_col] <= end]
    return df


def load_data(tsv_path=None, call_sign=None, start_utc=None, end_utc=None, download=False):
    """Load data either from a TSV or by downloading from wspr.rocks for a call sign.

    Returns a prepared DataFrame.
    """
    if download:
        if not call_sign:
            raise ValueError('call_sign must be provided when download=True')
        df = download_spots_from_wspr_rocks(call_sign, start_utc=start_utc, end_utc=end_utc)
    else:
        if not tsv_path:
            raise ValueError('tsv_path must be provided when download=False')
        df = load_tsv(tsv_path)

    df = prepare_dataframe(df)
    df = assign_band_column(df)
    if start_utc or end_utc:
        df = filter_by_time(df, start_utc=start_utc, end_utc=end_utc)
    return df
