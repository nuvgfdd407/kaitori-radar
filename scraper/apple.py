"""iPad・Apple Watch・AirPods の出品を、JAN と Apple の型番で突き合わせるための小さな関数。

Apple の製品は、色・容量・通信方式（Wi-Fi / Cellular）・バンドの組み合わせごとに型番（「MDWK4J/A」など）と
JAN が決まっている。店舗は JAN か型番のどちらか（または両方）を商品名に書いていることが多いので、
出品には JAN と {型番: 価格} を付け、カタログの "aliases" に書いた JAN・型番で突き合わせる（scraper.update）。
型番も JAN も書かない店舗の iPad は、名前（機種・世代かチップ・大きさ・容量・Wi-Fi か Cellular か）と色で
カタログの iPad を探し、その JAN を "codes" にする（ipad_offer）。
"""
import functools
import re
import unicodedata

# 「MDWK4J/A」「MJEU4X/A」「MHWN4ZA/A」など
_CODE = re.compile(r"(?<![A-Z0-9])([A-Z0-9]{5}(?:J|X|ZA|ZP|LL|CH)/A)(?![A-Z0-9])")
_JAN = re.compile(r"(?<!\d)(4549995\d{6})(?!\d)")


def apple_codes(text):
    """文字列に含まれる Apple の型番の一覧（重複なし、出てきた順）。"""
    return list(dict.fromkeys(_CODE.findall(unicodedata.normalize("NFKC", text or "").upper())))


def apple_jans(text):
    """文字列に含まれる Apple の JAN（4549995 で始まる13桁）の一覧。"""
    return list(dict.fromkeys(_JAN.findall(text or "")))


def apple_offer(name, price, url, jan=None, text=""):
    """出品の辞書。name と text（備考など）に書かれた型番・JAN は、どれも同じ価格の商品として扱う。"""
    codes = apple_codes(f"{name} {text}") + [j for j in apple_jans(f"{name} {text}") if j != jan]
    return {"jan": jan, "codes": dict.fromkeys(codes, price), "name": name, "price": price, "url": url}


# ---- 型番も JAN も書かない店舗の iPad（名前で突き合わせる） ----
# 店舗は「iPad Air 13インチ 第8世代」「iPad Pro 11インチ M5」「13iPad Air8 M4【1TB】」「iPad mini8」のように、
# 世代かチップ（両方あればチップを優先。「iPad Pro 13インチ M5 第2世代」のように13インチの Pro を M4 から数える店舗がある）と
# 画面の大きさで機種を書く。カタログの名前（「iPad Pro 11インチ（M5）256GB Wi-Fi + Cellular シルバー」）も同じ関数で読み、
#（機種, 大きさ, カタログの（）の中, 容量, Cellular か, Nano-texture か）が同じ商品の全色を候補にする。
# (機種, 画面の大きさ) → {世代の番号・チップ: カタログの（）の中}
_IPAD_MODELS = {
    ("iPad", None): {"9": "第9世代", "A13": "第9世代", "10": "第10世代", "A14": "第10世代", "11": "A16", "A16": "A16"},
    ("iPad mini", None): {"6": "第6世代", "A15": "第6世代", "7": "A17 Pro", "A17": "A17 Pro", "8": "A20", "A20": "A20"},
    ("iPad Air", None): {"5": "第5世代", "M1": "第5世代"},
    ("iPad Air", "11"): {"6": "M2", "M2": "M2", "7": "M3", "M3": "M3", "8": "M4", "M4": "M4"},
    ("iPad Air", "13"): {"6": "M2", "M2": "M2", "7": "M3", "M3": "M3", "8": "M4", "M4": "M4"},
    ("iPad Pro", "11"): {"3": "第3世代", "M1": "第3世代", "4": "第4世代", "M2": "第4世代", "5": "M4", "M4": "M4",
                         "6": "M5", "M5": "M5"},
    ("iPad Pro", "12.9"): {"5": "第5世代", "M1": "第5世代", "6": "第6世代", "M2": "第6世代"},
    ("iPad Pro", "13"): {"1": "M4", "7": "M4", "M4": "M4", "2": "M5", "8": "M5", "M5": "M5"},
}
# 画面の大きさの書き方 → 表の大きさ（Air の 10.9インチは第5世代）
_IPAD_SIZES = {"iPad Air": {"10.9": None, "11": "11", "13": "13"}, "iPad Pro": {"11": "11", "12.9": "12.9", "13": "13"}}
# 店舗の色の書き方（英語・漢字1文字など）→ カタログの色名
_IPAD_COLORS = {"スペースグレイ": ["スペースグレー", "spacegray", "spacegrey", "グレー", "グレイ", "灰"],
                "シルバー": ["silver", "銀"], "スターライト": ["starlight"], "スペースブラック": ["spaceblack", "ブラック", "黒"],
                "パープル": ["purple", "紫"], "ブルー": ["blue", "青"], "ピンク": ["pink", "桃"], "イエロー": ["yellow", "黄"],
                "ミッドナイト": ["midnight", "黒"]}
