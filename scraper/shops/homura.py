"""買取ホムラ。

カテゴリ（ゲームは13、iPhone は10）の中に機種ごとのサブカテゴリがある。
2026-10-13 にサイトが作り直され、一覧はブラウザで組み立てるようになった。
中身はサイトが使っている API（api.kaitori-homura.com/api/v1/products?product_sub_category_id=…）から
JSON で読む（1ページ20件。商品名・JAN・価格・画像が入っている）。
買取の受付を止めている商品（products/availability で exhausted）は使わない。
iPhone は色ごとに「【未開封】iPhone 17 Pro 256GB orange」のような名前で載っている。
トレカは JAN が載っていないので、「【BOX】ストームエメラルダ」のような名前のセット名で突き合わせる。
Android（18）は「【未開封】Galaxy A25 5G SC-53F docomo版 [ブルー]」のように色・キャリアごとに載っていて、
「【開封】」「【中古】」の付いた行は新品未開封ではないので使わない。
iPad・Apple Watch・AirPods はその他（16）にあり、JAN と型番が載っている（AirPods はイヤホンの中にある）。
PSA 鑑定品（21）はポケモンカードの PSA10 だけで、「PSA10 ブラッキーVMAX SA 095/069」のような名前で載っている。
新しい出品は「PSA10 モルペコex SAR [M5 115/081](拡張パック「アビスアイ」)」のように、番号の前にパックの記号、
後ろに収録パック名が付いている（_psa_name で前の形にそろえる）。
鑑定品の画像は、カード単体の画像（PSA のケースは写っていない）。
"""
import re

from ..apple import apple_offer
from ..cards import card_key
from ..phones import android_key, one_color, phone_key
from ..psa import parse_name, psa_key
from ..text import find_jan

ID = "homura"
NAME = "買取ホムラ"
SHORT = "ホムラ"
URL = "https://kaitori-homura.com/"

API_URL = "https://api.kaitori-homura.com/api/v1/"
GAME_CATEGORY = 13
IPHONE_CATEGORY = 10
# Switch（Switch 2 を含む） / PlayStation / Xbox / Meta Quest / その他（Steam Deck など）
GAME_SUBS = [124, 122, 126, 121, 127]
# iPhone Duo / 18 Pro / 18 Pro Max / 17 Pro / 17 Pro Max / 17 / Air / 17e / 16 Pro / 16 Pro Max / 16 / 16 Plus / 16e
IPHONE_SUBS = [194, 193, 192, 96, 97, 95, 155, 173, 100, 101, 98, 99, 156]
PIXEL_CATEGORY = 9
# Pixel 10 / 10 Pro / 10 Pro XL / 10a / 9 / 9 Pro / 9 Pro Fold / 9 Pro XL / 9a（新品だけのカテゴリ）
PIXEL_SUBS = [78, 79, 80, 184, 81, 82, 83, 84, 85]
ANDROID_CATEGORY = 18
# Galaxy / AQUOS / Xperia
ANDROID_SUBS = [158, 161, 163]
# その他（16）> iPad / AppleWatch / イヤホン・ヘッドホン・スピーカー（AirPods だけ使う）
APPLE_SUBS = [(16, 137), (16, 174), (16, 140)]
# PSA（21）> PSA
PSA_CATEGORY, PSA_SUB = 21, 182
CARD_CATEGORY = 14
# ポケモンカード（シュリンク有りのBOX・スペシャルセット） / ワンピース 未開封BOX / 遊戯王 未開封BOX / ドラゴンボールBOX
CARD_SUBS = [128, 130, 132, 159, 171]
MAX_PAGES = 20


