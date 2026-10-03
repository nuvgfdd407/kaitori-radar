"""公開用のサイトを dist/ に組み立てる。

    python -m scraper.build

- public/ の中身（CSS・JavaScript・画像・価格データなど）をそのままコピーし、
  public/data/prices.json からHTMLのページとサイトマップを作る
- 作るページ: トップページ、ジャンル別ページ（/nintendo/ など）、機種別ページ（/switch2/ など）、
  商品ページ（/item/<JAN>/）
- ジャンル・シリーズの分け方は catalog/products.json から読む
- dist/ は毎回作り直す生成物なので、Git には入れない
"""
import hashlib
import json
import shutil
import sys
from datetime import date, datetime, timedelta, timezone

from . import history
from . import templates as t
from .common import CATALOG, PRICES, ROOT, SITE_URL, load_json

PUBLIC = ROOT / "public"
DIST = ROOT / "dist"
PREVIEW = 10  # トップページとジャンルのページで、シリーズごとに出す商品の数（全部出すと重いので）
JST = timezone(timedelta(hours=9))


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    data = load_json(PRICES)
    site = prepare(data, load_json(CATALOG))

    if DIST.exists():
        shutil.rmtree(DIST)
    shutil.copytree(PUBLIC, DIST)

    pages = [("/", list_page(site))]
    pages += [(c["href"], list_page(site, category=c)) for c in site["categories"] if c["own_page"]]
    pages += [(f"/{s['id']}/", list_page(site, series=s)) for s in site["series"]]
    pages += [(f"/item/{p['jan']}/", item_page(site, p)) for p in site["products"]]
    pages += [("/ranking/", ranking_page(site))]
    # 比較リストは人によって中身が違うので、検索結果に出さずサイトマップにも載せない
    private_pages = [("/cart/", cart_page(site))]
    for path, html in pages + private_pages:
        out = DIST / path.strip("/") / "index.html"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(html, encoding="utf-8")
    write_sitemap([path for path, _ in pages], data["updated_at"])
    write_search_index(site)
    print(f"{len(pages) + len(private_pages)}ページを dist/ に作りました")


def prepare(data, catalog):
    """テンプレートで使う値（最高値・差益・日時の表示など）を計算しておく。"""
    today = datetime.now(JST).date().isoformat()
    series = {s["id"]: s for s in catalog["series"]}
    categories = []
    for c in catalog["categories"]:
        members = [s for s in catalog["series"] if s["category"] == c["id"]]
        # シリーズが1つだけのジャンル（Xbox）は、ジャンルのページを作らずシリーズのページを使う
        own_page = len(members) > 1
        categories.append({**c, "series": members, "own_page": own_page,
                           "href": f"/{c['id']}/" if own_page else f"/{members[0]['id']}/"})
    category_of = {s["id"]: c for c in categories for s in c["series"]}
    # 価格データより後にカタログでシリーズを付け替えても、すぐに反映されるようにする
    series_of = {p["jan"]: p["series"] for p in catalog["products"]}
    data["products"] = [p for p in data["products"] if series_of.get(p["jan"]) in series]
    records = history.load(date.fromisoformat(today), t.HISTORY_DAYS)
    shops = data["shops"]
    for shop in shops:
        if not shop["ok"]:
            shop["failing_label"] = format_time(shop["failing_since"])
    for index, p in enumerate(data["products"]):
        prices = [(s, p["prices"][s["id"]]["price"]) for s in shops if s["id"] in p["prices"]]
        best = max((price for _, price in prices), default=None)
        p["index"] = index
        p["series"] = series_of[p["jan"]]
        p["series_name"] = series[p["series"]]["name"]
        p["category"] = category_of[p["series"]]
        p["best"] = best
        p["best_shops"] = [s for s, price in prices if price == best]
        # 発売前の買取価格は仮のことが多いので、差益は出さない
        p["released"] = not (p.get("release") and p["release"] > today)
        has_msrp = best and p.get("msrp") and p["released"]
        p["profit"] = best - p["msrp"] if has_msrp else None
        p["ratio"] = best / p["msrp"] if has_msrp else None
        p["history"] = [(day, prices[p["jan"]]) for day, prices in records if p["jan"] in prices]
        # 画像を差し替えたら URL も変わるようにして、ブラウザに古い画像を使い回させない
        src = (p.get("image") or {}).get("src", "")
        if src.startswith("/images/") and (PUBLIC / src.lstrip("/")).exists():
            p["image"] = {**p["image"], "src": versioned(src.lstrip("/"))}
        # 前日比: 今日より前で最後に記録がある日の最高値と比べる
        before = [max(prices.values()) for day, prices in p["history"] if day < today and prices]
        p["change"] = best - before[-1] if best and before else None
        # 値動きランキング用: 前日と今の両方に価格がある店舗だけで比べた最高値（店舗を足した日に順位が乱れないように）
        last = next(((day, prices) for day, prices in reversed(p["history"]) if day < today and prices), None)
        now = {s["id"]: price for s, price in prices}
        common = [sid for sid in now if last and sid in last[1]]
        p["move"] = (last[0], max(last[1][sid] for sid in common), max(now[sid] for sid in common)) if common else None
    # PSA 鑑定品はカタログの順が追加した順なので、標準の並びは最高値の高い順にする（買取が止まっているものは最後）
    psa = iter(sorted((p for p in data["products"] if p["series"].startswith("psa-")), key=lambda p: -(p["best"] or 0)))
    data["products"] = [next(psa) if p["series"].startswith("psa-") else p for p in data["products"]]
    for index, p in enumerate(data["products"]):
        p["index"] = index
    return {
        "shops": shops,
        "categories": categories,
        "series": catalog["series"],
        "products": data["products"],
        "updated": format_time(data["updated_at"]),
        "css": versioned("style.css"),
        "js": versioned("app.js"),
    }


