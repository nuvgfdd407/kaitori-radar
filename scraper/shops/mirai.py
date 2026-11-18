"""買取ミライ。

nopCommerce のサイトで、カテゴリ（/nintendo・/playstation など）の一覧ページに、商品名・「JANコード : 4902370552683」・
説明・価格（「82,000 円」）が並ぶ。1ページの件数はカテゴリで違い（ゲーム20件、FUJIFILM・ポケモンカード12件、
ワンピースカード・Apple 6件）、?pagenumber=N でページを送る。
親カテゴリの一覧にはサブカテゴリの商品は出ず、じかに付いた商品だけが出る。トレカ（/trading-card）には
じかに付いた商品（スペシャルBOX フクオカ）があるので、ポケモンカード・ワンピースカードとは別に読む。
標準の並び（強化商品順）は同じ順位の商品の順番がページを開くたびに変わり、重複や取りこぼしが出るので、
登録の新しい順（orderby=15）で読む。
新品・未開封だけを買い取る店なので、一覧の価格をそのまま使う（日付の表示はなく「価格随時更新」）。
- 説明に「4948872417075 同額」のように別の JAN が書かれていれば、その JAN の商品にも同じ価格を当てはめる
  （PS5 Pro・Xbox Series X の新旧の型番など。Steam Deck は「814585022629同額」と12桁で書かれている）
- 説明欄の買取の条件は、ほかの店（guild・tojo・base）と同じく一覧の価格のまま "note" に載せる。
  ポケモンカードの BOX の「LINE予約必須 / 購入履歴／レシート提示必須」、製造時期（Switch 有機ELモデルの
  「買取対象は2025年以降に製造された商品に限らせていただきます」、PS5 デジタル・エディションの
  「【2026年10月以降製造モデル -2000】」）、使用期限（写ルンです の「使用期限残り18ヶ月以上」）
- JAN の欄が店独自の15桁の番号の商品（スタートデッキ100 バトルコレクション）は使わない
- Apple Watch・AirPods は「その他家電」にあり、JAN（と名前に型番）が載っている
PS5 ソフト・ホビー・Fitbit・Kindle・グラフィックボード・Polaroid のカテゴリはカタログにないので取らない。
「買取強化商品」は他のカテゴリの商品を集めたものなので取らない。
"""
import re
from urllib.parse import quote, urljoin

from bs4 import BeautifulSoup

from ..apple import apple_offer
from ..text import parse_yen

ID = "mirai"
NAME = "買取ミライ"
SHORT = "ミライ"
URL = "https://kaitori-mirai.com/"

# Switch 本体 / PlayStation / Xbox / Meta Quest / Steam Deck / Switch ソフト / Switch 2 ソフト / チェキ・写ルンです /
# トレカ（じかに付いた商品） / ポケモンカード / ワンピースカード
CATEGORIES = ["nintendo", "playstation", "xbox", "meta", "steam-deck", "switch", "switch-2-2", "fujifilm",
              "trading-card", "ポケモンカード", "ワンピースカード"]
APPLE_CATEGORY = "その他家電"
CARD_NOTE = "LINE予約と購入履歴・レシートの提示が必要"
NEWEST = 15  # 並び順: 登録の新しい順
MAX_PAGES = 10
_JAN = re.compile(r"(?<!\d)(\d{12,13})(?!\d)")
_MADE_SINCE = re.compile(r"(\d{4})\s*年以降に製造された商品に限")
_MADE_AFTER = re.compile(r"\d{4}\s*年\s*\d{1,2}\s*月以降製造[^】]*")  # 「【2026年10月以降製造モデル -2000】」
_EXPIRY = re.compile(r"使用期限残り(\d+)ヶ月以上")


def fetch(http):
    offers = []
    for category in CATEGORIES:
        for name, jans, desc, price, url in _read_list(http, category):
            note = {"note": n} if (n := _note(desc)) else {}
            offers += [{"jan": jan, "name": name, "price": price, "url": url, **note} for jan in jans]
    for name, jans, desc, price, url in _read_list(http, APPLE_CATEGORY):
        offers += [apple_offer(name, price, url, jan=jan, text=desc) for jan in jans]
    return offers


def _read_list(http, category):
    """一覧の（商品名, [JAN, 同額の JAN…], 説明, 価格, 商品ページの URL）を順に返す。"""
    for page in range(1, MAX_PAGES + 1):
        res = http.get(URL + quote(category), params={"orderby": NEWEST, "pagenumber": page})
        soup = BeautifulSoup(res.content, "html.parser")
        for item in soup.select(".product-item"):
            title, gtin, price, desc = (item.select_one(s) for s in (".product-title a", ".GTIN", ".actual-price", ".description"))
            jans = _jans(gtin.get_text()) if gtin else []
            price = parse_yen(price.get_text()) if price else None
            if not (title and jans and price):
                continue  # JAN の欄が店独自の番号の商品と、価格のない商品
            desc = " ".join(desc.get_text().split()) if desc else ""
            if "同額" in desc:
                jans += [j for j in _jans(desc) if j not in jans]
            yield " ".join(title.get_text().split()), jans, desc, price, urljoin(URL, title["href"])
        if not soup.select_one(".pager .next-page"):
            break


def _note(desc):
    """説明欄の買取の条件（トレカの予約とレシート・製造時期・使用期限）。なければ空文字。"""
    notes = [CARD_NOTE] if "レシート提示必須" in desc else []
    if m := _MADE_SINCE.search(desc):
        notes.append(f"{m.group(1)}年以降の製造品のみ")
    if m := _MADE_AFTER.search(desc):
        notes.append(m.group().strip())
    if m := _EXPIRY.search(desc):
        notes.append(f"使用期限まで{m.group(1)}ヶ月以上のもののみ")
    return "・".join(notes)


def _jans(text):
    """文字列の中の JAN（12桁の UPC は先頭に0を付けて13桁にする）。"""
    return [jan.zfill(13) for jan in _JAN.findall(text)]
