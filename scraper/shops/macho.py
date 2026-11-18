"""買取マッチョ（ALC株式会社）。

トレカ（ポケモン・ワンピース・ドラゴンボール フュージョンワールド・遊戯王）の宅配買取の価格の一覧（/buyback-prices）を使う。
価格を出すのは毎日14時〜24時だけで、それ以外の時間は全商品の価格が null で「調整中」（hidden_label）になる（HOURS）。
一覧は ?game=…&type=…（package が BOX・パック、set がスペシャルセット、single がシングル）で絞り込め、1ページ96件で続きは &page=N。
ページに埋め込まれたデータ（self.__next_f.push の中）の "rows" に、商品ごとに
{"name", "model_number"（型番。BOX は「M6a」「OP-17」のような弾の記号）, "product_type", "condition", "kaitori_price",
"hidden_label"（価格を隠しているときの理由。「調整中」など）, "rank_value"（PSA の点数）, "image_url"} が入っている。
hidden_label がある行と、価格が null か 0 の行（画面では「査定」）は使わない。
同じ BOX が状態ごとに別の行で載っている（condition）。使うのは、ポケモン・遊戯王の「Shrink」（シュリンク有り）、
ワンピース・ドラゴンボールの「Tape」（テープ付き）、スペシャルセットの「Normal」と「Pokecen box」（ポケセン未開封）だけ。
シュリンク無し（No shrink）・ペリ無（No shrink/Pull tab）・テープカット（Tape cut）・統一パック（Unified pack）・
バラのパック（Pack）・カートン（Carton）・箱なし（No box）の行は使わない。
スペシャルセットの一覧に混ざっている、セットの中身だけの行（「…9種セット」プロモのみ (27枚)）と、
シングルのプロモカード（型番「SV-P 062」の「YU NAGABA イーブイ プロモ」）も使わない。
JAN は載っていない（ボードゲームなど一部だけ型番が JAN）ので、BOX は商品名のセット名で突き合わせる（card_key）。
遊戯王などの「…スペシャルパック「遊☆戯☆王 オリジナル アートワーク コレクション」日本版 ボックス」のような名前は、「」の中をセット名にする。
PSA 鑑定品はポケモンカードの PSA10 だけ（type=single&grade=psa10）。名前は「ブラッキーGX」、型番は「SM1M 069/060」
（プロモは「SM-P 281」）のように別々に載っている。名前の書き方がほかの店舗と違うもの（「お誕生日のピカチュウ」
「マクドナルドピカチュウ」「長場雄 ブラッキー」）は、カタログの書き方にそろえる（_psa_name）。
店頭買取は止めていて、宅配買取だけ受け付けているので、どの価格も買取方法は郵送。
商品ページはないので、出品の URL は型番で絞り込んだ一覧にする。
"""
import json
import re
from urllib.parse import urlencode

from ..cards import card_key
from ..psa import psa_key
from ..text import find_jan

ID = "macho"
NAME = "買取マッチョ"
SHORT = "マッチョ"
URL = "https://kaitori.alc-japan.co.jp/"
HOURS = (14, 24)  # 価格を出している時間（日本時間）

# BOX・スペシャルセットの一覧（ポケモンのシングルとバルクは取らない）
CARD_LISTS = [{"game": "pokemon", "type": "package"}, {"game": "pokemon", "type": "set"},
              {"game": "onepiece"}, {"game": "dragonball"}, {"game": "yugioh"}]
PSA_LIST = {"game": "pokemon", "type": "single", "grade": "psa10"}
# 新品・未開封の状態（シュリンク有り・テープ付き・スペシャルセット・ポケセン未開封）
NEW = {"Shrink", "Tape", "Normal", "Pokecen box"}
PAGE_SIZE = 96
MAX_PAGES = 10


