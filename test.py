import requests
import pymongo
from bs4 import BeautifulSoup as Soup
from bs4.element import Tag, ResultSet
from typing import *
from utils.logger import logger
from data.database import db
from tqdm import trange
import secrets

from datetime import timedelta
import requests_cache
from requests_cache import CachedSession

session = CachedSession(
    'demo_cache',
    use_cache_dir=True,  # Save files in the default user cache dir
    cache_control=True,  # Use Cache-Control headers for expiration, if available
    expire_after=timedelta(days=3),  # Otherwise expire responses after one day
    allowable_methods=['GET', 'POST'],  # Cache POST requests to avoid sending the same data twice
    allowable_codes=[200, 400],  # Cache 400 responses as a solemn reminder of your failures
    ignored_parameters=['api_key'],  # Don't match this param or save it in the cache
    match_headers=False,  # Match all request headers
    stale_if_error=True,  # In case of request errors, use stale cache data if possible
)
requests_cache.install_cache('demo_cache')
url_prefix = 'https://ieee-globecom-virtual.org'


def test_fetch_symposium_paper():
    def get_paper_list(soup: Soup):
        cards = soup.find_all("div", class_="card")
        logger.info(f"{len(cards)} cards!")
        cards_info = [parse_symposium_item(card) for card in cards]
        return cards_info

    def parse_symposium_item(card: Tag):
        hrefs: List[Tag] = card.find_all('a')
        hrefs = [href for href in hrefs[1:] if 'use-ajax' not in href.attrs.get('class', [])]
        try:
            url: str = hrefs[0].attrs.get('href')
            card_info = {
                "title": hrefs[0].get_text().strip(),
                "type": hrefs[1].get_text().strip() if len(hrefs) >= 2 else None,
                "url": url if not url.startswith('/') else url_prefix + url
            }
            return card_info
        except IndexError:
            logger.error("card: " + card.get_text().replace('\n', ' ') + " failed!")

    resp = requests.get('https://ieee-globecom-virtual.org/type/symposium-paper', headers={"Cookie": secrets.COOKIE})
    soup = Soup(resp.content, "html.parser")
    symposium_papers = get_paper_list(soup)
    db.symposium_paper.update_by_title(symposium_papers)
    logger.info(f"Done")


def test_parse_symposiums():
    def get_paper_list(soup: Soup):
        cards = soup.find_all("div", class_="card")
        cards_info = [parse_presentation_item(card) for card in cards]
        return cards_info

    def parse_presentation_item(card: Tag):
        hrefs: List[Tag] = card.find_all('a')
        try:
            url: str = hrefs[0].attrs.get('href')
            card_info = {
                "title": hrefs[0].get_text().strip(),
                "url": url if not url.startswith('/') else url_prefix + url
            }
            return card_info
        except IndexError:
            logger.error("card: " + card.get_text().replace('\n', ' ') + " failed!")

    def parse_symposium(symposium: dict):
        # logger.info(f"{symposium.get('title')}")
        resp = requests.get(symposium.get('url'), headers={"Cookie": secrets.COOKIE})
        soup = Soup(resp.content, "html.parser")
        presentations = get_paper_list(soup)
        presentations = [{"symposium": symposium.get('title'), **p} for p in presentations]
        db.presentations.update_by_title(presentations)

    symposiums = db.symposium_paper.find({})
    logger.info(f"{len(symposiums)} symposiums!")
    for i in trange(len(symposiums)):
        parse_symposium(symposiums[i])
    logger.info(f"Done")


def test_parse_presentations():
    def parse_presentation(presentation: dict):
        # logger.info(f"{presentation.get('title')}")
        resp = requests.get(presentation.get('url'), headers={"Cookie": secrets.COOKIE})
        soup = Soup(resp.content, "html.parser")

        # Find abstract
        abstract: Tag = soup.find("div", class_="field--name-field-cc-abstract"). \
            find("div", class_="field__item")

        # Find papers & slides link
        download_buttons: List[Tag] = soup.find_all("a", attrs={"type": "button", "data-action": "Download"})
        slides: List[Tag] = [a for a in download_buttons if 'papers' in a.attrs.get('href')]
        papers: List[Tag] = [a for a in download_buttons if 'slides' in a.attrs.get('href')]

        presentation_info = {
            "title": presentation.get('title'),
            "papers": [p.attrs.get("href") for p in papers],
            "slides": [s.attrs.get("href") for s in slides],
            "abstract": abstract.get_text().strip()
        }
        db.presentation_info.update_by_title(presentation_info)

    presentations = db.presentations.find({})
    for i in trange(len(presentations)):
        parse_presentation(presentations[i])
    logger.info(f"Done")


if __name__ == '__main__':
    # test_fetch_symposium_paper()
    # test_parse_symposiums()
    test_parse_presentations()
