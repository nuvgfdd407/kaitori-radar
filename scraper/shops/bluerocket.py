"""BlueRocket（トレカの郵送買取。運営は買取ホムラと同じ株式会社SIG）。

一覧（/products?q[product_sub_category_id_eq]=<サブカテゴリ>&q[product_sub_category_product_category_id_eq]=<カテゴリ>）は
1ページ20件で、続きは &page=N（「次のページ」のリンク a[rel=next] がなくなるまで）。
商品ごとの「追加」ボタンに data-product-name・data-product-price があり、商品名の下に店の商品コードが載っている。
コードは「11＋JAN」（シュリンク有りのBOX・ワンピースのBOX）、「12＋JAN」（シュリンク無し）、「22＋JAN」（カートン）のような
15桁で、スペシャルセットは JAN そのもの（13桁）。下13桁を JAN として使う。
JAN がカタログと違う商品（VMAXクライマックスなど）もあるので、「【BOX】ストームエメラルダ」のセット名（card_key）も付ける。
ポケモンカードのBOXはシュリンク有り・無しで別の価格があり、シュリンク有り（1）だけを使う。
シュリンク無し（2）・カートン（4・6）・バラパック（12）・シングルカード（7）は使わない。
商品名の「※」の後ろは条件（「※輸送箱未開封」）なので、"note" にする。
PSA 鑑定品（カテゴリ2 > 13）はポケモンカードの PSA10 だけで、「PSA10 ブラッキーVMAX SA 095/069」のほか、ホムラと同じ
「PSA10 ヒカリ SAR [M2 115/080](拡張パック「インフェルノX」)」の形もある（_psa_name でそろえる）。画像はカード単体の画像。
商品には「郵送のみ」の印が付いていて（サイトの価格は郵送買取の価格。秋葉原店・福岡店の持込は別）、そのときは mode を「郵送」にする。
価格の更新日の表示はない。
"""
import re
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from ..cards import card_key
from ..psa import parse_name, psa_key

ID = "bluerocket"
NAME = "BlueRocket"
SHORT = "BlueRocket"
URL = "https://bluerocket-tcg.com/"

LIST_URL = URL + "products"
# トレカ（1）> ポケモンカード シュリンク有り / スペシャルセット / ワンピース 未開封BOX
BOX_SUBS = [(1, 1), (1, 3), (1, 5)]
# PSA（2）> PSA
PSA_SUB = (2, 13)
MAX_PAGES = 30


def fetch(http):
    offers = fetch_psa(http)
    for category, sub in BOX_SUBS:
        for name, code, price, url, mode, _ in _read_list(http, category, sub):
            note = name.partition("※")[2].strip()  # 「※輸送箱未開封」のような条件
            offers.append({"jan": _jan(code), "key": card_key(name), "name": name, "price": price, "url": url,
                           **({"note": note} if note else {}), **({"mode": mode} if mode else {})})
    return offers


def fetch_psa(http):
    """PSA 鑑定品の出品（scraper.psa_catalog でも使う）。"""
    offers = []
    for name, _, price, url, mode, image in _read_list(http, *PSA_SUB):
        parsed = parse_name(_psa_name(name))
        key = psa_key("pokemon", parsed[0], parsed[1], parsed[3]) if parsed else None
        if key:
            offers.append({"jan": None, "key": key, "name": name, "price": price, "url": url,
                           **({"mode": mode} if mode else {}),
                           "psa": {"game": "pokemon", "grade": parsed[0], "name": parsed[1], "rarity": parsed[2],
                                   "number": parsed[3], "image": image, "page": url}})
    return offers


def _psa_name(name):
    """「PSA10 ヒカリ SAR [M2 115/080](拡張パック「インフェルノX」)」→「PSA10 ヒカリ SAR 115/080」。"""
    name = re.sub(r"\([^()]*(?:「|パック|ポケモンカード)[^()]*\)", " ", name)  # 収録パック名
    name = re.sub(r"\s*\[(?:[A-Za-z0-9\-]+ )?([^\]]*/[^\]]*)\]", r" \1", name)  # [M2 115/080]・[XY-BEST 180/171] のパックの記号
    name = re.sub(r"(?<![A-Za-z])[A-Z]{1,3}\s*:\s*|\s*:\s*", " ", name)  # 「HR: SA」
    name = name.replace("/SV/P", "/SV-P")  # 「288/SV/P」
    return " ".join(name.split())


def _jan(code):
    m = re.fullmatch(r"(?:\d\d)?(\d{13})", code or "")
    return m.group(1) if m else None


def _read_list(http, category, sub):
    """（商品名, 店の商品コード, 価格, 商品ページのURL, 買取方法, 画像のURL）を順に返す。"""
    params = {"q[product_sub_category_id_eq]": sub, "q[product_sub_category_product_category_id_eq]": category}
    for page in range(1, MAX_PAGES + 1):
        soup = BeautifulSoup(http.get(LIST_URL, params={**params, "page": page}).content, "html.parser")
        for button in soup.select('[data-view-mode-target="cardContainer"] button[data-product-id]'):
            card = button.find_parent("div", class_="h-full")
            price = int(button.get("data-product-price") or 0)
            if not price:
                continue
            code = card.select_one("div.min-h-\\[20px\\] span")
            img = card.find("img")
            badges = [s.get_text(strip=True) for s in card.select("div.absolute span")]
            yield (button["data-product-name"].strip(), code.get_text(strip=True) if code else None, price,
                   f"{URL}products/{button['data-product-id']}", "郵送" if "郵送のみ" in badges else None,
                   urljoin(URL, img["src"]) if img else None)
        if not soup.select_one('a[rel="next"]'):
            break
