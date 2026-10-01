"""買取ルデヤ。

カテゴリページに全商品が載っている（ページ送りなし）。
商品カードに「新品」「中古」のバッジがあるので、新品だけを取る。
"""
from bs4 import BeautifulSoup

from ..text import find_jan, parse_yen

ID = "rudeya"
NAME = "買取ルデヤ"
SHORT = "ルデヤ"
URL = "https://kaitori-rudeya.com/"

# Nintendo Switch 2 / Nintendo Switch / PlayStation5 / Xbox / PlayStation Portal / Steam / ASUS ROG /
# Meta Quest / PlayStation VR / PICO 4 / Legion Go
PAGES = [f"https://kaitori-rudeya.com/category/detail/{i}" for i in (214, 1, 2, 3, 159, 55, 136, 42, 120, 121, 160)]


def fetch(http):
    offers = []
    for page in PAGES:
        soup = BeautifulSoup(http.get(page).content, "html.parser")
        for card in soup.select("article.pgrid-card"):
            badge = card.select_one(".product-card-cond-badge")
            if badge is None or "is-new" not in badge.get("class", []):
                continue
            link = card.select_one("a.product-card-name-link")
            jan = card.select_one(".product-card-jan-text")
            price = card.select_one(".product-card-price-value")
            if not (link and jan and price):
                continue  # 「近日公開」など価格が出ていない商品
            offers.append({
                "jan": find_jan(jan.get_text()),
                "name": link.get_text(strip=True),
                "price": parse_yen(price.get_text()),
                "url": link["href"],
            })
    return [o for o in offers if o["jan"] and o["price"]]
