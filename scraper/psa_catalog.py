"""PSA 鑑定品のカタログ（catalog/products.json の psa-* シリーズ）を、店舗の出品から作り直す。

    python -m scraper.psa_catalog

- PSA を買い取っている店舗（SHOP_ORDER）の出品を集め、同じカードを1商品にまとめる
- 同じカードとみなすのは、psa_key が同じとき。または、ゲーム・点数・カード番号・バリエーションが同じで、
  片方の名前がもう片方の名前で始まるとき（「R団のサンダー 25th」と「R団のサンダー(25th)」など）。
  ただし、同じ店舗が別々に載せている商品（ナミと「ナミ SP」など）は、別のカードなのでまとめない
- 名前を通称で書く店舗（トレカバースの「ムンクコダック」）や、番号を略す店舗（ゴールデンホビーの「063」、
  トレカバースの遊戯王の「JP003」）のために、次のどちらかで候補が1つに決まり、価格も近ければ同じカードとみなす（_loose）
  - 番号が合っていて（「063」と「063/051」、「JP003」と「QCCU-JP003」も合うとする）、片方の名前がもう片方に含まれる。
    ただし、その店舗の同じ番号のカードのうち、名前が合うのが1枚だけのとき（トレカバースの「フラシペローナ」と
    「ぬいぐるみペローナ」のように、同じ番号の別のカードを通称で分けている店舗があるため）
  - ワンピースで、番号とバリエーションがまったく同じ商品が1つしかなく、その店舗もその番号のカードを1枚しか載せていない
    （名前は見ない。ワンピースの番号は収録弾ごとに別なので。ポケモンカードは「173/086」がブラックボルトと
    ホワイトフレアの両方にあるように、番号だけでは決まらない）
  価格が近いとは、その商品のほかの店舗の価格との差が PRICE_RATIO 倍以内（金のカードと通常のカードなどを取り違えないように）
- すでにある商品は ID（URL）と名前を変えず、店舗の書き方（"keys"）を足すだけ。新しいカードは商品を追加する。
  ただし、番号を略す店舗（NO_NEW）のカードや、番号がまったく同じ商品があるのに同じカードと決められなかったカードは、
  重複を避けるため商品を追加しない。ワンピースは、トレカラウンジ以外の店舗のカードは、バリエーションが違っても
  番号がまったく同じ商品があれば追加しない（和柄・金背景・手配書などの別の版を、店舗ごとにばらばらの書き方で分けているため）
- 店舗の一覧から消えたカードも、商品は残す（価格は「取扱なし」になる）
- 店舗ごとの書き方の違いで同じカードが2つの商品になっていたら、まとめる（_duplicates）
- 画像は、IMAGE_SHOPS の順に、載っている店舗のカード画像を使う。
  森森買取は一覧に画像がないので、画像のないカードだけ商品ページを見にいく。
  シンソク・森森買取の画像には PSA のケースごと写したものがあり、"image_crop": "slab" を付けてカードの部分だけ切り抜く
  （scraper.images）。上の店舗に載ったら、その店舗の画像に替える
- 並び順は、ゲームごとに、すでにある商品は今のまま、新しい商品はその後ろに最高値の高い順で足す
  （毎日自動で動かすので、変化がなければファイルを書き換えない）
"""
import hashlib
import json
import sys
from concurrent.futures import ThreadPoolExecutor

from .common import CATALOG, load_json, write_catalog
from .http import INTERVAL, Http
from .shops import birth, club, golden, homura, lounge, morimori, shinsoku, torecabank

SERIES = {
    "pokemon": {"id": "psa-pokemon", "name": "PSA鑑定品（ポケモンカード）", "category": "tcg"},
    "onepiece": {"id": "psa-onepiece", "name": "PSA鑑定品（ワンピース）", "category": "tcg"},
    "yugioh": {"id": "psa-yugioh", "name": "PSA鑑定品（遊戯王）", "category": "tcg"},
}
# 名前を付けるときに優先する店舗（トレカラウンジは名前・レアリティ・番号が別々に載っていて読みやすい）
SHOP_ORDER = ["lounge", "homura", "morimori", "shinsoku", "torecabank", "club", "birth", "golden"]
SHOPS = {"lounge": lounge, "homura": homura, "morimori": morimori, "shinsoku": shinsoku, "torecabank": torecabank,
         "club": club, "birth": birth, "golden": golden}
