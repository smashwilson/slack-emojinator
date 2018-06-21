#!/usr/bin/env python

# Export emoji in a Slack team as files
# https://github.com/smashwilson/slack-emojinator

import aiohttp
import argparse
import asyncio
import logging
import lxml.html
import os
from typing import List

logging.basicConfig(level=logging.INFO, format="%(asctime)-15s\t%(message)s")
logger = logging.getLogger(__name__)

BASE_URL = 'https://{team_name}.slack.com'
EMOJI_ENDPOINT = '/customize/emoji'


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

    async def http_get(url, name):
        nonlocal semaphore
        with (await semaphore):
            response = await session.get(url)
            body = await response.content.read()
            await response.wait_for_close()
        return body, name, url

    return http_get


def save_to_file(response, name: str, url: str, directory: str):
    logger.info(f"Got {name.ljust(15)} {url}")
    ext = url.split(".")[-1]
    with open(os.path.join(directory, f"{name}.{ext}"), 'wb') as out:
        out.write(response)


def parse_emoji_from_page(text: str) -> List[str]:
    '''Given the text of an HTML page, retrieve a list of (relative) URLs to emoji.
    :param text Raw HTML.
    :return ['/path/to/first.png', '/path/to/second.png', ...]'''
    tree = lxml.html.fromstring(text)
    urls = tree.xpath(r'//td[@headers="custom_emoji_image"]/span/@data-original')
    return urls


def _async_session(auth_cookie):
    return aiohttp.ClientSession(headers={"Cookie": auth_cookie})


async def main():
    args = _argparse()

    if not os.path.exists(args.directory):
        os.makedirs(args.directory)

    base_url = BASE_URL.format(team_name=args.team_name)
    emoji_url = base_url + EMOJI_ENDPOINT

    async with _async_session(args.cookie) as session:
        logger.info(f"Getting {emoji_url}")

        async with session.get(emoji_url) as base_page_q:
            if base_page_q.status != 200:
                logger.error(f"Failed to retrieve emoji list ({base_page_q.status})")
                return
            text = await base_page_q.text()
            tree = lxml.html.fromstring(text)

            emoji_urls = []
            emoji_urls.extend(parse_emoji_from_page(text))
            other_emoji_pages = [f"{base_url}{p}" for p in
                                 tree.xpath(r'//div[@class="pagination pagination-centered"]'
                                            r'/ul/li/a[.!="Next"]/@href[.!="#"]')
                                 if p != EMOJI_ENDPOINT]
            logger.info(f"Getting other emoji from: {other_emoji_pages}")
            for emoji_page in other_emoji_pages:
                async with session.get(f"{emoji_page}") as page:
                    text = await page.text()
                    emoji_urls.extend(parse_emoji_from_page(text))

            emoji_names = [u.split('/')[-2] for u in emoji_urls]

            logger.info(f"Parsed {len(emoji_names)} emojis")
            assert len(emoji_names) > 0

        http_get = concurrent_http_get(args.concurrent_requests, session)
        tasks = [http_get(emoji_url, emoji_name) for emoji_name, emoji_url in zip(emoji_names, emoji_urls)
                 if "alias" not in emoji_url]
        for future in asyncio.as_completed(tasks):
            data, name, url = await future
            save_to_file(data, name, url, args.directory)


if __name__ == '__main__':
    loop = asyncio.get_event_loop()
    loop.run_until_complete(main())
