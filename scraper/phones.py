"""スマホ（iPhone・Google Pixel・Galaxy・Xperia・AQUOS）の商品名から「機種＋容量」と色を読み取る。

スマホは店舗によって、色ごとに分けて載せていたり、JANがなかったりするので、
「iPhone 17 Pro 256GB」「Pixel 10 Pro 256GB」のような機種＋容量の名前と、色で突き合わせる。
カタログのスマホの商品名は「<phone_key の結果> <公式の色名>」の形にしておく。

Galaxy・Xperia・AQUOS はキャリア版（docomo・au など）も別の商品なので、機種＋容量のあとにキャリアを付けて
「Galaxy S26 Ultra 256GB docomo」のようにする。キャリアは、店舗のカテゴリでわかるときは引数で渡し、
わからないときは商品名（「docomo版」「SIMフリー」や、SC-53G のような型番）から読む。
"""
import re
import unicodedata

# 「iPhone 17 Pro Max」「iPhone16e」「iPhone 17 air」「iPhone Air」「iPhone Duo」などを読む
_MODEL = re.compile(r"iPhone\s*(?:(\d{2})\s*(e)?\s*(Pro\s*Max|Pro|Plus|Air)?|(Air|Duo))", re.IGNORECASE)
# 「Pixel 10 Pro XL」「Pixel 10a」「Pixel 9 Pro Fold」などを読む
_PIXEL = re.compile(r"Pixel\s*(\d{1,2})\s*(a|Pro\s*Fold|Pro\s*XL|Pro)?(?![A-Za-z])", re.IGNORECASE)
# 「256GB」「1TB」のほか、「256G+12G」（容量＋メモリ）のような書き方もある
_CAPACITY = re.compile(r"(\d+)\s*(GB|TB|G)(?![A-Za-z])", re.IGNORECASE)
_VARIANTS = {"promax": "Pro Max", "pro": "Pro", "plus": "Plus"}

# Galaxy・Xperia・AQUOS の機種名（読み取るための正規表現, 表記をそろえる関数）
_ANDROID = [
    (re.compile(r"Galaxy\s*Z\s*(Fold|Flip)\s*(\d+)\s*(Ultra|FE)?(?![A-Za-z])", re.IGNORECASE),
     lambda m: f"Galaxy Z {m[1].capitalize()}{m[2]}" + (f" {'Ultra' if m[3].lower() == 'ultra' else 'FE'}" if m[3] else "")),
    (re.compile(r"Galaxy\s*(S\d{2})\s*(Ultra|Edge|FE|\+|Plus)?(?![A-Za-z])", re.IGNORECASE),
     lambda m: f"Galaxy {m[1].upper()}" + ({"ultra": " Ultra", "edge": " Edge", "fe": " FE", "+": "+", "plus": "+"}
                                           [m[2].lower()] if m[2] else "")),
    (re.compile(r"Galaxy\s*(A\d{2})(?![A-Za-z\d])", re.IGNORECASE), lambda m: f"Galaxy {m[1].upper()}"),
    (re.compile(r"Xperia\s*(10|1|5)\s*(VIII|VII|VI|IV|V)(?![A-Za-z])", re.IGNORECASE),
     lambda m: f"Xperia {m[1]} {m[2].upper()}"),
    (re.compile(r"AQUOS\s*(R|sense|wish)\s*(\d+)\s*(pro)?(?![A-Za-z])", re.IGNORECASE),
     lambda m: f"AQUOS {m[1].upper() if m[1].lower() == 'r' else m[1].lower()}{m[2]}" + (" pro" if m[3] else "")),
]
# キャリア。キャリア名と、キャリアごとの型番（SC-53G は docomo、SCG37 は au など）で見分ける。
# キャリア版の名前に「SIMフリー」が書かれていることもあるので、SIMフリーは最後に調べる
CARRIERS = ["SIMフリー", "docomo", "au", "SoftBank", "楽天モバイル", "Y!mobile"]
_CARRIER_PATTERNS = [
    ("docomo", re.compile(r"docomo|ドコモ|\b(?:SC|SO|SH)-\d\d[A-Z]\b", re.IGNORECASE)),
    # UQ mobile 版は au 版と同じ機種（型番も同じ）なので、au 版として扱う
    ("au", re.compile(r"(?<![A-Za-z])au(?![A-Za-z])|UQ|\bS[COH]G\d\d\b", re.IGNORECASE)),
    ("SoftBank", re.compile(r"soft\s*bank|ソフトバンク", re.IGNORECASE)),
    ("Y!mobile", re.compile(r"y!?\s*mobile|ワイモバイル", re.IGNORECASE)),
    ("楽天モバイル", re.compile(r"楽天|rakuten|\bSM-\w+C\b|\bSH-RM\d+", re.IGNORECASE)),
    ("SIMフリー", re.compile(r"sim\s*フリー|sim\s*free|\bSM-\w+Q\b|\bXQ-\w+|\bSH-M\d\d", re.IGNORECASE)),
]
# 同じ容量でメモリ違いのモデルがある機種（容量のあとにメモリも付けて区別する）
_RAM_VARIANTS = {"Xperia 1 VIII 512GB", "Xperia 1 VII 512GB"}


