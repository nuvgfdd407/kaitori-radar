"""買取北斎（株式会社Ｎ＆Ｕ）。

トレカの郵送買取の店。トップページの買取表（#public-pricelist）に、未開封 BOX の価格がサーバー側で組み立てた HTML で
載っているので、トップページだけを読む。「ポケモンカード」「ワンピースカード」「シングルカード」「その他」の見出しごとに
表があり、1つのマスに「変幻の仮面 [SV6] 11,700円」のように商品名・弾の記号・価格が入っている。
JAN は載っていないので、セット名（scraper.cards.card_key）でカタログの "names" と突き合わせる。
買取表の上の「(2026/11/18 更新)」が30日以上前なら使わない。
- ポケモンカード: 「ブラックボルト (通常)」「ブラックボルト (DX)」は「ブラックボルト」「ブラックボルトDX」にする
- ワンピースカード: カタログの名前は「OP-16 決戦の刻」の形なので、弾の記号（[OP-16]）を名前の前に付ける
- その他: スペシャルBOX・セット品・遊戯王の BOX など。「段ボール開封済み」の行は使わない
- シングルカード（PSA10 の一括価格とレアリティごとの価格）は使わない
新しい弾の一部は「18,500円 / 16,000円」のように価格が2つ並んでいる。左がシュリンク付き、右がシュリンク無しの価格なので
（サイトに説明はないが、右の値がトレカマサイの「シュリンク無し」と一致する。2026-11 時点）、左（先に書かれた方）を使う。
"""
import re
from datetime import date, timedelta

from bs4 import BeautifulSoup

from ..cards import card_key
from ..text import parse_yen

ID = "hokusai"
NAME = "買取北斎"
SHORT = "北斎"
URL = "https://www.kaitori-hokusai.com/"

LIST_URL = URL + "#public-pricelist"
MAX_AGE = timedelta(days=30)
SECTIONS = ("ポケモンカード", "ワンピースカード", "その他")
_UPDATED = re.compile(r"(\d{4})/(\d{1,2})/(\d{1,2})\s*更新")
_KIND = re.compile(r"\s*[(（](通常|DX)[)）]")
_YEN = re.compile(r"[\d,]+円")


def fetch(http):
    soup = BeautifulSoup(http.get(URL).content, "html.parser")
    pricelist = soup.select_one("#public-pricelist")
    updated = _UPDATED.search(pricelist.select_one(".date-display").get_text())
    if date.today() - date(*map(int, updated.groups())) >= MAX_AGE:
        return []
    offers = []
    for title in pricelist.select("h4.pricelist-category-title"):
        section = title.get_text(strip=True)
        if section not in SECTIONS:
            continue
        for cell in title.find_next_sibling("table").select("td.item-cell"):
            name = cell.select_one(".name-main").get_text(" ", strip=True)
            suffix = cell.select_one(".name-suffix")
            code = suffix.get_text(strip=True).strip("[]") if suffix else ""  # 弾の記号（「OP-16」など）
            prices = [p for p in map(parse_yen, _YEN.findall(cell.select_one(".price").get_text())) if p]
            if "開封済" in name or not prices:
                continue
            if section == "ポケモンカード":
                key = card_key(_KIND.sub(lambda m: "DX" if m.group(1) == "DX" else "", name))
            elif section == "ワンピースカード":
                key = card_key(f"{code} {name}")
            else:
                key = card_key(name)
            offers.append({"jan": None, "key": key, "name": f"{name} [{code}]" if code else name,
                           "price": prices[0], "url": LIST_URL})
    return offers
