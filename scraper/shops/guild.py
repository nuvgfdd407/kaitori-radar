"""買取ギルド。

新品・未開封だけを買い取る会員制の店。買取商品の一覧（/catalog?lc=<ジャンル>&page=N、1ページ15件）は
Next.js のサーバー側で組み立てられていて、HTML に埋め込まれたデータ（self.__next_f.push）に、商品ごとの
商品名・JAN・買取価格（目安）が入っている。robots.txt が /api/ を禁止しているので、一覧の HTML だけを読む。
ジャンルはゲーム機・トレカ・iPhone・カメラ・Apple製品を取る（家電は Kindle・Starlink などでカタログにないので取らない）。
- 色・型番違いや状態違いは1つの商品の中に「variantGroup」としてまとまっていて、それぞれに JAN と価格がある
- トレカの BOX は「シュリンク有」「シュリンク無」が同じ JAN で別の行になっている。シュリンク無と開封済みの行は使わない
- 価格が0円（「個別にお見積りします」）、問い合わせだけの商品（isInquiryOnly）、受付の残りが0の商品は使わない
- iPhone・iPad・AirPods も JAN が載っているので JAN で突き合わせる（iPad・AirPods は商品名の型番も付ける）
- 「翌日午前着のみ」（iPhone）、備考の製造時期の条件（Switch 有機ELモデルの「2025 年以前に製造された商品は買取お断り」、
  PS5 デジタル・エディションの「※2026年10月以降製造モデル減額対象」）、使用期限の条件（写ルンです・フィルムの
  「使用期限残り16ヶ月以上」）は "note" に載せる
商品ごとのページはない（一覧から詳細を開く形）ので、URL は JAN で検索した一覧（/catalog?q=JAN）にする。
更新日は載っていない。
"""
import json
import re

from ..apple import apple_offer

ID = "guild"
NAME = "買取ギルド"
SHORT = "ギルド"
URL = "https://kaitoriguild.co.jp/"

LIST_URL = URL + "catalog"
# ジャンル（lc）: ゲーム機 / トレカ / iPhone / カメラ
GENRES = ["d070d393-b5ac-408e-8c77-810ce2a8d761", "c9e42f51-db2d-4c0e-ae47-918c86a57236",
          "fdf20e9b-1c83-4768-aaba-050a020c520c", "4363e9ff-3cfe-4658-90f4-00d9624e68f2"]
# Apple製品（iPad・AirPods）。商品名の型番でも突き合わせる
APPLE_GENRE = "ce3406cb-0a26-43da-b067-37b64649b5ad"
MAX_PAGES = 10
_PUSH = re.compile(r'self\.__next_f\.push\(\[1,(".*?")\]\)</script>', re.S)
_ROW = re.compile(r'\{"product":\{"id"')
_PAGES = re.compile(r'"totalPages":(\d+)')
_NOT_NEW = re.compile(r"シュリンク無|開封済")
_MADE_BEFORE = re.compile(r"(\d{4})\s*年以前に製造された商品")
_MADE_AFTER = re.compile(r"\d{4}\s*年\s*\d{1,2}\s*月以降製造\S*")  # 「2026年10月以降製造モデル減額対象」
_EXPIRY = re.compile(r"使用期限残り(\d+)ヶ月以上")


def fetch(http):
    offers = []
    for genre in GENRES + [APPLE_GENRE]:
        for item in _read_genre(http, genre):
            name, jan, price = item["name"], item["janCode"], item["referencePrice"]
            if not price or item["isInquiryOnly"] or item.get("remainingQuantity") == 0 or _NOT_NEW.search(name):
                continue
            url = f"{LIST_URL}?q={jan}"
            offer = (apple_offer(name, price, url, jan=jan) if genre == APPLE_GENRE
                     else {"jan": jan, "name": name, "price": price, "url": url})
            if note := _note(item):
                offer["note"] = note
            offers.append(offer)
    return offers


def _read_genre(http, genre):
    """ジャンルの一覧の商品を、ページを順にめくって返す。色違いなどは1つずつの商品にして返す。
    最後のページより先を開くと最後のページがもう一度出るので、ページ数（totalPages）までで止める。"""
    for page in range(1, MAX_PAGES + 1):
        html = http.get(LIST_URL, params={"lc": genre, **({"page": page} if page > 1 else {})}).text
        data = "".join(json.loads(s) for s in _PUSH.findall(html))
        for m in _ROW.finditer(data):
            row = json.JSONDecoder().raw_decode(data, m.start())[0]["product"]
            group = row.get("variantGroup")
            yield from ([v["product"] for v in group["variants"]] if group else [row])
        pages = _PAGES.search(data)
        if not pages or page >= int(pages.group(1)):
            break


def _note(item):
    """買取の条件（郵送の着日・製造時期・使用期限）。なければ None。"""
    notes = []
    text = item.get("notes") or ""
    if item.get("requiresNextDayDelivery"):
        notes.append("郵送は翌日午前着のみ")
    if m := _MADE_BEFORE.search(text):
        notes.append(f"{int(m.group(1)) + 1}年以降の製造品のみ")
    if m := _MADE_AFTER.search(text):
        notes.append(m.group())
    if m := _EXPIRY.search(text):
        notes.append(f"使用期限まで{m.group(1)}ヶ月以上のもののみ")
    return "・".join(notes) or None
