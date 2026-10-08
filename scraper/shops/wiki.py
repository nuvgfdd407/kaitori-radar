"""買取wiki。

機種別のページが新しい機種に対応していないので、メーカー別の一覧を使う。
1ページ28件で、2ページ目以降は /brand/<メーカー>/<ページ番号>。
中古品も新品と同じJANで載っていて、商品名に「中古」と入っているので除外する。
スマホは同じ買取wiki のスマホ用のサイト（iphonekaitori.tokyo）に、同じ作りの一覧で載っている。
iPhone は色ごとに「iPhone 18 Pro 256GB ブラック」のように載っていて、一覧の価格は未開封の価格。
Android はキャリア版も同じ一覧に載っていて、商品名の「Softbank版」「docomo」や型番でキャリアを見分ける。
Apple Watch・AirPods は家電用のサイト（kadenkaitori.tokyo）の Apple の一覧に、JAN と型番つきで載っている。
（iPad 用のサイトは機種ごとにまとめた価格しか載っていないので使わない）
"""
import re
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from ..apple import apple_offer
from ..phones import android_key, one_color, phone_colors, phone_key
from ..text import find_jan, parse_yen

ID = "wiki"
NAME = "買取wiki"
SHORT = "買取wiki"
URL = "https://gamekaitori.jp/"

BRANDS = ["nintendo", "sony", "microsoft", "Oculus", "no-brand"]  # no-brand: Switch 2 の microSD Express カードなど
PHONE_URL = "https://iphonekaitori.tokyo/"
# iPhone / Google（Pixel） / SAMSUNG（Galaxy） / SONY（Xperia） / SHARP（AQUOS）
PHONE_LISTS = ["series/iphone", "brand/google", "brand/samsung", "brand/sony", "brand/sharp"]
APPLE_URL = "https://kadenkaitori.tokyo/"
# Mac は PC 用の別サイト（同じ作りの一覧）
MAC_URL = "https://pckaitori.tokyo/"
MAC_PATHS = ["category/mac-note-pc", "category/mac-desktop-pc"]
# カメラは別サイト（同じ作りの一覧）: チェキ・写ルンです / アクションカメラ（GoPro・DJI・Insta360）
CAMERA_URL = "https://camerakaitori.tokyo/"
CAMERA_PATHS = ["category/insant-camera", "category/video-camera"]
MAX_PAGES = 20


def fetch(http):
    offers = []
    for brand in BRANDS:
        offers += [o for o in _read_list(http, URL, f"brand/{brand}") if o["jan"]]
    for path in CAMERA_PATHS:
        offers += [o for o in _read_list(http, CAMERA_URL, path) if o["jan"]]
    for path in PHONE_LISTS:
        for o in _read_list(http, PHONE_URL, path):
            name = o["name"]
            key = phone_key(name) if re.search("iPhone|Pixel", name) else android_key(name)
            # 古い機種や、扱っていない機種は取らない
            if key and phone_colors(key):
                offers.append({**o, "key": key, "colors": one_color(key, name, o["price"])})
    apple = list(_read_list(http, APPLE_URL, "brand/apple"))
    for path in MAC_PATHS:
        apple += _read_list(http, MAC_URL, path)
    for o in apple:
        offers.append(apple_offer(o["name"], o["price"], o["url"], jan=o["jan"]))
    return [o for o in offers if o["price"]]


def _read_list(http, base, path):
    """一覧の全ページの {"jan", "name", "price", "url"}。中古品は除く。"""
    offers = []
    for page in range(1, MAX_PAGES + 1):
        url = f"{base}{path}/" + (str(page) if page > 1 else "")
        soup = BeautifulSoup(http.get(url).content, "html.parser")
        cards = soup.select("div.pro_list")
        for card in cards:
            link = card.select_one("li.sub-pro-name a[href]")
            price = card.select_one("li.sub-pro-jia span")
            if link is None or price is None:
                continue
            name = link.get_text(" ", strip=True)
            if "中古" in name:
                continue
            jan_line = next((li for li in card.select("li.sub-pro-name") if "JAN" in li.get_text()), None)
            offers.append({
                "jan": find_jan(jan_line.get_text() if jan_line else name),
                "name": name,
                "price": parse_yen(price.get_text()),
                "url": urljoin(base, link["href"]),
            })
        if not cards or not soup.select_one(f'a[href$="/{path}/{page + 1}"]'):
            break
    return offers
