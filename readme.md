# 75-10m EFHW WSPR Dataset Analysis

This repository contains a Jupyter notebook that analyzes a 4-hour WSPR spot capture from a 75-10m End-Fed Half-Wave (EFHW) station. The dataset is stored in `7510m_wspr_spots.tsv` and includes the fields:

`Time`, `TX`, `txGrid`, `RX`, `rxGrid`, `MHz`, `Watts`, `SNR`, `drift`, `k`, `az`, `mode`, `k/W`, `spotQ`, `version`

The notebook is designed to support both propagation analysis and antenna diagnostics with clearly labeled sections, visual outputs, and dataset-driven conclusions.

---

## 1. What this analysis reveals

### Phase I: Propagation and band behavior

1. **Band openings and closures**
   * Tracks how often each amateur band produces spots over time.
   * Uses time binning to reveal when 80m, 40m, 30m, 20m, 17m, 15m, 12m, and 10m were active.
   * Useful for identifying the daily propagation window and when the MUF was high enough to support a given band.

2. **Distance profiling by band**
   * Computes mean, maximum, and spread of skip distance `k` for each band.
   * Shows the effective reach for each band during the dataset interval.
   * Useful for quantifying whether the station is currently in a domestic, regional, or DX-friendly state.

3. **Geographical footprint mapping**
   * Extracts the 4-character Maidenhead grid prefix from received spots.
   * Counts the most active grid squares to show which parts of the world are actually being heard.
   * Useful for quickly identifying directional bias or coverage gaps.

4. **SNR versus distance relationship**
   * Plots path distance against received signal-to-noise ratio for each band.
   * Helps identify whether attenuation follows expected path-loss trends or if certain bands deviate.
   * Useful for detecting unusual propagation or anomalies in the station's system.

### Phase II: Antenna and local station diagnostics

5. **TX/RX path asymmetry**
   * Compares reciprocal legs for the local station `KD3CCO`.
   * Matches the same remote station on the same band within a ±20 minute window.
   * Useful for identifying whether the local receive or transmit side is disproportionately strong or weak.

6. **Azimuthal polar pattern**
   * Uses transmit azimuth (`az`) and path distance (`k`) to map the station's directional performance.
   * Helps visualize main lobes and deep nulls.
   * Useful for diagnosing antenna directionality and comparing physical orientation to actual propagation.

7. **Normalized band efficiency (`k/W`)**
   * Focuses on remote stations heard across three or more bands.
   * Normalizes distance by transmit power to compare band performance more fairly.
   * Useful for finding which high-frequency bands remain efficient and which are suffering from mismatch or loss.

8. **Takeoff angle inference via inner skip boundary**
   * Computes low percentile distances (10th, 25th, 50th) for higher bands.
   * The near-skip-zone distance acts as an empirical proxy for takeoff angle.
   * Useful for determining whether the antenna is radiating too high or too low for DX versus local coverage.

---

## 2. Notebook structure and implementation

The working notebook is `wspr_7510_analysis.ipynb`.

It uses:

* `pandas` for dataset loading and grouping
* `numpy` for numeric conversion and angle math
* `matplotlib` and `seaborn` for plotting

The notebook follows this workflow:

1. Load `7510m_wspr_spots.tsv` with `pd.read_csv(..., sep='\t', parse_dates=['Time'])`.
2. Map `MHz` to amateur band labels.
3. Build derived fields such as `Band`, `TimeBin`, `rxPrefix`, and `az_rad`.
4. Perform the Phase I propagation analyses.
5. Perform the Phase II diagnostic analyses.
6. Save representative visual outputs to `analysis_images/`.

### Band mapping logic

The notebook defines band labels by frequency ranges:

* `80m` = 3.5–4.0 MHz
* `40m` = 7.0–7.3 MHz
* `30m` = 10.1–10.15 MHz
* `20m` = 14.0–14.35 MHz
* `17m` = 18.068–18.168 MHz
* `15m` = 21.0–21.45 MHz
* `12m` = 24.89–24.99 MHz
* `10m` = 28.0–29.7 MHz

### Representative pseudocode snippets

#### Load and preprocess

```python
import pandas as pd
import numpy as np

df = pd.read_csv('7510m_wspr_spots.tsv', sep='\t', parse_dates=['Time'])
```

#### TX/RX path asymmetry

```python
tx = df[df['TX'] == 'KD3CCO']
rx = df[df['RX'] == 'KD3CCO']
merged = pd.merge(rx, tx, on=['Remote', 'Band'])
merged['SNR_delta'] = merged['SNR_tx'] - merged['SNR_rx']
```

#### Azimuthal polar mapping

```python
theta = np.radians(tx_local['az'])
radius = tx_local['k']
ax.scatter(theta, radius, c=tx_local['SNR'])
```

---

## 3. Actual dataset findings

For this dataset, the notebook produced the following representative values:

* 20m has the highest mean distance at about **4247 km**.
* 80m shows a much shorter average distance around **444 km**.
* The 10th percentile of higher band skip distances is:
  * `20m` ≈ **706 km**
  * `17m` ≈ **536 km**
  * `15m` ≈ **536 km**
  * `12m` ≈ **1039 km**
  * `10m` ≈ **909 km**
* Some reciprocal TX/RX pairs show large asymmetries, with `SNR_tx - SNR_rx` values above **+20 dB** for matched station/band pairs.

### What this means

* The station is clearly operating in a DX-friendly window on 20m and 15m during the capture.
* The large positive TX/RX bias in several pairs suggests the receive side may be noisier or less sensitive than the transmit path.
* The inner skip boundary for 10m and 12m supports a relatively high takeoff angle, which is consistent with longer local skip distances.

---

## 4. Output files and visuals

Generated example figures are available in `analysis_images/`:

* `analysis1_band_openings.png`
* `analysis2_distance_profiling.png`
* `analysis3_geographical_spread.png`
* `analysis4_snr_distance.png`
* `analysis5_tx_rx_asymmetry.png`
* `analysis6_azimuthal_pattern.png`
* `analysis7_efficiency_normalization.png`
* `analysis8_takeoff_angle.png`

These plots respectively document:

* band activity and mean SNR over time
* skip-distance statistics by band
* most active receive grid prefixes
* SNR decay across path distance
* local TX/RX reciprocity asymmetry
* compass-based antenna lobes
* normalized band efficiency in `k/W`
* higher-band skip boundary behavior

---

## 5. Running the notebook

Open `wspr_7510_analysis.ipynb` in Jupyter and execute all cells.

Dependencies:

* `pandas`
* `numpy`
* `matplotlib`
* `seaborn`

The notebook is self-contained and regenerates the `analysis_images/` outputs when run from the repository root.
