"""カタログの商品画像を用意して public/images/ と catalog/images.json に保存する。

商品に "image_url"（メーカー公式サイトの本体画像のURL）があれば、その画像を使う。
メーカー以外の画像（PSA 鑑定品のトレカラウンジの画像など）は、"image_source" に出典の名前を書く。
"image_crop": "slab" の商品は、PSA のケースごと写した画像なら、カードの部分だけ切り抜く（SLAB_CARD）。
ないときだけ、Yahoo!ショッピングの商品検索APIで JAN から探す。

    python -m scraper.images                        # 画像がまだない商品などの画像を探す
    python -m scraper.images --candidates JAN ...   # 画像の候補（出品ごと）を一覧表示する

- Client ID は環境変数 YAHOO_CLIENT_ID から読む（コードやファイルには書かない）
- JAN コードで検索し、画像のある新品の出品の中から1件を選ぶ（中古の出品は、実物の写真のことが多いので使わない）。
  選ばれた画像が宣伝用の文字入りなどでいまいちなときは、--candidates で候補を見て、
  catalog/products.json の商品に "image_item": "<出品コード>" を書くと、その出品の画像を使う
  （同じ店舗が画像の違う出品を複数出していることがあるので、店舗ではなく出品で指定する）
- 新品の出品がない商品は、見た目が同じ別の商品（容量違いの iPhone など）のJANを
  "image_from": "<JAN>" に書くと、その商品の画像を使う
- 選んだ画像は public/images/<JAN>.jpg に保存して、サイトから直接出す（元の出品が消えても使える）。
  出品ごとに余白や大きさがバラバラなので、大きい画像（600px）から余白を切り取り、
  同じ大きさの白い正方形の中央に、同じ大きさで置いて保存する（normalize）
  一度保存した画像は使い続け、探し直すのは、まだ画像がない商品と "image_item" を変えた商品だけ
- API は1秒に1回までだが、続けて使うと一時的に制限されるので間隔を広めにしている
"""
import argparse
import io
import os
import sys
import time

import requests
from PIL import Image, ImageDraw

from .common import CATALOG, IMAGES, ROOT, load_json, set_github_output, warn, write_json

API = "https://shopping.yahooapis.jp/ShoppingWebService/V3/itemSearch"
INTERVAL = 2.5   # 秒。1秒に1回の上限ぎりぎりだと、30件ほどで制限がかかった
IMAGE_DIR = ROOT / "public" / "images"
LARGE_URL = "https://item-shopping.c.yimg.jp/i/l/{code}"  # 600px の画像（i/g/ は 146px）
IMAGE_SIZE = 240   # 保存する画像の一辺（商品ページの大きい画像の2倍）
IMAGE_FILL = 0.86  # 商品が正方形に占める大きさ
# PSA のケースごと写した画像（縦横比が SLAB_RATIO より細長い）でカードが写っている範囲（左・上・右・下の割合）。
# 森森買取の画像（800×1350 など）で、ケースの絵・実物の写真のどちらもこの範囲に収まる
SLAB_CARD = (0.1, 0.268, 0.9, 0.924)
SLAB_RATIO = 0.65
IMAGE_TYPES = {"image/jpeg", "image/png", "image/webp"}
RESULTS = 20     # 1商品あたりに見る出品の数
RETRY_WAITS = [15, 30, 60]  # 秒。アクセス過多（HTTP 429）と言われたときに待ってやり直す
# 画像に「送料無料」「レビュー特典」などの文字や枠を入れている店舗（出品コードの「_」より前）。
# ほかに画像のある出品がないときだけ使う
NOISY_STORES = {
    "jcka-mobile", "jcka-mobile2", "quality-shop", "mobax", "brave-shopping", "evalue-omochayasan",
    "free-world", "1913store", "panda-mobile", "anshin-happy-mark", "arunni7", "mobilestation", "whitemocha",
}


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
    searched = []
    for product in catalog["products"]:
        if product.get("image_from"):
            continue
        if product.get("image_url"):
            official = official_image(session, product, previous.get(product["jan"]))
            if official:
                images[product["jan"]] = official
            else:
                warn(f"{product['name']}: 公式の画像（{product['image_url']}）を取得できませんでした")
            continue
        if not product["jan"].isdigit():
            continue  # JAN がない商品（PSA 鑑定品など）は、Yahoo!ショッピングで探せないので画像なし
        old = previous.get(product["jan"])
        item_code = product.get("image_item")
        if old and (not item_code or old.get("code") == item_code) and save(session, product["jan"], old):
            images[product["jan"]] = old
        else:
            searched.append(product)
    print(f"{len(images)}商品は前回の画像のまま。{len(searched)}商品の画像を探します")
    errors = 0
    for i, product in enumerate(searched):
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
        if chosen and save(session, jan, chosen):
            images[jan] = chosen
            print(f"[OK] {product['name']}（{chosen['seller']}）")
        else:
            print(f"[--] {product['name']}: 画像のある出品が見つかりませんでした")
    for product in catalog["products"]:
        source = product.get("image_from")
        if source and source in images:
            images[product["jan"]] = images[source]
        elif source:
            warn(f"{product['name']}: image_from の商品（{source}）に画像がありません")

    changed = images != previous
    if changed:
        write_json(IMAGES, images)
    print(f"{len(images)}/{len(catalog['products'])}商品の画像あり。"
          + ("images.json を更新しました" if changed else "変化なし"))
    set_github_output("changed", "true" if changed else "false")
    if searched and errors == len(searched):
        sys.exit("すべての商品で検索に失敗しました")


