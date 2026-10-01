"""買取商店。

カテゴリページの表（品目・新品買取・中古買取）に全商品が載っている（ページ送りなし）。
表にはJANがないので、ページに埋め込まれた構造化データ（JSON-LD）の gtin13 から、
商品ページのURLを手がかりにJANを引く。価格は表の「新品買取」の列を使う。
iPhone は色ごとに「iPhone 17 Pro 256GB シルバー … SIMフリー」のような名前で載っている。
"""
import json
import re
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from ..iphone import iphone_key
from ..text import find_jan, parse_yen

ID = "shouten"
NAME = "買取商店"
SHORT = "買取商店"
URL = "https://www.kaitorishouten-co.jp/"

# Nintendo Switch 2 / Nintendo Switch / PlayStation / Xbox / VR / Steam Deck / ASUS ROG / ゲーム周辺機器 /
# ポケモンカード / ONE PIECEカード
PAGES = [f"https://www.kaitorishouten-co.jp/category/2/{i}" for i in (703, 281, 280, 279, 587, 602, 639, 637, 739, 740)]
# iPhone Duo / 18 Pro / 18 Pro Max / 17 / Air / 17 Pro / 17 Pro Max / 17e / 16 / 16 Plus / 16 Pro / 16 Pro Max
IPHONE_PAGES = [f"https://www.kaitorishouten-co.jp/category/1/{i}"
                for i in (748, 746, 747, 708, 709, 710, 711, 725, 687, 688, 689, 690)]


def fetch(http):
    offers = []
    for page in PAGES:
        offers += [o for o in _read_table(http, page) if o["jan"]]
    for page in IPHONE_PAGES:
        offers += [{**o, "key": iphone_key(o["name"])} for o in _read_table(http, page)]
    return [o for o in offers if (o["jan"] or o.get("key")) and o["price"]]


def _read_table(http, page):
    soup = BeautifulSoup(http.get(page).content, "html.parser")
    jans = _jans_by_url(soup)
    header = soup.find("th", string=re.compile("新品買取"))
    if header is None:
        return []
    table = header.find_parent("table")
    new_col = [th.get_text(strip=True) for th in table.select("th")].index(header.get_text(strip=True))
    offers = []
    for row in table.select("tr"):
        cells = row.find_all("td")
        link = row.select_one('a[href*="/products/detail/"]')
        if link is None or len(cells) <= new_col:
            continue
        url = urljoin(URL, link["href"])
        offers.append({
            "jan": jans.get(url),
            "name": link.get_text(strip=True),
            "price": parse_yen(cells[new_col].get_text()),  # 「—」「近日公開」は None になる
            "url": url,
        })
    return offers


def _jans_by_url(soup):
    jans = {}
    for tag in soup.select('script[type="application/ld+json"]'):
        try:
            data = json.loads(tag.string or "")
        except ValueError:
            continue
        for item in data if isinstance(data, list) else [data]:
            if isinstance(item, dict) and item.get("@type") == "Product" and item.get("url"):
                jans[item["url"]] = find_jan(item.get("gtin13"))
    return jans
