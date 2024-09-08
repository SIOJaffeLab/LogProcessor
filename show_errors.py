
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
logger.add("show_errors_process.log", format="{time} {level} {message}", level="INFO")

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

# Extract and plot range request data with closest boat GPS points based on seconds_after_start
original_distances = []
calculated_distances = []
errors = []
seconds_after_start_values = []

for entry in modified_sorted_logs:
    seconds_after_start = int(entry["seconds_after_start"])
    
    # Constrain the index to be within the bounds of the lists
    boat_index = int(seconds_after_start * 2.1)
    buoy_index = int(seconds_after_start * 1.8)
    
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
    else:  # Failed range
        popup_content = (f"Timestamp: {entry['timestamp']}<br>"
                         f"Actual Distance: {calculated_distance:.2f} meters")

# Calculate the total duration of the boat data in minutes
boat_end_minutes = len(boat_data) * 2 // 60  # Assuming each point represents 2 seconds

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

plt.show()
