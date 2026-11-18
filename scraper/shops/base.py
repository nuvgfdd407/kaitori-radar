"""買取BASE。

WordPress のサイトで、ジャンルごとの買取価格表のページ（3ページ）に、見出しと表が並んでいる（ふつうの HTML）。
ページの先頭に「更新日：2026年11月18日」があり、30日以上前のページは使わない。JAN は載っていない。
表の1行は「商品名 / 買取価格 / 備考」（トレカは「商品名 / 定価 / 買取価格」）。「要問合せ」「要相談」「買取停止」の行は飛ばす。
- iPhone（?p=9907）: 「新品未開封品のみの買取」。「18 Pro 256GB」「17 e 256GB」「Air 256GB」のように「iPhone」を省いた
  機種＋容量の行で、キャリアの区別はない（SIMフリー版として扱う）。価格は一番高い色の価格で、色で価格が違うときは
  備考に「青,黒-1,500､銀-4,000」のように色（漢字1文字）ごとの減額が書かれているので、全色の価格にする。
  減額の色を公式の色名にできない行は、その色だけ高い価格になってしまうので使わない
- Pixel（同じページ）: 「Pixel 11Pro XL 256GB」のような機種＋容量の行。備考の「キャリア版要問合せ」のとおり SIMフリー版の価格。
  「Isai Blue -4,000」のような色の減額も同じように読む
- ゲーム機（?p=67）: PS5・Xbox・PlayStation Portal は商品名の括弧に型番（「CFI-2000A01」「RRT-00015」など）があるので、
  カタログの "model" で JAN を探す。Meta Quest はカタログの商品名と同じ名前。型番のない Switch の行は GAME_JANS で JAN を決める
  （「Switch Lite 各色」は全色の行で、備考の「グレー,ターコイズ-500」の減額を引く）。
  備考の製造時期の条件（「※2024年以前に製造された商品は買取不可」「2026年10月以降製造版 -2,000」）は、
  ほかの店（mobax・guild）と同じく表の価格のまま "note" にする
- AirPods（同じページ）: 商品名に型番がある
- トレカ BOX（?p=9534）: 見出し「BOX買取」の下の表。「BOXは全て新品未開封/シュリンク付きのみの買取」。名前はセット名だけ。
  ポケカ（「ストームエメラルダ」）はそのまま card_key でカタログの "names" と突き合わせる。
  ワンピース（「決戦の刻」）はカタログの "names" が「OP-16 決戦の刻」の形なので、弾の記号を外した名前で JAN を探す
  （名前の書き方が違う行は ONEPIECE_NAMES）。表の下の「国内生産分以外は買取不可又は減額」は "note" にする。
  シングルカードの表は「買取停止中」なので使わない
"""
import re
import unicodedata
from datetime import date, timedelta

from bs4 import BeautifulSoup

from ..apple import apple_offer
from ..cards import card_key
from ..common import CATALOG, load_json
from ..phones import phone_color, phone_colors, phone_key
from ..text import parse_yen

ID = "base"
NAME = "買取BASE"
SHORT = "BASE"
URL = "https://kaitori-base.com/"

PHONE_PAGE = URL + "?p=9907"
GAME_PAGE = URL + "?p=67"
CARD_PAGE = URL + "?p=9534"
STALE_DAYS = 30
# 型番のない Switch の行 → JAN（「各色」の行は {色: JAN}）
GAME_JANS = {
    "Switch 2 (日本語・国内専用)": "4902370553024",
    "Switch 2 (多言語対応版)": "4902370552683",
    "Switch 2 (日本語・国内専用) ゼルダの伝説 40周年 アニバーサリーエディション": "4902370554595",
    "Switch 2 (日本語・国内専用) スプラトゥーン レイダース セット": "4902370554779",
    "Switch 2 (日本語・国内専用) Pokémon LEGENDS Z-A セット": "4902370553505",
    "Switch 2 (日本語・国内専用) マリオカート ワールド セット": "4902370553031",
    "EL Switch ホワイト": "4902370548495",
    "EL Switch ネオン": "4902370548501",
    "EL Switch ゼルダの伝説版": "4902370550481",
    "EL Switch マリオ版": "4902370551495",
    "EL Switch ポケモン版": "4902370550412",
    "EL Switch スプラトゥーン版": "4902370549706",
    "新型Switch 2022年版 ネオン": "4902370550733",
    "新型Switch 2022年版 グレー": "4902370551198",
    "Switch Lite ハイラルエディション": "4902370552232",
    "Switch Lite どうぶつの森セット まめきちver": "4902370551457",
    "Switch Lite どうぶつの森セット しずえver": "4902370551471",
    "Switch Lite 各色": {"グレー": "4902370542929", "イエロー": "4902370542936", "ターコイズ": "4902370542943",
                       "コーラル": "4902370545302", "ブルー": "4902370547672"},
}
# 減額の色の漢字のうち、phones.py の別名にないもの（iPhone 18 Pro・18 Pro Max の色）→ 英語の別名
KANJI_COLORS = {"青": "glacier", "黒": "black", "銀": "silver"}
# ワンピースの行の名前のうち、カタログの名前（弾の記号を外したもの）と書き方が違うもの
ONEPIECE_NAMES = {"THE BEST ザベスト": "ONE PIECE CARD THE BEST", "THE BEST ザベスト vol.2": "ONE PIECE CARD THE BEST vol.2",
                  "ONEPIECE Heroines Edition": "Heroines Edition"}
