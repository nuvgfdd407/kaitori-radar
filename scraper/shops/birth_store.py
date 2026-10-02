"""トレカバースの店頭買取の価格（PSA 鑑定品だけ）。

郵送買取（birth）と同じ買取表の CSV の「店頭価格」の列を使う。
"""
from . import birth

ID = "birth_store"
NAME = birth.NAME
SHORT = birth.SHORT
MODE = "店頭"
URL = birth.URL


def fetch(http):
    return fetch_psa(http)


def fetch_psa(http):
    """PSA 鑑定品の出品（scraper.psa_catalog でも使う）。"""
    return birth.fetch_psa(http, column="店頭価格")
