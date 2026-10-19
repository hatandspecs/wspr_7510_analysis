#!/usr/bin/env python
# coding: utf-8
"""Interactive path map for the cyberdeck's overnight band-hopping run.

The dataset is not one of the antenna comparisons -- it is the cyberdeck's
first unattended band-hopping session, 2026-10-17/18, five watts, eight bands,
and it is here because the folium pattern in `wspr_folium_map.py` is the one
the blog's maps are drawn with. The great-circle interpolation, the
antimeridian handling and the band colors all come from that module.

The deck's own spot log (`~/.local/share/cyberdeck/wspr.log`) holds only the
receive side, because a beacon sent carries no record of who heard it. So the
paths come from wspr.live, which has both directions, and the deck's log is
the cross-check on the receive half.

**One path per unique pair of stations**, not one per spot and not one per
band. A 29-hour run on eight bands is ~15,000 spots and the same two stations
account for dozens of them -- VK5ARG heard the deck on five different bands,
VK6WR took it three times in one half hour. Drawing each spot buries that:
the line to VK5ARG is one path that was open on five bands, and saying so is
the point of the run. Every spot on a path is in its fly-out instead, broken
down by band.

A path belongs to the layer of **every band it was decoded on**, so turning
on `20m` shows every path that was open on 20 m rather than only the paths
20 m carried most. A multi-band path therefore draws once per enabled band;
the geometry is identical, so it simply reads heavier, which is the correct
emphasis.
"""

import re

import pandas as pd
import folium
from folium import FeatureGroup, LayerControl
from folium.plugins import Fullscreen

from wspr_folium_map import (
    BAND_COLORS,
    interpolate_great_circle,
    _ensure_continuous_path,
)

# ── User configuration ─────────────────────────────────────────────────────
TSV_FILENAME = 'cyberdeck_wspr_sessions_2026-10-19_spots.tsv'
CALLSIGN     = 'KD3CCO'
HTML_PATH    = ('/home/natale/git_repos/hamradio-source/assets/'
                'cyberdeck_wspr_overnight_spots_map.html')
# ───────────────────────────────────────────────────────────────────────────

# wspr.live reports the band as the integer MHz of the band's low edge.
BAND_BY_MHZ = {3: '80m', 7: '40m', 10: '30m', 14: '20m',
               18: '17m', 21: '15m', 24: '12m', 28: '10m'}

# Low to high, so a path's bands read in a sensible order in the fly-out.
BAND_ORDER = ['80m', '40m', '30m', '20m', '17m', '15m', '12m', '10m']

# WSPR decodes wrong occasionally and wsprnet aggregates whatever it is sent.
# Two filters, and the second is the one that earns its place.
#
# **Q, 0 and 1 are never the first character of a callsign** -- Q is reserved
# for Q-codes and 0 and 1 are unallocated -- so `QD9PDP` and `002ADF` cannot
# be stations. Q anywhere else is ordinary: SQ2WB is Polish and KQ4ADJ is
# American, and an earlier version of this rule threw both away along with
# every compound call (`CT/G0MZJ`) and every SDR reporter (`KM3T-1`).
BAD_FIRST = re.compile(r'^[Q01]')

# **A station nobody else on the network has ever heard was not there.**
# A real WSPR beacon is received by dozens of stations; DP0GVN at Neumayer
# III was heard 127,162 times by 1,126 receivers in October. A corrupt decode
# is heard once, by one receiver, and never again.
#
# `cyberdeck_wspr_corroboration_2026-10-19.tsv` is one wspr.live query
# counting, for every station this deck heard, how many distinct receivers
# heard it network-wide that month. The answer is bimodal and there is
# nothing in the middle: 454 of 463 were heard by five receivers or more,
# nine were heard by exactly one -- this deck -- and each of those nine
# appeared exactly once. `X18IYP` is the case that makes it: a plausible
# enough callsign, but an unallocated `X1` prefix, a grid in the open Arctic
# Ocean, and a claim of 1 mW that works out to 3.9 million km per watt.
#
# This replaced two heuristics of mine. One dropped a path whose far end lay
# beyond 72 N or 60 S and was decoded once, which also threw away Antarctica.
# The other is kept below, because it still guards the transmit side, where
# no such corroboration is available -- those spots are other people's
# decodes of this deck, and a bogus RECEIVER callsign is a different problem.
CORROBORATION = 'cyberdeck_wspr_corroboration_2026-10-19.tsv'
MIN_RECEIVERS = 2


