import folium
import numpy as np
from geopy.distance import geodesic
import matplotlib.pyplot as plt
from matplotlib import colors as mcolors
import rasterio
from rasterio.plot import reshape_as_image
from folium.raster_layers import ImageOverlay
from folium import CircleMarker, Marker
from matplotlib.colors import LinearSegmentedColormap
from loguru import logger
import json

# Initialize logger
logger.add("make_site.log", format="{time} {level} {message}", level="INFO")

def is_valid_coordinate(latitude, longitude):
    return latitude is not None and longitude is not None

# Load the buoy GPS data from the resampled_buoy_gps_data.json file
buoy_data = []
buoy_file_path = './logs/resampled_buoy_gps_data.json'
with open(buoy_file_path, 'r') as f:
    for line in f:
        try:
            entry = json.loads(line)
            buoy_latitude = entry["Latitude"]
            buoy_longitude = entry["Longitude"]
            if is_valid_coordinate(buoy_latitude, buoy_longitude):
                buoy_data.append({
                    'latitude': buoy_latitude,
                    'longitude': buoy_longitude,
                    'timestamp': entry.get("timestamp", "N/A")
                })
            else:
                logger.warning(f"Invalid buoy coordinate found: {entry}")
        except json.JSONDecodeError as e:
            logger.error(f"Error parsing JSON from buoy data: {e}")
        except KeyError as e:
            logger.error(f"Missing key in buoy data: {e}")

logger.info(f"Loaded {len(buoy_data)} buoy GPS points.")

# Load the boat GPS data from the resampled_boat_gps_data.json file
boat_data = []
boat_file_path = './logs/resampled_boat_gps_data.json'
with open(boat_file_path, 'r') as f:
    for line in f:
        try:
            entry = json.loads(line)
            boat_latitude = entry["phone_latitude"]
            boat_longitude = entry["phone_longitude"]
            if is_valid_coordinate(boat_longitude, boat_longitude):
                boat_data.append({
                    'latitude': boat_latitude,
                    'longitude': boat_longitude,
                    'timestamp': entry.get("timestamp", "N/A")
                })
            else:
                logger.warning(f"Invalid buoy coordinate found: {entry}")
        except json.JSONDecodeError as e:
            logger.error(f"Error parsing JSON from boat data: {e}")
        except KeyError as e:
            logger.error(f"Missing key in boat data: {e}")

logger.info(f"Loaded {len(boat_data)} boat GPS points.")

# Load the modified JSON file data (ranges)
modified_json_file_path = './logs/pi_runs.json'
with open(modified_json_file_path, 'r') as file:
    try:
        modified_sorted_logs = json.load(file)
        logger.info(f"Loaded {len(modified_sorted_logs)} range request entries.")
    except json.JSONDecodeError as e:
        logger.error(f"Error parsing modified sorted logs JSON file: {e}")

# Define bounds based on the provided coordinates
bounds = [[32.84947, -117.40825], [32.96678, -117.24071]]

# Open the TIFF image using rasterio
tiff_file = './site/bethymetry.tiff'
with rasterio.open(tiff_file) as dataset:
    image_data = dataset.read([1, 2, 3])  # Assuming RGB bands
    image_data = reshape_as_image(image_data)

# Create a folium map object centered on the average coordinates of the bounds
my_map = folium.Map(location=[(32.84947 + 32.96678) / 2, (-117.40825 + -117.24071) / 2], zoom_start=13)

# Add the bathymetry image as an overlay
ImageOverlay(image=image_data, name='Scripps Bathymetry Overlay', bounds=bounds, opacity=0.4).add_to(my_map)

# Add Google Satellite as the default basemap (pure satellite view)
folium.TileLayer(
    tiles='http://mt1.google.com/vt/lyrs=s&x={x}&y={y}&z={z}',
    attr='Google',
    name='Google Satellite',
    overlay=False,
    control=True,
    max_zoom=22
).add_to(my_map)

# Add Google Maps as an optional layer
folium.TileLayer(
    tiles='http://mt1.google.com/vt/lyrs=m&x={x}&y={y}&z={z}',
    attr='Google',
    name='Google Maps',
    overlay=False,
    control=False,
    max_zoom=22
).add_to(my_map)

# Plot boat GPS points (Phone data) with gradient color
boat_cmap = LinearSegmentedColormap.from_list("boat_gradient", [(1.0, 0.75, 0.8), (0.8, 0.0, 0.4)])  # Light pink to dark pink
boat_color_values = [boat_cmap(i / len(boat_data)) for i in range(len(boat_data))]

