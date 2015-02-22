# Upload files named on ARGV as Slack emoji.

import os
import sys
import requests

team_name = os.getenv('SLACK_TEAM')
cookie = os.getenv('SLACK_COOKIE')
crumb = os.getenv('SLACK_CRUMB')

url = "https://{}.slack.com/customize/emoji".format(team_name)

for filename in sys.argv[1:]:
    print("Processing {}.".format(filename))

    emoji_name = os.path.basename(filename)

    headers = {
        'Cookie': cookie,
    }
    data = {
        'add': 1,
        'crumb': crumb,
        'name': emoji_name,
        'mode': 'data',
    }
    files = {'img': open(filename, 'rb')}
    r = requests.post(url, headers=headers, data=data, files=files, allow_redirects=False)
    r.raise_for_status()
