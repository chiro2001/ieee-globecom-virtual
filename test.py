import os
import json
import requests
import pymongo
from bs4 import BeautifulSoup as Soup
from bs4.element import Tag, ResultSet
from typing import *
from utils.logger import logger
from data.database import db
from tqdm import trange
import secrets
from requests_toolbelt import threaded

from datetime import timedelta
import requests_cache
from requests_cache import CachedSession

session = CachedSession(
    os.path.join(os.path.join(os.environ.get('userprofile', '~'), '.requests_cache'), 'icc_cache'),
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

url_prefix = 'https://ieee-icc-virtual.org'


def test_fetch_symposium_paper():
    def get_paper_list(s: Soup):
        cards = s.find_all("li", class_="card")
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

    resp = session.get('https://ieee-icc-virtual.org/terms/cc_track', headers={"Cookie": secrets.COOKIE})
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
        slides: List[Tag] = [a for a in download_buttons if 'slides' in a.attrs.get('href')]
        papers: List[Tag] = [a for a in download_buttons if 'papers' in a.attrs.get('href')]

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


def test_fix_papers_slides():
    presentations_info: List[Dict] = db.presentation_info.find({})
    for i in trange(len(presentations_info)):
        presentation_info = presentations_info[i]
        papers = presentation_info.get('papers')
        slides = presentation_info.get('slides')
        presentation_info['slides'] = papers
        presentation_info['papers'] = slides
        db.presentation_info.update_by_title(presentation_info)


def replace_symbols(p: str, replace: str = '_') -> str:
    symbols = "/\\*#$@!\"<>?|:"
    for s in symbols:
        p = p.replace(s, replace)
    return p


def test_download():
    if not os.path.exists("download"):
        os.mkdir("download")
    symposiums_all = db.symposium_paper.find({})
    types = list(set([f"{s.get('type')}" for s in symposiums_all]))
    types.sort()
    download_list = []
    logger.info(f"generating download list...")
    for i in trange(len(types)):
        t = types[i]
        path_type = os.path.join("download", replace_symbols(t))
        if not os.path.exists(path_type):
            os.mkdir(path_type)
        symposiums = db.symposium_paper.find({'type': t})
        for symposium in symposiums:
            path_symposium = os.path.join(path_type, replace_symbols(symposium.get('title')))
            if not os.path.exists(path_symposium):
                os.mkdir(path_symposium)
            presentations = db.presentations.find({'symposium': symposium.get('title')})
            for presentation in presentations:
                presentation_info_list: list = db.presentation_info.find({'title': presentation.get('title')})
                presentation_info: dict = presentation_info_list[0] if len(presentation_info_list) > 0 else {}
                title = presentation_info.get("title")
                if title is None:
                    logger.warning(f"Info err: {presentation}")
                    continue
                path_presentation = os.path.join(path_symposium, replace_symbols(replace_symbols(title)))
                if not os.path.exists(path_presentation):
                    os.mkdir(path_presentation)
                papers = presentation_info.get('papers')
                slides = presentation_info.get('slides')

                def get_download_list(download_type: str, data: list):
                    if len(data) == 0:
                        return
                    paths_data = os.path.join(path_presentation, download_type)
                    if not os.path.exists(paths_data):
                        os.mkdir(paths_data)
                    for index in range(len(data)):
                        url = data[index]
                        # ext = url.split('.')[-1]
                        ext = 'pdf'
                        filename = f"{replace_symbols(title)}{('(%s)' % str(index)) if len(data) > 1 else ''}.{ext}"
                        filepath = os.path.join(paths_data, filename)
                        download_info = {
                            'title': title,
                            'filepath': filepath,
                            'url': url,
                            'ext': ext,
                            'type': download_type
                        }
                        if len(db.downloaded.find(
                                {'title': download_info['title'], 'type': download_info['type']})) == 0 \
                                and not os.path.exists(filepath):
                            download_list.append(download_info)
                        else:
                            logger.info(f"Fin {download_type}: {title}")
                            db.downloaded.update_by_title(download_info)

                get_download_list('papers', papers)
                get_download_list('slides', slides)

    def save_download(information: dict, data: bytes):
        with open(information.get('filepath'), 'wb') as f_write:
            f_write.write(data)

    # print(download_list)
    logger.info(f"{len(download_list)} tasks!")
    download_map = {d['url']: d for d in download_list}
    requests_list = [{'method': 'GET', 'url': d['url']} for d in download_list]
    if len(requests_list) == 0:
        logger.info(f"No task!")
        return

    def initialize_session(s):
        session.headers['User-Agent'] = "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:95.0) Gecko/20100101 Firefox/95.0"
        return session

    responses_generator, exceptions_generator = threaded.map(requests_list, initializer=initialize_session)
    for response in responses_generator:
        u = response.request_kwargs['url']
        info = download_map.get(u)
        if info is None:
            logger.error(f"err resp!")
            continue
        logger.info(f"Done: {info.get('title')}")
        db.downloaded.update_by_title(info)
        save_download(info, response.response.content)
    for e in exceptions_generator:
        logger.error(f"{e.__class__.__name__}: {e.request_kwargs['url']}")


if __name__ == '__main__':
    test_fetch_symposium_paper()
    # test_parse_symposiums()
    # test_parse_presentations()
    # test_generate_list()
    # test_fix_papers_slides()
    # test_download()
