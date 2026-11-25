"""Touchstone (.s2p) sweeps from a NanoVNA, read as SWR against the bands.

Every other module here analyzes spots -- what the antenna *did*. This one
reads what the antenna *is*: a one-port S11 sweep, turned into SWR, return
loss and feedpoint impedance, and then read against the band edges the rest
of the project already uses (`wspr_analysis_utils.BAND_RANGES`) and against
the WSPR dial frequencies the spots were made on.

Why both. A sweep that says "1.9:1 somewhere in 20 m" is not the measurement
that explains a WSPR result: WSPR sits on one frequency per band, near the
bottom edge, and an end-fed half wave is resonant on a harmonic series that
does not line up with the band edges. The number that matters for a spot
count is the SWR at the dial, not the best SWR in the band.

Only S11 is used. A NanoVNA writes a four-column .s2p with S21, S12 and S22
present and zero when one port is in use, and reading them would invent a
two-port measurement that was never taken.
"""
from __future__ import annotations

import cmath
import math
import os

from wspr_analysis_utils import BAND_RANGES

# The dial frequency a WSPR transmission is referenced to, in MHz, as the
# deck's `src/wsprbands.py` has them -- the USB dial, not the audio-shifted
# carrier. Kept here as data rather than imported, because this repository
# does not depend on the cyberdeck's source tree.
# 160 m and 60 m are deliberately absent. This is a 75-10 m antenna, they
# are not among its design bands, and the operator does not work them -- so
# a 3:1 and a 5:1 on two bands nobody transmits on is noise in every table
# and two wasted panels in every figure.
WSPR_DIAL_MHZ = {
    '80m': 3.568600,
    '40m': 7.038600,
    '30m': 10.138700,
    '20m': 14.095600,
    '17m': 18.104600,
    '15m': 21.094600,
    '12m': 24.924600,
    '10m': 28.124600,
}

# What SWR is worth calling what. 2:1 is the usual "no tuner needed" line and
# 3:1 is roughly where a solid-state finals protection circuit starts folding
# back power; both are conventions, not physics, and they are named here so a
# plot and a table cannot drift apart.
SWR_GOOD = 1.5
SWR_USABLE = 2.0
SWR_MARGINAL = 3.0

Z0 = 50.0


def read_touchstone(path):
    """Read a one- or two-port Touchstone file. Returns [(hz, gamma), ...].

    Handles the `# Hz S RI R 50` and `# MHz S DB R 50` header forms, which
    are what a NanoVNA writes depending on its firmware and export menu.
    Raises ValueError on a header it does not understand rather than
    guessing: a sweep read with the wrong format is wrong everywhere and
    looks plausible.
    """
    scale, fmt = 1.0, 'RI'
    out = []
    with open(path, errors='replace') as fh:
        for line in fh:
            line = line.strip()
            if not line or line.startswith('!'):
                continue
            if line.startswith('#'):
                parts = line[1:].split()
                if not parts:
                    continue
                unit = parts[0].upper()
                scale = {'HZ': 1.0, 'KHZ': 1e3, 'MHZ': 1e6,
                         'GHZ': 1e9}.get(unit)
                if scale is None:
                    raise ValueError(f'unknown frequency unit in {line!r}')
                fmt = next((p.upper() for p in parts[1:]
                            if p.upper() in ('RI', 'MA', 'DB')), 'RI')
                continue
            cols = line.split()
            if len(cols) < 3:
                continue
            hz = float(cols[0]) * scale
            a, b = float(cols[1]), float(cols[2])
            if fmt == 'RI':
                gamma = complex(a, b)
            elif fmt == 'MA':
                gamma = cmath.rect(a, math.radians(b))
            else:                                   # DB
                gamma = cmath.rect(10 ** (a / 20.0), math.radians(b))
            out.append((hz, gamma))
    if not out:
        raise ValueError(f'no data rows in {path}')
    return out


def swr(gamma):
    """SWR from a reflection coefficient. Clamped, because |gamma| >= 1 is a
    calibration artifact and infinity propagates through every later mean."""
    g = min(abs(gamma), 0.999999)
    return (1.0 + g) / (1.0 - g)


def return_loss_db(gamma):
    g = abs(gamma)
    return 99.0 if g <= 0 else -20.0 * math.log10(g)


def impedance(gamma, z0=Z0):
    """Feedpoint impedance as (R, X). The sign of X says which way to go:
    positive is inductive, so the wire is long for that frequency."""
    denom = (1.0 - gamma.real) ** 2 + gamma.imag ** 2
    r = z0 * ((1.0 - gamma.real ** 2 - gamma.imag ** 2) / denom)
    x = z0 * (2.0 * gamma.imag / denom)
    return r, x


def verdict(value):
    if value <= SWR_GOOD:
        return 'good'
    if value <= SWR_USABLE:
        return 'usable'
    if value <= SWR_MARGINAL:
        return 'marginal'
    return 'poor'


def as_table(points):
    """[(hz, gamma)] -> [dict], one row per sweep point."""
    rows = []
    for hz, gamma in points:
        r, x = impedance(gamma)
        rows.append({
            'hz': hz,
            'mhz': hz / 1e6,
            'swr': swr(gamma),
            'return_loss_db': return_loss_db(gamma),
            'r_ohm': r,
            'x_ohm': x,
            'gamma_mag': abs(gamma),
        })
    return rows


