"""サイトのHTMLのひな形。scraper.build から使う。

表や商品ページはここでHTMLとして組み立てる（検索エンジンが JavaScript なしで内容を読めるように）。
ブラウザ側の app.js は、表の並び替えと、切れた画像の差し替えだけを行う。
"""
import json
from html import escape

from .common import SITE_URL

SITE_NAME = "買取レーダー"
SCHEDULE = "10:00〜21:00は15分ごとに確認"

FAVICON = (
    "data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 32 32'%3E"
    "%3Ccircle cx='16' cy='16' r='15' fill='%233b5bdb'/%3E"
    "%3Ccircle cx='16' cy='16' r='10' fill='none' stroke='%23fff' stroke-opacity='.45' stroke-width='1.5'/%3E"
    "%3Ccircle cx='16' cy='16' r='5' fill='none' stroke='%23fff' stroke-opacity='.45' stroke-width='1.5'/%3E"
    "%3Cpath d='M16 16V1a15 15 0 0 1 13 7.5z' fill='%23fff' fill-opacity='.3'/%3E"
    "%3Cpath d='M16 16 29 8.5' stroke='%23fff' stroke-width='2' stroke-linecap='round'/%3E"
    "%3Ccircle cx='22' cy='11' r='2.4' fill='%23ffd43b'/%3E%3C/svg%3E"
)

LOGO = """<svg class="logo-mark" viewBox="0 0 32 32" aria-hidden="true">
          <circle class="logo-bg" cx="16" cy="16" r="15"/>
          <circle class="logo-ring" cx="16" cy="16" r="10"/>
          <circle class="logo-ring" cx="16" cy="16" r="5"/>
          <path class="logo-sweep" d="M16 16V1a15 15 0 0 1 13 7.5z"/>
          <path class="logo-beam" d="M16 16 29 8.5"/>
          <circle class="logo-blip" cx="22" cy="11" r="2.4"/>
        </svg>"""

# Yahoo! のクレジット表記。利用条件なので、HTMLを変えずにページ下部に置く
YAHOO_CREDIT = """<!-- Begin Yahoo! JAPAN Web Services Attribution Snippet -->
        <span style="margin:15px 15px 15px 15px"><a href="https://developer.yahoo.co.jp/sitemap/">Webサービス by Yahoo! JAPAN</a></span>
        <!-- End Yahoo! JAPAN Web Services Attribution Snippet -->"""

NONE_CELL = '<td class="num none">—</td>'


# ---- 共通の外枠 ---------------------------------------------------------------

def page(site, *, path, title, description, active, content, controls="", breadcrumbs=None):
    """全ページ共通の外枠。

    site は build.py が用意する辞書（shops・series・updated・shop_count など）。
    active はシリーズの切り替えで強調するもの（"all" またはシリーズID）。
    """
    url = SITE_URL + path
    structured = _breadcrumb_json(breadcrumbs) if breadcrumbs else ""
    return f"""<!doctype html>
<html lang="ja">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <meta name="color-scheme" content="light dark">
  <title>{esc(title)}</title>
  <meta name="description" content="{esc(description)}">
  <link rel="canonical" href="{esc(url)}">
  <meta property="og:type" content="website">
  <meta property="og:site_name" content="{SITE_NAME}">
  <meta property="og:title" content="{esc(title)}">
  <meta property="og:description" content="{esc(description)}">
  <meta property="og:url" content="{esc(url)}">
  <meta property="og:image" content="{SITE_URL}/ogp.png">
  <meta property="og:image:width" content="1200">
  <meta property="og:image:height" content="630">
  <meta property="og:locale" content="ja_JP">
  <meta name="twitter:card" content="summary_large_image">
  <link rel="icon" href="{FAVICON}">
  <link rel="stylesheet" href="{site["css"]}">
  <script src="{site["js"]}" defer></script>{structured}
</head>
<body>
  <header class="site-header">
    <div class="inner">
      <p class="site-title"><a href="/">
        {LOGO}
        {SITE_NAME}
      </a></p>
      <p class="meta">
        <span class="updated">価格更新 {esc(site["updated"])}</span>
        <span>{SCHEDULE}</span>
      </p>
    </div>
  </header>

  <main class="inner">
{_alerts(site)}
    <div class="controls">
      <nav class="chips" aria-label="シリーズ">{_series_nav(site, active)}</nav>
      {controls}
    </div>
{content}
{_notes(site)}
  </main>

  <footer class="site-footer">
    <div class="inner">
      <p class="yahoo-credit">
        {YAHOO_CREDIT}
      </p>
      <p>© {SITE_NAME}</p>
    </div>
  </footer>
</body>
</html>
"""


