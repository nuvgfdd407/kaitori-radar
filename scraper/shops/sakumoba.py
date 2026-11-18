"""サクモバ買取。

ジャンルごとの一覧のページ（/smartphone/iphone/ など）に、そのジャンルの全機種の行が並んでいる（ふつうの HTML。
「もっと見る」で隠れている行も最初から入っている）。1行は「Apple Store版 SIMフリー iPhone17 Pro シルバー 256GB MG854J/A」
のような商品名（キャリア・色・容量・型番入り）と、「新品買取価格」「中古買取価格」の2つの価格。新品の方だけを使い、
0円の行（買取していない）は飛ばす。一覧の上の「買取価格更新日」が30日以上前のページは使わない。
- iPhone: 色・容量ごとの行。「Apple Store版 SIMフリー」の行だけを使う（au・docomo などのキャリア版の行は使わない）
- Pixel: 色・容量ごとの行。「国内版SIMフリー」の行だけを使う
- Galaxy・Xperia・AQUOS: 色・容量・キャリアごとの行。キャリアは商品名（「AU版SIMフリー」や SC-55G のような型番）から
  android_key が読む。SIMフリーは「国内版SIMフリー」の行だけ（「mineo版SIMフリー」の行は使わない）
- iPad・Mac・Apple Watch・AirPods: 商品名の Apple の型番で突き合わせる。iPad の Cellular 版は SIMフリーの行と
  キャリア版の行に同じ型番が書かれているので、キャリア名の入った行は使わない。型番の書き間違い（色・容量違いの行に同じ型番）が
  あるので、iPad の2つ以上の行に書かれた型番は、カタログの同じ機種の中から名前の容量・色に合う商品の型番に選び直す。
  型番のない iPad mini（第6世代）の行も同じように名前で選ぶ。それ以外で違う価格の行に出てくる型番は使わない。
  「MWRR3JA」のように / の抜けた型番は直して読む。AirPods Max（2020年モデル）は全色の行にグリーンの型番 MGYN3J/A が
  書かれているので、名前の色の型番に直す
- ゲーム機・ROG Ally などの携帯ゲーム機（game.sakumoba.jp）・Meta Quest・Steam Deck: 「Nintendo Switch 2 BEE-S-KB6CA」の
  ように型番が書かれていて、JAN は PS5 の一部にしかない。JAN のない行は、カタログの "model"（Meta Quest は型番を除いた
  商品名）で JAN を探す。Steam Deck は型番がないので、「Steam Deck OLED Zen2 ホワイト 1TB」をカタログの名前の形
  （「Steam Deck 有機EL（OLED）1TB ホワイト」、OLED でないものは「Steam Deck LCD 256GB」）に直して探す。
  「Nintendo Switch 2019年モデル グレー」の行にはネオンの型番 HAD-S-KABAA が書かれているので、グレーの HAD-S-KAAAA に直す
Garmin などの腕時計・ゲーミングノート PC など、カタログにないジャンルのページは開かない。
"""
import re
import unicodedata
from collections import Counter
from datetime import date, timedelta
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from ..apple import apple_offer
from ..common import CATALOG, load_json
from ..phones import android_key, one_color, phone_colors, phone_key
from ..text import find_jan, parse_yen

ID = "sakumoba"
NAME = "サクモバ買取"
SHORT = "サクモバ"
URL = "https://sakumoba.jp/"

IPHONE_PAGE = URL + "smartphone/iphone/"
PIXEL_PAGE = URL + "smartphone/google-pixel/"
ANDROID_PAGES = [URL + "smartphone/" + p + "/" for p in ("galaxy", "xperia", "aquos")]
APPLE_PAGES = [URL + p for p in ("tablet/ipad/", "mac/", "wearable/apple-watch/", "accessories/headphones-speakers/airpods/")]
# ゲーム機・ROG Ally などの携帯ゲーム機（asus・lenovo）・Steam Deck・Meta Quest
GAME_PAGES = (["https://game.sakumoba.jp/" + p + "/" for p in ("nintendo", "playstation", "xbox", "asus", "lenovo", "steam-deck")]
              + [URL + "accessories/meta-vr/"])
