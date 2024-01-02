#!/usr/bin/env python

import os

from dotenv import load_dotenv
from stravalib import Client, exc
from stravalib.util.limiter import RateLimiter, XRateLimitRule
from requests.exceptions import ConnectionError
import csv
import shutil
import time
from datetime import datetime, timedelta
import logging
import sys

#####################################
# Access Token
#
# You need to run the strava_local_client.py script, with your application's ID and secret,
# to generate the access token.
#
# When you have the access token, you need to add it to <project_root>/.env, like:
#   STRAVA_UPLOADER_TOKEN=<your token>
#####################################

DATA_ROOT_DIR = "runkeeper-data"
cardio_file = os.path.join(DATA_ROOT_DIR, 'cardioActivities.csv')

archive_dir = os.path.join(DATA_ROOT_DIR, "uploader-output", 'archive')
skip_dir = os.path.join(DATA_ROOT_DIR, "uploader-output", 'skipped')

# This list can be expanded
# @see https://developers.strava.com/docs/uploads/#upload-an-activity
# @see https://github.com/hozn/stravalib/blob/master/stravalib/model.py#L723
activity_translations = {
    'running': 'run',
    'cycling': 'ride',
    'mountain biking': 'ride',
    'hiking': 'hike',
    'walking': 'walk',
    'swimming': 'swim'
}

# https://stackoverflow.com/a/35904211/1106893
this = sys.modules[__name__]
logger: logging.Logger = None


def set_up_logger():
    if this.logger is None:
        this.logger = logging.getLogger(__name__)
    else:
        raise RuntimeError("Logger has already been set up.")

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
    access_token = os.environ.get('STRAVA_UPLOADER_TOKEN')
    if access_token is not None:
        logger.info('Found access token')
        return access_token

    logger.error('Access token not found. Please set the env variable STRAVA_UPLOADER_TOKEN')
    exit(1)


def get_strava_client():
    token = get_strava_access_token()
    rate_limiter = RateLimiter()
    rate_limiter.rules.append(XRateLimitRule(
        {'short': {'usageFieldIndex': 0, 'usage': 0,
                   # 60s * 15 = 15 min
                   'limit': 100, 'time': (60 * 15),
                   'lastExceeded': None, },
         'long': {'usageFieldIndex': 1, 'usage': 0,
                  # 60s * 60m * 24 = 1 day
                  'limit': 1000, 'time': (60 * 60 * 24),
                  'lastExceeded': None}}))
    client = Client(rate_limiter=rate_limiter)
    client.access_token = token
    return client


def archive_file(file):
    if not os.path.isdir(archive_dir):
        os.mkdir(archive_dir)

    if os.path.isfile(archive_dir + '/' + file):
        logger.warning('[' + file + '] already exists in [' + archive_dir + ']')
        return

    logger.info('Backing up [' + file + '] to [' + archive_dir + ']')
    shutil.move(file, archive_dir)


def skip_file(file):
    if not os.path.isdir(skip_dir):
        os.mkdir(skip_dir)

    logger.info('Skipping [' + file + '], moving to [' + skip_dir + ']')
    shutil.move(file, skip_dir)


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

    total_seconds = seconds + (minutes * 60) + (hours * 60 * 60)
    return total_seconds


# Translate RunKeeper's activity codes to Strava's
def activity_translator(rk_type):
    # Normalise to lower case
    rk_type = rk_type.lower()

    if rk_type not in activity_translations:
        return None

    return activity_translations[rk_type]


def increment_activity_counter(counter):
    counter += 1
    return counter


def upload_gpx(client, gpxfile, strava_activity_type, notes):
    if not os.path.isfile(os.path.join(DATA_ROOT_DIR, gpxfile)):
        logger.warning("No file found for " + gpxfile + "!")
        return False

    logger.debug("Uploading " + gpxfile)

    for i in range(2):
        try:
            upload = client.upload_activity(
                activity_file=open(gpxfile, 'r'),
                data_type='gpx',
                private=False,
                description=notes,
                activity_type=strava_activity_type
            )
        except exc.RateLimitExceeded:
            if i > 0:
                logger.error("Daily Rate limit exceeded - exiting program")
                exit(1)
            logger.warning("Rate limit exceeded in uploading - pausing uploads for 15 minutes to avoid rate-limit")
            time.sleep(900)
            continue
        except ConnectionError as err:
            logger.error("No Internet connection: {}".format(err))
            exit(1)
        break

    logger.info("Upload succeeded.\nWaiting for response...")

    for i in range(2):
        try:
            up_result = upload.wait()

        # catch RateLimitExceeded and retry after 15 minutes
        except exc.RateLimitExceeded as err:
            if i > 0:
                logger.error("Daily Rate limit exceeded - exiting program")
                exit(1)
            logger.warning(
                "Rate limit exceeded in processing upload - pausing uploads for 15 minutes to avoid rate-limit")
            time.sleep(900)
            continue
        except exc.ActivityUploadFailed as err:
            errStr = str(err)
            # deal with duplicate type of error, if duplicate then continue with next file, else stop
            if errStr.find('duplicate of activity'):
                archive_file(gpxfile)
                logger.debug("Duplicate File " + gpxfile)
                return True
            else:
                logger.error("Another ActivityUploadFailed error: {}".format(err))
                exit(1)
        except Exception as err:
            try:
                logger.error("Problem raised: {}\nExiting...".format(err))
            except:
                logger.error("Problem raised: An error that was not specified, sorry\nExiting...")
            exit(1)
        break

    logger.info("Uploaded " + gpxfile + " - Activity id: " + str(up_result.id))
    archive_file(gpxfile)
    return True


