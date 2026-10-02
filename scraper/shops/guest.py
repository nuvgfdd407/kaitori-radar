"""ゲストモバイル。

ページごとの表（機種名・備考・価格）に載っている。商品ごとのページはない。
- iPhone: 「iPhone 18 Pro 256GB」のように機種＋容量ごと。価格は「新品未開封品」の列を使う。
  色による減額は備考に「色減額:シルバー-9000/ブラック-9000」のように書かれている
- Android: SIMフリー・docomo・au（UQ を含む）・SoftBank（Y!mobile を含む）のページ。価格は「未使用品」の列
  （開封品は備考に書かれた額を減額するので、未使用品の価格は未開封品の価格）。
  SoftBank のページの機種は、備考に「Yモバイル/ソフトバンク同額」とあれば Y!mobile 版も同じ価格
- ゲーム機など: 「ピックアップ買取機種」のページ。JAN は備考に「JAN:…」と書かれている
色減額が読み取れない書き方（「黒/赤/桃 -2000」など）の機種は、色ごとの価格がわからないので使わない。
"""
import re

from bs4 import BeautifulSoup

from ..phones import android_key, phone_color, phone_colors, phone_key
from ..text import parse_yen

ID = "guest"
NAME = "ゲストモバイル"
SHORT = "ゲスト"
URL = "https://www.guestmobile.jp/"

IPHONE_PAGE = URL + "iphone%e8%b2%b7%e5%8f%96%e4%be%a1%e6%a0%bc/"
# （ページ, キャリア）。SoftBank のページには Y!mobile 版も載っている
ANDROID_PAGES = [
    (URL + "sim%e3%83%95%e3%83%aa%e3%83%bc%e8%b2%b7%e5%8f%96%e4%be%a1%e6%a0%bc/", "SIMフリー"),
    (URL + "docomo%e8%b2%b7%e5%8f%96%e4%be%a1%e6%a0%bc/", "docomo"),
    (URL + "au%e8%b2%b7%e5%8f%96%e4%be%a1%e6%a0%bc/", "au"),
    (URL + "sb%e8%b2%b7%e5%8f%96%e4%be%a1%e6%a0%bc/", "SoftBank"),
]
PICKUP_PAGE = URL + "%e3%83%94%e3%83%83%e3%82%af%e3%82%a2%e3%83%83%e3%83%97%e8%b2%b7%e5%8f%96%e6%a9%9f%e7%a8%ae/"
_JAN = re.compile(r"JAN\s*[:：]\s*(\d{13})")


def fetch(http):
    offers = []
    for name, note, price in _read_rows(http, IPHONE_PAGE):
        offers += _phone_offer(phone_key(name), name, note, price, IPHONE_PAGE)
    for page, carrier in ANDROID_PAGES:
        for name, note, price in _read_rows(http, page):
            if "Pixel" in name:
                offers += _phone_offer(phone_key(name), name, note, price, page)
                continue
            for c in _carriers(carrier, note):
                offers += _phone_offer(android_key(name, c), name, note, price, page)
    for name, note, price in _read_rows(http, PICKUP_PAGE):
        offers += [{"jan": jan, "name": name, "price": price, "url": PICKUP_PAGE} for jan in _JAN.findall(note)]
    return [o for o in offers if o["price"]]


def _read_rows(http, page):
    """表の（機種名, 備考, 価格）を順に返す。価格は左から1つ目の価格の列（新品未開封品・未使用品）。"""
    soup = BeautifulSoup(http.get(page).content, "html.parser")
    for row in soup.select("table tr"):
        cells = [" ".join(c.get_text(" ").split()) for c in row.find_all("td")]
        if len(cells) >= 3 and re.fullmatch(r"[\d,]+円", cells[2]):
            yield cells[0], cells[1], parse_yen(cells[2])


def _carriers(carrier, note):
    if carrier != "SoftBank":
        return [carrier]
    if "同額" in note and re.search(r"Y!?\s*モバイル|ワイモバイル", note):
        return ["SoftBank", "Y!mobile"]
    if re.search(r"Y!?\s*モバイル版", note):
        return ["Y!mobile"]
    return ["SoftBank"]


def _phone_offer(key, name, note, price, page):
    if not (key and phone_colors(key)):
        return []  # 古い機種や、扱っていない機種
    colors = _color_prices(key, price, note)
    if colors is None:
        return []
    return [{"jan": None, "key": key, "name": name, "price": price, "url": page, "colors": colors}]


def _color_prices(key, base, note):
    """備考の「色減額:シルバー-9000/ブラック-9000」から {色: 価格}。読み取れない書き方なら None。"""
    colors = dict.fromkeys(phone_colors(key), base)
    m = re.search(r"色減額\s*[:：]\s*", note)
    if not m or note[m.end():].startswith("なし"):
        return colors
    pending, parsed = [], False
    for token in re.findall(r"[-−]\s*(?:\d+|なし)|[^\s/／、,:：\-−]+", note[m.end():]):
        if token[0] in "-−":
            amount = re.sub(r"\D", "", token)
            for color in pending:
                colors[color] = base - int(amount or 0)
            pending, parsed = [], True
        elif color := phone_color(key, token):
            pending.append(color)
        else:
            break  # 色の部分の終わり（または読み取れない書き方）
    return colors if parsed and not pending else None
