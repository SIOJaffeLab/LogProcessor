import os
import re
import json
from datetime import datetime

# Directory and file paths
log_dir = './logs/pi_runs/'
output_file = './logs/pi_runs_duplicate.json'

# Regex patterns to parse the log lines
log_pattern = re.compile(r'(\w+ \d{1,2}, \d{4}) > (\d{2}:\d{2}:\d{2}) \| SER_IN \| Range 0 to 1 : ([\d\.]+) m')
no_response_pattern = re.compile(r'(\w+ \d{1,2}, \d{4}) > (\d{2}:\d{2}:\d{2}) \| SER_IN \| Response Not Received')

# Placeholder for all parsed log entries
log_entries = []

# Process all log files in the directory
for log_file in os.listdir(log_dir):
    if log_file.endswith('.log'):
        with open(os.path.join(log_dir, log_file), 'r') as file:
            for line in file:
                # Check for log entries with a distance
                match = log_pattern.match(line)
                if match:
                    date_str, time_str, distance = match.groups()
                    timestamp = datetime.strptime(f'{date_str} {time_str}', '%B %d, %Y %H:%M:%S')
                    distance = float(distance)
                    
                    log_entries.append({
                        "timestamp": timestamp,
                        "distance": distance,
                    })
                
                # Check for log entries without a response
                match = no_response_pattern.match(line)
                if match:
                    date_str, time_str = match.groups()
                    timestamp = datetime.strptime(f'{date_str} {time_str}', '%B %d, %Y %H:%M:%S')
                    
                    log_entries.append({
                        "timestamp": timestamp,
                        "distance": None,
                    })

# Determine the earliest timestamp as the start time
if log_entries:
    start_time = min(entry["timestamp"] for entry in log_entries)

    # Calculate `seconds_after_start` for each entry
    for entry in log_entries:
        entry["seconds_after_start"] = (entry["timestamp"] - start_time).total_seconds()
        entry["timestamp"] = entry["timestamp"].isoformat()

    # Sort log entries by 'seconds_after_start'
    log_entries.sort(key=lambda x: x['seconds_after_start'])

    # Write sorted log entries to the output JSON file
    with open(output_file, 'w') as json_file:
        json.dump(log_entries, json_file, indent=4)

    print(f"Converted log files to {output_file}")
else:
    print("No log entries found.")
