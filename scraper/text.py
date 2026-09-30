"""ページの文字列から価格やJANコードを取り出す小さな関数。"""
import re

_JAN = re.compile(r"(?<!\d)(\d{13}|\d{8})(?!\d)")


def parse_yen(text):
    """「82,600円」「¥ 54,000」などを整数にする。数字がなければ None。"""
    digits = re.sub(r"\D", "", text or "")
    return int(digits) if digits else None


def find_jan(text):
    """文字列に含まれる最初のJANコード（13桁または8桁）を返す。"""
    m = _JAN.search(text or "")
    return m.group(1) if m else None
