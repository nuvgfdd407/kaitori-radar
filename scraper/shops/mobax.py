"""モバックス名古屋大須店。

WordPress のサイトで、ジャンルごとの買取価格表のページ（/p-561/ など）に、見出しと表が並んでいる。
ページの先頭に「2026年11月18日 12時30分 時点の参考価格」のような日時があり、価格は「【新品】の上限金額」。
日時が30日以上前のページは、価格が古いので使わない（Mac・Apple Watch・Galaxy・Xperia・Pixel・AQUOS のページは
2025年9月〜2026年6月で止まっているので、はじめから取らない）。
価格の数字や容量が「135</strong>,000円」「5<strong>12GB</strong>」のようにタグで分かれていることがあるので、
セルの文字はそのままつなげて読む（<br> だけ空白にする）。
- iPhone: 機種＋容量の行に「Apple版 新品未開封 / キャリア版 新品未開封 / キャリア版 新品開封済」の3列がある。
  Apple版の列だけを使う。色で価格が違うときは「258,000円 銀-1000円 赤-1000円」のように、色（漢字1文字）ごとの
  減額が書かれているので、全色の価格にする。「購入証明書必須」と書かれた価格は、Apple Store で買った証明
  （シリアル番号の書かれた書類）が要るので "note" にする。「準備中」の行は飛ばす
- ゲーム機（Switch・PlayStation・Xbox・その他のゲーム機）: 「モデル / 新品買取価格」の表で、モデルの欄に JAN がある
  （1行に何色分かの JAN が書かれていれば、それぞれに同じ価格）。Steam Deck・Meta Quest は12桁の UPC なので頭に0を付ける。
  JAN のない行（Switch のソフト・「各色」のコントローラーなど）と「要問合せ」の行は使わない。
  別の商品の行に同じ JAN が書かれていることがある（スプラトゥーン レイダースの行に Star Fox の JAN）ので、
  そういう JAN はどちらの価格か決められないので使わない。
  PS5 デジタル・エディションは製造時期（「26年9月以前製造 47,500円 26年10月以降製造 45,000円」）で価格が分かれているので、
  高い方を使い、価格の欄をそのまま "note" にする
- AirPods: 機種ごとの見出し（「AirPods Pro 3 MFHP4J/A」）に型番があり、その下の表に「新品未開封(保証未開始)」の価格がある
iPad は型番も JAN も載っていないので使わない。Apple Pencil などの周辺機器はカタログにないので取らない。
"""
import re
import unicodedata
from collections import Counter
from datetime import datetime, timedelta, timezone

from bs4 import BeautifulSoup

from ..apple import apple_offer
from ..phones import phone_color, phone_colors, phone_key
from ..text import parse_yen

ID = "mobax"
NAME = "モバックス名古屋大須店"
SHORT = "モバックス"
URL = "https://mobax-ohsu.com/"

IPHONE_PAGE = URL + "p-561/"
AIRPODS_PAGE = URL + "p-662/"
# Nintendo Switch / PlayStation / Xbox / その他のゲーム機（Steam Deck・Meta Quest・ROG Xbox Ally）
GAME_PAGES = [URL + f"p-{n}/" for n in (3297, 3305, 3307, 3309)]
APPLE_STORE_NOTE = "Apple Storeで購入した証明が必要"
MAX_AGE = timedelta(days=30)
JST = timezone(timedelta(hours=9))
# 減額の色の漢字1文字 → 公式の色名を探すための英語の別名（機種によってどの色を指すかが違うので、候補を順に試す）
KANJI_COLORS = {"黒": ["black"], "白": ["white"], "銀": ["silver"], "金": ["gold"], "青": ["blue", "glacier"],
                "赤": ["burgundy", "red"], "橙": ["orange"], "緑": ["green", "sage", "teal"],
                "紫": ["purple", "lavender"], "桃": ["pink"], "灰": ["natural"]}
