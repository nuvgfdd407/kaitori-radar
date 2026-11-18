"""買取ポケット。

秋葉原の携帯買取専門店。ジャンルごとのページ（iPhone は /kaitori1/、SIMフリーのスマホは /kaitori8/ など）に
手書きの HTML の表が並んでいて、1行が「商品名（色: JAN …）・買取価格・コメント」。列は表の見出しの行
（「買取価格」「新品買取額」の列が価格、「コメント」の列が条件）で決める。iPhone のページだけは「新品買取額」と
「中古買取」の2つの価格の列があるので、新品の列だけを使う。どのページにも「中古品の買取はお問い合わせ」とあり、
載っている価格は新品・未開封の価格（ページに更新日の表示はない）。
価格は「￥87 ,500」「￥90 ,0 00」のように数字の途中に空白が入るので、「￥」で区切ってそれぞれの数字を読む。
コメントに「問い合わせ」とある行（Xperia の SIMフリー版・アクションカメラ・iPad Pro 13インチの一部など）は
要問い合わせなので使わない。Mac のページ（/huaz1/）は全行がそうなので取らない。
- スマホ（iPhone・Pixel・Galaxy・Xperia・AQUOS）: 機種＋容量の1行に「色: JAN」が並ぶ。価格が1つなら、行に並んだ色
  （色が書かれていない行は全色）が同じ価格。行にない色は、別の容量の行で減額とされている色のことがあるので使わない。
  コメントに「BLUE減額」「Peony-3000」「ブラック、コーラル、ホワイト減額」「黒白-1000」のような色ごとの減額があれば、
  その色も使わない（減額の色が読み取れない行は使わない）。iPhone 17・18 Pro などは色の数だけ価格が並ぶので、
  色ごとの価格にする。色名が読み取れない色（Galaxy の英語の色名など）は JAN で突き合わせる。
  iPhone のページにキャリア版の行はなく、JAN も Apple 版（SIMフリー）のもの。iPhone・Pixel は iPhone と SIMフリーの
  ページの行だけを使う。キャリア版は docomo・au・SoftBank のページから取る（SoftBank のページには Y!mobile 版も載っている）。
  Pixel の「正規購入証明必須」、トレカの BOX と AirPods の一部の「予約必要」（持ち込む前の予約が要る）は "note" にする
- iPad・AirPods: 型番と JAN が書かれている。JAN が別の行と重なっていることがある（iPad Pro の Nano-texture の行に
  通常モデルの JAN）ので、型番だけで突き合わせる。色ごとの減額（「ピンク減額」）の色の型番は使わない
- ゲーム・カメラ（チェキ・デジカメ）・トレカの BOX: 商品名に JAN がある（1行に何色分かあれば同じ価格）。
  トレカは「シュリンクなしは買取不可」の店なので、BOX の価格はシュリンク付きの価格
Apple Watch のページ（/used/）は型番も JAN もないので取らない。中古品・Wi-Fi ルーター・家電・PC パーツのページは
カタログにないので取らない。
"""
import re
import unicodedata

from bs4 import BeautifulSoup

from ..apple import apple_offer
from ..phones import android_key, phone_color, phone_colors, phone_key
from ..text import parse_yen

ID = "pocket"
NAME = "買取ポケット"
SHORT = "ポケット"
URL = "https://pocketmall.jp/"

# iPhone / SIMフリー（Pixel・Galaxy・Xperia・AQUOS） / docomo / au / SoftBank（Y!mobile も）と、そのページのキャリア
PHONE_PAGES = [("kaitori1", "SIMフリー"), ("kaitori8", "SIMフリー"), ("kaitori2", "docomo"), ("kaitori4", "au"),
               ("kaitori3", "SoftBank")]
# タブレット（iPad） / イヤホン・ヘッドホン（AirPods）
APPLE_PAGES = ["huaz2", "huaz5"]
# ゲーム / カメラ / トレカ
JAN_PAGES = ["huaz4", "huaz3", "kaitori6"]
# コメントの条件（店の書き方, "note" に載せる言葉）
CONDITIONS = [("購入証明", "購入の証明が必要"), ("予約必要", "予約が必要")]
# 減額の色を漢字1文字で書く行（「黒減額」「黒白-1000」）の色
_KANJI = {"黒": ["ブラック", "Obsidian"], "白": ["ホワイト", "Porcelain"]}
_JAN = re.compile(r"(?<!\d)(\d{12,13})(?!\d)")
# コメントの「BLUE減額」「Peony-3000」「ブラック、コーラル、ホワイト減額」の色の部分
_REDUCTION = re.compile(r"([^\s、,/]+(?:[、,]\s*[^\s、,/]+)*)\s*(?:減額|-\s*\d)")
# 色ではない減額（キャリア版・開封・利用制限・保証開始・箱の状態など）
_NOT_COLOR = re.compile(r"版|開封|利用制限|[△▲]|保証|シール|潰れ|印|シュリンク")


def fetch(http):
    offers = []
    for page, carrier in PHONE_PAGES:
        for name, prices, comment, url in _read_rows(http, page):
            offers += _phone_offers(name, prices, comment, url, carrier)
    for page in APPLE_PAGES:
        for name, prices, comment, url in _read_rows(http, page):
            kept = _kept(_split(name), comment)
            if len(prices) == 1 and kept:
                # JAN は使わず、型番だけで突き合わせる
                offer = apple_offer(" ".join(label for label, _ in kept), prices[0], url)
                if offer["codes"]:
                    offers.append({**offer, **_note(comment)})
    for page in JAN_PAGES:
        for name, prices, comment, url in _read_rows(http, page):
            kept = _kept(_split(name), comment)
            if len(prices) == 1 and kept:
                offers += [{"jan": _jan13(jan), "name": name, "price": prices[0], "url": url, **_note(comment)}
                           for _, jan in kept if jan]
    return offers


