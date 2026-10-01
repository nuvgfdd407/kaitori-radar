"""海峡通信（モバイル一番）。

カテゴリページは1ページ20件。2ページ目以降は、ページ内の検索フォームの値を付けて
POST で取得する（画面上のページ送りと同じ）。商品ごとのページはない（カートに入れる方式）。
商品カードの「新品」の価格を使う。表示価格は郵送の価格で、「来店+200」は来店時の加算。
備考に「JAN:xxxx同額」とあるときは、そのJANの商品も同じ価格で買い取るという意味なので、
そのJANにも同じ価格を当てはめる。
iPhone はJANがなく、「iPhone 17 Pro 256GB」「simfree未開封」のように機種＋容量と状態で載っている。
色による減額は備考に「シルバー -32000 / グレイシャー、ブラック -8000」のように書かれていて、
表示価格はいちばん高い色の価格（備考に出てこない色は表示価格のまま）。
ポケモンカード・遊戯王はおもちゃ買取（3）> ポケモン トレーディングカード（04）・遊戯王トレーディングカード（07）にあり、
JAN が載っている。
"""
import re
import unicodedata

from bs4 import BeautifulSoup

from ..iphone import iphone_color, iphone_colors, iphone_key
from ..text import find_jan, parse_yen

ID = "kaikyo"
NAME = "海峡通信"
SHORT = "海峡"
URL = "https://www.mobile-ichiban.com/"

BASE = "https://www.mobile-ichiban.com"
# 家電買取（2）> ゲーム（01）> Nintendo Switch 2 / Nintendo Switch / PlayStation / Xbox Series /
# Meta Quest / Steam Deck / ASUS
CATEGORIES = ["11", "01", "02", "03", "04", "07", "09"]
# 携帯買取（1）> iPhone（01）> 18 Pro Max / 18 Pro / 17 Pro Max / 17 Pro / Air / 17 / 17e /
# 16 Pro Max / 16 Pro / 16 / 16e / 16 Plus
IPHONE_CATEGORIES = ["40", "39", "37", "36", "35", "34", "38", "32", "31", "30", "33", "29"]
# おもちゃ買取（3）> ポケモン トレーディングカード / 遊戯王トレーディングカード
CARD_CATEGORIES = ["04", "07"]


def fetch(http):
    offers = []
    aliases = []
    for mid in CATEGORIES:
        for card, name, price, url in _read_category(http, "2", "01", mid):
            jan = find_jan(_text(card.select_one("small.text-muted")))
            if not jan:
                continue
            offer = {"jan": jan, "name": name, "price": price, "url": url}
            offers.append(offer)
            for alias in re.findall(r"JAN:\s*(\d{13})\s*同額", _text(card.select_one("small.my-prod-remarks"))):
                aliases.append({**offer, "jan": alias})
    for mid in IPHONE_CATEGORIES:
        for card, name, price, url in _read_category(http, "1", "01", mid):
            # 状態は「simfree未開封」「simfree開封」のように書かれている
            if "未開封" in name:
                key = iphone_key(name)
                labels = [t.get_text(" ", strip=True) for t in card.select('label[data-toggle="tooltip"]')]
                remark = labels[2] if len(labels) > 2 else ""
                offers.append({"jan": None, "key": key, "name": name, "price": price, "url": url,
                               "colors": _color_prices(key, price, remark)})
    for bid in CARD_CATEGORIES:
        for card, name, price, url in _read_category(http, "3", bid):
            # 状態は3つ目の表示に「シュリンク付き、新品未開封」のように書かれている
            labels = [t.get_text(" ", strip=True) for t in card.select('label[data-toggle="tooltip"]')]
            jan = find_jan(_text(card.select_one("small.text-muted")))
            if jan and any("未開封" in label for label in labels[1:3]):
                offers.append({"jan": jan, "name": name, "price": price, "url": url})
    # 「同額」で当てはめた価格は、そのJANの直接の出品があればそちらを優先したいので後ろに置く
    return offers + aliases


def _color_prices(key, price, remark):
    """備考の色ごとの減額から {色: 価格} を作る。"""
    colors = dict.fromkeys(iphone_colors(key), price)
    pending = []
    for token in re.findall(r"[-−]\s*\d+|[^\s/、,・\-−\d]+", unicodedata.normalize("NFKC", remark)):
        if token[0] in "-−":
            for color in pending:
                colors[color] = price - int(token[1:].strip())
            pending = []
        elif color := iphone_color(key, token):
            pending.append(color)
    return colors


def _read_category(http, kid, bid, mid=None):
    """カテゴリの全ページの（商品カード, 商品名, 新品の価格, ページのURL）を順に返す。"""
    page_url = f"{BASE}/Prod/{kid}/{bid}" + (f"/{mid}" if mid else "")
    soup = BeautifulSoup(http.get(page_url).content, "html.parser")
    yield from _read_cards(soup, page_url)

    form = soup.select_one("#G01_ProdutShow_searchForm")
    pager = soup.select_one("ul.pagination[data-pagecount]")
    if form is None or pager is None:
        return
    data = {i["name"]: i.get("value", "") for i in form.select("input[name]")}
    for page in range(2, int(pager["data-pagecount"]) + 1):
        res = http.post(
            f"{BASE}/G01_ProdutShow/Index/{page}",
            params={"kid": kid, "bid": bid, **({"mid": mid} if mid else {})},
            data=data,
            headers={"X-Requested-With": "XMLHttpRequest", "Referer": page_url},
        )
        yield from _read_cards(BeautifulSoup(res.content, "html.parser"), page_url)


def _read_cards(soup, page_url):
    for label in soup.select('label[id^="NewPrice_"]'):
        card = label.find_parent("div", class_="card")
        price = parse_yen(label.get_text())
        if card is None or not price:
            continue
        names = [t.get_text(" ", strip=True) for t in card.select('label[data-toggle="tooltip"]')[:2]]
        yield card, " ".join(n for n in names if n), price, page_url


def _text(tag):
    return tag.get_text(" ", strip=True) if tag else ""
