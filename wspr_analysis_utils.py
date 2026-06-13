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
    """Download spots from wspr.rocks API for a call sign and optional UTC range.

    Queries https://wspr.rocks/api/spots and normalizes the response columns
    to match the TSV schema used by the rest of this project.

    Column mapping from wspr.rocks JSON → DataFrame:
        tx_sign / tx   → TX
        rx_sign / rx   → RX
        frequency / mhz / MHz → MHz
        snr / SNR      → SNR
        distance / km / k → k
        power / watts / Watts → Watts
        tx_loc / txGrid → txGrid
        rx_loc / rxGrid → rxGrid
        az / azimuth   → az
        spot_time / time / Time → Time

    Raises RuntimeError with response details if the HTTP request fails.
    Returns a pandas DataFrame ready for the standard pipeline.
    """
    base = 'https://wspr.rocks/api/spots'
    params = {'call': call_sign}
    if start_utc is not None:
        params['start'] = pd.to_datetime(start_utc).isoformat()
    if end_utc is not None:
        params['end'] = pd.to_datetime(end_utc).isoformat()

    resp = requests.get(base, params=params, timeout=60)
    if not resp.ok:
        raise RuntimeError(
            f'wspr.rocks API returned HTTP {resp.status_code}: {resp.text[:500]}'
        )

    data = resp.json()
    if not data:
        return pd.DataFrame()

    df = pd.DataFrame(data)

    # Normalize column names to match the expected TSV schema
    col_map = {
        'tx_sign': 'TX', 'tx': 'TX',
        'rx_sign': 'RX', 'rx': 'RX',
        'frequency': 'MHz', 'mhz': 'MHz',
        'snr': 'SNR',
        'distance': 'k', 'km': 'k',
        'power': 'Watts', 'watts': 'Watts',
        'tx_loc': 'txGrid',
        'rx_loc': 'rxGrid',
        'azimuth': 'az',
        'spot_time': 'Time', 'time': 'Time',
        'drift': 'drift', 'mode': 'mode',
    }
    df = df.rename(columns={c: col_map[c] for c in df.columns if c in col_map})

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
