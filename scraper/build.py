"""公開用のサイトを dist/ に組み立てる。

    python -m scraper.build

- public/ の中身（CSS・JavaScript・画像・価格データなど）をそのままコピーし、
  public/data/prices.json からHTMLのページとサイトマップを作る
- 作るページ: トップページ、機種別ページ（/switch2/ など）、商品ページ（/item/<JAN>/）
- dist/ は毎回作り直す生成物なので、Git には入れない
"""
import hashlib
import shutil
import sys
from datetime import datetime, timedelta, timezone

from . import templates as t
from .common import PRICES, ROOT, SITE_URL, load_json

PUBLIC = ROOT / "public"
DIST = ROOT / "dist"
JST = timezone(timedelta(hours=9))


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    data = load_json(PRICES)
    site = prepare(data)

    if DIST.exists():
        shutil.rmtree(DIST)
    shutil.copytree(PUBLIC, DIST)

    pages = [("/", list_page(site, None))]
    pages += [(f"/{s['id']}/", list_page(site, s)) for s in site["series"]]
    pages += [(f"/item/{p['jan']}/", item_page(site, p)) for p in site["products"]]
    # 比較リストは人によって中身が違うので、検索結果に出さずサイトマップにも載せない
    private_pages = [("/cart/", cart_page(site))]
    for path, html in pages + private_pages:
        out = DIST / path.strip("/") / "index.html"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(html, encoding="utf-8")
    write_sitemap([path for path, _ in pages], data["updated_at"])
    print(f"{len(pages) + len(private_pages)}ページを dist/ に作りました")


def prepare(data):
    """テンプレートで使う値（最高値・差益・日時の表示など）を計算しておく。"""
    today = datetime.now(JST).date().isoformat()
    shops = data["shops"]
    for shop in shops:
        if not shop["ok"]:
            shop["failing_label"] = format_time(shop["failing_since"])
    for index, p in enumerate(data["products"]):
        prices = [(s, p["prices"][s["id"]]["price"]) for s in shops if s["id"] in p["prices"]]
        best = max((price for _, price in prices), default=None)
        p["index"] = index
        p["best"] = best
        p["best_shops"] = [s for s, price in prices if price == best]
        # 発売前の買取価格は仮のことが多いので、差益は出さない
        p["released"] = not (p.get("release") and p["release"] > today)
        has_msrp = best and p.get("msrp") and p["released"]
        p["profit"] = best - p["msrp"] if has_msrp else None
        p["ratio"] = best / p["msrp"] if has_msrp else None
    return {
        "shops": shops,
        "series": data["series"],
        "products": data["products"],
        "updated": format_time(data["updated_at"]),
        "shop_count": len(shops),
        "css": versioned("style.css"),
        "js": versioned("app.js"),
    }


def versioned(name):
    """中身が変わるとURLも変わるようにして、ブラウザに古いファイルを使い回させない。"""
    digest = hashlib.sha256((PUBLIC / name).read_bytes()).hexdigest()[:10]
    return f"/{name}?v={digest}"


def list_page(site, series):
    """トップページ（series が None）と機種別ページ。"""
    n = site["shop_count"]
    if series is None:
        products = site["products"]
        path, active = "/", "all"
        title = f"{t.SITE_NAME}｜Switch 2・PS5・Xboxの新品買取価格を比較"
        heading = f"Switch 2・PS5・Xboxの新品買取価格を{n}店舗で比較"
        description = (
            "Nintendo Switch 2・PlayStation 5・Xbox Series X|Sの新品買取価格を買取店ごとに比較。"
            "いちばん高く売れるお店と、定価との差額がひと目でわかります。"
        )
        lead = f"ゲーム機本体{len(products)}商品の新品（未開封）買取価格を、{n}店舗の最新の価格で比較しています。"
    else:
        products = [p for p in site["products"] if p["series"] == series["id"]]
        path, active = f"/{series['id']}/", series["id"]
        title = f"{series['name']}の新品買取価格比較【{n}店舗】｜{t.SITE_NAME}"
        heading = f"{series['name']}の新品買取価格を{n}店舗で比較"
        lead = f"{series['name']}の本体{len(products)}商品の新品（未開封）買取価格を、{n}店舗の最新の価格で比較しています。"
        top = next((p for p in products if p["best"]), None)
        if top:
            lead += f"{top['name']}の最高値は、{t.best_shop_names(top, full=True)}の{t.yen(top['best'])}です（{site['updated']}時点）。"
        description = f"{series['name']}の本体の新品買取価格を{n}店舗で比較。" + (
            f"{top['name']}は最高{t.yen(top['best'])}（{t.best_shop_names(top, full=True)}）。" if top else ""
        ) + "15分ごとに自動更新。"

    content = f"""    <h1 class="page-title">{t.esc(heading)}</h1>
    <p class="lead">{t.esc(lead)}</p>
    <p class="count">{len(products)}商品</p>
{t.price_table(site, products, grouped=series is None)}"""
    return t.page(site, path=path, title=title, description=description, active=active,
                  content=content, controls=t.SORT_CONTROL)


def item_page(site, p):
    series = next(s for s in site["series"] if s["id"] == p["series"])
    siblings = [q for q in site["products"] if q["series"] == p["series"]]
    n = site["shop_count"]
    if p["best"]:
        best = f"最高{t.yen(p['best'])}（{t.best_shop_names(p, full=True)}）"
        title = f"{p['name']}の買取価格比較｜{best}｜{t.SITE_NAME}"
        description = f"{p['name']}の新品買取価格を{n}店舗で比較。{best}。{site['updated']}時点の価格です。"
    else:
        title = f"{p['name']}の買取価格比較｜{t.SITE_NAME}"
        description = f"{p['name']}の新品買取価格を{n}店舗で比較しています。"
    return t.page(site, path=f"/item/{p['jan']}/", title=title, description=description, active=series["id"],
                  content=t.item_content(site, p, series, siblings),
                  breadcrumbs=t.item_breadcrumbs(series, p))


def cart_page(site):
    return t.page(site, path="/cart/", title=f"比較リスト｜{t.SITE_NAME}",
                  description="選んだゲーム機を、どの買取店に売ると一番高くなるかを計算します。",
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
