#!/usr/bin/env python

# Upload files named on ARGV as Slack emoji.
# https://github.com/smashwilson/slack-emojinator

from __future__ import print_function

import argparse
import os
import re
import requests

from bs4 import BeautifulSoup

try:
    raw_input
except NameError:
    raw_input = input

URL = "https://{team_name}.slack.com/customize/emoji"


def _session(args):
    assert args.cookie, "Cookie required"
    assert args.team_name, "Team name required"
    session = requests.session()
    session.headers = {'Cookie': args.cookie}
    session.url = URL.format(team_name=args.team_name)
    return session


def _argparse():
    parser = argparse.ArgumentParser(
        description='Bulk upload emoji to slack'
    )
    parser.add_argument(
        '--team-name', '-t',
        default=os.getenv('SLACK_TEAM'),
        help='Defaults to the $SLACK_TEAM environment variable.'
    )
    parser.add_argument(
        '--cookie', '-c',
        default=os.getenv('SLACK_COOKIE'),
        help='Defaults to the $SLACK_COOKIE environment variable.'
    )
    parser.add_argument(
        '--prefix', '-p',
        default=os.getenv('EMOJI_NAME_PREFIX', ''),
        help='Prefix to add to genereted emoji name. '
        'Defaults to the $EMOJI_NAME_PREFIX environment variable.'
    )
    parser.add_argument(
        '--suffix', '-s',
        default=os.getenv('EMOJI_NAME_SUFFIX', ''),
        help='Suffix to add to generated emoji name. '
        'Defaults to the $EMOJI_NAME_SUFFIX environment variable.'
    )
    parser.add_argument(
        'slackmoji_files',
        nargs='+',
        help=('Paths to slackmoji, e.g. if you '
              'unzipped http://cultofthepartyparrot.com/parrots.zip '
              'in your home dir, then use ~/parrots/*'),
    )
    args = parser.parse_args()
    if not args.team_name:
        args.team_name = raw_input('Please enter the team name: ').strip()
    if not args.cookie:
        args.cookie = raw_input('Please enter the "emoji" cookie: ').strip()
    return args


def main():
    args = _argparse()
    session = _session(args)
    existing_emojis = get_current_emoji_list(session)
    uploaded = 0
    skipped = 0
    for filename in args.slackmoji_files:
        print("Processing {}.".format(filename))
        emoji_name = '{}{}{}'.format(
            args.prefix.strip(),
            os.path.splitext(os.path.basename(filename))[0],
            args.suffix.strip()
        )
        if emoji_name in existing_emojis:
            print("Skipping {}. Emoji already exists".format(emoji_name))
            skipped += 1
        else:
            upload_emoji(session, emoji_name, filename)
            print("{} upload complete.".format(filename))
            uploaded += 1
    print('\nUploaded {} emojis. ({} already existed)'.format(uploaded, skipped))


def get_current_emoji_list(session):
    r = session.get(session.url)
    r.raise_for_status()
    x = re.findall("data-emoji-name=\"(.*?)\"", r.text)
    return x


def upload_emoji(session, emoji_name, filename):
    # Fetch the form first, to generate a crumb.
    r = session.get(session.url)
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
    r = session.post(session.url, data=data, files=files, allow_redirects=False)
    r.raise_for_status()
    # Slack returns 200 OK even if upload fails, so check for status of 'alert_error' info box
    if b'alert_error' in r.content:
        soup = BeautifulSoup(r.text, "html.parser")
        crumb = soup.find("p", attrs={"class": "alert_error"})
        print("Error with uploading %s: %s" % (emoji_name, crumb.text))


if __name__ == '__main__':
    main()
