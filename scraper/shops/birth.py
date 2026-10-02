"""トレカバース（PSA 鑑定品だけ）。

買取表のページ（/page/pk_purchase など）は、Google スプレッドシートを「ウェブに公開」した CSV を読んで表示しているので、
その CSV を直接読む。列は 分類1〜4・ガチャ選択肢名称・画像URL・店頭価格・大口価格・郵送価格。
名称は「リーリエ SR 119/114」「コミパラエース(受け継がれる意志) OP13-119」のように、最後がカード番号。
価格はどれも PSA10 のもので、ほかの店舗に合わせて郵送価格を使う。
「AR保証 PSA10 999」のような最低保証の行や、番号のない行（BOX など）は使わない。
名前は「ムンクコダック」「マスボ グレイシア」のような通称が多いので、カタログとは番号を中心に突き合わせる（scraper.psa_catalog）。
"""
import csv
import io
import re

from ..psa import psa_key
from ..text import parse_yen

ID = "birth"
NAME = "トレカバース"
SHORT = "バース"
URL = "https://www.torecabirth.jp/"

_CSV = "https://docs.google.com/spreadsheets/d/e/{}/pub?gid={}&single=true&output=csv"
# ゲーム（突き合わせ用の名前, 買取表のページ, CSV）
GAMES = [
    ("pokemon", "page/pk_purchase",
     _CSV.format("2PACX-1vSZJwNiow20zuY4qCVeUW6InwmXPtS-Cp2IzFeR8CGKA7IdmTOT16rR-W4rfa849zBtXzv89ZXpUJrg", 773181349)),
    ("yugioh", "page/yg_purchase",
     _CSV.format("2PACX-1vQWR8uh3M_ex-iQkx9vbjWaYSqR0EUjKnQek5VaCQDjH1AdYWGhNaoxCeKXhxa9En-1KxMmYvArD9q5", 958671698)),
    ("onepiece", "page/onepiece_purchase",
     _CSV.format("2PACX-1vQO2mQ2puvWMG_Jahwc_2gB5Puz0I-ZXrJSCT6BDEoJidoKYpjpFhnDyOWWk-DETcITZAdZSvv5RNrr", 844084145)),
]
GRADE = "PSA10"


def fetch(http):
    return fetch_psa(http)


def fetch_psa(http):
    """PSA 鑑定品の出品（scraper.psa_catalog でも使う）。"""
    offers = []
    for game, page, csv_url in GAMES:
        for row in csv.DictReader(io.StringIO(http.get(csv_url).content.decode("utf-8"))):
            title = " ".join((row.get("ガチャ選択肢名称") or "").split())
            name, _, number = title.rpartition(" ")
            price = parse_yen(row.get("郵送価格"))
            # 遊戯王は同じカードの別の版を括弧の中で分けている（「青眼の白龍(プリシク) JP001」「青眼の白龍(25th浮世絵) JP001」）。
            # psa_key は括弧の中を除くので、括弧を外して名前の一部にする
            key_name = re.sub(r"[()（）]", " ", name) if game == "yugioh" else name
            key = psa_key(game, GRADE, key_name, number) if name and "保証" not in name else None
            if key and price:
                offers.append({"jan": None, "key": key, "name": f"{GRADE} {title}", "price": price, "url": URL + page,
                               "psa": {"game": game, "grade": GRADE, "name": name, "rarity": None, "number": number,
                                       "image": row.get("画像URL") or None, "page": URL + page}})
    return offers
