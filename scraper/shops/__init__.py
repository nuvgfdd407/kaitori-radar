"""対象店舗の一覧。

各店舗モジュールは ID・NAME・SHORT（表の見出し用の略称）・URL と fetch(http) を持つ。
fetch は {"jan", "name", "price", "url"} の辞書のリストを返す（新品・買取中のものだけ）。
店舗を増やすときは、モジュールを作ってここに追加する。並び順は比較表の列の順になる。
"""
from . import guest, homura, ichome, kaikyo, keitaigod, morimori, panda, rudeya, shouten, toban, wiki

SHOPS = [homura, shouten, kaikyo, ichome, toban, rudeya, wiki, morimori, keitaigod, guest, panda]
