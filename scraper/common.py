"""価格の更新（update）と画像の更新（images）で共通して使うファイルの場所と小さな関数。"""
import json
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CATALOG = ROOT / "catalog" / "products.json"
IMAGES = ROOT / "catalog" / "images.json"
PRICES = ROOT / "public" / "data" / "prices.json"

# 公開しているサイトの正式なURL（canonical やサイトマップに使う）
SITE_URL = "https://kaitori-radar.com"


def load_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def warn(message):
    # GitHub Actions では実行結果の画面に警告として表示される
    prefix = "::warning::" if os.environ.get("GITHUB_ACTIONS") == "true" else "[NG] "
    print(prefix + message)


def set_github_output(name, value):
    if "GITHUB_OUTPUT" in os.environ:
        with open(os.environ["GITHUB_OUTPUT"], "a", encoding="utf-8") as f:
            f.write(f"{name}={value}\n")


def write_catalog(catalog):
    """catalog/products.json を、手で編集しやすい書き方（1行に1件、商品はシリーズの変わり目に空行）で書き出す。"""
    def line(obj):
        return json.dumps(obj, ensure_ascii=False, separators=(", ", ": ")).replace("{", "{ ", 1)[:-1] + " }"

    lines = ["{"]
    for key, items in catalog.items():
        lines.append(f'  "{key}": [')
        previous = None
        for item in items:
            if key == "products" and previous is not None and item["series"] != previous:
                lines.append("")
            lines.append(f"    {line(item)},")
            previous = item.get("series")
        lines[-1] = lines[-1].rstrip(",")
        lines.append("  ],")
    lines[-1] = lines[-1].rstrip(",")
    lines.append("}")
    CATALOG.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
