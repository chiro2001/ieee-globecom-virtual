import requests
import pymongo
from bs4 import BeautifulSoup as Soup
from bs4.element import Tag
from typing import *
from utils.logger import logger
from data.database import db
import secrets

url_prefix = 'https://ieee-globecom-virtual.org'


def test_fetch_symposium_paper():
    def get_paper_list(soup: Soup):
        cards = soup.find_all("div", class_="card")
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
    db.symposium_paper.update(symposium_papers)
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
        logger.info(f"{symposium.get('title')}")
        resp = requests.get(symposium.get('url'), headers={"Cookie": secrets.COOKIE})
        soup = Soup(resp.content, "html.parser")
        presentations = get_paper_list(soup)
        db.presentations.update(presentations)

    symposiums = db.symposium_paper.find({})
    for s in symposiums:
        parse_symposium(s)
    logger.info(f"Done")


if __name__ == '__main__':
    # test_fetch_symposium_paper()
    test_parse_symposiums()
