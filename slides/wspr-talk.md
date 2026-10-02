---
marp: true
paginate: true
footer: "KD3CCO · github.com/hatandspecs/wspr_7510_analysis"
style: |
  /* Plain white, one clear typeface, nothing decorative.
     Assertion-evidence: the headline is a full sentence making a claim and the
     body is the evidence for it. Carried inside this file rather than in a
     separate theme so the deck renders identically in the VS Code preview, in
     `marp` on the command line, and in an exported PDF, with nothing to
     register or configure first. */
  section {
    background: #ffffff;
    color: #111111;
    font-family: "Liberation Sans", Helvetica, Arial, sans-serif;
    font-size: 23px;
    line-height: 1.45;
    padding: 44px 56px 56px;
    /* The built-in theme wins on specificity for these, and its selectors are
       not ones a style block can match, so they are forced. The h1 color is a
       variable the theme exposes; the rest are not. */
    display: flex !important;
    flex-direction: column !important;
    justify-content: flex-start !important;
    --h1-color: #111111;
  }
  /* The assertion. A whole sentence, left aligned, never a category label. */
  section h1 { font-size: 32px; font-weight: 600; line-height: 1.25; margin: 0 0 20px 0; color: #111111 !important; }
  section h2 { font-size: 25px; font-weight: 600; margin: 0 0 12px 0; }
  section p { margin: 0 0 12px 0; }
  section ul { margin: 0 0 12px 0; padding-left: 26px; }
  section li { margin: 0 0 8px 0; }
  section strong { font-weight: 600; }
  section blockquote { margin: 0 0 16px 0; padding: 0 0 0 18px; border-left: 3px solid #cccccc; color: #222222; }
  section a { color: #0b4fa8; text-decoration: none; }
  section code { font-family: "Liberation Mono", Consolas, monospace; font-size: 0.86em; background: #f3f3f3; padding: 1px 5px; }
  section pre { background: #f6f6f6; border-left: 3px solid #cccccc; padding: 12px 16px; font-size: 17px; line-height: 1.45; margin: 0 0 14px 0; }
  section pre code { background: none; padding: 0; font-size: 17px; }
  /* Whatever the source image is, it fits the space that is left. */
  section img { display: block; margin: 0 auto; max-width: 100%; max-height: 430px; width: auto; height: auto; }
  section.evidence h1 { margin-bottom: 14px; }
  section.evidence img { max-height: 440px; }
  /* A slide whose evidence is a tall photograph: the picture is a panel down
     one side, so it is never scaled to a stamp to make it fit. */
  section.panel h1 { margin-bottom: 18px; }
  section.title, section.closing { justify-content: center !important; }
  section.title h1 { font-size: 42px; margin-bottom: 16px; }
  section.title p, section.closing p { font-size: 25px; color: #444444; }
  section .caption { display: block; font-size: 18px; color: #555555; margin-top: 10px; }
  section footer { font-size: 14px; color: #888888; }
  section::after { font-size: 14px; color: #888888; }
---

<!-- _class: title -->
<!-- _paginate: false -->
<!-- _footer: "" -->

# Asking a wire what it actually does

**KD3CCO**

One evening of WSPR, ten analyses, and several things I had wrong

---

# I built a 75–10 m end-fed half-wave and had no honest way to judge it

The SWR meter says the transmitter is comfortable. It says nothing about where the signal goes, which bands the thing is really good on, or whether the problem is me.

On the air it is worse: you work someone, or you do not, and you never find out which part was responsible.

I wanted a measurement, not an impression.

---

<!-- _class: evidence -->

# One evening of WSPR answered it — 5,000 receptions, on two continents

![](../analysis_images/analysis10_spots_map_screenshot.png)

<span class="caption">Every line is one reception of my signal by a real receiver, or of theirs by mine, 2026-06-06, 18:20–21:36 UTC.</span>

---

# Every WSPR spot is a calibrated measurement that somebody else paid for

A WSPR transmission is two minutes of a few watts carrying nothing but a callsign, a grid square, and a power level.

Hundreds of volunteer receivers decode it and upload what they heard, **with the signal-to-noise ratio attached**.

You do not need their equipment, their time, or their permission. You need a TSV file and an evening.

---

<!-- _class: evidence -->

# The band worth being on changed three times in three hours

![](img/band-openings-counts.png)

<span class="caption">Spot count per band per 15 minutes. 30 m peaks at 19:00, 17 m at 20:30, 20 m runs away with it after 20:15.</span>

---

<!-- _class: evidence -->

# It is a midband antenna, whatever the name on the label says

![](../analysis_images/analysis7_efficiency_normalization.png)

<span class="caption">Distance per watt, per band. 20 m 383 km/W, 17 m 354, 15 m 354 — against 75 km/W on 40 m and 39 on 80 m.</span>

---

<!-- _class: evidence -->

# The surprise was that my receiver, not my antenna, is the weak end

![](../analysis_images/analysis5_tx_rx_asymmetry.png)

<span class="caption">38 matched pairs where the same station and I heard each other within 20 minutes. Mean delta +6.3 dB in favor of transmit — that is local noise, in my house and my neighborhood.</span>

---

<!-- _class: evidence -->

# On 10 and 12 m, almost nothing closer than 900 km could hear me at all

![](../analysis_images/analysis8_takeoff_angle.png)

<span class="caption">10th percentile distance by band. A far inner skip boundary means a high takeoff angle — the harmonic modes of an EFHW are not a pattern anyone designed.</span>

---

<!-- _class: evidence -->

# Spots become a decision: where a voice contact would actually have worked

![](img/ssb-feasibility-40m-20m.png)

<span class="caption">WSPR SNR is referenced to roughly an SSB bandwidth, so it scales with power. 40 m: 55% of paths clear a 3 dB margin within 100 W. 20 m: 818 workable paths, but only 38% of its spots.</span>

---

# The whole thing runs from one configuration cell

```python
TSV_FILENAME      = '7510m_wspr_spots.tsv'   # a file from wspr.rocks
CALLSIGN          = 'KD3CCO'
START_UTC         = None                     # or '2026-06-06T18:00:00'
END_UTC           = None
DOWNLOAD_FROM_API = False
```

Point it at your own callsign and your own capture and every figure in this talk rebuilds itself.

I have since run the same notebook against a 20 m dipole, a 15 m dipole, and a center-loaded 40 m dipole on a mast — which is the actual point. **Comparisons between antennas are worth more than a number for any one of them.**

---

<!-- _class: evidence -->

# An AI coding assistant reads your whole repository, and that changes which projects are worth starting

![width:880px](img/agent-loop.svg)

Hobby time arrives as confetti: twenty minutes before dinner, an hour on a Sunday. What decides whether a project happens is not the work in it — it is how much progress fits inside one of those fragments. Ten separate analyses of one evening's spots was never going to happen otherwise.

---

<!-- _class: evidence -->

# The gain is not just faster and better code — it is the practices the AI made affordable

![width:1000px](img/doc-first-cycle.svg)

<span class="caption">Interfaces, failure modes and what happens when a part is missing, all decided in the document before anything exists. Here it produced test files for the great-circle geometry, because a plausible-looking map is the easiest thing in the world to get wrong.</span>

---

# Its best trick is telling me what I did not know to ask

**Argue with it for an hour at two in the morning** without spending a friend's patience. In a solo hobby, that back-and-forth was the scarce ingredient.

**Then turn it against your own design.** I write down how I think something should work, and ask for an analysis of alternatives — and specifically: *does this design imply there are tools, techniques or facts out there that I am not accounting for?*

It is a retrieval system over what other people have already worked out. Use it as one.

---

<!-- _class: evidence -->

# Code, documentation, slides and the blog in one window, where the assistant can see all of it

![width:810px](img/vscode-workspace.png)

<span class="caption">Documentation is markdown in the repository, beside the code. Everything advances in the same sitting, so nothing drifts. The blog is another repository in the same workspace; these slides are markdown in this one.</span>

---

# This is the cheapest experiment in amateur radio

No new hardware. A few watts, an evening, and a receiver network that already exists.

**Transmit WSPR tonight on whatever you already have up.** Download the spots tomorrow. You will learn more about your antenna in one evening than in a year of "how's my signal."

Then change one thing — height, feedpoint, a different wire — and do it again.

---

<!-- _class: closing -->

# Measure the antenna you have before you buy the next one

**Notebook, dataset, and all ten analyses**
github.com/hatandspecs/wspr_7510_analysis

**Write-up, with every figure and what it means**
hatandspecs.github.io/hamradio/articles/7510-wspr-results-analysis/

Also run against a 20 m dipole, a 15 m dipole, and a loaded 40 m dipole — same notebook, four antennas.

**KD3CCO** — questions welcome
