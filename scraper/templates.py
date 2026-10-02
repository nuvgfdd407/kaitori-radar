"""サイトのHTMLのひな形。scraper.build から使う。

表や商品ページはここでHTMLとして組み立てる（検索エンジンが JavaScript なしで内容を読めるように）。
ブラウザ側の app.js は、表の並び替えと、切れた画像の差し替えだけを行う。
"""
import json
import math
import re
from datetime import date, timedelta
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


# スマホは機種＋容量（Android はキャリアも）＋色ごとに載せている（scraper.phones を参照）
PHONE_NOTE = (
    "スマホは新品未開封の価格を、色ごとに載せています。iPhone・PixelはSIMフリー版、"
    "Galaxy・Xperia・AQUOSはSIMフリー版とキャリア版（docomo・au・SoftBank・楽天モバイル・Y!mobile）を別々に載せています"
    "（UQ mobile版はau版に含めています）。色を区別していない店舗の価格は、すべての色に同じ価格を表示しています。"
)


# ---- 共通の外枠 ---------------------------------------------------------------

def page(site, *, path, title, description, active, content, controls="", breadcrumbs=None,
         noindex=False, page_id=""):
    """全ページ共通の外枠。

    site は build.py が用意する辞書（shops・series・products・updated など）。
    active は切り替えボタンで強調するもの（(ジャンルID または "all", シリーズID または None)）。
    noindex は検索結果に出さないページ（比較リストなど、人ごとに中身が違うページ）。
    """
    url = SITE_URL + path
    structured = _breadcrumb_json(breadcrumbs) if breadcrumbs else ""
    robots = '\n  <meta name="robots" content="noindex">' if noindex else ""
    body_attr = f' data-page="{page_id}"' if page_id else ""
    return f"""<!doctype html>
<html lang="ja">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <meta name="color-scheme" content="light dark">
  <title>{esc(title)}</title>
  <meta name="description" content="{esc(description)}">{robots}
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
<body{body_attr}>
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
      {_nav(site, active, path)}
      {controls}
    </div>
    <div id="content">
{content}
    </div>
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


def _nav(site, active, path):
    """上の段はジャンル、下の段は選んでいるジャンルの中のシリーズ（シリーズが2つ以上あるときだけ）。"""
    category_id, series_id = active or (None, None)
    top = [("all", "すべて", "/")] + [(c["id"], c["name"], c["href"]) for c in site["categories"]]
    html = f'<nav class="chips" aria-label="ジャンル">{_chips(top, category_id, path)}</nav>'
    category = next((c for c in site["categories"] if c["id"] == category_id), None)
    if category and category["own_page"]:
        sub = [(s["id"], s["name"], f"/{s['id']}/") for s in category["series"]]
        html += f'<nav class="chips chips--sub" aria-label="シリーズ">{_chips(sub, series_id, path)}</nav>'
    return f'<div class="nav">{html}</div>'


def _chips(items, active, path):
    links = []
    for key, name, href in items:
        # 商品ページなど、今いるページの上の階層にあたるボタンは aria-current="true"
        current = f' aria-current="{"page" if href == path else "true"}"' if key == active else ""
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
        <li>定価は、メーカー希望小売価格またはメーカー公式ストアの販売価格（税込）です。販売終了した商品は、販売していたときの最後の価格です。限定版など、定価を決めにくい商品は「—」と表示しています。スマホのキャリア版は、各キャリアのオンラインショップの販売価格（割引なし）です。</li>
        <li>{PHONE_NOTE}</li>
        <li>PSA鑑定品は、PSA10 のシングルカードの買取価格です。カード名とカード番号で同じカードかどうかを判断しています。定価がないので差益は出していません。</li>
        <li>トレカ（ポケモンカード・ワンピースカード・遊戯王・フュージョンワールド）は、シュリンク付き・未開封のBOX（ポケモンカードは特別なセットも）の買取価格です。</li>
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


# 一覧の絞り込み（動かすのは app.js。JavaScript が使えないときは表示しない）
SEARCH_CONTROL = """<label class="search">
        <span class="visually-hidden">商品を検索</span>
        <input type="search" id="search" placeholder="商品名・型番で絞り込み" autocomplete="off" enterkeyhint="search">
      </label>"""

# 検索で、英語の名前をカナ（ひらがなでも）で打っても見つかるようにする読み。
# 商品名の英単語を読みに置き換えた文字を検索用に足す（「あいふぉん17ぷろ」のようにつなげて打っても当たる）。
# 読みが2通りあるものは、2つめの読みでも置き換えた文字を足す
READINGS = [
    ("Nintendo", ["ニンテンドー"]), ("Switch", ["スイッチ"]), ("Lite", ["ライト"]),
    ("PlayStation", ["プレイステーション", "プレステ"]), ("Portal", ["ポータル"]), ("VR2", ["ブイアール2"]),
    ("iPhone", ["アイフォン", "アイフォーン"]), ("Pro", ["プロ"]), ("Max", ["マックス"]), ("Plus", ["プラス"]),
    ("Air", ["エアー"]), ("Duo", ["デュオ"]),
    ("Pixel", ["ピクセル"]), ("Fold", ["フォールド"]), ("XL", ["エックスエル"]),
    ("iPad", ["アイパッド"]), ("mini", ["ミニ"]), ("Watch", ["ウォッチ"]), ("AirPods", ["エアーポッズ", "エアポッズ"]),
    ("Cellular", ["セルラー"]), ("Wi-Fi", ["ワイファイ"]),
    ("Galaxy", ["ギャラクシー"]), ("Flip", ["フリップ"]), ("Xperia", ["エクスペリア"]), ("AQUOS", ["アクオス"]),
    ("sense", ["センス"]), ("wish", ["ウィッシュ"]), ("SIM", ["シム"]), ("docomo", ["ドコモ"]),
    ("au", ["エーユー"]), ("SoftBank", ["ソフトバンク"]), ("Y!mobile", ["ワイモバイル"]),
    ("Xbox", ["エックスボックス"]), ("Series", ["シリーズ"]), ("Steam", ["スチーム"]), ("Deck", ["デッキ"]),
    ("Machine", ["マシン"]), ("Frame", ["フレーム"]), ("Controller", ["コントローラー"]),
    ("ROG", ["ログ", "アールオージー"]), ("Ally", ["アライ"]), ("Legion", ["レギオン"]), ("Go", ["ゴー"]),
    ("Meta", ["メタ"]), ("Quest", ["クエスト"]), ("PICO", ["ピコ"]), ("Ultra", ["ウルトラ"]),
    ("Pokémon", ["ポケモン"]), ("BOX", ["ボックス"]),
]
# ジャンルの呼び方（検索用）
CATEGORY_ALIASES = {"apple": "アップル", "android": "アンドロイド", "tcg": "トレーディングカード"}
# シリーズの呼び方（検索用）
SERIES_ALIASES = {
    "pokemon": "ポケカ", "onepiece": "ワンピ ワンピカ", "ps5": "プレステ5 PS5",
    "pixel11": "Google グーグル", "pixel10": "Google グーグル", "pixel9": "Google グーグル",
    "yugioh": "ユウギオウ 遊戯王OCG", "fusionworld": "ドラゴンボール ドラゴンボールスーパーカードゲーム FW",
}


def search_text(p):
    """一覧の行の検索用の文字（商品名・型番・シリーズ名と、英語の名前の読み）。"""
    readings = []
    for i in range(2):
        text = p["name"]
        for word, kana in READINGS:
            text = re.sub(rf"(?<![A-Za-z]){re.escape(word)}(?![A-Za-z])", kana[min(i, len(kana) - 1)], text,
                          flags=re.IGNORECASE)
        if text != p["name"] and text not in readings:
            readings.append(text)
    parts = [p["name"], p.get("model"), p.get("series_name"), p["category"]["name"],
             CATEGORY_ALIASES.get(p["category"]["id"]), *readings, SERIES_ALIASES.get(p["series"])]
    return " ".join(part for part in parts if part)


SORT_CONTROL = """<label class="sort">
        <span>並び順</span>
        <select id="sort">
          <option value="default">標準</option>
          <option value="best">最高買取が高い順</option>
          <option value="profit">差益が大きい順</option>
          <option value="ratio">定価比が高い順</option>
        </select>
      </label>"""


def price_table(site, products, shops, *, grouped):
    """一覧（定価・最高買取・差益だけを並べ、タップで店舗ごとの価格を開く）。

    店舗が増えても横に広がらないように、店舗ごとの価格は行を開いたときだけ出す。
    行は <details> なので、JavaScript がなくても開ける。並び替えと絞り込みは app.js。
    """
    head = ('<div class="list-head" aria-hidden="true"><span>商品名</span><span class="num">定価</span>'
            '<span class="num">最高買取</span><span class="num">差益</span><span></span></div>')
    if grouped:
        groups = []
        for series in site["series"]:
            items = [p for p in products if p["series"] == series["id"]]
            if items:
                groups.append(
                    f'<section class="list-group"><h2 class="group-title"><a href="/{series["id"]}/">'
                    f'{esc(series["name"])}</a></h2><div class="rows">{"".join(_row(p, shops) for p in items)}</div></section>'
                )
        body = "".join(groups)
    else:
        body = f'<div class="rows">{"".join(_row(p, shops) for p in products)}</div>'
    return f"""    <div class="price-list">
      {head}
      {body}
    </div>"""


def _row(p, shops):
    attrs = (
        f'data-search="{esc(search_text(p))}" '
        f'data-index="{p["index"]}" data-best="{_num(p["best"])}" '
        f'data-profit="{_num(p["profit"])}" data-ratio="{_num(p["ratio"])}"'
    )
    sub = _sub_line(p)
    name = (
        f'<div class="name-wrap">{thumb(p)}<div class="name-text">'
        f'<a class="product" href="/item/{p["jan"]}/">{esc(p["name"])}</a>'
        + (f'<span class="sub">{sub}</span>' if sub else "")
        + f"</div>{add_button(p)}</div>"
    )
    msrp = f'<div class="num col-msrp">{yen(p["msrp"])}</div>' if p.get("msrp") else '<div class="num none">—</div>'
    best = (
        f'<div class="num col-best">{yen(p["best"])}<span class="sub">{esc(best_shop_names(p))}</span></div>'
        if p["best"] else '<div class="num none">—</div>'
    )
    return (
        f'<details class="item" {attrs}><summary class="item-main">{name}{msrp}{best}{_profit_cell(p)}'
        f'<span class="chevron" aria-hidden="true"></span></summary>{_shop_prices(p, shops)}</details>'
    )


def _shop_prices(p, shops):
    """行を開いたときに出す、店舗ごとの価格（高い順）。"""
    offers = sorted(((s, p["prices"][s["id"]]) for s in shops if s["id"] in p["prices"]),
                    key=lambda so: -so[1]["price"])
    items = []
    for shop, offer in offers:
        best = offer["price"] == p["best"]
        diff = "最高値" if best else signed_yen(offer["price"] - p["best"])
        title = f'{shop["name"]}で見る' if shop["ok"] else f'{shop["name"]}（前回取得時の価格）'
        classes = " ".join(c for c in ["is-best" if best else "", "is-stale" if not shop["ok"] else ""] if c)
        items.append(
            f'<li class="{classes}"><span class="shop-name">{esc(shop["name"])}{_offer_note(offer)}</span>'
            f'<span class="shop-price">{_link(offer.get("url"), yen(offer["price"]), title)}</span>'
            f'<span class="shop-diff">{diff}</span></li>'
        )
    if not items:
        items.append('<li class="none">現在、買取価格を掲載している店舗はありません。</li>')
    return (
        f'<div class="item-shops"><ul class="shop-prices">{"".join(items)}</ul>'
        f'<a class="item-more" href="/item/{p["jan"]}/">価格の推移・商品の詳細 →</a></div>'
    )


def _offer_note(offer):
    """店舗の買取条件の注記（例: Apple Store の購入証明が必要）。"""
    return f'<small class="shop-note">※{esc(offer["note"])}</small>' if offer.get("note") else ""


def _profit_cell(p):
    if p["profit"] is None:
        return '<div class="num none">—</div>'
    cls = "pos" if p["profit"] > 0 else "neg" if p["profit"] < 0 else ""
    return f'<div class="num profit {cls}">{signed_yen(p["profit"])}<span class="sub">{signed_pct(p["ratio"])}</span></div>'


# ---- 商品ページ -----------------------------------------------------------------

def item_content(site, p, series, siblings, shops):
    word = price_word(series["id"])
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
            f'<tr class="{classes}"><th scope="row">{esc(shop["name"])}{_offer_note(offer)}</th>'
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
        summary = f"現在、この商品の{word}を掲載している店舗はありません。"
    if is_phone(p):
        summary += PHONE_NOTE

    facts = [("最高買取", f'<span class="col-best">{yen(p["best"])}</span>' if p["best"] else "—")]
    facts.append(("定価", yen(p["msrp"]) if p.get("msrp") else "—"))
    if p.get("change") is not None:
        cls = "pos" if p["change"] > 0 else "neg" if p["change"] < 0 else ""
        facts.append(("前日比", f'<span class="profit {cls}">{signed_yen(p["change"])}</span>'))
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
        <h1 class="page-title">{esc(p["name"])}の{word}</h1>
        {f'<p class="sub">{sub}</p>' if sub else ""}
        <dl class="item-facts">{facts_html}</dl>
        {add_button(p, label=True)}
      </div>
    </section>
    <p class="lead">{summary}</p>

    <h2 class="section-title">店舗別の{word}</h2>
    <div class="table-wrap table-wrap--auto">
      <table class="shop-table">
        <thead><tr><th scope="col">店舗</th><th scope="col">{word}</th><th scope="col">最高値との差</th></tr></thead>
        <tbody>{"".join(rows)}</tbody>
      </table>
    </div>

    <h2 class="section-title">買取価格の推移（最近{HISTORY_DAYS}日）</h2>
{price_history(site, p, shops)}

    <h2 class="section-title">{esc(series["name"])}のほかの商品</h2>
    <ul class="related">{related}</ul>
    <p><a href="/{series["id"]}/">{esc(series["name"])}の{word}を一覧で比較する</a></p>"""