def phone_key(name, carrier=None):
    """「【未開封】iPhone 17 Pro 256GB orange」→「iPhone 17 Pro 256GB」、
    「Google Pixel 10 Pro 256GB SIMフリー Jade」→「Pixel 10 Pro 256GB」、
    「Galaxy S26 Ultra SC-53G 12G+256G [ブラック]」→「Galaxy S26 Ultra 256GB docomo」。読み取れなければ None。"""
    text = unicodedata.normalize("NFKC", name or "")
    model = _MODEL.search(text)
    if not model:
        return _pixel_key(text) or android_key(text, carrier)
    capacity = _CAPACITY.search(text, model.end())
    if not capacity:
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
    return f"{label} {_capacity(capacity)}"


def _pixel_key(text):
    model = _PIXEL.search(text)
    capacity = _CAPACITY.search(text, model.end()) if model else None
    if not model or not capacity:
        return None
    generation, variant = model.groups()
    variant = re.sub(r"\s+", "", variant or "").lower()
    label = f"Pixel {generation}" + {"": "", "a": "a", "pro": " Pro", "proxl": " Pro XL", "profold": " Pro Fold"}[variant]
    return f"{label} {_capacity(capacity)}"


def android_key(name, carrier=None):
    """Galaxy・Xperia・AQUOS の「機種 容量 キャリア」。容量が書かれていなければ「機種 キャリア」
    （容量が1種類だけの機種は、scraper.update がその容量の商品に当てはめる）。扱っていない機種は None。"""
    text = unicodedata.normalize("NFKC", name or "")
    for pattern, label in _ANDROID:
        model = pattern.search(text)
        if model:
            break
    else:
        return None
    if label(model) not in COLORS:
        return None  # 扱っていない機種（古い機種など）
    carrier = carrier or next((c for c, pattern in _CARRIER_PATTERNS if pattern.search(text)), None)
    if carrier is None:
        return None
    storage, ram = _storage_and_ram(text)
    if storage is None:
        return f"{label(model)} {carrier}"
    capacity = f"{label(model)} {storage}"
    if capacity in _RAM_VARIANTS:
        if ram is None:
            return None
        capacity += f"({ram})"
    return f"{capacity} {carrier}"


def _storage_and_ram(text):
    """「12G+256G」「256GB(RAM 12GBモデル)」「1TB+16G」などから（容量, メモリ）。大きい方が容量。"""
    sizes = []
    for match in _CAPACITY.finditer(text):
        if match.group(1) == "5" and match.group(2).upper() == "G":
            continue  # 「Galaxy A25 5G」の 5G は通信方式
        before = text[match.start() - 1:match.start()]
        if before == "-" or (before.isascii() and before.isalpha()):
            continue  # 「SC-54G」「SCG37」のような型番の一部
        gb = int(match.group(1)) * (1024 if match.group(2).upper() == "TB" else 1)
        sizes.append((gb, _capacity(match)))
    storage = max((s for s in sizes if s[0] >= 32), default=None)
    ram = max((s for s in sizes if s[0] <= 24), default=None)
    return (storage[1] if storage else None), (ram[1] if ram else None)


