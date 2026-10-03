"""買取ホムラ。

カテゴリ（ゲームは13、iPhone は10）の中に機種ごとのサブカテゴリがあり、
一覧は1ページ40件でページ送りがある。
各商品の「追加」ボタンに商品IDと価格が埋め込まれていて、JANはカード内に表示されている。
iPhone は色ごとに「【未開封】iPhone 17 Pro 256GB orange」のような名前で載っている。
トレカは JAN が載っていないので、「【BOX】ストームエメラルダ」のような名前のセット名で突き合わせる。
Android（18）は「【未開封】Galaxy A25 5G SC-53F docomo版 [ブルー]」のように色・キャリアごとに載っていて、
「【開封】」「【中古】」の付いた行は新品未開封ではないので使わない。
iPad・Apple Watch・AirPods はその他（16）にあり、JAN と型番が載っている（AirPods はイヤホンの中にある）。
PSA 鑑定品（21）はポケモンカードの PSA10 だけで、「PSA10 ブラッキーVMAX SA 095/069」のような名前で載っている。
鑑定品の画像は、カード単体の画像（PSA のケースは写っていない）。
"""
import re
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from ..apple import apple_offer
from ..cards import card_key
from ..phones import android_key, one_color, phone_key
from ..psa import parse_name, psa_key
from ..text import find_jan

ID = "homura"
NAME = "買取ホムラ"
SHORT = "ホムラ"
URL = "https://kaitori-homura.com/"

LIST_URL = "https://kaitori-homura.com/products"
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
        parsed = parse_name(name)
        key = psa_key("pokemon", parsed[0], parsed[1], parsed[3]) if parsed else None
        if key:
            offers.append({"jan": None, "key": key, "name": name, "price": price, "url": url, "mode": "郵送",
                           "psa": {"game": "pokemon", "grade": parsed[0], "name": parsed[1], "rarity": parsed[2],
                                   "number": parsed[3], "image": image, "page": url}})
    return offers


def _read_list(http, category, sub, with_image=False):
    """（商品名, JAN, 価格, 商品ページのURL）を順に返す。with_image なら、最後に商品の画像の URL も付ける
    （PSA 鑑定品の画像はカード単体の画像）。"""
    for page in range(1, MAX_PAGES + 1):
        params = {
            "q[product_sub_category_id_eq]": sub,
            "q[product_sub_category_product_category_id_eq]": category,
            "page": page,
        }
        soup = BeautifulSoup(http.get(LIST_URL, params=params).content, "html.parser")
        buttons = soup.select("button[data-product-id][data-product-price]")
        for button in buttons:
            if button.get("aria-disabled") == "true":
                continue
            card = button.find_parent(lambda tag: tag.find("h5") is not None)
            if card is None:
                continue
            row = (
                card.find("h5").get_text(strip=True),
                find_jan(card.get_text(" ")),
                int(button["data-product-price"]),
                f"{URL}products/{button['data-product-id']}",
            )
            if with_image:
                img = card.parent.find("img")  # 画像はカード名の欄の隣にある
                row += (urljoin(URL, img.get("data-src") or img["src"]) if img and (img.get("data-src") or img.get("src")) else None,)
            yield row
        if not buttons or not _has_page(soup, page + 1):
            break


def _has_page(soup, page):
    pattern = re.compile(rf"[?&]page={page}(?:&|$)")
    return any(pattern.search(a["href"]) for a in soup.select("a[href]"))