def official_image(session, product, old):
    """メーカー公式の画像（"image_url"）を保存する。前回と同じ画像なら、保存済みのファイルを使う。"""
    url = product["image_url"]
    image = {"src": url, "url": product.get("image_page") or "", "origin": url,
             **({"source": product["image_source"]} if product.get("image_source") else {})}
    same = bool(old) and old.get("origin") == url and (IMAGE_DIR / f"{product['jan']}.jpg").exists()
    return image if save(session, product["jan"], image, refresh=not same,
                         slab=product.get("image_crop") == "slab") else None


def save(session, jan, image, refresh=False, slab=False):
    """画像を整えて public/images/<JAN>.jpg に保存し、image["src"] をそのパスにする。保存できなければ False。"""
    path = IMAGE_DIR / f"{jan}.jpg"
    if refresh or not path.exists():
        urls = [LARGE_URL.format(code=image["code"])] if image.get("code") else []
        urls += [image["src"]] if image["src"].startswith("https://") else []
        data = next((d for d in (_download(session, url) for url in urls) if d), None)
        if data is None:
            return False
        IMAGE_DIR.mkdir(parents=True, exist_ok=True)
        path.write_bytes(normalize(data, slab=slab))
    image["src"] = f"/images/{jan}.jpg"
    return True


def _download(session, url):
    try:
        res = session.get(url, timeout=30)
    except requests.RequestException:
        return None
    # Yahoo!の出品が消えた画像のURLは「画像なし」の GIF を返す
    if res.status_code != 200 or res.headers.get("content-type", "").split(";")[0].strip().lower() not in IMAGE_TYPES:
        return None
    return res.content


