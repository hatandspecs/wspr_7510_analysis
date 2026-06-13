"""Integration test: verify that the wspr.live API returns the same spots as
the local TSV snapshot when queried with the same callsign and time bounds.

Run with:
    pytest test_api_comparison.py -v

Note: wspr.live ingests data with a variable lag. If the spots in the TSV have
not yet propagated into the wspr.live ClickHouse database, the comparison tests
will be skipped automatically (rather than failing). The first test
(test_api_returns_data) will indicate this clearly.
"""
import pandas as pd
import pytest
from wspr_analysis_utils import (
    download_spots_from_wspr_rocks,
    prepare_dataframe,
    assign_band_column,
)

TSV_PATH = '7510m_wspr_spots.tsv'
CALLSIGN = 'KD3CCO'

# Columns compared between the API and TSV results.
COMPARE_COLS = ['Time', 'TX', 'RX', 'MHz', 'SNR', 'k', 'az', 'Watts']


def _load_tsv():
    df = pd.read_csv(TSV_PATH, sep='\t', parse_dates=['Time'])
    df = prepare_dataframe(df)
    df = assign_band_column(df)
    return df


def _sort(df, cols):
    available = [c for c in cols if c in df.columns]
    return df[available].sort_values(available).reset_index(drop=True)


@pytest.fixture(scope='module')
def local_df():
    return _load_tsv()


@pytest.fixture(scope='module')
def api_df(local_df):
    start = local_df['Time'].min()
    end = local_df['Time'].max()
    df = download_spots_from_wspr_rocks(CALLSIGN, start_utc=start, end_utc=end)
    df = prepare_dataframe(df)
    df = assign_band_column(df)
    return df


def test_api_returns_data(api_df, local_df):
    """API must return at least one row for the given callsign and time window.

    If this test is skipped, the wspr.live database does not yet have data for
    the TSV time window (start={local_df['Time'].min()},
    end={local_df['Time'].max()}). Re-run once ingestion catches up.
    """
    if len(api_df) == 0:
        pytest.skip(
            f'wspr.live has no spots for {CALLSIGN} between '
            f'{local_df["Time"].min()} and {local_df["Time"].max()} — '
            'data may not be ingested yet'
        )


def test_api_row_count_matches_tsv(api_df, local_df):
    """API row count must equal the TSV row count for the same query."""
    if len(api_df) == 0:
        pytest.skip('No API data available; see test_api_returns_data')
    assert len(api_df) == len(local_df), (
        f'Row count mismatch: API returned {len(api_df)} rows, TSV has {len(local_df)} rows'
    )


def test_api_spots_match_tsv(api_df, local_df):
    """Key fields (Time, TX, RX, MHz, SNR, k, az, Watts) must be identical after sorting."""
    if len(api_df) == 0:
        pytest.skip('No API data available; see test_api_returns_data')
    api_sorted = _sort(api_df, COMPARE_COLS)
    local_sorted = _sort(local_df, COMPARE_COLS)
    pd.testing.assert_frame_equal(
        api_sorted,
        local_sorted,
        check_like=False,
        obj='API vs TSV spots',
    )


def test_api_band_distribution_matches_tsv(api_df, local_df):
    """Per-band spot counts must match between API and TSV."""
    if len(api_df) == 0:
        pytest.skip('No API data available; see test_api_returns_data')
    api_bands = api_df['Band'].value_counts().sort_index()
    local_bands = local_df['Band'].value_counts().sort_index()
    pd.testing.assert_series_equal(
        api_bands,
        local_bands,
        check_names=False,
        obj='Band distribution (API vs TSV)',
    )


def test_api_time_bounds_are_within_tsv_range(api_df, local_df):
    """API results must fall within the TSV time window."""
    if len(api_df) == 0:
        pytest.skip('No API data available; see test_api_returns_data')
    tsv_start = local_df['Time'].min()
    tsv_end = local_df['Time'].max()
    assert api_df['Time'].min() >= tsv_start, 'API returned spots before TSV start time'
    assert api_df['Time'].max() <= tsv_end, 'API returned spots after TSV end time'