def corroborated_calls(path=CORROBORATION):
    """Stations more than one receiver on the network has heard."""
    try:
        t = pd.read_csv(path, sep='\t')
    except OSError:
        return None
    return set(t.loc[t['heard_by'] >= MIN_RECEIVERS, 'tx_sign'])


def load(path=TSV_FILENAME, call_sign=CALLSIGN):
    df = pd.read_csv(path, sep='\t', parse_dates=['time'])
    df['Band'] = df['band'].map(BAND_BY_MHZ)
    df = df.dropna(subset=['Band'])

    mine_tx = df['tx_sign'] == call_sign
    df['far'] = df['rx_sign'].where(mine_tx, df['tx_sign'])
    df['far_lat'] = df['rx_lat'].where(mine_tx, df['tx_lat'])
    df['far_lon'] = df['rx_lon'].where(mine_tx, df['tx_lon'])
    df['far_loc'] = df['rx_loc'].where(mine_tx, df['tx_loc'])
    df['my_lat'] = df['tx_lat'].where(mine_tx, df['rx_lat'])
    df['my_lon'] = df['tx_lon'].where(mine_tx, df['rx_lon'])
    df['role'] = mine_tx.map({True: 'heard_by', False: 'heard'})

    dropped = df['far'].str.upper().str.match(BAD_FIRST)

    # The corroboration check applies only where the deck was the receiver.
    real = corroborated_calls()
    if real is not None:
        heard = df['role'] == 'heard'
        uncorroborated = heard & ~df['far'].isin(real)
        for call in sorted(set(df.loc[uncorroborated & ~dropped, 'far'])):
            print(f'  excluded {call}: no other receiver on the network has '
                  f'ever heard it')
        dropped = dropped | uncorroborated
    if dropped.any():
        print(f'  excluded {dropped.sum()} corrupt decodes '
              f'({df.loc[dropped, "far"].nunique()} impossible callsigns)')

    df = df[~dropped].copy()

    # **A lone decode far beyond anything the band repeated is not a path.**
    # The character rule above catches a callsign that cannot exist; it does
    # nothing about a plausible callsign on an impossible path. This run put
    # `RO0KNE` in Indonesia at 16,368 km on 80 m, once, and `WY5QPI` at
    # 10,530 km on 80 m, once -- while the furthest 80 m path anybody
    # repeated was G4HSB in England at 5,646 km.
    #
    # Hand-listing the offenders does not generalize, so the band judges its
    # own: the furthest path decoded more than once on a band is what that
    # band demonstrably did, and a single decode beyond half as far again is
    # uncorroborated. It is the same standard the write-up already applies to
    # a distance record, applied to every path on the map. On this data it
    # drops the two above and keeps VK5HW at 16,803 km on 40 m, which is a
    # single decode on a band that repeated 14,237 km.
    pair = df.groupby(['role', 'far', 'Band'])
    repeats = pair['time'].transform('size')
    corroborated = df[repeats > 1].groupby('Band')['distance'].max()
    ceiling = df['Band'].map(corroborated * 1.5)
    lone = (repeats == 1) & ceiling.notna() & (df['distance'] > ceiling)
    if lone.any():
        for _, r in df[lone].iterrows():
            print(f'  excluded {r["far"]} at {int(r["distance"]):,} km on '
                  f'{r["Band"]}: decoded once, and the band repeated no '
                  f'further than {int(corroborated[r["Band"]]):,} km')
        df = df[~lone].copy()
    # km per watt, the figure this project quotes for a weak-signal path.
    df['kmw'] = df['distance'] / 10.0 ** ((df['power'] - 30.0) / 10.0)
    return df


def rebase(lon, cut):
    """Put `lon` in the half-open window (cut - 360, cut]."""
    return cut - ((cut - lon) % 360.0)


