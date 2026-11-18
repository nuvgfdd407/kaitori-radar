"""アメモバ買取。

機種のカテゴリ（/smartphone/iphone/ や /smartphone/galaxy/ など）のページに、機種ごとの表がある。
表の1行は「国内版SIMフリー」「docomo版SIMフリー」のようなキャリアと、「iPhone 18 Pro 256GB」のような機種＋容量で、
価格は「未開封買取価格」（キャリア版は「新品買取価格」）と「中古買取価格」の2つ。新品の方だけを使う。
色の区別は一覧にはなく、行の「査定する」のリンク先（機種ごとのページ）の JSON（json_str2）に
色・容量ごとの価格が入っている（s_rank が「新品未使用品（初期）」）。
- iPhone・Pixel: 国内版SIMフリーの行だけを使う（キャリア版は別の価格だが、カタログでは同じ商品なので）。
  色ごとの価格は機種ごとのページから読む（扱っている機種のページだけ開く）
- Galaxy・Xperia・AQUOS: キャリアごとの行を、そのキャリアの商品として使う（色の区別なし）
iPad・ゲーム機などのページもあるが、JAN も Apple の型番も載っていないので使わない。
"""
import json
import re

from bs4 import BeautifulSoup

from ..phones import android_key, phone_color, phone_colors, phone_key
from ..text import parse_yen

ID = "amemoba"
NAME = "アメモバ"
SHORT = "アメモバ"
URL = "https://amemoba.com/"

IPHONE_PAGES = [URL + "smartphone/iphone/", URL + "smartphone/google-pixel/"]
ANDROID_PAGES = [URL + "smartphone/galaxy/", URL + "smartphone/xperia/", URL + "smartphone/aquos/"]
# 表のキャリア（data-carrier）→ phones.py のキャリア名
_CARRIERS = {"SIMフリー": "SIMフリー", "docomo": "docomo", "au": "au", "SoftBank": "SoftBank",
             "楽天モバイル": "楽天モバイル", "rakuten": "楽天モバイル", "Y!mobile": "Y!mobile"}
_JSON = re.compile(r"json_str2\s*=\s*'(\[.*?\])';", re.S)


def fetch(http):
    offers = []
    pages = {}  # 機種ごとのページ（同じページを何度も開かない）
    for page in IPHONE_PAGES:
        for carrier, name, price, link in _read_rows(http, page):
            key = phone_key(name)
            if carrier != "SIMフリー" or not (key and phone_colors(key)):
                continue  # キャリア版と、古い機種・扱っていない機種
            if link not in pages:
                pages[link] = _detail_prices(http, link)
            colors = _color_prices(key, pages[link], key.rsplit(" ", 1)[1], price)
            offers.append({"jan": None, "key": key, "name": name, "price": price, "url": link, "colors": colors})
    for page in ANDROID_PAGES:
        for carrier, name, price, link in _read_rows(http, page):
            key = android_key(name, _CARRIERS.get(carrier))
            if key and _CARRIERS.get(carrier):
                offers.append({"jan": None, "key": key, "name": name, "price": price, "url": link})
    return [o for o in offers if o["price"]]


def _read_rows(http, page):
    """一覧の表の（キャリア, 機種名, 新品の価格, 機種ごとのページ）を順に返す。"""
    soup = BeautifulSoup(http.get(page).content, "html.parser")
    for row in soup.select("tr.p-purchaseArchive__tableRow"):
        carrier = row.select_one(".p-purchaseArchive__termCarrier")
        name = row.select_one(".p-purchaseArchive__termName")
        price = row.select_one(".p-purchaseArchive__priceNew .p-purchaseArchive__priceDesc")
        link = row.select_one("a.p-purchaseArchive__assessmentButton")
        if not (carrier and name and price and link):
            continue
        text = price.get_text().strip()
        if not re.fullmatch(r"[\d,]+円", text):
            continue  # 「〜」の付いた幅のある価格や「--円」は使わない
        yield (carrier.get("data-carrier", "").strip(), " ".join(name.get_text().split()), parse_yen(text),
               URL.rstrip("/") + link["href"] if link["href"].startswith("/") else link["href"])


def _detail_prices(http, page):
    """機種ごとのページの {(容量, 色): 新品未使用品の価格}。読めなければ空。"""
    m = _JSON.search(http.get(page).text)
    if not m:
        return {}
    try:
        items = json.loads(m.group(1))
    except ValueError:
        return {}
    return {(i.get("volume"), i.get("color")): int(float(i.get("s_rank_purchase_price") or 0)) for i in items}


def _color_prices(key, detail, volume, base):
    """{公式の色名: 価格}。機種ごとのページに色ごとの価格がなければ、全色に一覧の価格を当てはめる。"""
    colors = {}
    for (vol, color), price in detail.items():
        official = phone_color(key, color or "")
        if vol == volume and official and price:
            colors[official] = price
    return colors or dict.fromkeys(phone_colors(key), base)
