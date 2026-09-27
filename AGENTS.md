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

20 m is the strongest DX band on this antenna. Receive-side asymmetry is clear —
mean TX/RX SNR delta +6.3 dB over 38 matched pairs, which points at local noise
rather than the antenna. Normalized efficiency peaks on 20/17/15 m. SSB is
realistically reachable on 40 m and 80 m at 100 W and not on the higher bands.

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
