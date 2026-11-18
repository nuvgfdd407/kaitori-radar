"""ハチ買取（蜂電株式会社）。

新品・未開封だけを買い取る店。商品の一覧はサイトが使っている API（/api/public/products?limit=500）から
JSON で全件を1回で読める。商品は「iPhone 18 Pro 256GB」のような機種＋容量ごとで、variants に
色ごとの価格（price）が入っている。sale_price があれば、それがその色の買取価格（price は取り消し線で出す元の価格）。
一覧の JAN は商品ごとの代表の1つだけで、色ごとの JAN は商品の詳細（/api/public/products/{id}）にある。
- updated_at（商品の更新日時）が30日以上前の商品は、価格が古いので使わない（2025年のままの商品が多い）
- 色の欄が「印あり」（保証書に販売店の印がある）・「保証開始」の行は減額の価格なので使わない
- トップページのお知らせ（/api/public/banner）に「■ iPhone 18シリーズおよびDuoシリーズは、店頭買取のみの受付」と
  書かれている機種は、店頭持ち込みだけの価格なので使わない（お知らせを毎回読んで、その行の「〜シリーズ」の名前で外す）
- iPhone・Pixel: 商品名から機種＋容量、色の欄から公式の色名を読む（店は SIMフリー版・キャリア版を区別していない）
- iPad・Mac・Apple Watch・AirPods: 色の欄に型番（「ミッドナイト【MDHE4J/A】」）があればそれで、なければ
  詳細の色ごとの JAN で突き合わせる（JAN が別の容量・色のものになっている行があるので、型番を優先する）。
  詳細を開くのは、色が2つ以上あって型番のない色がある商品だけ
- MacBook は商品名に「【キーボード英語（US）のみ】」と条件が付いているので、"note" にする
- ゲーム機・カメラ: JAN で突き合わせる。色が2つ以上ある商品（instax など）だけ詳細を開いて色ごとの JAN を読む
イヤホン・腕時計のカテゴリの Apple 以外（Bose・SONY・Pixel Watch など）はカタログにないので使わない。
説明に「問い合わせ」とある商品は価格が決まっていないので使わない。
"""
import re
from datetime import datetime, timedelta, timezone

from ..apple import apple_codes, apple_offer
from ..phones import phone_color, phone_key
from ..text import find_jan

ID = "hachi"
NAME = "ハチ買取"
SHORT = "ハチ"
URL = "https://hachiden.com/"

API_URL = URL + "api/public/products"
BANNER_URL = URL + "api/public/banner"
MAX_PAGES = 5
MAX_AGE = timedelta(days=30)
JST = timezone(timedelta(hours=9))
# カテゴリの番号: 携帯 / iPad / パソコン / イヤホン / 腕時計（カメラ 3・ゲーム機 1 は JAN で読む）
PHONE, IPAD, MAC, AUDIO, WATCH = 4, 6, 7, 2, 5
APPLE_CATEGORIES = (IPAD, MAC, AUDIO, WATCH)
# 色の欄の書き方 → phone_color で読める英語の名前（「ブルー」だけでは iPhone 17 のミストブルーなどに、
# 「ブラック」だけでは iPhone Air のスペースブラックに当たらない。「Natrural」は店の綴り間違い）
_COLOR_WORDS = {"ブルー": "blue", "ゴールド": "gold", "ゴールト": "gold", "ブラック": "black", "ホワイト": "white",
                "Natrural": "natural"}
_CONDITION = re.compile(r"【([^】]*のみ)】")


def fetch(http):
    since = datetime.now(JST).replace(tzinfo=None) - MAX_AGE
    store_only = _store_only(http)
    offers = []
    for p in _read_all(http):
        if datetime.fromisoformat(p["updated_at"]) < since or "問い合わせ" in (p["description"] or ""):
            continue
        if any(series in p["name"] for series in store_only):
            continue
        category = p["category_id"]
        if category in (AUDIO, WATCH) and p["brand"] != "Apple":
            continue
        # 「MacBook Air …【キーボード英語（US）のみ】」の【…のみ】は買取の条件
        condition = _CONDITION.search(p["name"])
        name = " ".join(_CONDITION.sub(" ", p["name"]).split())
        url = f"{URL}product.html?id={p['id']}"
        variants = _variants(p["variants"])
        if not variants:
            continue
        if category == PHONE:
            offers += _phone_offer(name, variants, url)
            continue
        apple = category in APPLE_CATEGORIES
        if len(p["variants"]) == 1:  # 色が1つだけの商品は、代表の JAN がその色の JAN
            variants[0]["jan_code"] = p["representative_jan_code"]
        elif not (apple and all(apple_codes(v["color"]) for v in variants)):  # 色ごとの JAN は詳細にしかない
            variants = _variants(http.get(f"{API_URL}/{p['id']}").json()["variants"])
        for v in variants:
            jan = find_jan(v.get("jan_code") or "")
            if apple:
                # 色ごとの JAN が型番と食い違っている行がある（iPad Pro 11インチ 512GB シルバーに 256GB の JAN）ので、
                # 色の欄に型番があれば型番だけで突き合わせる
                offer = apple_offer(name, v["price"], url, jan=None if apple_codes(v["color"]) else jan, text=v["color"])
            elif jan:
                offer = {"jan": jan, "name": f"{name} {v['color']}", "price": v["price"], "url": url}
            else:
                continue
            if condition:
                offer["note"] = condition.group(1)
            offers.append(offer)
    return [o for o in offers if o["jan"] or o.get("key") or o.get("codes")]


def _store_only(http):
    """お知らせの「店頭買取のみ」の行にある「〜シリーズ」の名前（今は「iPhone 18」「Duo」）。"""
    text = http.get(BANNER_URL).json()["text"] or ""
    return [series.strip() for line in text.splitlines() if "店頭買取のみ" in line
            for series in re.findall(r"([A-Za-z0-9 ]+)シリーズ", line)]


def _read_all(http):
    for page in range(1, MAX_PAGES + 1):
        data = http.get(API_URL, params={"page": page, "limit": 500}).json()
        yield from data["products"]
        if page >= data["pagination"]["totalPages"]:
            break


def _variants(variants):
    """未開封で価格のある色の一覧。price は sale_price があればそちら。「印あり」「保証開始」の行は使わない。"""
    rows = []
    for v in variants:
        price = int(float(v["sale_price"] or v["price"] or 0))
        color = " ".join((v["color"] or "").split())
        if v["condition"] == "未開封" and price and color not in ("印あり", "保証開始"):
            rows.append({**v, "color": color, "price": price})
    return rows


def _phone_offer(name, variants, url):
    key = phone_key(name)
    colors = {}
    for v in variants:
        if color := _color(key, v["color"]):
            colors[color] = v["price"]
    if not colors:
        return []
    return [{"jan": None, "key": key, "name": name, "price": max(colors.values()), "url": url, "colors": colors}]


def _color(key, text):
    """色の欄（「シルバー」「Obsidian（Matte）」「ブルー」など）をその機種の公式の色名にする。"""
    text = text.replace("－", "ー")  # 「ラベンダ－」のような全角のマイナス
    return phone_color(key, text) or phone_color(key, _COLOR_WORDS.get(text, ""))
