#!/usr/bin/env python

# Export emoji in a Slack team as files
# https://github.com/smashwilson/slack-emojinator

import aiohttp
import argparse
import asyncio
import logging
import lxml.html
import os
import re
from collections import namedtuple

Emoji = namedtuple('Emoji', 'url name extension')

logging.basicConfig(level=logging.INFO, format="%(asctime)-15s\t%(message)s")
logger = logging.getLogger(__name__)

BASE_URL = 'https://{team_name}.slack.com'
EMOJI_ENDPOINT = '/customize/emoji'
EMOJI_API = '/api/emoji.adminList'

API_TOKEN_REGEX = r'.*(?:\"?api_token\"?):\s*\"([^"]+)\".*'
API_TOKEN_PATTERN = re.compile(API_TOKEN_REGEX)


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
    parser.add_argument(
        '--concurrent-requests', '-r',
        default=os.getenv('CONCURRENT_REQUESTS', 200),
        type=int,
        help='Maximum concurrent requests. Defaults to the $CONCURRENT_REQUESTS environment variable or 200.'
    )
    args = parser.parse_args()
    return args


def concurrent_http_get(max_concurrent: int, session: aiohttp.ClientSession):
    semaphore = asyncio.Semaphore(max_concurrent)

    async def http_get(emoji: Emoji):
        nonlocal semaphore
        with (await semaphore):
            response = await session.get(emoji.url)
            body = await response.content.read()
            await response.wait_for_close()
        return emoji, body

    return http_get


def save_to_file(response: bytes, emoji: Emoji, directory: str):
    logger.info(f"Downloaded {emoji.name.ljust(20)} from {emoji.url}")
    with open(os.path.join(directory, f"{emoji.name}.{emoji.extension}"), 'wb') as out:
        out.write(response)


def _async_session(auth_cookie) -> aiohttp.ClientSession:
    return aiohttp.ClientSession(headers={"Cookie": auth_cookie})


async def _fetch_api_token(session: aiohttp.ClientSession, base_url: str):
    # Fetch the form first, to get an api_token.
    emoji_url = base_url + EMOJI_ENDPOINT

    async with session.get(emoji_url) as base_page:

        if base_page.status != 200:
            raise Exception(f"Failed to fetch token from '{emoji_url}', status {base_page.status}")

        text = await base_page.text()
        tree = lxml.html.fromstring(text)

        all_scripts = tree.xpath('//script[@type=\'text/javascript\']/text()')

        for script in all_scripts:
            for line in script.splitlines():
                if 'api_token' in line:
                    # api_token: "xoxs-12345-abcdefg....",
                    # "api_token":"xoxs-12345-abcdefg....",
                    match_group = API_TOKEN_PATTERN.match(line.strip())

                    if not match_group:
                        raise Exception("Could not parse API token from remote data! Regex requires updating.")

                    return match_group.group(1)

    raise Exception("No api_token found in page")


async def _determine_all_emoji_urls(session: aiohttp.ClientSession, base_url: str, token: str):
    page = 1
    total_pages = None

    entries = list()

    while total_pages is None or page <= total_pages:

        data = {
            'token': token,
            'page': page,
            'count': 100
        }

        response = await session.post(base_url + EMOJI_API, data=data)

        logger.info(f"loaded {response.real_url} (page {page})")

        if response.status != 200:
            raise Exception(f"Failed to load emoji from {response.request_info.real_url} (status {response.status})")

        json = await response.json()

        for entry in json['emoji']:
            url = str(entry['url'])
            name = str(entry['name'])
            extension = str(url.split('.')[-1])

            # slack uses 0/1 to represent false/true in the API
            if entry['is_alias'] != 0:
                logger.info(f"Skipping emoji \"{name}\", is alias of \"{entry['alias_for']}\"")
                continue

            entries.append(Emoji(url, name, extension))

        if total_pages is None:
            total_pages = int(json['paging']['pages'])

        page += 1

    return entries


async def main():
    args = _argparse()

    if not os.path.exists(args.directory):
        os.makedirs(args.directory)

    base_url = BASE_URL.format(team_name=args.team_name)

    async with _async_session(args.cookie) as session:
        token = await _fetch_api_token(session, base_url)

        emojis = await _determine_all_emoji_urls(session, base_url, token)

        if len(emojis) == 0:
            raise Exception('Failed to find any custom emoji')

        function_http_get = concurrent_http_get(args.concurrent_requests, session)

        for future in asyncio.as_completed([function_http_get(emoji) for emoji in emojis]):
            emoji, data = await future
            save_to_file(data, emoji, args.directory)

        logger.info(f"Exported {len(emojis)} custom emoji to directory '{args.directory}'")


if __name__ == '__main__':
    loop = asyncio.get_event_loop()
    loop.run_until_complete(main())
