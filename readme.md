# 75-10m EFHW WSPR Dataset Analysis

This framework processes a standard 15-column WSPR dataset (`Time`, `TX`, `txGrid`, `RX`, `rxGrid`, `MHz`, `Watts`, `SNR`, `drift`, `k`, `az`, `mode`, `k/W`, `spotQ`, `version`) to evaluate both real-time environmental propagation conditions and physical antenna performance characteristics.

---

## 1. High-Level Overview

### Phase I: Standard Propagation Metrics (Atmospheric Characterization)

* **Analysis 1: Band Openings and Closures (Temporal MUF Shift)**
* *Usefulness:* Maps out the precise times when specific bands open or close. By tracking spot counts and SNR over the 4-hour window, you can visually observe the Maximum Usable Frequency (MUF) rising or falling, letting you optimize your operating schedule.


* **Analysis 2: Distance Profiling (Path Maxima)**
* *Usefulness:* Quantifies the boundary limits of your current reach across all eight bands by calculating mean and maximum skip distances ($k$). This sets an empirical baseline for what conditions are permitting.


* **Analysis 3: Geographical Spread (Footprint Mapping)**
* *Usefulness:* Groups unique spots by Maidenhead grid locators (`txGrid`/`rxGrid`). This visualizes the overall geographic distribution of your signals, revealing whether your footprint is primarily domestic, trans-oceanic, or regional.


* **Analysis 4: SNR vs. Distance Regression**
* *Usefulness:* Establishes a standard baseline curve of path loss versus signal degradation for each frequency. Deviations from this baseline are what allow you to detect unique antenna behaviors or abnormal propagation.



### Phase II: Antenna Setup Diagnostics (Hardware Performance)

* **Analysis 5: TX vs. RX Asymmetry (The Local Noise Floor Test)**
* *Usefulness:* Compares reciprocal signal paths with identical stations within narrow time windows. If your outgoing signals consistently show higher SNR than incoming signals, your local ambient RF noise floor is masking weak signals. If the reverse is true, you may be experiencing transmission path inefficiencies (e.g., core saturation or high feedline losses).


* **Analysis 6: Azimuthal Pattern Mapping (Lobe & Null Identification)**
* *Usefulness:* Plots spot density and signal strength relative to the exact compass bearing (`az`). This maps the actual physical radiation lobes and deep nulls of your antenna system, highlighting structural or directional blind spots.


* **Analysis 7: Band-by-Band Efficiency Normalization (Harmonic Matching)**
* *Usefulness:* Filters data to stations that spotted you on multiple distinct bands, then normalizes the data to isolate your system's efficiency on higher harmonics. This shows whether your matching transformer or wire geometry maintains performance on the upper bands or drops off rapidly due to core loss or high SWR.


* **Analysis 8: Take-Off Angle Inference via Minimum Skip Boundaries**
* *Usefulness:* Examines the inner edge of your skip zone on the higher bands (20m–10m). A small minimum skip distance points to a high takeoff angle (indicative of an antenna mounted too low to the ground), whereas an open near-field indicates a low, DX-friendly takeoff angle.



---

## 2. Detailed Implementation, Pseudocode & Visualizations

### Recommended Python Libraries

* **Data Structures:** `pandas`, `numpy`
* **Graphics & Visualization:** `matplotlib`, `seaborn`

---

### Phase I: Standard Propagation Metrics

#### Analysis 1: Band Openings and Closures

* **Pseudocode Logic:**
1. Parse `Time` to datetime objects.
2. Group data into 15 or 30-minute bins using the `MHz` column categorized into discrete amateur bands.
3. Count total spots and calculate the mean `SNR` for each band per time bin.


* **Visualization:** Line chart with time on the X-axis, spot count/mean SNR on the Y-axis, and distinct lines or subplots representing each band.

#### Analysis 2: Distance Profiling

* **Pseudocode Logic:**
1. Map `MHz` frequencies to their corresponding band labels (`80m`, `40m`, etc.).
2. Group by band label and compute descriptive statistics (`max`, `mean`, `std`) on the distance column `k`.


* **Visualization:** Bar chart with error bars representing standard deviation, ordered by increasing frequency.

#### Analysis 3: Geographical Spread

* **Pseudocode Logic:**
1. Extract the 4-character Maidenhead locator prefix from `txGrid` or `rxGrid`.
2. Calculate unique counts or total traffic per grid square.


* **Visualization:** A horizontal bar chart or a matrix heatmap sorting the top 20 most active grid squares, indicating the core geographic directions interacting with your station.

#### Analysis 4: SNR vs. Distance Regression

* **Pseudocode Logic:**
1. Filter dataset by band.
2. Isolate the distance (`k`) and `SNR` columns.
3. Fit a trendline or scatter plot density profile.


