"""トレカラウンジ。

シングルカードの PSA10 の一覧（/products/<ゲーム>/single?grade=PSA10）を使う。1ページ100件で、続きは &page=N。
最後のページより先を指定すると最後のページがもう一度返ってくるので、「全N件」の件数で止める。
ページに埋め込まれたデータ（self.__next_f.push の中）に、商品ごとに
{"productName", "modelNumber"（カード番号）, "rarity", "seriesCode", "grades": [{"grade", "buyPrice"}], "publicId"} がある。
「AR以上最低保証」のような、カードではない行（番号がない）は使わない。
"""
import json
import re

from ..psa import psa_key

ID = "lounge"
NAME = "トレカラウンジ"
SHORT = "ラウンジ"
MODE = "郵送"  # 店名の後ろに付ける買取方法
URL = "https://kaitori.toreca-lounge.com/"

# ゲーム（サイトの URL の名前, 突き合わせ用の名前）
GAMES = [("pokemon", "pokemon"), ("onepiece", "onepiece"), ("yugioh", "yugioh")]
PAGE_SIZE = 100
MAX_PAGES = 20


def fetch(http):
    return fetch_psa(http)


def fetch_psa(http):
    """PSA 鑑定品の出品（scraper.psa_catalog でも使う）。"""
    offers = []
    for path, game in GAMES:
        for item in _read_psa(http, path):
            for grade in item.get("grades") or []:
                price = int(grade.get("buyPrice") or 0)
                # レアリティ（「SEC(Manga)」など）にもパラレルかどうかが書かれているので、名前と一緒に渡す
                key = psa_key(game, grade.get("grade"), f"{item.get('productName')} {item.get('rarity') or ''}",
                              item.get("modelNumber"))
                if key and price:
                    offers.append({"jan": None, "key": key, "name": _display(item, grade["grade"]), "price": price,
                                   "url": f"{URL}product/{item['publicId']}", "psa": _info(item, game, grade["grade"])})
    return offers


def _read_psa(http, path):
    seen = set()
    for page in range(1, MAX_PAGES + 1):
        html = http.get(f"{URL}products/{path}/single", params={"grade": "PSA10", "page": page}).text
        items = [i for i in _items(html) if i.get("productFormat") == "PSA"]
        new = [i for i in items if i["publicId"] not in seen]
        yield from new
        seen.update(i["publicId"] for i in new)
        total = re.search(r"全\s*(\d+)\s*件", html)
        if not new or (total and len(seen) >= int(total.group(1))) or len(items) < PAGE_SIZE:
            break


def _items(html):
    """ページに埋め込まれたデータから、商品の辞書を取り出す。"""
    chunks = re.findall(r'self\.__next_f\.push\(\[1,"(.*?)"\]\)</script>', html, re.S)
    payload = "".join(json.loads(f'"{c}"') for c in chunks)
    decoder = json.JSONDecoder()
    items = []
    for m in re.finditer(r'\{"productFormat"', payload):
        item, _ = decoder.raw_decode(payload, m.start())
        items.append(item)
    return items


def _display(item, grade):
    parts = [grade, item.get("productName"), item.get("rarity"), item.get("modelNumber")]
    return " ".join(p for p in parts if p)


def _info(item, game, grade):
    """カタログを作るときに使う、カードの情報。"""
    return {"game": game, "grade": grade, "name": item.get("productName"), "rarity": item.get("rarity") or None,
            "number": item.get("modelNumber"), "set": item.get("seriesCode") or None,
            "image": item.get("imageUrl"), "page": f"{URL}product/{item['publicId']}"}