# designates part of day for name assignment, matching Strava convention for GPS activities
def strava_day_conversion(hour_of_day):
    if 3 <= hour_of_day <= 11:
        return "Morning"
    elif 12 <= hour_of_day <= 4:
        return "Afternoon"
    elif 5 <= hour_of_day <= 7:
        return "Evening"

    return "Night"


# Get a small range of time. Note runkeeper does not maintain timezone
# in the CSV, so we must get about 12 hours earlier and later to account
# for potential miss due to UTC
def get_date_range(time, hour_buffer=12):
    if type(time) is not datetime:
        raise TypeError('time arg must be a datetime, not a %s' % type(time))

    return {
        'from': time + timedelta(hours=-1 * hour_buffer),
        'to': time + timedelta(hours=hour_buffer),
    }


def activity_exists(client, activity_name, start_time):
    date_range = get_date_range(start_time)

    logger.debug("Getting existing activities from [" + date_range['from'].isoformat() + "] to [" + date_range[
        'to'].isoformat() + "]")

    activities = client.get_activities(
        before=date_range['to'],
        after=date_range['from']
    )

    for activity in activities:
        if activity.name == activity_name:
            return True

    return False


def create_activity(client, activity_id, duration, distance, start_time, strava_activity_type, notes):
    # convert to total time in seconds
    duration = duration_calc(duration)

    day_part = strava_day_conversion(start_time.hour)

    activity_name = day_part + " " + strava_activity_type + " (Manual)"

    # Check to ensure the manual activity has not already been created
    if activity_exists(client, activity_name, start_time):
        logger.warning('Activity [' + activity_name + '] already created, skipping')
        return

    logger.info("Manually uploading [" + activity_id + "]:[" + activity_name + "]")

    try:
        upload = client.create_activity(
            name=activity_name,
            start_date_local=start_time,
            elapsed_time=duration,
            distance=distance,
            description=notes,
            activity_type=strava_activity_type
        )

        logger.debug("Manually created " + activity_id)
        return True

    except ConnectionError as err:
        logger.error("No Internet connection: {}".format(err))
        exit(1)


def miles_to_meters(miles):
    return float(miles) * 1609.344


def km_to_meters(km):
    return float(km) * 1000


def main():
    set_up_env_vars()
    set_up_logger()

    cardio_file = get_cardio_file()

    client = get_strava_client()

    logger.debug('Connecting to Strava')
    for i in range(2):
        try:
            athlete = client.get_athlete()
        except exc.RateLimitExceeded:
            if i > 0:
                logger.error("Daily Rate limit exceeded - exiting program")
                exit(1)
            logger.warning("Rate limit exceeded in connecting - Retrying strava connection in 15 minutes")
            time.sleep(900)
            continue
        break

    logger.info("Now authenticated for " + athlete.firstname + " " + athlete.lastname)

    # We open the cardioactivities CSV file and start reading through it
    with cardio_file as csvfile:
        activities = csv.DictReader(csvfile)
        activity_counter = 0
        completed_activities = []
        distance_convertor = None
        distance_key = None

        if 'Distance (mi)' in activities.fieldnames:
            distance_key = 'Distance (mi)'
            distance_convertor = miles_to_meters

        if 'Distance (km)' in activities.fieldnames:
            distance_key = 'Distance (km)'
            distance_convertor = km_to_meters

        for row in activities:
            # if there is a gpx file listed, find it and upload it
            act_type = str(row['Type'])
            gpx_file = row['GPX File']
            if ".gpx" in gpx_file:
                gpxfile = gpx_file
                strava_activity_type = activity_translator(act_type)

                if strava_activity_type is not None:
                    if upload_gpx(client, gpxfile, strava_activity_type, row['Notes']):
                        activity_counter = increment_activity_counter(activity_counter)
                else:
                    logger.info('Invalid activity type ' + act_type + ', skipping file ' + gpxfile)
                    skip_file(gpxfile)

            # if no gpx file, upload the data from the CSV
            else:
                activity_id = row['Activity Id']

                if activity_id not in completed_activities:
                    duration = row['Duration']
                    distance = distance_convertor(row[distance_key])
                    start_time = datetime.strptime(str(row['Date']), "%Y-%m-%d %H:%M:%S")
                    strava_activity_type = activity_translator(act_type)
                    notes = row['Notes']

                    if strava_activity_type is not None:
                        if create_activity(client, activity_id, duration, distance, start_time, strava_activity_type,
                                           notes):
                            completed_activities.append(activity_id)
                            activity_counter = increment_activity_counter(activity_counter)
                    else:
                        logger.info('Invalid activity type ' + act_type + ', skipping')

                else:
                    logger.warning('Activity [' + activity_id + '] should already be processed')

        logger.info("Complete! Created approximately [" + str(activity_counter) + "] activities.")


def set_up_env_vars():
    dotenv_path = os.path.join(os.path.dirname(__file__), '.env')
    load_dotenv(dotenv_path)


if __name__ == '__main__':
    main()
