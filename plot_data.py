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
logger.add("conversion_process.log", format="{time} {level} {message}", level="INFO")

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
            if is_valid_coordinate(boat_latitude, boat_longitude):
                boat_data.append({
                    'latitude': boat_latitude,
                    'longitude': boat_longitude,
                    'timestamp': entry.get("timestamp", "N/A")
                })
            else:
                logger.warning(f"Invalid boat coordinate found: {entry}")
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

# Initialize lists to store distances and time for plotting
times = []
calculated_distances_plot = []
original_distances_plot = []
boat_distances = []
boat_times = []  # For storing times that correspond to boat distances
original_times = []  # For storing times that correspond to original distances
all_distances = []  # For storing all calculated distances between boat and buoy

# Function to calculate the mean GPS coordinates
def calculate_mean_gps_coordinates(gps_points):
    latitudes = [point['latitude'] for point in gps_points]
    longitudes = [point['longitude'] for point in gps_points]
    
    mean_latitude = np.mean(latitudes)
    mean_longitude = np.mean(longitudes)
    
    return {'mean_latitude': mean_latitude, 'mean_longitude': mean_longitude}

# Iterate over all entries in the pi_runs.json data for distance calculation and plotting
for entry in modified_sorted_logs:
    seconds_after_start = int(entry["seconds_after_start"])
    boat_index = int(seconds_after_start * 2)
    buoy_index = int(seconds_after_start * 1.6)
    
    try:
        closest_boat_point = boat_data[boat_index]
        closest_buoy_point = buoy_data[buoy_index]
        
        # Calculate the distance between the boat and buoy using geopy
        calculated_distance = geodesic(
            (closest_boat_point['latitude'], closest_boat_point['longitude']),
            (closest_buoy_point['latitude'], closest_buoy_point['longitude'])
        ).meters
        
        # Store the time and calculated distance
        times.append(seconds_after_start)
        all_distances.append(calculated_distance)
        
        # Calculate the distance of the boat from the starting point (assuming the first point is the start)
        boat_distance = geodesic(
            (boat_data[0]['latitude'], boat_data[0]['longitude']),
            (closest_boat_point['latitude'], closest_boat_point['longitude'])
        ).meters
        boat_distances.append(boat_distance)
        boat_times.append(seconds_after_start)  # Append the time corresponding to boat_distance
        
        if entry["distance"] is not None:  # Successful range
            calculated_distances_plot.append(calculated_distance)
            original_distances_plot.append(entry["distance"])
            original_times.append(seconds_after_start)  # Append the time corresponding to original distance
        
    except IndexError:
        logger.warning(f"Boat or Buoy index out of bounds for seconds_after_start {seconds_after_start}. Skipping this entry.")
        continue

# Create a figure with subplots
plt.figure(figsize=(12, 12))

# Subplot 1: Boat distance over time
plt.subplot(4, 1, 1)
plt.plot(boat_times, boat_distances, 'o-', label='Boat Distance (meters)', color='orange')
plt.xlabel('Time (seconds after start)')
plt.ylabel('Boat Distance (meters)')
plt.title('Boat Distance Over Time')
plt.legend()
plt.grid(True)

# Subplot 2: Original vs. Calculated Distances over time
plt.subplot(4, 1, 2)
plt.plot(original_times, original_distances_plot, 'o-', label='Original Distance (meters)', color='blue')
plt.plot(original_times, calculated_distances_plot, 'x-', label='Calculated Distance (meters)', color='green')
plt.xlabel('Time (seconds after start)')
plt.ylabel('Distance (meters)')
plt.title('Comparison of Original and Calculated Distances Over Time')
plt.legend()
plt.grid(True)

# Subplot 3: Error vs. Seconds After Start
errors = np.abs(np.array(original_distances_plot) - np.array(calculated_distances_plot))
plt.subplot(4, 1, 3)
plt.plot(original_times, errors, color='purple', marker='o', linestyle='-', label='Error vs Seconds After Start')
plt.xlabel('Time (seconds after start)')
plt.ylabel('Error (meters)')
plt.title('Error vs. Seconds After Start')
plt.legend()
plt.grid(True)

# Subplot 4: All calculated distances between boat and buoy over time
plt.subplot(4, 1, 4)
plt.plot(times, all_distances, 'o-', label='Calculated Distance (meters)', color='green')
plt.xlabel('Time (seconds after start)')
plt.ylabel('Distance (meters)')
plt.title('Calculated Distance Between Boat and Buoy Over Time')
plt.legend()
plt.grid(True)

plt.tight_layout()

# Save the plot
plt.savefig('all_plots_with_boat_buoy_distances.png')
logger.info("Saved all plots with boat and buoy distances to 'all_plots_with_boat_buoy_distances.png'.")

# Optionally display the plot
plt.show()
