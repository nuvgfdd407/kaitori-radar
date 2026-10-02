"""各店舗の買取価格を取得して public/data/prices.json を更新する。

    python -m scraper.update

- 店舗ごとに並行して取得する。失敗した店舗は前回の価格を残し、取得エラーとして記録する
- 価格や取得状況が前回と同じなら prices.json は書き換えない
  （GitHub Actions で変化があったときだけコミットするため）
- カタログにない高額商品は reports/unmatched.json に書き出す（新しい本体の登録漏れに気づくため）
- 商品画像は scraper.images が作った catalog/images.json から載せる
- 日ごとの価格の記録（data/history/）も更新する（scraper.history を参照）
- スマホ（iPhone・Android）は「機種＋容量（Android はキャリアも）」（scraper.phones.phone_key）と色で突き合わせる。
  店舗の色の書き方は scraper.phones.phone_color で公式の色名にそろえる。色の区別がない店舗の価格は、全色に当てはめる。
  容量を書かない店舗の商品は、その機種（とキャリア）の容量が1種類だけなら、その容量の商品に当てはめる
- JAN を載せていない店舗のトレカは、カタログの "names"（セット名）と商品名（scraper.cards.card_key）で突き合わせる
- iPad・Apple Watch・AirPods は JAN か Apple の型番（"codes"）で突き合わせる。カタログの "aliases" に、
  その商品の JAN と型番（Apple Watch はバンド違いの分もすべて）を書いておく
"""
import sys
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone

from . import history
from .common import CATALOG, IMAGES, ROOT, load_json, set_github_output, warn, write_json
from .cards import card_key
from .http import INTERVAL, Http
from .phones import color_part, phone_color, phone_key, without_capacity
from .shops import SHOPS

OUTPUT = ROOT / "public" / "data" / "prices.json"
UNMATCHED = ROOT / "reports" / "unmatched.json"

JST = timezone(timedelta(hours=9))
# カタログにない商品のうち、この金額以上のものは本体の可能性があるので報告する
REPORT_MIN_PRICE = 20000
# カタログの項目のうち、公開するデータには載せないもの（画像選びの設定、別のJAN、突き合わせ用の名前）
# 機種＋容量＋色で突き合わせるスマホのジャンル
PHONE_CATEGORIES = ("apple", "android")
INTERNAL_KEYS = {"image_item", "image_from", "image_url", "image_page", "aliases", "names"}


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    catalog = load_json(CATALOG)
    images = load_json(IMAGES) if IMAGES.exists() else {}
    # 同じ商品が別のJAN（新旧のJANなど）で載っていることがあるので、"aliases" のJANも同じ商品として扱う
    owner = {jan: p["jan"] for p in catalog["products"] for jan in [p["jan"], *p.get("aliases", [])]}
    # スマホ: {"iPhone 17 Pro 256GB": {"シルバー": JAN, ...}}
    phone_series = {s["id"] for s in catalog["series"] if s["category"] in PHONE_CATEGORIES}
    by_color = {}
    for p in catalog["products"]:
        key = phone_key(p["name"]) if p["series"] in phone_series else None
        if key:  # iPad・Apple Watch・AirPods は JAN・型番で突き合わせるので、ここには入れない
            by_color.setdefault(key, {})[phone_color(key, color_part(p["name"]))] = p["jan"]
    # 容量を書かない店舗用: {"Galaxy A25 docomo": {色: JAN}}（容量が1種類だけの機種のみ）
    capacities = {}
    for key in by_color:
        capacities.setdefault(without_capacity(key), []).append(key)
    by_color.update({short: by_color[keys[0]] for short, keys in capacities.items()
                     if len(keys) == 1 and short != keys[0]})
    by_key = {card_key(name): p["jan"] for p in catalog["products"] for name in p.get("names", [])}
    by_key.pop(None, None)  # 名前から読み取れなかった商品が、互いに一致しないように
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
                targets = _phone_targets(offer, by_color.get(offer.get("key")))
                if not targets:  # スマホでない商品と、色を読み取れなかったスマホ（JANがあればJANで探す）
                    target = owner.get(jan) or by_key.get(offer.get("key"))
                    targets = {target: offer["price"]} if target else {}
                if not targets and offer.get("codes"):
                    # Apple の型番（{型番: 価格}）。1行に何色分も書かれていれば、それぞれの商品に当てはめる
                    targets = {owner[code]: price for code, price in offer["codes"].items() if code in owner}
                for target, price in targets.items():
                    # 同じ商品が複数回（ページ内の重複・別のJAN）載っていたら、高い方を使う
                    current = found.get(target)
                    if current is None or price > current["price"]:
                        # 店舗の条件（「Apple Store の購入証明が必要」など）があれば、価格と一緒に載せる
                        found[target] = {"price": price, "url": offer["url"],
                                         **({"note": offer["note"]} if offer.get("note") else {})}
                if not targets and jan not in ignored and offer["price"] >= REPORT_MIN_PRICE:
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

    # ジャンル・シリーズの分け方はカタログから直接読む（scraper.build）ので、ここには入れない
    data = {
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
    # その日の最初の実行では、価格が変わっていなくても記録のファイルができる（グラフに今日の点が増える）
    if history.record({"shops": shops, **data}, now[:10]):
        changed = True
        print("価格の記録（data/history/）を更新しました")

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
        # robots.txt でアクセス間隔（Crawl-delay）を指定している店舗は、その間隔にする
        offers = shop.fetch(Http(getattr(shop, "INTERVAL", INTERVAL)))
    except Exception as e:  # 1店舗の失敗で全体を止めない
        return shop, None, f"{type(e).__name__}: {e}"
    if not offers:
        return shop, None, "商品を1件も読み取れませんでした（ページの構成が変わった可能性があります）"
    return shop, offers, None


def _phone_targets(offer, colors):
    """スマホの出品を、色ごとの商品の {JAN: 価格} にする。スマホでなければ None。

    colors はその機種＋容量の {色: JAN}。出品の "colors" は {色: 価格} で、
    "colors" がない出品（色の区別がない店舗）は全色に同じ価格を当てはめる。
    """
    if not colors:
        return None
    prices = offer["colors"] if "colors" in offer else dict.fromkeys(colors, offer["price"])
    return {colors[color]: price for color, price in prices.items() if color in colors and price}


def _unique(offers):
    """同じ商品（iPhone は色違いも同じとみなす）は1件だけにする。"""
    seen = set()
    for o in offers:
        key = (o["shop"], o.get("key") or o["jan"] or o["name"])
        if key not in seen:
            seen.add(key)
            yield o


if __name__ == "__main__":
    main()