# カタログにないカードでも商品を追加しない店舗（番号が略してあり、ほかの店舗のカードと突き合わせられなくなる）
NO_NEW = {"golden"}
# 名前を見ずに番号だけで突き合わせてよいゲーム（番号に収録弾が入っている）
NUMBER_ONLY_GAMES = {"onepiece"}
PRICE_RATIO = 2
# 画像を使う店舗（先のものほど優先。カード単体の画像の店舗が先で、PSA のケースごと写した画像の店舗（SLAB_SHOPS）は後）
IMAGE_SHOPS = {name: SHOPS[name].NAME
               for name in ["lounge", "homura", "club", "birth", "torecabank", "golden", "shinsoku", "morimori"]}
SLAB_SHOPS = {"shinsoku", "morimori"}


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    jobs = [(name, shop, Http(getattr(shop, "INTERVAL", INTERVAL))) for name, shop in SHOPS.items()]
    with ThreadPoolExecutor(len(jobs)) as pool:
        results = list(pool.map(lambda job: [{**o, "shop": job[0]} for o in job[1].fetch_psa(job[2])], jobs))
    offers = [o for result in results for o in result]
    print("出品: " + "・".join(f"{name} {len(result)}件" for (name, _, _), result in zip(jobs, results)))

    catalog = load_json(CATALOG)
    before = json.dumps(catalog, ensure_ascii=False)
    added, lookups, skipped = merge(catalog, offers)
    if lookups:
        print(f"森森買取の商品ページで画像を探します（{len(lookups)}件）")
    for product, url in lookups:
        try:
            image = morimori.psa_image(Http(morimori.INTERVAL), url)
        except Exception as e:  # noqa: BLE001 - 画像が取れなくてもカタログの更新は続ける
            print(f"{product['name']}: 画像を取得できませんでした（{e}）", file=sys.stderr)
            continue
        if image:
            _set_image(product, image, url, "morimori")
    changed = json.dumps(catalog, ensure_ascii=False) != before
    if changed:
        write_catalog(catalog)
    count = sum(1 for p in catalog["products"] if p["series"].startswith("psa-"))
    if skipped:
        print(f"カタログと突き合わせられなかった出品 {len(skipped)}件: " + "、".join(skipped[:20]))
    print(f"PSA の商品は {count}件（うち新しく追加 {added}件）。"
          + ("catalog/products.json を更新しました" if changed else "変化なし"))