def versioned(name):
    """中身が変わるとURLも変わるようにして、ブラウザに古いファイルを使い回させない。"""
    digest = hashlib.sha256((PUBLIC / name).read_bytes()).hexdigest()[:10]
    return f"/{name}?v={digest}"


def list_page(site, *, category=None, series=None):
    """トップページ（どちらも None）と、ジャンル別のページ、機種別のページ。"""
    if series:
        products = [p for p in site["products"] if p["series"] == series["id"]]
        shops = shops_for(site, products)
        n = shop_count(shops)
        path, active = f"/{series['id']}/", (category_of(site, series)["id"], series["id"])
        word = t.price_word(series["id"])
        title = f"{series['name']}の{word}比較【{n}店舗】｜{t.SITE_NAME}"
        heading = f"{series['name']}の{word}を{n}店舗で比較"
        lead = (f"{series['name']}の{len(products)}商品の"
                f"{'買取価格' if series['id'].startswith('psa-') else '新品（未開封）買取価格'}を、{n}店舗の最新の価格で比較しています。")
        top = next((p for p in products if p["best"]), None)
        if top:
            lead += f"{top['name']}の最高値は、{t.best_shop_names(top, full=True)}の{t.yen(top['best'])}です（{site['updated']}時点）。"
        description = f"{series['name']}の{word}を{n}店舗で比較。" + (
            f"{top['name']}は最高{t.yen(top['best'])}（{t.best_shop_names(top, full=True)}）。" if top else ""
        ) + "15分ごとに自動更新。"
    elif category:
        ids = [s["id"] for s in category["series"]]
        products = [p for p in site["products"] if p["series"] in ids]
        shops = shops_for(site, products)
        n = shop_count(shops)
        name = category.get("title", category["name"])
        names = "・".join(s["name"] for s in category["series"])
        path, active = category["href"], (category["id"], None)
        title = f"{name}の新品買取価格比較【{n}店舗】｜{t.SITE_NAME}"
        heading = f"{name}の新品買取価格を{n}店舗で比較"
        lead = f"{name}の{len(products)}商品の新品（未開封）買取価格を、{n}店舗の最新の価格で比較しています。"
        description = (f"{names}の新品買取価格を{n}店舗で比較。"
                       "いちばん高く売れるお店と、定価との差額がひと目でわかります。15分ごとに自動更新。")
    else:
        products = site["products"]
        shops = site["shops"]
        n = shop_count(shops)
        path, active = "/", ("all", None)
        title = f"{t.SITE_NAME}｜Switch 2・iPhone・ポケカなどの新品買取価格を比較"
        heading = f"ゲーム機・スマホ・トレカの新品買取価格を{n}店舗で比較"
        description = (
            "Nintendo Switch 2・PlayStation 5・Xbox・Steam Deckなどのゲーム機、iPhone・Google Pixel、"
            "ポケモンカード・ワンピースカードの未開封BOXの買取価格を買取店ごとに比較。"
            "いちばん高く売れるお店と、定価との差額がひと目でわかります。"
        )
        lead = f"ゲーム機・スマホ・トレカ、{len(products)}商品の新品（未開封）買取価格を、{n}店舗の最新の価格で比較しています。"

    # トップページだけ、値動きランキングの上位を少し見せる
    teaser = t.movers_teaser(movers(site)[0][:3]) if not (series or category) else ""
    content = f"""    <h1 class="page-title">{t.esc(heading)}</h1>
    <p class="lead">{t.esc(lead)}</p>
{teaser}
    <p class="count" data-total="{len(products)}">{len(products)}商品</p>
{t.price_table(site, products, shops, grouped=series is None, limit=None if series else PREVIEW,
                scope=[s["id"] for s in category["series"]] if category else None)}
    <ul class="search-results" id="search-results" hidden></ul>
    <p class="no-results" hidden>条件に合う商品はありません。</p>"""
    return t.page(site, path=path, title=title, description=description, active=active,
                  content=content, controls=t.SEARCH_CONTROL + t.SORT_CONTROL)


