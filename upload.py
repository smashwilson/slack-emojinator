# Upload files named on ARGV as Slack emoji.

import os
import sys
import requests

from bs4 import BeautifulSoup

team_name = os.getenv('SLACK_TEAM')
cookie = os.getenv('SLACK_COOKIE')

url = "https://{}.slack.com/customize/emoji".format(team_name)

for filename in sys.argv[1:]:
    print("Processing {}.".format(filename))

    emoji_name = os.path.splitext(os.path.basename(filename))[0]

    headers = {
        'Cookie': cookie,
    }

    # Fetch the form first, to generate a crumb.
    r = requests.get(url, headers=headers)
    r.raise_for_status()
    soup = BeautifulSoup(r.text)
    crumb = soup.find("input", attrs={"name": "crumb"})["value"]

    data = {
        'add': 1,
        'crumb': crumb,
        'name': emoji_name,
        'mode': 'data',
    }
    files = {'img': open(filename, 'rb')}
    r = requests.post(url, headers=headers, data=data, files=files, allow_redirects=False)
    r.raise_for_status()
    print("{} complete.".format(filename))
