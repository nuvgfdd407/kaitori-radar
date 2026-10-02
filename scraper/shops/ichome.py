"""買取一丁目。

画面は JavaScript で組み立てているが、裏側の API から JSON で取れる。
【ゲーム】の中に本体だけのカテゴリがあるので、そこだけを取得する。
価格は goodsKbDetails の中にあり、「来店」（来店時の加算）ではない方の価格を使う。
（商品データの price は買取価格ではないので使わない）
iPhone・Pixel は携帯用の API にあり、JANのない「iPhone 17 Pro 256GB」のような機種＋容量の商品で、
「未開封」の価格に色ごとの増減（varPrice）が付く。いちばん高い色の価格を使う。
Android も同じ API にあり、SIMフリー・キャリアごとのカテゴリに機種＋容量の商品で載っている。
価格の選択肢の名前は「新品未開封」「未開封」「docomo版 未開封」「銀色シール未開封」「新品」などいろいろで、
SIMフリーの商品に「楽天版 未開封」（楽天モバイル版の価格）が付いていることもある。
iPad・Apple Watch も携帯用の API にあり、色（Watch はバンド）ごとの JAN と型番、価格の増減が付いている。
AirPods は家電用の API にあり、JAN が付いている。
"""
import re

from ..apple import apple_codes, apple_offer
from ..phones import android_key, phone_color, phone_key

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
# Google Pixel は機種ごとのカテゴリが多いので、商品名の検索でまとめて取る
PIXEL_KEYWORD = "Pixel"
# Android の SIMフリー / AU&UQ / Docomo / Softbank / Y!mobile / 楽天モバイル
ANDROID_CATEGORIES = [("WkCcKCxwC6NInC5c", "SIMフリー"), ("GsGv92VhqBU8Mvuj", "au"), ("eUuVCbUWMuHBlQ6p", "docomo"),
                      ("3Hrb86KrMNz86mzg", "SoftBank"), ("T0hAdlufks5mS1ez", "Y!mobile"), ("vYZ5NQzgQ1sIaXO4", "楽天モバイル")]
# iPad / Apple Watch（携帯用の API）、AirPods / AirPods Max（家電用の API）
APPLE_KEITAI_CATEGORIES = ["df7CCyzC7GlrzAMt", "CS6O5bYC0Ezu2Zj9"]
APPLE_GOODS_CATEGORIES = ["P2GdGa4Qo46DdnXO", "lWMiNtQABsWADyJY"]
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
    phones = [item for category in IPHONE_CATEGORIES for item in _read_category(http, IPHONE_API, category)]
    phones += list(_read_category(http, IPHONE_API, keyword=PIXEL_KEYWORD))
    for item in phones:
        name = (item.get("title") or "").strip()
        key = phone_key(name)
        price, colors = _unopened_prices(item, key)
        if price and key:  # 「Pixel」の検索には Pixel Watch なども出てくるので、スマホだけにする
            offers.append({
                "jan": None,
                "key": key,
                "name": name,
                "price": price,
                "colors": colors,
                "url": f"{URL}productDetail/{item['goodsId']}/{item['allGoodsKbId']}",
            })
    for category in APPLE_KEITAI_CATEGORIES:
        for item in _read_category(http, IPHONE_API, category):
            offers += _apple_offers(item)
    for category in APPLE_GOODS_CATEGORIES:
        for item in _read_category(http, API, category):
            price = _new_price(item)
            if price:
                offers.append(apple_offer((item.get("title") or "").strip(), price,
                                          f"{URL}wineDetail/{item['goodsId']}/{item['allGoodsKbId']}", jan=item.get("jan")))
    for category, carrier in ANDROID_CATEGORIES:
        for item in _read_category(http, IPHONE_API, category):
            name = (item.get("title") or "").strip()
            for detail_carrier, detail in _android_details(item, carrier):
                key = android_key(name, detail_carrier)
                colors = _color_prices(item, key, detail)
                if not key or (item.get("keitaiColorOptions") and not colors):
                    continue
                offer = {
                    "jan": None,
                    "key": key,
                    "name": name,
                    "price": max(colors.values()) if colors else detail["kbDetailPrice"],
                    "url": f"{URL}productDetail/{item['goodsId']}/{item['allGoodsKbId']}",
                }
                # 色の選択肢がない商品は、どの色でも同じ価格（"colors" を付けない）
                if colors:
                    offer["colors"] = colors
                offers.append(offer)
    return offers


def _read_category(http, api, category=None, keyword=None):
    query = {"cateCode": category} if category else {"keyword": keyword}
    page = 1
    while True:
        body = http.get(api, params={**query, "page": page, "size": PAGE_SIZE}).json()
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
        if not re.search("来店|中古|開封済|傷(?!なし)", detail.get("kbDetailName") or "")
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
    colors = _color_prices(item, key, detail)
    return (max(colors.values()) if colors else detail["kbDetailPrice"]), colors


def _apple_offers(item):
    """iPad・Apple Watch の商品の、色（バンド）ごとの出品。未開封の価格に色ごとの増減を足す。"""
    details = _android_details(item, None)
    if not details:
        return []
    detail = details[0][1]
    name = (item.get("title") or "").strip()
    url = f"{URL}productDetail/{item['goodsId']}/{item['allGoodsKbId']}"
    offers = []
    for option in item.get("keitaiColorOptions") or []:
        change = next((rel.get("varPrice") or 0 for rel in option.get("keitaiKbDetailColorRels") or []
                       if rel.get("keitaiKbDetailId") == detail.get("allGoodsKbDetailId")), 0)
        price = detail["kbDetailPrice"] + change
        jan = (option.get("jan") or "").strip() or None
        offer = apple_offer(f"{name} {option.get('color') or ''}", price, url, jan=jan)
        if jan or apple_codes(option.get("color")):
            offers.append(offer)
    return offers


def _android_details(item, carrier):
    """Android の商品の、新品未開封の価格の選択肢を（キャリア, 選択肢）で返す。

    「未開封」と書かれた選択肢を使い、なければ「新品」「国内版」だけの選択肢を使う（開封品・mineo版などは使わない）。
    """
    if not re.search("新品|国内版", item.get("kbName") or ""):
        return []
    details = [d for d in item.get("goodsKbDetails") or [] if d.get("kbDetailPrice")]
    unopened = [d for d in details if "未開封" in (d.get("kbDetailName") or "")]
    if not unopened:
        unopened = [d for d in details if (d.get("kbDetailName") or "").strip() in ("新品", "国内版")]
    result = []
    for detail in unopened:
        label = detail.get("kbDetailName") or ""
        if "mineo" in label.lower():
            continue
        result.append(("楽天モバイル" if "楽天" in label else carrier, detail))
    return result


def _color_prices(item, key, detail):
    """選択肢の価格に色ごとの増減（varPrice）を足した {色: 価格}。"""
    base = detail["kbDetailPrice"]
    colors = {}
    for option in item.get("keitaiColorOptions") or []:
        change = next((rel.get("varPrice") or 0 for rel in option.get("keitaiKbDetailColorRels") or []
                       if rel.get("keitaiKbDetailId") == detail.get("allGoodsKbDetailId")), 0)
        color = phone_color(key, option.get("color"))
        if color:
            colors[color] = max(colors.get(color, 0), base + change)
    return colors
