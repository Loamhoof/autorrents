#!/usr/bin/python3

import collections
import datetime
import logging
import os
import re
import shelve
import subprocess
import time

import feedparser
import yaml


CURRENT_DIR = os.path.dirname(os.path.realpath(__file__))
CONFIG_FILE = os.path.join(CURRENT_DIR, 'config.yaml')
LOG_FILE = os.path.join(CURRENT_DIR, 'log')
SLEEP_DURATION = 300
SHELVE_DIR = os.path.join(CURRENT_DIR, 'shelve')
FEED_SHELF = os.path.join(SHELVE_DIR, 'feed')
DOWNLOAD_SHELF = os.path.join(SHELVE_DIR, 'download')
ONCOMPLETE_SCRIPT = os.path.join(CURRENT_DIR, 'clean.sh')

AnimeEpisode = collections.namedtuple(
    'AnimeEpisode',
    ('anime', 'number', 'version', 'quality', 'extension', 'link', 'published')
)
Download = collections.namedtuple('Download', AnimeEpisode._fields + ('start',))


logging.basicConfig(filename=LOG_FILE, level=logging.INFO)


def feed(feed_url, title_parser):
    feed = feedparser.parse(feed_url)

    with shelve.open(FEED_SHELF) as feed_shelf:
        for feed_item in feed['items']:
            parsed_title = title_parser.match(feed_item['title'])

            if parsed_title is None:
                logging.error('Could not parse: %s' % feed_item)
                continue

            anime_item = AnimeEpisode(
                link=feed_item['link'],
                published=feed_item['published_parsed'],
                **parsed_title.groupdict()
            )

            anime_book = feed_shelf.get(anime_item.anime, collections.defaultdict(dict))
            anime_book[anime_item.quality][anime_item.number] = anime_item
            feed_shelf[anime_item.anime] = anime_book


def download(animes_config):
    with shelve.open(FEED_SHELF) as feed_shelf, shelve.open(DOWNLOAD_SHELF) as download_shelf:
        for anime_config in animes_config:
            anime_title = anime_config['title']
            anime_quality = anime_config['quality']

            try:
                available_episodes = feed_shelf[anime_title][anime_quality]
            except KeyError:
                continue

            download_book = download_shelf.get(anime_title, collections.defaultdict(dict))
            downloaded_episodes = download_book[anime_quality]

            episode_numbers_to_dl = set(available_episodes) - set(downloaded_episodes)

            for episode_number_to_dl in episode_numbers_to_dl:
                episode_to_dl = available_episodes[episode_number_to_dl]

                download_cmd = [
                    'transmission-remote',
                    '--add', episode_to_dl.link,
                    '--no-downlimit',
                    '--no-uplimit',
                    '--torrent-done-script', ONCOMPLETE_SCRIPT,
                ]
                subprocess.Popen(download_cmd)
                
                download = Download(
                    start=datetime.datetime.now().isoformat(),
                    **episode_to_dl._asdict()
                )
                downloaded_episodes[episode_number_to_dl] = download
                download_shelf[anime_title] = download_book

                logging.info('Download: %s' % (download,))


def main(config):
    animes_config = config['animes']
    feed_url = config['feed_url']
    title_parser = re.compile(config['title_parser'])

    while True:
        feed(feed_url=feed_url, title_parser=title_parser)
        download(animes_config=animes_config)
        time.sleep(SLEEP_DURATION)


if __name__ == '__main__':
    with open(CONFIG_FILE) as config_file:
        config = yaml.load(config_file)
    main(config)
