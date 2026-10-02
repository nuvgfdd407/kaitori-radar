"""買取商店。

カテゴリページの表（品目・新品買取・中古買取）に全商品が載っている（ページ送りなし）。
表にはJANがないので、ページに埋め込まれた構造化データ（JSON-LD）の gtin13 から、
商品ページのURLを手がかりにJANを引く。価格は表の「新品買取」の列を使う。
iPhone は色ごとに「iPhone 17 Pro 256GB シルバー … SIMフリー」のような名前で載っている。
Android は SIMフリー・キャリアごとの表（「Galaxy S26 Ultra SC-53G 12G+256G docomo [ブラック]」のように色ごと）から、
Galaxy・Xperia・AQUOS の行を使う。
"""
import json
import re
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from ..phones import android_key, one_color, phone_key
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
# Google Pixel（機種ごとのページ。キャリア版も載っているので SIMフリーの行だけを使う）
PIXEL_PAGES = [f"https://www.kaitorishouten-co.jp/model/google-pixel-{m}"
               for m in ("11", "11-pro", "11-pro-xl", "11-pro-fold", "10a")]

# Android の SIMフリー / docomo / au / UQモバイル（au 版と同じ機種） / SoftBank / Y!mobile / 楽天モバイル の表
ANDROID_PAGES = [(f"https://www.kaitorishouten-co.jp/category/1/{i}", carrier) for i, carrier in (
    (262, "SIMフリー"), (261, "docomo"), (260, "au"), (418, "au"), (259, "SoftBank"), (258, "Y!mobile"), (419, "楽天モバイル"))]


def fetch(http):
    offers = []
    for page in PAGES:
        offers += [o for o in _read_table(http, page) if o["jan"]]
    for page in IPHONE_PAGES:
        for o in _read_table(http, page):
            key = phone_key(o["name"])
            offers.append({**o, "key": key, "colors": one_color(key, o["name"], o["price"] or 0)})
    for page in PIXEL_PAGES:
        for o in _read_table(http, page):
            if "SIMフリー" in o["name"]:
                key = phone_key(o["name"])
                offers.append({**o, "key": key, "colors": one_color(key, o["name"], o["price"] or 0)})
    for page, carrier in ANDROID_PAGES:
        for o in _read_table(http, page):
            key = android_key(o["name"], carrier)
            # 「セット付き」は付属品込みの別の買取なので使わない
            if key and not o["name"].startswith("セット付き"):
                offers.append({**o, "key": key, "colors": one_color(key, o["name"], o["price"] or 0)})
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
