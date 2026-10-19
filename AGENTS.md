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
- **There are four datasets and four notebooks** — the 75-10 m EFHW, plus 15 m
  and 20 m field-day dipoles and a center-loaded 40 m dipole. Comparisons
  between antennas are the point; a number for one antenna alone is weak.
- **Do not claim a change from a small sample.** Two spots out of nine is
  consistent with almost any true rate. This project has already produced one
  retraction from exactly that mistake; check whether a difference survives
  before writing it down.
- **Geometry has its own tests** (`test_geodesic_geometry.py`,
  `test_api_comparison.py`) because a plausible-looking great-circle map is the
  easiest thing in the world to get wrong.

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
- **Unchanged across both captures:** SNR vs distance, −7.2 dB/decade in June
  and −7.0 in October, r = −0.35 and −0.34. That is what a real relationship
  looks like measured twice, and it calibrates how much to trust the rest.

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
already published, add a dated update section rather than rewriting the
narrative — the wrong turns are part of why it is worth reading. Do not repeat
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
