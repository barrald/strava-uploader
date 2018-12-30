#!/usr/bin/env python

import os
from stravalib import Client, exc, model
from requests.exceptions import ConnectionError, HTTPError
import requests
import csv
import shutil
import time
import datetime as dt
from datetime import datetime
import logging
import sys

logger = None

#####################################
# Access Token
#
# You need to run the strava_local_client.py script, with your application's ID and secret,
# to generate the access token.
#
# When you have the access token, you can
#   (a) set an environment variable `STRAVA_UPLOADER_TOKEN` or;
#   (b) replace `None` below with the token in quote marks, e.g. access_token = 'token'
#####################################
access_token = None

cardio_file = 'cardioActivities.csv'

archive_dir = 'archive'

# This list can be expanded
# https://developers.strava.com/docs/uploads/#upload-an-activity
activity_translations = {
	'running': 'run',
	'cycling': 'ride',
	'hiking': 'hike',
	'walking': 'walk',
	'swimming': 'swim'
}

def set_up_logger():
	global logger
	logger = logging.getLogger(__name__)
	formatter = logging.Formatter('[%(asctime)s] [%(levelname)s]:%(message)s')
	std_out_handler = logging.StreamHandler(sys.stdout)
	std_out_handler.setLevel(logging.DEBUG)
	std_out_handler.setFormatter(formatter)
	file_handler = logging.FileHandler('strava-uploader.log')
	file_handler.setLevel(logging.DEBUG)
	file_handler.setFormatter(formatter)
	logger.addHandler(file_handler)
	logger.addHandler(std_out_handler)
	logger.setLevel(logging.DEBUG)

def get_cardio_file():
	if os.path.isfile(cardio_file):
		return open(cardio_file)

	logger.error(cardio_file + ' file cannot be found')
	exit(1)

def get_strava_access_token():
	global access_token

	if access_token is not None:
		logger.info('Found access token')
		return access_token

	access_token = os.environ.get('STRAVA_UPLOADER_TOKEN')
	if access_token is not None:
		logger.info('Found access token')
		return access_token

	logger.error('Access token not found. Please set the env variable STRAVA_UPLOADER_TOKEN')
	exit(1)

def get_strava_client():
    token = get_strava_access_token()
    client = Client()
    client.access_token = token
    return client

def archive_file(file):
	if not os.path.isdir(archive_dir):
		os.mkdir(archive_dir)

	if os.path.isfile(archive_dir + '/' + file):
		logger.warning('[' + file + '] already exists in [' + archive_dir +']')
		return

	logger.info('Backing up [' + file + '] to [' + archive_dir +']')
	shutil.move(file, archive_dir)

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

# Translate RunKeeper's activity codes to Strava's
def activity_translator(rk_type):
	# Normalise to lower case
	rk_type = rk_type.lower()

	return activity_translations[rk_type];

def increment_activity_counter(counter):
	if counter >= 599:
		logger.warning("Upload count at 599 - pausing uploads for 15 minutes to avoid rate-limit")
		time.sleep(900)
		return 0

	counter += 1
	return counter

def main():
	set_up_logger()

	cardioFile = get_cardio_file()

	client = get_strava_client()

	logger.debug('Connecting to Strava')
	athlete = client.get_athlete()
	logger.info("Now authenticated for " + athlete.firstname + " " + athlete.lastname)

	# We open the cardioactivities CSV file and start reading through it
	with cardioFile as csvfile:
		activities = csv.DictReader(csvfile)
		activity_counter = 0
		for row in activities:

			# if there is a gpx file listed, find it and upload it
			if ".gpx" in row['GPX File']:
				gpxfile = row['GPX File']
				strava_activity_type = activity_translator(str(row['Type']))
				if gpxfile in os.listdir('.'):
					logger.debug("Uploading " + gpxfile)
					try:
						upload = client.upload_activity(
							activity_file = open(gpxfile,'r'),
							data_type = 'gpx',
							private = False,
							description = row['Notes'],
							activity_type = strava_activity_type
							)
					except exc.ActivityUploadFailed as err:
						logger.warning("Uploading problem raised: {}".format(err))
						errStr = str(err)
						# deal with duplicate type of error, if duplicate then continue with next file, else stop
						if errStr.find('duplicate of activity'):
							archive_file(gpxfile)
							isDuplicate = True
							logger.debug("Duplicate File " + gpxfile)
						else:
							exit(1)

					except ConnectionError as err:
						logger.error("No Internet connection: {}".format(err))
						exit(1)

					logger.info("Upload succeeded.\nWaiting for response...")

					try:
						upResult = upload.wait()
					except HTTPError as err:
						logger.error("Problem raised: {}\nExiting...".format(err))
						exit(1)
					except:
						logger.error("Another problem occured, sorry...")
						exit(1)

					logger.info("Uploaded " + gpxfile + " - Activity id: " + str(upResult.id))
					activity_counter = increment_activity_counter(activity_counter)

					archive_file(gpxfile)
				else:
					logger.warning("No file found for " + gpxfile + "!")

			#if no gpx file, upload the data from the CSV
			else:
				if row['Activity Id'] not in log:
					logger.info("Manually uploading " + row['Activity Id'])
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

						logger.debug("Manually created " + row['Activity Id'])
						activity_counter = increment_activity_counter(activity_counter)

					except ConnectionError as err:
						logger.error("No Internet connection: {}".format(err))
						exit(1)

		logger.info("Complete! Logged " + str(activity_counter) + " activities.")

if __name__ == '__main__':
	main()
