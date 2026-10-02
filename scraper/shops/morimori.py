"""森森買取。

カテゴリごとの「本日の買取価格一覧」（/category/price-list/<カテゴリ>）に、
カテゴリ・商品タイプ（新品）・商品名・JAN・価格が表で載っている。1ページ100件で、続きは ?page=N。
価格は「通常買取価格」を使う（「預かり買取」「即フリ買取」は条件付きの別の価格）。
iPhone は色ごとに「Apple iPhone18 ProMax 256GB バーガンディ SIMフリー」のように、
Android はキャリア版も「… docomo」「… (SIMフリー)」のように、別の行で載っている。
JAN は、先頭が0のもの（Steam Deck など）を、0を省いた12桁で載せていることがある。
iPad・Apple Watch も同じ一覧で、色ごと（Watch はバンドごと）に JAN と型番が載っている。
AirPods は専用のカテゴリがないので、ヘッドホン・イヤホンの一覧から「AirPods」の行だけを使う。
トレカの一覧には PSA 鑑定品（「ポケモンカード PSA10 リーリエ SR 119/114」、仮のJAN付き）も載っていて、
カード名・番号・点数で突き合わせる。
robots.txt に Crawl-delay: 5 があるので、アクセスは5秒ずつ空ける。
"""
import re
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from ..apple import apple_offer
from ..phones import android_key, one_color, phone_colors, phone_key
from ..psa import parse_name, psa_key
from ..text import parse_yen

ID = "morimori"
NAME = "森森買取"
SHORT = "森森"
URL = "https://www.morimori-kaitori.jp/"
INTERVAL = 5.0

LIST_URL = "https://www.morimori-kaitori.jp/category/price-list/"
# Switch本体 / PS5本体 / Xbox Series X本体 / Xbox Series S本体 / Steam Deck / Steam Machine / Meta Quest
GAME_CATEGORIES = ["0104001", "0101001", "0108001", "0113001", "0115001", "0116001", "0114"]
# iPhone（全機種。新しい機種から順に載っている）
IPHONE_CATEGORIES = ["0301"]
# Android: SAMSUNG / Google Pixel / SONY Xperia / AQUOS
ANDROID_CATEGORIES = ["0304012", "0304001", "0304002", "0304003"]
# iPad Pro / iPad Air / iPad / iPad mini / Apple Watch / ヘッドホン・イヤホン（AirPods）
APPLE_CATEGORIES = ["0401001", "0401002", "0401003", "0401004", "0303001", "0602001"]
# トレカ: ポケモンカード / 遊戯王 / ワンピース / ドラゴンボール
CARD_CATEGORIES = ["2401", "2402", "2403", "2404"]
CARD_GAMES = {"2401": "pokemon", "2402": "yugioh", "2403": "onepiece"}
MAX_PAGES = 10


def fetch(http):
    offers = []
    for category in GAME_CATEGORIES + CARD_CATEGORIES:
        rows = _read_list(http, category)
        offers += [o for o in rows if "PSA" not in o["name"]]
        offers += _psa_offers(rows, category)
    for category in IPHONE_CATEGORIES + ANDROID_CATEGORIES:
        for o in _read_list(http, category):
            key = phone_key(o["name"]) if re.search("iPhone|Pixel", o["name"]) else android_key(o["name"])
            # 古い機種（iPhone 15 など）は扱っていないので取らない
            if key and phone_colors(key):
                offers.append({**o, "key": key, "colors": one_color(key, o["name"], o["price"])})
    for category in APPLE_CATEGORIES:
        for o in _read_list(http, category):
            if category != "0602001" or "AirPods" in o["name"]:
                offers.append(apple_offer(o["name"], o["price"], o["url"], jan=o["jan"]))
    return [o for o in offers if (o["jan"] or o.get("key") or o.get("codes")) and o["price"]]


def fetch_psa(http):
    """PSA 鑑定品の出品（scraper.psa_catalog でも使う）。"""
    return [o for category in CARD_GAMES for o in _psa_offers(_read_list(http, category), category)]


def _psa_offers(rows, category):
    """鑑定済みのシングルカード（PSA）の JAN は仮のものなので、カード名・番号・点数で突き合わせる。"""
    offers = []
    for o in rows:
        parsed = parse_name(o["name"]) if "PSA" in o["name"] and category in CARD_GAMES else None
        key = psa_key(CARD_GAMES[category], parsed[0], parsed[1], parsed[3]) if parsed else None
        if key:
            offers.append({**o, "jan": None, "key": key,
                           "psa": {"game": CARD_GAMES[category], "grade": parsed[0], "name": parsed[1],
                                   "rarity": parsed[2], "number": parsed[3]}})
    return offers


def _read_list(http, category):
    """カテゴリの全ページの新品の行を {"jan", "name", "price", "url"} で返す。"""
    offers = []
    for page in range(1, MAX_PAGES + 1):
        url = LIST_URL + category + (f"?page={page}" if page > 1 else "")
        soup = BeautifulSoup(http.get(url).content, "html.parser")
        table = soup.select_one("table.price-list")
        for row in table.select("tr") if table else []:
            cells = row.find_all("td")
            link = row.select_one('a[href*="/product/"]')
            # 列: カテゴリ×3・商品タイプ・商品名・JAN・通常買取価格・預かり買取価格・即フリ買取価格
            if len(cells) < 7 or link is None or cells[3].get_text(strip=True) != "新品":
                continue
            offers.append({
                "jan": _jan(cells[5].get_text()),
                "name": " ".join(link.get_text().split()),
                "price": parse_yen(cells[6].get_text()),
                "url": urljoin(URL, link["href"]),
            })
        if not soup.select_one(f'a[href*="price-list/{category}?page={page + 1}"]'):
            break
    return offers


def _jan(text):
    digits = re.sub(r"\D", "", text or "")
    if len(digits) == 12:  # UPC（先頭の0を省いた JAN）
        digits = "0" + digits
    return digits if len(digits) == 13 else None
