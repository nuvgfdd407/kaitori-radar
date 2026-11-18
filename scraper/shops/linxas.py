"""リンクサス買取（LINXAS）。

機種のページ（/services/brand/iphone など）に、シリーズごとの表（.product-price-list）が並んでいる。
表の1行は「キャリア（.store）・機種名（.type）・新品(未開封)買取価格・中古品買取価格」で、新品(未開封)の価格だけを使う。
表ごとに「価格更新日」が書かれていて、30日以上前の表は使わない。「お問い合わせ」の行は飛ばす。JAN は載っていない。
- iPhone・Pixel: 「iPhone17 Pro 国内版SIMフリー 256GB」のように機種＋容量ごと。キャリア版・海外版の行もあるが、
  カタログは SIMフリー版なので「国内版SIMフリー」の行だけを使う。色の区別はない（機種ごとのページも全色同じ価格）
- Galaxy・Xperia・AQUOS: キャリアの欄（「docomo」「UQmobile」「国内版SIM」など）を android_key に渡す。
  欄が空や「全キャリア」の行は、商品名の型番（SC-53F・SOG14 など）からキャリアを読む。
  海外版の行と、国内版SIMフリーの欄にある mineo 版・J:COM 版（au の型番）の行は使わない。
  同じ機種の行がキャリアのタブごとに何度も出てくる（価格は同じ。au 版と UQ mobile 版で違うときは高い au 版の価格になる）
- Mac・AirPods: 機種名に型番（「MW2U3J/A」など）が書かれている。CTO の行（「CTO (MW0W3J/A)」のように
  元の型番が書かれているが、メモリや容量が違う）は使わない。型番のない AirPods Max は全色の型番を補う
- Switch・PS5: 機種名に任天堂・ソニーの型番（「HEG-S-KAAAA」「CFI-2000A01」など）が書かれているので、
  カタログの "model" から JAN を引く（JAN は載っていないので）。型番のない Switch 2 多言語対応版は型番を補う。
  型番のない Switch Lite の行は、「本体」を除いた商品名がカタログの商品名と同じなら使う
iPad・Apple Watch は型番も JAN もなく（Wi-Fi/Cellular やバンドの区別もない）、Xbox は全部「お問い合わせ」なので取らない。
"""
import re
import unicodedata
from datetime import date, timedelta

from bs4 import BeautifulSoup

from ..apple import apple_offer
from ..common import CATALOG, load_json
from ..phones import android_key, phone_colors, phone_key
from ..text import parse_yen

ID = "linxas"
NAME = "リンクサス買取"
SHORT = "リンクサス"
URL = "https://linx-as.co.jp/"

IPHONE_PAGES = [URL + "services/brand/iphone", URL + "services/brand/pixel"]
ANDROID_PAGES = [URL + "services/brand/" + p for p in ("galaxy", "xperia", "aquos")]
APPLE_PAGES = [URL + "services/notepc/mac", URL + "services/earphone/airpods"]
GAME_PAGES = [URL + "services/game/nintendoswitch", URL + "services/game/playstation"]
GAME_SERIES = {"switch2", "switch", "ps5"}
MAX_AGE = timedelta(days=30)
# キャリアの欄 → android_key のキャリア名（UQ mobile 版は au 版として扱う。欄が空・「全キャリア」なら商品名から読む）
_CARRIERS = {"docomo": "docomo", "au": "au", "UQmobile": "au", "SoftBank": "SoftBank", "楽天モバイル": "楽天モバイル",
             "Y!mobile": "Y!mobile", "国内版SIMフリー": "SIMフリー", "SIMフリー": "SIMフリー", "国内版SIM": "SIMフリー"}
_OTHER_VERSIONS = re.compile(r"海外版|mineo|J:COM", re.IGNORECASE)
# 任天堂（BEE-S-KB6CA・HEG-S-KAAAA）とソニー（CFI-2000A01・CFIJ-10027）の型番
_GAME_CODE = re.compile(r"(?<![A-Z0-9-])([A-Z]{3}-[A-Z]-[A-Z0-9]{5}|CFIJ?-[0-9A-Z]{5,})(?![A-Z0-9])")
# 型番が書かれていない行の型番（AirPods Max は色の区別がないので全色）
_CODES = {
    "Nintendo Switch 2 多言語対応版": ["BEE-S-KB6AA"],
    "AirPods Max(USB-C)": ["MWW43ZA/A", "MWW53ZA/A", "MWW63ZA/A", "MWW73ZA/A", "MWW83ZA/A"],
    "AirPods Max": ["MGYH3J/A", "MGYJ3J/A", "MGYL3J/A", "MGYM3J/A", "MGYN3J/A"],
}


def fetch(http):
    offers = []
    for page in IPHONE_PAGES:
        for store, name, price in _read_rows(http, page):
            key = phone_key(name)
            if store == "国内版SIMフリー" and key and phone_colors(key):
                offers.append({"jan": None, "key": key, "name": name, "price": price, "url": page})
    for page in ANDROID_PAGES:
        for store, name, price in _read_rows(http, page):
            if _OTHER_VERSIONS.search(f"{store} {name}"):
                continue
            key = android_key(name, _CARRIERS.get(store))
            if key:
                offers.append({"jan": None, "key": key, "name": name, "price": price, "url": page})
    for page in APPLE_PAGES:
        for _, name, price in _read_rows(http, page):
            offer = apple_offer(name, price, page, text=" ".join(_CODES.get(name, [])))
            if offer["codes"] and "CTO" not in name:
                offers.append(offer)
    models, names = _catalog_games()
    for page in GAME_PAGES:
        for _, name, price in _read_rows(http, page):
            codes = _GAME_CODE.findall(name) or _CODES.get(name, [])
            # 型番のある行は型番だけで引く（旧型の HAC-S- が名前で新型に当たらないように）
            jan = (next((models[c] for c in codes if c in models), None) if codes
                   else names.get(_game_name(name.replace("本体", ""))))
            if codes or jan:
                offers.append({"jan": jan, "name": name, "price": price, "url": page})
    return offers


def _catalog_games():
    """カタログのゲーム機の {型番: JAN} と {商品名: JAN}。"""
    products = [p for p in load_json(CATALOG)["products"] if p["series"] in GAME_SERIES]
    return ({p["model"]: p["jan"] for p in products if p.get("model")},
            {_game_name(p["name"]): p["jan"] for p in products})


def _game_name(name):
    return " ".join(unicodedata.normalize("NFKC", name).split())


def _read_rows(http, page):
    """表の（キャリアの欄, 機種名, 新品(未開封)買取価格）を順に返す。更新日が古い表と、価格のない行は飛ばす。"""
    soup = BeautifulSoup(http.get(page).content, "html.parser")
    for table in soup.select(".product-price-list"):
        updated = table.select_one(".price-update")
        m = re.search(r"(\d{4})年(\d{1,2})月(\d{1,2})日", updated.get_text() if updated else "")
        if not m or date.today() - date(*map(int, m.groups())) >= MAX_AGE:
            continue
        for row in table.select("tr.list-item"):
            store, name, price = (row.select_one(s) for s in (".store", ".type", ".new-price"))
            price = parse_yen(price.get_text()) if price else None
            if name and price:
                yield (store.get_text(strip=True) if store else "", " ".join(name.get_text(" ").split()), price)
