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

# Whether each band has any phone (SSB) allocation under the amateur band
# plan. 30m is a CW/data-only WARC band with no phone privileges at any
# license class; every other HF band here has at least an upper phone segment.
PHONE_ALLOWED_BANDS = {
    '80m': True,
    '40m': True,
    '30m': False,
    '20m': True,
    '17m': True,
    '15m': True,
    '12m': True,
    '10m': True,
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

def matched_pairs(df, call_sign, window='20min'):
    """Spots of the same remote station on the same band, both directions.

    The TX/RX asymmetry test (Analysis 5) compares what a remote station
    reported hearing from us against what we reported hearing from them,
    close enough in time to be the same propagation. `SNR_delta` positive
    means our transmit path beat our receive path, which points at local
    noise rather than at the antenna.

    **`SNR_delta_norm` is the figure to quote.** WSPR SNR scales dB for dB
    with transmit power, and the two sides of a pair are rarely running the
    same power -- so a raw delta partly measures who was louder, not which
    path was better. Normalizing each side to one watt removes it.

    This matters more than it sounds. The June 2026 EFHW capture transmitted
    at 10 W against remote stations whose median was 5 W, and its raw mean
    delta of +6.3 dB over 38 pairs was published as evidence of a receive
    deficit. Normalized, that capture's mean was -0.9 dB with a bootstrap
    confidence interval spanning zero: it was not evidence of anything. The
    October 2026 capture, at 5 W against a 5 W median over 143 pairs, gives
    +8.5 dB with the interval well clear of zero. Same conclusion, and only
    the second dataset actually supports it.

    **Normalizing is a repair, not a cure, and `same_power` is better.**
    Scaling a 20 mW station's SNR up by 24 dB assumes you saw a fair sample
    of that station, and you did not: a weak transmitter is only decoded when
    the path is unusually good, so its reported SNRs are censored from below
    and normalizing flatters it. One station in the October capture, HK4CZE,
    claims 1000 W on every spot; normalized, its twelve pairs carry +38 dB
    deltas and drag the whole mean with them.

    So prefer the pairs where both ends ran the same power, where no
    normalization is needed and nothing has to be assumed. In the October
    capture those 66 pairs, from 19 distinct stations, give **+11.0 dB with a
    confidence interval of [+8.6, +13.3]** -- and collapsed to one median pair
    per station, +7.6 dB [+3.6, +11.5], so it is not one station repeating.

    That subset is also the thing most captures do not have. June has one
    equal-power pair; the three field-antenna captures have none, none and
    three. **A TX/RX asymmetry number from those datasets cannot be rescued
    by normalizing -- it simply is not measurable, and the honest answer is
    to say so rather than to quote a normalized figure with a wide interval.**
    """
    cols = ['Time', 'Band', 'SNR', 'k', 'az']
    if 'Watts' in df.columns:
        cols = cols + ['Watts']
    tx = df[df['TX'] == call_sign][cols + ['RX']].rename(
        columns={'RX': 'Remote', 'SNR': 'SNR_tx', 'Time': 'Time_tx',
                 'k': 'k_tx', 'az': 'az_tx', 'Watts': 'W_tx'})
    rx = df[df['RX'] == call_sign][cols + ['TX']].rename(
        columns={'TX': 'Remote', 'SNR': 'SNR_rx', 'Time': 'Time_rx',
                 'k': 'k_rx', 'az': 'az_rx', 'Watts': 'W_rx'})
    paired = pd.merge(rx, tx, on=['Remote', 'Band'], suffixes=('_rx', '_tx'))
    paired['time_delta'] = (paired['Time_tx'] - paired['Time_rx']).abs()
    paired = paired[paired['time_delta'] <= pd.Timedelta(window)].copy()
    paired = paired.sort_values(
        ['Remote', 'Band', 'Time_rx', 'time_delta']).drop_duplicates(
        ['Remote', 'Band', 'Time_rx'])
    paired['SNR_delta'] = paired['SNR_tx'] - paired['SNR_rx']
    if 'W_tx' in paired.columns and 'W_rx' in paired.columns:
        paired['SNR_delta_norm'] = (
            (paired['SNR_tx'] - 10 * np.log10(paired['W_tx']))
            - (paired['SNR_rx'] - 10 * np.log10(paired['W_rx'])))
        # **The subset to trust.** See the note on censoring below.
        paired['same_power'] = np.isclose(paired['W_tx'], paired['W_rx'])
    paired['abs_time_delta_min'] = paired['time_delta'] / pd.Timedelta('1min')
    return paired


def bootstrap_mean_ci(values, n=5000, pct=95, seed=7):
    """Percentile bootstrap interval for a mean, for small-sample sanity.

    A mean over a few dozen pairs is easy to over-read, and this project has
    already published one conclusion that a confidence interval would have
    stopped. Returns (low, high).
    """
    v = np.asarray(values, dtype=float)
    v = v[~np.isnan(v)]
    if len(v) == 0:
        return (float('nan'), float('nan'))
    rng = np.random.default_rng(seed)
    means = rng.choice(v, (n, len(v)), replace=True).mean(axis=1)
    half = (100 - pct) / 2
    return tuple(np.percentile(means, [half, 100 - half]))
