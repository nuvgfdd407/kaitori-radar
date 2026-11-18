"""モバイルミックス。

買取商品一覧（/?category=N）のカテゴリごとのページに、全商品の行が載っている（商品ごとのページはない）。
使うのは「Apple(iPhone)」（7）・「Apple(others)」（8: iPad・AirPods）・「Google」（4: Pixel）。
「買取強化」（トップ）は他のカテゴリと同じ行の抜粋、「Apple(iPhone開封済)」（10）は開封品なので読まない。
Cookie がないと /cookie-error に302され、そこで Cookie を受け取って元のページに302で戻る（http.session がそのまま保持する）。
1つの商品は2行で、1行目が機種名と価格、2行目が状態（「未開封」）・減額の説明・買取申込の欄。
申込の欄の色の選択肢（radio）の value がその色の減額（「-2000」など）で、価格＋減額がその色の価格。
価格は「未開封」の行だけを使い、価格が0円以下になる色（「グレイシャー買取不可」は -価格 になっている）は使わない。
ネットワーク利用制限△・保証開始済みの減額は使わない（基準の価格は○・保証開始前の未開封品）。
ページの「更新日：2026/11/18」が30日以上前のページは使わない。JAN は載っていない。
- iPhone・Pixel: 「iPhone 18 Pro 256GB」「Google Pixel 11 Pro 256GB」のように機種＋容量ごと。キャリア版・海外版の区別はなく、
  国内の未開封品の価格として使う。色の選択肢は公式の色名（Pixel は英語）で、選択肢にない色は買い取っていない
- iPad・AirPods: 型番で突き合わせる。型番は色の選択肢（「ブルー/MD4A4J/A」）か、機種名・減額の説明（「MDWL4J/A/MDWK4J/A」
  「MDWM4/MDWN4」のように J/A を省くこともある）に書かれている。説明に並んだ型番は色の選択肢と同じ順
  （2026-11 時点で確かめた。選択肢より型番が多い行は、選択肢の数だけ前から使う）
Fitbit は型番が書かれていないので使わない。
"""
import re
from datetime import date, timedelta

from bs4 import BeautifulSoup

from ..apple import apple_codes
from ..phones import phone_color, phone_colors, phone_key
from ..text import parse_yen

ID = "mobilemix"
NAME = "モバイルミックス"
SHORT = "ミックス"
URL = "https://mobile-mix.jp/"

PAGES = [URL + "?category=" + c for c in ("7", "8", "4")]  # iPhone・iPad と AirPods・Pixel
MAX_AGE = timedelta(days=30)
_UPDATED = re.compile(r"更新日：(\d{4})/(\d{1,2})/(\d{1,2})")
# J/A を省いた型番（「MDWM4」）
_SHORT_CODE = re.compile(r"\b(M[A-Z0-9]{3}\d)(?![A-Z0-9])")


def fetch(http):
    offers = []
    for page in PAGES:
        for name, note, colors in _read_rows(http, page):
            key = phone_key(name)
            if key and phone_colors(key):
                prices = {}
                for label, price in colors:
                    if color := phone_color(key, label):
                        prices[color] = price
                if prices:
                    offers.append({"jan": None, "key": key, "name": name, "price": max(prices.values()), "url": page,
                                   "colors": prices})
                continue
            codes = _code_prices(name, note, colors)
            if codes:
                offers.append({"jan": None, "codes": codes, "name": name, "price": max(codes.values()), "url": page})
    return offers


def _read_rows(http, page):
    """未開封の商品の（機種名, 減額の説明, [(色の選択肢, 価格)]）を順に返す。更新日が古いページは読まない。"""
    soup = BeautifulSoup(http.get(page).content, "html.parser")
    title = soup.select_one("h2.title2")
    updated = _UPDATED.search(title.get_text() if title else "")
    if not updated or date.today() - date(*map(int, updated.groups())) >= MAX_AGE:
        return
    for row in soup.select("table.list tr[id]"):
        name, price, detail = row.select_one("td.product"), row.select_one("td.price"), row.find_next_sibling("tr")
        base = parse_yen(price.get_text()) if price else None
        cells = detail.find_all("td", recursive=False) if detail else []
        if not (name and base and len(cells) > 1 and cells[0].get_text(strip=True) == "未開封"):
            continue
        colors = []
        for label in detail.select(".colorCircle label"):
            adjust = label.input.get("value") if label.input else None
            if adjust and re.fullmatch(r"-?\d+", adjust) and base + int(adjust) > 0:
                colors.append((label.get_text(strip=True), base + int(adjust)))
        yield " ".join(name.get_text(" ").split()), " ".join(cells[1].get_text(" ").split()), colors


def _code_prices(name, note, colors):
    """iPad・AirPods の {型番: 価格}。色の選択肢に型番がなければ、機種名・説明の型番を選択肢の順に当てる。"""
    listed = apple_codes(name + " " + _SHORT_CODE.sub(r"\1J/A", note))
    prices = {}
    for i, (label, price) in enumerate(colors):
        code = (apple_codes(label) or listed[i:i + 1] or [None])[0]
        if code:
            prices[code] = price
    return prices
