"""買取一丁目。

画面は JavaScript で組み立てているが、裏側の API から JSON で取れる。
【ゲーム】の中に本体だけのカテゴリがあるので、そこだけを取得する。
価格は goodsKbDetails の中にあり、「来店」（来店時の加算）ではない方の価格を使う。
（商品データの price は買取価格ではないので使わない）
"""
import re

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
PAGE_SIZE = 100


def fetch(http):
    offers = []
    for category in CATEGORIES:
        page = 1
        while True:
            body = http.get(API, params={"cateCode": category, "page": page, "size": PAGE_SIZE}).json()
            if body.get("code") != 200:
                raise RuntimeError(f"API のエラー: {body.get('msg')}")
            data = body["data"]
            for item in data.get("content") or []:
                price = _new_price(item)
                if item.get("jan") and price and item.get("disp") is not False:
                    offers.append({
                        "jan": item["jan"],
                        "name": (item.get("title") or "").strip(),
                        "price": price,
                        # サイトの共有リンクと同じ形の商品ページ
                        "url": f"{URL}wineDetail/{item['goodsId']}/{item['allGoodsKbId']}",
                    })
            if page * PAGE_SIZE >= (data.get("totalElements") or 0):
                break
            page += 1
    return offers


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
