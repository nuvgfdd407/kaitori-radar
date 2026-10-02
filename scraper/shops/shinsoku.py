"""シンソク（PSA 鑑定品と、トレカの未開封BOX）。

宅配買取の「簡単カート買取」（/yuso-kaitori）が読んでいる API（/api/items?postal_only=true&type=PSA&brand=…）を使う。
BOX は type=BOX で、名前は「強化拡張パック「ポケモンカード151」(SV2a)」のような形なので、「」の中をセット名として
カタログの "names" と突き合わせる（「」がない古いBOXは名前全体）。
1回に limit 件ずつ、page=0 から順に、has_more が false になるまで読む。
1件に name（「ロイヤルマスク(SR仕様)」）・rarity・modelno（カード番号）・tags（「PSA10」など）・
postal_purchase_price_s / _a / _am（状態ごとの郵送買取価格。s が最も状態のよいときの価格）・image_url_public がある。
ほかの店舗に合わせて、PSA10 だけ、最も状態のよいときの価格（s）を使う。
"""
import re

from ..cards import card_key
from ..psa import psa_key

ID = "shinsoku"
NAME = "シンソク"
SHORT = "シンソク"
MODE = "郵送・店頭"  # 店名の後ろに付ける買取方法（郵送と店頭で同じ価格）
URL = "https://shinsoku-tcg.com/"

LIST_URL = URL + "yuso-kaitori"
API_URL = URL + "api/items"
# サイトのブランド名, 突き合わせ用の名前
BRANDS = [("ポケモン", "pokemon"), ("ワンピース", "onepiece"), ("遊戯王", "yugioh")]
GRADE = "PSA10"
LIMIT = 40   # サイトと同じ件数
MAX_PAGES = 50


def fetch(http):
    return fetch_psa(http) + fetch_box(http)


def fetch_psa(http):
    """PSA 鑑定品の出品（scraper.psa_catalog でも使う）。"""
    return [o for brand, game in BRANDS for o in map(lambda item: _offer(item, game), _items(http, "PSA", brand)) if o]


def fetch_box(http):
    """トレカの未開封BOXの出品。"""
    offers = []
    for brand, _ in BRANDS:
        for item in _items(http, "BOX", brand):
            price = item.get("postal_purchase_price_s")
            name = item.get("name") or ""
            if price and item.get("is_postal_buy_target"):
                offers.append({"jan": None, "key": card_key(box_set_name(name)), "name": name, "price": int(price),
                               "url": LIST_URL})
    return offers


def box_set_name(name):
    """「強化拡張パック「ポケモンカード151」(SV2a)」→「ポケモンカード151」。「」『』がなければ名前のまま。"""
    m = re.search(r"[「『｢]([^」』｣]+)[」』｣]", name)
    return m.group(1) if m else name


def _items(http, kind, brand):
    for page in range(MAX_PAGES):
        params = {"postal_only": "true", "sort": "price_desc", "type": kind, "brand": brand, "page": page, "limit": LIMIT}
        data = http.get(API_URL, params=params).json()["data"]
        yield from data.get("items") or []
        if not data.get("has_more"):
            break


def _offer(item, game):
    grades = [t.get("label") or "" for t in item.get("tags") or []]
    price = item.get("postal_purchase_price_s")
    if GRADE not in grades or not price or not item.get("is_postal_buy_target"):
        return None
    name, rarity, number = item.get("name") or "", item.get("rarity") or "", item.get("modelno") or ""
    # ワンピースは同じ番号の別の版を括弧の中で分けている（「(パラレル/金背景)」「(パラレル/銀背景)」）。
    # psa_key は括弧の中を除くので、括弧を外して名前の一部にする
    key_name = re.sub(r"[()（）]", " ", name) if game == "onepiece" else name
    key = psa_key(game, GRADE, f"{key_name} {rarity}", number)
    if not key:
        return None
    rarity = rarity if re.fullmatch(r"[A-Z]+", rarity) and rarity != "P" else None  # 「P」はプロモの印
    return {"jan": None, "key": key, "name": " ".join(p for p in [GRADE, name, rarity, number] if p), "price": int(price),
            "url": LIST_URL,
            "psa": {"game": game, "grade": GRADE, "name": name, "rarity": rarity, "number": number,
                    "image": item.get("image_url_public") or None, "page": LIST_URL}}
