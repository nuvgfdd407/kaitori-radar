"""トレカバンク（PSA 鑑定品だけ。ポケモンカード）。

郵送買取の一覧（/mail_buy_list、1ページ100件で続きは ?page=N）を使う。
商品ごとに <li class="item" data-id="…"> があり（画像表示とリスト表示で同じ商品が2回出てくる）、
名前（「アセロラ[SM2+] SR 056/049」のように、カード名[収録弾] レアリティ カード番号）・
種類（「PSA10」「未開封BOX（シュリンク付き）」）・価格・残り数が載っている。
受付を終えた商品（class に closed、「受付終了」）は使わない。
"""
import re
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from ..psa import psa_key
from ..text import parse_yen

ID = "torecabank"
NAME = "トレカバンク"
SHORT = "バンク"
URL = "https://store.torecabank.com/"

LIST_URL = URL + "mail_buy_list"
MAX_PAGES = 20


def fetch(http):
    return fetch_psa(http)


def fetch_psa(http):
    """PSA 鑑定品の出品（scraper.psa_catalog でも使う）。"""
    offers, seen = [], set()
    for page in range(1, MAX_PAGES + 1):
        soup = BeautifulSoup(http.get(LIST_URL, params={"page": page} if page > 1 else None).content, "html.parser")
        items = [i for i in soup.select("li.item[data-id]") if i["data-id"] not in seen]
        for item in items:
            if item["data-id"] in seen:
                continue  # 画像表示とリスト表示の2回目
            seen.add(item["data-id"])
            offer = _offer(item)
            if offer:
                offers.append(offer)
        if not items or not soup.select_one(f'a[href*="page={page + 1}"]'):
            break
    return offers


def _offer(item):
    tag = item.select_one(".tag")
    grade = re.fullmatch(r"PSA\s*\d+", tag.get_text(strip=True)) if tag else None
    title = " ".join(item.select_one(".name").get_text(" ").split()) if item.select_one(".name") else ""
    price = parse_yen(item.select_one(".price").get_text()) if item.select_one(".price") else None
    if not grade or "closed" in item.get("class", []) or not price:
        return None
    grade = grade.group(0).replace(" ", "")
    words = title.split()
    if len(words) < 2:
        return None
    number = words[-1]
    rarity = words[-2] if len(words) >= 3 else ""
    name = " ".join(words[:-2] if rarity else words[:-1])
    key = psa_key("pokemon", grade, f"{name} {rarity}", number)
    img = item.find("img")
    return key and {"jan": None, "key": key, "name": f"{grade} {title}", "price": price, "url": LIST_URL,
                    "psa": {"game": "pokemon", "grade": grade, "name": name,
                            "rarity": rarity if rarity not in ("", "-") else None, "number": number,
                            "image": urljoin(URL, img["src"]) if img and img.get("src") else None, "page": LIST_URL}}
