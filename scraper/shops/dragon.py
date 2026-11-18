"""ドラゴンモバイル（総合買取ドラゴンモバイル）。

一覧（sell.html?cat1=…&cat2=…&cat3=…&page=N）は1ページ24件で、各行に「JAN:」の欄・商品名・「新品」と「中古」の価格がある。
「新品」の価格だけを使い、「中古」は使わない。新品が0円の行（中古だけの買取）と1円の行（買取中止）は飛ばす。更新日の表示はない。
JAN の欄には JAN のほか、型番や「air11-m4-128-wifi」のような店の番号、JAN の下4桁だけが入っている行もある
（12桁の UPC は先頭に 0 を付けて JAN にする）。

一覧の新品の価格は、商品ページの新品のタブ（1つ目の .proDeta9a）の条件（色・容量・Nano-texture・判定◯/△・来店/郵送・
キャリア版・保証の登録の有無など）ごとの価格のうち一番高いもの（iPhone 18 Pro 2TB はバーガンディ 373,000円・ほかの3色 363,000円で、
一覧は 373,000円。iPhone Duo は店頭に持ち込むときだけの「来店」の価格）。条件ごとの価格は1件ずつ別のリクエスト
（get_attr.html?attr_id=…）でしか読めず、全部読むと300回ほどかかる。商品ページは次の順に、それぞれ一覧の価格の高い行から、
リクエストが120回に達するまで開く。
1. Apple Watch・Mac・AirPods の、一覧に JAN も型番もない行（1回で何色分も増える。開けなかった行は使わない）
2. iPhone・Pixel の色ごとの価格（一覧の価格は一番高い色の価格で、安い色が数千円高く出てしまうので、開けなかった行と、
   途中で回数が尽きて全部の条件を読めなかった行は使わない）
3. Galaxy・AQUOS の容量（容量ごとに get_attr が要る。開けなかった行の容量は使わない）
- iPhone・Pixel（SIMフリーの行）: 条件の色（「バーガンディ」「金灰黒」「黑/白/金」「Obsidian以外」など）ごとの価格を "colors" にする。
  キャリア版（SoftBank・docomo など）と「来店」の条件は使わない（Duo は「郵送」の価格）。色の区別のない条件
  （「郵送」「判定-/◯」）の価格は、色ごとの条件のない色に当てはめる。色の区別のない条件が1つだけで、ほかが△・中古だけ
  （キャリア版・来店の条件がない）なら、一覧の価格がその価格なので get_attr は読まない
- Galaxy・Xperia・AQUOS: SIMフリー（Google・SONY・SHARP・Samsung）とキャリア（au・SoftBank/Y!mobile・docomo・楽天）の
  カテゴリのキャリアで android_key を作る。JAN の欄は容量違いの行に同じ JAN が入っていたりするので使わない。
  「256GB 512GB 1TB」のように容量をまとめた行の価格は一番大きい容量の価格なので、その容量に当てはめる。
  ほかの容量は、カタログにあれば商品ページの新品・未開封の条件（「未開封品256GB ◯ 一括証明添付」など）の価格を get_attr で読む。
  容量の書かれていない Galaxy S・Z の行は、一覧の価格がどの容量のものかわからない（Z Flip7 au版は一覧 135,000円だが、
  条件は 256GB 120,000円・512GB 115,000円）ので、商品ページの条件の価格だけを使う。
  Z Flip7 SIMフリー版 256GB は色ごとの条件で、最初の色（ジェットブラック）の価格を全色に当てはめる（ミントは 1,000円安い）
- iPad: 一覧の名前（世代・サイズ・容量・Wi-Fi/Cellular）をカタログの iPad の名前と照らして、その全色の型番・JAN に当てはめる
  （商品ページの色の一覧には型番がないものが多く、11インチの型番や隣の容量の JAN が書かれていたりもするので開かない）。
  色ごとの条件がある行も、一覧の価格（一番高い色）を全色に当てはめる（iPad（A16）Wi-Fi 128GB のイエローは 1,000円安い）。
  カタログに Nano-texture もある iPad（Pro の 1TB・2TB、mini（A20）の 256GB・512GB）の行は、標準ガラスと Nano-texture を
  1行にまとめていて、一覧の価格は高い方の Nano-texture の価格（mini（A20）256GB は Nano-texture 115,000円・標準 110,000円）なので、
  Nano-texture の商品にだけ当てはめる（分けるには商品ページと get_attr が20回ほど要るので開かない）
- Apple Watch・Mac・AirPods: JAN と型番（apple_offer）。一覧に JAN も型番もない行は、商品ページの色や条件の一覧
  （色ごとの型番・JAN が書かれていることが多い）を読む
- ゲーム機・Switch ソフト・VR・Steam Deck・アクションカメラ・インスタントカメラ: JAN。商品ページは開かないので、
  店頭に持ち込むときの「来店」の価格が一覧の価格になっている商品もある（郵送より数百円高い。Switch 2 日本語版は来店 52,500円・郵送 52,000円）。
  Insta360 ONE RS ツイン版はカメラのサブカテゴリのどれにも入っていないので、カメラの中を「Insta360」で検索して拾う
条件の「予約のみ」「一括証明添付」「納品書提示」「ストア版購入証明添付」、商品名の「台数限定」は "note" にする
（容量をまとめた行は、開いたときに一覧の価格の容量の出品にも付ける）。SoftBank・Y!mobile の端末は、
利用制限の確認ページが止まっている間（2026-10-17 から。12月中旬に復旧の見込み）一括購入の証明と安心サポートに入っていない
画面がないと判定不明品として買い取る（お知らせ /ndetail/169.html）ので "note" にする。復旧したら外す。
JAN や型番には書き間違いがある（MacBook Air 13インチと15インチの行に同じ JAN、MacBook Pro の 16GB/1TB と 24GB/2TB の行に同じ JAN）。
同じ JAN・型番が、容量やサイズの違う行に違う価格で出てきたら使わない（_drop_ambiguous）。
PS5 ソフト・デジカメ・GoPro（JAN の欄が下4桁だけ）・ドローンは取らない。トレカのカテゴリは空。
"""
import re
import unicodedata

