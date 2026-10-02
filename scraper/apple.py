"""iPad・Apple Watch・AirPods の出品を、JAN と Apple の型番で突き合わせるための小さな関数。

Apple の製品は、色・容量・通信方式（Wi-Fi / Cellular）・バンドの組み合わせごとに型番（「MDWK4J/A」など）と
JAN が決まっている。店舗は JAN か型番のどちらか（または両方）を商品名に書いていることが多いので、
出品には JAN と {型番: 価格} を付け、カタログの "aliases" に書いた JAN・型番で突き合わせる（scraper.update）。
"""
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
