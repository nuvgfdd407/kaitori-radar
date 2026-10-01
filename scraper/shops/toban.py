"""買取当番。

サイトが WooCommerce なので、標準の Store API から JSON で取れる。
SKU 欄に JAN コードが入っている。この店は新品専門で、中古は別カテゴリ。
"""
import html

ID = "toban"
NAME = "買取当番"
SHORT = "当番"
URL = "https://tobansyoji.co.jp/"

API = "https://tobansyoji.co.jp/wp-json/wc/store/v1/products"
# Nintendo Switch 2 / Nintendo Switch / PlayStation / Xbox / Meta Quest / Steam Deck / ASUS ROG / PS5 周辺機器
CATEGORIES = [184, 185, 186, 187, 188, 189, 190, 239]


def fetch(http):
    offers = []
    for category in CATEGORIES:
        page = 1
        while True:
            res = http.get(API, params={"category": category, "per_page": 100, "page": page})
            for item in res.json():
                prices = item["prices"]
                price = int(prices["price"]) // 10 ** prices["currency_minor_unit"]
                # 0円や申込不可は、今は買い取っていない商品
                if price <= 0 or not item["is_purchasable"]:
                    continue
                offers.append({
                    "jan": item["sku"].strip(),
                    "name": html.unescape(item["name"]),
                    "price": price,
                    "url": item["permalink"],
                })
            if page >= int(res.headers.get("X-WP-TotalPages", 1)):
                break
            page += 1
    return offers