def cut_meridian(records):
    """The meridian to cut the world at: the one no path crosses.

    Every path starts at this station, so the longitudes they use form one
    arc, and the rest of the planet is a gap no line passes through. Cutting
    the world in the middle of that gap means **no path is split at all** --
    no line leaves one edge of the map and resumes at the other, and no
    station sits on a second copy of a continent while its path runs to the
    first. For this run the arc runs from 65 E (the furthest-east station)
    westward to Western Australia at 115 E, leaving a 50-degree gap across
    the Indian Ocean and central Asia with nothing in it.

    This is better than cutting at the antimeridian, which runs straight
    through the VK and ZL paths -- the longest and most interesting ones.
    """
    lo = hi = records[0]['mine_ll'][1]
    for r in records:
        for _lat, lon in _ensure_continuous_path(interpolate_great_circle(
                *r['mine_ll'], *r['far_ll'], num_points=24)):
            lo, hi = min(lo, lon), max(hi, lon)
    return ((hi + lo + 360.0) / 2.0 + 180.0) % 360.0 - 180.0, hi - lo


def pairs(df):
    """One record per (direction, far-end station), carrying its bands."""
    out = []
    for (role, call), g in df.groupby(['role', 'far']):
        per_band = []
        for band in BAND_ORDER:
            b = g[g['Band'] == band]
            if b.empty:
                continue
            per_band.append({'band': band, 'decodes': len(b),
                             'best_snr': int(b['snr'].max()),
                             'km_w': int(round(b['kmw'].max()))})
        out.append({
            'role': role, 'far': call,
            'grid': g['far_loc'].iloc[0],
            'far_ll': (g['far_lat'].iloc[0], g['far_lon'].iloc[0]),
            'mine_ll': (g['my_lat'].iloc[0], g['my_lon'].iloc[0]),
            'km': int(round(g['distance'].max())),
            'azimuth': int(round(g['azimuth'].iloc[0])),
            'decodes': len(g), 'bands': per_band,
        })
    return out


def flyout(rec, call_sign=CALLSIGN):
    """The fly-out: the pair, then every spot on it, band by band.

    Styled with classes rather than inline CSS. The same fly-out is attached
    to every line and dot of a path, once per band it was decoded on, so a
    `style="..."` run repeated on each table row is most of the file.
    """
    direction = f'heard {call_sign}' if rec['role'] == 'heard_by' \
        else f'heard by {call_sign}'
    rows = ''.join(
        f'<tr><td><i style="background:{BAND_COLORS[b["band"]]}"></i></td>'
        f'<td><b>{b["band"]}</b></td><td>{b["decodes"]}&times;</td>'
        f'<td>best {b["best_snr"]} dB</td><td>{b["km_w"]:,} km/W</td></tr>'
        for b in rec['bands'])
    n_b = len(rec['bands'])
    return (
        f'<div class=wf><b>{rec["far"]}</b> {rec["grid"]}<br>{direction}<br>'
        f'{rec["km"]:,} km | {rec["azimuth"]}&deg; | '
        f'{n_b} band{"" if n_b == 1 else "s"} | '
        f'{rec["decodes"]} spot{"" if rec["decodes"] == 1 else "s"}'
        f'<table>{rows}</table></div>')


FLYOUT_CSS = """<style>
.wf{font:12px sans-serif;white-space:nowrap}
.wf>b{font-size:14px}
.wf table{margin-top:4px;border-collapse:collapse}
.wf td{padding:0 6px 0 0}
.wf i{display:inline-block;width:10px;height:10px}
</style>"""


