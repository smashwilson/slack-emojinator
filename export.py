#!/usr/bin/env python

# Export emoji in a Slack team as files
# https://github.com/smashwilson/slack-emojinator

import requests
import lxml.html

import argparse
import os
import shutil
import asyncio, aiohttp
import logging

from upload import _session

logging.basicConfig(level=logging.INFO, format="%(asctime)-15s\t%(message)s")
logger = logging.getLogger(__name__)

URL = "https://{team_name}.slack.com/customize/emoji"


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
        help='Maximum concurrent requests. Defaults to the $CONCURRENT_REQUESTS environment variable or 200.'
    )
    args = parser.parse_args()
    return args

def concurrent_http_get(num_chunks: int, session: aiohttp.ClientSession):
    semaphore = asyncio.Semaphore(num_chunks)

    async def http_get(url, name):
        nonlocal semaphore
        with (await semaphore):
            response = await session.get(url)
            body = await response.content.read()
            await response.wait_for_close()
        return body, name, url
    return http_get

def handle_response(response, name: str, url: str, directory: str):
    logger.info(f"Got {name.ljust(15)} {url}")
    ext = url.split(".")[-1]
    with open(os.path.join(directory, f"{name}.{ext}"), 'wb') as out:
        out.write(response)

def _async_session(auth_cookie):
    return aiohttp.ClientSession(headers={"Cookie": auth_cookie})

async def main():
    args = _argparse()

    if not os.path.exists(args.directory):
        os.makedirs(args.directory)

    async with _async_session(args.cookie) as session:
        endpoint = URL.format(team_name=args.team_name)
        logger.info(f"Getting {endpoint}")
        resp = await session.get(endpoint)
        async with resp:
            if resp.status != 200:
                logger.error(f"Failed to retrieve emoji list ({resp.status})")
                return
            text = await resp.text()
            tree = lxml.html.fromstring(text)
            urls = tree.xpath(r'//td[@headers="custom_emoji_image"]/span/@data-original')
            names = [u.split('/')[-2] for u in urls]

            logger.info(f"Parsed {len(names)} emojis")
            assert len(names) > 0

        http_get = concurrent_http_get(args.concurrent_requests, session)
        tasks = [http_get(emoji_url, emoji_name) for emoji_name, emoji_url in zip(names, urls) if "alias" not in emoji_url]
        for future in asyncio.as_completed(tasks):
            data, name, url = await future
            handle_response(data, name, url, args.directory)


if __name__ == '__main__':
    loop = asyncio.get_event_loop()
    loop.run_until_complete(main())