def _series_nav(site, active):
    items = [("all", "すべて", "/")] + [(s["id"], s["name"], f"/{s['id']}/") for s in site["series"]]
    links = []
    for key, name, href in items:
        current = ' aria-current="page"' if key == active else ""
        links.append(f'<a class="chip" href="{href}"{current}>{esc(name)}</a>')
    return "".join(links)


def _alerts(site):
    return "".join(
        f'    <div class="alert" role="status">⚠ {esc(s["name"])}の価格を取得できていません'
        f'（{esc(s["failing_label"])}から）。前回取得した価格を表示しています。</div>\n'
        for s in site["shops"] if not s["ok"]
    )


def _notes(site):
    sources = "".join(f'<a href="{esc(s["url"])}" target="_blank" rel="noopener">{esc(s["name"])}</a>' for s in site["shops"])
    return f"""    <section class="notes" aria-labelledby="notes-title">
      <h2 id="notes-title">ご利用にあたって</h2>
      <ul>
        <li>各店舗の公式サイトに掲載されている、新品（未開封）の買取価格を自動で集めています。</li>
        <li>実際の買取価格は、申込の時点で各店舗が決めます。お申込みの前に、必ず各店舗のページで最新の価格と条件をご確認ください。</li>
        <li>定価はメーカー希望小売価格（税込）です。限定版など、現在の定価がない商品は「—」と表示しています。</li>
        <li>発売前の商品は、買取価格が仮のことが多いため、差益は表示していません。</li>
        <li>価格の確認は10:00〜21:00のあいだ15分ごとに行っています。価格をクリックすると、その店舗の商品ページが開きます。</li>
        <li>商品画像は、Yahoo!ショッピングに出品されている同じ商品（JANコードが一致するもの）の画像を表示しています。画像をクリックすると、その出品ページが開きます。</li>
      </ul>
      <p class="sources">出典: {sources}</p>
    </section>"""


def _breadcrumb_json(crumbs):
    items = [
        {"@type": "ListItem", "position": i, "name": name, "item": SITE_URL + path}
        for i, (name, path) in enumerate(crumbs, start=1)
    ]
    data = {"@context": "https://schema.org", "@type": "BreadcrumbList", "itemListElement": items}
    return f'\n  <script type="application/ld+json">{json.dumps(data, ensure_ascii=False)}</script>'


def breadcrumb_nav(crumbs):
    parts = []
    for i, (name, path) in enumerate(crumbs):
        last = i == len(crumbs) - 1
        parts.append(f'<span aria-current="page">{esc(name)}</span>' if last else f'<a href="{path}">{esc(name)}</a>')
    return '<nav class="breadcrumb" aria-label="パンくずリスト">' + " › ".join(parts) + "</nav>"


# ---- 比較表（トップページと機種別ページ） -------------------------------------

SORT_CONTROL = """<label class="sort">
        <span>並び順</span>
        <select id="sort">
          <option value="default">標準</option>
          <option value="best">最高買取が高い順</option>
          <option value="profit">差益が大きい順</option>
          <option value="ratio">定価比が高い順</option>
        </select>
      </label>"""


def price_table(site, products, *, grouped):
    shops = site["shops"]
    columns = 4 + len(shops)
    head = (
        '<tr><th scope="col" class="col-name">商品名</th><th scope="col">定価</th>'
        '<th scope="col">最高買取</th><th scope="col">差益</th>'
        + "".join(
            f'<th scope="col" title="{esc(s["name"])}"><a href="{esc(s["url"])}" target="_blank" rel="noopener">{esc(s["short"])}</a>'
            + ("" if s["ok"] else '<span class="warn-mark" aria-label="取得エラー">⚠</span>') + "</th>"
            for s in shops
        )
        + "</tr>"
    )
    if grouped:
        bodies = []
        for series in site["series"]:
            items = [p for p in products if p["series"] == series["id"]]
            if not items:
                continue
            bodies.append(
                f'<tbody><tr class="group"><th colspan="{columns}" scope="rowgroup">'
                f'<span><a href="/{series["id"]}/">{esc(series["name"])}</a></span></th></tr></tbody>'
            )
            bodies.append('<tbody class="rows">' + "".join(_row(p, shops) for p in items) + "</tbody>")
        body = "".join(bodies)
    else:
        body = '<tbody class="rows">' + "".join(_row(p, shops) for p in products) + "</tbody>"
    return f"""    <div class="table-wrap">
      <table class="price-table">
        <caption class="visually-hidden">ゲーム機本体の新品買取価格（店舗別）</caption>
        <thead>{head}</thead>
        {body}
      </table>
    </div>"""


