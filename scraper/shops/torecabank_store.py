"""トレカバンクの店頭買取の価格（PSA 鑑定品だけ。ポケモンカード）。

「本日の店頭買取表」（/kaitori_list）のページに、全商品のデータが const allProducts = [...] として埋め込まれている。
1件に product_master_name（「(PSA10)アセロラ[SM2+]」）・product_master_key1（レアリティ）・
product_master_key2（カード番号）・product_type_name（「PSA10」「未開封BOX（シュリンク付き）」）・buy_price・
remaining_quantity（あと何枚買い取るか。0 は受付終了）・image_path がある。
"""
import json
import re
from urllib.parse import urljoin

from ..psa import psa_key
from . import torecabank

ID = "torecabank_store"
NAME = torecabank.NAME
SHORT = torecabank.SHORT
MODE = "店頭"
URL = torecabank.URL

LIST_URL = URL + "kaitori_list"


def fetch(http):
    return fetch_psa(http)


def fetch_psa(http):
    """PSA 鑑定品の出品（scraper.psa_catalog でも使う）。"""
    html = http.get(LIST_URL).content.decode("utf-8")  # 文字コードがヘッダーにないので、UTF-8 として読む
    m = re.search(r"const allProducts = (\[.*?\]);\s*\n", html, re.S)
    if not m:
        raise RuntimeError("店頭買取表のデータが見つかりません")
    offers = []
    for item in json.loads(m.group(1)):
        grade = (item.get("product_type_name") or "").replace(" ", "")
        price = int(item.get("buy_price") or 0)
        if not re.fullmatch(r"PSA\d+", grade) or not price or str(item.get("remaining_quantity")) == "0":
            continue
        name = re.sub(r"^\(PSA\d+\)", "", item.get("product_master_name") or "").strip()
        rarity = item.get("product_master_key1") or ""
        number = item.get("product_master_key2") or ""
        key = psa_key("pokemon", grade, f"{name} {rarity}", number)
        if key:
            image = item.get("image_path")
            offers.append({"jan": None, "key": key, "name": " ".join(x for x in [grade, name, rarity, number] if x),
                           "price": price, "url": LIST_URL,
                           "psa": {"game": "pokemon", "grade": grade, "name": name,
                                   "rarity": rarity if rarity not in ("", "-") else None, "number": number,
                                   "image": urljoin(URL, image) if image else None, "page": LIST_URL}})
    return offers
