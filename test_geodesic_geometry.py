#!/usr/bin/env python3
"""Test script to diagnose and demonstrate great circle geometry on Mercator projection."""

import pandas as pd
import folium
from folium import FeatureGroup, LayerControl
from geopy.distance import geodesic
from math import radians, cos, sin, asin, sqrt, atan2, degrees

def vincenty_forward(lat, lon, bearing, distance_km):
    """Calculate endpoint given a starting point, bearing, and distance (Vincenty formula)."""
    R = 6371.0  # Earth radius in km
    
    lat_rad = radians(lat)
    lon_rad = radians(lon)
    bearing_rad = radians(bearing)
    angular_distance = distance_km / R
    
    lat2_rad = asin(sin(lat_rad) * cos(angular_distance) +
                    cos(lat_rad) * sin(angular_distance) * cos(bearing_rad))
    
    lon2_rad = lon_rad + atan2(sin(bearing_rad) * sin(angular_distance) * cos(lat_rad),
                              cos(angular_distance) - sin(lat_rad) * sin(lat2_rad))
    
    return degrees(lat2_rad), degrees(lon2_rad)

def interpolate_great_circle(lat1, lon1, lat2, lon2, num_points=20):
    """Interpolate points along a great circle arc between two points."""
    from geopy import distance as geo_distance
    
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

def main():
    # Load data
    df = pd.read_csv('7510m_wspr_spots.tsv', sep='\t', parse_dates=['Time'])
    
    def get_band(mhz):
        if 3.5 <= mhz <= 4.0:
            return '80m'
        elif 7.0 <= mhz <= 7.3:
            return '40m'
        elif 10.1 <= mhz <= 10.15:
            return '30m'
        elif 14.0 <= mhz <= 14.35:
            return '20m'
        elif 18.068 <= mhz <= 18.168:
            return '17m'
        elif 21.0 <= mhz <= 21.45:
            return '15m'
        elif 24.89 <= mhz <= 24.99:
            return '12m'
        elif 28.0 <= mhz <= 29.7:
            return '10m'
        return 'Other'
    
    df['Band'] = df['MHz'].apply(get_band)
    
    # Import helper function
    from wspr_folium_map import maidenhead_to_latlon, BAND_COLORS
    
    # Process data
    rows = []
    for role, role_name in [('heard', 'KD3CCO heard'), ('heard_by', 'KD3CCO heard by')]:
        if role == 'heard':
            subset = df[(df['RX'] == 'KD3CCO')].copy()
        else:
            subset = df[(df['TX'] == 'KD3CCO')].copy()
        
        subset['role'] = role_name
        rows.append(subset)
    
    plot_df = pd.concat(rows, ignore_index=True)
    plot_df = plot_df.dropna(subset=['txGrid', 'rxGrid', 'Band'])
    plot_df['tx_ll'] = plot_df['txGrid'].apply(maidenhead_to_latlon)
    plot_df['rx_ll'] = plot_df['rxGrid'].apply(maidenhead_to_latlon)
    plot_df = plot_df.dropna(subset=['tx_ll', 'rx_ll'])
    
    # Filter to long-distance paths for clear visualization
    plot_df['distance_km'] = plot_df.apply(
        lambda row: geodesic(row['tx_ll'], row['rx_ll']).km,
        axis=1
    )
    
    # Select a few long-distance paths for demonstration
    long_distance = plot_df[plot_df['distance_km'] > 5000].head(5)
    
    print(f"\n=== GEODESIC GEOMETRY TEST ===")
    print(f"Testing {len(long_distance)} long-distance paths (5000+ km)")
    print(f"\nPath details:")
    for idx, (_, row) in enumerate(long_distance.iterrows(), 1):
        tx_lat, tx_lon = row['tx_ll']
        rx_lat, rx_lon = row['rx_ll']
        dist = row['distance_km']
        print(f"  Path {idx}: {row['Band']} {row['TX']}→{row['RX']} | Distance: {dist:.0f} km")
        print(f"    TX: ({tx_lat:.2f}, {tx_lon:.2f})  RX: ({rx_lat:.2f}, {rx_lon:.2f})")
    
    # Create diagnostic map with interpolated paths
    latitudes = [ll[0] for ll in plot_df['tx_ll'].tolist() + plot_df['rx_ll'].tolist()]
    longitudes = [ll[1] for ll in plot_df['tx_ll'].tolist() + plot_df['rx_ll'].tolist()]
    center = [sum(latitudes) / len(latitudes), sum(longitudes) / len(longitudes)]
    
    # Map with interpolated great circles
    map_with_gc = folium.Map(
        location=center,
        zoom_start=3,
        tiles='OpenStreetMap',
        prefer_canvas=False
    )
    
    gc_group = FeatureGroup(name='Great Circle (Interpolated)', show=True)
    straight_group = FeatureGroup(name='Straight Line', show=True)
    
    for _, row in long_distance.iterrows():
        tx_lat, tx_lon = row['tx_ll']
        rx_lat, rx_lon = row['rx_ll']
        color = BAND_COLORS.get(row['Band'], 'gray')
        
        # Straight line
        folium.PolyLine(
            locations=[(tx_lat, tx_lon), (rx_lat, rx_lon)],
            color=color,
            weight=3,
            opacity=0.5,
            dash_array='5, 5',  # Dashed
        ).add_to(straight_group)
        
        # Great circle (interpolated)
        gc_points = interpolate_great_circle(tx_lat, tx_lon, rx_lat, rx_lon, num_points=50)
        folium.PolyLine(
            locations=gc_points,
            color=color,
            weight=2,
            opacity=0.9,
        ).add_to(gc_group)
        
        # Mark endpoints
        folium.CircleMarker(
            location=(tx_lat, tx_lon),
            radius=4,
            color=color,
            fill=True,
            fillColor=color,
            popup=f'{row["TX"]} TX',
        ).add_to(gc_group)
        
        folium.CircleMarker(
            location=(rx_lat, rx_lon),
            radius=4,
            color=color,
            fill=True,
            fillColor=color,
            popup=f'{row["RX"]} RX',
        ).add_to(gc_group)
    
    map_with_gc.add_child(gc_group)
    map_with_gc.add_child(straight_group)
    LayerControl(collapsed=False).add_to(map_with_gc)
    map_with_gc.save('analysis_images/test_geodesic_comparison.html')
    
    print(f"\n✓ Saved test map to: analysis_images/test_geodesic_comparison.html")
    print(f"  - Toggle 'Great Circle (Interpolated)' to see curved paths")
    print(f"  - Toggle 'Straight Line' to see direct connections")
    print(f"  - On a Mercator projection, great circles appear curved")

if __name__ == '__main__':
    main()