def interpolate_swr(rows, mhz):
    """SWR at an arbitrary frequency, linearly between bracketing points.

    Needed rather than optional: a NanoVNA sweeping 1-30 MHz in 301 points
    steps 96.7 kHz, and 30 m is 50 kHz wide -- so a nearest-point lookup can
    miss an entire band, and did on the first pass at this data. Returns None
    outside the sweep instead of extrapolating.
    """
    if not rows or mhz < rows[0]['mhz'] or mhz > rows[-1]['mhz']:
        return None
    for a, b in zip(rows, rows[1:]):
        if a['mhz'] <= mhz <= b['mhz']:
            if b['mhz'] == a['mhz']:
                return a['swr']
            f = (mhz - a['mhz']) / (b['mhz'] - a['mhz'])
            return a['swr'] + f * (b['swr'] - a['swr'])
    return None


def band_summary(rows, ranges=None):
    """Best and worst SWR inside each band the sweep covers.

    The best-in-band figure is the flattering one and is reported beside the
    frequency it occurs at, because on an end-fed half wave that frequency is
    often an edge -- which is the whole reason `wspr_dial_summary` exists.
    """
    ranges = ranges or dict(BAND_RANGES)
    order = sorted(ranges, key=lambda b: ranges[b][0])
    out = []
    for band in order:
        lo, hi = ranges[band]
        inside = [r for r in rows if lo <= r['mhz'] <= hi]
        if not inside:
            # Not "no data": the band is inside the sweep but narrower than
            # the step. Say which, so a missing row is never read as a
            # missing measurement.
            covered = rows[0]['mhz'] <= lo and hi <= rows[-1]['mhz']
            out.append({'band': band, 'low_mhz': lo, 'high_mhz': hi,
                        'best_swr': None, 'best_mhz': None,
                        'worst_swr': None,
                        'note': 'band narrower than the sweep step'
                                if covered else 'outside the sweep'})
            continue
        best = min(inside, key=lambda r: r['swr'])
        worst = max(inside, key=lambda r: r['swr'])
        out.append({
            'band': band, 'low_mhz': lo, 'high_mhz': hi,
            'best_swr': best['swr'], 'best_mhz': best['mhz'],
            'worst_swr': worst['swr'],
            'r_ohm': best['r_ohm'], 'x_ohm': best['x_ohm'],
            'points': len(inside), 'note': '',
        })
    return out


def wspr_dial_summary(rows, dials=None):
    """SWR at each WSPR dial frequency -- the number a spot count rides on."""
    dials = dials or WSPR_DIAL_MHZ
    out = []
    for band, mhz in sorted(dials.items(), key=lambda kv: kv[1]):
        value = interpolate_swr(rows, mhz)
        out.append({'band': band, 'dial_mhz': mhz, 'swr': value,
                    'verdict': verdict(value) if value else 'outside the sweep'})
    return out


def resonances(rows, below=6.0):
    """Local SWR minima. Not the same thing as resonance, strictly.

    Resonance is where reactance crosses zero; a minimum in SWR is where the
    whole load is closest to 50 ohms, and the two coincide only when the
    resistance at the crossing happens to be near 50.

    An end-fed wire alternates the two kinds of crossing, a series
    resonance where X rises through zero and a parallel one where it falls,
    and only some of them land near an SWR minimum. The 2026-11-24 sweep has
    fifteen crossings in a strict S-A-S-A-... order against eight SWR
    minima, which is what the structure does on its own.

    One caveat worth knowing before reading much into `x_ohm`: SWR depends
    only on the magnitude of the reflection coefficient, so it survives any
    length of lossless feedline, while R and X separately do not, because a
    line rotates the impedance a full turn every half wavelength. Minima and
    the Q figures built from their widths are safe at any measurement plane.
    Reactance is only the antenna's if the analyzer was at the antenna.

    An end-fed half wave resonates on a harmonic series of its fundamental,
    and those harmonics do not land on the band edges. Listing them is what
    turns "30 m is bad" into "the third harmonic is 600 kHz above 30 m",
    which is a different and fixable statement.
    """
    out = []
    for prev, here, nxt in zip(rows, rows[1:], rows[2:]):
        if here['swr'] < prev['swr'] and here['swr'] <= nxt['swr'] \
                and here['swr'] < below:
            out.append(here)
    return out


