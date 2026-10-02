"""トレカクラブ（PSA 鑑定品だけ。郵送買取の専門店で、ポケモンカードの PSA10 を扱う）。

一覧（/pokemon/psa10/、1ページ100件で続きは ?page=N）に、カード名・番号・点数・価格・画像が載っている。
画面の番号は「085/SM」のように略してあるので、リンク先の URL（/pokemon/cards/psa10/085-SM-P/）の番号を使う。
URL は「<番号>-<分母>-<収録弾>-<記号>」の形で（119-114-SM4%2B-B）、プロモは「<番号>-<SM-P など>」、
末尾に -1ED（初版）・-CH（中国語版）が付くことがある。
"""
import re
from urllib.parse import unquote, urljoin

from bs4 import BeautifulSoup

from ..psa import psa_key
from ..text import parse_yen

ID = "club"
NAME = "トレカクラブ"
SHORT = "クラブ"
MODE = "郵送"  # 店名の後ろに付ける買取方法
URL = "https://torecaclub.com/"

LIST_URL = URL + "pokemon/psa10/"
PAGE_SIZE = 100
MAX_PAGES = 20
_SLUG = re.compile(r"/pokemon/cards/psa10/([^/]+)/")


def fetch(http):
    return fetch_psa(http)


def fetch_psa(http):
    """PSA 鑑定品の出品（scraper.psa_catalog でも使う）。"""
    offers = []
    for page in range(1, MAX_PAGES + 1):
        soup = BeautifulSoup(http.get(LIST_URL, params={"page": page} if page > 1 else None).content, "html.parser")
        links = [a for a in soup.select("a[href]") if _SLUG.search(a["href"])]
        for a in links:
            offer = _offer(a)
            if offer:
                offers.append(offer)
        if len(links) < PAGE_SIZE:
            break
    return offers


def _offer(a):
    spans = a.select("span span")
    name = spans[0].get_text(strip=True) if spans else ""
    grade = re.search(r"PSA\s*\d+", a.get_text(" "))
    number, extra = _number(_SLUG.search(a["href"]).group(1))
    price = parse_yen(a.select_one("strong").get_text() if a.select_one("strong") else "")
    if not (name and grade and number and price):
        return None
    grade = grade.group(0).replace(" ", "")
    key = psa_key("pokemon", grade, f"{name} {extra}", number)
    img = a.find("img")
    page = urljoin(URL, a["href"])
    return key and {"jan": None, "key": key, "name": f"{grade} {name} {number}", "price": price, "url": page,
                    "psa": {"game": "pokemon", "grade": grade, "name": f"{name} {extra}".strip(), "rarity": None,
                            "number": number, "image": img.get("src") if img else None, "page": page}}


def _number(slug):
    """URL の「119-114-SM4%2B-B」→（「119/114」, 付記）。付記は初版・中国語版の印（名前に足して区別する）。"""
    parts = unquote(slug).upper().split("-")
    extra = " ".join(w for flag, w in (("1ED", "1ED"), ("CH", "中国版")) if flag in parts[2:])
    if len(parts) >= 3 and parts[2] == "P" and not parts[1].isdigit():
        return f"{parts[0]}/{parts[1]}-P", extra  # プロモ（085-SM-P）
    if len(parts) >= 2 and parts[0].isdigit() and parts[1].isdigit():
        return f"{parts[0]}/{parts[1]}", extra
    return None, extra