for entry, color in zip(boat_data, boat_color_values):
    folium.CircleMarker(
        location=[entry['latitude'], entry['longitude']],
        radius=5,
        color=mcolors.rgb2hex(color[:3]),  # Convert to hex color
        fill=True,
        fill_opacity=1,
        popup=folium.Popup(f"Timestamp: {entry['timestamp']}", max_width=200)
    ).add_to(my_map)

# Plot buoy GPS points with gradient color
buoy_cmap = LinearSegmentedColormap.from_list("buoy_gradient", [(0.75, 0.75, 1.0), (0.0, 0.0, 0.8)])  # Light blue to dark blue
buoy_color_values = [buoy_cmap(i / len(buoy_data)) for i in range(len(buoy_data))]

for entry, color in zip(buoy_data, buoy_color_values):
    folium.CircleMarker(
        location=[entry['latitude'], entry['longitude']],
        radius=5,
        color=mcolors.rgb2hex(color[:3]),  # Convert to hex color
        fill=True,
        fill_opacity=1,
        popup=folium.Popup(f"Timestamp: {entry['timestamp']}", max_width=200)
    ).add_to(my_map)

logger.info(f"Plotted {len(boat_data)} boat GPS points and {len(buoy_data)} buoy GPS points on the map.")

# Create feature groups for good and bad ranges with popups showing time and range
good_ranges_group = folium.FeatureGroup(name='Good Ranges').add_to(my_map)
bad_ranges_group = folium.FeatureGroup(name='Bad Ranges').add_to(my_map)

# Extract and plot range request data with closest boat GPS points based on seconds_after_start
original_distances = []
calculated_distances = []
errors = []
seconds_after_start_values = []

for entry in modified_sorted_logs:
    seconds_after_start = int(entry["seconds_after_start"])
    
    # Constrain the index to be within the bounds of the lists
    boat_index = int(seconds_after_start * 2.1)
    buoy_index = int(seconds_after_start *1.6)
    
    try:
        closest_boat_point = boat_data[boat_index]
        closest_buoy_point = buoy_data[buoy_index]
    except:
        print(boat_index, len(boat_data))
        print(buoy_index, len(buoy_data))
        continue
    
    # Calculate the distance between the boat and buoy using geopy
    calculated_distance = geodesic(
        (closest_boat_point['latitude'], closest_boat_point['longitude']),
        (closest_buoy_point['latitude'], closest_buoy_point['longitude'])
    ).meters

    # Store the original and calculated distances
    if entry["distance"] is not None:  # Successful range
        original_distances.append(entry["distance"])
        calculated_distances.append(calculated_distance)
        errors.append(entry["distance"] - calculated_distance)
        seconds_after_start_values.append(seconds_after_start)
        
        popup_content = (f"Timestamp: {entry['timestamp']}<br>"
                         f"Modem Distance: {entry['distance']} meters<br>"
                         f"Actual Distance: {calculated_distance:.2f} meters")
        folium.Marker(
            location=[closest_boat_point['latitude'], closest_boat_point['longitude']],
            icon=folium.Icon(color='green', icon='check', prefix='fa'),
            popup=folium.Popup(popup_content, max_width=200)
        ).add_to(good_ranges_group)
    else:  # Failed range
        popup_content = (f"Timestamp: {entry['timestamp']}<br>"
                         f"Actual Distance: {calculated_distance:.2f} meters")
        folium.Marker(
            location=[closest_boat_point['latitude'], closest_boat_point['longitude']],
            icon=folium.Icon(color='red', icon='times', prefix='fa'),
            popup=folium.Popup(popup_content, max_width=200)
        ).add_to(bad_ranges_group)

# Add the feature groups to the map
my_map.add_child(good_ranges_group)
my_map.add_child(bad_ranges_group)

# Calculate the total duration of the boat data in minutes
boat_end_minutes = len(boat_data) * 2 // 60  # Assuming each point represents 2 seconds

