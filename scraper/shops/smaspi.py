"""スマスピ（スマホスピタル）。

スマホのカテゴリ（/smartphone/iphone/・/smartphone/galaxy/ など）のページに、機種ごとの表が並んでいる（アメモバと同じ作り）。
表1つが1行で、「国内版SIMフリー」「docomo版SIMフリー」のようなキャリアの欄と、「Apple iPhone 18 Pro 国内版SIMフリー 256GB」
「Galaxy S26 Ultra docomo版SIMフリー SC-53G 256GB」のような機種名、価格は「未開封買取価格」（Android などは「新品買取価格」。
どちらも未開封・保証未開始の価格）と「中古買取価格」。新品の方だけを使う。JAN は載っていない。
ページの先頭に「買取価格更新日」があり、30日以上前のページは使わない。
行の「査定する」のリンク先（機種ごとのページ）の JSON（json_str）に、容量と色ごとの価格がある（s_rank が新品）。
一覧の価格が全部「0円」になり、機種ごとのページの価格も一律8万円低くなっている時間があった（2026-11-18 16時台。
価格の入れ替え中とみられる）。0円の行は飛ばし、機種ごとのページの価格が一覧の価格と食い違うときは一覧の価格を全色に当てはめる。
- iPhone・Pixel: 国内版SIMフリーの行だけを使う（キャリア版の行は使わない）。色ごとの価格は機種ごとのページから読む
  （17 Pro 256GB のコズミックオレンジだけ安いなど）。カタログにある機種のページだけ開く
- Galaxy・Xperia・AQUOS: キャリアの欄（UQ mobile 版は au 版として扱う）を android_key に渡す。
  一覧の価格は、機種ごとのページで最初に出てくる色の価格にすぎない。Galaxy は行が1つでも色で価格が違ったり
  （Z Flip7 SoftBank版はブルーシャドウ 97,000円・ジェットブラック 100,000円）、買い取らない色があったりするので、
  機種ごとのページで色ごとの価格を読む。同じ機種・容量の行が容量の書き方を変えて2つ出ることもある（Z Flip8 の
  「12GB/256GB」129,000円がピンク・グラファイト・クリーム、「256GB」124,000円がミント）。
  Xperia・AQUOS は色による価格の違いがなかった（2026-11-18）ので、一覧の価格を全色に当てはめる
  （Android の機種ごとのページを全部開くと120回を超える）。行が2つで価格が違うときだけ機種ごとのページを読む
- 「国内版SIMフリー」の欄に入っている海外版の行、スターウォーズ限定などの限定版、J:COM 版（欄は「SIMフリー」）は使わない。
  mineo・OCN・IIJmio・ahamo 版の行も使わない
- 2026-11-05 から、SoftBank の確認システムが使えない間の暫定の条件がある（お知らせ /news/80/・/news/81/）。
  SoftBank・Y!mobile 版の Android は、キャリアが発行した一括購入・完済の証明書がないと新品でも買い取らない。
  国内版SIMフリーの iPhone は、Apple Store のレシート（シリアル番号入り）がないとネットワーク利用制限「△」相当で査定する
  （機種ごとのページの計算では、SIMフリー版の△の減額は0円）。どちらも "note" にする。条件が終わったら note を外す
iPad やゲーム機などの買取はない。
"""
import json
import re
from datetime import date, timedelta

from bs4 import BeautifulSoup

from ..phones import android_key, phone_color, phone_colors, phone_key
from ..text import parse_yen

ID = "smaspi"
NAME = "スマスピ"
SHORT = "スマスピ"
URL = "https://smaspi.jp/"

IPHONE_PAGES = [URL + "smartphone/iphone/", URL + "smartphone/google-pixel/"]
ANDROID_PAGES = [URL + "smartphone/" + p + "/" for p in ("galaxy", "xperia", "aquos")]
MAX_AGE = timedelta(days=30)
# キャリアの欄の頭 → phones.py のキャリア名（「docomo版SIMフリー」も「docomo」もある）
_CARRIERS = [("国内版SIMフリー", "SIMフリー"), ("SIMフリー", "SIMフリー"), ("docomo", "docomo"), ("au", "au"), ("UQ", "au"),
             ("SoftBank", "SoftBank"), ("楽天モバイル", "楽天モバイル"), ("Y!mobile", "Y!mobile")]