def write_search_index(site):
    """トップページなどの検索用の、全商品の索引（data/search.json）。
    一覧には各シリーズの先頭しか出していないので、検索欄に入力したときに app.js が読み込む。"""
    names = {s["id"]: s["name"] for s in site["series"]}
    items = [{"j": p["jan"], "n": p["name"], "g": p["series"], "gn": names.get(p["series"], ""),
              "s": t.search_text(p), "b": p["best"], "h": t.best_shop_names(p) if p["best"] else "",
              "i": (p.get("image") or {}).get("src", "") if str((p.get("image") or {}).get("src", "")).startswith("/images/") else ""}
             for p in site["products"]]
    (DIST / "data" / "search.json").write_text(json.dumps(items, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")


def shop_count(shops):
    """店舗の数。郵送と店頭で別々に載せている店舗（「トレカバンク(郵送)」「トレカバンク(店頭)」）は1店と数える。"""
    return len({s["name"].split("(")[0] for s in shops})


def category_of(site, series):
    return next(c for c in site["categories"] if c["id"] == series["category"])


def shops_for(site, products):
    """その商品を1つでも扱っている店舗（iPhone を扱わない店舗などは、表や店舗数から外す）。"""
    shops = [s for s in site["shops"] if any(s["id"] in p["prices"] for p in products)]
    return shops or site["shops"]


def item_page(site, p):
    series = next(s for s in site["series"] if s["id"] == p["series"])
    siblings = [q for q in site["products"] if q["series"] == p["series"]]
    shops = shops_for(site, siblings)
    n = shop_count(shops)
    if p["best"]:
        best = f"最高{t.yen(p['best'])}（{t.best_shop_names(p, full=True)}）"
        title = f"{p['name']}の買取価格比較｜{best}｜{t.SITE_NAME}"
        description = f"{p['name']}の{t.price_word(p['series'])}を{n}店舗で比較。{best}。{site['updated']}時点の価格です。"
    else:
        title = f"{p['name']}の買取価格比較｜{t.SITE_NAME}"
        description = f"{p['name']}の{t.price_word(p['series'])}を{n}店舗で比較しています。"
    return t.page(site, path=f"/item/{p['jan']}/", title=title, description=description, active=(p["category"]["id"], series["id"]),
                  content=t.item_content(site, p, series, siblings, shops),
                  breadcrumbs=t.item_breadcrumbs(series, p))


RANKING_SIZE = t.RANKING_SHOWN
RANKING_MIN_PRICE = 3000  # 前日の最高値がこれより安い商品は、少しの変動で率が大きく出るので外す


def movers(site):
    """前日と比べて、最高値が上がった・下がった商品（率の大きい順）。（商品, 前日の最高値, 今の最高値）の並び。"""
    moves = [(p, before, now) for p in site["products"] if p.get("move")
             for _, before, now in [p["move"]] if before >= RANKING_MIN_PRICE and now != before]
    ups = sorted((m for m in moves if m[2] > m[1]), key=lambda m: -m[2] / m[1])[:RANKING_SIZE]
    downs = sorted((m for m in moves if m[2] < m[1]), key=lambda m: m[2] / m[1])[:RANKING_SIZE]
    return ups, downs


def ranking_page(site):
    """前日と比べて、最高値が大きく上がった・下がった商品（率の大きい順）。"""
    ups, downs = movers(site)
    days = sorted({p["move"][0] for p in site["products"] if p.get("move")})
    since = f"{int(days[-1][5:7])}/{int(days[-1][8:])}" if days else "前日"
    title = f"買取価格の値上がり・値下がりランキング｜{t.SITE_NAME}"
    description = (f"ゲーム機・スマホ・トレカ・PSA鑑定品の買取価格が、前日（{since}）から大きく上がった商品・下がった商品のランキング。"
                   f"{site['updated']}時点。")
    return t.page(site, path="/ranking/", title=title, description=description, active=("ranking", None),
                  content=t.ranking_content(site, ups, downs, since, RANKING_MIN_PRICE))


def cart_page(site):
    return t.page(site, path="/cart/", title=f"比較リスト｜{t.SITE_NAME}",
                  description="選んだ商品を、どの買取店に売ると一番高くなるかを計算します。",
                  active=None, content=t.cart_content(), noindex=True, page_id="cart")


def write_sitemap(paths, updated_at):
    lastmod = updated_at[:10]
    urls = "".join(f"  <url><loc>{SITE_URL}{path}</loc><lastmod>{lastmod}</lastmod></url>\n" for path in paths)
    (DIST / "sitemap.xml").write_text(
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n' + urls + "</urlset>\n",
        encoding="utf-8",
    )


def format_time(iso):
    dt = datetime.fromisoformat(iso).astimezone(JST)
    return f"{dt.month}/{dt.day} {dt:%H:%M}"


if __name__ == "__main__":
    main()
