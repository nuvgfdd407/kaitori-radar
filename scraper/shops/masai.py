"""トレカマサイ。

トレカの店頭・郵送買取の店。買取価格表（/products）に全カテゴリの商品がサーバー側で組み立てた HTML で1ページに載っているので、
そのページだけを読む。商品ごとに「カテゴリ・商品名・買取価格」の枠があり、状態で価格が違う商品は枠の中の選択肢に
「シュリンク付き ￥7,700」「シュリンク無し ￥6,800」「ペリペリ無し」「統一パック」（ワンピース・ドラゴンボールは
「テープ付き」「テープカット」）の価格が並ぶ。使うのは「シュリンク付き」「テープ付き」の価格だけで、選択肢にそれがない商品
（「メガシンフォニア＆メガブレイブ」セットのペリペリ無し・統一パックだけの行など）は使わない。
選択肢のない商品は状態が1つだけで、商品ページではポケカの BOX が「シュリンク付き」、ワンピース・ドラゴンボールが
「テープ付き」、サプライが「通常」になっている（2026-11 時点）ので、その価格を使う。
JAN は商品ページにしか載っていないので、セット名（scraper.cards.card_key）でカタログの "names" と突き合わせる。
- ポケモンカード: 「『ストームエメラルダ』(M6)」のように『』の中がセット名
- ワンピースカード・ドラゴンボール: 「決戦の刻【OP16】」「BRIGHTNESS OF HOPE [FB11]」のように弾の記号が後ろに付く。
  カタログの名前は「OP-16 決戦の刻」の形なので、記号を名前の前に付ける
- サプライ（ポケカ・ワンピース）: 名前をそのまま使う（「30th CELEBRATION FUTURISTIC BOX」など）
サプライのカテゴリに混ざるシングルカードの行（「RR シングル最低保証」「おいわいファンファーレ(2026)【P】{147/M-P}」）と、
「⚠️111g以上」「⚠️ポケセン段ボール未開封のみ」のように条件付きの価格の行は使わない。
UNION ARENA・その他（ヴァイスシュヴァルツ）はカタログにないので使わない。
価格表の上の「2026/11/18 13:50 現在」（価格の更新日時）が30日以上前なら使わない。
"""
import re
from datetime import date, timedelta
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from ..cards import card_key
from ..text import parse_yen

ID = "masai"
NAME = "トレカマサイ"
SHORT = "マサイ"
URL = "https://www.masai-tcg.com/"

LIST_URL = URL + "products"
MAX_AGE = timedelta(days=30)
GAMES = ("ポケモンカード", "ワンピースカード", "ドラゴンボール")  # 「ポケモンカード サプライ」なども含む
STATES = ("シュリンク付き", "テープ付き")
_UPDATED = re.compile(r"(\d{4})/(\d{1,2})/(\d{1,2})\s+\d{1,2}:\d{2}\s*現在")
_TITLE = re.compile(r"『(.+?)』")
_CODE = re.compile(r"\s*[【\[]([A-Z]+-?\d+)[】\]]")
_SKIP = re.compile(r"⚠|シングル|\{\d+/")  # 条件付きの価格・シングルカード


def fetch(http):
    soup = BeautifulSoup(http.get(LIST_URL).content, "html.parser")
    updated = _UPDATED.search(soup.select_one("main h1").find_next("p").get_text())
    if date.today() - date(*map(int, updated.groups())) >= MAX_AGE:
        return []
    offers = []
    for li in soup.select("li"):
        link = li.select_one("a[href^='/products/']")
        if not link or not link.h3:
            continue
        category = link.p.get_text(strip=True)
        if not category.startswith(GAMES):
            continue
        name = link.h3.get_text(" ", strip=True)
        if _SKIP.search(name):
            continue
        price = _price(li, link)
        if price:
            offers.append({"jan": None, "key": _key(category, name), "name": name, "price": price,
                           "url": urljoin(URL, link["href"])})
    return offers


def _price(li, link):
    """選択肢があれば「シュリンク付き」「テープ付き」の価格（なければ None）、なければ枠の買取価格。"""
    options = li.select("select option")
    if not options:
        return parse_yen(link.select("p")[-1].get_text())
    for option in options:
        state, _, yen = option.get_text(" ", strip=True).partition("￥")
        if state.strip() in STATES:
            return parse_yen(yen)
    return None


def _key(category, name):
    """カタログの "names" と比べる文字列。ポケカの BOX は『』の中、ワンピース・ドラゴンボールは「OP16 決戦の刻」の形にする。"""
    if category == "ポケモンカード":
        title = _TITLE.search(name)
        return card_key(title.group(1) if title else name)
    code = _CODE.search(name)
    return card_key(f"{code.group(1)} {_CODE.sub('', name)}" if code else name)
