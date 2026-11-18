"""OnMyPlan（秋葉原・町田・二子玉川）。

価格一覧（/price/?cid=1 など）はブラウザで組み立てるページで、中身はサイトが使っている API
（admin.onmyplan.jp/api/products?category_id=…）から JSON で読める（1ページ200件で、どのカテゴリも1ページに収まる）。
商品は「iPhone18 ProMax」のような機種ごとで、specifications に容量ごとの価格がある。
- 価格は「完済済み」の「新品未開封品」（price_s）だけを使う。Aランク以下（price_a など）と、
  「分割支払中」（installment_price_*）・「不明」（unknown_price_*）の価格は使わない
- 同じ容量に「SIMロック解除済」（sim_locked が false）と「解除していない」の2行がある機種は、解除済の行だけを使う
- iPhone・Pixel: キャリアの区別も色の区別もない（全色同じ価格）。カタログにある機種だけを使う
- iPad（2）: 「Apple 【国内版 SIMフリー】iPad Pro 13インチ 第1世代 標準ガラス搭載 Wi-Fi+Cellularモデル」
  「iPad Air 11インチ 第6世代 WIFI」のような名前と容量でカタログの iPad と突き合わせる（scraper.apple.ipad_offer。
  名前に「Cellular」があれば Cellular 版。色の区別はない）
JAN・更新日は載っていない。Mac・Apple Watch・AirPods は型番がなく、Xperia・Galaxy はキャリアが書かれておらず、
Switch・PS5 は型番のない古い機種だけなので使わない。
"""
from ..apple import ipad_offer
from ..phones import phone_colors, phone_key

ID = "onmyplan"
NAME = "OnMyPlan"
SHORT = "OnMyPlan"
URL = "https://onmyplan.jp/"

API_URL = "https://admin.onmyplan.jp/api/products"
# iPhone / Pixel
CATEGORIES = [1, 8]
IPAD = 2


def fetch(http):
    offers = []
    for category in CATEGORIES:
        data = http.get(API_URL, params={"category_id": category, "per_page": 200, "page": 1}).json()
        for product in data["data"]:
            page = f"{URL}price/?cid={category}&pid=p{product['id']}"  # その機種の欄まで移動する
            for spec in product["specifications"]:
                name = f"{product['name']} {spec['name']}"
                key = phone_key(name)
                if spec["sim_locked"] or not spec["price_s"] or not (key and phone_colors(key)):
                    continue
                offers.append({"jan": None, "key": key, "name": name, "price": spec["price_s"], "url": page})
    for product, spec, page in _specs(http, IPAD):
        offer = ipad_offer(f"{product['name']} {spec['name']}", spec["price_s"], page)
        if offer:
            offers.append(offer)
    return offers


def _specs(http, category):
    """カテゴリの（機種, 容量の行, 価格一覧のその機種の欄の URL）。SIMロックを解除していない行と価格のない行は飛ばす。"""
    data = http.get(API_URL, params={"category_id": category, "per_page": 200, "page": 1}).json()
    for product in data["data"]:
        for spec in product["specifications"]:
            if not spec["sim_locked"] and spec["price_s"]:
                yield product, spec, f"{URL}price/?cid={category}&pid=p{product['id']}"