def _read_rows(http, page):
    """表の行の（商品名, [価格…], コメント, ページの URL）を順に返す。価格のない行・要問い合わせの行は飛ばす。"""
    url = f"{URL}{page}/"
    soup = BeautifulSoup(http.get(url).content, "html.parser")
    columns = None  # 見出しの行で決めた（商品名, 価格, コメント）の列の位置
    for row in soup.select("tr"):
        cells = [unicodedata.normalize("NFKC", " ".join(c.get_text(" ").split()))
                 for c in row.find_all(["td", "th"], recursive=False)]
        heads = [i for i, c in enumerate(cells) if c in ("買取価格", "新品買取額")]
        if heads:
            columns = (heads[0] - 1, heads[0], cells.index("コメント") if "コメント" in cells else None)
            continue
        if not columns or len(cells) <= columns[1]:
            continue
        name = cells[columns[0]]
        comment = cells[columns[2]] if columns[2] is not None and columns[2] < len(cells) else ""
        # 「￥360,000 ￥360,000」（色ごとの価格）や「￥ 365 ,000」。NFKC で「￥」は「¥」になる。
        # 価格のない色は「￥」だけなので None にする（色と価格の並びがずれないように）
        prices = [parse_yen(text) for text in cells[columns[1]].split("¥")[1:]]
        if name and any(prices) and "問い合わせ" not in comment.replace(" ", ""):
            yield name, prices, comment, url


def _phone_offers(name, prices, comment, url, carrier):
    """スマホの1行の出品。価格が色の数だけ並んでいれば色ごと、1つなら行に並んだ色（書かれていなければ全色）から
    減額の色を除いた色の価格にする。色名が読み取れない色は、"colors" を空にして JAN で突き合わせる。"""
    if re.search(r"iPhone|Pixel", name, re.IGNORECASE):
        key = phone_key(name) if carrier == "SIMフリー" else None
    else:
        # 商品名からキャリアがわからなければ（SoftBank の「A402SO」など）、ページのキャリアにする
        key = android_key(name) or android_key(name, carrier)
    if not (key and phone_colors(key)):
        return []
    base = {"key": key, "name": name, "url": url, **_note(comment)}
    pairs = [(_label_color(key, label), _jan13(jan)) for label, jan in _split(name) if jan]
    if len(prices) > 1:
        if len(pairs) != len(prices):
            return []
        return [{**base, "jan": jan, "price": price, "colors": {color: price} if color else {}}
                for (color, jan), price in zip(pairs, prices) if price]
    reduced = _reduced_colors(key, comment)
    if reduced is None:
        return []
    price = prices[0]
    listed = [color for color, _ in pairs if color] if pairs else phone_colors(key)
    colors = {color: price for color in listed if color not in reduced}
    offers = [{**base, "jan": None, "price": price, "colors": colors}] if colors else []
    if not reduced:  # 減額の色がある行では、色名の読めない色がその色かもしれないので使わない
        offers += [{**base, "jan": jan, "price": price, "colors": {}} for color, jan in pairs if not color]
    return offers


def _split(name):
    """商品名を（色などの説明, その後ろの JAN）の組に分ける。最後の JAN より後ろは JAN なしの組にする。"""
    parts = _JAN.split(name)
    return list(zip(parts[0::2], [*parts[1::2], None]))


def _reduction_words(comment):
    """コメントの色ごとの減額（「BLUE減額」「Peony-3000」）の色の部分。キャリア版・開封などの減額は除く。"""
    words = [w for found in _REDUCTION.findall(comment) for w in re.split(r"[、,]\s*", found)]
    # 「黒白-1000」は黒と白の2色
    words = [c for w in words for c in (w if re.fullmatch(r"[黒白]+", w) else [w])]
    return [w for w in words if w and not _NOT_COLOR.search(w)]


def _reduced_colors(key, comment):
    """コメントで減額とされている色（公式の色名）。読み取れない色の減額があれば None。"""
    reduced = set()
    for word in _reduction_words(comment):
        found = set().union(*(_colors(key, w) for w in [word, *_KANJI.get(word, [])]))
        if not found:
            return None
        reduced |= found
    return reduced


def _label_color(key, label):
    """「色: JAN」の色の部分（JAN の前の言葉）を公式の色名にする。読み取れなければ None。"""
    words = re.findall(r"[^\s:\[\]]+", label)
    found = _colors(key, words[-1]) if words else set()
    return phone_color(key, label) or (found.pop() if len(found) == 1 else None)


def _colors(key, word):
    """言葉に当たる公式の色名。「BLUE」→ スカイブルー（別名）、「ブラック」→ スペースブラック（公式の色名の一部）。"""
    return {c for c in phone_colors(key) if c == phone_color(key, word) or _norm(word) in _norm(c)}


def _kept(pairs, comment):
    """（説明, JAN）の組から、コメントで減額とされている色の組を除く。減額の色がどの組かわからなければ空。"""
    words = [_norm(w) for w in _reduction_words(comment)]
    if not all(any(w in _norm(label) for label, _ in pairs) for w in words):
        return []
    return [(label, jan) for label, jan in pairs if not any(w in _norm(label) for w in words)]


def _note(comment):
    """コメントの条件（「正規購入証明必須」「予約必要」）の "note"。"""
    notes = [note for word, note in CONDITIONS if word in comment]
    return {"note": "・".join(notes)} if notes else {}


def _norm(text):
    return re.sub(r"\s+", "", text).lower()


def _jan13(jan):
    """12桁の UPC（Pixel・Meta Quest など）は頭に0を付けて13桁にする（カタログの書き方）。"""
    return jan.zfill(13)