def fetch(http):
    offers = []
    for sub in GAME_SUBS:
        for name, jan, price, url in _read_list(http, GAME_CATEGORY, sub):
            offers.append({"jan": jan, "name": name, "price": price, "url": url})
    for sub in IPHONE_SUBS:
        for name, jan, price, url in _read_list(http, IPHONE_CATEGORY, sub):
            if "未開封" in name:
                key = phone_key(name)
                offers.append({"jan": jan, "key": key, "name": name, "price": price, "url": url,
                               "colors": one_color(key, name, price)})
    for sub in PIXEL_SUBS:
        for name, jan, price, url in _read_list(http, PIXEL_CATEGORY, sub):
            key = phone_key(name)
            offers.append({"jan": jan, "key": key, "name": name, "price": price, "url": url,
                           "colors": one_color(key, name, price)})
    for sub in ANDROID_SUBS:
        for name, jan, price, url in _read_list(http, ANDROID_CATEGORY, sub):
            key = android_key(name)
            if key and not re.search(r"【(開封|中古)", name):
                offers.append({"jan": jan, "key": key, "name": name, "price": price, "url": url,
                               "colors": one_color(key, name, price)})
    for category, sub in APPLE_SUBS:
        for name, jan, price, url in _read_list(http, category, sub):
            if sub != 140 or "AirPods" in name or "Mac" in name:  # 140 はイヤホンなどだが、AirPods と MacBook も入っている
                offers.append(apple_offer(name, price, url, jan=jan))
    offers += fetch_psa(http)
    for sub in CARD_SUBS:
        for name, jan, price, url in _read_list(http, CARD_CATEGORY, sub):
            offers.append({"jan": jan, "key": card_key(name), "name": name, "price": price, "url": url})
    return [o for o in offers if (o["jan"] or o.get("key") or o.get("codes")) and o["price"] > 0]


def fetch_psa(http):
    """PSA 鑑定品の出品（scraper.psa_catalog でも使う）。"""
    offers = []
    for name, jan, price, url, image in _read_list(http, PSA_CATEGORY, PSA_SUB, with_image=True):
        parsed = parse_name(_psa_name(name))
        key = psa_key("pokemon", parsed[0], parsed[1], parsed[3]) if parsed else None
        if key:
            offers.append({"jan": None, "key": key, "name": name, "price": price, "url": url, "mode": "郵送",
                           "psa": {"game": "pokemon", "grade": parsed[0], "name": parsed[1], "rarity": parsed[2],
                                   "number": parsed[3], "image": image, "page": url}})
    return offers


def _psa_name(name):
    """「PSA10 モルペコex SAR [M5 115/081](拡張パック「アビスアイ」)」→「PSA10 モルペコex SAR 115/081」。"""
    name = re.sub(r"\([^()]*「[^()]*\)", " ", name)  # (拡張パック「…」) の収録パック名
    name = re.sub(r"\s*\[(?:[A-Za-z0-9]+ )?([^\]]*/[^\]]*)\]", r" \1", name)  # [M5 115/081] のパックの記号
    name = re.sub(r"(?<![A-Za-z])[A-Z]{1,3}\s*:\s*|\s*:\s*", " ", name)  # 「SR: SA」「C: マスターボールミラー」
    # 「ゼニガメ マスターボールミラー」→「ゼニガメ(マスターボールミラー)」（括弧の中は名前として比べない）
    name = re.sub(r"\s*((?:マスター|モンスター)ボールミラー)", r"(\1)", name)
    return " ".join(name.split())


def _read_list(http, category, sub, with_image=False):
    """（商品名, JAN, 価格, 商品ページのURL）を順に返す。with_image なら、最後に商品の画像の URL も付ける
    （PSA 鑑定品の画像はカード単体の画像）。category は API では使わない（サブカテゴリの番号だけで決まる）。"""
    for page in range(1, MAX_PAGES + 1):
        data = http.get(API_URL + "products", params={"product_sub_category_id": sub, "page": page}).json()
        items = data["data"]
        exhausted = _exhausted(http, [item["id"] for item in items])
        for item in items:
            if item["id"] in exhausted or not item.get("price"):
                continue
            # iPhone・トレカの JAN の欄は「514549995648300」のような店独自の15桁の番号なので、JAN として使わない
            row = (item["name"].strip(), find_jan(item.get("jan_code") or ""), int(item["price"]),
                   f"{URL}products/{item['id']}")
            if with_image:
                row += (item.get("image_url"),)
            yield row
        if page >= data["meta"]["total_pages"]:
            break


def _exhausted(http, ids):
    """買取の受付を止めている（上限に達した）商品の ID。"""
    if not ids:
        return set()
    data = http.get(API_URL + "products/availability", params={"product_ids[]": ids}).json()
    return {a["product_id"] for a in data["data"] if a.get("exhausted")}
