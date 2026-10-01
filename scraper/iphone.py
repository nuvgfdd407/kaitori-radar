"""iPhone の商品名から「機種＋容量」を読み取る。

iPhone は店舗によって、色ごとに分けて載せていたり、JANがなかったりするので、
「iPhone 17 Pro 256GB」のような機種＋容量の名前で突き合わせる。
カタログの iPhone の商品名も、この形（iphone_key の結果と同じ文字列）にしておく。
"""
import re
import unicodedata

# 「iPhone 17 Pro Max」「iPhone16e」「iPhone 17 air」「iPhone Air」「iPhone Duo」などを読む
_MODEL = re.compile(r"iPhone\s*(?:(\d{2})\s*(e)?\s*(Pro\s*Max|Pro|Plus|Air)?|(Air|Duo))", re.IGNORECASE)
_CAPACITY = re.compile(r"(\d+)\s*(GB|TB)", re.IGNORECASE)
_VARIANTS = {"promax": "Pro Max", "pro": "Pro", "plus": "Plus"}


def iphone_key(name):
    """「【未開封】iPhone 17 Pro 256GB orange」→「iPhone 17 Pro 256GB」。読み取れなければ None。"""
    text = unicodedata.normalize("NFKC", name or "")
    model = _MODEL.search(text)
    capacity = _CAPACITY.search(text, model.end()) if model else None
    if not model or not capacity:
        return None
    generation, e, variant, other = model.groups()
    if other:
        label = f"iPhone {other.capitalize()}"
    else:
        variant = re.sub(r"\s+", "", variant or "").lower()
        if variant == "air":  # 「iPhone 17 Air」と書く店舗がある
            label = "iPhone Air"
        else:
            label = f"iPhone {generation}{'e' if e else ''}"
            if variant:
                label += " " + _VARIANTS[variant]
    return f"{label} {int(capacity.group(1))}{capacity.group(2).upper()}"


# 機種ごとの色（公式の日本語名）と、店舗での別の書き方（英語・漢字1文字など）。
# 公式の名前そのものも別名として扱う。商品ページの「色別の買取価格」はこの順に並べる
_PRO_18 = {"バーガンディ": ["burgundy"], "ブラック": ["black"], "グレイシャー": ["glacier", "グレイシャ"],
           "シルバー": ["silver"]}
_PRO_17 = {"コズミックオレンジ": ["orange", "オレンジ", "橙"], "ディープブルー": ["blue", "ブルー", "青"],
           "シルバー": ["silver", "銀"]}
_PRO_16 = {"ブラックチタニウム": ["black", "黒"], "ホワイトチタニウム": ["white", "白"],
           "ナチュラルチタニウム": ["natural", "灰"], "デザートチタニウム": ["desert", "金"]}
_BASE_16 = {"ブラック": ["black", "黒"], "ホワイト": ["white", "白"], "ピンク": ["pink", "桃"],
            "ティール": ["teal", "緑"], "ウルトラマリン": ["ultramarine", "青"]}
COLORS = {
    "iPhone 18 Pro": _PRO_18,
    "iPhone 18 Pro Max": _PRO_18,
    "iPhone Duo": {"スターホワイト": ["white"], "ナイトスカイ": ["black"]},
    "iPhone 17 Pro": _PRO_17,
    "iPhone 17 Pro Max": _PRO_17,
    "iPhone 17": {"ラベンダー": ["purple", "lavender"], "セージ": ["green", "sage"], "ミストブルー": ["blue"],
                  "ホワイト": ["white"], "ブラック": ["black"]},
    "iPhone Air": {"スカイブルー": ["skyblue", "sky blue", "blue", "青"], "ライトゴールド": ["gold"],
                   "クラウドホワイト": ["white"], "スペースブラック": ["black"]},
    "iPhone 17e": {"ブラック": ["black"], "ホワイト": ["white"], "ソフトピンク": ["pink"]},
    "iPhone 16 Pro": _PRO_16,
    "iPhone 16 Pro Max": _PRO_16,
    "iPhone 16": _BASE_16,
    "iPhone 16 Plus": _BASE_16,
    "iPhone 16e": {"ブラック": ["black"], "ホワイト": ["white"]},
}


def iphone_colors(key):
    """「iPhone 17 Pro 256GB」の色の一覧（公式の日本語名）。わからない機種は空。"""
    return list(COLORS.get(_model(key), {}))


def iphone_color(key, text):
    """商品名の容量より後ろの部分などから色を読み取り、公式の日本語名にする。読み取れなければ None。"""
    text = unicodedata.normalize("NFKC", text or "").lower()
    names = [(alias.lower(), color) for color, aliases in COLORS.get(_model(key), {}).items()
             for alias in [color, *aliases]]
    # 「ブラックチタニウム」が「ブラック」より先に当たるように、長い名前から探す
    for alias, color in sorted(names, key=lambda n: -len(n[0])):
        if alias in text:
            return color
    return None


def color_part(name):
    """商品名の容量より後ろの部分（色が書かれている部分）。"""
    text = unicodedata.normalize("NFKC", name or "")
    capacity = _CAPACITY.search(text)
    return text[capacity.end():] if capacity else ""


def _model(key):
    return re.sub(r"\s+\d+(GB|TB)$", "", key or "")


def one_color(key, name, price):
    """色ごとに別の商品として載っている店舗用。{色: 価格}（色が読み取れなければ空）。"""
    color = iphone_color(key, color_part(name))
    return {color: price} if color else {}
