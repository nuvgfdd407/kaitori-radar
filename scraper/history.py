"""買取価格の記録（日ごと）。商品ページの「買取価格の推移」のグラフに使う。

    python -m scraper.history --backfill   # これまでの prices.json のコミットから、過去の日の記録を作る

- data/history/<日付>.json に、その日の最後に取得した各店舗の価格を1日1ファイルで残す
  （15分ごとの更新のたびに、その日のファイルを上書きしていく）
- 取得に失敗している店舗は、前回の価格を使い回しているだけなので記録しない
  （その日のうちに取得できていれば、そのときの価格が残る）
- 1日1ファイルにしているのは、毎回のコミットで変わるのをその日のファイルだけにするため
"""
import argparse
import json
import subprocess
import sys
from datetime import datetime, timedelta, timezone

from .common import PRICES, ROOT

HISTORY = ROOT / "data" / "history"
JST = timezone(timedelta(hours=9))


def record(data, day):
    """prices.json と同じ形の data から、day（"2026-10-02" の形）の記録を更新する。変わったら True。"""
    path = HISTORY / f"{day}.json"
    previous = _read(path)
    today = {jan: dict(prices) for jan, prices in previous.items()}
    ok_shops = {s["id"] for s in data["shops"] if s["ok"]}
    for p in data["products"]:
        prices = {shop: offer["price"] for shop, offer in p["prices"].items() if shop in ok_shops}
        kept = {shop: price for shop, price in today.get(p["jan"], {}).items() if shop not in ok_shops}
        if prices or kept:
            today[p["jan"]] = {**kept, **prices}
        else:
            today.pop(p["jan"], None)
    if today == previous:
        return False
    _write(path, today)
    return True


def load(end, days):
    """end（date）までの days 日分の記録を、古い順に [(日付の文字列, {JAN: {店舗: 価格}})] で返す。"""
    result = []
    for i in range(days - 1, -1, -1):
        day = (end - timedelta(days=i)).isoformat()
        prices = _read(HISTORY / f"{day}.json")
        if prices:
            result.append((day, prices))
    return result


def backfill():
    """Git に残っている prices.json の各版から、まだ記録のない日の記録を作る。"""
    shas = subprocess.run(
        ["git", "log", "--reverse", "--format=%H", "--", str(PRICES.relative_to(ROOT))],
        cwd=ROOT, capture_output=True, text=True, check=True,
    ).stdout.split()
    existing = {p.stem for p in HISTORY.glob("*.json")}
    made = set()
    for sha in shas:
        shown = subprocess.run(
            ["git", "show", f"{sha}:{PRICES.relative_to(ROOT).as_posix()}"],
            cwd=ROOT, capture_output=True, check=True,
        ).stdout
        data = json.loads(shown.decode("utf-8"))
        day = datetime.fromisoformat(data["updated_at"]).astimezone(JST).date().isoformat()
        if day in existing:
            continue
        record(data, day)
        made.add(day)
    print(f"{len(shas)}個の版から、{len(made)}日分の記録を作りました: {', '.join(sorted(made)) or 'なし'}")


def _read(path):
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def _write(path, prices):
    # 1商品1行にして、Git の差分を見やすくする
    lines = [f'  "{jan}": {json.dumps(shops, separators=(",", ":"))}' for jan, shops in sorted(prices.items())]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("{\n" + ",\n".join(lines) + "\n}\n", encoding="utf-8")


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description="買取価格の日ごとの記録")
    parser.add_argument("--backfill", action="store_true", help="過去の prices.json のコミットから記録を作る")
    args = parser.parse_args()
    if args.backfill:
        backfill()
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
