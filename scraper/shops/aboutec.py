"""アバウテック。

買取商品の一覧（/purchase/?pca=カテゴリ&ca=サブカテゴリ）は静的な HTML で、1ページ10件。
各商品に「新品買取価格」（メーカー出荷時の未開封・未使用）・参考価格・JAN・発売日が載っている。
価格は「新品買取価格」だけを使う（詳細ページにある「新古買取価格」は使わない）。
古い商品は「お問い合わせください」で価格がないので、買取価格の高い順（order=2）に並べて、
価格のない商品が出てきたページまでを読む。
- iPhone: すべて SIMフリー版で、JAN で突き合わせる
- iPad・Apple Watch・AirPods・Mac: JAN と、商品名に入っている型番（apple_offer）で突き合わせる。
  AirPods は「イヤホン」のサブカテゴリにほかの社の商品が多いので、キーワード検索（keywords=AirPods）で読む
- ゲーム機・ビデオカメラ（Insta360・GoPro・ハンディカム）・デジカメ（PowerShot・Tough・RICOH WG）: JAN
一眼・テレビ・PC（Mac 以外）などのカテゴリはカタログにないので読まない。
詳細ページに商品ごとの更新日があるが、確かめた商品はどれも当日の日付だったので、詳細ページは開かない。
"""
from bs4 import BeautifulSoup

from ..apple import apple_offer
from ..text import find_jan, parse_yen

ID = "aboutec"
NAME = "アバウテック"
SHORT = "アバウテック"
URL = "https://www.aboutec.jp/"

LIST_URL = URL + "purchase/"
# iPhone / ゲーム機器 / ビデオカメラ / PowerShot / RICOH WG / Tough
JAN_LISTS = ["pca=23", "pca=5", "pca=7", "pca=6&ca=45", "pca=6&ca=99", "pca=6&ca=101"]
# iPad / Apple Watch / AirPods / MacBook / Mac
APPLE_LISTS = ["pca=3&ca=16", "pca=15&ca=63", "keywords=AirPods", "pca=1&ca=13", "pca=2&ca=14"]
MAX_PAGES = 30


def fetch(http):
    offers = []
    for query in JAN_LISTS:
        for name, jan, price, url in _read_list(http, query):
            offers.append({"jan": jan, "name": name, "price": price, "url": url})
    for query in APPLE_LISTS:
        for name, jan, price, url in _read_list(http, query):
            offers.append(apple_offer(name, price, url, jan=jan))
    return [o for o in offers if o["jan"] or o.get("codes")]


def _read_list(http, query):
    """（商品名, JAN, 新品買取価格, 詳細ページの URL）を、価格の高い順に価格のある商品だけ返す。"""
    for page in range(1, MAX_PAGES + 1):
        soup = BeautifulSoup(http.get(f"{LIST_URL}?{query}&order=2&p={page}").content, "html.parser")
        items = soup.select(".purchase-list article")
        for item in items:
            fields = {dt.get_text(strip=True): dd.get_text(strip=True)
                      for dt, dd in zip(item.select(".infor dt"), item.select(".infor dd"))}
            price = parse_yen(fields.get("新品買取価格")) if "円" in fields.get("新品買取価格", "") else None
            if not price:
                return  # ここから後ろは「お問い合わせください」の商品
            table = {th.get_text(strip=True): td.get_text(strip=True)
                     for th, td in zip(item.select(".right th"), item.select(".right td"))}
            yield (" ".join(item.select_one("h3").get_text().split()), find_jan(table.get("JANコード")), price,
                   f"{LIST_URL}?pid={item['id'].removeprefix('n_')}")
        if not soup.select_one(".pager li.next"):
            return
