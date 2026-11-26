# AGENTS.md — WSPR analysis

Parameterized Jupyter notebooks that analyze WSPR spot captures for a callsign:
band openings, distance profiling, geographic spread, SNR-vs-distance, TX/RX
asymmetry, azimuthal pattern, normalized efficiency, takeoff angle, SSB
feasibility, and an interactive path map.

## Start here

| Read | For |
|---|---|
| `readme.md` | Every analysis: purpose, how to interpret, actual findings |
| `wspr_7510_analysis.ipynb` | The main notebook (75-10 m EFHW dataset) |
| `analysis_images/` | Rendered figures, referenced by the readme and the blog |

Note the readme is lowercase `readme.md`.

## Things that cost a lot to rediscover

- **One configuration cell at the top of the notebook drives everything** —
  `TSV_FILENAME`, `CALLSIGN`, `START_UTC`, `END_UTC`, `DOWNLOAD_FROM_API`.
- **The live API download does not work yet.** Use the TSV path. The readme
  describes the API route as though it works; the blog write-up says plainly
  that it does not. Believe the blog.
- **There are four antennas and several captures** — the 75-10 m EFHW, plus
  15 m and 20 m field-day dipoles and a center-loaded 40 m dipole. The EFHW
  has three captures: June, the October three-day, and
  `7510m_cyberdeck_2026-11-24_spots.tsv` (3,723 spots, 13:16-22:00 UTC, 5 W,
  `run_7510m_cyberdeck_2026-11-24.py`). Comparisons between antennas are the
  point; a number for one antenna alone is weak.
- **Do not claim a change from a small sample.** Two spots out of nine is
  consistent with almost any true rate. This project has already produced one
  retraction from exactly that mistake; check whether a difference survives
  before writing it down.
- **Geometry has its own tests** (`test_geodesic_geometry.py`,
  `test_api_comparison.py`) because a plausible-looking great-circle map is the
  easiest thing in the world to get wrong.

## Antenna sweeps, not just spots

`antenna_sweep.py` reads a NanoVNA Touchstone file as SWR, return loss and
feedpoint impedance, against the same `BAND_RANGES` the spot analysis uses so
a band means one thing across the repository. `run_7510m_sweep_2026-11-24.py`
is the first data set, `7510m_s11_sweep_2026-11-24.s2p`, 301 points from 1 to
30 MHz.

- **There is no `wspr_analysis` conda env on this machine**, whatever
  `environment.yaml` says. Nothing in the root env has matplotlib either. The
  sweep scripts were run with
  `/home/natale/.conda/envs/terminal_map/bin/python`, which has matplotlib
  3.11.2 and scipy. **`terminal_map` has no seaborn, pandas or folium, so the
  spot notebooks will not run in it.** Those need
  `/home/natale/.conda/envs/repeater_monitoring/bin/python`, which is the only
  env on this machine with seaborn, pandas, folium, scipy and matplotlib
  together.
- **Interpolate before reading a narrow band.** The sweep steps 96.7 kHz and
  30 m is 50 kHz wide, so no sweep point lands inside it and a nearest-point
  lookup reports the band as absent. `interpolate_swr` exists for that, and
  `band_summary` distinguishes "narrower than the sweep step" from "outside
  the sweep" rather than returning nothing for both.
- **The fundamental is the deepest low-frequency match, not the lowest
  minimum.** `find_fundamental` picks by depth below 5 MHz. Taking the lowest
  minimum caught a shallow 1.19 MHz dip and made every harmonic an 18% miss
  against a frequency the antenna does not resonate on.
- **`resonance_bandwidths` is the diagnostic worth running.** Loaded Q per
  harmonic, from one sweep, cancels height, ground and feedline because every
  row shares them. On 2026-11-24 it gave Q=2 at the fundamental against 24 to
  59 for n=2 through 8, which is a loss signature and not a tuning result.
- **Fifteen reactance crossings against eight SWR minima is normal**, not a
  feedline artifact. An end-fed wire alternates series resonances (X rises
  through zero) with parallel ones (X falls), and 2026-11-24 gives a clean
  S-A-S-A-... of 8 and 7. Harmonics spaced 3.590 MHz is a 279 ns round trip,
  which is 132 ft of wire and nothing else. A phase-slope fit over the whole
  sweep returns ~134 ns, *below* the wire's own round trip, so it is not
  measuring a feedline; do not read a line length out of it.
