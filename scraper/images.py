"""Yahoo!ショッピングの商品検索APIで、カタログの商品画像を探して catalog/images.json に保存する。

    python -m scraper.images                        # 全商品の画像を更新する
    python -m scraper.images --candidates JAN ...   # 画像の候補（出品ごと）を一覧表示する

- Client ID は環境変数 YAHOO_CLIENT_ID から読む（コードやファイルには書かない）
- JAN コードで検索し、画像のある新品の出品の中から1件を選ぶ（中古の出品は、実物の写真のことが多いので使わない）。
  選ばれた画像が宣伝用の文字入りなどでいまいちなときは、--candidates で候補を見て、
  catalog/products.json の商品に "image_item": "<出品コード>" を書くと、その出品の画像を使う
  （同じ店舗が画像の違う出品を複数出していることがあるので、店舗ではなく出品で指定する）
- API は1秒に1回までだが、続けて使うと一時的に制限されるので間隔を広めにしている。
  全商品で2分ほどかかる。1日1回の実行で十分
- 画像ファイルはコピーせず、Yahoo!が配信している画像のURLをそのまま使う
"""
import argparse
import os
import sys
import time

import requests

from .common import CATALOG, IMAGES, load_json, set_github_output, warn, write_json

API = "https://shopping.yahooapis.jp/ShoppingWebService/V3/itemSearch"
INTERVAL = 2.5   # 秒。1秒に1回の上限ぎりぎりだと、30件ほどで制限がかかった
RESULTS = 20     # 1商品あたりに見る出品の数
RETRY_WAITS = [15, 30, 60]  # 秒。アクセス過多（HTTP 429）と言われたときに待ってやり直す


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description="Yahoo!ショッピングから商品画像を取得する")
    parser.add_argument("--candidates", nargs="+", metavar="JAN", help="指定した商品の画像の候補を一覧表示する")
    args = parser.parse_args()

    client_id = os.environ.get("YAHOO_CLIENT_ID")
    if not client_id:
        sys.exit("環境変数 YAHOO_CLIENT_ID が設定されていません")
    session = requests.Session()
    if args.candidates:
        show_candidates(session, client_id, args.candidates)
    else:
        update_all(session, client_id)


def update_all(session, client_id):
    catalog = load_json(CATALOG)
    previous = load_json(IMAGES) if IMAGES.exists() else {}
    images = {}
    errors = 0
    for i, product in enumerate(catalog["products"]):
        if i:
            time.sleep(INTERVAL)
        jan = product["jan"]
        try:
            hits = search(session, client_id, jan)
        except RuntimeError as e:
            errors += 1
            warn(f"{product['name']}: {e}")
            if jan in previous:
                images[jan] = previous[jan]  # 取れなかったときは前回の画像を残す
            continue
        item_code = product.get("image_item")
        chosen = choose(hits, jan, item_code)
        if chosen and item_code and chosen["code"] != item_code:
            warn(f"{product['name']}: 指定した出品（{item_code}）が見つからないので、自動で選びました")
        if chosen:
            images[jan] = chosen
            print(f"[OK] {product['name']}（{chosen['seller']}）")
        else:
            print(f"[--] {product['name']}: 画像のある出品が見つかりませんでした")

    changed = images != previous
    if changed:
        write_json(IMAGES, images)
    print(f"{len(images)}/{len(catalog['products'])}商品の画像あり。"
          + ("images.json を更新しました" if changed else "変化なし"))
    set_github_output("changed", "true" if changed else "false")
    if errors == len(catalog["products"]):
        sys.exit("すべての商品で検索に失敗しました")


def show_candidates(session, client_id, jans):
    for i, jan in enumerate(jans):
        if i:
            time.sleep(INTERVAL)
        print(f"=== {jan}")
        for hit in _with_image(search(session, client_id, jan), jan):
            seller = (hit.get("seller") or {}).get("name", "")
            reviews = (hit.get("review") or {}).get("count") or 0
            print(f"  {hit.get('code', ''):<40} レビュー{reviews:>5}件  {seller}")
            print(f"      {hit['image']['medium']}")


def search(session, client_id, jan):
    params = {"appid": client_id, "jan_code": jan, "results": RESULTS}
    for wait in [*RETRY_WAITS, None]:
        try:
            res = session.get(API, params=params, timeout=30)
        except requests.RequestException as e:
            # 例外のメッセージには Client ID 入りの URL が含まれるので、そのまま表示しない
            raise RuntimeError(f"通信エラー（{type(e).__name__}）") from None
        if res.status_code == 429 and wait is not None:
            time.sleep(wait)
            continue
        if res.status_code != 200:
            raise RuntimeError(f"HTTP {res.status_code}")
        return res.json().get("hits", [])


def choose(hits, jan, item_code=None):
    """画像のある出品から1件選ぶ。

    出品の指定があればその出品を使う。なければ、レビューの多い出品ほど
    きちんとした商品画像を使っていることが多いので、レビュー数が最も多いものを選ぶ
    （同数なら API のおすすめ順で先のもの）。
    """
    candidates = _with_image(hits, jan)
    if not candidates:
        return None
    preferred = [h for h in candidates if item_code and h.get("code") == item_code]
    best = preferred[0] if preferred else max(
        candidates, key=lambda h: (h.get("review") or {}).get("count") or 0)
    return {
        "src": best["image"]["medium"],
        "url": best["url"],
        "seller": (best.get("seller") or {}).get("name", ""),
        "code": best.get("code", ""),
    }


def _with_image(hits, jan):
    return [
        h for h in hits
        if h.get("janCode") == jan and h.get("condition") == "new" and (h.get("image") or {}).get("medium")
    ]


if __name__ == "__main__":
    main()
