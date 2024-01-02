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

FIFTEEN_MINUTES = 60 * 15
ONE_DAY = 60 * 60 * 24

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


class Conversion:
    @staticmethod
    def miles_to_meters(miles):
        return float(miles) * 1609.344

    @staticmethod
    def km_to_meters(km):
        return float(km) * 1000

    @staticmethod
    def duration_calc(duration):
        """
        Function to convert the HH:MM:SS in the Runkeeper CSV to seconds
        """
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

    @staticmethod
    def strava_day_conversion(hour_of_day):
        """
        designates part of day for name assignment, matching Strava convention for GPS activities
        """
        if 3 <= hour_of_day <= 11:
            return "Morning"
        elif 12 <= hour_of_day <= 4:
            return "Afternoon"
        elif 5 <= hour_of_day <= 7:
            return "Evening"

        return "Night"


class Setup:
    @staticmethod
    def set_up_env_vars():
        dotenv_path = os.path.join(os.path.dirname(__file__), '.env')
        load_dotenv(dotenv_path)

    @staticmethod
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


class FileUtils:
    @staticmethod
    def archive_file(file):
        if not os.path.isdir(archive_dir):
            os.mkdir(archive_dir)

        if os.path.isfile(archive_dir + '/' + file):
            logger.warning('[%s] already exists in [%s]', file, archive_dir)
            return

        logger.info('Backing up [%s] to [%s]', file, archive_dir)
        shutil.move(file, archive_dir)

    @staticmethod
    def skip_file(file):
        if not os.path.isdir(skip_dir):
            os.mkdir(skip_dir)

        logger.info('Skipping [%s], moving to [%s]', file, skip_dir)
        shutil.move(file, skip_dir)

    @staticmethod
    def get_cardio_file():
        if os.path.isfile(cardio_file):
            return open(cardio_file)

        logger.error('%s file cannot be found', cardio_file)
        exit(1)



def get_date_range(time, hour_buffer=12):
    """
    Get a small range of time. Note runkeeper does not maintain timezone
    in the CSV, so we must get about 12 hours earlier and later to account
    for potential miss due to UTC
    """
    if type(time) is not datetime:
        raise TypeError('time arg must be a datetime, not a %s' % type(time))

    return {
        'from': time + timedelta(hours=-1 * hour_buffer),
        'to': time + timedelta(hours=hour_buffer),
    }

class StravaClientUtils:
    @staticmethod
    def get_client():
        token = StravaClientUtils.get_strava_access_token()
        if not token:
            logger.error('Access token not found. Please set the env variable STRAVA_UPLOADER_TOKEN')
            exit(1)

        rate_limiter = RateLimiter()
        rate_limiter.rules.append(XRateLimitRule(
            {'short': {'usageFieldIndex': 0, 'usage': 0,
                       # 60s * 15 = 15 min
                       'limit': 100, 'time': FIFTEEN_MINUTES,
                       'lastExceeded': None, },
             'long': {'usageFieldIndex': 1, 'usage': 0,
                      # 60s * 60m * 24 = 1 day
                      'limit': 1000, 'time': ONE_DAY,
                      'lastExceeded': None}}))
        client = Client(rate_limiter=rate_limiter)
        client.access_token = token
        return client

    @staticmethod
    def get_strava_access_token():
        access_token = os.environ.get('STRAVA_UPLOADER_TOKEN')
        if access_token is not None:
            logger.info('Found access token')
            return access_token
        return None


class DistanceMode:
    def __init__(self, d_key, d_converter):
        self.key = d_key
        self.converter = d_converter

    def convert_distance(self, row):
        return self.converter(row[self.key])

    @staticmethod
    def from_csv_header(fieldnames):
        distance_converter = None
        distance_key = None

        if 'Distance (mi)' in fieldnames:
            distance_key = 'Distance (mi)'
            distance_converter = Conversion.miles_to_meters

        if 'Distance (km)' in fieldnames:
            distance_key = 'Distance (km)'
            distance_converter = Conversion.km_to_meters

        return DistanceMode(distance_key, distance_converter)


