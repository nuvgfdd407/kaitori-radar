"""買取ルデヤ。

カテゴリページに全商品が載っている（ページ送りなし）。
商品カードに「新品」「中古」のバッジがあるので、新品だけを取る。
iPhone は色ごとに「iPhone 17 Pro 256GB ブラック … 未開封 SIMフリー」のような名前で載っている。
Galaxy・Xperia・AQUOS も色ごとに載っていて、SIMフリー版の未開封品だけを買い取っている（キャリア版は対象外）。
iPad・Apple Watch・AirPods も色ごと（Watch はバンドごと）に、JAN と型番つきで載っている。
"""
from bs4 import BeautifulSoup

from ..apple import apple_offer
from ..phones import android_key, one_color, phone_key
from ..text import find_jan, parse_yen

ID = "rudeya"
NAME = "買取ルデヤ"
SHORT = "ルデヤ"
URL = "https://kaitori-rudeya.com/"

# Nintendo Switch 2 / Nintendo Switch / PlayStation5 / Xbox / PlayStation Portal / Steam / ASUS ROG /
# Meta Quest / PlayStation VR / PICO 4 / Legion Go
PAGES = [f"https://kaitori-rudeya.com/category/detail/{i}" for i in (214, 1, 2, 3, 159, 55, 136, 42, 120, 121, 160)]
# Google（Pixel）
PIXEL_PAGES = ["https://kaitori-rudeya.com/category/detail/172"]
# SAMSUNG（Galaxy） / SONY（Xperia） / SHARP（AQUOS）
ANDROID_PAGES = [f"https://kaitori-rudeya.com/category/detail/{i}" for i in (249, 248, 247)]
# iPad / Apple Watch Series 12 / Series 11 / SE 3 / Ultra 3 / Ultra 4 / AirPods / AirPods Pro / AirPods Max
APPLE_PAGES = [f"https://kaitori-rudeya.com/category/detail/{i}" for i in (5, 71, 72, 73, 256, 222, 223, 244, 259, 4, 74, 33, 8, 9)]  # 8: Mac book, 9: Macデスクトップ
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
    for page in IPHONE_PAGES + PIXEL_PAGES:
        for o in _read_page(http, page):
            if "未開封" in o["name"] and ("iPhone" in o["name"] or "SIMフリー" in o["name"]):
                key = phone_key(o["name"])
                offers.append({**o, "key": key, "colors": one_color(key, o["name"], o["price"])})
    for page in ANDROID_PAGES:
        for o in _read_page(http, page):
            key = android_key(o["name"], "SIMフリー")
            if key:
                offers.append({**o, "key": key, "colors": one_color(key, o["name"], o["price"])})
    for page in APPLE_PAGES:
        offers += [apple_offer(o["name"], o["price"], o["url"], jan=o["jan"]) for o in _read_page(http, page)]
    return [o for o in offers if (o["jan"] or o.get("key") or o.get("codes")) and o["price"]]


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