def build(records, html_path=HTML_PATH, call_sign=CALLSIGN, zoom_start=2):
    home = records[0]['mine_ll']
    cut, used = cut_meridian(records)
    print(f'  world cut at {cut:.1f} deg, which no path crosses '
          f'({360.0 - used:.0f} deg of empty longitude)')
    # Tiles repeat, so the window (cut - 360, cut] renders as one continuous
    # world; `max_bounds` keeps the view inside it so the duplicate copy on
    # the far side of the cut is never reachable.
    spot_map = folium.Map(location=[home[0], (cut - 180.0)],
                          zoom_start=zoom_start, tiles=None,
                          prefer_canvas=True, max_bounds=True,
                          min_lat=-85, max_lat=85,
                          min_lon=cut - 360.0, max_lon=cut)
    folium.TileLayer('OpenStreetMap', control=False).add_to(spot_map)
    Fullscreen().add_to(spot_map)

    # A group per band per direction, so each can be switched independently.
    label = {'heard_by': f'heard {call_sign}',
             'heard': f'{call_sign} heard'}
    groups = {}
    for role in ('heard_by', 'heard'):
        for band in BAND_ORDER:
            groups[(role, band)] = FeatureGroup(
                name=f'{band} &nbsp;&middot;&nbsp; {label[role]}', show=True)

    for rec in records:
        html = flyout(rec, call_sign)
        # Two decimal places is about a kilometre, finer than a 4-character
        # grid square, and it keeps the file a fraction of the size. Every
        # longitude -- line and dot alike -- is rebased into the same window,
        # which is what makes them land on the same copy of the world.
        path = [(round(lat, 2), round(rebase(lon, cut), 2))
                for lat, lon in _ensure_continuous_path(
                    interpolate_great_circle(
                        rec['mine_ll'][0], rec['mine_ll'][1],
                        rec['far_ll'][0], rec['far_ll'][1], num_points=24))]
        far_point = path[-1]
        for b in rec['bands']:
            color = BAND_COLORS[b['band']]
            group = groups[(rec['role'], b['band'])]
            folium.PolyLine(
                locations=path, color=color,
                # A path decoded many times is drawn heavier, putting
                # the reliable openings forward without hiding one-offs.
                weight=min(0.6 + 0.25 * b['decodes'] ** 0.5, 3.0),
                opacity=0.5,
                popup=folium.Popup(html, max_width=360), tooltip=html,
            ).add_to(group)
            # A dot at the far end of the path, in the band's color.
            # Tooltip only on the dot; the line beside it carries the
            # popup, and the fly-out HTML is the bulk of the file.
            folium.CircleMarker(
                location=far_point, radius=2.5, color=color,
                fill=True, fill_color=color, fill_opacity=0.9, weight=0,
                tooltip=html,
            ).add_to(group)

    for g in groups.values():
        spot_map.add_child(g)

    # A star at this station, outside the groups so it never switches off.
    folium.Marker(
        location=home,
        icon=folium.DivIcon(
            icon_size=(30, 30), icon_anchor=(15, 15),
            html='<div style="font-size:26px;line-height:26px;color:#111;'
                 'text-shadow:0 0 3px #fff,0 0 3px #fff,0 0 3px #fff;'
                 'text-align:center">&#9733;</div>'),
        popup=f'{call_sign} — the deck',
        tooltip=f'{call_sign} — the deck',
    ).add_to(spot_map)

    legend = ''.join(
        f'<div><span style="display:inline-block;width:18px;height:3px;'
        f'background:{BAND_COLORS[b]};vertical-align:middle"></span> {b}</div>'
        for b in BAND_ORDER)
    spot_map.get_root().html.add_child(folium.Element(FLYOUT_CSS))
    spot_map.get_root().html.add_child(folium.Element(
        '<div style="position:fixed;bottom:18px;left:12px;z-index:9999;'
        'background:rgba(255,255,255,.92);padding:8px 10px;border-radius:4px;'
        'font:12px sans-serif;line-height:1.5">'
        '<div style="margin-bottom:3px">&#9733; <b>' + call_sign + '</b></div>'
        + legend +
        '<div style="margin-top:4px;opacity:.7">thicker = more decodes</div>'
        '</div>'))

    LayerControl(collapsed=False, position='topright').add_to(spot_map)
    spot_map.save(html_path)
    return spot_map


if __name__ == '__main__':
    df = load()
    records = pairs(df)
    heard_by = [r for r in records if r['role'] == 'heard_by']
    heard = [r for r in records if r['role'] == 'heard']
    multi = [r for r in records if len(r['bands']) > 1]

    print(f'{len(df):,} spots, '
          f'{df["time"].min():%Y-%m-%d %H:%MZ} to {df["time"].max():%Y-%m-%d %H:%MZ}')
    print(f'  {len(records):,} unique paths '
          f'({len(heard_by)} heard the deck, {len(heard)} the deck heard)')
    print(f'  {len(multi)} open on more than one band')
    print(f'  {sum(len(r["bands"]) for r in records):,} path-band lines drawn '
          f'across {2 * len(BAND_ORDER)} switchable layers')
    print('  furthest: ' + ', '.join(
        f'{r["far"]} {r["km"]:,} km'
        for r in sorted(records, key=lambda r: -r['km'])[:3]))

    build(records)
    print(f'Saved {HTML_PATH}')