# Add a custom legend for both boat and buoy times with gradients and range markers
legend_html = f'''
<div style="
     position: fixed; 
     bottom: 30px; left: 30px; width: 450px; 
     background-color: rgba(44, 44, 44, 0.4); border: 0px solid #666; z-index:9999; font-size: 12px;
     padding: 15px; padding-bottom: 30px; color: #f0f0f0; border-radius: 10px;
     backdrop-filter: blur(3px);">
    <u><b style="font-size: 16px;">Legend</b></u><br><br>
    
    <div style="display: flex; align-items: center;">
        <b style="width: 30px;">Boat</b>
        <div style="flex-grow: 1; height: 15px; background: linear-gradient(to right, #ffb3cc, #cc0066); position: relative; margin-left: 10px; margin-right: 40px;">
            <!-- Start and End Lines -->
            <div style="position: absolute; left: 0%; bottom: -30px; height: 30px; width: 1px; background-color: #f0f0f0;"></div>
            <div style="position: absolute; right: 0%; bottom: -30px; height: 30px; width: 1px; background-color: #f0f0f0;"></div>
        </div>
    </div>
    
    <div style="display: flex; align-items: center; margin-top: 20px;">
        <b style="width: 30px;">Buoy</b>
        <div style="flex-grow: 1; height: 15px; background: linear-gradient(to right, #b3b3ff, #0000cc); position: relative; margin-left: 10px; margin-right: 40px;">
            <!-- Start and End Lines -->
            <div style="position: absolute; left: 0%; bottom: -30px; height: 30px; width: 1px; background-color: #f0f0f0;"></div>
            <div style="position: absolute; right: 0%; bottom: -30px; height: 30px; width: 1px; background-color: #f0f0f0;"></div>
        </div>
    </div>
    
    <!-- Center-aligned labels directly under the lines -->
    <div style="position: relative; margin-top: 25px;">
        <div style="position: absolute; left: calc(0% + 15px); text-align: center;">0 minutes</div>
        <div style="position: absolute; right: calc(0% - 0px); text-align: center;">{boat_end_minutes} minutes</div>
    </div>
    <br>
    
    <!-- Good and Bad Range Markers -->
    <div style="display: flex; align-items: center; margin-top: 20px;">
        <i class="fa fa-check-circle" style="color: green; font-size: 24px; margin-right: 10px;"></i>
        <b style="font-size: 14px;">Good Range</b>
    </div>
    <div style="display: flex; align-items: center; margin-top: 10px;">
        <i class="fa fa-times-circle" style="color: red; font-size: 24px; margin-right: 10px;"></i>
        <b style="font-size: 14px;">Bad Range</b>
    </div>
    
    <br>
</div>
'''

my_map.get_root().html.add_child(folium.Element(legend_html))

# Add a layer control panel to toggle the ranges on and off
my_map.add_child(folium.LayerControl())

# Save and display the map
map_file = './site/index.html'
my_map.save(map_file)
logger.info(f"Map saved to {map_file}")

# Plot original vs. calculated distances
plt.figure(figsize=(10, 6))
plt.scatter(original_distances, calculated_distances, color='blue', edgecolors='k', label='Distance Comparison', alpha=0.7)
plt.plot([min(original_distances), max(original_distances)], [min(original_distances), max(original_distances)], color='red', linestyle='--', label='Ideal Correlation')

plt.xlabel('Original Distance (meters)')
plt.ylabel('Calculated Distance (meters)')
plt.title('Comparison of Original and Calculated Distances')
plt.legend()
plt.grid(True)
plt.tight_layout()

# Save the plot
plt.savefig('distance_comparison_plot.png')
logger.info("Saved distance comparison plot to 'distance_comparison_plot.png'.")

# Calculate absolute errors
absolute_errors = np.abs(np.array(original_distances) - np.array(calculated_distances))

# Create a figure with two subplots
plt.figure(figsize=(12, 10))

# Subplot 1: Original vs. Calculated Distances
plt.subplot(2, 1, 1)
plt.scatter(original_distances, calculated_distances, color='blue', edgecolors='k', label='Distance Comparison', alpha=0.7)
plt.plot([min(original_distances), max(original_distances)], [min(original_distances), max(original_distances)], color='red', linestyle='--', label='Ideal Correlation')
plt.xlabel('Original Distance (meters)')
plt.ylabel('Calculated Distance (meters)')
plt.title('Comparison of Original and Calculated Distances')
plt.legend()
plt.grid(True)

# Subplot 2: Absolute Error
plt.subplot(2, 1, 2)
plt.plot(original_distances, absolute_errors, color='green', marker='o', linestyle='-', label='Absolute Error')
plt.xlabel('Original Distance (meters)')
plt.ylabel('Absolute Error (meters)')
plt.title('Absolute Error Between Original and Calculated Distances')
plt.legend()
plt.grid(True)

plt.tight_layout()

# Save the plot
plt.savefig('distance_comparison_with_error_plot.png')
logger.info("Saved distance comparison and error plot to 'distance_comparison_with_error_plot.png'.")


# Plot error vs. seconds after start
plt.figure(figsize=(10, 6))
plt.plot(seconds_after_start_values, errors, color='purple', marker='o', linestyle='-', label='Error vs Seconds After Start')
plt.xlabel('Seconds After Start')
plt.ylabel('Error (meters)')
plt.title('Error vs. Seconds After Start')
plt.grid(True)
plt.legend()

# Save the plot
plt.savefig('error_vs_seconds_after_start_plot.png')
logger.info("Saved error vs seconds after start plot to 'error_vs_seconds_after_start_plot.png'.")

# Optionally display the plot
plt.show()
