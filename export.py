#!/usr/bin/env python

# Export emoji in a Slack team as files
# https://github.com/smashwilson/slack-emojinator

from __future__ import print_function

import requests
import lxml.html

import argparse
import os
import shutil

from upload import _session


def _argparse():
    parser = argparse.ArgumentParser(
        description='Bulk import of emoji from a slack team'
    )
    parser.add_argument(
        'directory',
        help='Where do we store downloaded emoji?'
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
    args = parser.parse_args()
    return args


def main():
    args = _argparse()

    if not os.path.exists(args.directory):
        os.makedirs(args.directory)

    session = _session(args)
    resp = session.get(session.url)
    tree = lxml.html.fromstring(resp.text)
    urls = tree.xpath(r'//td[@headers="custom_emoji_image"]/span/@data-original')
    names = [u.split('/')[-2] for u in urls]

    for emoji_name, emoji_url in zip(names, urls):
        if "alias" not in emoji_url:  # this does not seem necessary ...
            file_extension = emoji_url.split(".")[-1]
            request = session.get(emoji_url, stream=True)
            if request.status_code == 200:
                filename = '%s/%s.%s' % (args.directory, emoji_name,
                                         file_extension)
                with open(filename, 'wb') as out_file:
                    shutil.copyfileobj(request.raw, out_file)
                del request

if __name__ == '__main__':
    main()