- **SWR survives any feedline; R and X do not.** SWR depends only on the
  magnitude of the reflection coefficient, so dip frequencies and the Q
  figures hold at any measurement plane. A line rotates the impedance a full
  turn per half wavelength, so the sign of X is only the antenna's if the
  analyzer was at the antenna. Worth settling before R and X drive a tuning
  decision.
- **An SWR minimum is not a resonance** (X crossing zero), but on a deep dip
  the distinction has no room to mean anything: the impedance is confined to
  a circle of radius `50*2|G|/(1-|G|^2)`, so at SWR 1.09 nothing in the dip
  can exceed 4.3 ohms reactive. 3.610, 10.763 and 21.397 MHz show no
  crossing, each sitting at that bound. **That is not a loss signature and
  does not corroborate the capacitor diagnosis** -- loaded Q does, and it
  does so independently, since coax loss rises with frequency and would
  broaden the high bands rather than the fundamental. `reactance_zeros`,
  `minima_vs_zeros` and `plot_swr_and_reactance` are the functions.
- **160 m and 60 m are deliberately absent** from `WSPR_DIAL_MHZ` and from the
  figures. Not design bands of this antenna and not operated.

The write-up is `_articles/7510-efhw-checkin-2026-11.md` in `hamradio-source`,
unpublished pending the operator acting on its tuning plan.

## Findings worth knowing

**Revised 2026-10-19 against a three-day capture on the same antenna**
(`7510m_cyberdeck_2026-10_spots.tsv`, 18,315 spots, `run_7510m_cyberdeck_2026-10.py`).
The June figures below were drawn from a 3h16m afternoon capture and three of
the five did not survive.

- **20 m produces the most reports; it does not reach the furthest.** It leads
  on spot count because it is open to the most people for the most hours. 15 m
  and 10 m average longer paths. The old "strongest DX band by spot count and
  average distance" was a statement about one afternoon.
- **Receive-side asymmetry is +11.0 dB over the 66 pairs where both ends ran
  5 W**, CI [+8.6, +13.3], from 19 distinct stations, no normalizing involved.
  Concentrated on 40 m (+17.8) and 20 m (+10.5), absent on 30 m. The
  band-selective shape points at a local noise source, not the antenna.
  Probably an underestimate: the transmissions we manage to decode are the
  better moments of each path.
- **The old +6.3 dB figure was mostly transmit power**, not asymmetry. That
  capture ran 10 W against a 5 W remote median; normalized it is −0.9 dB with
  a CI spanning zero. **Prefer `matched_pairs()['same_power']` over both the raw delta and
  `SNR_delta_norm`.** Normalizing is a repair, not a cure: a low-power station
  is only decoded when the path is good, so its SNRs are censored and scaling
  them up flatters it, and one station claiming 1000 W (HK4CZE) dragged the
  normalized mean by ~3 dB. **Most captures cannot measure this at all** --
  June has 1 equal-power pair, the three field captures have 0, 0 and 3 -- and
  the honest answer there is "not measurable", not a normalized figure with a
  wide interval. The original error ran through all three field-antenna
  articles; all are corrected in place.
- **Normalized efficiency peaks on 15/17/20 m**, which holds. The apparent
  10 m and 12 m lead is a selection effect: those bands only open for DX, so
  their only paths are long ones. Note `k/W` doubles when power halves, so it
  is comparable only within a capture.
- **SSB at 100 W is best on 80 m** (62.8% of paths, 40 W median). 20 m now
  needs the same median power as 40 m, 126 W either way. The old "higher bands
  need far more power" came from a DX-only sample on those bands.
- **Unchanged across all three captures:** SNR vs distance, −7.2 dB/decade in
  June and −7.0 in October, r = −0.35 and −0.34. That is what a real
  relationship looks like measured repeatedly, and it calibrates how much to
  trust the rest. **It is a TX-side fit of SNR against log10(k)** — that is
  how −7.0 and −7.2 were produced, and pooling both directions gives −5.8
  instead, so reproduce it on `df[df['TX'] == CALLSIGN]` before comparing.