* **Visualization:** Scatter plot with a overlaid trendline (using `sns.regplot`), using separate subplots for each band to observe the changing rate of path attenuation.

---

### Phase II: Antenna Setup Diagnostics

```python
# Master Initialization and Helper Definitions for Data Selection
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns

df = pd.read_csv("wspr_data.tsv", sep="\t", parse_dates=['Time'])

def get_band(mhz):
    if 3.5 <= mhz <= 4.0: return '80m'
    elif 7.0 <= mhz <= 7.3: return '40m'
    elif 10.1 <= mhz <= 10.15: return '30m'
    elif 14.0 <= mhz <= 14.35: return '20m'
    elif 18.068 <= mhz <= 18.168: return '17m'
    elif 21.0 <= mhz <= 21.45: return '15m'
    elif 24.89 <= mhz <= 24.99: return '12m'
    elif 28.0 <= mhz <= 29.7: return '10m'
    return 'Other'

df['Band'] = df['MHz'].apply(get_band)

```

#### Analysis 5: TX vs. RX Asymmetry

* **Pseudocode Logic:**
1. Split the dataset into two dataframes: `tx_df` (where `TX == 'KD3CCO'`) and `rx_df` (where `RX == 'KD3CCO'`).
2. Merge `tx_df` and `rx_df` on the remote station's call sign and the `Band`.
3. Filter for matching timestamps within a $\pm20$ minute window.
4. Calculate $\Delta \text{SNR} = \text{SNR}_{\text{TX}} - \text{SNR}_{\text{RX}}$.



```python
# Pseudocode Execution for Path Asymmetry
tx = df[df['TX'] == 'KD3CCO'].rename(columns={'RX': 'Remote', 'SNR': 'SNR_tx', 'Time': 'Time_tx'})
rx = df[df['RX'] == 'KD3CCO'].rename(columns={'TX': 'Remote', 'SNR': 'SNR_rx', 'Time': 'Time_rx'})

merged = pd.merge(tx, rx, on=['Remote', 'Band'])
merged['Time_Delta'] = (merged['Time_tx'] - merged['Time_rx']).abs().dt.total_seconds()
simultaneous = merged[merged['Time_Delta'] <= 1200].copy() # 20 minute window
simultaneous['SNR_Delta'] = simultaneous['SNR_tx'] - simultaneous['SNR_rx']

```

* **Visualization:** A histogram distribution of `SNR_Delta` centered around $0\text{ dB}$. Shifting significantly into positive territory quantifies a high local noise floor; shifting negative points to transmission losses.

#### Analysis 6: Azimuthal Pattern Mapping

* **Pseudocode Logic:**
1. Filter for transmissions: `TX == 'KD3CCO'`.
2. Select the operating band.
3. Convert the compass headings in `az` into radians.


* **Visualization:** Polar Scatter Plot where angle matches `az` (converted to radians), radius matches distance `k`, and point color scales with `SNR`.

```python
# Pseudocode Execution for Polar Radiation Mapping
tx_band = df[(df['TX'] == 'KD3CCO') & (df['Band'] == '20m')]
rads = np.radians(tx_band['az'])

fig, ax = plt.subplots(subplot_kw={'projection': 'polar'})
ax.set_theta_zero_location('N')
ax.set_theta_direction(-1) # Clockwise compass direction
sc = ax.scatter(rads, tx_band['k'], c=tx_band['SNR'], cmap='viridis')

```

#### Analysis 7: Band-by-Band Efficiency Normalization

* **Pseudocode Logic:**
1. Identify remote unique stations that have heard your transmissions across 3 or more bands.
2. For each of these multi-band reference stations, trace your distance-per-watt (`k/W`) or `SNR` trends to evaluate relative harmonic performance.



```python
# Pseudocode Execution for Multi-Band Performance Tracking
multi_band_spotters = tx.groupby('Remote')['Band'].nunique()
target_stations = multi_band_spotters[multi_band_spotters >= 3].index
efficiency_df = tx[tx['Remote'].isin(target_stations)]

```

* **Visualization:** Categorical Box Plots or Violin Plots of `k/W` grouped sequentially by band label along the X-axis. This highlights rapid drops in hardware efficiency on specific harmonically related bands.

#### Analysis 8: Take-Off Angle Inference via Minimum Skip Boundaries

* **Pseudocode Logic:**
1. Filter out ground-wave paths by extracting spots from ionospheric bands ($>14\text{ MHz}$).
2. For each high band, calculate the lowest 5th to 10th percentile of the distance array `k`. This defines your local skip zone radius.


* **Visualization:** Kernel Density Estimation (KDE) plot or ridgeline chart charting distance `k` for individual bands. A sharp rise further down the axis points to a low takeoff angle favoring long-distance ionospheric reflections over short skip paths.

---

### 3. Interactive WSPR Diagnostic Explorer
 TBD