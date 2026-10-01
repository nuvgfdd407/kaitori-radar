"""買取ホムラ。

ゲームカテゴリ（ID 13）の中に Switch / PlayStation / Xbox のサブカテゴリがあり、
一覧は1ページ40件でページ送りがある。
各商品の「追加」ボタンに商品IDと価格が埋め込まれていて、JANはカード内に表示されている。
"""
import re

from bs4 import BeautifulSoup

from ..text import find_jan

ID = "homura"
NAME = "買取ホムラ"
SHORT = "ホムラ"
URL = "https://kaitori-homura.com/"

LIST_URL = "https://kaitori-homura.com/products"
GAME_CATEGORY = 13
# Switch（Switch 2 を含む） / PlayStation / Xbox / Meta Quest / その他（Steam Deck など）
SUB_CATEGORIES = [124, 122, 126, 121, 127]
MAX_PAGES = 10


def fetch(http):
    offers = []
    for sub in SUB_CATEGORIES:
        for page in range(1, MAX_PAGES + 1):
            params = {
                "q[product_sub_category_id_eq]": sub,
                "q[product_sub_category_product_category_id_eq]": GAME_CATEGORY,
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
                offers.append({
                    "jan": find_jan(card.get_text(" ")),
                    "name": card.find("h5").get_text(strip=True),
                    "price": int(button["data-product-price"]),
                    "url": f"{URL}products/{button['data-product-id']}",
                })
            if not buttons or not _has_page(soup, page + 1):
                break
    return [o for o in offers if o["jan"] and o["price"] > 0]


def _has_page(soup, page):
    pattern = re.compile(rf"[?&]page={page}(?:&|$)")
    return any(pattern.search(a["href"]) for a in soup.select("a[href]"))
