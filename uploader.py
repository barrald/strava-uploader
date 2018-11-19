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
        print(message)

    # Opening the connection to Strava
    logger("Connecting to Strava")
    client = Client()

    # You need to run the strava_local_client.py script - with your application's ID and secret - to generate the access token.
    access_token = "442a2a9e4db1f7008fc96789e18c16e05875305d" # replace this with your token
    client.access_token = access_token
    athlete = client.get_athlete()
    logger("Now authenticated for " + athlete.firstname + " " + athlete.lastname)
           
    # We open the cardioactivities CSV file and start reading through it
    with open('logarun.csv') as csvfile:
        activities = csv.reader(csvfile)
        activity_counter = 0
        for row in activities:
            if row[2] == 'time':
                continue
            if activity_counter >= 500:
                logger("Upload count at 500 - pausing uploads for 15 minutes to avoid rate-limit")
                time.sleep(900)
                activity_counter = 0
            if row[0] not in log:
                logger("Manually uploading " + row[0])
                duration = int(float(row[2])) # time in seconds
                dist = float(row[1])*1609.344 # convert miles to meters
                starttime = row[0]
                strava_activity_type = "Run"


                try:
                    upload = client.create_activity(
                        name = "logarun Run",
                        start_date_local = starttime,
                        elapsed_time = duration,
                        distance = dist,
                        description = "Shoe used: " + row[3],
                        activity_type = strava_activity_type
                    )
                    
                    logger("Manually created " + row[0])
                    activity_counter += 1

                except ConnectionError as err:
                    logger("No Internet connection: {}".format(err))
                    exit(1)

        logger("Complete! Logged " + str(activity_counter) + " activities.")

if __name__ == '__main__':
    main()

