"""家電市場。

新品・未使用品の買取が中心の店。カテゴリ（/item/node/<ID>/<名前>）、いくつかのカテゴリをまとめたグループ
（/item/group/<ID>/<名前>）、検索（/item/search/<語>?s=<語>）の一覧に、1ページ50件ずつ（続きは ?page=N）商品が並ぶ。
ほとんどの商品に JAN が載っている。価格は商品ごとの x-data（itemCard({...})）の JSON にあり、
"prices" に状態ごとの価格（"conds" で「新品」の番号が 0、「中古」が 2）が入っている。新品の価格だけを使う
（来店の上乗せ「ご来店 +300円」や、振込を遅らせる「プライム価格」の分は含まない）。
新品の価格は「未開封」「保証未開始」「残債なし」「シュリンク付き」などの選択肢（"groups"）がすべて 0円の状態の価格。
- "stale" が true の商品は、ページに価格を出さず「申込後にご案内」としている（古い価格）ので使わない
- JAN は商品名の下の「JAN: …」の行から読む（備考に別の商品の JAN が書かれていることがある）
- 商品名の下のオレンジの備考に条件が書かれている。「正規代理店の購入証明原本の提出が必要」（ポケモンカードの BOX・
  アクションカメラなど）と「appleストア版のみ買取可」「Appleストア版　未開封」（Cellular の iPad・Apple Watch）は
  "note" に載せる。備考が「お問い合わせください。」の商品（Xperia 1 V・10 V）と「キャリアによって金額が違います、
  お問い合わせください」の商品は要問い合わせなので使わない（「512GB別途お問い合わせください」のように別の容量の案内は除く）。
  備考に他の色の JAN が書かれている商品（「TI:4548736055605　R:4548736055599」）は、その JAN にも同じ価格を当てはめる
- 製造時期で減額のある商品（PS5 デジタル・エディション 日本語専用の選択肢「製造年」の「2026年10月以降 -2000」）は、
  ほかの店と同じく基本の価格のまま、減額を "note" に載せる
- iPhone・Pixel・Galaxy・Xperia・AQUOS は「iPhone 17 Pro 256GB SIMフリー [ディープブルー]」
  「Galaxy A25 5G SC-53F docomo [ブルー]」のように色・キャリアごとに1商品。JAN と、機種＋容量（＋キャリア）と色で突き合わせる。
  [ ] に色のない商品（「Galaxy S25 Ultra 1TB SCG32 au」）は色を問わない価格なので、全色に当てはめる。
  iPhone・Pixel は SIMフリーの商品だけ
- iPad・Apple Watch・AirPods・Mac は商品名に型番が書かれているので、apple_offer で JAN と型番から突き合わせる
- Steam Deck 有機EL・ROG Xbox Ally はノートパソコン（数が多い）、microSD Express は Switch 周辺機器のカテゴリにあるので、
  検索で取る
"""
import json
import re

from bs4 import BeautifulSoup

from ..apple import apple_offer
from ..phones import android_key, one_color, phone_key
from ..text import find_jan

ID = "kaden"
NAME = "家電市場"
SHORT = "家電市場"
URL = "https://www.kaden-ichiba.com/"

# 一覧のパス（/item/ の後ろ。最後の名前の部分が違うと、正しい名前のページへ転送される）
IPHONE_PAGES = ["node/M0003/iPhone Duo", "node/M0005/iPhone 18 Pro Max", "node/M0004/iPhone 18 Pro",
                "node/M0007/iPhone 17 Pro Max", "node/M0006/iPhone 17 Pro", "node/M0008/iPhone 17",
                "node/M0009/iPhone 17e", "node/M0010/iPhone Air", "node/M0011/iPhone 16 Pro Max",
                "node/M0012/iPhone 16 Pro", "node/M0013/iPhone 16 Plus", "node/M0014/iPhone 16",
                "node/M0037/iPhone 16e"]
ANDROID_PAGES = ["node/M0026/Google Pixel", "node/M0032/Samsung Galaxy", "node/M0030/SONY Xperia",
                 "node/M0031/SHARP AQUOS"]
APPLE_PAGES = ["node/M0070/Apple Watch Ultra", "node/M0076/Apple Watch Series", "node/M0077/Apple Watch SE",
               "node/M0089/AirPods", "node/M0069/iPad Pro", "node/M0066/iPad Air", "node/M0068/iPad mini",
               "node/M0067/iPad", "node/0029/Mac ノート", "node/0019/Mac デスクトップ"]
# ゲーム機は Switch・PS5・Xbox・Steam などのカテゴリをまとめたグループ。PS5 ソフトのカテゴリには PS5 の同梱版がある。
# PlayStation 周辺機器は PlayStation Portal のため。フィルムカメラには写ルンです、VR には PlayStation VR2 もある
JAN_PAGES = ["group/35/ゲーム機", "node/4107/プレイステーション5(PS5) ソフト", "node/4143/Nintendo Switch ソフト",
             "node/M0078/PlayStation 周辺機器", "group/71/トレーディングカード", "node/M0121/アクションカメラ",
             "node/0050/デジタルカメラ", "node/2020/ビデオカメラ", "node/1040/インスタントカメラ", "node/1020/フィルムカメラ",
             "node/0087/VRゴーグル・VRヘッドセット"]
