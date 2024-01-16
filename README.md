# Runkeeper to Strava Uploader

Uses the Strava v3 API (documented [here](http://strava.github.io/api/)) to upload GPX and CSV activities exported from RunKeeper.

Borrows liberally from @anthonywu's [Strava API Experiment](https://github.com/anthonywu/strava-api-experiment) and @marthinsen's [Strava Upload](https://github.com/marthinsen/stravaupload) projects. Uses @hozn's [stravalib](https://github.com/hozn/stravalib) to interact with the Strava API. Thanks to all.

## Usage:
1. **Register Strava application**<br>First, you need to **register an application with the Strava API service.** Go to the [Strava API Management Page](https://www.strava.com/settings/api), and create a new application. Note the Client ID and Client Secret - you will need them later.
1. **Get data from Runkeeper**<br>Next, you need to **get your data from Runkeeper.** Go to the Settings page, and look for "Export Data" near the bottom. Define your time range, wait a minute or two, and then click download. Unzip the file - the directory should have .gpx files for all of your GPS-tracked runs, and two spreadsheets - "measurements.csv" and "cardio_activities.csv".
1. **Copy or move the Runkeeper data folder to the script directory**<br>The directory should be something like "runkeeper-data-export-1234567"). Copy or move it to `<script_root_dir>/runkeeper-data`.
1. **Install requirements**<br>Install the requirements - from any shell run `pip install -r requirements.txt`
1. **Get authorization from Strava**<br>Next, we need to **get an Authorization Token from Strava** for your Athlete account. <br>Make sure to add `CLIENT_ID=<your_client_id>` and `CLIENT_SECRET=<your_client_secret>` to the file `.env`, with the codes you pulled from the [Strava API Management Page](https://www.strava.com/settings/api) <br>Run the command `python strava_local_client.py get_write_token`. It should open a browser and ask you to log in to Strava. You should then be shown a code - copy this, and add `STRAVA_UPLOADER_TOKEN=<your_code>` to the `.env` file with the code you received.
1. **Upload to Strava**<br>Now we're ready to upload. Run the command `python uploader.py` and let it run!

**A few notes on how this works:**
- The script will crawl through the cardio activities csv file line by line, uploading each event.
- Right now it handles runs, rides, walks, swims, hikes and elliptical exercises. You can add more - be sure to grab the RunKeeper definition and the Strava definition and add to the `activity_translator` function.
- If there is a GPX file listed in the last column, it will look for that file in the directory. If there is no GPX file, it will manually upload using the distance and duration data listed in the spreadsheet.
- Strava's API [rate-limits you to 200 requests every 15 minutes](https://developers.strava.com/docs/rate-limits/), and 2000 daily requests.
The `uploader.py` script will automatically wait for 15 minutes when the upload count hits 199. This is probably too conservative - feel free to adjust. 
- It will move successfully uploaded GPX files to a sub-folder called archive.
- It will try to catch various errors, and ignore duplicate files.
- It will log everything in a file `strava-uploader.log`.

## Misc other notes:
- Do NOT modify or even save (without modification) the CSV from Excel. Even if you just open it and save it with no modification, Excel changes the date formatting which will break this script. If you do need to modify the CSV for some reason (e.g., mine had a run with a missing distance, not clear why), do it in Sublime or another text editor.
- I personally ran into a few errors of "malformed GPX files". You can try opening the file in a text editor and looking for issues - look for missing closure tags (e.g., `</trkseg>`) - that was the issue with one of my files. You could also try to use other solutions - some ideas that solved other issues [here](https://support.strava.com/hc/en-us/articles/216942247-How-to-Fix-GPX-File-Errors).
## Updates specific to this branch

You can use this script to upload a non-Runkeeper file in CSV format.  The current Runkeeper CSV file format includes the following columns: Activity Id, Date,Type, Route Name, Distance (mi), Duration, Average Pace, Average Speed (mph), Calories Burned, Climb (ft), Average Heart Rate (bpm), Friend's Tagged, Notes, GPX File.  If you wish to upload a non-Runkeeper file you have to create a cardioActivities.csv in this folder containing at least the following columns: Activity Id, Date, Type, Distance (mi), Duration.  The non-Runkeeper file must have matching column names to the Runkeeper original!  The GPX file if included should be a filename located in the same folder.

**Some specific information about formatting requirements:**
- The Activity Id is just an internal identifier that must be unique per activity.  You can use numbers, letters, whatever.
- Date format must be `YYYY-MM-DD HH:MM:SS`.
- Distance should be decimal formatted in miles.  This is converted to meters for Strava.
- Duration must be formatted as `MM:SS` even for times over 1 hour!  So 1 hour 5 minutes 3 seconds = 65:03.  This is converted to total duration in seconds in the `duration_calc` function if you want to use a different format.
- Some attribute errors are returned when running this script which seem to be related to missing pieces in the create_activity API call; however, the activity is still successfully uploaded if these errors are received.
- Pip install requirements only works with versions of pip < 9.0.3.  I did not update the `strava_local_client.py` file to work with the updated pip as it was very simple to downgrade pip to a workable version.
- When manually creating an activity (no GPX file), only the following information is saved: Date, Type, Distance (mi), and Duration.  The rest of the file row contents are ignored.

The primary changes from the original branch are updating the CSV file to be read as a dictionary, allowing Runkeeper to change their file format all they want as long as they keep the important column headers the same.  I did this because they added some new columns since the original script was written and it was difficult to figure out what the old file format was, and what updates needed to be made to accomodate the new format.

## Running tests
```py
cd tests
PYTHONPATH=..:$PYTHONPATH python -m unittest test_get_date_range
```
