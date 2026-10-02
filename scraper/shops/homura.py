"""買取ホムラ。

カテゴリ（ゲームは13、iPhone は10）の中に機種ごとのサブカテゴリがあり、
一覧は1ページ40件でページ送りがある。
各商品の「追加」ボタンに商品IDと価格が埋め込まれていて、JANはカード内に表示されている。
iPhone は色ごとに「【未開封】iPhone 17 Pro 256GB orange」のような名前で載っている。
トレカは JAN が載っていないので、「【BOX】ストームエメラルダ」のような名前のセット名で突き合わせる。
"""
import re

from bs4 import BeautifulSoup

from ..cards import card_key
from ..iphone import iphone_key, one_color
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
CARD_CATEGORY = 14
# ポケモンカード（シュリンク有りのBOX・スペシャルセット） / ワンピース 未開封BOX / 遊戯王 未開封BOX / ドラゴンボールBOX
CARD_SUBS = [128, 130, 132, 159, 171]
MAX_PAGES = 10


def fetch(http):
    offers = []
    for sub in GAME_SUBS:
        for name, jan, price, url in _read_list(http, GAME_CATEGORY, sub):
            offers.append({"jan": jan, "name": name, "price": price, "url": url})
    for sub in IPHONE_SUBS:
        for name, jan, price, url in _read_list(http, IPHONE_CATEGORY, sub):
            if "未開封" in name:
                key = iphone_key(name)
                offers.append({"jan": jan, "key": key, "name": name, "price": price, "url": url,
                               "colors": one_color(key, name, price)})
    for sub in CARD_SUBS:
        for name, jan, price, url in _read_list(http, CARD_CATEGORY, sub):
            offers.append({"jan": jan, "key": card_key(name), "name": name, "price": price, "url": url})
    return [o for o in offers if (o["jan"] or o.get("key")) and o["price"] > 0]


def _read_list(http, category, sub):
    """（商品名, JAN, 価格, 商品ページのURL）を順に返す。"""
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
            yield (
                card.find("h5").get_text(strip=True),
                find_jan(card.get_text(" ")),
                int(button["data-product-price"]),
                f"{URL}products/{button['data-product-id']}",
            )
        if not buttons or not _has_page(soup, page + 1):
            break


def _has_page(soup, page):
    pattern = re.compile(rf"[?&]page={page}(?:&|$)")
    return any(pattern.search(a["href"]) for a in soup.select("a[href]"))
