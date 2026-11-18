"""ダイワンテレコム（スマホ買取のダイワン）。

ジャンルの一覧（/product/sumaho/iphone など）に、機種ごとのページの行が全部載っているので、ジャンルの一覧を読む。
1行は「iPhone18 Pro 256GB 国内版SIMフリー」のような機種・容量・キャリアの名前と、キャリアの欄（docomo・au・SIMフリーなど）、
「新品買取価格」「中古上限」「下限」「画面割れ等」の価格。新品買取価格（未開封）だけを使う。JAN は載っていない。
一覧の上の「買取価格更新日」が30日以上前の一覧は使わない。
- iPhone: 「国内版SIMフリー」の行だけを使う（キャリア版は別の行だが、カタログは SIMフリー版なので）。
  一覧の価格は基準の色の価格で、色ごとの減額（「グレイシャー(-5,000円)」など。全色が減額のこともある）は商品ページにある。
  商品ページ（/item/iPhone18_Pro_Max?id=3293 など）には、同じ機種の全容量・全キャリアの色ごとの減額が
  `const items = {...}` の JSON で埋め込まれているので、カタログにある機種ごとに1ページだけ開いて、行の id で引く。
  色が載っていない機種（iPhone Duo）は一覧の価格を全色に当てはめる
- Pixel: 「国内版SIMフリー」の行だけを使う。商品ページに色ごとの減額はない（2026-11 時点）ので、一覧の価格を全色に当てはめる
- Galaxy・Xperia・AQUOS: キャリアの欄を android_key に渡す。mineo・BIGLOBE などの MVNO 版の行は使わない。
  容量の書かれていない行は、容量が1種類だけの機種なら scraper.update がその容量の商品に当てはめる
- Mac: 名前に型番（「MW0W3J/A」など）と「M4 8コア 16GB 256GB」のような GPU のコア数・メモリ・SSD が書かれている。
  M4 の MacBook Air などは、同じ型番でメモリ・SSD・GPU の違う行（カスタマイズモデル）が並んでいるので、
  カタログのその型番の商品名とメモリ・SSD（名前に書かれていれば GPU のコア数も）が同じ行だけを使う。
  標準の構成の行がない型番（M4 の MacBook Air 15インチの多く）は使わない
- iPad（/product/tablet/ipad）: 「iPad Air 第8世代(M4) 13インチ 1TB 国内版SIMフリー(A3462)」のような名前で
  カタログの iPad と突き合わせる（scraper.apple.ipad_offer）。「国内版Wi-Fi」と「国内版SIMフリー」（Apple 版の
  Wi-Fi + Cellular）の行だけを使う。色ごとの減額は iPhone と同じく商品ページの JSON から読む
  （カタログにある iPad の行の機種ごとに1ページ）
Apple Watch は型番・JAN・バンドが書かれていないので使わない。ゲーム機などは扱っていない。
"""
import json
import re
from datetime import date, timedelta

from bs4 import BeautifulSoup

from ..apple import apple_codes, apple_offer, ipad_offer
from ..common import CATALOG, load_json
from ..phones import android_key, phone_color, phone_colors, phone_key
from ..text import parse_yen

ID = "daiwan"
NAME = "ダイワンテレコム"
SHORT = "ダイワン"
URL = "https://shiroromu.jp/"

IPHONE_PAGE = URL + "product/sumaho/iphone"
PIXEL_PAGE = URL + "product/sumaho/pixel"
ANDROID_PAGES = [URL + "product/sumaho/" + p for p in ("galaxy", "xperia", "aquos")]
MAC_PAGE = URL + "product/pc/mac"
IPAD_PAGE = URL + "product/tablet/ipad"
MAX_AGE = timedelta(days=30)
# キャリアの欄 → android_key のキャリア名（UQ mobile 版は au 版として扱う。ここにない MVNO 版は使わない）
_CARRIERS = {"docomo": "docomo", "au": "au", "UQmobile": "au", "SoftBank": "SoftBank", "Rakuten": "楽天モバイル",
             "Y!mobile": "Y!mobile", "SIMフリー": "SIMフリー"}
_UPDATED = re.compile(r"買取価格更新日：(\d{4})/(\d{1,2})/(\d{1,2})")
_ITEMS = re.compile(r"const items = (\{.*\});")
_ITEM_ID = re.compile(r"[?&]id=(\d+)")
_MEMORY = re.compile(r"(\d+)GB (\d+(?:GB|TB))")   # メモリ・SSD
_SHOP_GPU = re.compile(r"(\d+)コア ")              # 店の行「M4 8コア 16GB 256GB」
_CATALOG_GPU = re.compile(r"(\d+)コアGPU")         # カタログ「（M4 10コアCPU/8コアGPU）」


