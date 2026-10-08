"""PANDA買取。

カテゴリ（?cpro=game など）の一覧に、JAN・商品名・新品価格が表で載っている。
1ページ20件で、続きは &nowpage=N。商品ごとのページはないので、URL は一覧のページにする。
iPhone は色ごとに「iPhone 17 Pro Max 256GB ディープブルー MFYA4J/A」のように載っている。
新品価格が「¥1」の商品は、買い取っていない商品。
"""
import re

from bs4 import BeautifulSoup

from ..phones import android_key, one_color, phone_colors, phone_key
from ..text import find_jan, parse_yen

ID = "panda"
NAME = "PANDA買取"
SHORT = "PANDA"
URL = "https://panda-kaitori.co.jp/"

# ゲーム機（ソフト・周辺機器も同じ一覧に載っている） / iPhone / スマートフォン
CATEGORIES = ["game", "iphone", "smart-phone", "instax-camera"]  # instax-camera: チェキ・写ルンです
MAX_PAGES = 20
MIN_PRICE = 100


def fetch(http):
    offers = []
    for category in CATEGORIES:
        for o in _read_category(http, category):
            if re.search("iPhone|Pixel|Galaxy|Xperia|AQUOS", o["name"]):
                key = phone_key(o["name"]) if re.search("iPhone|Pixel", o["name"]) else android_key(o["name"])
                if not (key and phone_colors(key)):
                    continue  # 古い機種や、扱っていない機種
                o = {**o, "key": key, "colors": one_color(key, o["name"], o["price"])}
            offers.append(o)
    return [o for o in offers if (o["jan"] or o.get("key")) and o["price"] and o["price"] >= MIN_PRICE]


def _read_category(http, category):
    for page in range(1, MAX_PAGES + 1):
        url = f"{URL}?cpro={category}" + (f"&nowpage={page}" if page > 1 else "")
        soup = BeautifulSoup(http.get(url).content, "html.parser")
        for row in soup.select("tr"):
            jan = row.select_one("td.tb-var")
            name = row.select_one("td.tb-product .product-name")
            price = row.select_one("td.tb-price ins")
            if jan and name and price:
                yield {
                    "jan": find_jan(jan.get_text()),
                    "name": " ".join(name.get_text().split()),
                    "price": parse_yen(price.get_text()),
                    "url": url,
                }
        if not soup.select_one(f'a[href*="cpro={category}&nowpage={page + 1}"]'):
            break