def reactance_zeros(rows, z0=Z0):
    """Where reactance crosses zero: resonance in the strict sense.

    A minimum in SWR is where the whole load is nearest 50 ohms; a zero
    crossing of X is where the load is purely resistive. The two coincide
    only when the resistance at the crossing is itself near 50, so this
    returns the resistance there and the SWR that resistance alone implies.
    Compare that against the SWR at the nearby minimum: when they differ,
    the difference is the part of the mismatch that is not reactance.

    Returned as [{'mhz', 'r_ohm', 'swr_at_zero', 'slope_ohm_per_khz'}],
    interpolated linearly in frequency across the sign change. A 96.7 kHz
    step cannot place a crossing finer than that, so the figure is good to
    roughly a step.

    **Feedline rotates all of this.** Unlike SWR, a zero crossing of X is
    not invariant under a length of line, so on a sweep taken at the shack
    end these frequencies belong to the antenna plus its feedline. What does
    NOT indicate a feedline: crossings outnumbering the SWR minima. A bare
    end-fed wire alternates series and parallel resonances, so roughly twice
    the minima is the expected count, and 2026-11-24 gives a clean
    alternating fifteen. Its harmonics are spaced 3.590 MHz, a 279 ns round
    trip, consistent with 132 ft of wire and nothing else.

    A trap at a deep dip. The whole impedance sits inside a circle of
    radius 50*2|G|/(1-|G|^2), so at SWR 1.09 no point in the dip can be more
    than 4.3 ohms reactive whatever the antenna is doing. "X never reached
    zero" is then a statement about two or three ohms, which the sweep step
    and the feedline each move by more than that. It is not a loss
    signature. Loaded Q is the loss measurement; see `resonance_bandwidths`.

    Both kinds of crossing are included. An end-fed half wave alternates
    series resonances, where R is low or near 50, with parallel ones between
    the harmonics, where R runs to several hundred ohms; the resistance
    column is what tells them apart.
    """
    out = []
    for lo, hi in zip(rows, rows[1:]):
        x0, x1 = lo['x_ohm'], hi['x_ohm']
        if x0 == 0.0 or (x0 < 0.0) == (x1 < 0.0) or x1 == x0:
            continue
        t = -x0 / (x1 - x0)
        mhz = lo['mhz'] + t * (hi['mhz'] - lo['mhz'])
        r = lo['r_ohm'] + t * (hi['r_ohm'] - lo['r_ohm'])
        g = abs(r - z0) / (r + z0) if (r + z0) else 1.0
        step_khz = (hi['mhz'] - lo['mhz']) * 1000.0
        out.append({'mhz': mhz, 'r_ohm': r,
                    'swr_at_zero': (1.0 + g) / (1.0 - g) if g < 1 else None,
                    # Rising X is a series resonance, falling X a parallel
                    # one. Feedline rotation can swap them, so this labels
                    # the measurement, not the antenna.
                    'slope_ohm_per_khz': (x1 - x0) / step_khz})
    return out


def minima_vs_zeros(rows, below=6.0, near_khz=200.0):
    """Each SWR minimum paired with its nearest reactance zero, if it has one.

    `offset_khz` is the zero minus the minimum, so a positive number means
    the purely resistive point sits above the best match. `zero` is None
    when no crossing falls within `near_khz`, which is not a rounding
    detail: a resonance damped hard enough brings reactance down toward
    zero and turns back without reaching it, and three minima on the
    2026-11-24 sweep do exactly that.
    """
    zeros = reactance_zeros(rows)
    out = []
    for m in resonances(rows, below=below):
        best, gap = None, None
        for z in zeros:
            d = abs(z['mhz'] - m['mhz'])
            if gap is None or d < gap:
                best, gap = z, d
        if best is None or gap * 1000.0 > near_khz:
            out.append({'minimum': m, 'zero': None, 'offset_khz': None})
        else:
            out.append({'minimum': m, 'zero': best,
                        'offset_khz': (best['mhz'] - m['mhz']) * 1000.0})
    return out


def spans_under(rows, limit):
    """Contiguous frequency spans where SWR stays at or under `limit`.

    Returned as (low_mhz, high_mhz) pairs at sweep resolution. The edges are
    sweep points, not interpolated crossings: a 96.7 kHz step cannot
    honestly resolve a band edge any finer.
    """
    spans, start = [], None
    for row in rows:
        if row['swr'] <= limit and start is None:
            start = row['mhz']
        elif row['swr'] > limit and start is not None:
            spans.append((start, row['mhz']))
            start = None
    if start is not None:
        spans.append((start, rows[-1]['mhz']))
    return spans


def find_fundamental(rows, below=6.0, max_mhz=5.0):
    """The half-wave resonance, as the DEEPEST match below `max_mhz`.

    Not the lowest-frequency minimum, which is what this did first and got
    wrong: a 1-30 MHz sweep of a 75-10 m end-fed half wave shows a shallow
    dip around 1.2 MHz -- 18 ohms and 2.7:1, the transformer and the feedline
    doing something uninteresting -- and taking that as the fundamental made
    every harmonic an 18% miss against a frequency the antenna does not
    resonate on. The half-wave resonance is the deep one, and depth is what
    identifies it.
    """
    candidates = [r for r in resonances(rows, below=below)
                  if r['mhz'] <= max_mhz]
    if not candidates:
        return None
    return min(candidates, key=lambda r: r['swr'])['mhz']


# How far off an integer multiple a resonance may be and still be called
# part of the harmonic series. End effects pull the real harmonics of an
# end-fed half wave a percent or two low; anything off by more than this is a
# different feature of the match, not a harmonic that moved.
HARMONIC_TOLERANCE_PCT = 5.0


