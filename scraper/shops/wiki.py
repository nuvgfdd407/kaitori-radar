"""買取wiki。

機種別のページが新しい機種に対応していないので、メーカー別の一覧を使う。
1ページ28件で、2ページ目以降は /brand/<メーカー>/<ページ番号>。
中古品も新品と同じJANで載っていて、商品名に「中古」と入っているので除外する。
"""
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from ..text import find_jan, parse_yen

ID = "wiki"
NAME = "買取wiki"
SHORT = "買取wiki"
URL = "https://gamekaitori.jp/"

BRANDS = ["nintendo", "sony", "microsoft", "Oculus"]
MAX_PAGES = 20


def fetch(http):
    offers = []
    for brand in BRANDS:
        for page in range(1, MAX_PAGES + 1):
            url = f"{URL}brand/{brand}/" + (str(page) if page > 1 else "")
            soup = BeautifulSoup(http.get(url).content, "html.parser")
            cards = soup.select("div.pro_list")
            for card in cards:
                link = card.select_one("li.sub-pro-name a[href]")
                price = card.select_one("li.sub-pro-jia span")
                if link is None or price is None:
                    continue
                name = link.get_text(" ", strip=True)
                if "中古" in name:
                    continue
                jan_line = next((li for li in card.select("li.sub-pro-name") if "JAN" in li.get_text()), None)
                offers.append({
                    "jan": find_jan(jan_line.get_text() if jan_line else name),
                    "name": name,
                    "price": parse_yen(price.get_text()),
                    "url": urljoin(URL, link["href"]),
                })
            if not cards or not soup.select_one(f'a[href$="/brand/{brand}/{page + 1}"]'):
                break
    return [o for o in offers if o["jan"] and o["price"]]
