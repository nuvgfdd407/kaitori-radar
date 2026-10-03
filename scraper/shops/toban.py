"""買取当番。

サイトが WooCommerce なので、標準の Store API から JSON で取れる。
SKU 欄に JAN コードが入っている。この店は新品専門で、中古は別カテゴリ。
iPhone は JAN がなく「iPhone 17 Pro 256GB」のような機種＋容量の商品で、
色ごとに価格が違うときは価格の幅（price_range）が付くので、その最大値を使う。
色ごとの価格は、色の選択肢（variation）をカテゴリごとにまとめて取得する。
トレカは「BOXシュリンクあり」「カートン」などの選択肢があり、表示価格（いちばん安い選択肢）が
BOX の価格になる。「BOXシュリンクなし」もある商品だけは、シュリンクありの選択肢の価格を取り直す。
「郵送専用」「来店専用」の2つで載っている商品は、郵送の方を使う（郵送の方は JAN がないことが多い）。
Apple Watch・AirPods は JAN か型番が載っている（iPad は JAN も型番もないので使わない）。
AirPods は「保証未開始」「保証開始済」の選択肢があり、高い方（保証未開始）が未開封の価格。
同じ商品が2回載っていて片方の価格が桁違い（入力ミス）のことがあるので、同じ商品は安い方を使う。
PSA 鑑定品（ポケモンカードの PSA10）は「PSA10 リーリエ SR 119/114」のような名前で、郵送買取のみ。
"""
import html
from urllib.parse import unquote

from ..apple import apple_offer
from ..cards import card_key
from ..phones import phone_color, phone_key
from ..psa import parse_name, psa_key

ID = "toban"
NAME = "買取当番"
SHORT = "当番"
URL = "https://tobansyoji.co.jp/"

API = "https://tobansyoji.co.jp/wp-json/wc/store/v1/products"
# Nintendo Switch 2 / Nintendo Switch / PlayStation / Xbox / Meta Quest / Steam Deck / ASUS ROG / PS5 周辺機器
CATEGORIES = [184, 185, 186, 187, 188, 189, 190, 239]
# iPhone 18 / 17 / 16 / Google（Pixel）
IPHONE_CATEGORIES = [306, 207, 208, 263]
# ポケモンカード / ワンピース
CARD_CATEGORIES = [172, 174]
# Apple Watch / Apple Watch GPS+Cellular / AirPods / AirPods Max
APPLE_CATEGORIES = [168, 169, 165, 166, 170]  # 170: MacBook（型番・JAN は商品説明にある）
PSA_CATEGORY = 279
SHRINK = "BOXシュリンクあり"
NO_SHRINK = "BOXシュリンクなし"


def fetch(http):
    offers = []
    for category in CATEGORIES:
        for item, name in _read_category(http, category):
            offers.append({"jan": item["sku"].strip(), "name": name, "price": _price(item, "max"), "url": item["permalink"]})
    for category in IPHONE_CATEGORIES:
        items = list(_read_category(http, category))
        colors = _variation_prices(http, [item for item, _ in items])
        for item, name in items:
            key = phone_key(name)
            offer = {"jan": None, "key": key, "name": name, "price": _price(item, "max"), "url": item["permalink"]}
            # 色の選択肢がない商品は、どの色でも同じ価格（"colors" を付けない）
            if item["type"] == "variable":
                offer["colors"] = {c: price for text, price in colors.get(item["id"], []) if (c := phone_color(key, text))}
            offers.append(offer)
    for category in CARD_CATEGORIES:
        for item, name in _read_category(http, category):
            if "来店専用" in name:
                continue
            offers.append({"jan": item["sku"].strip() or None, "key": card_key(name), "name": name,
                           "price": _card_price(http, item), "url": item["permalink"]})
    apple = {}
    for category in APPLE_CATEGORIES:
        for item, name in _read_category(http, category):
            offer = apple_offer(name, _price(item, "max"), item["permalink"], jan=item["sku"].strip() or None,
                                text=html.unescape(item.get("description") or "") if category == 170 else "")
            same = offer["jan"] or tuple(offer["codes"])
            if same and (same not in apple or offer["price"] < apple[same]["price"]):
                apple[same] = offer
    offers += apple.values()
    offers += fetch_psa(http)
    return [o for o in offers if o["price"] > 0]


def fetch_psa(http):
    """PSA 鑑定品の出品（scraper.psa_catalog でも使う）。"""
    offers = []
    for item, name in _read_category(http, PSA_CATEGORY):
        parsed = parse_name(name)
        key = psa_key("pokemon", parsed[0], parsed[1], parsed[3]) if parsed else None
        price = _price(item, "max")
        if key and price:
            image = (item.get("images") or [{}])[0].get("src")
            offers.append({"jan": None, "key": key, "name": name, "price": price, "url": item["permalink"], "mode": "郵送",
                           "psa": {"game": "pokemon", "grade": parsed[0], "name": parsed[1], "rarity": parsed[2],
                                   "number": parsed[3], "image": image, "page": item["permalink"]}})
    return offers


def _read_category(http, category):
    """買取中の（商品データ, 商品名）を順に返す。"""
    page = 1
    while True:
        res = http.get(API, params={"category": category, "per_page": 100, "page": page})
        for item in res.json():
            # 申込不可は、今は買い取っていない商品
            if item["is_purchasable"]:
                yield item, html.unescape(item["name"])
        if page >= int(res.headers.get("X-WP-TotalPages", 1)):
            break
        page += 1


def _variation_prices(http, items):
    """{親の商品ID: [（「カラー: ブラック」のような選択肢の文字列, 価格）]}。"""
    parents = [item["id"] for item in items if item["type"] == "variable"]
    if not parents:
        return {}
    params = [("type", "variation"), ("per_page", 100)] + [("parent[]", i) for i in parents]
    result = {}
    for variation in http.get(API, params=params).json():
        if variation.get("is_purchasable"):
            result.setdefault(variation["parent"], []).append((variation.get("variation") or "", _price(variation)))
    return result


def _price(item, which="min"):
    """表示価格（which="max" なら選択肢の中の最高値）。0円は買い取っていない商品。"""
    prices = item["prices"]
    price_range = prices.get("price_range") or {}
    amount = price_range.get("max_amount") if which == "max" else None
    return int(amount or prices["price"]) // 10 ** prices["currency_minor_unit"]


def _card_price(http, item):
    terms = {t["name"]: t["slug"] for a in item.get("attributes", []) for t in a.get("terms", [])}
    if NO_SHRINK not in terms or SHRINK not in terms:
        return _price(item)
    # シュリンクなしの方が安いので、表示価格ではなくシュリンクありの選択肢の価格を使う
    for variation in item.get("variations", []):
        values = [unquote(a["value"]) for a in variation.get("attributes", [])]
        if unquote(terms[SHRINK]) in values:
            return _price(http.get(f"{API}/{variation['id']}").json())
    return 0