ONEPIECE_NOTE = "国内生産分以外は買取不可または減額の場合あり"
# カタログのワンピースの "names" の頭の弾の記号（「OP-16 」「EB-04 」「PRB-01 」「OP01 」）
_SET_CODE = re.compile(r"^[A-Z]+-?\d+\s+")
_UPDATED = re.compile(r"更新日[:：]\s*(\d{4})年\s*(\d{1,2})月\s*(\d{1,2})\s*日")
# 「青,黒-1,500」「Isai Blue -4,000」→（色, 減額）
_DEDUCTION = re.compile(r"([^-]+?)\s*-\s*(\d{1,3}(?:,\d{3})*)")
# 商品名の括弧の中の型番（「(CFI-2000A01)」「(EP2-10065)」）。全角の括弧は NFKC で半角にしてある
_MODEL = re.compile(r"\(\s*([A-Z0-9]+(?:-[A-Z0-9]+)+)\s*\)")


def fetch(http):
    offers = []
    for _, (name, price, remark) in _read_rows(http, PHONE_PAGE):
        if re.match(r"\d{2}|Air|Duo", name):  # iPhone の行は「iPhone」が省かれている
            name = "iPhone " + name
        price = _price(price)
        key = phone_key(name) if price else None
        colors = _colors(key, remark, price) if key else {}
        if colors:
            offers.append({"jan": None, "key": key, "name": name, "price": price, "url": PHONE_PAGE, "colors": colors})

    models, names, onepiece = _catalog()
    for _, (name, price, remark) in _read_rows(http, GAME_PAGE):
        price = _price(price)
        if not price:
            continue
        if "AirPods" in name:
            offers.append(apple_offer(name, price, GAME_PAGE))
            continue
        model = _MODEL.search(name)
        jans = GAME_JANS.get(name) or (models.get(model.group(1)) if model else names.get(name.upper()))
        if isinstance(jans, dict):  # 「各色」の行
            cut = _deductions(remark)
            if set(cut) - set(jans):  # 知らない色の減額があれば、その色だけ高くなるので使わない
                continue
            targets = {jan: price - cut.get(color, 0) for color, jan in jans.items()}
        else:
            targets = {jans: price}
        for jan, p in targets.items():
            offer = {"jan": jan, "name": name, "price": p, "url": GAME_PAGE}
            if "製造" in remark:
                offer["note"] = remark.lstrip("※")
            offers.append(offer)

    for section, (name, _, price) in _read_rows(http, CARD_PAGE):
        price = _price(price)
        if "BOX" not in section or not price:
            continue
        if "ONE PIECE" in section:
            jan = onepiece.get(card_key(ONEPIECE_NAMES.get(name, name)))
            offers.append({"jan": jan, "name": name, "price": price, "url": CARD_PAGE, "note": ONEPIECE_NOTE})
        else:
            offers.append({"jan": None, "key": card_key(name), "name": name, "price": price, "url": CARD_PAGE})
    return offers


def _read_rows(http, page):
    """表の（見出し（直前の h2 と h3）, 行の最初の3つのセルの文字）を順に返す。更新日が古いページは何も返さない。"""
    soup = BeautifulSoup(http.get(page).content, "html.parser")
    article = soup.select_one("article")
    updated = _UPDATED.search(article.get_text())
    if updated and date(*map(int, updated.groups())) <= date.today() - timedelta(days=STALE_DAYS):
        return
    for table in article.select("table"):
        headings = (table.find_previous("h2"), table.find_previous("h3"))
        section = " ".join(h.get_text(" ", strip=True) for h in headings if h)
        for row in table.select("tr"):
            cells = [unicodedata.normalize("NFKC", " ".join(td.get_text(" ").split())) for td in row.select("td")]
            yield section, (cells + ["", "", ""])[:3]


def _price(text):
    """「208,500」→ 208500。「要問合せ」「買取停止」などは None。"""
    return parse_yen(text) if re.fullmatch(r"[\d,]+", text) else None


def _deductions(remark):
    """備考の「青,黒-1,500､銀-4,000」→ {"青": 1500, "黒": 1500, "銀": 4000}。"""
    cut = {}
    for words, amount in _DEDUCTION.findall(remark):
        for word in re.split(r"[,、]", words):
            if word.strip():
                cut[word.strip()] = parse_yen(amount)
    return cut


def _colors(key, remark, price):
    """{公式の色名: 価格}。備考の色ごとの減額を引く。扱っていない機種と、減額の色を読めない行は空。"""
    colors = dict.fromkeys(phone_colors(key), price)
    for word, amount in _deductions(remark).items():
        # 色の漢字（「青」「銀」など）や色名（「Isai Blue」）を、その機種の公式の色名にする
        color = phone_color(key, word) or phone_color(key, KANJI_COLORS.get(word))
        if not color:  # 無視するとその色だけ高い価格になるので、行ごと使わない
            return {}
        colors[color] = price - amount
    return colors


def _catalog():
    """カタログの {型番: JAN}・{商品名（大文字）: JAN}・{ワンピースの弾の記号を外したセット名の card_key: JAN}
    （この店は JAN を載せていないので）。"""
    products = load_json(CATALOG)["products"]
    return ({p["model"]: p["jan"] for p in products if p.get("model")},
            {unicodedata.normalize("NFKC", p["name"]).upper(): p["jan"] for p in products},
            {card_key(_SET_CODE.sub("", name)): p["jan"]
             for p in products if p["series"] == "onepiece" for name in p.get("names", [])})
