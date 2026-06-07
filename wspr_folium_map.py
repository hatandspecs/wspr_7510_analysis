import pandas as pd
import folium
from folium import FeatureGroup, LayerControl
from folium.plugins import Fullscreen

from math import radians, cos, sin, asin, sqrt, atan2, degrees
from geopy.distance import geodesic
BAND_COLORS = {
    '80m': 'blue',
    '40m': 'green',
    '30m': 'purple',
    '20m': 'red',
    '17m': 'orange',
    '15m': 'darkred',
    '12m': 'cadetblue',
    '10m': 'darkgreen',
    'Other': 'gray',
}


def maidenhead_to_latlon(locator: str):
    """Convert a Maidenhead grid locator to latitude and longitude.

    Only 4- and 6-character locators are supported. The returned coordinate is
    the approximate center of the grid square.
    """
    if not isinstance(locator, str) or len(locator) < 4:
        return None
    locator = locator.strip().upper()
    if len(locator) not in (4, 6):
        locator = locator[:6] if len(locator) > 6 else locator.ljust(6, 'A')

    lon = (ord(locator[0]) - ord('A')) * 20 - 180
    lat = (ord(locator[1]) - ord('A')) * 10 - 90
    lon += int(locator[2]) * 2
    lat += int(locator[3]) * 1
    if len(locator) >= 6:
        lon += (ord(locator[4]) - ord('A')) * 5.0 / 60.0
        lat += (ord(locator[5]) - ord('A')) * 2.5 / 60.0
    lon += 1.0
    lat += 0.5
    return lat, lon


def interpolate_great_circle(lat1, lon1, lat2, lon2, num_points=30):
    """Interpolate points along a great circle arc between two points.
    
    This creates a curved path that appears as a true geodesic on Mercator projection.
    """
    # Calculate total distance
    total_distance = geodesic((lat1, lon1), (lat2, lon2)).km
    
    # Calculate initial bearing
    lat1_rad = radians(lat1)
    lat2_rad = radians(lat2)
    dlon = radians(lon2 - lon1)
    
    bearing = atan2(sin(dlon) * cos(lat2_rad),
                   cos(lat1_rad) * sin(lat2_rad) - 
                   sin(lat1_rad) * cos(lat2_rad) * cos(dlon))
    bearing = degrees(bearing)
    
    points = [(lat1, lon1)]
    for i in range(1, num_points - 1):
        distance_fraction = (i / (num_points - 1)) * total_distance
        intermediate_point = geodesic(kilometers=distance_fraction).destination(
            (lat1, lon1), bearing
        )
        # Convert Point object to tuple
        points.append((intermediate_point.latitude, intermediate_point.longitude))
    
    points.append((lat2, lon2))
    return points


def create_spot_map(df, bands=None, roles=None, html_path='analysis_images/analysis9_spots_map.html', zoom_start=3):
    """Create an interactive folium map of WSPR spots and save it as HTML.

    Parameters:
        df: pandas DataFrame containing columns TX, RX, txGrid, rxGrid, Band, SNR, k.
        bands: list of band labels to include, e.g. ['20m','40m']. If None, all bands are included.
        roles: list of role filters, subset of ['heard', 'heard_by'].
            'heard' = rows where KD3CCO is RX.
            'heard_by' = rows where KD3CCO is TX.
        html_path: path to write the generated HTML map.
        zoom_start: initial zoom level for the map.

    Returns:
        folium.Map object.
    """
    if bands is None:
        bands = sorted(df['Band'].dropna().unique())
    if roles is None:
        roles = ['heard', 'heard_by']
    bands = [b for b in bands if b in BAND_COLORS]
    if not bands:
        raise ValueError('No valid bands provided.')

    rows = []
    if 'heard' in roles:
        heard = df[(df['RX'] == 'KD3CCO') & df['Band'].isin(bands)].copy()
        heard['role'] = 'KD3CCO heard'
        rows.append(heard)
    if 'heard_by' in roles:
        heard_by = df[(df['TX'] == 'KD3CCO') & df['Band'].isin(bands)].copy()
        heard_by['role'] = 'KD3CCO heard by'
        rows.append(heard_by)
    if not rows:
        raise ValueError('No rows found for selected role filters.')

    plot_df = pd.concat(rows, ignore_index=True)
    plot_df = plot_df.dropna(subset=['txGrid', 'rxGrid', 'Band'])
    plot_df['tx_ll'] = plot_df['txGrid'].apply(maidenhead_to_latlon)
    plot_df['rx_ll'] = plot_df['rxGrid'].apply(maidenhead_to_latlon)
    plot_df = plot_df.dropna(subset=['tx_ll', 'rx_ll'])
    plot_df = plot_df[plot_df['Band'].isin(bands)]

    if plot_df.empty:
        raise ValueError('No valid spot paths exist for the selected bands and roles.')

    latitudes = [ll[0] for ll in plot_df['tx_ll'].tolist() + plot_df['rx_ll'].tolist()]
    longitudes = [ll[1] for ll in plot_df['tx_ll'].tolist() + plot_df['rx_ll'].tolist()]
    center = [sum(latitudes) / len(latitudes), sum(longitudes) / len(longitudes)]

    # Create map with Mercator projection
    spot_map = folium.Map(
        location=center, 
        zoom_start=zoom_start, 
        tiles='OpenStreetMap',
        prefer_canvas=False
    )
    Fullscreen().add_to(spot_map)

    # Create feature groups for each band and role combination
    for band in bands:
        for role in ['KD3CCO heard', 'KD3CCO heard by']:
            if ((role == 'KD3CCO heard' and 'heard' not in roles) or
                    (role == 'KD3CCO heard by' and 'heard_by' not in roles)):
                continue
            
            role_key = 'heard' if role == 'KD3CCO heard' else 'heard_by'
            group_name = f'{band} {role_key}'
            group = FeatureGroup(name=group_name, show=True)
            subset = plot_df[(plot_df['Band'] == band) & (plot_df['role'] == role)]
            
            for _, row in subset.iterrows():
                tx_lat, tx_lon = row['tx_ll']
                rx_lat, rx_lon = row['rx_ll']
                color = BAND_COLORS.get(band, 'gray')
                popup_html = (
                    f'<strong>{band}</strong><br>'
                    f'{role}<br>'
                    f'TX: {row["TX"]} ({row["txGrid"]})<br>'
                    f'RX: {row["RX"]} ({row["rxGrid"]})<br>'
                    f'SNR: {row.get("SNR", "n/a")} dB<br>'
                    f'k: {row.get("k", "n/a")}'
                )
                
                # Create polyline with interpolated great circle path
                gc_path = interpolate_great_circle(tx_lat, tx_lon, rx_lat, rx_lon, num_points=30)
                folium.PolyLine(
                    locations=gc_path,
                    color=color,
                    weight=0.8,
                    opacity=0.7,
                    popup=popup_html,
                    tooltip=popup_html,
                ).add_to(group)
            
            if not subset.empty:
                spot_map.add_child(group)

    # Add native folium layer control with legend
    LayerControl(collapsed=False, position='topright').add_to(spot_map)
    
    spot_map.save(html_path)
    return spot_map
