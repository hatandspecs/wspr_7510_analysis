import pandas as pd
import geopandas as gpd
import matplotlib.pyplot as plt
import numpy as np
from shapely.geometry import Point, box, Polygon, MultiPolygon, LineString, MultiLineString
import warnings

# Suppress harmless warnings from geopandas datasets
warnings.filterwarnings('ignore')

# ==========================================
# 1. Coordinate & Projection Math
# ==========================================

def maidenhead_to_latlon(grid):
    """Converts a Maidenhead grid locator (4 or 6 chars) to Latitude and Longitude."""
    grid = str(grid).strip().upper()
    if len(grid) < 4: return None, None
    try:
        lon = (ord(grid[0]) - 65) * 20 - 180
        lat = (ord(grid[1]) - 65) * 10 - 90
        lon += int(grid[2]) * 2
        lat += int(grid[3]) * 1
        
        if len(grid) == 4:
            lon += 1
            lat += 0.5
        elif len(grid) >= 6:
            lon += (ord(grid[4]) - 65) * (5/60) + (2.5/60)
            lat += (ord(grid[5]) - 65) * (2.5/60) + (1.25/60)
        return lat, lon
    except:
        return None, None

def mercator_y(lat):
    """Projects latitude into Mercator Y coordinate."""
    lat = np.clip(lat, -85.0511, 85.0511)
    lat_rad = np.radians(lat)
    return np.degrees(np.log(np.tan(np.pi / 4 + lat_rad / 2)))

def shift_and_project(geom):
    """
    Splits geometries at 90°E.
    Longitudes > 90 are shifted by -360 so the map seamlessly centers around the Americas.
    Then, applies the Mercator projection to the Y axis.
    """
    box_west = box(-180, -90, 90, 90)
    box_east = box(90, -90, 180, 90)
    
    geom_west = geom.intersection(box_west)
    geom_east = geom.intersection(box_east)
    
    parts = []
    
    # Process West part (<= 90)
    if not geom_west.is_empty:
        g_list = geom_west.geoms if hasattr(geom_west, 'geoms') else [geom_west]
        for g in g_list:
            if g.geom_type == 'Polygon':
                ext = [(x, mercator_y(y)) for x, y in g.exterior.coords]
                ints = [[(x, mercator_y(y)) for x, y in i.coords] for i in g.interiors]
                parts.append(Polygon(ext, ints))
            elif g.geom_type == 'LineString':
                parts.append(LineString([(x, mercator_y(y)) for x, y in g.coords]))
                
    # Process East part (> 90), shifting X by -360
    if not geom_east.is_empty:
        g_list = geom_east.geoms if hasattr(geom_east, 'geoms') else [geom_east]
        for g in g_list:
            if g.geom_type == 'Polygon':
                ext = [(x - 360, mercator_y(y)) for x, y in g.exterior.coords]
                ints = [[(x - 360, mercator_y(y)) for x, y in i.coords] for i in g.interiors]
                parts.append(Polygon(ext, ints))
            elif g.geom_type == 'LineString':
                parts.append(LineString([(x - 360, mercator_y(y)) for x, y in g.coords]))
                
    if not parts: return None
    if len(parts) == 1: return parts[0]
    
    # Re-group by matching types to prevent GeometryCollections
    polys = [p for p in parts if p.geom_type == 'Polygon']
    lines = [p for p in parts if p.geom_type == 'LineString']
    if polys: return MultiPolygon(polys)
    if lines: return MultiLineString(lines)
    return None

def freq_to_band(mhz):
    """Categorizes Frequency into Ham Bands."""
    b = float(mhz)
    if 1.8 <= b <= 2.0: return "160m"
    if 3.5 <= b <= 4.0: return "80m"
    if 5.2 <= b <= 5.4: return "60m"
    if 7.0 <= b <= 7.3: return "40m"
    if 10.1 <= b <= 10.2: return "30m"
    if 14.0 <= b <= 14.35: return "20m"
    if 18.0 <= b <= 18.2: return "17m"
    if 21.0 <= b <= 21.45: return "15m"
    if 24.8 <= b <= 24.99: return "12m"
    if 28.0 <= b <= 29.7: return "10m"
    if 50.0 <= b <= 54.0: return "6m"
    return "Unknown"

# ==========================================
# 2. Data Processing
# ==========================================

# Load geographical features
# path = gpd.datasets.get_path('naturalearth_lowres')
# world = gpd.read_file(path)


# New code (reads directly from the Natural Earth AWS bucket)
url = "https://naturalearth.s3.amazonaws.com/110m_cultural/ne_110m_admin_0_countries.zip"
world = gpd.read_file(url)