def harmonic_fit(rows, below=6.0, fundamental_mhz=None, max_mhz=5.0,
                 tolerance_pct=HARMONIC_TOLERANCE_PCT):
    """The resonance series read as harmonics of the half-wave resonance.

    Reports, per resonance, which harmonic it is nearest and by how much it
    misses. An end-fed half wave that is behaving correctly shows a series
    slightly BELOW exact integer multiples -- end effects and the velocity
    factor of the wire both lower the higher resonances relative to the
    fundamental -- so a uniform small negative error is the healthy result,
    not a fault. A single outlier against that trend is usually the matching
    transformer rather than the wire.

    Resonances that do not land within `tolerance_pct` of an integer
    multiple are reported with `harmonic = None` rather than forced into the
    series. This data has two of them -- a shallow 1.19 MHz dip and a
    1.41:1 point at 2.837 MHz on the skirt of the fundamental -- and calling
    the second one "n=1, 21% low" was arithmetic rather than a measurement.
    """
    found = resonances(rows, below=below)
    if not found:
        return []
    base = fundamental_mhz or find_fundamental(rows, below=below,
                                               max_mhz=max_mhz)
    if not base:
        return []
    out = []
    for row in found:
        n = max(1, round(row['mhz'] / base))
        predicted = base * n
        error_pct = 100.0 * (row['mhz'] - predicted) / predicted
        if abs(error_pct) > tolerance_pct:
            out.append({'mhz': row['mhz'], 'swr': row['swr'],
                        'harmonic': None, 'predicted_mhz': None,
                        'error_khz': None, 'error_pct': None})
            continue
        out.append({
            'mhz': row['mhz'], 'swr': row['swr'], 'harmonic': n,
            'predicted_mhz': predicted,
            'error_khz': (row['mhz'] - predicted) * 1e3,
            'error_pct': error_pct,
        })
    return out


def resonance_bandwidths(rows, limit=SWR_USABLE, below=6.0, **kw):
    """The span each resonance holds under `limit`, and its loaded Q.

    **The most diagnostic number a one-port sweep gives up.** A resonance is
    narrow because energy leaves it slowly, and the only ways energy leaves
    an antenna are radiation and loss. Comparing the width of one resonance
    against the others on the same wire cancels most of what is hard to know
    about an installation: same wire, same height, same ground, same
    feedline, measured in the same sweep. A fundamental an order of
    magnitude broader than every one of its harmonics is therefore not a
    tuning result. It is a loss that acts at the fundamental and not above
    it, and the design has exactly one element like that.

    Q here is f / bandwidth at `limit`, which is a loaded Q against an SWR
    contour rather than a half-power Q. It is comparable between the rows of
    one sweep, which is what it is for, and not with a figure from elsewhere.
    """
    spans = spans_under(rows, limit)
    out = []
    for row in harmonic_fit(rows, below=below, **kw):
        if row['harmonic'] is None:
            continue
        span = next(((lo, hi) for lo, hi in spans if lo <= row['mhz'] <= hi),
                    None)
        if span is None:
            out.append({**row, 'span_mhz': None, 'bandwidth_mhz': None,
                        'bandwidth_pct': None, 'q': None})
            continue
        lo, hi = span
        width = hi - lo
        out.append({**row, 'span_mhz': span, 'bandwidth_mhz': width,
                    'bandwidth_pct': 100.0 * width / row['mhz'],
                    'q': row['mhz'] / width if width else None})
    return out


def plot_resonance_q(rows, path, title='', limit=SWR_USABLE):
    """Loaded Q against harmonic number: the loss signature, as one picture.

    Drawn as bars rather than a line. The x axis is a harmonic index, which
    is an integer and not a continuum, and a line between n=1 and n=2 would
    imply values in between that do not exist.
    """
    import matplotlib.pyplot as plt

    found = [r for r in resonance_bandwidths(rows, limit=limit)
             if r['q'] is not None]
    if not found:
        return None
    labels = [f"n={r['harmonic']}\n{r['mhz']:.2f}" for r in found]
    values = [r['q'] for r in found]

    fig, ax = plt.subplots(figsize=(10, 5.2))
    bars = ax.bar(labels, values,
                  color=['tab:red' if r['harmonic'] == 1 else 'tab:blue'
                         for r in found])
    for bar, row in zip(bars, found):
        ax.annotate(f"{row['q']:.0f}",
                    xy=(bar.get_x() + bar.get_width() / 2.0, row['q']),
                    xytext=(0, 3), textcoords='offset points',
                    ha='center', fontsize=10)
    ax.set_ylabel(f'Loaded Q (f / {limit:g}:1 bandwidth)')
    ax.set_xlabel('Harmonic, and its frequency in MHz')
    ax.set_title(title or 'Resonance sharpness by harmonic')
    ax.grid(True, axis='y', alpha=0.3)
    fig.tight_layout()
    fig.savefig(path, dpi=120, bbox_inches='tight')
    plt.close(fig)
    return path


# -- plotting -------------------------------------------------------------
#
# Figures go to `analysis_images/` beside the rest of the 75-10 m set, as
# `readme.md` expects. Written with an explicit Agg backend by the caller:
# these run headless on the same machine that builds the slides.

