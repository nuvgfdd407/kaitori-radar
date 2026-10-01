"""買取当番。

サイトが WooCommerce なので、標準の Store API から JSON で取れる。
SKU 欄に JAN コードが入っている。この店は新品専門で、中古は別カテゴリ。
iPhone は JAN がなく「iPhone 17 Pro 256GB」のような機種＋容量の商品で、
色ごとに価格が違うときは価格の幅（price_range）が付くので、その最大値を使う。
"""
import html

from ..iphone import iphone_key

ID = "toban"
NAME = "買取当番"
SHORT = "当番"
URL = "https://tobansyoji.co.jp/"

API = "https://tobansyoji.co.jp/wp-json/wc/store/v1/products"
# Nintendo Switch 2 / Nintendo Switch / PlayStation / Xbox / Meta Quest / Steam Deck / ASUS ROG / PS5 周辺機器
CATEGORIES = [184, 185, 186, 187, 188, 189, 190, 239]
# iPhone 18 / 17 / 16
IPHONE_CATEGORIES = [306, 207, 208]


def fetch(http):
    offers = []
    for category in CATEGORIES:
        for item, name, price in _read_category(http, category):
            offers.append({"jan": item["sku"].strip(), "name": name, "price": price, "url": item["permalink"]})
    for category in IPHONE_CATEGORIES:
        for item, name, price in _read_category(http, category):
            offers.append({"jan": None, "key": iphone_key(name), "name": name, "price": price, "url": item["permalink"]})
    return offers


def _read_category(http, category):
    """（商品データ, 商品名, 価格）を順に返す。"""
    page = 1
    while True:
        res = http.get(API, params={"category": category, "per_page": 100, "page": page})
        for item in res.json():
            prices = item["prices"]
            unit = 10 ** prices["currency_minor_unit"]
            price_range = prices.get("price_range") or {}
            price = int(price_range.get("max_amount") or prices["price"]) // unit
            # 0円や申込不可は、今は買い取っていない商品
            if price <= 0 or not item["is_purchasable"]:
                continue
            yield item, html.unescape(item["name"]), price
        if page >= int(res.headers.get("X-WP-TotalPages", 1)):
            break
        page += 1
