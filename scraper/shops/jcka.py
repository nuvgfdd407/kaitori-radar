"""ジェーシカモバイル（JCKA）。

WordPress（TablePress）のサイトで、買取価格のページ（/kaitori_price/）に全商品の投稿（機種＋容量や
メーカーごと）が並び、投稿ごとに表がある。1ページで全部載っているので、このページだけを読む。
投稿のクラス（kisyu-iphone など）のない「中古iPhone18シリーズ」などの投稿は中古の価格なので使わない。
ページにも投稿にも価格の更新日は出ていない（投稿の更新日時は表の更新と連動しない）。
- iPhone: 「iPhone18Pro Max [2TB]」の投稿に「未開封 判定〇 / 未開封 判定△ / 開封 …」の行がある。
  最初の「未開封」の行（判定〇）だけを使う。この行の備考の「Apple版同額（購入証明必須）」は、
  Apple Store で買った証明があれば SIMフリー版も同じ価格という条件なので "note" にする
  （証明がなければ判定△の行の価格になる）。色の欄の「青・黒・白-10,000」「ｵﾚﾝｼﾞ-5,500・ﾌﾞﾙｰ-1,000」は
  色（漢字1文字やカタカナ）ごとの減額なので、全色の価格にする
- iPad: 「Wi-Fi版・Cellular版 未開封」の行を使い、投稿の下の「[JANコード]」に書かれた JAN（Wi-Fi 版の全色）に
  同じ価格を当てはめる。JAN のない投稿（iPad Pro M5・iPad Air M4・iPad mini8 など）は突き合わせられない。
  色の欄に「黄-2000」のような減額がある行は、どの JAN がその色かわからないので使わない
- AirPods: 「型番 / カラー / 価格」の表で、行ごとの型番で突き合わせる
- Pixel: 「[Google]-ストア版 or キャリア版判定〇のみ」の表の「ｽﾄｱ版価格」（SIMフリー）を使う。
  備考の「Fog-1000」「ブルー-3000」は色ごとの減額
- AQUOS など: メーカーごとの表の「ｽﾄｱ版価格」を SIMフリー版の価格として使う（キャリア版は減額の場合あり）
- ゲーム機: 「機種 / JANｺｰﾄﾞ / 価格 / 備考」の表（Meta Quest は12桁の UPC）。1行に JAN が2つあれば（PS5 Pro の新旧の型番）、
  備考の「CFI-7000B01-10,000」のような型番ごとの減額を、商品名の型番と同じ順の JAN に当てはめる
Apple Watch は型番も JAN もなく、MacBook は「他店対抗価額」で価格がないので使わない。
「お問合せ」の行は飛ばす。
"""
import re
import unicodedata

from bs4 import BeautifulSoup

from ..apple import apple_offer
from ..phones import android_key, phone_color, phone_colors, phone_key
from ..text import parse_yen

ID = "jcka"
NAME = "ジェーシカモバイル"
SHORT = "JCKA"
URL = "https://www.jcka-mobile.co.jp/"

PRICE_PAGE = URL + "kaitori_price/"
APPLE_STORE_NOTE = "Apple Storeで購入した証明が必要"
# 減額の色の書き方 → 公式の色名を探すための別名（機種によってどの色を指すかが違うので、候補を順に試す）
COLOR_ALIASES = {"白": ["white", "silver"], "黒": ["black"], "青": ["blue", "glacier"], "紫": ["purple", "lavender"],
                 "緑": ["green", "sage", "teal"], "ブルー": ["blue", "isai blue"]}
_DEDUCTION = re.compile(r"([^\s\d,\-・]+(?:・[^\s\d,\-・]+)*)\s*-\s*([\d,]+)")
_JAN = re.compile(r"(?<!\d)\d{12,13}(?!\d)")
_MODEL = re.compile(r"[A-Z]{3,4}-[0-9A-Z]+")
# 備考の「CFI-7000B01-10,000」（型番ごとの減額）
_MODEL_DEDUCTION = re.compile(rf"({_MODEL.pattern})\s*-\s*([\d,]+)")