def plot_sweep(rows, path, title='', bands=None, dials=None,
               swr_ceiling=6.0):
    """SWR across the sweep, with the band segments and the WSPR dials on it.

    The y axis is clipped at `swr_ceiling` deliberately. Between the
    harmonics an end-fed half wave reaches an SWR in the tens, and an
    unclipped axis spends its whole range on frequencies nobody transmits on
    while flattening every band to the bottom pixel.

    The legend sits under the axes rather than inside them: the bands are
    narrow and scattered across 30 MHz, so there is no corner of this plot
    that is reliably empty -- an inside legend covered the 10 m label.
    """
    import matplotlib.pyplot as plt

    bands = bands or dict(BAND_RANGES)
    dials = dials or WSPR_DIAL_MHZ

    mhz = [r['mhz'] for r in rows]
    value = [min(r['swr'], swr_ceiling) for r in rows]

    fig, ax = plt.subplots(figsize=(13.5, 6.2))

    # Bands are drawn as a shaded span AND a tick at the top, because at
    # this scale 30 m is 50 kHz wide -- a span alone is one pixel.
    label_y = swr_ceiling - 0.08 * (swr_ceiling - 1.0)
    for band, (lo, hi) in sorted(bands.items(), key=lambda kv: kv[1][0]):
        ax.axvspan(lo, hi, color='tab:blue', alpha=0.16, lw=0, zorder=0)
        ax.annotate(band, xy=((lo + hi) / 2.0, label_y),
                    ha='center', va='center', fontsize=9, color='tab:blue',
                    rotation=90,
                    bbox=dict(boxstyle='round,pad=0.18', fc='white',
                              ec='none', alpha=0.85), zorder=6)

    ax.axhline(SWR_USABLE, color='tab:green', ls='--', lw=1.4, zorder=2,
               label=f'{SWR_USABLE:g}:1')
    ax.axhline(SWR_MARGINAL, color='tab:orange', ls='--', lw=1.4, zorder=2,
               label=f'{SWR_MARGINAL:g}:1')
    ax.plot(mhz, value, color='0.15', lw=1.8, zorder=3, label='SWR')

    for band, dial in dials.items():
        at = interpolate_swr(rows, dial)
        if at is None:
            continue
        ax.plot([dial], [min(at, swr_ceiling)], marker='o', ms=7,
                mfc='white', mec='tab:red', mew=2.0, zorder=5)
    ax.plot([], [], marker='o', ms=7, mfc='white', mec='tab:red', mew=2.0,
            ls='none', label='WSPR dial')

    ax.set_xlabel('Frequency (MHz)')
    ax.set_ylabel(f'SWR (clipped at {swr_ceiling:g}:1)')
    ax.set_ylim(1.0, swr_ceiling)
    # Ticks before limits: setting ticks outside the data range lets
    # matplotlib widen the view, which left a blank 0-1 MHz margin.
    ax.set_xticks([t for t in range(0, 31, 2)])
    ax.set_xlim(min(mhz), max(mhz))
    ax.set_title(title or 'S11 sweep')
    ax.grid(True, alpha=0.3, zorder=1)
    ax.legend(loc='upper center', bbox_to_anchor=(0.5, -0.13), ncol=4,
              frameon=False)
    fig.tight_layout()
    fig.savefig(path, dpi=120, bbox_inches='tight')
    plt.close(fig)
    return path