def price_word(series_id):
    """見出しなどに使う言葉。PSA 鑑定品は新品ではないので「買取価格」にする。"""
    return "買取価格" if series_id.startswith("psa-") else "新品買取価格"


def is_phone(p):
    return p["series"].startswith(("iphone", "pixel", "galaxy", "xperia", "aquos"))


def item_breadcrumbs(series, p):
    category = p["category"]
    crumbs = [(SITE_NAME, "/")]
    if category["own_page"]:
        crumbs.append((category.get("title", category["name"]), category["href"]))
    return crumbs + [(series["name"], f"/{series['id']}/"), (p["name"], f"/item/{p['jan']}/")]


# ---- 価格の推移（商品ページ） ---------------------------------------------------

HISTORY_DAYS = 30  # 商品ページのグラフに出す日数
CHART_W, CHART_H = 560, 240
CHART_LEFT, CHART_RIGHT, CHART_TOP, CHART_BOTTOM = 84, 8, 12, 28


def price_history(site, p, shops):
    """店舗ごとの買取価格の推移のグラフ（SVG）と、日ごとの最高値の表。

    p["history"] は build.py が用意する [(日付の文字列, {店舗ID: 価格})]（古い順）。
    線の色は店舗ごとに固定（全店舗の並び順で style.css の .c0〜.c6 を使う）。
    """
    history = p["history"]
    if len(history) < 2:
        return ('    <p class="chart-note">価格の記録を始めたばかりです。'
                '2日分以上の記録がたまると、ここに店舗ごとの推移のグラフを表示します。</p>')
    color = {s["id"]: i for i, s in enumerate(site["shops"])}
    first = date.fromisoformat(history[0][0])
    span = max((date.fromisoformat(history[-1][0]) - first).days, 1)
    lines = []
    for shop in shops:
        points = [((date.fromisoformat(day) - first).days, prices[shop["id"]])
                  for day, prices in history if shop["id"] in prices]
        if points:
            lines.append((shop, points))
    if not lines:
        return '    <p class="chart-note">この期間に、この商品の買取価格を掲載していた店舗はありません。</p>'

    ticks = _nice_ticks(min(v for _, pts in lines for _, v in pts), max(v for _, pts in lines for _, v in pts))
    low, high = ticks[0], ticks[-1]
    plot_w, plot_h = CHART_W - CHART_LEFT - CHART_RIGHT, CHART_H - CHART_TOP - CHART_BOTTOM

    def x(offset):
        return round(CHART_LEFT + offset / span * plot_w, 1)

    def y(value):
        return round(CHART_TOP + (high - value) / (high - low) * plot_h, 1)

    grid = "".join(
        f'<line x1="{CHART_LEFT}" x2="{CHART_W - CHART_RIGHT}" y1="{y(v)}" y2="{y(v)}"/>'
        f'<text x="{CHART_LEFT - 6}" y="{y(v) + 4}" text-anchor="end">{yen(v)}</text>'
        for v in ticks
    )
    label_days = sorted({round(i * span / 4) for i in range(5)}) if span >= 4 else range(span + 1)
    # 両端の日付は、はみ出さないように内側に寄せる
    anchors = {0: "start", span: "end"}
    grid += "".join(
        f'<text x="{x(d)}" y="{CHART_H - 6}" text-anchor="{anchors.get(d, "middle")}">'
        f'{_month_day(first + timedelta(days=d))}</text>'
        for d in label_days
    )
    paths = "".join(
        f'<g class="c{color[shop["id"]]}"><title>{esc(shop["name"])}</title>'
        f'<polyline class="line" points="{" ".join(f"{x(d)},{y(v)}" for d, v in points)}"/>'
        + "".join(f'<circle class="dot" cx="{x(d)}" cy="{y(v)}" r="2.5"/>' for d, v in points)
        + "</g>"
        for shop, points in lines
    )
    latest = sorted(lines, key=lambda line: -line[1][-1][1])
    legend = "".join(
        f'<li><span class="swatch c{color[shop["id"]]}" aria-hidden="true"></span>{esc(shop["short"])}'
        f' <span class="legend-price">{yen(points[-1][1])}</span></li>'
        for shop, points in latest
    )
    period = f"{_month_day(first)}〜{_month_day(date.fromisoformat(history[-1][0]))}"
    rows = []
    for day, prices in reversed(history):
        shown = {s["short"]: prices[s["id"]] for s in shops if s["id"] in prices}
        if not shown:
            continue
        best = max(shown.values())
        names = "・".join(name for name, price in shown.items() if price == best)
        rows.append(f'<tr><th scope="row">{_month_day(date.fromisoformat(day))}</th>'
                    f'<td class="num">{yen(best)}</td><td>{esc(names)}</td></tr>')
    return f"""    <figure class="chart-wrap">
      <svg class="chart" viewBox="0 0 {CHART_W} {CHART_H}" role="img" aria-label="{esc(p["name"])}の店舗別の買取価格の推移（{period}）">
        <g class="grid">{grid}</g>{paths}
      </svg>
      <figcaption><ul class="chart-legend">{legend}</ul></figcaption>
    </figure>
    <details class="history-table">
      <summary>日ごとの最高値を表で見る</summary>
      <div class="table-wrap table-wrap--auto">
        <table class="shop-table">
          <thead><tr><th scope="col">日付</th><th scope="col">最高買取</th><th scope="col">店舗</th></tr></thead>
          <tbody>{"".join(rows)}</tbody>
        </table>
      </div>
    </details>"""