world['geometry'] = world['geometry'].apply(shift_and_project)
world = world.dropna(subset=['geometry'])

# Read and parse WSPR data
try:
    df = pd.read_csv('spots.tsv', sep='\t')
except FileNotFoundError:
    print("Could not find 'spots.tsv'. Ensure it is in the same directory.")
    exit(1)

# Filter for the correct station and drop duplicates to prevent map clutter
df = df[df['RX'].str.upper() == 'KD3CCO']
df = df.drop_duplicates(subset=['TX', 'txGrid'])

# Calculate grid locators
df['Lat'], df['Lon'] = zip(*df['txGrid'].apply(maidenhead_to_latlon))
df = df.dropna(subset=['Lat', 'Lon'])

# Shift WSPR marker longitudes to match the 90E split (-270 to +90 span)
df['Shifted_Lon'] = df['Lon'].apply(lambda x: x - 360 if x > 90 else x)
df['Mercator_Y'] = df['Lat'].apply(mercator_y)

# Extract unique bands heard for the bottom display
df['Band'] = df['MHz'].apply(freq_to_band)
heard_bands = [b for b in ['160m', '80m', '60m', '40m', '30m', '20m', '17m', '15m', '12m', '10m', '6m'] if b in df['Band'].unique()]
band_text = " | ".join(heard_bands)

# Setup Receiver Coordinate
rx_lat, rx_lon = maidenhead_to_latlon('FN10cs')
rx_shifted_lon = rx_lon - 360 if rx_lon > 90 else rx_lon
rx_merc_y = mercator_y(rx_lat)

# ==========================================
# 3. Plot Generation (Exact 800x480)
# ==========================================

# 800x480 resolution at 100 DPI
fig, ax = plt.subplots(figsize=(8.0, 4.8), dpi=100, facecolor='#000000')
fig.subplots_adjust(left=0, right=1, bottom=0, top=1) # Remove all margins
ax.set_facecolor('#000000')

# Set map boundaries (-270 = 90E split, +90 = 90E split)
ax.set_xlim([-270, 90])
# ax.set_ylim([mercator_y(-60), mercator_y(80)]) # Clip poles cleanly
# ax.set_ylim([mercator_y(-85.0511), mercator_y(80)])

ax.set_ylim([mercator_y(-78), mercator_y(80)])

# Plot Dim Green Coastlines
world.plot(ax=ax, facecolor='none', edgecolor='#004100', linewidth=0.6, antialiased=False)

# Plot Bright Green TX markers (1 pixel crosshairs)
ax.scatter(df['Shifted_Lon'], df['Mercator_Y'], color='#00FF00', marker='+', s=15, linewidths=0.5)

# Plot Home Station distinctly (KD3CCO)
ax.scatter([rx_shifted_lon], [rx_merc_y], color='#00FF00', marker='s', s=25, facecolors='none', linewidths=0.8)

# Optional Typography Overlay
# ax.text(-265, mercator_y(74), "RX: KD3CCO\nGRID: FN10cs", color='#00FF00', family='monospace', fontsize=9, va='top')
# ax.text(-90, mercator_y(74), "WSPR WORLD SPOTS", color='#00FF00', family='monospace', fontsize=10, va='top', ha='center')
# ax.text(85, mercator_y(74), "TIBET SPLIT (~90°E)", color='#00FF00', family='monospace', fontsize=9, va='top', ha='right')

# Optional Typography Overlay (Pinned to screen coordinates)
ax.text(0.01, 0.98, "RX: KD3CCO\nGRID: FN10cs", color='#00FF00', family='monospace', fontsize=9, va='top', transform=ax.transAxes)
ax.text(0.50, 0.98, "WSPR WORLD SPOTS", color='#00FF00', family='monospace', fontsize=10, va='top', ha='center', transform=ax.transAxes)
ax.text(0.99, 0.98, "TIBET SPLIT (~90°E)", color='#00FF00', family='monospace', fontsize=9, va='top', ha='right', transform=ax.transAxes)

# Add bands to the bottom of the screen
# ax.text(-265, mercator_y(-58), f"BANDS HEARD: {band_text}", color='#00FF00', family='monospace', fontsize=9, va='bottom')
ax.text(0.01, 0.02, f"BANDS HEARD: {band_text}", color='#00FF00', family='monospace', 
        fontsize=9, va='bottom', transform=ax.transAxes)


# Disable axes
ax.axis('off')

# Save directly to PNG ensuring exact pixel map with no white borders
plt.savefig('wspr_mercator_phosphor_800x480.png', facecolor='#000000', edgecolor='none', pad_inches=0, transparent=False)
print("Saved: wspr_mercator_phosphor_800x480.png")