def merge(catalog, offers):
    psa_ids = {s["id"] for s in SERIES.values()}
    for series in SERIES.values():
        if series["id"] not in {s["id"] for s in catalog["series"]}:
            catalog["series"].append(dict(series))
    products = [p for p in catalog["products"] if p["series"] in psa_ids]
    position = {p["jan"]: n for n, p in enumerate(products)}
    by_key = {key: p for p in products for key in p.get("keys", [])}
    shops = {}  # 商品 → {店舗: その店舗での書き方}
    best = {}
    images = {}  # 商品 → 画像を使う店舗の（店舗, 出品）
    added = 0
    skipped = []  # 突き合わせられず、商品も追加しなかった出品の名前
    offers = sorted(offers, key=lambda o: SHOP_ORDER.index(o["shop"]))
    # 店舗ごとの、同じ番号・バリエーションのカードの名前
    same_number = {}
    for o in offers:
        same_number.setdefault((o["shop"], *_number_head(o["key"])), []).append(o["key"].split("|")[3])
    for o in offers:
        key = o["key"]
        product = by_key.get(key) or _similar(products, key, o["shop"], shops, o["price"], best)
        if product is None:
            group = same_number[(o["shop"], *_number_head(key))]
            product, candidates = _loose(products, key, o["shop"], shops, o["price"], best, group)
            if product is None and (candidates or o["shop"] in NO_NEW):
                skipped.append(f"{SHOPS[o['shop']].NAME} {o['name']}")
                continue
        if product is None:
            info = o["psa"]
            product = {"jan": "psa-" + hashlib.sha1(key.encode()).hexdigest()[:10],
                       "series": SERIES[info["game"]]["id"], "name": _name(info), "msrp": None, "keys": []}
            products.append(product)
            added += 1
        if key not in product["keys"]:
            product["keys"].append(key)
        if _image_rank(o["shop"]) < _image_rank(images.get(product["jan"], (None,))[0]):
            images[product["jan"]] = (o["shop"], o)
        shops.setdefault(product["jan"], {}).setdefault(o["shop"], key)
        by_key[key] = product
        best[product["jan"]] = max(best.get(product["jan"], 0), o["price"] or 0)
    for gone in _duplicates(products, shops, best):
        products.remove(gone)
    lookups = []  # 森森買取の商品ページで画像を探す（商品, 商品ページのURL）
    by_name = {v: k for k, v in IMAGE_SHOPS.items()}
    for p in products:
        shop, o = images.get(p["jan"], (None, None))
        current = by_name.get(p.get("image_source")) if p.get("image_url") else None
        if shop is None or _image_rank(shop) >= _image_rank(current):
            continue
        if shop == "morimori":
            lookups.append((p, o["url"]))
        elif o["psa"].get("image"):
            _set_image(p, o["psa"]["image"], o["psa"]["page"], shop)
    order = [s["id"] for s in SERIES.values()]
    products.sort(key=lambda p: (order.index(p["series"]) if p["series"] in order else 99, p["jan"] not in position,
                                 position.get(p["jan"], 0), -best.get(p["jan"], 0)))
    # PSA 以外の商品の並びは変えず、PSA の商品はトレカの最後のシリーズの後ろに置く
    others = [p for p in catalog["products"] if p["series"] not in psa_ids]
    tcg = {s["id"] for s in catalog["series"] if s["category"] == "tcg" and s["id"] not in psa_ids}
    i = max((n for n, p in enumerate(others) if p["series"] in tcg), default=len(others) - 1) + 1
    catalog["products"] = others[:i] + products + others[i:]
    return added, lookups, skipped


def _duplicates(products, shops, best):
    """店舗ごとの書き方の違いで別々にできてしまった同じカードの商品（「ムンクコダック」と「コダック(ムンク)」）を
    まとめ、消す方の商品を返す。番号・バリエーションがまったく同じで、片方の名前がもう片方に含まれ、
    同じ店舗が両方に載せておらず、価格も近いものをまとめる。先にある商品（URL）を残し、後の商品の "keys" を移す。"""
    gone = []
    for i, a in enumerate(products):
        for b in products[i + 1:]:
            if b in gone or a in gone or not _same_card(a, b) or set(shops.get(a["jan"], {})) & set(shops.get(b["jan"], {})):
                continue
            if not _near(best.get(a["jan"]), best.get(b["jan"])):
                continue
            a["keys"] += [k for k in b["keys"] if k not in a["keys"]]
            shops.setdefault(a["jan"], {}).update(shops.get(b["jan"], {}))
            best[a["jan"]] = max(best.get(a["jan"], 0), best.get(b["jan"], 0))
            gone.append(b)
    return gone


def _same_card(a, b):
    for ka in a.get("keys", []):
        game, grade, number, core, variant = ka.split("|")
        if "/" not in number and "-" not in number:
            continue  # 略した番号（遊戯王の「JP001」）は別のカードでも同じになる
        for kb in b.get("keys", []):
            o_game, o_grade, o_number, o_core, o_variant = kb.split("|")
            if (game, grade, number, variant) == (o_game, o_grade, o_number, o_variant) and _name_match(core, o_core):
                return True
    return False


def _image_rank(shop):
    return list(IMAGE_SHOPS).index(shop) if shop in IMAGE_SHOPS else len(IMAGE_SHOPS)


def _set_image(product, url, page, shop):
    product.update({"image_url": url, "image_page": page, "image_source": IMAGE_SHOPS[shop]})
    product.pop("image_crop", None)
    if shop in SLAB_SHOPS:
        product["image_crop"] = "slab"


def _parts(key):
    game, grade, number, core, variant = key.split("|")
    return (game, grade, number, variant.replace("1ED", "").strip("+")), core


