"""対象店舗の一覧。

各店舗モジュールは ID・NAME・SHORT（表の見出し用の略称）・URL と fetch(http) を持つ。
fetch は {"jan", "name", "price", "url"} の辞書のリストを返す（新品・買取中のものだけ）。
店舗を増やすときは、モジュールを作ってここに追加する。並び順は比較表の列の順になる。
買取wiki（wiki.py）は、2026-10-08 から GitHub Actions からのアクセスを拒否されるようになったので外している。
スマスピ（smaspi.py）は、2026-11-18 の16時ごろからサイトの価格が全部0円になっているので、戻るまで外している。
"""
from . import (aboutec, amemoba, base, birth, birth_store, bluerocket, club, daiwan, dragon, golden, guest, guild, hachi, hokusai,
               homura, ichome, jcka, kaden, kaikyo, kaumobile, keitaigod, linxas, lounge, macho, mafia, masai, mirai, mobax,
               mobilemix, morimori, onmyplan, panda, pocket, quick, rakuen, rudeya, sakumoba, shinsoku, shouten, somurie,
               star, toban, tojo, torecabank, torecabank_store)

SHOPS = [homura, shouten, kaikyo, ichome, toban, rudeya, morimori, keitaigod, guest, panda, rakuen, quick, amemoba,
         dragon, sakumoba, kaumobile, aboutec, pocket, kaden, mirai, tojo, hachi, guild, mobax, somurie, linxas, daiwan,
         star, jcka, base, onmyplan, mobilemix, bluerocket, macho, hokusai, masai, mafia,
         lounge, shinsoku, torecabank, torecabank_store, club, birth, birth_store, golden]