**Added 2026-11-24, from the daylight band-hopping capture.** The same day as
the first sweep, before any adjustment, so it is the before half of the
tuning comparison and not a test of the capacitor diagnosis.

- **Normalize by transmit slot.** The deck hops, and the rotation gave each
  band three to seven two-minute slots, so total spot counts rank time on air
  as much as propagation. On totals 30 m beats 20 m; per slot 20 m beats
  30 m. The per-slot figure still carries time of day.
- **Match the hours before comparing slopes.** This capture gives −6.34
  dB/decade, CI [−7.09, −5.59]. Against the published −7.0 that reads as a
  change and is not one: −7.0 is a three-day average including the steeper
  overnight paths, and October restricted to 13:16−22:00 UTC gives −6.14, CI
  [−6.55, −5.72], which brackets it.
- **AA1QR is filtered out of the November capture** as a receiver-side
  artifact, in the runner with a comment. All three of its spots are
  cross-band impossibilities, reporting 80 m or 30 m in minutes when 133 to
  193 other stations reported the deck on 40 m. Left in it invents three
  one-spot slots and drops 80 m per slot from 72.5 to 54.6. Worth checking
  for in any future capture: group by minute and look for a band with one
  spot beside a band with hundreds.
- **`analysis1_band_openings.png` misleads for a hopping capture.** It draws
  one line per band across the whole window, so the stretches where a band
  was simply not transmitting read as closures.
- **80 m works, and that does not refute the Q=2 loss finding.** The 21:56
  UTC slot reached 110 distinct receivers at 5 W, mean 2,143 km, out to
  7,042 km. WSPR decodes ~30 dB below the noise, so a band can be several dB
  down and still fill a map. Only a post-adjustment sweep settles the
  capacitor question.

## How I work — standing preferences

These are the same in every repository of mine. They are restated in each one
so that any assistant reads them, not only the one configured on my machine.

**Git is mine.** Never run `git commit` or `git push`, in any repository, for
any reason. Reading history is encouraged — `log`, `diff`, `status`, `show` —
and so is telling me when a good commit point has been reached, or drafting a
commit message for me to use. Finish the work, leave it uncommitted, and say
what changed and where.

**Hardware is mine.** Do not build SD-card images, `rsync` to a device, open an
`ssh` session to one, or run anything on a Raspberry Pi or the cyberdeck unless
I ask in that message. Hand me the exact commands to copy and paste — one block
per step, in order — say what each should print, and stop. I will run them and
paste the output back. Local work in the repository needs no such restraint.

**Writing.** No British spellings; US throughout. Design documents are
declarative: no hero's-journey narrative, no second-person "you", and never
state something as fact and then refute it a few lines later. For an article
already published, ask whether I want a dated update section or an in-place
rewrite. A dated update is the better default, because the wrong turns are part
of why a piece is worth reading, but it is my call rather than a rule. Do not repeat
a warning I have already acknowledged.

**Images.** Look at any photograph or screenshot before adding it to an
article, a slide deck, or a repository. Phone numbers show up in radio screens
and log captures, coordinates show up in beacon lines and station pages, and
backgrounds show rooms. Say what you found and redact it rather than guess.

**Destructive commands.** `/dev/sdX` stays a placeholder in any flashing or
disk-writing instructions. Never substitute a real device node.

**Amateur radio.** Test traffic uses my own callsign and its SSIDs — never
another operator's call, unless I explicitly ask for one.

**Working style.** I start fresh sessions often rather than carrying one for
weeks, so assume no memory of previous conversations. Everything you need
should be in this file or in the documents it points at.

**Keeping this file true is part of the work.** Anything dated here records
what was true on that date, not what is true now — check it against the
repository before relying on it, and correct it when it is wrong. When a
session has changed how the project works, turned up a gotcha worth the next
session not rediscovering, or outdated something in a "where it stands"
section, propose the edit to this file before the session ends. Do not wait to
be asked, and do not save it for a tidy-up later: the next session starts cold,
and this file is most of what it gets.
