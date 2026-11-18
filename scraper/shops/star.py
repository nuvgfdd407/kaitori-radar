"""買取スター。

白ロム（新品）買取の店で、携帯買取のページ（/mobile?cate=N）にタブごとの価格表がある
（1 Apple / 2 docomo / 3 au / 4 SoftBank / 5 Y!mobile / 6 タブレット / 7 SIMフリー / 9 WiFiルーター / 8 中古端末）。
表の1行は「機種名・備考・買取価格」で、買取価格は未開封の価格（開封品の価格や減額は備考に書かれている）。
ページの「更新日期:2026/11/18」が30日以上前なら、そのページは使わない。
- iPhone（Apple のタブ）: 「iPhone 17 Pro 256GB」のような機種＋容量の行。備考に「アップルストア版」とある行だけを使う。
  色の違いは備考に「橙 -6000」「black / pink -2000」「ブルー/ブラック -2,000円」のような減額で書かれているので、全色の価格にする
- Galaxy・Xperia・AQUOS: docomo・au・SoftBank・SIMフリーのタブから取る。キャリアは型番（SC-53F など）か、なければタブで決める。
  備考に別の容量の価格（「512GB 165.000 256GB 156.000」）があれば、その容量の商品にも当てはめる。
  機種名に容量がない行（「Galaxy Z Fold7 SCG34 | 12GB/512GB 170.000 12GB/256GB 160.000 | ¥175,000」）は、
  本価格を備考のいちばん大きい容量の1つ上（ここでは 1TB）の価格とする（本価格が備考の価格より高いときだけ）。
  「Y!mobile同額」とある SoftBank 版の価格は Y!mobile 版にも当てはめる
- Pixel（SIMフリーのタブ）: Google ストア版の価格。「黒色72.000円」（その色の価格）「白のみ 他色-1.000」「黒白以外減額」
  （書かれた色だけがこの価格で、ほかの色は「他色」の減額があればその価格、なければ使わない）も読む
- 備考に「購入証明」とある価格は、買ったときの証明が要るので "note" にする
- iPad（タブレットのタブ）は備考に全色の型番、AirPods（Apple のタブ）は備考に型番と JAN がある。型番のない行は使わない
使わないもの: 「お問い合わせてください」の行、中古端末のタブ、Y!mobile・WiFiルーターのタブ（カタログの機種がない）、
家電買取のページ（/elec。表の「更新日期」が 2019/02/06 のまま）。
"""
import re
import unicodedata
from datetime import date, datetime, timedelta, timezone

from bs4 import BeautifulSoup

from ..apple import apple_offer
from ..phones import android_key, phone_color, phone_colors, phone_key, without_capacity
from ..text import parse_yen

ID = "star"
NAME = "買取スター"
SHORT = "スター"
URL = "https://www.kaitoristar.com/"

LIST_URL = URL + "mobile?cate={}"
APPLE, TABLET, SIMFREE = 1, 6, 7
# スマホのタブ → phones.py のキャリア名
CARRIERS = {2: "docomo", 3: "au", 4: "SoftBank", SIMFREE: "SIMフリー"}
TABS = [APPLE, *CARRIERS, TABLET]
PROOF_NOTE = "購入証明が必要"
APPLE_NOTE = "Apple Store版の価格"
MAX_AGE = timedelta(days=30)
JST = timezone(timedelta(hours=9))
# 色の漢字1文字 → 公式の色名を探すための別名（機種によってどの色を指すかが違うので、候補を順に試す）。
# phones.py の別名にない書き方（Pixel の「黒」「白」、Xperia の「青」）の分だけ
KANJI_COLORS = {"黒": ["black", "ブラック", "obsidian"], "白": ["white", "ホワイト", "porcelain"], "青": ["blue", "ブルー"]}
_UPDATED = re.compile(r"更新日期\s*:\s*(\d{4})/(\d{1,2})/(\d{1,2})")
# 「橙 -6000」「black / pink -2000」（色の減額）。「開封-1500」「キャリア版-2.000」も同じ形だが、色でないので飛ばす
_DEDUCTION = re.compile(r"([^\s\d.,/-]+(?:\s*/\s*[^\s\d.,/-]+)*)\s*-\s*([\d.,]+)")
# 「黒色72.000円」（その色の価格）
_COLOR_PRICE = re.compile(r"([^\s\d.,/-]+?)色\s*(\d{1,3}[.,]\d{3}|\d{4,})")
# 「白のみ」「黒白以外減額」
_ONLY = re.compile(r"([^\s\d.,/-]+?)(?:のみ|以外減額)")
# 「256GB 89.000」「12GB/512GB 170.000」（別の容量の価格）
_CAPACITY_PRICE = re.compile(r"(?:\d+GB?[/+])?(\d+(?:GB|TB))\s*(\d{1,3}[.,]\d{3}|\d{4,})")


