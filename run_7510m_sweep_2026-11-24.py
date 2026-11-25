#!/usr/bin/env python
# coding: utf-8
"""S11 sweep of the 75-10 m end-fed half wave, 2026-11-24.

A NanoVNA-F V2 sweep taken after the antenna had been up for months with no
adjustment of any kind -- no retuning, no re-dressing of the wire, no change
to the transformer. The point of the measurement is the absence of
intervention, so nothing here corrects for it.

Run from the repository root:

    python run_7510m_sweep_2026-11-24.py

Writes two figures into `analysis_images/` beside the rest of the 75-10 m
set and prints the tables the readme quotes.
"""
import matplotlib
matplotlib.use('Agg')

import antenna_sweep

SWEEP = '7510m_s11_sweep_2026-11-24.s2p'
LABEL = '75-10 m EFHW, 2026-11-24'
PREFIX = '7510m_sweep_2026-11-24'

rows = antenna_sweep.report(SWEEP, label=LABEL, prefix=PREFIX)

# The operating consequence, stated separately from the measurement. A tuner
# at the radio matches any of these; what it cannot do is change what the
# antenna is, so the resonance series below is the thing to compare against
# the next sweep rather than the SWR figures above.
print('\nHarmonic series, as a baseline for the next sweep')
fit = [r for r in antenna_sweep.harmonic_fit(rows)
       if r['harmonic'] is not None]
base = antenna_sweep.find_fundamental(rows)
if fit and base:
    print(f'fundamental {base:.3f} MHz, {len(fit)} resonances in the series')
    errors = [r['error_pct'] for r in fit if r['harmonic'] > 1]
    if errors:
        print(f'harmonic error: {min(errors):+.1f}% to {max(errors):+.1f}%, '
              f'mean {sum(errors) / len(errors):+.1f}%')
    worst = max(fit, key=lambda r: abs(r['error_pct']))
    print(f'largest: n={worst["harmonic"]} at {worst["mhz"]:.3f} MHz, '
          f'{worst["error_pct"]:+.1f}% ({worst["error_khz"]:+.0f} kHz)')
