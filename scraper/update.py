"""各店舗の買取価格を取得して public/data/prices.json を更新する。

    python -m scraper.update

- 店舗ごとに並行して取得する。失敗した店舗は前回の価格を残し、取得エラーとして記録する
- 価格や取得状況が前回と同じなら prices.json は書き換えない
  （GitHub Actions で変化があったときだけコミットするため）
- カタログにない高額商品は reports/unmatched.json に書き出す（新しい本体の登録漏れに気づくため）
- 商品画像は scraper.images が作った catalog/images.json から載せる
"""
import sys
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone

from .common import CATALOG, IMAGES, ROOT, load_json, set_github_output, warn, write_json
from .http import Http
from .shops import SHOPS

OUTPUT = ROOT / "public" / "data" / "prices.json"
UNMATCHED = ROOT / "reports" / "unmatched.json"

JST = timezone(timedelta(hours=9))
# カタログにない商品のうち、この金額以上のものは本体の可能性があるので報告する
REPORT_MIN_PRICE = 20000
# カタログの項目のうち、公開するデータには載せないもの（画像選びの設定、別のJAN）
INTERNAL_KEYS = {"image_item", "aliases"}


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    catalog = load_json(CATALOG)
    images = load_json(IMAGES) if IMAGES.exists() else {}
    # 同じ商品が別のJAN（新旧のJANなど）で載っていることがあるので、"aliases" のJANも同じ商品として扱う
    owner = {jan: p["jan"] for p in catalog["products"] for jan in [p["jan"], *p.get("aliases", [])]}
    ignored = {p["jan"] for p in catalog.get("ignore", [])}
    previous = load_json(OUTPUT) if OUTPUT.exists() else {"shops": [], "products": []}
    prev_shops = {s["id"]: s for s in previous["shops"]}
    prev_prices = {p["jan"]: p["prices"] for p in previous["products"]}

    with ThreadPoolExecutor(max_workers=len(SHOPS)) as pool:
        results = list(pool.map(fetch_shop, SHOPS))

    now = datetime.now(JST).isoformat(timespec="seconds")
    prices = {p["jan"]: {} for p in catalog["products"]}
    shops = []
    unmatched = []
    for shop, offers, error in results:
        found = {}
        if offers:
            for offer in offers:
                jan = offer["jan"]
                if jan in owner:
                    # 同じ商品が複数回（ページ内の重複や別のJANで）載っていたら、高い方を使う
                    current = found.get(owner[jan])
                    if current is None or offer["price"] > current["price"]:
                        found[owner[jan]] = {"price": offer["price"], "url": offer["url"]}
                elif jan not in ignored and offer["price"] >= REPORT_MIN_PRICE:
                    unmatched.append({"shop": shop.NAME, **offer})
            if not found:
                error = "対象商品が1件も見つかりませんでした（ページの構成が変わった可能性があります）"

        entry = {"id": shop.ID, "name": shop.NAME, "short": shop.SHORT, "url": shop.URL, "ok": error is None}
        if error:
            warn(f"{shop.NAME}: {error}")
            entry["failing_since"] = prev_shops.get(shop.ID, {}).get("failing_since") or now
            found = {jan: p[shop.ID] for jan, p in prev_prices.items() if jan in prices and shop.ID in p}
        else:
            print(f"[OK] {shop.NAME}: {len(offers)}件を取得、うち対象商品 {len(found)}件")
        for jan, offer in found.items():
            prices[jan][shop.ID] = offer
        shops.append(entry)

    data = {
        "series": catalog["series"],
        "shops": shops,
        "products": [
            {
                **{k: v for k, v in p.items() if k not in INTERNAL_KEYS},
                **({"image": images[p["jan"]]} if p["jan"] in images else {}),
                "prices": prices[p["jan"]],
            }
            for p in catalog["products"]
        ],
    }
    changed = any(data[key] != previous.get(key) for key in data)
    if changed:
        write_json(OUTPUT, {"updated_at": now, **data})
    print("価格や取得状況に変化あり。prices.json を更新しました" if changed else "変化なし")

    unmatched = sorted(_unique(unmatched), key=lambda o: (o["shop"], -o["price"]))
    if not UNMATCHED.exists() or load_json(UNMATCHED) != unmatched:
        write_json(UNMATCHED, unmatched)
    if unmatched:
        print(f"カタログにない2万円以上の商品が {len(unmatched)}件あります（reports/unmatched.json）")

    set_github_output("changed", "true" if changed else "false")
    if not any(s["ok"] for s in shops):
        sys.exit("すべての店舗で取得に失敗しました")


def fetch_shop(shop):
    try:
        offers = shop.fetch(Http())
    except Exception as e:  # 1店舗の失敗で全体を止めない
        return shop, None, f"{type(e).__name__}: {e}"
    if not offers:
        return shop, None, "商品を1件も読み取れませんでした（ページの構成が変わった可能性があります）"
    return shop, offers, None


def _unique(offers):
    seen = set()
    for o in offers:
        if (o["shop"], o["jan"]) not in seen:
            seen.add((o["shop"], o["jan"]))
            yield o


if __name__ == "__main__":
    main()
