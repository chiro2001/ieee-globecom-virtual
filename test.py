import os
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
    os.path.join(os.path.join(os.environ.get('userprofile', '~'), '.requests_cache'), 'globecom_cache'),
    use_cache_dir=True,  # Save files in the default user cache dir
    cache_control=False,  # Use Cache-Control headers for expiration, if available
    expire_after=timedelta(days=3),  # Otherwise expire responses after one day
    allowable_methods=['GET', 'POST'],
    # Cache POST requests to avoid sending the same data twice
    allowable_codes=[200, 400],  # Cache 400 responses as a solemn reminder of your failures
    ignored_parameters=['api_key', '.pdf'],  # Don't match this param or save it in the cache
    match_headers=False,  # Match all request headers
    stale_if_error=True  # In case of request errors, use stale cache data if possible)
)

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

    resp = session.get('https://ieee-globecom-virtual.org/type/symposium-paper', headers={"Cookie": secrets.COOKIE})
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
        resp = session.get(symposium.get('url'), headers={"Cookie": secrets.COOKIE})
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
        resp = session.get(presentation.get('url'), headers={"Cookie": secrets.COOKIE})
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


def test_generate_list():
    symposiums_all = db.symposium_paper.find({})
    types = list(set([f"{s.get('type')}" for s in symposiums_all]))
    types.sort()
    res_all = ""
    for t in types:
        symposiums = db.symposium_paper.find({'type': t})
        res = "\\section{%s}\n" % t
        for symposium in symposiums:
            res = res + "\\subsection{%s}\n" % symposium.get('title')
            presentations = db.presentations.find({'symposium': symposium.get('title')})
            for presentation in presentations:
                res = res + "\\subsubsection{%s}\n" % presentation.get('title')
                presentation_info_list: list = db.presentation_info.find({'title': presentation.get('title')})
                presentation_info: dict = presentation_info_list[0] if len(presentation_info_list) > 0 else {}
                res = res + "abstract:%s\n" % presentation_info.get('abstract', 'None').replace('\n', '')
        res_all = res_all + res
    with open('result.tex', 'w', encoding='utf8') as f:
        f.write(res_all)


if __name__ == '__main__':
    # test_fetch_symposium_paper()
    # test_parse_symposiums()
    # test_parse_presentations()
    test_generate_list()