def plot_swr_and_reactance(rows, path, title='', bands=None,
                           swr_ceiling=6.0, ohm_clip=250.0):
    """SWR and feedpoint impedance on one frequency axis, as two panels.

    Stacked and sharing the x axis rather than drawn as two y scales on one
    set of axes. SWR is a dimensionless ratio floored at 1 and impedance is
    in ohms and signed; putting them on twin axes would let the choice of
    scaling decide which crossings look aligned, which is the question the
    figure exists to answer.

    What to read off it. A purple line marks a series resonance, where X
    rises through zero, and a gray line a parallel one, where X falls
    through zero. An end-fed wire alternates them, so about twice as many
    lines as SWR dips is the expected picture and not a fault. Which kind a
    given band sits on decides which way the usual trim rules run, and on
    this antenna it is not the same kind on every band.

    The shaded envelope on the lower panel is the whole point of drawing
    the two together. SWR confines the impedance to a circle, so at any
    frequency the reactance cannot exceed 50*2|G|/(1-|G|^2); where SWR is
    low that envelope pinches shut and X has nowhere to go. It is drawn
    only under `SWR_MARGINAL`, since a looser bound than the axis is no
    bound at all. Reading
    significance into a few ohms of reactance at the bottom of a deep dip,
    or into whether X quite reached zero there, is reading the width of
    that pinch. Loaded Q measures loss; reactance at a dip does not.
    """
    import matplotlib
    import matplotlib.patches
    import matplotlib.pyplot as plt

    bands = bands or dict(BAND_RANGES)

    mhz = [r['mhz'] for r in rows]
    swr_v = [min(r['swr'], swr_ceiling) for r in rows]
    r_v = [min(r['r_ohm'], ohm_clip) for r in rows]
    x_v = [max(-ohm_clip, min(r['x_ohm'], ohm_clip)) for r in rows]

    # The reactance the measured SWR allows at each frequency, which is the
    # radius of the constant-SWR circle in the impedance plane. Drawn only
    # where SWR is under SWR_MARGINAL: above that the bound is wider than
    # the axis and says nothing, and a band of shading across the whole
    # panel buries the curves it exists to qualify.
    cap = []
    for row in rows:
        g = row['gamma_mag']
        if row['swr'] > SWR_MARGINAL or g >= 1:
            cap.append(float('nan'))
        else:
            cap.append(min(Z0 * 2.0 * g / (1.0 - g * g), ohm_clip))

    zeros = reactance_zeros(rows)
    series = [z for z in zeros if z['slope_ohm_per_khz'] > 0]
    parallel = [z for z in zeros if z['slope_ohm_per_khz'] <= 0]
    mins = resonances(rows, below=swr_ceiling)

    fig, (top, bot) = plt.subplots(
        2, 1, figsize=(13.5, 8.8), sharex=True,
        gridspec_kw={'height_ratios': [1.0, 1.0], 'hspace': 0.07})

    for ax in (top, bot):
        for lo, hi in bands.values():
            ax.axvspan(lo, hi, color='tab:blue', alpha=0.16, lw=0, zorder=0)
        # Drawn on both panels so the eye can carry a frequency from one to
        # the other without a ruler.
        for z in parallel:
            ax.axvline(z['mhz'], color='0.6', ls=':', lw=1.0, zorder=2)
        for z in series:
            ax.axvline(z['mhz'], color='tab:purple', ls=':', lw=1.2,
                       zorder=2)
        ax.grid(True, alpha=0.3, zorder=1)

    label_y = swr_ceiling - 0.07 * (swr_ceiling - 1.0)
    for band, (lo, hi) in sorted(bands.items(), key=lambda kv: kv[1][0]):
        top.annotate(band, xy=((lo + hi) / 2.0, label_y),
                     ha='center', va='center', fontsize=9, color='tab:blue',
                     rotation=90,
                     bbox=dict(boxstyle='round,pad=0.18', fc='white',
                               ec='none', alpha=0.85), zorder=6)

    top.axhline(SWR_USABLE, color='tab:green', ls='--', lw=1.4, zorder=3)
    top.plot(mhz, swr_v, color='0.15', lw=1.8, zorder=4)
    for m in mins:
        top.plot([m['mhz']], [min(m['swr'], swr_ceiling)], marker='o', ms=8,
                 mfc='white', mec='tab:red', mew=2.0, zorder=6)
    top.set_ylabel(f'SWR (clipped at {swr_ceiling:g}:1)')
    top.set_ylim(1.0, swr_ceiling)
    top.set_title(title or 'SWR and feedpoint impedance')

    bot.fill_between(mhz, [-c for c in cap], cap, color='tab:orange',
                     alpha=0.22, lw=0, zorder=1)
    bot.axhline(0.0, color='0.35', lw=1.2, zorder=3)
    bot.axhline(Z0, color='tab:green', ls='--', lw=1.2, zorder=3)
    bot.plot(mhz, r_v, color='tab:blue', lw=1.8, zorder=4)
    bot.plot(mhz, x_v, color='tab:orange', lw=1.8, zorder=5)
    for z in zeros:
        bot.plot([z['mhz']], [0.0], marker='o', ms=6, mfc='white',
                 mec=('tab:purple' if z['slope_ohm_per_khz'] > 0 else '0.5'),
                 mew=1.8, zorder=6)
    bot.set_ylabel(f'Ohms (clipped at {ohm_clip:g})')
    bot.set_ylim(-ohm_clip * 0.8, ohm_clip)
    bot.set_xlabel('Frequency (MHz)')
    # Ticks before limits, as in `plot_sweep`: ticks outside the data range
    # let matplotlib widen the view and open a blank margin below 1 MHz.
    bot.set_xticks([t for t in range(0, 31, 2)])
    bot.set_xlim(min(mhz), max(mhz))

    # One legend for both panels, under the figure. The bands are narrow and
    # scattered across 30 MHz, so neither panel has a corner that is
    # reliably empty: an inside legend covered the 15 m and 10 m labels.
    marks = [
        plt.Line2D([], [], color='0.15', lw=1.8, label='SWR'),
        plt.Line2D([], [], color='tab:blue', lw=1.8, label='R'),
        plt.Line2D([], [], color='tab:orange', lw=1.8, label='X'),
        matplotlib.patches.Patch(
            facecolor='tab:orange', alpha=0.22,
            label=f'reactance the SWR allows (under {SWR_MARGINAL:g}:1)'),
        plt.Line2D([], [], color='tab:green', ls='--', lw=1.4,
                   label=f'{SWR_USABLE:g}:1 and {Z0:g} ohm'),
        plt.Line2D([], [], color='tab:purple', ls=':', lw=1.2,
                   label=f'series resonance, X rising ({len(series)})'),
        plt.Line2D([], [], color='0.6', ls=':', lw=1.0,
                   label=f'parallel resonance, X falling ({len(parallel)})'),
        plt.Line2D([], [], marker='o', ms=8, mfc='white', mec='tab:red',
                   mew=2.0, ls='none', label='SWR minimum'),
    ]
    fig.legend(handles=marks, loc='upper center',
               bbox_to_anchor=(0.5, 0.055), ncol=4, frameon=False,
               fontsize=10)

    fig.savefig(path, dpi=120, bbox_inches='tight')
    plt.close(fig)
    return path