def fetch(http):
    soup = BeautifulSoup(http.get(PRICE_PAGE).content, "html.parser")
    offers = []
    for post in soup.select("div.vk_post"):
        title = post.select_one(".vk_post_title a")
        if not title or not any(c.startswith("kisyu-") for c in post.get("class", [])):
            continue  # 中古の価格の投稿
        name, url = _text(title), title["href"]
        rows = [[_text(td) for td in tr.select("th, td")] for tr in post.select("table tr")]
        if not rows:
            continue
        head = rows[0]
        if head[0] == "未使用品":
            offers += _iphone_offers(name, rows[1:], url)
        elif head[0] == "モデル" and len(head) == 4:
            offers += _ipad_offers(name, rows[1:], " ".join(_text(p) for p in post.select("p")), url)
        elif head[0] == "型番" and "AirPods" in name:
            offers += [apple_offer(f"{name} {row[0]}", parse_yen(row[2]), url) for row in rows[1:] if parse_yen(row[2])]
        elif head[0].startswith("機種") and len(head) > 1 and "JAN" in head[1]:
            offers += _game_offers(rows[1:], url)
        elif head[0].startswith("機種") and len(head) > 1 and "ストア版" in head[1]:
            offers += _android_offers(rows[1:], url)
    return offers


def _text(tag):
    return " ".join(unicodedata.normalize("NFKC", tag.get_text(" ")).split())


def _iphone_offers(name, rows, url):
    """最初の「未開封」の行の価格を、色ごとの減額を引いて全色の価格にする。"""
    key = phone_key(name)
    row = next((r for r in rows if r[0].startswith("未開封")), None)
    if not (key and phone_colors(key) and row and len(row) >= 3 and parse_yen(row[2])):
        return []
    colors = _color_prices(key, parse_yen(row[2]), row[1])
    if not colors:
        return []
    offer = {"jan": None, "key": key, "name": name, "price": max(colors.values()), "url": url, "colors": colors}
    if len(row) > 3 and "購入証明" in row[3]:
        offer["note"] = APPLE_STORE_NOTE
    return [offer]


def _ipad_offers(name, rows, jans, url):
    row = next((r for r in rows if "未開封" in r[0] and "判定" not in r[0]), None)
    if not row or row[1] != "全色" or not parse_yen(row[2]):
        return []  # 色ごとの減額がある行は、どの JAN がその色かわからない
    offer = apple_offer(name, parse_yen(row[2]), url, text=jans)
    return [offer] if offer["codes"] else []


def _android_offers(rows, url):
    offers = []
    for row in rows:
        price = parse_yen(row[1]) if len(row) >= 3 else None
        if not price:
            continue
        name = row[0]
        key = phone_key(name) if "Pixel" in name else android_key(name, "SIMフリー")
        if not (key and phone_colors(key)):
            continue
        colors = _color_prices(key, price, row[2])
        if colors:
            offers.append({"jan": None, "key": key, "name": name, "price": max(colors.values()), "url": url,
                           "colors": colors})
    return offers


def _game_offers(rows, url):
    """1行に JAN が複数あれば、備考の型番ごとの減額を、商品名の型番と同じ順の JAN に当てはめる。"""
    offers = []
    for row in rows:
        price = parse_yen(row[2]) if len(row) >= 3 else None
        jans = _JAN.findall(row[1]) if len(row) >= 2 else []
        if not (price and jans):
            continue
        deductions = {model: parse_yen(amount) for model, amount in _MODEL_DEDUCTION.findall(" ".join(row[3:]))}
        models = _MODEL.findall(row[0])
        if deductions and len(models) != len(jans):
            continue  # どの JAN の減額か決められない
        for i, jan in enumerate(jans):
            amount = deductions.get(models[i], 0) if deductions else 0
            # Meta Quest は12桁の UPC なので、頭に0を付けて13桁にする（カタログの書き方）
            offers.append({"jan": jan.zfill(13), "name": row[0], "price": price - amount, "url": url})
    return offers


def _color_prices(key, base, text):
    """「青・黒・白-10,000」「Fog-1000」→ {公式の色名: 価格}（書かれた色だけ減額する）。
    「開封品-5,000」のような色でない減額は飛ばす。読み取れない色があれば None。"""
    colors = dict.fromkeys(phone_colors(key), base)
    for words, amount in _DEDUCTION.findall(text):
        if "開封" in words or "保証" in words:
            continue
        for word in words.split("・"):
            color = _color(key, word)
            if not color:
                return None
            colors[color] = base - parse_yen(amount)
    return colors


def _color(key, word):
    for alias in [word, *COLOR_ALIASES.get(word, [])]:
        if found := phone_color(key, alias):
            return found
    return None
