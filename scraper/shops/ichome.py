"""買取一丁目。

画面は JavaScript で組み立てているが、裏側の API から JSON で取れる。
【ゲーム】の中に本体だけのカテゴリがあるので、そこだけを取得する。
価格は goodsKbDetails の中にあり、「来店」（来店時の加算）ではない方の価格を使う。
（商品データの price は買取価格ではないので使わない）
iPhone は携帯用の API にあり、JANのない「iPhone 17 Pro 256GB」のような機種＋容量の商品で、
「未開封」の価格に色ごとの増減（varPrice）が付く。いちばん高い色の価格を使う。
"""
import re

from ..iphone import iphone_color, iphone_key

ID = "ichome"
NAME = "買取一丁目"
SHORT = "一丁目"
URL = "https://www.1-chome.com/"

API = "https://www.1-chome.com/api/goods/listPage"
# Switch 2 / Switch本体 / PlayStation本体 / Xbox本体 / PlayStation 周辺機器 / Meta Quest / Steam Deck / ASUS
CATEGORIES = [
    "bBNHyqptq0nqvbcg", "KKXBEAyI9PC2HMjU", "NE0hGv3ube9UbM3H", "axsZ6sOue6IQhfht",
    "Hi6VUvS3BHzS9kvL", "Y3pbA65dEt2seG0B", "20304465", "20464007",
]
IPHONE_API = "https://www.1-chome.com/api/keitai/listPage"
# iPhone 18シリーズ / 17シリーズ / 16シリーズ
IPHONE_CATEGORIES = ["3mMfFdssdWf0cUTv", "FOwhVgpORbuy43jx", "sqwDCccRt4Woon0R"]
PAGE_SIZE = 100


def fetch(http):
    offers = []
    for category in CATEGORIES:
        for item in _read_category(http, API, category):
            price = _new_price(item)
            if item.get("jan") and price:
                offers.append({
                    "jan": item["jan"],
                    "name": (item.get("title") or "").strip(),
                    "price": price,
                    # サイトの共有リンクと同じ形の商品ページ
                    "url": f"{URL}wineDetail/{item['goodsId']}/{item['allGoodsKbId']}",
                })
    for category in IPHONE_CATEGORIES:
        for item in _read_category(http, IPHONE_API, category):
            name = (item.get("title") or "").strip()
            key = iphone_key(name)
            price, colors = _unopened_prices(item, key)
            if price:
                offers.append({
                    "jan": None,
                    "key": key,
                    "name": name,
                    "price": price,
                    "colors": colors,
                    "url": f"{URL}productDetail/{item['goodsId']}/{item['allGoodsKbId']}",
                })
    return offers


def _read_category(http, api, category):
    page = 1
    while True:
        body = http.get(api, params={"cateCode": category, "page": page, "size": PAGE_SIZE}).json()
        if body.get("code") != 200:
            raise RuntimeError(f"API のエラー: {body.get('msg')}")
        data = body["data"]
        for item in data.get("content") or []:
            if item.get("disp") is not False:
                yield item
        if page * PAGE_SIZE >= (data.get("totalElements") or 0):
            break
        page += 1


def _new_price(item):
    """新品（未開封）の郵送の買取価格。来店時の価格や中古・開封品の価格は使わない。"""
    if not re.search("新品|未開封", item.get("kbName") or ""):
        return None
    prices = [
        detail.get("kbDetailPrice")
        for detail in item.get("goodsKbDetails") or []
        if not re.search("来店|中古|開封済|傷", detail.get("kbDetailName") or "")
    ]
    prices = [p for p in prices if p]
    return max(prices) if prices else None


def _unopened_prices(item, key):
    """iPhone の「未開封」の価格。（いちばん高い色の価格, {色: 価格}）を返す。"""
    if not re.search("新品", item.get("kbName") or ""):
        return None, {}
    detail = next((d for d in item.get("goodsKbDetails") or [] if d.get("kbDetailName") == "未開封"), None)
    if not detail or not detail.get("kbDetailPrice"):
        return None, {}
    base = detail["kbDetailPrice"]
    colors = {}
    for option in item.get("keitaiColorOptions") or []:
        change = next((rel.get("varPrice") or 0 for rel in option.get("keitaiKbDetailColorRels") or []
                       if rel.get("keitaiKbDetailId") == detail.get("allGoodsKbDetailId")), 0)
        color = iphone_color(key, option.get("color"))
        if color:
            colors[color] = max(colors.get(color, 0), base + change)
    return (max(colors.values()) if colors else base), colors
