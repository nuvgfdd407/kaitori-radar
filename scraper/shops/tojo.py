"""買取TOJO。

Next.js のサイトで、商品の一覧はサイトが使っている API（/api/products?limit=100&page=…）から JSON で読める
（全部で250件ほど・3ページ）。商品ごとに sku（JAN）・basePrice・priceUpdatedAt（価格の更新日時）が入っている。
basePrice は商品ページで「買取価格（新品・未開封）」として出している価格で、状態ごとの価格は別にない。
扱っているのはゲーム機・ゲームソフト・コントローラー・チェキとフィルム・Kindle など。
iPhone・iPad のカテゴリもあるが、商品は載っていない。
- priceUpdatedAt が30日以上前の商品は、価格が古いので使わない（2026-06-01 のまま更新されていない商品が多い）
- sku の前に空白が入っていることがある。ROG Xbox Ally などは12桁の UPC なので、頭に0を付けて JAN にする
- 商品名の「※」の後ろは条件（「※2026年10月以降製造モデル減額対象」など）なので、"note" にする
- 一覧には商品の説明欄がないので、検索の API（/api/products/search?q=、1ページ50件・5ページ）も読んで id で突き合わせ、
  説明欄の製造時期の条件（Switch 有機ELモデルの「※2024年以前に製造された商品は買取しておりません」）と
  使用期限の条件（写ルンです・フィルムの「使用期限まで16ヶ月以上の未開封品に限る」）を "note" にする。
  Switch2 ソフトの「外装シュリンクがないもの、再包装したものは買取不可」は新品・未開封の条件そのものなので載せない
- 「８の付く日のキャンペーン」の商品（sku が campaign）は JAN がないので落ちる
"""
import re
from datetime import datetime, timedelta, timezone

from ..text import find_jan

ID = "tojo"
NAME = "買取TOJO"
SHORT = "TOJO"
URL = "https://kaitoritojo.jp/"

API_URL = URL + "api/products"
SEARCH_URL = API_URL + "/search"
MAX_PAGES = 10
MAX_AGE = timedelta(days=30)
_MADE_BEFORE = re.compile(r"(\d{4})\s*年以前に製造された商品")
_EXPIRY = re.compile(r"使用期限まで\d+ヶ月以上")


def fetch(http):
    since = datetime.now(timezone.utc) - MAX_AGE
    details = {p["id"]: p for p in _read_all(http, SEARCH_URL, q="", limit=50)}
    offers = []
    for p in _read_all(http, API_URL, limit=100):
        sku = (p.get("sku") or "").strip()
        jan = find_jan("0" + sku if len(sku) == 12 and sku.isdigit() else sku)
        price = p.get("basePrice") or 0
        updated = p.get("priceUpdatedAt")
        if not (jan and price and updated and datetime.fromisoformat(updated) >= since):
            continue
        name, _, note = " ".join(p["name"].split()).partition("※")
        offer = {"jan": jan, "name": name.strip(), "price": price, "url": URL + "products/" + p["id"]}
        if note := _note(note.strip(), details.get(p["id"], {})):
            offer["note"] = note
        offers.append(offer)
    return offers


def _read_all(http, url, **params):
    """API の商品を、ページを順にめくって返す。"""
    for page in range(1, MAX_PAGES + 1):
        data = http.get(url, params={**params, "page": page}).json()
        yield from data["products"]
        # ページ数は一覧では pagination の中、検索では一番上にある
        if page >= data.get("pagination", data)["totalPages"]:
            break


def _note(name_note, detail):
    """商品名の「※」の後ろと説明欄の条件（製造時期・使用期限）。なければ空文字。"""
    notes = [name_note] if name_note else []
    text = " ".join(detail.get(k) or "" for k in ("description", "notes", "shortDescription"))
    if m := _MADE_BEFORE.search(text):
        notes.append(f"{int(m.group(1)) + 1}年以降の製造品のみ")
    if m := _EXPIRY.search(text):
        notes.append(m.group() + "のもののみ")
    return "・".join(notes)
