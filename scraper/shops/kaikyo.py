"""海峡通信（モバイル一番）。

カテゴリページは1ページ20件。2ページ目以降は、ページ内の検索フォームの値を付けて
POST で取得する（画面上のページ送りと同じ）。商品ごとのページはない（カートに入れる方式）。
商品カードの「新品」の価格を使う。表示価格は郵送の価格で、「来店+200」は来店時の加算。
備考に「JAN:xxxx同額」とあるときは、そのJANの商品も同じ価格で買い取るという意味なので、
そのJANにも同じ価格を当てはめる。
"""
import re

from bs4 import BeautifulSoup

from ..text import find_jan, parse_yen

ID = "kaikyo"
NAME = "海峡通信"
SHORT = "海峡"
URL = "https://www.mobile-ichiban.com/"

BASE = "https://www.mobile-ichiban.com"
# 家電買取（2）> ゲーム（01）> Nintendo Switch 2 / Nintendo Switch / PlayStation / Xbox Series /
# Meta Quest / Steam Deck / ASUS
CATEGORIES = ["11", "01", "02", "03", "04", "07", "09"]


def fetch(http):
    offers = []
    aliases = []
    for mid in CATEGORIES:
        page_url = f"{BASE}/Prod/2/01/{mid}"
        soup = BeautifulSoup(http.get(page_url).content, "html.parser")
        _read_cards(soup, page_url, offers, aliases)

        form = soup.select_one("#G01_ProdutShow_searchForm")
        pager = soup.select_one("ul.pagination[data-pagecount]")
        if form is None or pager is None:
            continue
        data = {i["name"]: i.get("value", "") for i in form.select("input[name]")}
        for page in range(2, int(pager["data-pagecount"]) + 1):
            res = http.post(
                f"{BASE}/G01_ProdutShow/Index/{page}",
                params={"kid": "2", "bid": "01", "mid": mid},
                data=data,
                headers={"X-Requested-With": "XMLHttpRequest", "Referer": page_url},
            )
            _read_cards(BeautifulSoup(res.content, "html.parser"), page_url, offers, aliases)
    # 「同額」で当てはめた価格は、そのJANの直接の出品があればそちらを優先したいので後ろに置く
    return offers + aliases


def _read_cards(soup, page_url, offers, aliases):
    for label in soup.select('label[id^="NewPrice_"]'):
        card = label.find_parent("div", class_="card")
        price = parse_yen(label.get_text())
        if card is None or not price:
            continue
        jan = find_jan(_text(card.select_one("small.text-muted")))
        if not jan:
            continue
        names = [t.get_text(" ", strip=True) for t in card.select('label[data-toggle="tooltip"]')[:2]]
        offer = {"jan": jan, "name": " ".join(n for n in names if n), "price": price, "url": page_url}
        offers.append(offer)
        for alias in re.findall(r"JAN:\s*(\d{13})\s*同額", _text(card.select_one("small.my-prod-remarks"))):
            aliases.append({**offer, "jan": alias})


def _text(tag):
    return tag.get_text(" ", strip=True) if tag else ""
