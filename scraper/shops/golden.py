"""ゴールデンホビー買取センター（PSA 鑑定品だけ。宅配買取のみで、ポケモンカードの PSA10 を扱う）。

「ポケモンカードPSA10.html」の1ページに、<section class="list"> ごとに
レアリティと点数（「SR【PSA10】」）・型番（「BW6F-063」）・カード名・買取価格・画像が載っている。
価格は「10月3日から10月6日までに到着した際の買取価格」のように、到着日ごとに決まっている。
型番は「収録弾-番号」で分母がないので、番号だけ（063）で渡し、カタログとは番号とカード名で突き合わせる
（scraper.psa_catalog）。プロモ（SM-P-325）は「325/SM-P」にする。
"""
import re
from urllib.parse import quote, urljoin

from bs4 import BeautifulSoup

from ..psa import psa_key
from ..text import parse_yen

ID = "golden"
NAME = "ゴールデンホビー"
SHORT = "ゴールデン"
URL = "https://buy-gh.tokyo/"

LIST_URL = URL + quote("ポケモンカードPSA10.html")


def fetch(http):
    return fetch_psa(http)


def fetch_psa(http):
    """PSA 鑑定品の出品（scraper.psa_catalog でも使う）。"""
    soup = BeautifulSoup(http.get(LIST_URL).content, "html.parser")
    offers = []
    for item in soup.select("section.list"):
        texts = [p.get_text(strip=True) for p in item.find_all("p")]
        name = item.find("h4").get_text(strip=True) if item.find("h4") else ""
        head = re.match(r"(.*?)【(PSA\s*\d+)】", texts[0]) if texts else None
        number = _number(texts[1]) if len(texts) > 1 else None
        price = parse_yen(item.select_one("p.buy").get_text()) if item.select_one("p.buy") else None
        if not (head and name and number and price):
            continue
        rarity, grade = head.group(1), head.group(2).replace(" ", "")
        key = psa_key("pokemon", grade, f"{name} {rarity}", number)
        img = item.find("img")
        if key:
            offers.append({"jan": None, "key": key, "name": f"{grade} {name} {rarity} {texts[1]}", "price": price,
                           "url": LIST_URL,
                           "psa": {"game": "pokemon", "grade": grade, "name": name, "rarity": rarity or None,
                                   "number": number, "image": urljoin(URL, img["src"]) if img else None,
                                   "page": LIST_URL}})
    return offers


def _number(code):
    """「BW6F-063」→「063」、プロモの「SM-P-325」→「325/SM-P」。"""
    m = re.fullmatch(r"(.+)-(\d+)", code.strip())
    if not m:
        return None
    series, number = m.groups()
    return f"{number}/{series}" if series.upper().endswith("-P") else number
