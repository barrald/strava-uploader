#!/usr/bin/env python

"""
Strava Development Sandbox.

Get your *Client ID* and *Client Secret* from https://www.strava.com/settings/api

Usage:
  strava_local_client.py get_write_token <client_id> <client_secret> [options]
  strava_local_client.py find_settings

Options:
  -h --help      Show this screen.
  --port=<port>  Local port for OAuth client [default: 8000].
"""

import stravalib
from flask import Flask, request

app = Flask(__name__)

API_CLIENT = stravalib.Client()

# set these in __main__
CLIENT_ID = None
CLIENT_SECRET = None

@app.route("/auth")
def auth_callback():
    code = request.args.get('code')
    access_token = API_CLIENT.exchange_code_for_token(
        client_id=CLIENT_ID,
        client_secret=CLIENT_SECRET,
        code=code
        )
    print(access_token)
    return "hi"


if __name__ == '__main__':
    import docopt
    import subprocess
    import sys

    args = docopt.docopt(__doc__)

    if args['get_write_token']:
        CLIENT_ID, CLIENT_SECRET = args['<client_id>'], args['<client_secret>']
        auth_url = API_CLIENT.authorization_url(
            client_id=args['<client_id>'],
            redirect_uri='http://127.0.0.1:{port}/auth'.format(port=args['--port']),
            scope='activity:write',
            state='from_cli'
            )
        if sys.platform == 'darwin':
            print('On OS X - launching {0} at default browser'.format(auth_url))
            subprocess.call(['open', auth_url])
        else:
            print('Go to {0} to authorize access: '.format(auth_url))
        app.run(port=int(args['--port']))
    elif args['find_settings']:
        subprocess.call(['open', 'https://www.strava.com/settings/api'])