def fetch(http):
    offers = []
    for params in CARD_LISTS:
        for row in _rows(http, params):
            price = _price(row)
            if price and _sealed(row):
                offers.append({"jan": find_jan(row["model_number"]), "key": card_key(_set_name(row["name"])),
                               "name": row["name"], "price": price, "url": _page(row), "mode": "郵送"})
    return offers + [o for o in fetch_psa(http) if o["price"]]


def fetch_psa(http):
    """PSA 鑑定品の出品（scraper.psa_catalog でも使う）。
    psa_catalog が動く朝（9:50）は全件「調整中」なので、価格の出ていないカードも price=None で返す（fetch では使わない）。"""
    offers = []
    for row in _rows(http, PSA_LIST):
        name = _psa_name(row["name"])
        number = _psa_number(row["model_number"])
        key = psa_key("pokemon", row["rank_value"], name, number)
        if key:
            url = _page(row)
            display = " ".join(filter(None, [row["rank_value"], name, row["rarity"], number]))
            offers.append({"jan": None, "key": key, "name": display, "price": _price(row), "url": url, "mode": "郵送",
                           "psa": {"game": "pokemon", "grade": row["rank_value"], "name": name, "rarity": row["rarity"],
                                   "number": number, "image": row["image_url"], "page": url}})
    return offers


def _rows(http, params):
    """一覧の行を順に返す。"""
    for page in range(1, MAX_PAGES + 1):
        html = http.get(URL + "buyback-prices", params={**params, "page": page}).text
        chunks = re.findall(r'self\.__next_f\.push\(\[1,"(.*?)"\]\)</script>', html, re.S)
        payload = "".join(json.loads(f'"{c}"') for c in chunks)
        rows, _ = json.JSONDecoder().raw_decode(payload, payload.index('"rows":[') + len('"rows":'))
        yield from rows
        if len(rows) < PAGE_SIZE:
            break


def _price(row):
    """画面に出ている買取価格。「調整中」などで隠している行や、価格のない「査定」の行は None。"""
    return None if row.get("hidden_label") else row.get("kaitori_price") or None


def _sealed(row):
    """未開封の BOX・セットの行か（中身だけの「プロモのみ」の行や、シングルのプロモカード「SV-P 062」は除く）。"""
    return row["condition"] in NEW and "のみ" not in row["name"] and not re.search(r"-P \d+$", row["model_number"])


def _set_name(name):
    """「…スペシャルパック「遊☆戯☆王 オリジナル アートワーク コレクション」日本版 ボックス」→「」の中。"""
    m = re.search(r"「([^」]+)」", name)
    return m.group(1) if m else name


def _psa_name(name):
    """カード名をカタログの書き方にそろえる。
    「カメックス: プロモ[S8a-P 003/025](…)」→「カメックス」（後ろは型番と収録パック）、
    「長場雄 ブラッキー」→「ブラッキー(長場雄)」（この店の「シャワーズ (YU NAGABA)」やほかの店舗と同じ形）、
    「マクドナルドピカチュウ」→「ピカチュウ(マクドナルド)」、
    「お誕生日のピカチュウ」→「のピカチュウ(お誕生日)」（カードの名前は「＿＿＿＿＿のピカチュウ」）。"""
    name = re.split(r"\s*[:：]", name)[0]
    name = re.sub(r"^(長場雄|マクドナルド)\s*(.+)", r"\2(\1)", name)
    return re.sub(r"^お誕生日(の.+)", r"\1(お誕生日)", name)


def _psa_number(model):
    """型番をカード番号にする。「SM1M 069/060」→「069/060」、プロモの「SM-P 281」→「281/SM-P」。"""
    code, _, number = model.rpartition(" ")
    return f"{number}/{code}" if "/" not in number and code.endswith("-P") else number


def _page(row):
    """型番で絞り込んだ一覧の URL。"""
    params = {"game": row["game"], "type": row["product_type"], "code": row["model_number"]}
    if row["rank_value"]:
        params["grade"] = row["rank_value"].lower()
    return URL + "buyback-prices?" + urlencode(params)
