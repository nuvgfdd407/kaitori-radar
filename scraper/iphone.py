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
