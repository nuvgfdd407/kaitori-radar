"""買取ルデヤ。

カテゴリページに全商品が載っている（ページ送りなし）。
商品カードに「新品」「中古」のバッジがあるので、新品だけを取る。
iPhone は色ごとに「iPhone 17 Pro 256GB ブラック … 未開封 SIMフリー」のような名前で載っている。
"""
from bs4 import BeautifulSoup

from ..iphone import iphone_key, one_color
from ..text import find_jan, parse_yen

ID = "rudeya"
NAME = "買取ルデヤ"
SHORT = "ルデヤ"
URL = "https://kaitori-rudeya.com/"

# Nintendo Switch 2 / Nintendo Switch / PlayStation5 / Xbox / PlayStation Portal / Steam / ASUS ROG /
# Meta Quest / PlayStation VR / PICO 4 / Legion Go
PAGES = [f"https://kaitori-rudeya.com/category/detail/{i}" for i in (214, 1, 2, 3, 159, 55, 136, 42, 120, 121, 160)]
# ポケモンカード / ワンピースカード / 遊戯王 / ドラゴンボールカード（カートンは対象外）
CARD_PAGES = [f"https://kaitori-rudeya.com/category/detail/{i}" for i in (114, 224, 116, 225)]
# iPhone Duo / 18 Pro / 18 Pro Max / 17 Pro / 17 Pro Max / Air / 17 / 17e / 16 / 16 Plus / 16 Pro / 16 Pro Max / 16e
IPHONE_PAGES = [f"https://kaitori-rudeya.com/category/detail/{i}"
                for i in (255, 254, 253, 219, 220, 221, 218, 232, 183, 184, 185, 186, 205)]


def fetch(http):
    offers = []
    for page in PAGES:
        offers += _read_page(http, page)
    for page in CARD_PAGES:
        offers += [o for o in _read_page(http, page) if "カートン" not in o["name"]]
    for page in IPHONE_PAGES:
        for o in _read_page(http, page):
            if "未開封" in o["name"]:
                key = iphone_key(o["name"])
                offers.append({**o, "key": key, "colors": one_color(key, o["name"], o["price"])})
    return [o for o in offers if o["jan"] and o["price"]]


def _read_page(http, page):
    offers = []
    soup = BeautifulSoup(http.get(page).content, "html.parser")
    for card in soup.select("article.pgrid-card"):
        badge = card.select_one(".product-card-cond-badge")
        if badge is None or "is-new" not in badge.get("class", []):
            continue
        link = card.select_one("a.product-card-name-link")
        jan = card.select_one(".product-card-jan-text")
        price = card.select_one(".product-card-price-value")
        if not (link and jan and price):
            continue  # 「近日公開」など価格が出ていない商品
        offers.append({
            "jan": find_jan(jan.get_text()),
            "name": link.get_text(strip=True),
            "price": parse_yen(price.get_text()),
            "url": link["href"],
        })
    return offers
