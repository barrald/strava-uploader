# Runkeeper to Strava Uploader

Uses the Strava v3 API (documented [here](http://strava.github.io/api/)) to upload GPX and CSV activities exported from RunKeeper.

Borrows liberally from @anthonywu's [Strava API Experiment](https://github.com/anthonywu/strava-api-experiment) and @marthinsen's [Strava Upload](https://github.com/marthinsen/stravaupload) projects. Uses @hozn's [stravalib](https://github.com/hozn/stravalib) to interact with the Strava API. Thanks to all.

## Usage:
1. First, you need to **register an application with the Strava API service.** Go to the [Strava API Management Page](https://www.strava.com/settings/api), and create a new application. Note the Client ID and Client Secret - you will need them later.
2. Next, you need to **get your data from Runkeeper.** Go to the Settings page, and look for "Export Data" near the bottom. Define your time range, wait a minute or two, and then click download. Unzip the file - the directory should have .gpx files for all of your GPS-tracked runs, and two spreadsheets - "measurements.csv" and "cardio_activities.csv". 
3. Open a Terminal window and `cd` to the data directory (should be something like "runkeeper-data-export-1234567")
4. Install the requirements - `pip install -r requirements.txt`
5. Next, we need to **get an Authorization Token from Strava** for your Athlete account. Run the command `python strava_local_client.py get_write_token <client_id> <client_secret>`, where you replace `<client_id>` and `<client_secret>` with the codes you pulled from the [Strava API Management Page](https://www.strava.com/settings/api). It should open a browser and ask you to log in to Strava. You should then be shown a code - copy this, and paste it in the `uploader.py` file as the `access_token` variable.
6. Now we're ready to upload. Run `python uploader.py`, and let it run!

**A few notes on how this works:**
- The script will crawl through the cardio activities csv file line for line, uploading each event.
- Right now it handles runs, rides, walks, swims, hikes and elliptical exercises. You can add more - be sure to grab the RunKeeper definition and the Strava definition and add to the `activity_translator` function.
- If there is a GPX file listed in the last column, it will look for that file in the directory. If there is no GPX file, it will manually upload using the distance and duration data listed in the spreadsheet.
- It will move successfully uploaded GPX files to a sub-folder called archive.
- It will try to catch various errors, and ignore duplicate files.
- It will log everything in a file `log.txt`.

## Misc other notes:
- Strava's API [rate-limits you to 600 requests every 15 minutes](http://strava.github.io/api/#rate-limiting). If you have more than 600 activities, it will likely time out - 
- Do NOT modify or even save (without modification) the CSV from Excel. Even if you just open it and save it with no modification, Excel changes the date formatting which will break this script. If you do need to modify the CSV for some reason (e.g., mine had a run with a missing distance, not clear why), do it in Sublime or another text editor.
- I personally ran into a few errors of "malformed GPX files". You can try opening the file in a text editor and looking for issues - look for missing closure tags (e.g., `</trkseg>`) - that was the issue with one of my files. You could also try to use other solutions - some ideas that solved other issues [here](https://support.strava.com/hc/en-us/articles/216942247-How-to-Fix-GPX-File-Errors).