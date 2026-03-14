import garminconnect
import os
import base64
import getpass
import configparser

# Gamin activity export settings > adjust as needed
garmin_activity_type = "cycling" # filter for this activity type only
garmin_min_distance = 10         # filter for min distance in km
garmin_max_activities = 1000     # max number of recent activities to fetch (Garmin API may have limits)

if not os.path.exists("login.ini"):  # create new file with login data, encoded in base64
    garmin_email = input("Enter Garmin Email Address: ")
    garmin_password = getpass.getpass("Enter Garmin Password: ")
    encoded_email = base64.b64encode(garmin_email.encode('utf-8')).decode('utf-8')
    encoded_pw = base64.b64encode(garmin_password.encode('utf-8')).decode('utf-8')
    config = configparser.ConfigParser()
    config['login'] = {'email': encoded_email, 'password': encoded_pw}
    with open("login.ini", "w") as f:
        config.write(f)

config = configparser.ConfigParser() # read login data from file, decode from base64
config.read("login.ini")

garmin_email = base64.b64decode(config['login']['email']).decode('utf-8')
garmin_password = base64.b64decode(config['login']['password']).decode('utf-8')
client = garminconnect.Garmin(garmin_email, garmin_password)
client.login()

activities = client.get_activities(0, garmin_max_activities)  # fetch n recent activities

activities_filtered = [ # filter activities by type and min distance
    a for a in activities
    if garmin_activity_type in a["activityType"]["typeKey"].lower()
    and a["distance"] >= garmin_min_distance*1000
]

print(f"Found {len(activities_filtered)} {garmin_activity_type} activities >= {garmin_min_distance} km")

os.makedirs("gpx_files", exist_ok=True)

for act in activities_filtered:  # export all matching activities as GPX files
    act_id = act["activityId"]
    file_path = f"gpx_files/{act_id}.gpx"

    # Skip if file already exists
    if os.path.exists(file_path):
        print(f"Skipping {file_path} (already exists)")
        continue

    # Download GPX
    gpx_data = client.download_activity(
        act_id, dl_fmt=client.ActivityDownloadFormat.GPX
    )

    # Convert to text for searching
    gpx_text = gpx_data.decode("utf-8", errors="ignore")

    # Check file for valid coordinates
    if "<trkpt" not in gpx_text:
        print(f"Skipping activity {act_id}: no GPS coordinates found (corrupt/indoor activity)")
        continue

    # Save GPX only if valid
    with open(file_path, "wb") as f:
        f.write(gpx_data)

    print(f"Saved {file_path}")

