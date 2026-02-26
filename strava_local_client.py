#!/usr/bin/env python

"""
Strava Development Sandbox.

Get your *Client ID* and *Client Secret* from https://www.strava.com/settings/api

Usage:
  strava_local_client.py get_write_token [options]
  strava_local_client.py find_settings

Options:
  -h --help      Show this screen.
  --port=<port>  Local port for OAuth client [default: 8000].
"""
import os

import stravalib
from dotenv import load_dotenv
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
    token = access_token['access_token']
    
    # Save/update token in .env file
    dotenv_path = os.path.join(os.path.dirname(__file__), '.env')
    try:
        with open(dotenv_path, 'r') as f:
            lines = f.readlines()
    except FileNotFoundError:
        lines = []
    
    # Replace existing token line or add new one
    token_found = False
    with open(dotenv_path, 'w') as f:
        for line in lines:
            if line.startswith('STRAVA_UPLOADER_TOKEN='):
                f.write(f"STRAVA_UPLOADER_TOKEN={token}\n")
                token_found = True
            else:
                f.write(line)
        if not token_found:
            f.write(f"STRAVA_UPLOADER_TOKEN={token}\n")
    
    print(f"\n✓ Access token obtained and saved to .env: {token[:20]}...")
    
    # Shutdown the Flask server after saving token
    import threading
    def shutdown():
        import time
        time.sleep(1)
        import os
        os.kill(os.getpid(), 15)
    threading.Thread(target=shutdown, daemon=True).start()
    
    # Return success message
    return f"""
    <html>
    <body style="font-family: Arial; text-align: center; margin-top: 50px;">
        <h1>✓ Authorization Successful!</h1>
        <p>Your access token has been saved to <code>.env</code></p>
        <p>You can close this window. The server will exit automatically.</p>
    </body>
    </html>
    """


if __name__ == '__main__':
    import docopt
    import subprocess
    import sys

    args = docopt.docopt(__doc__)

    if args['get_write_token']:
        dotenv_path = os.path.join(os.path.dirname(__file__), '.env')
        load_dotenv(dotenv_path)
        CLIENT_ID = int(os.environ.get("STRAVA_CLIENT_ID"))
        CLIENT_SECRET = os.environ.get("STRAVA_CLIENT_SECRET")

        auth_url = API_CLIENT.authorization_url(
            client_id=CLIENT_ID,
            redirect_uri='http://127.0.0.1:{port}/auth'.format(port=args['--port']),
            scope=['activity:write','activity:read_all','profile:read_all','profile:write','read_all'],
            state='from_cli'
            )
        if sys.platform == 'darwin':
            print('On OS X - launching {0} at default browser'.format(auth_url))
            subprocess.call(['open', auth_url])
        else:
            print('Go to {0} to authorize access: '.format(auth_url))
        
        print(f'\nListening for callback on http://127.0.0.1:{args["--port"]}/auth')
        print('After authorizing, the token will be saved to .env and the server will exit.\n')
        
        app.run(port=int(args['--port']), use_reloader=False)
    elif args['find_settings']:
        subprocess.call(['open', 'https://www.strava.com/settings/api'])