_OTHER_VERSIONS = re.compile(r"海外版|限定|J:?COM", re.IGNORECASE)
# 暫定の条件（2026-11-05 から）
APPLE_STORE_NOTE = "Apple Storeのレシート（シリアル番号入り）がないと△相当で査定"
PAYMENT_NOTE = "キャリア発行の一括購入・完済証明書が必要（ないと買取不可）"
_JSON = re.compile(r"json_str\s*=\s*'(\[.*?\])';", re.S)


def fetch(http):
    offers, details = [], {}  # details: 機種ごとのページの価格（同じページを何度も開かない）

    def detail(link):
        if link not in details:
            details[link] = _detail_prices(http, link)
        return details[link]

    for page in IPHONE_PAGES:
        for carrier, name, price, link in _read_rows(http, page):
            key = phone_key(name)
            if carrier != "SIMフリー" or not (key and phone_colors(key)):
                continue  # キャリア版と、古い機種・扱っていない機種
            colors = _color_prices(key, detail(link), {_volume(name)})
            if price not in colors.values():  # 機種ごとのページが一覧と食い違う（価格の入れ替え中など）
                colors = dict.fromkeys(phone_colors(key), price)
            offer = {"jan": None, "key": key, "name": name, "price": price, "url": link, "colors": colors}
            if key.startswith("iPhone"):
                offer["note"] = APPLE_STORE_NOTE
            offers.append(offer)
    rows = []
    for page in ANDROID_PAGES:
        for carrier, name, price, link in _read_rows(http, page):
            key = android_key(name, carrier) if carrier else None
            if key:
                rows.append((key, carrier, name, price, link))
    seen = set()
    for key, carrier, name, _, link in rows:
        if key in seen:
            continue  # 同じ機種・容量・キャリアは先の行だけ（au 版と UQ mobile 版など）
        seen.add(key)
        same = [(n, p) for k, _, n, p, l in rows if k == key and l == link]
        # 機種ごとのページが一覧と食い違って全色に当てはめるとき、高い方の行の価格にならないように安い方を載せる
        offer = {"jan": None, "key": key, "name": name, "price": min(p for _, p in same), "url": link}
        if carrier in ("SoftBank", "Y!mobile"):
            offer["note"] = PAYMENT_NOTE
        if key.startswith("Galaxy") or len({p for _, p in same}) > 1:
            colors = _color_prices(key, detail(link), {_volume(n) for n, _ in same})
            if all(p in colors.values() for _, p in same):  # 食い違えば（価格の入れ替え中など）一覧の価格を全色に当てはめる
                offer["colors"] = colors
        offers.append(offer)
    return offers


def _read_rows(http, page):
    """一覧の（キャリア, 機種名, 新品の価格, 機種ごとのページ）を順に返す。キャリアは phones.py の名前（使わない版は None）。
    更新日が古いページと、価格のない行は飛ばす。"""
    soup = BeautifulSoup(http.get(page).content, "html.parser")
    updated = soup.select_one(".header__update-date time")
    if not updated or date.today() - date.fromisoformat(updated["datetime"]) >= MAX_AGE:
        return
    for box in soup.select("table.model__sub-box"):
        carrier, name = box.select_one(".product_carrier_box-item th"), box.select_one(".model__title-02")
        price, link = box.select_one("td.new"), box.select_one("a[href]")
        if not (carrier and name and price and link):
            continue
        name = " ".join(name.get_text(" ").split())
        price = price.get_text(strip=True)
        if not re.fullmatch(r"[\d,]+円", price) or not parse_yen(price):
            continue
        head = carrier.get_text(strip=True)
        c = next((label for prefix, label in _CARRIERS if head.startswith(prefix)), None)
        yield None if _OTHER_VERSIONS.search(name) else c, name, parse_yen(price), URL.rstrip("/") + link["href"]


def _volume(name):
    """行の機種名の最後の「256GB」「12GB/256GB」（機種ごとのページの容量の書き方と同じ）。"""
    return name.rsplit(" ", 1)[-1]


def _detail_prices(http, page):
    """機種ごとのページの {(容量, 色): 新品の価格}。読めなければ空。"""
    m = _JSON.search(http.get(page).text)
    if not m:
        return {}
    try:
        items = json.loads(m.group(1))
    except ValueError:
        return {}
    return {(i.get("volume"), i.get("color")): int(float(i.get("s_rank_purchase_price") or 0)) for i in items}


def _color_prices(key, detail, volumes):
    """{公式の色名: 価格}（その容量の書き方の行の色だけ）。"""
    colors = {}
    for (volume, color), price in detail.items():
        official = phone_color(key, color or "")
        if volume in volumes and official and price:
            colors[official] = price
    return colors