def _row(p, shops):
    attrs = (
        f'data-index="{p["index"]}" data-best="{_num(p["best"])}" '
        f'data-profit="{_num(p["profit"])}" data-ratio="{_num(p["ratio"])}"'
    )
    sub = _sub_line(p)
    name = (
        f'<th scope="row" class="col-name"><div class="name-wrap">{thumb(p)}<div>'
        f'<a class="product" href="/item/{p["jan"]}/">{esc(p["name"])}</a>'
        + (f'<span class="sub">{sub}</span>' if sub else "")
        + "</div></div></th>"
    )
    msrp = f'<td class="num">{yen(p["msrp"])}</td>' if p.get("msrp") else NONE_CELL
    best = (
        f'<td class="num col-best">{yen(p["best"])}<span class="sub">{esc(best_shop_names(p))}</span></td>'
        if p["best"] else NONE_CELL
    )
    cells = "".join(_shop_cell(p, s) for s in shops)
    return f"<tr {attrs}>{name}{msrp}{best}{_profit_cell(p)}{cells}</tr>"


def _shop_cell(p, shop):
    offer = p["prices"].get(shop["id"])
    if not offer:
        return '<td class="num shop none" aria-label="取扱なし">—</td>'
    classes = ["num", "shop"]
    if offer["price"] == p["best"]:
        classes.append("is-best")
    if not shop["ok"]:
        classes.append("is-stale")
    title = f'{shop["name"]}で見る' if shop["ok"] else f'{shop["name"]}（前回取得時の価格）'
    return f'<td class="{" ".join(classes)}">{_link(offer.get("url"), yen(offer["price"]), title)}</td>'


def _profit_cell(p):
    if p["profit"] is None:
        return NONE_CELL
    cls = "pos" if p["profit"] > 0 else "neg" if p["profit"] < 0 else ""
    return f'<td class="num profit {cls}">{signed_yen(p["profit"])}<span class="sub">{signed_pct(p["ratio"])}</span></td>'


# ---- 商品ページ -----------------------------------------------------------------

def item_content(site, p, series, siblings):
    shops = site["shops"]
    offers = sorted(
        ((s, p["prices"][s["id"]]) for s in shops if s["id"] in p["prices"]),
        key=lambda so: -so[1]["price"],
    )
    missing = [s for s in shops if s["id"] not in p["prices"]]

    rows = []
    for shop, offer in offers:
        diff = offer["price"] - p["best"]
        diff_label = "最高値" if diff == 0 else signed_yen(diff)
        classes = " ".join(c for c in ["is-best" if diff == 0 else "", "is-stale" if not shop["ok"] else ""] if c)
        title = f'{shop["name"]}で見る' if shop["ok"] else f'{shop["name"]}（前回取得時の価格）'
        rows.append(
            f'<tr class="{classes}"><th scope="row">{esc(shop["name"])}</th>'
            f'<td class="num price">{_link(offer.get("url"), yen(offer["price"]), title)}</td>'
            f'<td class="num diff">{diff_label}</td></tr>'
        )
    for shop in missing:
        rows.append(f'<tr class="none"><th scope="row">{esc(shop["name"])}</th><td class="num">取扱なし</td><td></td></tr>')

    if p["best"]:
        summary = (
            f'最高値は<strong>{esc(best_shop_names(p, full=True))}</strong>の'
            f'<strong>{yen(p["best"])}</strong>です（{esc(site["updated"])}時点）。'
        )
    else:
        summary = "現在、この商品の新品買取価格を掲載している店舗はありません。"

    facts = [("最高買取", f'<span class="col-best">{yen(p["best"])}</span>' if p["best"] else "—")]
    facts.append(("定価", yen(p["msrp"]) if p.get("msrp") else "—"))
    if p["profit"] is not None:
        cls = "pos" if p["profit"] > 0 else "neg" if p["profit"] < 0 else ""
        facts.append(("差益", f'<span class="profit {cls}">{signed_yen(p["profit"])}（{signed_pct(p["ratio"])}）</span>'))
    facts_html = "".join(f"<div><dt>{name}</dt><dd>{value}</dd></div>" for name, value in facts)

    related = "".join(
        f'<li><a href="/item/{q["jan"]}/">{esc(q["name"])}</a>'
        f'<span class="related-price">{("最高 " + yen(q["best"])) if q["best"] else "取扱なし"}</span></li>'
        for q in siblings if q["jan"] != p["jan"]
    )
    sub = _sub_line(p)
    return f"""    {breadcrumb_nav(item_breadcrumbs(series, p))}
    <section class="item-summary">
      {thumb(p, large=True)}
      <div class="item-heading">
        <h1 class="page-title">{esc(p["name"])}の新品買取価格</h1>
        {f'<p class="sub">{sub}</p>' if sub else ""}
        <dl class="item-facts">{facts_html}</dl>
      </div>
    </section>
    <p class="lead">{summary}</p>

    <h2 class="section-title">店舗別の新品買取価格</h2>
    <div class="table-wrap table-wrap--auto">
      <table class="shop-table">
        <thead><tr><th scope="col">店舗</th><th scope="col">新品買取価格</th><th scope="col">最高値との差</th></tr></thead>
        <tbody>{"".join(rows)}</tbody>
      </table>
    </div>

    <h2 class="section-title">{esc(series["name"])}のほかの商品</h2>
    <ul class="related">{related}</ul>
    <p><a href="/{series["id"]}/">{esc(series["name"])}の新品買取価格を一覧で比較する</a></p>"""


