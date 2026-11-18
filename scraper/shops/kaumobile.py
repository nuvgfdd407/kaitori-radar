"""カウモバイル（大阪・梅田の携帯買取店）。

カテゴリごとのページ（/category/<名前>/）に、商品ごとの枠（div.price）が並ぶ静的な HTML。
ページはいくつかの節に分かれていて、節の頭に「[2026年11月17日]時点の価格です」と更新日がある。
更新日が30日以上前の節は使わない（2026-11 時点では Galaxy が9月1日、ゲーム機の旧型・限定版が2025年6月、GoPro が5月のまま）。
どのカテゴリにも「表示価格は新品未使用品の価格」とある。枠の形はカテゴリごとに違い、
表のある枠は新品の列（「新品」「未開封新品」「金額」「日本版 保証未」）だけを使う（中古・開封・制限△・ケア＋の列は使わない）。
表のない枠は、見出しが商品名で、価格は「新品：51300円(中古上限37000円)」や「416500円」。「問合せ」の行は飛ばす。
- iPhone: 機種ごとの表に「256GB バーガンディ」のような容量・色の行がある。「日本版 保証未（未開封）」の列を使う
  （保証開始・ケア＋・香港版・米国版は使わない）。色は「ブルー」「デザート」のように短く書かれていることがある
- Mac・Apple Watch・AirPods: 名前に型番と JAN がある。AirPods は状態ごとの表の「未開封-保証未開始」の価格を使う。
  Apple Watch の GPS+Cellular は、ネットワーク利用制限が「－」だと購入証明が必要なので、その条件を "note" に載せる
- ゲーム機・ソフト・チェキ・VR・GoPro: 名前に JAN がある（Steam Deck などは12桁の UPC なので前に0を付ける）。
  1行に JAN がいくつも書かれていれば、どれも同じ価格の商品として扱う（Steam Machine の行には同梱版の JAN も
  書かれているが、同梱版の行の方が高いので、scraper.update が高い方を使う）。
  PS5 本体と PlayStation Portal は、正規販売店の購入証明書がないと新品として買い取らないので "note" に載せる
- SIMフリー（Pixel・Xperia・AQUOS）: 「Google Pixel 11 Pro 256GB SIMフリー… JAN:…」のような行。機種＋容量（色が
  書かれていればその色）とキャリアで突き合わせ、機種を読めない行（キャリアの書かれていない Xperia など）は JAN で突き合わせる
- Galaxy: 機種ごとの表に「国内版SIMフリー 256GB」「SC-53G 256GB 制限○」のような行がある。「制限△」の行は使わない
iPad は世代・容量・色だけで型番も JAN も載っていないので使わない。デジカメ・DJI・Insta360 なども JAN がないので取らない。
"""
import re
from datetime import date, timedelta

from bs4 import BeautifulSoup

from ..apple import apple_offer
from ..phones import android_key, one_color, phone_color, phone_key
from ..text import parse_yen

ID = "kaumobile"
NAME = "カウモバイル"
SHORT = "カウモバ"
URL = "https://kaumobile.jp/"

PAGE = URL + "category/{}/"
APPLE_PAGES = ["mac", "applewatch", "airpods"]
JAN_PAGES = ["game", "game-soft", "instant-camera", "vr", "wearablecamera"]
MAX_AGE = timedelta(days=30)
PS5_NOTE = "正規販売店の購入証明書が必要"
WATCH_NOTE = "ネットワーク利用制限が「－」なら購入証明が必要"
# 表の新品の列の見出し
_NEW_COLUMNS = {"新品", "未開封新品", "金額", "日本版 保証未"}
# iPhone の短い色名 → scraper.phones の英語の別名（「ブルー」は iPhone 17 なら「ミストブルー」）
_SHORT_COLORS = {"ゴールド": "gold", "ブルー": "blue", "ブラック": "black", "ホワイト": "white", "ピンク": "pink",
                 "デザート": "desert", "ナチュラル": "natural"}
_DATE = re.compile(r"\[(\d{4})年(\d{1,2})月(\d{1,2})日\]")
_PRICE = re.compile(r"(?:新品：)?([\d,]+)円")
_JAN = re.compile(r"(?<!\d)\d{12,13}(?!\d)")
_PS5 = re.compile(r"PlayStation ?5|PlayStation Portal")


def fetch(http):
    offers = _iphone(http) + _galaxy(http) + _simfree(http)
    for page in APPLE_PAGES:
        offers += _apple(http, page)
    for page in JAN_PAGES:
        offers += _jan_offers(http, page)
    return offers


