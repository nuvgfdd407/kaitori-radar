"""クイック（携帯高価買取）。

シリーズごとのページに「キャリア（SIM の種類）・機種名・未使用品買取価格・中古買取価格」の行が並んでいる。
親のページ（「iPhone」「Galaxy」など）に子のページの行が全部載っているので、親のページだけを読む。
JAN は載っていない。価格は「未使用品買取価格」（新品・未開封）だけを使い、「中古買取価格」は使わない。
- iPhone・Pixel: 「iPhone17 Pro 256GB」のように機種＋容量ごと。色の区別はない（全色同じ価格）。
  キャリア版（docomo版SIMフリーなど）も載っているが、カタログは SIMフリー版なので「国内版SIMフリー」の行だけを使う
- Galaxy・Xperia・AQUOS: キャリアの欄（「docomo版SIMフリー」「au版」「UQmobile版」など）を android_key に渡す。
  同じ名前で価格の違う行（メモリ違いなど）は android_key が None を返すか、先に出た行だけを使う
- Mac・Apple Watch: 機種名に型番（「MDVN4J/A」など）が書かれている。型番のない行は使わない
- iPad: 型番が書かれていないので使わない
"""
import re

from bs4 import BeautifulSoup

from ..apple import apple_offer
from ..phones import android_key, phone_colors, phone_key
from ..text import parse_yen

ID = "quick"
NAME = "クイック"
SHORT = "クイック"
URL = "https://keitaikoukakaitori.com/"

IPHONE_PAGES = [URL + "price/smartphone/iphone/", URL + "price/smartphone/google-pixel/"]
ANDROID_PAGES = [URL + "price/smartphone/" + p + "/" for p in ("galaxy", "xperia", "aquos")]
APPLE_PAGES = [URL + "price/pc/" + p + "/" for p in ("macbook", "mac", "imac")] + [URL + "price/wearable/apple-watch/"]
# キャリアの欄の書き方 → android_key のキャリア名。UQ mobile 版は au 版として扱う（scraper.phones と同じ）
_CARRIERS = [("国内版", "SIMフリー"), ("docomo", "docomo"), ("au", "au"), ("UQ", "au"), ("SoftBank", "SoftBank"),
             ("Y!mobile", "Y!mobile"), ("楽天", "楽天モバイル")]
_PRICE = re.compile(r"未使用品買取価格\s*[:：]\s*([\d,]+)円")


def fetch(http):
    offers, seen = [], set()

    def add(offer, key):
        if key not in seen:  # 同じ商品が2回出てきたら先の行だけを使う
            seen.add(key)
            offers.append(offer)

    for page in IPHONE_PAGES:
        for carrier, name, price in _read_rows(http, page):
            key = phone_key(name)
            if carrier.startswith("国内版SIMフリー") and key and phone_colors(key):
                add({"jan": None, "key": key, "name": name, "price": price, "url": page}, key)
    for page in ANDROID_PAGES:
        for carrier, name, price in _read_rows(http, page):
            c = next((label for head, label in _CARRIERS if carrier.startswith(head)), None)
            key = android_key(name, c) if c else None
            if key:
                add({"jan": None, "key": key, "name": name, "price": price, "url": page}, key)
    for page in APPLE_PAGES:
        for _, name, price in _read_rows(http, page):
            offer = apple_offer(name, price, page)
            if offer["codes"]:
                add(offer, tuple(offer["codes"]))
    return offers


def _read_rows(http, page):
    """行の（キャリア, 機種名, 未使用品買取価格）を順に返す。未使用品の価格がない行（ASK など）は飛ばす。"""
    soup = BeautifulSoup(http.get(page).content, "html.parser")
    for row in soup.select(".model__price-row"):
        name, carrier = row.select_one(".model__price-name"), row.select_one(".model__price-carrier")
        prices = " ".join(p.get_text(" ") for p in row.select(".model__price-price"))
        m = _PRICE.search(" ".join(prices.split()))
        if name and m and parse_yen(m.group(1)):
            yield (" ".join(carrier.get_text(" ").split()) if carrier else "", " ".join(name.get_text(" ").split()),
                   parse_yen(m.group(1)))