_UPDATED = re.compile(r"(\d{4})年\s*(\d{1,2})月\s*(\d{1,2})日\s*(\d{1,2})時\s*(\d{1,2})分\s*時点")
_PRICE = re.compile(r"([\d,]+)円")
_DEDUCTION = re.compile(r"([^\s\d,円]+)\s*-\s*([\d,]+)円")
_JAN = re.compile(r"(?<!\d)(\d{12,13})(?!\d)")


def fetch(http):
    return _iphone_offers(http) + _airpods_offers(http) + _game_offers(http)


def _iphone_offers(http):
    offers = []
    for _, rows in _tables(http, IPHONE_PAGE):
        if len(rows[0]) < 2 or "Apple版" not in rows[0][1]:
            continue  # 色・容量・型番の表など
        for row in rows[1:]:
            key = phone_key(row[0])
            colors = _colors(key, row[1]) if key else None
            if colors:
                offer = {"jan": None, "key": key, "name": row[0], "price": max(colors.values()), "url": IPHONE_PAGE,
                         "colors": colors}
                if "購入証明書必須" in row[1]:
                    offer["note"] = APPLE_STORE_NOTE
                offers.append(offer)
    return offers


def _colors(key, text):
    """「258,000円 銀-1000円 赤-1000円」→ {公式の色名: 価格}（書かれた色だけ減額する）。
    価格がない（「準備中」）か、減額の色を読み取れなければ None。"""
    base = _PRICE.match(text)
    if not base or not phone_colors(key):
        return None
    colors = dict.fromkeys(phone_colors(key), parse_yen(base.group(1)))
    for mark, amount in _DEDUCTION.findall(text):
        color = _color(key, mark)
        if not color:
            return None
        colors[color] -= parse_yen(amount)
    return colors


def _color(key, mark):
    """減額の色の漢字（「銀」「赤」など）を、その機種の公式の色名にする。"""
    if found := phone_color(key, mark):
        return found
    for alias in KANJI_COLORS.get(mark, []):
        if found := phone_color(key, alias):
            return found
    return None


def _airpods_offers(http):
    offers = []
    for heading, rows in _tables(http, AIRPODS_PAGE):
        for row in rows:
            m = _PRICE.search(row[-1]) if len(row) == 2 and "未開封" in row[0] else None
            if m:
                offers.append(apple_offer(heading, parse_yen(m.group(1)), AIRPODS_PAGE))
    return offers


def _game_offers(http):
    offers = []
    for page in GAME_PAGES:
        for _, table in _tables(http, page):
            for row in table:
                prices = [parse_yen(p) for p in _PRICE.findall(row[-1])] if len(row) == 2 else []
                for jan in _JAN.findall(row[0]) if prices else []:
                    offer = {"jan": jan.zfill(13), "name": row[0], "price": max(prices), "url": page}
                    if len(prices) > 1:  # 製造時期で価格が分かれている
                        offer["note"] = row[-1]
                    offers.append(offer)
    # 別の商品の行に同じ JAN が書かれていたら（書き間違い）、どちらの価格か決められないので使わない
    count = Counter(o["jan"] for o in offers)
    return [o for o in offers if count[o["jan"]] == 1]


def _tables(http, page):
    """ページの表を（直前の見出し, 行ごとのセルの文字のリスト）で返す。日時が30日以上前のページは空。"""
    main = BeautifulSoup(http.get(page).content, "html.parser").select_one("main")
    m = _UPDATED.search(main.get_text())
    if not m or datetime.now(JST) - datetime(*map(int, m.groups()), tzinfo=JST) >= MAX_AGE:
        return []
    for br in main.find_all("br"):
        br.replace_with(" ")
    tables, heading = [], ""
    for el in main.find_all(["h2", "table"]):
        if el.name == "h2":
            heading = _text(el)
            continue
        rows = [[_text(td) for td in tr.find_all(["td", "th"])] for tr in el.select("tr")]
        if rows:
            tables.append((heading, rows))
    return tables


def _text(el):
    return " ".join(unicodedata.normalize("NFKC", el.get_text()).split())
