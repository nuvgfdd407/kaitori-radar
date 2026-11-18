"""トレカマフィア（宅配買取だけ。ポケモンカードの BOX と PSA10 を扱う）。

一覧はブラウザで組み立てていて、中身はページ自身が admin-ajax.php に POST（action=get_spreadsheet_catalog）して
受け取る JSON（{"data": {"items": {"psa10": [...], "box": [...]}}}）。1回で全件が取れる。
行ごとに recore_title（「【BOX】ストームエメラルダ」「【PSA10】ナンジャモ【SAR】{096/071} [SV2D]」）・price・status・
image_urls がある。status が false の行は画面に出ていない（買取していない）ので使わない。
BOX は JAN がないので、product_name（「ストームエメラルダ」）のセット名で突き合わせる（recore_title には
「ポケモカード151」のような書き損じがある）。「拡張パックデラックス『ブラックボルト』」はカタログの「ブラックボルトDX」にそろえる。
PSA10 の番号は recore_title の {} の中を使う（identification_bumber の列は別のカードの番号が入っていることがある）。
other_price・other_status（「買取停止」）の列は、名前の合わない別のカードの値が入っていることがあり、画面にも出ないので使わない。
「リストにない商品をカートに入れる」（1円）はカードではないので使わない。
画像はカード単体の画像。非対面の宅配買取だけなので、どの価格も買取方法は郵送。
"""
import re

from ..cards import card_key
from ..psa import parse_name, psa_key

ID = "mafia"
NAME = "トレカマフィア"
SHORT = "マフィア"
URL = "https://torecamafia.online/"

API_URL = URL + "wp-admin/admin-ajax.php"
# 画面に出さない行の status（ページの catalog.js と同じ）
_HIDDEN = (False, "FALSE", "false", "hidden")


def fetch(http):
    items = _items(http)
    offers = []
    for item in items["box"]:
        if _shown(item) and item["recore_title"].startswith("【BOX】"):
            name = _box_name(item["product_name"])
            offers.append({"jan": None, "key": card_key(name), "name": item["recore_title"], "price": int(item["price"]),
                           "url": URL, "mode": "郵送"})
    return offers + _psa_offers(items["psa10"])


def fetch_psa(http):
    """PSA 鑑定品の出品（scraper.psa_catalog でも使う）。"""
    return _psa_offers(_items(http)["psa10"])


def _items(http):
    return http.post(API_URL, data={"action": "get_spreadsheet_catalog"}).json()["data"]["items"]


def _shown(item):
    """画面に出ていて価格のある行か（status の列はチェックボックスで、外すと画面に出ない）。"""
    return item.get("status") not in _HIDDEN and bool(item.get("price"))


def _box_name(name):
    """「拡張パックデラックス『ブラックボルト』」→「ブラックボルトDX」。"""
    m = re.search(r"デラックス『([^』]+)』", name)
    return m.group(1) + "DX" if m else name


def _psa_offers(items):
    offers = []
    for item in items:
        if not _shown(item):
            continue
        title = item["recore_title"]
        parsed = parse_name(_psa_name(title))
        key = psa_key("pokemon", parsed[0], parsed[1], parsed[3]) if parsed else None
        if key:
            image = item["image_urls"][0] if item.get("image_urls") else None
            offers.append({"jan": None, "key": key, "name": title.strip(), "price": int(item["price"]), "url": URL,
                           "mode": "郵送",
                           "psa": {"game": "pokemon", "grade": parsed[0], "name": parsed[1], "rarity": parsed[2],
                                   "number": parsed[3], "image": image, "page": URL}})
    return offers


def _psa_name(title):
    """「【PSA10】ナンジャモ【SAR】{096/071} [SV2D]」→「PSA10 ナンジャモ SAR 096/071」。"""
    title = re.sub(r"\[[^\]]*\]", " ", title)  # [SV2D] の収録弾
    return " ".join(re.sub(r"[【】{}]", " ", title).split())