SEARCH_WORDS = ["Steam Deck", "Ally", "Micro SD Express"]
MAX_PAGES = 10
CARD_NOTE = "正規代理店の購入証明が必要"
APPLE_NOTE = "Apple Store版の価格"
_CARD = re.compile(r"itemCard\((.*)\)\s*$", re.S)
_JAN = re.compile(r"(?<!\d)\d{13}(?!\d)")
_ASK = re.compile(r"^お問い合わせください|金額が違います、お問い合わせください")


def fetch(http):
    offers, seen = [], set()

    def read(path, params=None):
        for item in _read_list(http, path, params or {}):
            if item["cco"] not in seen:  # 同じ商品がグループとカテゴリ（や検索）の両方に出てくることがある
                seen.add(item["cco"])
                yield item

    for path in IPHONE_PAGES:
        for item in read(path):
            if "SIMフリー" in item["name"]:
                offers.append(_phone_offer(item, phone_key(item["name"])))
    for path in ANDROID_PAGES:
        for item in read(path):
            name = item["name"]
            if "Pixel" in name and "SIMフリー" not in name:
                continue  # カタログの Pixel は SIMフリー版だけ
            key = phone_key(name) if "Pixel" in name else android_key(name)
            offers.append(_phone_offer(item, key) if key else _offer(item))
            # 「Galaxy A25 5G (Softbank・Y!mobile)」は Y!mobile 版にも当てはめる
            if key and key.endswith(" SoftBank") and "Y!mobile" in name:
                offers.append(_phone_offer(item, android_key(name, "Y!mobile")))
    for path in APPLE_PAGES:
        for item in read(path):
            offers.append({**apple_offer(item["name"], item["price"], item["url"], jan=item["jan"]), **_note(item)})
    items = [item for path in JAN_PAGES for item in read(path)]
    items += [item for word in SEARCH_WORDS for item in read("search/" + word, {"s": word})]
    for item in items:
        # 「JAN: …」と書かれた備考は別の商品の案内（「RICOH GR IIIx HDF 特別モデル JAN: …」）なので使わない
        others = _JAN.findall(item["remark"]) if "JAN" not in item["remark"] else []
        offers += [{**_offer(item), "jan": jan} for jan in dict.fromkeys([item["jan"], *others])]
    return [o for o in offers if o["jan"] or o.get("key") or o.get("codes")]


def _offer(item):
    return {"jan": item["jan"], "name": item["name"], "price": item["price"], "url": item["url"], **_note(item)}


def _note(item):
    """備考と選択肢の条件（購入証明・Apple Store 版・製造時期の減額）の "note"。なければ空の辞書。"""
    notes = [CARD_NOTE] if "購入証明" in item["remark"] else []
    if re.search(r"appleストア版", item["remark"], re.IGNORECASE):
        notes.append(APPLE_NOTE)
    notes += item["made"]
    return {"note": "・".join(notes)} if notes else {}


def _phone_offer(item, key):
    offer = {**_offer(item), "key": key}
    # 色ごとの商品は名前の [ ] に色がある。読み取れなければ "colors" を空にして JAN で突き合わせる
    if "[" in item["name"]:
        offer["colors"] = one_color(key, item["name"], item["price"]) if key else {}
    return offer


def _read_list(http, path, params):
    """一覧の新品の価格がある商品を {cco, name, jan, price, url, remark（備考）, made（製造時期の減額）} で順に返す。"""
    for page in range(1, MAX_PAGES + 1):
        soup = BeautifulSoup(http.get(f"{URL}item/{path}", params={**params, "page": page}).content, "html.parser")
        for li in soup.select("li[x-data^='itemCard(']"):
            data = json.loads(_CARD.match(li["x-data"]).group(1))
            new = next((c["code"] for c in data["conds"] if c["label"] == "新品"), None)
            price = data["prices"].get(str(new)) if new is not None else None
            remark = li.select_one("p.whitespace-pre-line")
            remark = " ".join(remark.get_text(" ").split()) if remark else ""
            if data["stale"] or not price or _ASK.search(remark):
                continue
            jan = li.select_one(r"p.mt-0\.5")  # 商品名の下の「JAN: …」の行
            made = [f"{o['label']}製造は{o['adj']:,}円" for g in data["groups"].get(str(new), []) if g.get("help") == "mfg"
                    for o in g["options"] if o["adj"] < 0]
            yield {"cco": data["cco"], "name": " ".join(data["name"].split()),
                   "jan": find_jan(jan.get_text()) if jan else None, "price": int(price),
                   "url": URL.rstrip("/") + data["href"], "remark": remark, "made": made}
        if not soup.select_one(f"a[href*='page={page + 1}']"):
            break
