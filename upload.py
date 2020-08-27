#!/usr/bin/env python

# Upload files named on ARGV as Slack emoji.
# https://github.com/smashwilson/slack-emojinator

from __future__ import print_function

import argparse
import os
import re
from time import sleep

from bs4 import BeautifulSoup

import requests

try:
    raw_input
except NameError:
    raw_input = input

URL_CUSTOMIZE = "https://{team_name}.slack.com/customize/emoji"
URL_ADD = "https://{team_name}.slack.com/api/emoji.add"
URL_LIST = "https://{team_name}.slack.com/api/emoji.adminList"

API_TOKEN_REGEX = r'.*(?:\"?api_token\"?):\s*\"([^"]+)\".*'
API_TOKEN_PATTERN = re.compile(API_TOKEN_REGEX)


class ParseError(Exception):
    pass


def _session(args):
    assert args.cookie, "Cookie required"
    assert args.team_name, "Team name required"
    session = requests.session()
    session.headers = {'Cookie': args.cookie}
    session.url_customize = URL_CUSTOMIZE.format(team_name=args.team_name)
    session.url_add = URL_ADD.format(team_name=args.team_name)
    session.url_list = URL_LIST.format(team_name=args.team_name)
    session.api_token = _fetch_api_token(session)
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


def _fetch_api_token(session):
    # Fetch the form first, to get an api_token.
    r = session.get(session.url_customize)
    r.raise_for_status()
    soup = BeautifulSoup(r.text, "html.parser")

    all_script = soup.findAll("script")
    for script in all_script:
        for line in script.text.splitlines():
            if 'api_token' in line:
                # api_token: "xoxs-12345-abcdefg....",
                # "api_token":"xoxs-12345-abcdefg....",
                match_group = API_TOKEN_PATTERN.match(line.strip())
                if not match_group:
                    raise ParseError(
                        "Could not parse API token from remote data! "
                        "Regex requires updating."
                    )

                return match_group.group(1)

    print("No api_token found in page. Search your https://<teamname>.slack.com/customize/emoji "
          "page source for \"api_token\" and enter its value manually.")
    return raw_input(
        'Please enter the api_token ("xoxs-12345-abcdefg....") from the page: ').strip()


def main():
    args = _argparse()
    session = _session(args)
    existing_emojis = get_current_emoji_list(session)
    uploaded = 0
    skipped = 0

    def process_file(filename):
        nonlocal skipped
        nonlocal uploaded
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

    for slackmoji_file in args.slackmoji_files:
        if os.path.isdir(slackmoji_file):
            for file in os.listdir(slackmoji_file):
                filename = os.path.join(slackmoji_file, file)
                process_file(filename)
        else:
            process_file(slackmoji_file)
    print('\nUploaded {} emojis. ({} already existed)'.format(uploaded, skipped))


def get_current_emoji_list(session):
    page = 1
    result = []
    while True:
        data = {
            'query': '',
            'page': page,
            'count': 1000,
            'token': session.api_token
        }
        resp = session.post(session.url_list, data=data)
        resp.raise_for_status()
        response_json = resp.json()

        result.extend(map(lambda e: e["name"], response_json["emoji"]))
        if page >= response_json["paging"]["pages"]:
            break

        page = page + 1
    return result


def upload_emoji(session, emoji_name, filename):
    data = {
        'mode': 'data',
        'name': emoji_name,
        'token': session.api_token
    }

    while True:
        with open(filename, 'rb') as f:
            files = {'image': f}
            resp = session.post(session.url_add, data=data, files=files, allow_redirects=False)

            if resp.status_code == 429:
                wait = int(resp.headers.get('retry-after', 1))
                print("429 Too Many Requests!, sleeping for %d seconds" % wait)
                sleep(wait)
                continue

        resp.raise_for_status()

        # Slack returns 200 OK even if upload fails, so check for status.
        response_json = resp.json()
        if not response_json['ok']:
            print("Error with uploading %s: %s" % (emoji_name, response_json))

        break


if __name__ == '__main__':
    main()
