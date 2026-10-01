"""トレカ（ポケモンカード・ワンピースカード）の商品名を、店舗をまたいで比べられる形にする。

トレカは JAN を載せていない店舗がある（買取ホムラ、買取当番の一部）。そういう店舗の商品は、
「【BOX】ストームエメラルダ」「郵送専用【M6a】 30th CELEBRATION」のような名前から
セット名の部分（「ストームエメラルダ」）を取り出して、カタログの "names" と突き合わせる。
"""
import re
import unicodedata

# 名前の前後に付く、セット名ではない部分
_TAGS = re.compile(r"【[^】]*】|\[[^\]]*\]|郵送専用|来店専用|未開封|BOX", re.IGNORECASE)
_SYMBOLS = re.compile(r"[\s・「」『』\-－‐ー―~〜!！?？]")


def card_key(name):
    """「【BOX】ストームエメラルダ」→「ストームエメラルダ」のような比較用の文字列。空なら None。"""
    text = unicodedata.normalize("NFKC", name or "")
    text = _TAGS.sub(" ", text)
    text = _SYMBOLS.sub("", text).lower()
    return text or None