def _iphone(http):
    phones = {}  # {機種＋容量: {色: 価格}}
    for heading, block in _blocks(http, "iphone"):
        for label, price, _ in _rows(heading, block):
            key = phone_key(f"{heading} {label}")
            color = key and _color(key, label)
            if color:
                phones.setdefault(key, {})[color] = price
    return [{"jan": None, "key": key, "name": key, "price": max(colors.values()), "url": PAGE.format("iphone"),
             "colors": colors} for key, colors in phones.items()]


def _color(key, label):
    """「256GB ブルー」の色を、その機種の公式の色名にする。"""
    color = label.split()[-1]
    return phone_color(key, color) or phone_color(key, _SHORT_COLORS.get(color, ""))


def _galaxy(http):
    offers = []
    for heading, block in _blocks(http, "galaxy"):
        for label, price, _ in _rows(heading, block):
            name = f"{heading} {label}"
            key = "制限△" not in label and android_key(name)
            if key:
                offers.append({"jan": None, "key": key, "name": name, "price": price, "url": PAGE.format("galaxy")})
    return offers


def _simfree(http):
    offers = []
    for heading, block in _blocks(http, "simfree"):
        for name, price, _ in _rows(heading, block):
            model = name.split("JAN")[0]  # 後ろの JAN・減額の説明は除く
            key = phone_key(model)
            if key:
                colors = one_color(key, model, price)
                offers.append({"jan": None, "key": key, "name": name, "price": price, "url": PAGE.format("simfree"),
                               **({"colors": colors} if colors else {})})
            else:
                offers += [{"jan": jan, "name": name, "price": price, "url": PAGE.format("simfree")} for jan in _jans(name)]
    return offers


def _apple(http, page):
    offers = []
    for heading, block in _blocks(http, page):
        for name, price, header in _rows(heading, block):
            jans = _jans(name)
            offer = apple_offer(name, price, PAGE.format(page), jan=jans[0] if jans else None)
            if "購入証明" in header:  # Apple Watch の GPS+Cellular の表
                offer["note"] = WATCH_NOTE
            if offer["jan"] or offer["codes"]:  # エルメスなど型番のない行は使わない
                offers.append(offer)
    return offers


def _jan_offers(http, page):
    offers = []
    for heading, block in _blocks(http, page):
        note = {"note": PS5_NOTE} if _PS5.search(heading) else {}
        for name, price, _ in _rows(heading, block):
            offers += [{"jan": jan, "name": name, "price": price, "url": PAGE.format(page), **note} for jan in _jans(name)]
    return offers


def _jans(name):
    """名前に書かれた JAN の一覧（12桁の UPC は前に0を付けて13桁にする）。"""
    return list(dict.fromkeys(jan.zfill(13) for jan in _JAN.findall(name)))


def _blocks(http, page):
    """ページの商品の枠の（見出し, div.price）を順に返す。更新日が30日以上前の節の枠は飛ばす。"""
    soup = BeautifulSoup(http.get(PAGE.format(page)).content, "html.parser")
    fresh = False
    for el in soup.select("div.time, div.price"):
        if "time" in el["class"]:
            m = _DATE.search(el.get_text())
            fresh = bool(m) and date.today() - date(*map(int, m.groups())) < MAX_AGE
        elif fresh and el.h3:
            yield _text(el.h3), el


def _rows(heading, block):
    """枠の（商品名, 新品の価格, 表の見出しの1つ目のセル）を順に返す。表のない枠は見出しが商品名。価格のない行は飛ばす。"""
    tables = block.select("table")
    if not tables:
        m = _PRICE.match(_text(block.select_one(".price-item-price2")))
        if m and parse_yen(m.group(1)):
            yield heading, parse_yen(m.group(1)), ""
    for table in tables:
        col, header = None, ""
        for tr in table.select("tr"):
            cells = [_text(c) for c in tr.find_all(["th", "td"])]
            if tr.th:  # 見出しの行（表の途中にもある）
                col = next((i for i, c in enumerate(cells) if c in _NEW_COLUMNS), col)
                header = cells[0]
                continue
            if cells[0] == "未開封-保証未開始":  # AirPods の状態ごとの表（商品名は枠の見出し）
                name, price = heading, parse_yen(cells[1])
            elif col is not None and col < len(cells):
                name, price = cells[0], parse_yen(cells[col])
            else:
                continue
            if price:
                yield name, price, header


def _text(el):
    return " ".join(el.get_text(" ").split()) if el else ""