def _nice_ticks(low, high, count=4):
    """グラフの縦軸の目盛り（きりのいい金額）。"""
    if low == high:
        low, high = low - max(1000, low // 20), high + max(1000, low // 20)
    raw = (high - low) / count
    magnitude = 10 ** math.floor(math.log10(raw))
    step = next(m * magnitude for m in (1, 2, 2.5, 5, 10) if m * magnitude >= raw)
    step = max(int(step), 100)
    start = math.floor(low / step) * step
    end = math.ceil(high / step) * step
    return list(range(start, end + 1, step))


def _month_day(d):
    return f"{d.month}/{d.day}"


# ---- 比較リスト ------------------------------------------------------------------

def add_button(p, label=False):
    """比較リストに入れるボタン。動かすのは app.js（JavaScript が使えないときは表示しない）。"""
    text = '<span class="add-label">比較リストに追加</span>' if label else ""
    size = "add-btn add-btn--label" if label else "add-btn"
    return (
        f'<button type="button" class="{size}" data-add="{p["jan"]}" aria-pressed="false"'
        f' aria-label="{esc(p["name"])}を比較リストに追加"><span class="add-icon" aria-hidden="true"></span>{text}</button>'
    )


def cart_content():
    """比較リストのページ。中身は app.js が、このブラウザに保存したリストと価格データから組み立てる。"""
    return """    <h1 class="page-title">比較リスト</h1>
    <p class="lead">選んだ商品を、どの店舗に売ると一番高くなるかを計算します。
      リストはこのブラウザの中だけに保存され、最後に変更してから1日たつと自動で消えます。</p>
    <div id="cart-root"><p class="empty">読み込み中…</p></div>
    <noscript><p class="alert">比較リストを使うには JavaScript を有効にしてください。</p></noscript>"""


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
    """最高値の店舗名。一覧の略称では、買取に条件がある店舗（Apple Store の購入証明が必要など）に「※」を付ける。"""
    if full:
        return "・".join(s["name"] for s in p["best_shops"])
    return "・".join(s["short"] + ("※" if p["prices"][s["id"]].get("note") else "") for s in p["best_shops"])


def thumb(p, large=False):
    """商品画像（メーカー公式サイトか Yahoo!ショッピングの出品の画像を public/images/ に保存したもの）。
    クリックすると、画像の出典のページが開く。"""
    size = "thumb thumb--large" if large else "thumb"
    image = p.get("image") or {}
    src = image.get("src")
    if not (isinstance(src, str) and src.startswith("/images/")):
        return f'<span class="{size} thumb-empty" aria-hidden="true"></span>'
    img = f'<img src="{esc(src)}" alt="" width="44" height="44" loading="lazy" decoding="async">'
    url = image.get("url")
    if not _is_http(url):
        return f'<span class="{size}">{img}</span>'
    source = "メーカー公式サイト" if image.get("origin") else "Yahoo!ショッピング"
    title = f"画像の出典: {source}" + (f'（{image["seller"]}）' if image.get("seller") and not image.get("origin") else "")
    return (
        f'<a class="{size}" href="{esc(url)}" target="_blank" rel="noopener" title="{esc(title)}"'
        f' aria-label="{esc(p["name"])}の画像の出典（{source}）">{img}</a>'
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
