"""携帯楽園。

WooCommerce のサイトで、商品の一覧はストア API（/wp-json/wc/store/v1/products）から JSON で読める
（1ページ100件。価格は買取価格）。ゲーム機・カメラ・Pixel・Galaxy などは sku に JAN が入っている。
- 色・状態で価格が変わる商品は「variable」で、色ごとの価格は type=variation の一覧に
  「状態: 新品, 色: 黒」のような形で載っている。状態が「新品」のものだけ使う
- iPhone は sku が空で、「iPhone 18 Pro 256GB」のような機種＋容量の商品に色（黒・青・銀・紫など漢字1文字）ごとの
  価格がある。同じ名前で「SIM FREE 開封済み」の商品もあるので、説明に「開封済」とある商品は使わない
- JAN のない Android は「AQUOS wish6 SH-M36 128G+4G SIMフリー [ソラ]」のように色ごとに1商品
お酒・化粧品・中古品のカテゴリもあるが、カタログにない商品は突き合わせで落ちる（中古品のカテゴリは最初に外す）。
"""
import re

from ..phones import android_key, one_color, phone_color, phone_key
from ..text import find_jan

ID = "rakuen"
NAME = "携帯楽園"
SHORT = "楽園"
URL = "https://www.keitairakuen.com/"

API_URL = URL + "wp-json/wc/store/v1/products"
MAX_PAGES = 40
# 色の漢字1文字 → 公式の色名を探すための英語の別名（機種によってどの色を指すかが違うので、候補を順に試す）
KANJI_COLORS = {"黒": ["black"], "白": ["white"], "銀": ["silver"], "金": ["gold"], "青": ["blue", "glacier"],
                "紫": ["purple", "lavender", "burgundy"], "橙": ["orange"], "緑": ["green", "sage", "teal"],
                "桃": ["pink"], "灰": ["natural"]}


def fetch(http):
    products = [p for p in _read_all(http, {}) if not _used(p)]
    parents = {p["id"]: p for p in products}
    offers = []
    for p in products:
        if p["type"] == "simple":
            offers += _simple_offer(p)
    phones = {}
    for v in _read_all(http, {"type": "variation"}):
        parent = parents.get(v.get("parent"))
        state, color = _variation(v.get("variation", ""))
        price = int(v["prices"]["price"] or 0)
        if not parent or state != "新品" or not price:
            continue
        jan = find_jan(v.get("sku") or "")
        if jan:
            offers.append({"jan": jan, "name": parent["name"], "price": price, "url": parent["permalink"]})
            continue
        key = _phone_key(parent["name"])
        found = key and _color(key, color)
        if found:
            phones.setdefault(parent["id"], (key, {}))[1][found] = price
    for pid, (key, colors) in phones.items():
        p = parents[pid]
        offers.append({"jan": None, "key": key, "name": p["name"], "price": max(colors.values()), "url": p["permalink"],
                       "colors": colors})
    return offers


def _read_all(http, params):
    for page in range(1, MAX_PAGES + 1):
        res = http.get(API_URL, params={**params, "per_page": 100, "page": page})
        yield from res.json()
        if page >= int(res.headers.get("x-wp-totalpages") or 1):
            break


def _used(p):
    """中古品のカテゴリや、説明に「開封済」「中古」とある商品。"""
    return (any("useditem" in c["slug"] for c in p.get("categories", []))
            or re.search(r"開封済|中古", p.get("description") or ""))


def _simple_offer(p):
    price = int(p["prices"]["price"] or 0)
    if not price:
        return []
    jan = find_jan(p.get("sku") or "")
    if jan:
        return [{"jan": jan, "name": p["name"], "price": price, "url": p["permalink"]}]
    key = _phone_key(p["name"])
    colors = one_color(key, p["name"], price) if key else {}
    if not colors:
        return []
    return [{"jan": None, "key": key, "name": p["name"], "price": price, "url": p["permalink"], "colors": colors}]


def _phone_key(name):
    if re.search(r"iPhone|Pixel", name, re.IGNORECASE):
        return phone_key(name)
    return android_key(name)


def _variation(text):
    """「状態: 新品, 色: 黒」→（"新品", "黒"）。"""
    fields = dict(re.findall(r"([^,:\s]+)\s*:\s*([^,]+)", text))
    return fields.get("状態", "").strip(), fields.get("色", "").strip()


def _color(key, text):
    """色の漢字（「黒」「青」など）や色名を、その機種の公式の色名にする。"""
    if found := phone_color(key, text):
        return found
    for alias in KANJI_COLORS.get(text, []):
        if found := phone_color(key, alias):
            return found
    return None
