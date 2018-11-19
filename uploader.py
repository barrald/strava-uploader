import os
from stravalib import Client, exc, model
from requests.exceptions import ConnectionError, HTTPError
import requests
import csv
import shutil
import time
import datetime as dt
from datetime import datetime

def main():

	# Creating a log file and a logging function
	log = open("log.txt","a+")
	now = str(datetime.now())
	def logger (message):
		log.write(now + " | " + message + "\n")
		print (message)

	# Opening the connection to Strava
	logger("Connecting to Strava")
	client = Client()

	# You need to run the strava_local_client.py script - with your application's ID and secret - to generate the access token.
	access_token = "your_token" # replace this with your token
	client.access_token = access_token
	athlete = client.get_athlete()
	logger("Now authenticated for " + athlete.firstname + " " + athlete.lastname)

	# Creating an archive folder to put uploaded .gpx files
	archive = "../archive"

	# Function to convert the HH:MM:SS in the Runkeeper CSV to seconds
	def duration_calc(duration):
		# Splits the duration on the :, so we wind up with a 3-part array
		split_duration = str(duration).split(":")
		# If the array only has 2 elements, we know the activity was less than an hour
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

	# Translate RunKeeper's activity codes to Strava's, could probably be cleverer
	def activity_translator(rk_type):
		if rk_type == "Running":
			return "Run"
		elif rk_type == "Cycling":
			return "Ride"
		elif rk_type == "Hiking":
			return "Hike"
		elif rk_type == "Walking":
			return "Walk"
		elif rk_type == "Swimming":
			return "Swim"
		elif rk_type == "Elliptical":
			return "Elliptical"
		else:
			return "None"
		# feel free to extend if you have other activities in your repertoire; Strava activity codes can be found in their API docs 


	# We open the cardioactivities CSV file and start reading through it
	with open('cardioActivities.csv') as csvfile:
		activities = csv.DictReader(csvfile)
		activity_counter = 0
		for row in activities:
			if activity_counter >= 599:
				logger("Upload count at 599 - pausing uploads for 15 minutes to avoid rate-limit")
				time.sleep(900)
				activity_counter = 0
			else:
				# used to have to check if we were trying to process the header row
				# no longer necessary when we process as a dictionary
				
				# if there is a gpx file listed, find it and upload it
				if ".gpx" in row['GPX File']:
					gpxfile = row['GPX File']
					strava_activity_type = activity_translator(str(row['Type']))
					if gpxfile in os.listdir('.'):
						logger("Uploading " + gpxfile)
						try:
							upload = client.upload_activity(
								activity_file = open(gpxfile,'r'),
								data_type = 'gpx',
								private = False,
								description = row['Notes'],
								activity_type = strava_activity_type
								)
						except exc.ActivityUploadFailed as err:
							logger("Uploading problem raised: {}".format(err))
							errStr = str(err)
							# deal with duplicate type of error, if duplicate then continue with next file, else stop
							if errStr.find('duplicate of activity'):
								logger("Moving duplicate activity file {}".format(gpxfile))
								shutil.move(gpxfile,archive)
								isDuplicate = True
								logger("Duplicate File " + gpxfile)
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
						activity_counter += 1

						shutil.move(gpxfile, archive)
					else:
						logger("No file found for " + gpxfile + "!")

				#if no gpx file, upload the data from the CSV
				else:
					if row['Activity Id'] not in log:
						logger("Manually uploading " + row['Activity Id'])
						# convert to total time in seconds
						dur = duration_calc(row['Duration'])
						# convert to meters
						dist = float(row['Distance (mi)'])*1609.344
						starttime = datetime.strptime(str(row['Date']),"%Y-%m-%d %H:%M:%S")
						strava_activity_type = activity_translator(str(row['Type']))

						# designates part of day for name assignment above, matching Strava convention for GPS activities
						if 3 <= starttime.hour <= 11:
							part = "Morning "
						elif 12 <= starttime.hour <= 4:
							part = "Afternoon "
						elif 5 <= starttime.hour <=7:
							part = "Evening "
						else:
							part = "Night "
						
						try:
							upload = client.create_activity(
								name = part + strava_activity_type + " (Manual)",
								start_date_local = starttime,
								elapsed_time = dur,
								distance = dist,
								description = row['Notes'],
								activity_type = strava_activity_type
								)
								
							logger("Manually created " + row['Activity Id'])
							activity_counter += 1

						except ConnectionError as err:
							logger("No Internet connection: {}".format(err))
							exit(1)

		logger("Complete! Logged " + str(activity_counter) + " activities.")

if __name__ == '__main__':
	main()