from bs4 import BeautifulSoup

from ..apple import apple_codes, apple_offer
from ..common import CATALOG, load_json
from ..phones import COLORS, android_key, phone_colors, phone_key, without_capacity
from ..text import parse_yen

ID = "dragon"
NAME = "ドラゴンモバイル"
SHORT = "ドラゴン"
URL = "https://mobileone.co.jp/"

LIST_URL = URL + "sell.html"
PRICE_URL = URL + "get_attr.html?attr_id="
MAX_REQUESTS = 120
# スマホのカテゴリ（cat1, cat2, cat3）→ キャリア。SIMフリーは Google・SONY・SHARP・Samsung だけ（OPPO・Xiaomi などは取らない）。
# SoftBank・docomo は SONY・SHARP・Samsung のサブカテゴリの方がページが少ない（au・楽天は変わらないか増える）
PHONES = {(140, 144, ""): "SIMフリー", (140, 145, 169): "SIMフリー", (140, 145, 172): "SIMフリー",
          (140, 145, 173): "SIMフリー", (140, 145, 174): "SIMフリー", (140, 146, ""): "au",
          (140, 147, 187): "SoftBank", (140, 147, 188): "SoftBank", (140, 147, 363): "SoftBank",
          (140, 148, 196): "docomo", (140, 148, 197): "docomo", (140, 148, 198): "docomo", (140, 178, ""): "楽天モバイル"}
# iPad・アクセサリ / スマートウォッチ / パソコン / オーディオ > Apple
APPLE = [(140, 149, ""), (140, 151, ""), (142, 263, ""), (142, 266, 310)]
# Nintendo / PlayStation / Xbox / VR / Switch ソフト / その他（Steam Deck） / カメラ > アクションカメラ・インスタントカメラ /
# カメラの中の「Insta360」の検索（4つ目は検索の言葉）
JAN_ONLY = [(141, 256, ""), (141, 257, ""), (141, 258, ""), (141, 259, ""), (141, 260, ""), (141, 262, ""),
            (142, 265, 305), (142, 265, 307), (142, 265, "", "Insta360")]
