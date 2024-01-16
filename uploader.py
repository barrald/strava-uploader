#!/usr/bin/env python

import os
import uuid

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

DRY_RUN_PREFIX = "[DRY RUN] "

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

output_dir = os.path.join(DATA_ROOT_DIR, "uploader-output")
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

DRY_RUN = False


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
    def setup_dirs():
        if not os.path.isdir(output_dir):
            os.mkdir(output_dir)
        if not os.path.isdir(archive_dir):
            os.mkdir(archive_dir)
        if not os.path.isdir(skip_dir):
            os.mkdir(skip_dir)

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
    def archive_file(file, dry_run=False):
        if dry_run:
            logger.info((DRY_RUN_PREFIX + "Archiving file, moving '%s' to dir '%s'"), file, archive_dir)
            return

        if os.path.isfile(archive_dir + '/' + file):
            logger.warning('[%s] already exists in [%s]', file, archive_dir)
            return

        logger.info('Backing up [%s] to [%s]', file, archive_dir)
        shutil.move(os.path.join(DATA_ROOT_DIR, file), archive_dir)

    @staticmethod
    def skip_file(file, dry_run=False):
        if dry_run:
            logger.info(DRY_RUN_PREFIX + "Skipping file, moving '%s' to dir '%s'", file, skip_dir)
            return

        logger.info('Skipping [%s], moving to [%s]', file, skip_dir)
        shutil.move(os.path.join(DATA_ROOT_DIR, file), skip_dir)

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
            logger.error('Access token not found in .env file. '
                         'Please set STRAVA_UPLOADER_TOKEN to a valid value in the file.')
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


def rate_limited(retries=2, sleep=900):
    def deco_retry(f):
        def f_retry(*args, **kwargs):
            for i in range(retries):
                try:
                    if hasattr(f, "__func__"):
                        # staticmethod or classmethod
                        return f.__func__(*args, **kwargs)
                    else:
                        return f(*args, **kwargs)
                except exc.RateLimitExceeded:
                    if i > 0:
                        logger.error("Daily Rate limit exceeded - exiting program")
                        exit(1)
                    logger.warning("Rate limit exceeded in connecting - "
                                   "Retrying strava connection in %d seconds", sleep)
                    time.sleep(sleep)
        return f_retry  # true decorator
    return deco_retry


class FakeUpload:
    def wait(self):
        class Object(object):
            pass

        obj = Object()
        obj.id = uuid.uuid4()
        return obj


class FakeAthlete:
    @property
    def firstname(self):
        return "John"

    @property
    def lastname(self):
        return "Doe"