def without_capacity(key):
    """「Galaxy A25 64GB docomo」→「Galaxy A25 docomo」（容量を書かない店舗の商品名と突き合わせるため）。"""
    return re.sub(r" \d+(GB|TB)(\(\d+GB\))?(?= |$)", "", key or "")


def _capacity(match):
    unit = match.group(2).upper()
    return f"{int(match.group(1))}{'GB' if unit == 'G' else unit}"


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
# Pixel の色は英語の名前が公式。カタカナで書く店舗もあるので読みも別名にする
_PIXEL_KANA = {
    "Obsidian": "オブシディアン", "Porcelain": "ポーセリン", "Hazel": "ヘーゼル", "Rose Quartz": "ローズクォーツ",
    "Peony": "ピオニー", "Wintergreen": "ウィンターグリーン", "Iris": "アイリス", "Frost": "フロスト",
    "Indigo": "インディゴ", "Lemongrass": "レモングラス", "Jade": "ジェード", "Moonstone": "ムーンストーン",
    "Lavender": "ラベンダー", "Berry": "ベリー", "Fog": "フォグ", "Isai Blue": "イサイブルー",
    "Hibiscus": "ハイビスカス", "Pistachio": "ピスタチオ", "Canyon": "キャニオン", "Olive": "オリーブ",
}


def _pixel(colors):
    return {color: [_PIXEL_KANA[color]] for color in colors}


_S26 = {"コバルトバイオレット": [], "ブラック": [], "スカイブルー": [], "ホワイト": [], "シルバーシャドウ": [],
        "ピンクゴールド": []}


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
    "Pixel 11": _pixel(["Obsidian", "Frost", "Hibiscus", "Pistachio"]),
    "Pixel 11 Pro": _pixel(["Obsidian", "Canyon", "Fog", "Olive"]),
    "Pixel 11 Pro XL": _pixel(["Obsidian", "Canyon", "Fog", "Olive"]),
    "Pixel 11 Pro Fold": _pixel(["Obsidian", "Olive"]),
    "Pixel 10": _pixel(["Obsidian", "Frost", "Indigo", "Lemongrass"]),
    "Pixel 10 Pro": _pixel(["Obsidian", "Porcelain", "Jade", "Moonstone"]),
    "Pixel 10 Pro XL": _pixel(["Obsidian", "Porcelain", "Jade", "Moonstone"]),
    "Pixel 10 Pro Fold": _pixel(["Jade", "Moonstone"]),
    "Pixel 10a": _pixel(["Obsidian", "Fog", "Lavender", "Berry", "Isai Blue"]),
    "Pixel 9": _pixel(["Obsidian", "Porcelain", "Peony", "Wintergreen"]),
    "Pixel 9 Pro": _pixel(["Obsidian", "Porcelain", "Hazel", "Rose Quartz"]),
    "Pixel 9a": _pixel(["Obsidian", "Porcelain", "Peony", "Iris"]),
    # Galaxy・Xperia・AQUOS（ここに載っている機種だけを扱う。キャリアごとの色の違いはカタログで決まる）
    "Galaxy S26 Ultra": _S26,
    "Galaxy S26+": _S26,
    "Galaxy S26": _S26,
    "Galaxy S25 Ultra": {"チタニウム シルバーブルー": ["シルバーブルー"], "チタニウム ブラック": ["ブラック"],
                         "チタニウム グレー": ["グレー"], "チタニウム ホワイトシルバー": ["ホワイトシルバー"],
                         "チタニウム ジェットブラック": ["ジェットブラック", "jetblack"],
                         "チタニウム ジェードグリーン": ["ジェードグリーン"], "チタニウム ピンクゴールド": ["ピンクゴールド"]},
    "Galaxy S25": {"アイシーブルー": [], "ネイビー": [], "シルバー シャドウ": [], "ミント": [],
                   "ブルーブラック": [], "コーラルレッド": [], "ピンクゴールド": []},
    "Galaxy Z Fold8 Ultra": {"バイオレットシャドウ": [], "グラファイト": [], "クリーム": [], "グリーンシャドウ": []},
    "Galaxy Z Fold8": {"ラベンダー": [], "グラファイト": [], "クリーム": [], "ピスタチオ": []},
    "Galaxy Z Flip8": {"ピンク": [], "グラファイト": [], "クリーム": [], "ミント": []},
    "Galaxy Z Fold7": {"ブルー シャドウ": [], "シルバー シャドウ": [], "ジェットブラック": ["jetblack"], "ミント": ["mint"]},
    "Galaxy Z Flip7": {"ブルー シャドウ": [], "ジェットブラック": ["jetblack"], "コーラルレッド": [], "ミント": ["mint"]},
    "Galaxy A57": {"オーサムネイビー": ["ネイビー"], "オーサムグレー": ["グレー"], "オーサムライラック": ["ライラック"],
                   "オーサムアイシーブルー": ["アイシーブルー"]},
    "Galaxy A36": {"オーサム ラベンダー": ["ラベンダー"], "オーサム ブラック": ["ブラック"], "オーサム ホワイト": ["ホワイト"],
                   "オーサム ライム": ["ライム"]},
    "Galaxy A25": {"ブルー": [], "ブラック": [], "ライト ブルー": []},
    "Xperia 1 VIII": {"グラファイトブラック": [], "アイオライトシルバー": [], "ガーネットレッド": [], "ネイティブゴールド": []},
    "Xperia 1 VII": {"スレートブラック": ["ブラック"], "オーキッドパープル": ["パープル"], "モスグリーン": ["グリーン"]},
    "Xperia 10 VII": {"チャコールブラック": ["ブラック", "black"], "ホワイト": ["white"], "ターコイズ": ["turquoise"]},
    "Xperia 10 VI": {"ブラック": [], "ホワイト": [], "ブルー": []},
    "AQUOS R11": {"ネイビー": [], "アイボリー": [], "テラコッタ": []},
    "AQUOS R10": {"チャコールブラック": ["ブラック"], "カシミヤホワイト": ["ホワイト"], "トレンチベージュ": ["ベージュ"]},
    "AQUOS sense10": {"デニムネイビー": ["ネイビー", "ネービー"], "カーキグリーン": ["カーキーグリーン", "グリーン"],
                      "ペールピンク": ["ピンク"], "ペールミント": ["ミント"], "フルブラック": ["ブラック"],
                      "ライトシルバー": ["シルバー"]},
    "AQUOS sense9": {"ブラック": [], "ホワイト": [], "グリーン": [], "ブルー": [], "コーラル": [], "グレージュ": []},
    "AQUOS wish6": {"ソラ": ["sora"], "キヌ": ["kinu"], "スミ": ["sumi"]},
    "AQUOS wish5": {"ミソラ": ["misora"], "ナデシコ": ["nadeshiko"], "ワカバ": ["wakaba"], "ユキ": ["yuki"],
                    "スミ": ["sumi"]},
}