def item_breadcrumbs(series, p):
    return [(SITE_NAME, "/"), (series["name"], f"/{series['id']}/"), (p["name"], f"/item/{p['jan']}/")]


# ---- 小さな部品 ------------------------------------------------------------------

def esc(s):
    return escape(str(s), quote=True)


def yen(n):
    return f"¥{n:,}"


def signed_yen(n):
    return ("+" if n > 0 else "−" if n < 0 else "±") + yen(abs(n))


def signed_pct(ratio):
    pct = round((ratio - 1) * 100)
    return ("+" if pct > 0 else "−" if pct < 0 else "±") + f"{abs(pct)}%"


def best_shop_names(p, full=False):
    return "・".join(s["name"] if full else s["short"] for s in p["best_shops"])


def thumb(p, large=False):
    """商品画像（Yahoo!ショッピングの出品の画像）。クリックすると、画像の出典の出品ページが開く。"""
    size = "thumb thumb--large" if large else "thumb"
    image = p.get("image") or {}
    src = image.get("src")
    if not _is_http(src):
        return f'<span class="{size} thumb-empty" aria-hidden="true"></span>'
    img = f'<img src="{esc(src)}" alt="" width="44" height="44" loading="lazy" decoding="async" referrerpolicy="no-referrer">'
    url = image.get("url")
    if not _is_http(url):
        return f'<span class="{size}">{img}</span>'
    title = "画像の出典: Yahoo!ショッピング" + (f'（{image["seller"]}）' if image.get("seller") else "")
    return (
        f'<a class="{size}" href="{esc(url)}" target="_blank" rel="noopener" title="{esc(title)}"'
        f' aria-label="{esc(p["name"])}の画像の出典（Yahoo!ショッピング）">{img}</a>'
    )


def _sub_line(p):
    parts = []
    if p.get("model"):
        parts.append(esc(p["model"]))
    if p.get("note"):
        parts.append(f'<span class="tag">{esc(p["note"])}</span>')
    if not p["released"]:
        month, day = int(p["release"][5:7]), int(p["release"][8:10])
        parts.append(f'<span class="tag">{month}/{day}発売</span>')
    return " ".join(parts)


def _link(url, label, title):
    if not _is_http(url):
        return label
    return f'<a href="{esc(url)}" target="_blank" rel="noopener" title="{esc(title)}">{label}</a>'


def _is_http(url):
    # 店舗サイトなどから取ってきたURLなので、http(s) 以外は使わない
    return isinstance(url, str) and url.startswith(("https://", "http://"))


def _num(value):
    if value is None:
        return ""
    return f"{value:.4f}" if isinstance(value, float) else str(value)