def _similar(products, key, shop, shops, price, best):
    """番号などが同じで、名前の片方がもう片方で始まる商品（なければ None）。
    同じ店舗が別の書き方で載せている商品や、価格が離れている商品（シンソクの「モンキー・D・ルフィ(ONE PIECE magazine)」と
    ほかの店舗の「モンキー・D・ルフィ」など）は、別のカードなので選ばない。"""
    head, core = _parts(key)
    for p in products:
        if shops.get(p["jan"], {}).get(shop, key) != key or not _near(price, best.get(p["jan"])):
            continue
        for other in p.get("keys", []):
            other_head, other_core = _parts(other)
            short = min(core, other_core, key=len)
            if other_head == head and len(short) >= 2 and (core.startswith(other_core) or other_core.startswith(core)):
                return p
    return None


def _near(price, known):
    """価格が近いか（片方がわからなければ近いとみなす）。"""
    return not (price and known) or max(known, price) / min(known, price) <= PRICE_RATIO


def _number_head(key):
    game, grade, number, _, variant = key.split("|")
    return game, grade, number, variant


def _loose(products, key, shop, shops, price, best, group):
    """名前を通称で書く店舗・番号を略す店舗のための、ゆるい突き合わせ（説明は先頭）。
    group は、その店舗が同じ番号・バリエーションで載せているカードの名前（_core）の一覧。
    （商品, 候補があったか）を返す。候補が絞れないか価格が離れていれば、商品は None。
    候補があったのに決められなかったカードは、重複を避けるため商品を追加しない。"""
    game, grade, number, core, variant = key.split("|")
    by_name, by_number, seen = [], [], False
    for p in products:
        for other in p.get("keys", []):
            o_game, o_grade, o_number, o_core, o_variant = other.split("|")
            # ワンピースは同じ番号の別の版（和柄・金背景など）を店舗ごとにばらばらの書き方で分けているので、
            # 2番目以降の店舗のカードは、バリエーションが違っても番号がまったく同じ商品があれば追加しない
            if (game in NUMBER_ONLY_GAMES and shop != SHOP_ORDER[0] and (o_game, o_grade) == (game, grade)
                    and number == o_number):
                seen = True
            if shops.get(p["jan"], {}).get(shop, key) != key:
                continue  # この店舗が別の書き方で載せている商品は、別のカード
            if (o_game, o_grade, o_variant) != (game, grade, variant) or not _same_number(number, o_number):
                continue
            # 番号がまったく同じ商品がある（遊戯王の「JP001」のように略した番号は、別のカードでも同じになるので数えない）
            seen = seen or (number == o_number and ("/" in number or "-" in number))
            # 名前が合い、この店舗の同じ番号のカードのうち名前が合うのがこのカードだけ
            if _name_match(core, o_core) and sum(_name_match(c, o_core) for c in group) == 1:
                by_name.append(p)
            if number == o_number and game in NUMBER_ONLY_GAMES and len(group) == 1:
                by_number.append(p)
    by_name = list({p["jan"]: p for p in by_name}.values())
    by_number = list({p["jan"]: p for p in by_number}.values())
    for candidates, need_price in ((by_name, False), (by_number, True)):
        if len(candidates) == 1:
            p = candidates[0]
            known = best.get(p["jan"])
            if not _near(price, known):
                return None, True
            if known or not need_price:
                return p, True
        if candidates:
            return None, True
    return None, seen


def _name_match(a, b):
    """片方の名前（_core）がもう片方に含まれる（「ムンクコダック」と「コダック」）。"""
    return len(min(a, b, key=len)) >= 2 and (a in b or b in a)


def _same_number(a, b):
    """「063」と「063/051」、「JP003」と「QCCU-JP003」のように、略した番号も合うとみなす。"""
    if a == b:
        return True
    short, full = sorted((a, b), key=len)
    return full.split("/")[0] == short if short.isdigit() else full.endswith("-" + short)


def _name(info):
    name = info.get("name") or ""
    rarity = info.get("rarity")
    if rarity and rarity in name.split():
        rarity = None  # 名前にレアリティが入っている店舗もある（「ミカンのまなざし SAR」）
    return " ".join(p for p in [info.get("grade"), name, rarity, info.get("number")] if p)


if __name__ == "__main__":
    main()