_IPAD_LINE = re.compile(r"iPad\s*(Pro|Air|mini)?", re.IGNORECASE)
_IPAD_CHIP = re.compile(r"(?<![A-Za-z0-9])(M[1-9]|A1[3-9]|A2\d)(?![0-9])")
_IPAD_GEN = re.compile(r"第\s*(\d{1,2})\s*世代")
# 「iPad mini8」「Air8」「iPad11」（大きさの「11インチ」は除く）
_IPAD_GEN_SHORT = re.compile(r"(?:mini|Air|iPad)\s*(\d{1,2})(?![\d.]|\s*(?:インチ|inch|型))", re.IGNORECASE)
_IPAD_SIZE = re.compile(r"(\d{1,2}(?:\.\d)?)\s*(?:インチ|inch|型)", re.IGNORECASE)
_IPAD_SIZE_LEAD = re.compile(r"(?<![\d.])(1[13]|12\.9)\s*iPad", re.IGNORECASE)  # 「13iPad Pro」「11 iPad Pro」
_IPAD_CAPACITY = re.compile(r"(\d+)\s*(GB|TB)", re.IGNORECASE)
_IPAD_OTHER = re.compile(r"Pencil|Keyboard|キーボード|ケース|カバー|フォリオ|用")
_IPAD_NANO = re.compile(r"Nano-texture(?:ガラス)?\s*", re.IGNORECASE)


def ipad_key(name, cellular=None):
    """iPad の名前から（機種, 大きさ, カタログの（）の中, 容量, Cellular か, Nano-texture か）。読み取れなければ None。
    cellular を渡さなければ、名前に「Cellular」があるかで決める。"""
    text = unicodedata.normalize("NFKC", name or "")
    line = _IPAD_LINE.search(text)
    capacity = _IPAD_CAPACITY.search(text)
    if not line or not capacity or _IPAD_OTHER.search(text):
        return None
    line = "iPad" + (" " + {"pro": "Pro", "air": "Air", "mini": "mini"}[line[1].lower()] if line[1] else "")
    size = _IPAD_SIZE.search(text) or _IPAD_SIZE_LEAD.search(text)
    # 大きさがない Air は第5世代だけ、表にない大きさ（10.5インチの Pro など）は "?"（どれにも合わない）
    size = _IPAD_SIZES[line].get(size[1], "?") if line in _IPAD_SIZES and size else None
    models = _IPAD_MODELS.get((line, size), {})
    words = [m[1] for m in (_IPAD_CHIP.search(text), _IPAD_GEN.search(text), _IPAD_GEN_SHORT.search(text)) if m]
    label = next((models[w] for w in words if w in models), None)
    if not label:
        return None
    if cellular is None:
        cellular = bool(re.search(r"Cellular|セルラー", text, re.IGNORECASE))
    return line, size, label, capacity[1] + capacity[2].upper(), cellular, "nano" in text.lower()


@functools.cache
def _catalog_ipads():
    """カタログの {ipad_key: {色: JAN}}。"""
    from .common import CATALOG, load_json
    ipads = {}
    for p in load_json(CATALOG)["products"]:
        key = ipad_key(p["name"]) if p["name"].startswith("iPad") else None
        if key:
            color = _IPAD_NANO.sub("", re.split(r"Wi-Fi(?: \+ Cellular)? ", p["name"])[-1]).strip()
            ipads.setdefault(key, {})[color] = p["jan"]
    return ipads


def ipad_colors(name, cellular=None):
    """名前に合うカタログの iPad の {色: JAN}（合うものがなければ空）。"""
    key = ipad_key(name, cellular)
    return dict(_catalog_ipads().get(key, {})) if key else {}


def ipad_color(colors, word):
    """店舗の色の書き方（「灰」「Space Gray」「スペースグレー」など）を、colors（カタログの色名）の1つにする。"""
    word = re.sub(r"\s+", "", unicodedata.normalize("NFKC", word or "")).lower()
    found = {c for c in colors for alias in [c, *_IPAD_COLORS.get(c, [])] if alias.lower() == word}
    found = found or {c for c in colors for alias in [c, *_IPAD_COLORS.get(c, [])] if len(alias) > 1 and alias.lower() in word}
    return found.pop() if len(found) == 1 else None


def ipad_offer(name, price, url, cellular=None, colors=None):
    """型番も JAN もない iPad の出品（カタログの JAN を "codes" にする）。price は全色の価格、colors は
    {色の書き方: 価格}（その色だけ別の価格。price が None なら colors の色だけ）。合う iPad がない・色が読めなければ None。"""
    found = ipad_colors(name, cellular)
    if not found:
        return None
    prices = dict.fromkeys(found, price) if price else {}
    for word, p in (colors or {}).items():
        color = ipad_color(found, word)
        if not color:
            return None
        prices[color] = p
    codes = {found[c]: p for c, p in prices.items() if p}
    if not codes:
        return None
    return {"jan": None, "codes": codes, "name": name, "price": max(codes.values()), "url": url}