def fetch(http):
    offers = []
    for tab in TABS:
        url = LIST_URL.format(tab)
        for name, note, price in _read_rows(http, url):
            if tab == TABLET or "AirPods" in name:
                offer = apple_offer(name, price, url, text=note)
                if offer["codes"]:
                    offers.append(offer)
            elif tab == APPLE or (tab == SIMFREE and "Pixel" in name):
                key = phone_key(name)
                # iPhone はアップルストア版の行だけ。「Pixel 9 Fold」は phone_key が Pixel 9 と読むので飛ばす
                if (key and phone_colors(key) and (tab != APPLE or "アップルストア版" in note)
                        and ("Fold" in key or "Fold" not in name)):
                    offers.append(_phone_offer(key, name, note, price, url))
            else:
                offers += [_phone_offer(key, name, note, p, url) for key, p in _android_prices(name, note, price, tab)]
    return offers


def _read_rows(http, url):
    """表の（機種名, 備考, 買取価格）を順に返す。価格のない行と、更新日が30日以上前のページは飛ばす。"""
    soup = BeautifulSoup(http.get(url).content, "html.parser")
    m = _UPDATED.search(soup.get_text())
    if m and datetime.now(JST).date() - date(*map(int, m.groups())) >= MAX_AGE:
        return
    for row in soup.select("table.table tbody tr"):
        cells = [unicodedata.normalize("NFKC", " ".join(td.get_text(" ").split())) for td in row.find_all("td")]
        price = parse_yen(cells[2]) if len(cells) == 3 else None
        if price:
            yield cells[0], cells[1], price


def _android_prices(name, note, price, tab):
    """Galaxy・Xperia・AQUOS の（機種＋容量＋キャリア, 価格）の一覧。備考の別の容量の価格と「Y!mobile同額」も含める。"""
    key = android_key(name) or android_key(name, CARRIERS[tab])
    if not key:
        return []
    model, carrier = without_capacity(key).rsplit(" ", 1)
    others = [(cap, parse_yen(p)) for cap, p in _CAPACITY_PRICE.findall(note)]
    if others and key == f"{model} {carrier}" and price > max(p for _, p in others):
        # 機種名に容量がない行の本価格は、備考の容量の1つ上の容量のもの（「12GB/512GB 170.000」→ 1TB）
        key = f"{model} {_one_size_up(cap for cap, _ in others)} {carrier}"
    pairs = [(key, price)] + [(f"{model} {cap} {carrier}", p) for cap, p in others]
    if "Y!mobile同額" in note:
        pairs += [(k.rsplit(" ", 1)[0] + " Y!mobile", p) for k, p in pairs]
    return pairs


def _one_size_up(capacities):
    """容量（「512GB」「256GB」）のいちばん大きいものの1つ上（512GB → 1TB）。"""
    gb = max(int(c[:-2]) * (1024 if c.endswith("TB") else 1) for c in capacities) * 2
    return f"{gb // 1024}TB" if gb >= 1024 else f"{gb}GB"


def _phone_offer(key, name, note, price, url):
    offer = {"jan": None, "key": key, "name": name, "price": price, "url": url}
    colors = _colors(key, note, price)
    if colors is not None:
        offer["colors"] = colors
    notes = [n for word, n in (("アップルストア版", APPLE_NOTE), ("購入証明", PROOF_NOTE)) if word in note]
    if notes:
        offer["note"] = "・".join(notes)
    return offer


def _colors(key, note, price):
    """備考の色の条件から {公式の色名: 価格}。色の条件が書かれていなければ None（全色が同じ価格）。"""
    colors = dict.fromkeys(phone_colors(key), price)
    found, others = False, None
    for marks, amount in _DEDUCTION.findall(note):
        if marks == "他色":
            others = price - parse_yen(amount)
        for color in _marked(key, marks):
            colors[color] -= parse_yen(amount)
            found = True
    for marks, amount in _COLOR_PRICE.findall(note):
        for color in _marked(key, marks):
            colors[color] = parse_yen(amount)
            found = True
    only = {color for marks in _ONLY.findall(note) for color in _marked(key, marks)}
    if only:
        colors = {c: p if c in only else others for c, p in colors.items()}
        colors = {c: p for c, p in colors.items() if p}
        found = True
    return colors if found else None


def _marked(key, marks):
    """「black / pink」「青/橙」「黒白」→ その機種の公式の色名の一覧（色でない言葉は飛ばす）。"""
    found = []
    for word in re.split(r"\s*/\s*", marks):
        words = list(word) if len(word) > 1 and all(c in KANJI_COLORS for c in word) else [word]
        found += [color for color in map(lambda w: _color(key, w), words) if color]
    return found


def _color(key, word):
    """色の言葉（「橙」「ブルー」「black」など）を、その機種の公式の色名にする。読み取れなければ None。"""
    for alias in [word, *KANJI_COLORS.get(word, [])]:
        if found := phone_color(key, alias):
            return found
        # 「ブルー」→「スカイブルー」のように、公式の色名の一部だけが書かれていることがある（1色に決まるときだけ）
        partial = [c for c in phone_colors(key) if alias.lower() in c.lower()]
        if len(partial) == 1:
            return partial[0]
    return None
