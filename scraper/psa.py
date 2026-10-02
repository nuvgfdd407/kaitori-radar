"""PSA 鑑定品（トレカのシングルカード）を、店舗をまたいで比べられる形にする。

鑑定品には JAN がないので、ゲーム・PSA の点数・カード番号・カード名で突き合わせる（psa_key）。
カード番号だけでは別のカードとぶつかる（070/066 がシロナとナタネ など）ので、名前もそろえて使う。
名前は（）［］【】の中の注記、レアリティ、「仕様」、空白や記号を取り除いてそろえる。
ただし、マスターボールミラー・1ED・英語版など、同じ番号で別の価格になるものは区別する（_variant）。
"""
import re
import unicodedata

GAMES = ("pokemon", "onepiece", "yugioh")
_RARITY = r"(?:SAR|SR|UR|AR|SA|CHR|CSR|MUR|HR|BWR|MA|ACE|RRR|RR|R|PR|MM|SSR|S|K|U|C|P|PROMO|-)"
_LANGUAGE = re.compile(r"英語版|韓国語版|中国版|簡体字|繁体字|海外版|English", re.IGNORECASE)
_LANGUAGE_CODES = {"英語版": "en", "韓国語版": "ko", "中国版": "zh", "簡体字": "zh", "繁体字": "zh"}
# 「PSA10 ブラッキーVMAX SA 095/069」「ポケモンカード PSA10 リーリエ SR 119/114」のような商品名
_NAME = re.compile(rf"(PSA\s*\d+)\s+(.*?)(?:\s+({_RARITY}))?(?:\s+(1ED))?\s+(\d{{1,3}}/[\w\-/]+|\d{{3}})(?:\s+\S+)?$")


def _nfkc(text):
    return unicodedata.normalize("NFKC", text or "").strip()


def psa_key(game, grade, name, number):
    """「pokemon|PSA10|119/114|リーリエ|」のような比較用の文字列。点数か番号がなければ None。"""
    grade = re.sub(r"\s+", "", _nfkc(grade)).upper()
    number = _number(number)
    if not re.fullmatch(r"PSA\d+", grade) or not number:
        return None
    return f"{game}|{grade}|{number}|{_core(name)}|{_variant(name)}"


def parse_name(text):
    """「PSA10 名前 レアリティ 番号」の形の商品名を（点数, 名前, レアリティ, 番号）に分ける。読めなければ None。"""
    m = _NAME.search(_nfkc(text))
    if not m:
        return None
    grade, name, rarity, first_edition, number = m.groups()
    if rarity == "MM":  # ホムラはマスターボールミラーを「MM」と書く
        name += "(マスターボールミラー)"
    return grade.replace(" ", ""), name + (" 1ED" if first_edition else ""), rarity, number


def _number(number):
    text = _nfkc(number).upper().replace(" ", "").replace("SM/P", "SM-P").replace("S/P", "S-P")
    m = re.search(r"(\d{1,3})/([A-Z0-9\-]+)", text)
    if m:
        return f"{int(m.group(1)):03d}/{m.group(2)}"
    if re.fullmatch(r"\d{1,3}", text):
        return f"{int(text):03d}"
    # ワンピース「OP05-119」、遊戯王「QCCU-JP001」など
    m = re.search(r"[A-Z0-9]+-[A-Z0-9]+", text)
    return m.group(0) if m else None


def _core(name):
    text = _nfkc(name)
    text = re.sub(r"\([^)]*\)|\[[^\]]*\]|【[^】]*】", " ", text)
    text = re.sub(r":?1ED", " ", text)
    text = re.sub(rf"(?<![A-Za-z]){_RARITY}(?:仕様)?(?![A-Za-z])", " ", text)
    text = text.replace("仕様", "")
    return re.sub(r"[\s・&＆!！~〜\-_]", "", text).lower()


def _variant(name):
    text = _nfkc(name)
    flags = []
    if "1ED" in text:
        flags.append("1ED")
    if "マスターボールミラー" in text or re.search(r"(?<![A-Za-z])MM(?![A-Za-z])", text):
        flags.append("masterball")
    elif "モンスターボールミラー" in text:
        flags.append("monsterball")
    elif re.search(r"ミラー|ホイル", text):
        flags.append("mirror")
    # ワンピースのコミックパラレル・パラレルは、同じ番号の通常のカードとは別のカード
    if re.search(r"コミパラ|コミックパラレル|Manga", text, re.IGNORECASE):
        flags.append("comic")
    elif "パラレル" in text:
        flags.append("parallel")
    language = _LANGUAGE.search(text)
    if language:
        flags.append(_LANGUAGE_CODES.get(language.group(0), "other"))
    return "+".join(flags)