class RunkeeperToStravaImporter:
    def __init__(self):
        Setup.setup_dirs()
        Setup.set_up_env_vars()
        Setup.set_up_logger()
        self.client = StravaClientUtils.get_client()
        self.activity_counter = 0
        self.completed_activities = set()
        self.distance_mode = None
        self.dry_run = DRY_RUN

    @rate_limited()
    def _get_athlete(self):
        if self.dry_run:
            logger.info(DRY_RUN_PREFIX + "Getting athlete")
            return FakeAthlete()
        return self.client.get_athlete()

    @rate_limited()
    def _upload_activity(self, gpx_file, notes, activity_type):
        if self.dry_run:
            logger.info(DRY_RUN_PREFIX + "Uploading activity from GPX file: %s, activity type: %s, notes: %s",
                        gpx_file, activity_type, notes)
            return FakeUpload()

        upload = self.client.upload_activity(
            activity_file=open(os.path.join(DATA_ROOT_DIR, gpx_file), 'r'),
            data_type='gpx',
            private=False,
            description=notes,
            activity_type=activity_type
        )
        return upload

    def _create_activity(self, activity_id, activity_name, activity_type, distance, duration, notes, start_time):
        if self.dry_run:
            logger.info(DRY_RUN_PREFIX + "Creating activity. ID: %s, name: %s, type: %s, distance: %s, "
                                         "duration: %s, notes: %s, start time: %s",
                        activity_id, activity_name, activity_type, distance, duration, notes, start_time)
            return object()

        self.client.create_activity(
            name=activity_name,
            start_date_local=start_time,
            elapsed_time=duration,
            distance=distance,
            description=notes,
            activity_type=activity_type
        )
        logger.debug("Manually created %s", activity_id)

    @rate_limited()
    def _wait_for_upload(self, upload):
        up_result = upload.wait()
        return up_result

    def run(self):
        logger.debug('Connecting to Strava')
        athlete = self._get_athlete()
        logger.info("Now authenticated for %s %s", athlete.firstname, athlete.lastname)

        # We open the cardioactivities CSV file and start reading through it
        cardio_file = FileUtils.get_cardio_file()
        with cardio_file as csvfile:
            activities = csv.DictReader(csvfile)
            self.distance_mode = DistanceMode.from_csv_header(activities.fieldnames)

            for row in activities:
                try:
                    # if there is a gpx file listed, find it and upload it
                    gpx_file = row['GPX File']
                    if ".gpx" in gpx_file:
                        raw_activity_type = str(row['Type'])
                        activity_type = RunkeeperToStravaImporter.activity_translator(raw_activity_type)

                        if activity_type is not None:
                            if self.upload_gpx(gpx_file, activity_type, row['Notes']):
                                self.activity_counter += 1
                        else:
                            logger.error('Invalid activity type %s, skipping file %s', raw_activity_type, gpx_file)
                            FileUtils.skip_file(gpx_file, dry_run=self.dry_run)

                    # if no gpx file, upload the data from the CSV
                    else:
                        self._create_activity_from_csv(raw_activity_type, row)
                except exc.Fault as e:
                    if e.code == 409:
                        logger.warning('Caught a 409 Client Error: Conflict. This likely means that you have a conflicting activity in Strava in this time block.')
                    else:
                        logger.warning(f'Caught a Client Error: {e}')

            logger.info("Complete! Created %d activities.", self.activity_counter)

    def _create_activity_from_csv(self, act_type, row):
        activity_id = row['Activity Id']
        if activity_id not in self.completed_activities:
            duration = row['Duration']
            notes = row['Notes']
            distance = self.distance_mode.convert_distance(row)
            start_time = datetime.strptime(str(row['Date']), "%Y-%m-%d %H:%M:%S")
            activity_type = self.activity_translator(act_type)

            if activity_type is not None:
                if self.create_activity(activity_id, duration, distance, start_time, activity_type, notes):
                    self.completed_activities.add(activity_id)
                    self.activity_counter += 1
            else:
                logger.error('Invalid activity type %s, skipping', act_type)

        else:
            logger.warning('Activity \'%s\' should already be processed', activity_id)

    def upload_gpx(self, gpxfile, strava_activity_type, notes):
        if not os.path.isfile(os.path.join(DATA_ROOT_DIR, gpxfile)):
            logger.warning("No file found for %s!", gpxfile)
            return False

        try:
            upload = self._upload(gpxfile, notes, strava_activity_type)
            up_result = self._wait_for_upload(upload)
        except exc.ActivityUploadFailed as err:
            # deal with duplicate type of error, if duplicate then continue with next file, stop otherwise
            if str(err).find('duplicate of activity'):
                FileUtils.archive_file(gpxfile, dry_run=self.dry_run)
                logger.debug("Duplicate File %s", gpxfile)
                return True
            else:
                logger.error("Another ActivityUploadFailed error: {}".format(err))
                exit(1)
        except Exception as err:
            try:
                logger.error("Exception raised: {}. Exiting...".format(err))
            except:
                logger.error("Unexpected exception. Exiting...")
            exit(1)

        logger.info("Uploaded %s - Activity id: %s", gpxfile, str(up_result.id))
        FileUtils.archive_file(gpxfile, dry_run=self.dry_run)
        return True

    def _upload(self, gpxfile, notes, strava_activity_type):
        prefix = DRY_RUN_PREFIX if self.dry_run else ""
        logger.info(prefix + "Uploading %s", gpxfile)
        upload = self._upload_activity(gpxfile, notes, strava_activity_type)
        logger.info(prefix + "Upload succeeded. Waiting for response...")
        return upload

    def create_activity(self, activity_id, duration, distance, start_time, activity_type, notes):
        # convert to total time in seconds
        duration = Conversion.duration_calc(duration)
        day_part = Conversion.strava_day_conversion(start_time.hour)
        activity_name = day_part + " " + activity_type + " (Manual)"

        # Check to ensure the manual activity has not already been created
        if self.activity_exists(activity_name, start_time):
            logger.warning('Activity [%s] already created, skipping', activity_name)
            return

        prefix = DRY_RUN_PREFIX if self.dry_run else ""
        logger.info(prefix + "Manually uploading [%s]:[%s]", activity_id, activity_name)

        try:
            self._create_activity(activity_id, activity_name, activity_type, distance, duration, notes, start_time)
            return True
        except ConnectionError as err:
            logger.error("No Internet connection: {}".format(err))
            exit(1)

    def activity_exists(self, activity_name, start_time):
        date_range = get_date_range(start_time)
        date_from = date_range['from'].isoformat()
        date_to = date_range['to'].isoformat()

        if self.dry_run:
            logger.info(DRY_RUN_PREFIX + "Getting existing activities from [%s] to [%s]", date_from, date_to)
            return False

        logger.debug("Getting existing activities from [%s] to [%s]", date_from, date_to)
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
