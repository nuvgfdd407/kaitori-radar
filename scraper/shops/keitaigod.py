"""ケータイゴッド。

価格一覧（/price/index.php?ci=<キャリア・ジャンル>&mi=<メーカー・機種>）の表に、商品名・買取価格が載っている。
1ページ50件で、続きは &page=N。ゲーム機・トレカは商品名の中に JAN が書かれている（2つ書かれていることもある）。
iPhone は「iPhone 18 Pro 256GB【APPLEストア版】」「…【docomo/au/SoftBank/楽天版】」のように機種＋容量ごとで、
色による価格の違いはない。APPLEストア版の新品価格は、Apple Store で買ったことがわかる書類がある場合の価格なので、
その条件を "note" として価格と一緒に載せる。
Android は SIMフリー・キャリアごとの一覧から、Galaxy・Xperia・AQUOS・Pixel を取る。
"""
import re
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from ..phones import android_key, phone_colors, phone_key
from ..text import parse_yen

ID = "keitaigod"
NAME = "ケータイゴッド"
SHORT = "ゴッド"
URL = "https://keitai-god.com/"

LIST_URL = "https://keitai-god.com/price/index.php"
# 家電・ゲーム機（8）: 任天堂 / SONY / Microsoft / Meta
GAME_MAKERS = [(8, 181), (8, 100), (8, 291), (8, 316)]
# トレーディングカード（20）: ポケモンカード BOX / 遊戯王 / ワンピースカード / ドラゴンボール
CARD_MAKERS = [(20, 395), (20, 403), (20, 408), (20, 422)]
# iPhone（11）: 18 Pro Max / 18 Pro / Duo / 17 Pro Max / 17 Pro / 17 / 17e / Air / 16 Pro Max / 16 Pro / 16 Plus / 16 / 16e
IPHONE_MODELS = [(11, m) for m in (502, 501, 500, 451, 452, 454, 467, 453, 432, 431, 433, 430, 440)]
# Android: (ジャンル, キャリア, [メーカー])。Pixel は SIMフリーの Google だけ
ANDROID_MAKERS = [
    (7, "SIMフリー", [66, 70, 68, 107]),  # Google / SAMSUNG / SONY / SHARP
    (1, "docomo", [8, 10, 9]),
    (3, "au", [23, 27, 25]),
    (15, "au", [257, 271, 252]),  # UQ mobile（au 版と同じ機種）
    (2, "SoftBank", [33, 55, 34]),
    (18, "楽天モバイル", [266, 263, 267]),
    (5, "Y!mobile", [441, 56, 186]),
]
MAX_PAGES = 10
APPLE_STORE_NOTE = "Apple Storeで購入した証明が必要"
_JAN = re.compile(r"(?<!\d)\d{13}(?!\d)")


def fetch(http):
    offers = []
    for ci, mi in GAME_MAKERS + CARD_MAKERS:
        for name, price, url in _read_list(http, ci, mi):
            offers += [{"jan": jan, "name": name, "price": price, "url": url} for jan in _JAN.findall(name)]
    for ci, mi in IPHONE_MODELS:
        for name, price, url in _read_list(http, ci, mi):
            key = phone_key(name)
            if key and phone_colors(key):
                offer = {"jan": None, "key": key, "name": name, "price": price, "url": url}
                if "APPLEストア版" in name:
                    offer["note"] = APPLE_STORE_NOTE
                offers.append(offer)
    for ci, carrier, makers in ANDROID_MAKERS:
        for mi in makers:
            for name, price, url in _read_list(http, ci, mi):
                key = phone_key(name) if "Pixel" in name else android_key(name, carrier)
                if key and phone_colors(key):
                    offers.append({"jan": None, "key": key, "name": name, "price": price, "url": url})
    return [o for o in offers if o["price"]]


def _read_list(http, ci, mi):
    """（商品名, 価格, 商品ページのURL）を順に返す。"""
    for page in range(1, MAX_PAGES + 1):
        params = {"ci": ci, "mi": mi, **({"page": page} if page > 1 else {})}
        soup = BeautifulSoup(http.get(LIST_URL, params=params).content, "html.parser")
        for row in soup.select("#price_table tr"):
            cells = row.find_all("td")
            link = row.select_one('a[href*="model.php"]')
            if len(cells) < 3:
                continue
            yield (" ".join(cells[1].get_text().split()), parse_yen(cells[2].get_text()),
                   urljoin(URL, link["href"]) if link else LIST_URL)
        if not soup.select_one(f'ul.pager a[href*="page={page + 1}&"]'):
            break
