"""PSA 鑑定品のカタログ（catalog/products.json の psa-* シリーズ）を、店舗の出品から作り直す。

    python -m scraper.psa_catalog

- PSA を買い取っている店舗（買取ホムラ・森森買取・トレカラウンジ）の出品を集め、同じカードを1商品にまとめる
- 同じカードとみなすのは、psa_key が同じとき。または、ゲーム・点数・カード番号・バリエーションが同じで、
  片方の名前がもう片方の名前で始まるとき（「R団のサンダー 25th」と「R団のサンダー(25th)」など）。
  ただし、同じ店舗が別々に載せている商品（ナミと「ナミ SP」など）は、別のカードなのでまとめない
- すでにある商品は ID（URL）と名前を変えず、店舗の書き方（"keys"）を足すだけ。新しいカードは商品を追加する
- 店舗の一覧から消えたカードも、商品は残す（価格は「取扱なし」になる）
- 並び順は、ゲームごとに、すでにある商品は今のまま、新しい商品はその後ろに最高値の高い順で足す
  （毎日自動で動かすので、変化がなければファイルを書き換えない）
"""
import hashlib
import json
import sys
from concurrent.futures import ThreadPoolExecutor

from .common import CATALOG, load_json, write_catalog
from .http import Http
from .shops import homura, lounge, morimori

SERIES = {
    "pokemon": {"id": "psa-pokemon", "name": "PSA鑑定品（ポケモンカード）", "category": "tcg"},
    "onepiece": {"id": "psa-onepiece", "name": "PSA鑑定品（ワンピース）", "category": "tcg"},
    "yugioh": {"id": "psa-yugioh", "name": "PSA鑑定品（遊戯王）", "category": "tcg"},
}
# 名前を付けるときに優先する店舗（トレカラウンジは名前・レアリティ・番号が別々に載っていて読みやすい）
SHOP_ORDER = ["lounge", "homura", "morimori"]


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    jobs = [("lounge", lounge, Http()), ("homura", homura, Http()), ("morimori", morimori, Http(morimori.INTERVAL))]
    with ThreadPoolExecutor(len(jobs)) as pool:
        results = list(pool.map(lambda job: [{**o, "shop": job[0]} for o in job[1].fetch_psa(job[2])], jobs))
    offers = [o for result in results for o in result]
    print("出品: " + "・".join(f"{name} {len(result)}件" for (name, _, _), result in zip(jobs, results)))

    catalog = load_json(CATALOG)
    before = json.dumps(catalog, ensure_ascii=False)
    added = merge(catalog, offers)
    changed = json.dumps(catalog, ensure_ascii=False) != before
    if changed:
        write_catalog(catalog)
    count = sum(1 for p in catalog["products"] if p["series"].startswith("psa-"))
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
    added = 0
    offers = sorted(offers, key=lambda o: SHOP_ORDER.index(o["shop"]))
    for o in offers:
        key = o["key"]
        product = by_key.get(key) or _similar(products, key, o["shop"], shops)
        if product is None:
            info = o["psa"]
            product = {"jan": "psa-" + hashlib.sha1(key.encode()).hexdigest()[:10],
                       "series": SERIES[info["game"]]["id"], "name": _name(info), "msrp": None, "keys": []}
            products.append(product)
            added += 1
        if key not in product["keys"]:
            product["keys"].append(key)
        shops.setdefault(product["jan"], {}).setdefault(o["shop"], key)
        by_key[key] = product
        best[product["jan"]] = max(best.get(product["jan"], 0), o["price"] or 0)
    order = [s["id"] for s in SERIES.values()]
    products.sort(key=lambda p: (order.index(p["series"]) if p["series"] in order else 99, p["jan"] not in position,
                                 position.get(p["jan"], 0), -best.get(p["jan"], 0)))
    # PSA 以外の商品の並びは変えず、PSA の商品はトレカの最後のシリーズの後ろに置く
    others = [p for p in catalog["products"] if p["series"] not in psa_ids]
    tcg = {s["id"] for s in catalog["series"] if s["category"] == "tcg" and s["id"] not in psa_ids}
    i = max((n for n, p in enumerate(others) if p["series"] in tcg), default=len(others) - 1) + 1
    catalog["products"] = others[:i] + products + others[i:]
    return added


def _parts(key):
    game, grade, number, core, variant = key.split("|")
    return (game, grade, number, variant.replace("1ED", "").strip("+")), core


def _similar(products, key, shop, shops):
    """番号などが同じで、名前の片方がもう片方で始まる商品（なければ None）。
    同じ店舗が別の書き方で載せている商品は、別のカードなので選ばない。"""
    head, core = _parts(key)
    for p in products:
        if shops.get(p["jan"], {}).get(shop, key) != key:
            continue
        for other in p.get("keys", []):
            other_head, other_core = _parts(other)
            short = min(core, other_core, key=len)
            if other_head == head and len(short) >= 2 and (core.startswith(other_core) or other_core.startswith(core)):
                return p
    return None


def _name(info):
    name = info.get("name") or ""
    rarity = info.get("rarity")
    if rarity and rarity in name.split():
        rarity = None  # 名前にレアリティが入っている店舗もある（「ミカンのまなざし SAR」）
    return " ".join(p for p in [info.get("grade"), name, rarity, info.get("number")] if p)


if __name__ == "__main__":
    main()
