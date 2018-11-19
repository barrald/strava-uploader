# CSV to Strava Uploader

## Usage:
** Getting your data from logarun **
TODO: write these instructions. tldr - get xml file from logarun front page, then convert xml to csv (I will upload a script I wrote for this)

** Getting your CSV to Strava **
1. First, you need to **register an application with the Strava API service.** Go to the [Strava API Management Page](https://www.strava.com/settings/api), and create a new application. Note the Client ID and Client Secret - you will need them later.
2. Clone this project. Put the logarun data in the same folder as the project on your computer.
3. Open Terminal on Mac, and go this folder (use cd).
3. Type `pip install -r requirements.txt` into terminal and hit enter to run the command. 
5. Next, we need to **get an Authorization Token from Strava** for your Athlete account. Now in your terminal, run the command `python strava_local_client.py get_write_token <client_id> <client_secret>`, where you replace `<client_id>` and `<client_secret>` with the codes you pulled from the [Strava API Management Page](https://www.strava.com/settings/api). It should open a browser and ask you to log in to Strava. You should then be shown a code in the Terminal - copy this, and paste it in the `uploader.py` file as the `access_token` variable.
6. Now it's ready to upload. Run `python uploader.py`, and let it run!
TODO - add simple prompts and a launcher so people don't have to use the terminal.

**Note:**
Strava only allows 600 logs every 15 minutes, so the program will space them out.

## References
Uses the Strava v3 API (documented [here](http://strava.github.io/api/)) to upload CSV activities exported from logarun/flotrack.

Borrows liberally from @anthonywu's [Strava API Experiment](https://github.com/anthonywu/strava-api-experiment) and @marthinsen's [Strava Upload](https://github.com/marthinsen/stravaupload) projects. Uses @hozn's [stravalib](https://github.com/hozn/stravalib) to interact with the Strava API. Thanks to all.

XML parsing from https://www.geeksforgeeks.org/xml-parsing-python/
