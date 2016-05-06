import os
from stravalib import Client, exc, model
from requests.exceptions import ConnectionError, HTTPError
import requests
import csv
import shutil
import datetime as dt
from datetime import datetime

# Creating a log file and a logging function
log = open("log.txt","a+")
def logger (message):
	now = str(datetime.now())
	log.write(now + " | " + message + "\n")
	print message

# Opening the connection to Strava
logger("Connecting to Strava")
client = Client()

# You need to run the strava_local_client.py script - with your application's ID and secret - to generate the access token.
access_token = "123456789" # replace this with your token
client.access_token = access_token
athlete = client.get_athlete()
logger("Now authenticated for " + athlete.firstname + " " + athlete.lastname)

# Creating an archive folder to put uploaded .gpx files
archive = "../archive"

# Function to convert the HH:MM:SS in the Runkeeper CSV to seconds
def duration_calc(duration):
	
	# Splits the duration on the :, so we wind up with a 3-part array
	split_duration = str(duration).split(":")

	# If the array only has 2 elements, we know the run was less than an hour
	if len(split_duration) == 2:
		hours = 0
		minutes = int(split_duration[0])
		seconds = int(split_duration[1])
	else:
		hours = int(split_duration[0])
		minutes = int(split_duration[1])
		seconds = int(split_duration[2])
	
	total_seconds = seconds + (minutes*60) + (hours*60*60)
	return total_seconds

activity_counter = 0
# We open the cardioactivities CSV file and start reading through it
with open('cardioActivities.csv', 'rb') as csvfile:
	runs = csv.reader(csvfile)
	for row in runs:
		# if there is a gpx file listed, find it and upload it
		if (".gpx" in row[11] and "Running" in row[1]):
			gpxfile = row[11]
			if gpxfile in os.listdir('.'):
				logger("Uploading " + gpxfile)
				try:
					upload = client.upload_activity(
						activity_file = open(gpxfile,'r'),
						data_type = 'gpx',
						private = False,
						description = row[10],
						activity_type = "run"
						)
				except exc.ActivityUploadFailed as err:
					logger("Uploading problem raised: {}".format(err))
					errStr = str(err)
					# deal with duplicate type of error, if duplicate then continue with next file, else stop
					if errStr.find('duplicate of activity'):
						logger("Moving dulicate activity file {}".format(gpxfile))
						shutil.move(gpxfile,archive)
						isDuplicate = True
						log_message = "Duplicate File " + gpxfile
						log.write(log_message)
					else:
						exit(1)

				except ConnectionError as err:
					logger("No Internet connection: {}".format(err))
					exit(1)

				logger("Upload succeeded.\nWaiting for response...")

				try:
					upResult = upload.wait()
				except HTTPError as err:
					logger("Problem raised: {}\nExiting...".format(err))
					exit(1)
				except:
					logger("Another problem occured, sorry...")
					exit(1)
				
				logger("Uploaded " + gpxfile + " - Activity id: " + str(upResult.id))

				shutil.move(gpxfile, archive)
			else:
				logger("No file found for " + gpxfile + "!")

		#if no gpx file, upload the data from the CSV
		else:
			if (("Running" in row[1]) and (row[0] not in log)):
				logger("Manually uploading " + row[0])
				dur = duration_calc(row[4])
				dist = float(row[3])*1609.344
				starttime = datetime.strptime(str(row[0]),"%Y-%m-%d %H:%M:%S")

				# designates part of day for name assignment above, matching Strava convention for GPS activities
				if 3 <= starttime.hour <= 11:
					part = "Morning"
				elif 12 <= starttime.hour <= 4:
					part = "Afternoon"
				elif 5 <= starttime.hour <=7:
					part = "Evening"
				else:
					part = "Night"
				
				try:
					upload = client.create_activity(
						name = part + " Run (Manual)",
						start_date_local = starttime,
						elapsed_time = dur,
						distance = dist,
						description = row[10],
						activity_type = "run"
						)

					logger("Manually created " + row[0])

				except ConnectionError as err:
					logger("No Internet connection: {}".format(err))
					exit(1)	
		activity_counter += 1

	logger("Complete! Logged " + str(activity_counter) + " activities.")