class RunkeeperToStravaImporter:
    def __init__(self):
        Setup.set_up_env_vars()
        Setup.set_up_logger()
        self.client = StravaClientUtils.get_client()
        self.activity_counter = 0
        self.completed_activities = set()
        self.distance_mode = None


    def run(self):
        cardio_file = FileUtils.get_cardio_file()

        logger.debug('Connecting to Strava')
        for i in range(2):
            try:
                athlete = self.client.get_athlete()
            except exc.RateLimitExceeded:
                if i > 0:
                    logger.error("Daily Rate limit exceeded - exiting program")
                    exit(1)
                logger.warning("Rate limit exceeded in connecting - Retrying strava connection in 15 minutes")
                time.sleep(900)
                continue
            break

        logger.info("Now authenticated for %s %s", athlete.firstname, athlete.lastname)

        # We open the cardioactivities CSV file and start reading through it
        with cardio_file as csvfile:
            activities = csv.DictReader(csvfile)
            self.distance_mode = DistanceMode.from_csv_header(activities.fieldnames)

            for row in activities:
                # if there is a gpx file listed, find it and upload it
                gpx_file = row['GPX File']
                if ".gpx" in gpx_file:
                    act_type = str(row['Type'])
                    strava_activity_type = RunkeeperToStravaImporter.activity_translator(act_type)

                    if strava_activity_type is not None:
                        if self.upload_gpx(gpx_file, strava_activity_type, row['Notes']):
                            self.activity_counter += 1
                    else:
                        logger.info('Invalid activity type %s, skipping file ', act_type, gpx_file)
                        FileUtils.skip_file(gpx_file)

                # if no gpx file, upload the data from the CSV
                else:
                    activity_id = row['Activity Id']

                    if activity_id not in self.completed_activities:
                        duration = row['Duration']
                        distance = self.distance_mode.convert_distance(row)
                        start_time = datetime.strptime(str(row['Date']), "%Y-%m-%d %H:%M:%S")
                        strava_activity_type = self.activity_translator(act_type)
                        notes = row['Notes']

                        if strava_activity_type is not None:
                            if self.create_activity(activity_id, duration, distance, start_time, strava_activity_type,
                                                    notes):
                                self.completed_activities.add(activity_id)
                                self.activity_counter += 1
                        else:
                            logger.info('Invalid activity type %s, skipping', act_type)

                    else:
                        logger.warning('Activity [%s] should already be processed', activity_id)
    
            logger.info("Complete! Created approximately [%s] activities.", self.activity_counter)

    def upload_gpx(self, gpxfile, strava_activity_type, notes):
        if not os.path.isfile(os.path.join(DATA_ROOT_DIR, gpxfile)):
            logger.warning("No file found for %s!", gpxfile)
            return False

        logger.debug("Uploading %s", gpxfile)

        for i in range(2):
            try:
                upload = self.client.upload_activity(
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

        logger.info("Upload succeeded. Waiting for response...")

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
                err_str = str(err)
                # deal with duplicate type of error, if duplicate then continue with next file, else stop
                if err_str.find('duplicate of activity'):
                    FileUtils.archive_file(gpxfile)
                    logger.debug("Duplicate File %s", gpxfile)
                    return True
                else:
                    logger.error("Another ActivityUploadFailed error: {}".format(err))
                    exit(1)
            except Exception as err:
                try:
                    logger.error("Exception raised: {}\nExiting...".format(err))
                except:
                    logger.error("Exception raised: An error that was not specified, sorry\nExiting...")
                exit(1)
            break

        logger.info("Uploaded %s - Activity id: %s", gpxfile, str(up_result.id))
        FileUtils.archive_file(gpxfile)
        return True

    def create_activity(self, activity_id, duration, distance, start_time, strava_activity_type, notes):
        # convert to total time in seconds
        duration = Conversion.duration_calc(duration)
        day_part = Conversion.strava_day_conversion(start_time.hour)

        activity_name = day_part + " " + strava_activity_type + " (Manual)"

        # Check to ensure the manual activity has not already been created
        if self.activity_exists(activity_name, start_time):
            logger.warning('Activity [%s] already created, skipping', activity_name)
            return

        logger.info("Manually uploading [%s]:[%s]", activity_id, activity_name)

        try:
            upload = self.client.create_activity(
                name=activity_name,
                start_date_local=start_time,
                elapsed_time=duration,
                distance=distance,
                description=notes,
                activity_type=strava_activity_type
            )

            logger.debug("Manually created %s", activity_id)
            return True

        except ConnectionError as err:
            logger.error("No Internet connection: {}".format(err))
            exit(1)

    def activity_exists(self, activity_name, start_time):
        date_range = get_date_range(start_time)

        logger.debug("Getting existing activities from [%s] to [%s]", date_range['from'].isoformat(), date_range[
            'to'].isoformat())

        activities = self.client.get_activities(
            before=date_range['to'],
            after=date_range['from']
        )

        for activity in activities:
            if activity.name == activity_name:
                return True

        return False

    @staticmethod
    def activity_translator(rk_type):
        """
        Translate RunKeeper's activity codes to Strava's
        """
        # Normalise to lower case
        rk_type = rk_type.lower()

        if rk_type not in activity_translations:
            return None

        return activity_translations[rk_type]


if __name__ == '__main__':
    importer = RunkeeperToStravaImporter()
    importer.run()