def phone_colors(key):
    """「iPhone 17 Pro 256GB」の色の一覧（公式の日本語名）。わからない機種は空。"""
    return list(COLORS.get(_model(key), {}))


def phone_color(key, text):
    """商品名の容量より後ろの部分などから色を読み取り、公式の日本語名にする。読み取れなければ None。"""
    # 「ライト ブルー」「ライトブルー」のような空白の違いは区別しない
    text = re.sub(r"\s+", "", unicodedata.normalize("NFKC", text or "")).lower()
    names = [(re.sub(r"\s+", "", alias).lower(), color) for color, aliases in COLORS.get(_model(key), {}).items()
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
    """キーから機種名だけを取り出す（「Galaxy S26 Ultra 256GB docomo」→「Galaxy S26 Ultra」）。"""
    key = key or ""
    for carrier in CARRIERS:
        if key.endswith(" " + carrier):
            key = key[:-len(carrier) - 1]
            break
    return re.sub(r"\s+\d+(GB|TB)(\(\d+GB\))?$", "", key)


def one_color(key, name, price):
    """色ごとに別の商品として載っている店舗用。{色: 価格}（色が読み取れなければ空）。"""
    # ふつうは容量の後ろに色が書かれているが、「Pixel 9 Obsidian 128GB」のように前に書く店舗もある
    color = phone_color(key, color_part(name)) or phone_color(key, name)
    return {color: price} if color else {}
