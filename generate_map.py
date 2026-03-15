import folium
import gpxpy
import glob
from datetime import datetime
from branca.colormap import LinearColormap

# Focus map on this initial location
INIT_LOCATION = [47.3769, 8.5417]  # Zurich, Switzerland

def format_duration(seconds):
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    if hours > 0:
        return f"{hours}h {minutes}m"
    else:
        return f"{minutes}m"

def compute_elevation_gain(segment):  # Function: Compute elevation gain for a GPX segment
    gain = 0
    elevations = [p.elevation for p in segment.points if p.elevation is not None]
    
    if not elevations:
        return 0
    
    # Apply moving average smoothing (adjust windows size as needed)
    window_size = 7
    smoothed = []
    for i in range(len(elevations)):
        start = max(0, i - window_size // 2)
        end = min(len(elevations), i + window_size // 2 + 1)
        smoothed.append(sum(elevations[start:end]) / (end - start))
    
    last_valid = None
    for elev in smoothed:
        if last_valid is not None:
            diff = elev - last_valid
            if diff > 0:
                gain += diff
        last_valid = elev
    
    return gain

# First pass: compute elevation gains + distances for all files
elevation_data = []
year_stats = {}

for gpx_file in glob.glob("gpx_files/*.gpx"):
    with open(gpx_file, "r") as f:
        gpx = gpxpy.parse(f)

    total_gain = 0
    total_distance = 0

    # Collect all timestamps to compute duration
    all_times = []
    for track in gpx.tracks:
        for segment in track.segments:
            total_gain += compute_elevation_gain(segment)
            total_distance += segment.length_3d() / 1000.0  # km
            for point in segment.points:
                if point.time:
                    all_times.append(point.time)

    if all_times:
        start_time = min(all_times)
        end_time = max(all_times)
        duration = end_time - start_time
        total_duration = duration.total_seconds()
    else:
        total_duration = 0

    year = gpx.time.year if gpx.time else "Unknown"

    if year not in year_stats:
        year_stats[year] = {"distance": 0.0, "gain": 0.0}

    year_stats[year]["distance"] += total_distance
    year_stats[year]["gain"] += total_gain

    elevation_data.append((gpx_file, total_gain, total_distance, total_duration))

# Determine min/max elevation gain for colormap
if elevation_data:
    min_gain = min(g[1] for g in elevation_data)
    max_gain = max(g[1] for g in elevation_data)
else:
    min_gain = 0
    max_gain = 1  # Avoid division by zero or invalid colormap

colormap = LinearColormap(
    colors=["blue", "red"],
    vmin=min_gain,
    vmax=max_gain
)

# Create map
m = folium.Map(location=INIT_LOCATION, zoom_start=12)

# Create layer groups by year
year_layers = {}

for year, stats in year_stats.items():
    km = round(stats["distance"], 1)
    gain = int(stats["gain"])
    layer_name = f"{year} - {km} km / {gain} m gain"
    year_layers[year] = folium.FeatureGroup(name=layer_name, show=True).add_to(m)

# Define JavaScript for on_each_feature (click to select/deselect)
on_each_feature_js = """
function(feature, layer) {
    if (typeof window._selectedLayer === 'undefined') {
        window._selectedLayer = null;
    }

    layer.on({
        click: function () {
            if (window._selectedLayer) {
                window._selectedLayer.setStyle({
                    color: window._selectedLayer.feature.properties.color,
                    weight: 3,
                    opacity: 0.8
                });
            }

            if (window._selectedLayer === layer) {
                window._selectedLayer = null;
                return;
            }

            layer.setStyle({color: 'yellow', weight: 6, opacity: 1.0});
            window._selectedLayer = layer;
        }
    });

    layer.bindPopup(feature.properties.tooltip);
}
"""

# Second pass: draw tracks
for gpx_file, elevation_gain, total_distance, total_duration in elevation_data:
    with open(gpx_file, "r") as f:
        gpx = gpxpy.parse(f)

    activity_name = gpx.tracks[0].name if gpx.tracks and gpx.tracks[0].name else gpx_file
    activity_time = gpx.time.strftime("%Y-%m-%d") if gpx.time else "Unknown date"
    year = gpx.time.year if gpx.time else "Unknown"

    route_color = colormap(elevation_gain)

    popup_text = (
        f"<div style='width: 150px'><b>{activity_name}</b></div><br>"
        f"Date: {activity_time}<br>"
        f"Distance: {total_distance:.1f} km<br>"
        f"Duration: {format_duration(total_duration)}<br>"
        f"Elevation gain: {int(elevation_gain)} m"
    )

    for track in gpx.tracks:
        for segment in track.segments:
            coords = [(p.longitude, p.latitude) for p in segment.points]
            if not coords:
                continue

            geojson_coords = [(lon, lat) for lon, lat in coords]

            geojson_feature = {
                "type": "Feature",
                "properties": {
                    "color": route_color,
                    "tooltip": popup_text
                },
                "geometry": {
                    "type": "LineString",
                    "coordinates": geojson_coords
                }
            }

            gj = folium.GeoJson(
                geojson_feature,
                style_function=lambda feature: {
                    "color": feature["properties"]["color"],
                    "weight": 3,
                    "opacity": 0.8
                },
                on_each_feature=on_each_feature_js
            )

            gj.add_to(year_layers[year])

# Add layer control to the map
folium.LayerControl().add_to(m)

m.save("cycling_routes_map.html")
