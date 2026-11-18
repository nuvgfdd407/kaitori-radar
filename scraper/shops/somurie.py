"""買取ソムリエ。

新品・未開封だけを買い取る店。Next.js のサイトで、商品の一覧（/products）の HTML には最初の40件しか出ないが、
中身はサイトが使っている API（api.somurie-kaitori.com/api/products/public?start=0&limit=…）から JSON で全件を読める
（全部で140件ほどなので1回で足りる）。商品ごとに商品名（nameSite）・条件（subTitle）・価格（costPrice）・
JAN（janCode）・更新日時（updatedAt）・残りの買取枠（freeSpace）が入っている。商品ごとのページはないので、
価格のページはカテゴリの一覧にする。
- updatedAt が30日以上前の商品は、価格が古いので使わない（Mac mini・HomePod・Apple Watch Series 12 の Cellular など）
- 残りの買取枠が最低数量より少ない商品は、サイトで「買取停止中」になっているので使わない
- 商品ごとに買取の受付時間（12〜19時など）があるが、時間外も同じ価格を出している（「買取時間外」になるだけ）ので使う
- iPhone: 色ごとに1商品で、JAN もある。機種＋容量と色で突き合わせる（SIMロック解除版＝SIMフリーだけ）。
  iPhone 17 の行は「計3台以上から買取」の条件付きなので "note" に載せる
- iPad・Apple Watch・HomePod・Mac: 商品名か条件の欄に型番があり、JAN と一緒に apple_offer で突き合わせる
- ゲーム機・カメラ・Meta Quest: JAN で突き合わせる。Meta Quest は12桁の UPC なので、頭に0を付けて13桁にする
- ポケモンカードの BOX: JAN があるが、熱風のアリーナはカタログと違う JAN が付いているので、
  「ポケモンカードゲーム 熱風のアリーナ（SV9a）シュリンク付きボックス」からセット名も読んで突き合わせる
  （30th CELEBRATION FUTURISTIC BOX は JAN がない）
フィギュア（Sonny Angel など）もあるが、カタログにないので突き合わせで落ちる。
"""
import re
import unicodedata
from datetime import datetime, timedelta, timezone

from ..apple import apple_offer
from ..cards import card_key
from ..phones import one_color, phone_key
from ..text import find_jan

ID = "somurie"
NAME = "買取ソムリエ"
SHORT = "ソムリエ"
URL = "https://somurie-kaitori.com/"

API_URL = "https://api.somurie-kaitori.com/api/products/public"
LIMIT = 200
MAX_PAGES = 5
MAX_AGE = timedelta(days=30)
# カテゴリの番号: iPhone / Apple その他（iPad・Apple Watch・HomePod・Mac） / トレーディングカード
IPHONE, APPLE, CARD = 1, 6, 2
_USED = re.compile(r"中古|開封済|開封品")
_MIN_UNITS = re.compile(r"計?\d+台以上から買取")
# BOX の商品名のうち、セット名ではない部分（「MEGAドリームex」の MEGA は消さない）
_CARD_WORDS = re.compile(r"ポケモンカードゲーム|MEGA(?=\s)|シュリンク付き|ボックス|\([A-Za-z0-9]+\)")


def fetch(http):
    since = datetime.now(timezone.utc) - MAX_AGE
    offers = []
    for p in _read_all(http):
        name, sub = " ".join(p["nameSite"].split()), " ".join((p["subTitle"] or "").split())
        price = int(float(p["costPrice"] or 0))
        if (not price or p["freeSpace"] < (p["minPurchaseQty"] or 1) or _USED.search(name + sub)
                or datetime.fromisoformat(p["updatedAt"]) < since):
            continue
        jan = _jan(p["janCode"])
        url = f"{URL}products?category={p['categoryId']}" + (f"&subcategory={p['subCategoryId']}" if p["subCategoryId"] else "")
        if p["categoryId"] == IPHONE:
            key = phone_key(name)
            offer = {"jan": jan, "key": key, "name": name, "price": price, "url": url,
                     "colors": one_color(key, name, price) if key else {}}
            if m := _MIN_UNITS.search(sub):
                offer["note"] = m.group(0)
        elif p["categoryId"] == APPLE:
            offer = apple_offer(name, price, url, jan=jan, text=sub)
        elif p["categoryId"] == CARD:
            offer = {"jan": jan, "key": card_key(_set_name(name)), "name": name, "price": price, "url": url}
        else:
            offer = {"jan": jan, "name": name, "price": price, "url": url}
        offers.append(offer)
    return offers


def _read_all(http):
    for page in range(MAX_PAGES):
        data = http.get(API_URL, params={"start": page * LIMIT, "limit": LIMIT}).json()["data"]
        yield from data["rows"]
        if (page + 1) * LIMIT >= data["count"]:
            break


def _jan(code):
    """JAN。12桁の UPC（Meta Quest など）は、頭に0を付けて13桁にする。"""
    code = (code or "").strip()
    return "0" + code if re.fullmatch(r"\d{12}", code) else find_jan(code)


def _set_name(name):
    """「ポケモンカードゲーム 熱風のアリーナ（SV9a）シュリンク付きボックス」→「熱風のアリーナ」。"""
    return _CARD_WORDS.sub(" ", unicodedata.normalize("NFKC", name))