_APPLE = re.compile(r"iPad|Apple Watch|MacBook|Mac mini|iMac|Mac Studio|AirPods", re.IGNORECASE)
# 名前に書かれた容量（「1TB/512/256」のように単位のないものも数える）
_CAPACITIES = re.compile(r"(?<![\d.])(?:64|128|256|512|[12]\s*TB)(?![\d.])", re.IGNORECASE)
# 商品ページの条件のうち、新品・未開封でないもの
_NOT_NEW = re.compile(r"△|中古|上限|減額|(?<!未)開封|要問合せ")
# iPhone・Pixel の条件のうち、キャリア版と、店頭に持ち込むときだけのもの
_NOT_SIMFREE = re.compile(r"来店|SoftBank|docomo|キャリア版", re.IGNORECASE)
# 価格の条件（商品名や条件の名前の言葉, "note" に載せる言葉）
_NOTES = [("ストア版購入証明", "Apple Storeで購入した証明が必要"), ("一括証明", "一括購入の証明が必要"),
          ("納品書", "納品書が必要"), ("予約のみ", "予約が必要"), ("台数限定", "台数限定")]
SOFTBANK_NOTE = "一括購入の証明と、安心サポートに入っていないことがわかる画面が必要（ないと判定不明品として買取）"
# 条件の名前の色の書き方 → scraper.phones の色の別名（単独の「ブラック」は iPhone Air なら「スペースブラック」）と書き間違い
_COLOR_WORDS = {"ブラック": "black", "ホワイト": "white", "ブルー": "blue", "ゴールド": "gold", "シルバー": "silver",
                "ピンク": "pink"}
_TYPOS = {"黑": "黒", "lemograss": "lemongrass", "idigo": "indigo"}


def fetch(http):
    rows, requests = [], 0
    for cat in [*PHONES, *APPLE, *JAN_ONLY]:
        found, pages = _read_category(http, cat)
        rows += found
        requests += pages
    ipads, capacities = _catalog()
    # details は商品ページを開く行（開く順, 開いて出品を読む関数, 引数, 開けなかったときの出品）。開く順は、1回で何色分も
    # 増える Apple の型番、一覧の価格（一番高い色）を直す iPhone・Pixel の色、容量ごとに get_attr が要る Galaxy の容量の順で、
    # それぞれ一覧の価格の高い順
    offers, apple, details = [], [], []
    for r in rows:
        if r["cat"] in PHONES:
            found, detail = _phone_offers(r, PHONES[r["cat"]], capacities)
            offers += found
            if detail:
                details.append(detail)
        elif r["cat"] not in APPLE:
            offers.append({"jan": r["jan"], "name": r["name"], "price": r["price"], "url": r["url"]})
        elif _APPLE.search(r["name"]) and not re.search(r"Keyboard|Pencil", r["name"]):  # Apple 以外の時計・PC・アクセサリは除く
            # 一覧の JAN も codes に入れる（scraper.update は jan が当たると codes を見ないので、2色分の型番がある行で1色しか当たらない）
            offer = apple_offer(r["name"], r["price"], r["url"], text=r["code"])
            if "ipad" in r["name"].lower():
                offer["codes"] = dict.fromkeys(_ipad_codes(r["name"], offer["codes"], ipads), r["price"])
            else:
                apple.append((offer, r["detail"]))
            offers.append(offer)
    _drop_ambiguous(offers)
    details += [((0, -offer["price"]), _apple_codes, (offer, page), []) for offer, page in apple if not offer["codes"]]
    for _, read, args, fallback in sorted(details, key=lambda d: d[0]):
        if requests < MAX_REQUESTS:
            found, used = read(http, *args, MAX_REQUESTS - requests)
            offers += found
            requests += used
        else:
            offers += fallback
    _drop_ambiguous(offers)
    return [o for o in offers if o["jan"] or o.get("key") or o.get("codes")]


def _read_category(http, cat):
    """カテゴリ（4つ目があればその言葉の検索）の全ページの行（新品の価格があるものだけ）と、開いたページ数。"""
    rows, page, last = [], 1, 1
    while page <= last:
        words = f"&words={cat[3]}" if len(cat) > 3 else ""
        url = f"{LIST_URL}?cat1={cat[0]}&cat2={cat[1]}&cat3={cat[2]}{words}&page={page}"
        soup = _page(http, url)
        if page == 1:
            last = max([int(n) for a in soup.select(".page a[href]") for n in re.findall(r"page=(\d+)", a["href"])],
                       default=1)
        for li in soup.select(".list2 li"):
            name, code = li.select_one(".splist1"), li.select_one(".splist")
            price = next((parse_yen(t) for t in (_text(p) for p in li.select(".hot4")) if t.startswith("新品")), None)
            link = li.select_one(".splist2 a[href]")
            if not (name and code and link) or (price or 0) <= 1:
                continue  # 0円（中古だけ）と1円（買取中止）
            code = re.sub(r"^JAN\s*:\s*", "", _text(code))
            rows.append({"cat": cat, "name": _text(name), "code": code, "jan": _jan(code), "price": price, "url": url,
                         "detail": URL.rstrip("/") + link["href"]})
        page += 1
    return rows, last