# カタログで型番（"model"）や商品名から JAN を探すシリーズ
GAME_SERIES = {"switch2", "switch", "ps5", "psvr2", "xbox", "vr", "gaming-pc"}
IPAD_SERIES = {"ipad", "ipad-air", "ipad-pro"}
STALE_DAYS = 30
# au と UQ は型番（MUUQ2J/A など）の中の文字に当たらないように、前後に英数字がないものだけ
_CARRIER = re.compile(r"(?<![A-Z0-9])(?:au|UQ)(?![A-Z0-9])|docomo|soft\s*bank|楽天|y!?\s*mobile|J:COM|ahamo|mineo", re.IGNORECASE)
# ゲーム機の型番（「BEE-S-KB6CA」「CFI-2000A01」「83E10027JP」など）と、商品名から除く型番（「899-00594-01」など）
_MODEL = re.compile(r"[A-Z0-9]+(?:-[A-Z0-9]+)*")
_HYPHENATED = re.compile(r"[A-Z0-9]+(?:-[A-Z0-9]+)+")
_JA = re.compile(r"(?<![A-Z0-9/])([A-Z0-9]{5})JA(?![A-Z0-9])")
# AirPods Max（2020年モデル）の色ごとの型番
_AIRPODS_MAX = {"グリーン": "MGYN3J/A", "シルバー": "MGYJ3J/A", "スペースグレー": "MGYH3J/A", "スカイブルー": "MGYL3J/A",
                "ピンク": "MGYM3J/A"}
# カタログの iPad の名前「iPad Air 13インチ（M3）128GB Wi-Fi + Cellular スターライト」→ 機種・容量・通信方式など・色
_IPAD_NAME = re.compile(r"(.+?)(\d+[GT]B) (.+) (\S+)")
_CAPACITY = re.compile(r"\d+[GT]B")
# 型番のない iPad の行の商品名の先頭 → カタログの機種（容量の前, 通信方式など）
_IPAD_NO_CODE = {"iPad mini6 Wi-Fiモデル": ("iPad mini（第6世代）", "Wi-Fi"),
                 "iPad mini6 Wi-Fi + Cellular SIMフリー": ("iPad mini（第6世代）", "Wi-Fi + Cellular")}
# 「STEAM DECK OLED ZEN2 ホワイト 1TB」（NFKC・大文字にしたもの）
_STEAM_DECK = re.compile(r"STEAM DECK (OLED )?ZEN2 (ブラック|ホワイト) (\d+[GT]B)")


def fetch(http):
    offers = []
    phones = {}  # {key: (最初の行の名前, ページ, {色: 価格})}

    def add_phone(key, name, price, url):
        for color in one_color(key, name, price):  # 同じ色が2回出てきたら高い方
            colors = phones.setdefault(key, (name, url, {}))[2]
            colors[color] = max(price, colors.get(color, 0))

    for name, price, url in _read_rows(http, IPHONE_PAGE):
        key = phone_key(name)
        if name.startswith("Apple Store版") and "SIMフリー" in name and key and phone_colors(key):
            add_phone(key, name, price, url)
    for name, price, url in _read_rows(http, PIXEL_PAGE):
        key = phone_key(name)
        if "国内版SIMフリー" in name and key and phone_colors(key):
            add_phone(key, name, price, url)
    for page in ANDROID_PAGES:
        for name, price, url in _read_rows(http, page):
            key = android_key(name)
            if key and (not key.endswith(" SIMフリー") or "国内版" in name):  # mineo版などは SIMフリーと読まれるので外す
                add_phone(key, name, price, url)
    for key, (name, url, colors) in phones.items():
        offers.append({"jan": None, "key": key, "name": name, "price": max(colors.values()), "url": url, "colors": colors})

    products = load_json(CATALOG)["products"]
    apple = [apple_offer(_apple_name(name), price, url)
             for page in APPLE_PAGES for name, price, url in _read_rows(http, page) if not _CARRIER.search(name)]
    _fix_ipads(apple, products)
    prices = {}  # {型番: その型番が書かれた行の価格}。価格が2つ以上なら書き間違いなので使わない
    for offer in apple:
        for code in offer["codes"]:
            prices.setdefault(code, set()).add(offer["price"])
    for offer in apple:
        offer["codes"] = {code: price for code, price in offer["codes"].items() if len(prices[code]) == 1}
    offers += apple

    models, names = _catalog_games(products)
    for page in GAME_PAGES:
        for name, price, url in _read_rows(http, page):
            text = unicodedata.normalize("NFKC", name).upper()
            if text.startswith("NINTENDO SWITCH 2019年モデル グレー"):  # ネオンの型番が書かれている
                text = text.replace("HAD-S-KABAA", "HAD-S-KAAAA")
            deck = _STEAM_DECK.fullmatch(text)
            if deck:  # 型番がないので、カタログの名前の形にする（黒はカタログの名前に色がない）
                text = f"STEAM DECK {'有機EL(OLED)' if deck[1] else 'LCD'} {deck[3]}" + (" ホワイト" if deck[2] == "ホワイト" else "")
            jan = (find_jan(name) or next((models[m] for m in _MODEL.findall(text) if m in models), None)
                   or names.get(re.sub(r"\s", "", _HYPHENATED.sub(" ", text))))
            offers.append({"jan": jan, "name": name, "price": price, "url": url})
    return offers