def _product_box(mask):
    """写っているもののうち、細い文字（著作権表示や「Front」など）を除いた商品の範囲。

    画像を 100×100 のマスに分け、つながったマスのかたまりごとに見る。
    高さが画像の長い方の辺の 5% に満たないかたまりは文字とみなして除く。
    """
    n = 100
    cw, ch = mask.width / n, mask.height / n
    filled = {(x, y) for y in range(n) for x in range(n)
              if mask.crop((int(x * cw), int(y * ch), int((x + 1) * cw) or 1, int((y + 1) * ch) or 1)).getbbox()}
    boxes = []
    seen = set()
    for cell in filled:
        if cell in seen:
            continue
        stack, part = [cell], []
        seen.add(cell)
        while stack:
            x, y = stack.pop()
            part.append((x, y))
            for nx, ny in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
                if (nx, ny) in filled and (nx, ny) not in seen:
                    seen.add((nx, ny))
                    stack.append((nx, ny))
        xs, ys = [c[0] for c in part], [c[1] for c in part]
        if (max(ys) - min(ys) + 1) * ch >= max(mask.width, mask.height) * 0.05:
            boxes.append((min(xs), min(ys), max(xs) + 1, max(ys) + 1))
    if not boxes:
        return mask.getbbox()
    left, top = min(b[0] for b in boxes), min(b[1] for b in boxes)
    right, bottom = max(b[2] for b in boxes), max(b[3] for b in boxes)
    region = (int(left * cw), int(top * ch), int(right * cw), int(bottom * ch))
    inner = mask.crop(region).getbbox()
    return (region[0] + inner[0], region[1] + inner[1], region[0] + inner[2], region[1] + inner[3]) if inner else None


def normalize(data, slab=False):
    """余白を切り取り、白い正方形の中央に同じ大きさで置いた JPEG にする。
    slab なら、PSA のケースごと写した画像からカードの部分だけ切り抜く。"""
    image = Image.open(io.BytesIO(data))
    if slab and image.width / image.height < SLAB_RATIO:
        w, h = image.size
        image = image.crop(tuple(round(v * (w if n % 2 == 0 else h)) for n, v in enumerate(SLAB_CARD)))
    # 背景が透明な画像（公式サイトの PNG など）は、白い背景に載せる
    if image.mode in ("RGBA", "LA", "P"):
        image = image.convert("RGBA")
        white = Image.new("RGBA", image.size, (255, 255, 255, 255))
        image = Image.alpha_composite(white, image)
    image = image.convert("RGB")
    w, h = image.size
    corners = [(0, 0), (w - 1, 0), (0, h - 1), (w - 1, h - 1)]
    # 背景が白っぽい（薄い灰色など）ときは、背景を白にそろえる（四隅からつながっている部分だけ）
    if all(min(image.getpixel(c)) >= 215 for c in corners):
        for c in corners:
            ImageDraw.floodfill(image, c, (255, 255, 255), thresh=24)
    mask = image.convert("L").point(lambda v: 255 if v < 245 else 0)
    box = _product_box(mask)
    if box:
        image = image.crop(box)
    target = IMAGE_SIZE * IMAGE_FILL
    scale = min(target / image.width, target / image.height)
    image = image.resize((max(1, round(image.width * scale)), max(1, round(image.height * scale))), Image.LANCZOS)
    canvas = Image.new("RGB", (IMAGE_SIZE, IMAGE_SIZE), (255, 255, 255))
    canvas.paste(image, ((IMAGE_SIZE - image.width) // 2, (IMAGE_SIZE - image.height) // 2))
    out = io.BytesIO()
    canvas.save(out, "JPEG", quality=88, optimize=True)
    return out.getvalue()


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

    出品の指定があればその出品を使う。なければ、画像に文字を入れている店舗（NOISY_STORES）を除いて、レビューの多い出品ほど
    きちんとした商品画像を使っていることが多いので、レビュー数が最も多いものを選ぶ
    （同数なら API のおすすめ順で先のもの）。
    """
    candidates = _with_image(hits, jan)
    if not candidates:
        return None
    preferred = [h for h in candidates if item_code and h.get("code") == item_code]
    if not preferred:
        candidates = [h for h in candidates if _store(h) not in NOISY_STORES] or candidates
    best = preferred[0] if preferred else max(
        candidates, key=lambda h: (h.get("review") or {}).get("count") or 0)
    return {
        "src": best["image"]["medium"],
        "url": best["url"],
        "seller": (best.get("seller") or {}).get("name", ""),
        "code": best.get("code", ""),
    }


def _store(hit):
    return (hit.get("code") or "").split("_")[0]


def _with_image(hits, jan):
    return [
        h for h in hits
        if h.get("janCode") == jan and h.get("condition") == "new" and (h.get("image") or {}).get("medium")
    ]


if __name__ == "__main__":
    main()