def _catalog():
    """カタログの {iPad の名前のキー: 全色の型番・JAN} と、Android の {機種＋キャリア: 機種＋容量＋キャリアの一覧}。"""
    catalog = load_json(CATALOG)
    android = {s["id"] for s in catalog["series"] if s["category"] == "android"}
    ipads, capacities = {}, {}
    for p in catalog["products"]:
        key = _ipad_key(p["name"]) if p["name"].startswith("iPad") else None
        if key:
            ipads.setdefault(key, set()).update([p["jan"], *p.get("aliases", [])])
        key = phone_key(p["name"]) if p["series"] in android else None
        if key:
            capacities.setdefault(without_capacity(key), set()).add(key)
    return ipads, capacities


def _ipad_key(name):
    """「iPad Air (M3) 11インチ 256GB WiFi+Cellularモデル」→（ipad air, 11, M3, 256GB, Cellular か, Nano-texture か）。"""
    text = unicodedata.normalize("NFKC", name)
    line = re.search(r"iPad\s*(Pro|Air|mini)?", text, re.IGNORECASE)
    chip = re.search(r"\b(M\d|A\d\d)\b", text) or re.search(r"第(\d+)世代", text)  # 「A17 Pro」「A20 Pro」は A17・A20
    size = re.search(r"(\d\d(?:\.\d)?)\s*(?:インチ|inch)", text) or re.search(r"(?:Air|Pro)\s+(\d\d(?:\.\d)?)\b", text)
    capacity = re.search(r"(\d+)\s*(GB|TB)", text)
    if not (line and chip and capacity) or re.search(r"Keyboard|Pencil|用", text):
        return None
    return (f"iPad {line[1] or ''}".strip().lower(), size and size[1], chip[1], capacity[1] + capacity[2],
            bool(re.search(r"Cellular|セルラー", text, re.IGNORECASE)), "nano" in text.lower())


def _ipad_codes(name, codes, ipads):
    """iPad の行の型番・JAN に、カタログの同じ iPad の全色の分を足す。カタログの別の iPad の JAN・型番なら足さない
    （一覧の書き間違い）。カタログに Nano-texture もある iPad は、Nano-texture の全色の型番・JAN だけにする
    （一覧の価格は高い方の Nano-texture の価格）。"""
    key = _ipad_key(name)
    if not key:
        return list(codes)
    if key[:5] + (True,) in ipads:
        return list(ipads[key[:5] + (True,)])
    found = ipads.get(key, set())
    if not found & set(codes) and any(f & set(codes) for f in ipads.values()):
        return list(codes)
    return list(codes) + list(found)


def _phone_offers(r, carrier, capacities):
    """一覧の行の出品と、商品ページを開くときの（開く順, 読む関数, 引数, 開けなかったときの出品）。"""
    # 「256GB 512GBdocomo版」のように容量の後ろに続けて書かれた文字を離す（phones.py が容量として読めるように）
    name = re.sub(r"(\d(?:GB|TB))(?=[A-Za-z])", r"\1 ", r["name"])
    if re.search(r"iPhone|Pixel", name, re.IGNORECASE):
        key = phone_key(name)
        if carrier != "SIMフリー" or not phone_colors(key):
            return [], None  # キャリア版と古い機種は使わない
        offer = {"jan": None, "key": key, "name": r["name"], "price": r["price"], "url": r["url"], **_note(r["name"])}
        return [], ((1, -r["price"]), _color_offers, (r, offer), [])
    keys = [key for key in (android_key(name, c) for c in _carriers(name, carrier)) if key]
    named = len({c.replace(" ", "").upper() for c in _CAPACITIES.findall(name)})
    galaxy = named == 0 and re.search(r"Galaxy\s*(S\d|Z)", name, re.IGNORECASE)
    wanted = set()
    if galaxy or named > 1:  # 容量の書かれていない Galaxy S・Z と、容量をまとめた行
        wanted = {k for key in keys for k in capacities.get(without_capacity(key), ()) if k != key}
    if galaxy:  # 一覧の価格がどの容量のものかわからない（カタログにない機種は、未登録の商品の報告のために残す）
        keys = [key for key in keys if without_capacity(key) not in capacities]
    offers = [{"jan": None, "key": key, "name": r["name"], "price": r["price"], "url": r["url"],
               **_note(r["name"], key=key)} for key in keys]
    return offers, (((2, -r["price"]), _capacity_offers, (r, wanted, offers), []) if wanted else None)