def _read_rows(http, page):
    """一覧の（商品名, 新品買取価格, 商品のページ）を順に返す。0円の行と、更新日が古いページは飛ばす。"""
    soup = BeautifulSoup(http.get(page).content, "html.parser")
    updated = soup.select_one(".product-price-head__date time[datetime]")
    if updated and date.fromisoformat(updated["datetime"]) <= date.today() - timedelta(days=STALE_DAYS):
        return
    for row in soup.select("tr.lb_4"):
        name, price, link = row.select_one(".lb_4tsp2"), row.select_one(".lb_5l1sp"), row.select_one(".lb_5r a[href]")
        price = price.get_text().strip() if price else ""
        if name and link and re.fullmatch(r"[\d,]+円", price) and parse_yen(price):  # 「〜」の付いた幅のある価格は使わない
            yield " ".join(name.get_text().split()), parse_yen(price), urljoin(page, link["href"])


def _apple_name(name):
    """型番の書き間違いを直した商品名。「MWRR3JA」→「MWRR3J/A」。AirPods Max（2020年モデル）は名前の色の型番にする。"""
    name = _JA.sub(r"\1J/A", name)
    color = next((c for c in _AIRPODS_MAX if c in name), None)
    if name.startswith("AirPods Max 2020年モデル") and color:
        name = name.replace("MGYN3J/A", _AIRPODS_MAX[color])
    return name


def _fix_ipads(apple, products):
    """iPad の行の型番を、名前の容量・色で選び直す。2つ以上の行に書かれた型番（書き間違いがある）の行と、型番のない
    iPad mini（第6世代）の行が対象。カタログの同じ機種の中で容量・色の合う商品が1つに決まらなければ型番を使わない。"""
    families, models = {}, {}  # {型番: 機種}, {機種: [(容量, 色, 型番)]}
    for p in products:
        m = _IPAD_NAME.fullmatch(p["name"]) if p["series"] in IPAD_SERIES else None
        if m:
            families[p["model"]] = (m[1], m[3])
            models.setdefault((m[1], m[3]), []).append((m[2], m[4], p["model"]))
    rows = Counter(code for offer in apple for code in offer["codes"])
    for offer in apple:
        name = offer["name"]
        family = next((families[c] for c in offer["codes"] if rows[c] > 1 and c in families),
                      next((f for prefix, f in _IPAD_NO_CODE.items() if name.startswith(prefix + " ")), None))
        if family:
            capacities = _CAPACITY.findall(name)
            found = [code for capacity, color, code in models[family] if capacity in capacities and color in name]
            offer["codes"] = {found[0]: offer["price"]} if len(found) == 1 else {}


def _catalog_games(products):
    """カタログのゲーム機・VR の {型番: JAN} と {空白を除いた商品名: JAN}。"""
    products = [p for p in products if p["series"] in GAME_SERIES]
    return ({p["model"].upper(): p["jan"] for p in products if p.get("model")},
            {re.sub(r"\s", "", unicodedata.normalize("NFKC", p["name"]).upper()): p["jan"] for p in products})