def plot_band_panels(rows, path, title='', bands=None, dials=None,
                     swr_ceiling=6.0, ncols=4):
    """One small panel per band: SWR across that band alone.

    The full sweep answers "what is this antenna"; this answers "what does
    it do where I transmit". At full-sweep scale a 50 kHz band is a single
    pixel and the slope across a band -- which is the thing that decides
    whether the WSPR dial at the bottom edge is matched -- is invisible.
    """
    import matplotlib.pyplot as plt

    bands = bands or dict(BAND_RANGES)
    dials = dials or WSPR_DIAL_MHZ
    order = sorted(bands, key=lambda b: bands[b][0])
    nrows = -(-len(order) // ncols)

    fig, axes = plt.subplots(nrows, ncols, figsize=(3.4 * ncols, 2.7 * nrows),
                             squeeze=False)
    for index, band in enumerate(order):
        ax = axes[index // ncols][index % ncols]
        lo, hi = bands[band]
        # A margin either side, so a band sitting on the skirt of a
        # resonance shows which way the curve is going.
        pad = max((hi - lo) * 0.6, 0.05)
        near = [r for r in rows if lo - pad <= r['mhz'] <= hi + pad]
        if len(near) < 2:
            ax.set_axis_off()
            continue
        ax.plot([r['mhz'] for r in near],
                [min(r['swr'], swr_ceiling) for r in near],
                color='0.15', lw=1.8, zorder=3)
        ax.axvspan(lo, hi, color='tab:blue', alpha=0.16, lw=0, zorder=0)
        ax.axhline(SWR_USABLE, color='tab:green', ls='--', lw=1.2, zorder=2)
        ax.axhline(SWR_MARGINAL, color='tab:orange', ls='--', lw=1.2,
                   zorder=2)
        dial = dials.get(band)
        if dial is not None:
            at = interpolate_swr(rows, dial)
            if at is not None and lo - pad <= dial <= hi + pad:
                ax.plot([dial], [min(at, swr_ceiling)], marker='o', ms=8,
                        mfc='white', mec='tab:red', mew=2.0, zorder=5)
                ax.annotate(f'{at:.2f}:1', xy=(dial, min(at, swr_ceiling)),
                            xytext=(4, 6), textcoords='offset points',
                            fontsize=9, color='tab:red')
        ax.set_title(band, fontsize=11)
        ax.set_ylim(1.0, swr_ceiling)
        ax.set_xlim(lo - pad, hi + pad)
        ax.tick_params(labelsize=8)
        ax.grid(True, alpha=0.3, zorder=1)
    for spare in range(len(order), nrows * ncols):
        axes[spare // ncols][spare % ncols].set_axis_off()

    fig.suptitle(title or 'SWR across each band', fontsize=13)
    fig.supxlabel('Frequency (MHz)', fontsize=10)
    fig.supylabel(f'SWR (clipped at {swr_ceiling:g}:1)', fontsize=10)
    fig.tight_layout()
    fig.savefig(path, dpi=120, bbox_inches='tight')
    plt.close(fig)
    return path


def plot_dial_bars(rows, path, title='', dials=None):
    """SWR at each WSPR dial as bars -- the operating view of the same sweep.

    Separate from `plot_sweep` because it answers a different question. The
    sweep says what the antenna is; this says what it does on the ten
    frequencies the spots in this repository were actually made on.
    """
    import matplotlib.pyplot as plt

    summary = [row for row in wspr_dial_summary(rows, dials)
               if row['swr'] is not None]
    if not summary:
        return None
    colors = {'good': 'tab:green', 'usable': 'tab:olive',
              'marginal': 'tab:orange', 'poor': 'tab:red'}

    labels = [r['band'] for r in summary]
    values = [r['swr'] for r in summary]
    fig, ax = plt.subplots(figsize=(10, 5.5))
    bars = ax.bar(labels, values,
                  color=[colors[r['verdict']] for r in summary])
    ax.axhline(SWR_USABLE, color='tab:green', ls='--', lw=1.4,
               label=f'{SWR_USABLE:g}:1')
    ax.axhline(SWR_MARGINAL, color='tab:orange', ls='--', lw=1.4,
               label=f'{SWR_MARGINAL:g}:1')
    for bar, row in zip(bars, summary):
        ax.annotate(f"{row['swr']:.2f}",
                    xy=(bar.get_x() + bar.get_width() / 2.0, row['swr']),
                    xytext=(0, 3), textcoords='offset points',
                    ha='center', fontsize=10)
    ax.set_ylabel('SWR at the WSPR dial')
    ax.set_title(title or 'SWR at the WSPR dial frequency')
    ax.legend(loc='upper left', framealpha=0.95)
    ax.grid(True, axis='y', alpha=0.3)
    fig.tight_layout()
    fig.savefig(path, dpi=120)
    plt.close(fig)
    return path


def report(path, label='', out_dir='analysis_images', prefix=''):
    """Read a sweep, print the tables, write both figures. Returns the rows."""
    rows = as_table(read_touchstone(path))
    name = label or os.path.basename(path)

    print(f'{name}: {len(rows)} points, '
          f'{rows[0]["mhz"]:.3f}-{rows[-1]["mhz"]:.3f} MHz, '
          f'step {(rows[1]["mhz"] - rows[0]["mhz"]) * 1e3:.1f} kHz')

    print('\nSWR at the WSPR dial frequency')
    print(f'{"band":<6} {"dial MHz":>11} {"SWR":>6}  verdict')
    for row in wspr_dial_summary(rows):
        if row['swr'] is None:
            print(f'{row["band"]:<6} {row["dial_mhz"]:>11.6f} '
                  f'{"--":>6}  {row["verdict"]}')
        else:
            print(f'{row["band"]:<6} {row["dial_mhz"]:>11.6f} '
                  f'{row["swr"]:>6.2f}  {row["verdict"]}')

    print('\nBest and worst SWR inside each band')
    print(f'{"band":<6} {"range MHz":<14} {"best":>6} {"@MHz":>8} '
          f'{"worst":>6}   R+jX at best')
    for row in band_summary(rows):
        span = f'{row["low_mhz"]:g}-{row["high_mhz"]:g}'
        if row['best_swr'] is None:
            print(f'{row["band"]:<6} {span:<14} {"--":>6} {"--":>8} '
                  f'{"--":>6}   ({row["note"]})')
            continue
        print(f'{row["band"]:<6} {span:<14} {row["best_swr"]:>6.2f} '
              f'{row["best_mhz"]:>8.3f} {row["worst_swr"]:>6.2f}   '
              f'{row["r_ohm"]:>6.1f} {row["x_ohm"]:+7.1f} j')

    base = find_fundamental(rows)
    print(f'\nResonances, read as harmonics of {base:.3f} MHz'
          if base else '\nResonances')
    print(f'{"MHz":>8} {"SWR":>6} {"n":>3} {"predicted":>10} {"error":>9}')
    for row in harmonic_fit(rows):
        if row['harmonic'] is None:
            print(f'{row["mhz"]:>8.3f} {row["swr"]:>6.2f} {"--":>3} '
                  f'{"--":>10} {"not in the series":>9}')
            continue
        print(f'{row["mhz"]:>8.3f} {row["swr"]:>6.2f} {row["harmonic"]:>3} '
              f'{row["predicted_mhz"]:>10.3f} {row["error_pct"]:>8.1f}%')

    print('\nResonance sharpness: how wide each one is, and its loaded Q')
    print(f'{"n":>3} {"MHz":>8} {"2:1 span MHz":>14} {"% of f":>8} {"Q":>5}')
    for row in resonance_bandwidths(rows):
        if row['q'] is None:
            continue
        print(f'{row["harmonic"]:>3} {row["mhz"]:>8.3f} '
              f'{row["bandwidth_mhz"]:>14.3f} {row["bandwidth_pct"]:>7.1f}% '
              f'{row["q"]:>5.0f}')

    print('\nResonance in the strict sense: where reactance crosses zero')
    print(f'{"SWR min MHz":>12} {"SWR":>6} {"X there":>8} '
          f'{"X=0 MHz":>9} {"offset kHz":>11} {"R at X=0":>9} {"SWR(R)":>7}')
    for pair in minima_vs_zeros(rows):
        m, z = pair['minimum'], pair['zero']
        if z is None:
            print(f'{m["mhz"]:>12.3f} {m["swr"]:>6.2f} {m["x_ohm"]:>+8.1f} '
                  f'{"none":>9} {"--":>11} {"--":>9} {"--":>7}   '
                  f'no crossing within 200 kHz')
            continue
        swr_r = z['swr_at_zero']
        print(f'{m["mhz"]:>12.3f} {m["swr"]:>6.2f} {m["x_ohm"]:>+8.1f} '
              f'{z["mhz"]:>9.3f} {pair["offset_khz"]:>+11.0f} '
              f'{z["r_ohm"]:>9.1f} '
              f'{(f"{swr_r:.2f}" if swr_r else "--"):>7}')

    for limit in (SWR_USABLE, SWR_MARGINAL):
        spans = spans_under(rows, limit)
        pretty = ', '.join(f'{a:.2f}-{b:.2f}' for a, b in spans) or 'nowhere'
        print(f'\nunder {limit:g}:1 — {pretty}')

    os.makedirs(out_dir, exist_ok=True)
    stem = prefix or 'antenna_sweep'
    one = plot_sweep(rows, os.path.join(out_dir, f'{stem}_swr.png'),
                     title=f'{name} - S11 sweep')
    two = plot_dial_bars(rows, os.path.join(out_dir, f'{stem}_wspr_dial.png'),
                         title=f'{name} - SWR at the WSPR dial')
    three = plot_band_panels(rows, os.path.join(out_dir, f'{stem}_bands.png'),
                             title=f'{name} - SWR across each band')
    four = plot_resonance_q(rows, os.path.join(out_dir, f'{stem}_q.png'),
                            title=f'{name} - resonance sharpness')
    five = plot_swr_and_reactance(
        rows, os.path.join(out_dir, f'{stem}_swr_reactance.png'),
        title=f'{name} - SWR and feedpoint impedance')
    print(f'\nwrote {one}')
    for extra in (two, three, four, five):
        if extra:
            print(f'wrote {extra}')
    return rows