def _carriers(name, carrier):
    """SoftBank・Y!mobile のカテゴリは、商品名でどちらか（両方のこともある）を決める。書かれていなければ SoftBank。"""
    if carrier != "SoftBank":
        return [carrier]
    ymobile = re.search(r"y!?\s*mobile|ワイモバイル", name, re.IGNORECASE)
    softbank = re.search(r"soft\s*bank|ソフトバンク|\bSB\b", name, re.IGNORECASE)
    return [c for c, hit in (("SoftBank", softbank or not ymobile), ("Y!mobile", ymobile)) if hit]


def _color_offers(http, r, offer, budget):
    """iPhone・Pixel の商品ページの、SIMフリー版の新品の条件の色ごとの価格（"colors"）。"""
    labels, used = _conditions(_page(http, r["detail"])), 1
    usable = [(label, attr) for label, attr in labels if not (_NOT_NEW.search(label) or _NOT_SIMFREE.search(label))]
    note = _note(r["name"], *(label for label, _ in usable))
    # キャリア版・来店の条件は SIMフリー版の条件より高いことがある（一覧の価格がそちらの価格のことがある）
    higher = [label for label, _ in labels if _NOT_SIMFREE.search(label) and not _NOT_NEW.search(label)]
    if len(usable) == 1 and not higher and not _label_colors(offer["key"], usable[0][0]):
        return [{**offer, **note}], used  # 一覧の価格がこの条件の価格
    named, rest = {}, []
    for label, attr in usable:
        if used >= budget:  # 全部の条件を読めなければ、色ごとの価格がわからないので使わない
            return [], used
        price, used = _price(http, attr), used + 1
        colors = _label_colors(offer["key"], label)
        for color in colors:
            named[color] = max(price, named.get(color, 0))
        if not colors:  # 色の区別のない条件（「郵送」「判定-/◯」）と、色を読めない条件は、ほかの色の価格
            rest.append(price)
    colors = {c: named.get(c, max(rest, default=0)) for c in phone_colors(offer["key"])}
    colors = {c: p for c, p in colors.items() if p > 1}
    return ([{**offer, **note, "price": max(colors.values()), "colors": colors}] if colors else []), used


def _label_colors(key, label):
    """条件の名前に書かれた色（公式の色名）。「金灰黒」「黑/白/金」のように何色も書かれていることがある。
    「Obsidian以外」はその色を除く全色。"""
    text = unicodedata.normalize("NFKC", label).lower()
    text = re.sub(f"(?<![ァ-ヴー])({'|'.join(_COLOR_WORDS)})(?![ァ-ヴー])", lambda m: _COLOR_WORDS[m[1]], text)
    for typo, word in _TYPOS.items():
        text = text.replace(typo, word)
    text = re.sub(r"\s+", "", text)
    colors = COLORS.get(without_capacity(key), {})
    aliases = sorted(((re.sub(r"\s+", "", a).lower(), c) for c, names in colors.items() for a in [c, *names]),
                     key=lambda a: -len(a[0]))
    found = []
    for alias, color in aliases:  # 「ブラックチタニウム」が「黒」より先に当たるように、長い名前から
        if alias in text:
            text = text.replace(alias, "/")
            found.append(color)
    return [c for c in colors if c not in found] if "以外" in label else list(dict.fromkeys(found))


def _capacity_offers(http, r, wanted, listed, budget):
    """商品ページの新品・未開封の条件のうち、wanted の容量の価格（get_attr。容量ごとに最初の条件）。
    一覧の価格の出品（listed）には、その容量の条件に共通の注意書き（「予約のみ」など）を付ける。"""
    labels, used = _conditions(_page(http, r["detail"])), 1
    bases = {without_capacity(key) for key in wanted | {o["key"] for o in listed}}
    found = {}  # 機種＋容量＋キャリア → 条件の（名前, get_attr の番号）
    for label, attr in labels:
        if not _NOT_NEW.search(label):
            for base in bases:
                found.setdefault(android_key(f"{base} {label}", base.rsplit(" ", 1)[1]), []).append((label, attr))
    for o in listed:
        names = [label for label, _ in found.get(o["key"], [])]
        if names and all(_note(n) == _note(names[0]) for n in names):
            o.update(_note(o["name"], names[0], key=o["key"]))
    offers = []
    for key in sorted(wanted):
        for label, attr in found.get(key, []):
            if used >= budget:
                break
            price, used = _price(http, attr), used + 1
            if price > 1:
                offers.append({"jan": None, "key": key, "name": f"{r['name']} {label}", "price": price,
                               "url": r["detail"], **_note(r["name"], label, key=key)})
                break
    return offers, used