def fetch(http):
    offers = []
    iphones = [(name, price, link, key) for carrier, name, price, link in _read_rows(http, IPHONE_PAGE)
               if carrier == "SIMフリー" and "国内版" in name and (key := phone_key(name)) and phone_colors(key)]
    differences = _color_differences(http, [link for _, _, link, _ in iphones])
    for name, price, link, key in iphones:
        colors = _colors(key, price, differences.get(_ITEM_ID.search(link)[1], {}))
        offers.append({"jan": None, "key": key, "name": name, "price": max(colors.values(), default=price),
                       "url": link, **({"colors": colors} if colors else {})})
    for carrier, name, price, link in _read_rows(http, PIXEL_PAGE):
        key = phone_key(name)
        if carrier == "SIMフリー" and "国内版" in name and key and phone_colors(key):
            offers.append({"jan": None, "key": key, "name": name, "price": price, "url": link})
    for page in ANDROID_PAGES:
        for carrier, name, price, link in _read_rows(http, page):
            key = android_key(name, _CARRIERS[carrier]) if carrier in _CARRIERS else None
            if key:
                offers.append({"jan": None, "key": key, "name": name, "price": price, "url": link})
    ipads = [(name, price, link, carrier == "SIMフリー") for carrier, name, price, link in _read_rows(http, IPAD_PAGE)
             if carrier in ("SIMフリー", "Wi-Fi") and "国内版" in name and ipad_offer(name, price, link, carrier == "SIMフリー")]
    differences = _color_differences(http, [link for _, _, link, _ in ipads])
    for name, price, link, cellular in ipads:
        colors = {color: price + d for color, d in differences.get(_ITEM_ID.search(link)[1], {}).items()}
        offer = ipad_offer(name, price, link, cellular, colors)
        if offer:
            offers.append(offer)
    specs = _mac_specs()
    for _, name, price, link in _read_rows(http, MAC_PAGE):
        offer = apple_offer(name, price, link)
        if offer["codes"] and all(_standard(name, specs.get(code)) for code in offer["codes"]):
            offers.append(offer)
    return offers


def _read_rows(http, page):
    """一覧の行の（キャリアの欄, 名前, 新品買取価格, 商品ページ）を順に返す。更新日が古い一覧は読まない。"""
    soup = BeautifulSoup(http.get(page).content, "html.parser")
    lead = soup.select_one(".product_lead_updated")
    updated = _UPDATED.search(lead.get_text() if lead else "")
    if not updated or date.today() - date(*map(int, updated.groups())) >= MAX_AGE:
        return
    for box in soup.select(".product_detail_onebox"):
        name = box.select_one(".detail_onebox_name h3, .detail_onebox_name h4")
        carrier = box.select_one(".detail_text_box p")
        link = box.select_one("a[href]")
        price = next((div.dd.get_text() for div in box.select("dl.detail_pricelist > div")
                      if div.dt and div.dt.get_text(strip=True) == "新品買取価格" and div.dd), None)
        if name and carrier and link and parse_yen(price):
            yield carrier.get_text(strip=True), " ".join(name.get_text(" ").split()), parse_yen(price), link["href"]


def _color_differences(http, links):
    """商品ページの JSON から {商品の id: {色: 減額}}。同じ機種のページは全容量・全キャリアの分を持つので、機種ごとに1回だけ開く。"""
    differences = {}
    for link in {link.split("?")[0]: link for link in links}.values():
        found = _ITEMS.search(http.get(link).text)
        for group in json.loads(found[1]).values() if found else ():
            for item_id, item in group.items():
                differences[item_id] = {c["name"]: c["price_difference"] for c in item["item_colors"]}
    return differences


def _colors(key, base, differences):
    """{公式の色名: 価格}。色が載っていなければ空（全色が一覧の価格）。"""
    colors = {}
    for name, difference in differences.items():
        color = phone_color(key, name)
        if color:
            colors[color] = base + difference
    return colors


def _mac_specs():
    """カタログの型番 → 商品名の（メモリ・SSD, GPU のコア数）。GPU のコア数は名前に書かれているときだけ。"""
    specs = {}
    for product in load_json(CATALOG)["products"]:
        memory = _MEMORY.search(product["name"])
        gpu = _CATALOG_GPU.search(product["name"])
        for code in apple_codes(" ".join(product.get("aliases", []))):
            specs[code] = (memory and memory.groups(), gpu and gpu[1])
    return specs


def _standard(name, spec):
    """店の行のメモリ・SSD（と GPU のコア数）が、カタログの型番の構成と同じか。"""
    if not spec or not spec[0]:
        return False
    memory = _MEMORY.search(name)
    gpu = _SHOP_GPU.search(name)
    return memory is not None and memory.groups() == spec[0] and spec[1] in (None, gpu and gpu[1])
