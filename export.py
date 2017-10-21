#!/usr/bin/env python

# Export emoji in a Slack team as files
# https://github.com/smashwilson/slack-emojinator

from __future__ import print_function
from slacker import Slacker

import argparse
import os
import requests
import shutil


def _argparse():
    parser = argparse.ArgumentParser(
        description='Bulk import of emoji from a slack team'
    )
    parser.add_argument(
        '--directory', '-d',
        default=os.getenv('EMOJI_DIR'),
        help='Defaults to the $EMOJI_DIR environment variable.'
    )
    parser.add_argument(
        '--slack-api-token', '-s',
        default=os.getenv('SLACK_API_TOKEN'),
        help='Defaults to the $SLACK_API_TOKEN environment variable.'
    )
    args = parser.parse_args()
    return args

def main():
    args = _argparse()
    download_emoji(args.directory, args.slack_api_token)

def download_emoji(directory, slack_api_token):
    print("slack API token: %s" % slack_api_token)
    slack = Slacker(slack_api_token)
    if not os.path.exists(directory):
        os.makedirs(directory)
    emojis = slack.emoji.list()
    for emoji_name, emoji_url in emojis.body['emoji'].items():
        if "alias" not in emoji_url:
            file_extension = emoji_url.split(".")[-1]
            request = requests.get(emoji_url, stream=True)
            if request.status_code == 200:
                with open('%s/%s.%s' % (directory, emoji_name, file_extension), 'wb') as out_file:
                    shutil.copyfileobj(request.raw, out_file)
                del request

if __name__ == '__main__':
    main()