def _apple_codes(http, offer, page, _):
    """商品ページの色や条件の一覧（「MRXN3J/A [スペースグレイ] 4549995446272」のように型番・JAN が書かれていることが多い）。
    型番がある色は型番だけにする（同じ色の JAN が、_drop_ambiguous で型番と別に残らないように）。"""
    soup = _page(http, page)
    conditions = [label for label, _ in _conditions(soup)]
    text = " ".join(" ".join(apple_codes(t)) or t for t in [*map(_text, soup.select(".proDeta7 span")), *conditions])
    found = apple_offer(offer["name"], offer["price"], offer["url"], text=text)
    usable = [label for label in conditions if not _NOT_NEW.search(label)]
    if usable and all(_note(label) == _note(usable[0]) for label in usable):
        found.update(_note(usable[0]))  # Apple Watch Ultra 2 の新品の条件は「未開封 ストア版購入証明添付」だけ
    return [found] if found["codes"] else [], 1


def _page(http, url):
    return BeautifulSoup(http.get(url).content, "html.parser")


def _conditions(soup):
    """商品ページの新品のタブ（1つ目の .proDeta9a）の条件の（名前, get_attr の番号）。"""
    tab = soup.select_one(".proDeta9a")
    spans = tab.select("span[onclick]") if tab else []
    return [(_text(s), m[1]) for s in spans if (m := re.search(r"get_price\((\d+)\)", s["onclick"]))]


def _price(http, attr):
    """条件の価格（get_attr）。読めなければ 0。"""
    data = http.get(PRICE_URL + attr).json()
    return int(data["data"]["price"]) if data.get("code") == 0 else 0


def _note(*texts, key=""):
    """商品名や条件の名前に書かれた価格の条件と、SoftBank・Y!mobile の端末（key）の条件の "note"。なければ空の辞書。"""
    notes = [note for word, note in _NOTES if any(word in t for t in texts)]
    if key.endswith(("SoftBank", "Y!mobile")):  # 一括購入の証明は SOFTBANK_NOTE に含まれる
        notes = [n for n in notes if n != "一括購入の証明が必要"] + [SOFTBANK_NOTE]
    return {"note": "・".join(notes)} if notes else {}


def _drop_ambiguous(offers):
    """同じ JAN・型番が、容量やサイズの違う行に違う価格で書かれていたら、どの商品のものかわからないので使わない
    （一覧の JAN の欄に別の商品の JAN が書かれていたりする）。容量やサイズが同じ行どうしなら同じ商品が2行にあるだけなので残す
    （scraper.update が高い方を使う）。"""
    rows = {}
    for o in offers:
        for i in [o["jan"], *o.get("codes", {})]:
            rows.setdefault(i, []).append(o)
    for i, found in rows.items():
        if i and len({o["price"] for o in found}) > 1 and len({_spec(o["name"]) for o in found}) > 1:
            for o in found:
                if o["jan"] == i:
                    o["jan"] = None
                o.get("codes", {}).pop(i, None)


def _spec(name):
    """名前の容量・メモリとサイズ（「13インチ」「13.6」→ 13）。"""
    text = unicodedata.normalize("NFKC", name)
    capacities = {n + u[0] for n, u in re.findall(r"(\d+)\s*(GB|TB|G)(?![A-Za-z])", text)}  # 「512G」と「512GB」は同じ
    sizes = set(re.findall(r"(?<![\d.])(1[1-6])(?:\.\d)?(?=\s*(?:インチ|inch|\s|$))", text))
    return frozenset(capacities), frozenset(sizes)


def _jan(text):
    m = re.search(r"(?<!\d)(\d{12,13})(?!\d)", text)
    return m.group(1).zfill(13) if m else None


def _text(tag):
    return " ".join(unicodedata.normalize("NFKC", tag.get_text(" ")).split())
