#!/usr/bin/env python

# Upload files named on ARGV as Slack emoji.
# https://github.com/smashwilson/slack-emojinator

import os
import re
import sys
import requests

from bs4 import BeautifulSoup

team_name = os.getenv('SLACK_TEAM')
cookie = os.getenv('SLACK_COOKIE')

url = "https://{}.slack.com/customize/emoji".format(team_name)
headers = {
    'Cookie': cookie,
}


def main():
    existing_emojis = get_current_emoji_list()
    uploaded = 0
    skipped = 0
    for filename in sys.argv[1:]:
        print("Processing {}.".format(filename))
        emoji_name = os.path.splitext(os.path.basename(filename))[0]
        if emoji_name in existing_emojis:
            print("Skipping {}. Emoji already exists").format(emoji_name)
            skipped += 1
        else:
            upload_emoji(emoji_name, filename)
            print("{} upload complete.".format(filename))
            uploaded += 1
    print('\nUploaded {} emojis. ({} already existed)'.format(uploaded, skipped))


def get_current_emoji_list():
    r = requests.get(url, headers=headers)
    r.raise_for_status()
    x = re.findall("data-emoji-name=\"(.*)\"", r.text)
    return x


def upload_emoji(emoji_name, filename):
    # Fetch the form first, to generate a crumb.
    r = requests.get(url, headers=headers)
    r.raise_for_status()
    soup = BeautifulSoup(r.text, "html.parser")
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
    # Slack returns 200 OK even if upload fails, so check for status of 'alert_error' info box
    if 'alert_error' in r.content:
        soup = BeautifulSoup(r.text, "html.parser")
        crumb = soup.find("p", attrs={"class": "alert_error"})
        raise Exception("Error with uploading %s: %s" % (emoji_name, crumb.text))

if __name__ == '__main__':
    main()
