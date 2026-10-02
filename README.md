# 買取レーダー

Nintendo Switch 2・Nintendo Switch・PlayStation 5・Xbox Series X|S・Steam Deck などのゲーミングPC・VRヘッドセットと、
iPhone 18・17・16シリーズ（SIMフリー版）、iPad・Apple Watch・AirPods、Androidスマホ（Google Pixel・Galaxy・Xperia・AQUOS）、
ポケモンカード・ワンピースカードなどの未開封BOXの
**新品（未開封）買取価格**を、買取店ごとに比較するサイトです。

- 対象店舗: 買取ホムラ・買取商店・海峡通信・買取一丁目・買取当番・買取ルデヤ・買取wiki・森森買取・ケータイゴッド・
  ゲストモバイル・PANDA買取・トレカラウンジ・トレカクラブ・トレカバース・ゴールデンホビー
  （15店舗。トレカラウンジ・トレカクラブ・トレカバース・ゴールデンホビーは PSA 鑑定品だけ）
- 店舗ごとの価格、最高値、定価との差益を一覧表示
- 日本時間 10:00〜21:00 に15分ごとに価格を確認（GitHub Actions。開始の合図は Cloudflare の Worker）
- 商品画像は Yahoo!ショッピングの商品検索APIから取得（1日1回）

## 仕組み

```
GitHub Actions（毎日 9:50。Cloudflare の Worker が開始する）
  └ python -m scraper.images
      └ 画像がない商品だけ JAN コードで Yahoo!ショッピングを検索し、画像を public/images/ に保存

GitHub Actions（10:07〜20:52 に15分ごと。Cloudflare の Worker が開始する）
  └ python -m scraper.update
      ├ 各店舗のサイトから価格を取得（店舗ごとに並行して実行）
      ├ catalog/products.json の商品と JAN コード（iPhone は機種＋容量）で突き合わせ、画像も載せる
      ├ 価格が変わったときだけ public/data/prices.json を更新してコミット
      └ 日ごとの価格の記録 data/history/<日付>.json も更新（その日の最後の価格が残る）
  └ python -m scraper.build（価格が変わったときだけ）
      └ public/ と prices.json から、公開用のサイトを dist/ に組み立てる
            ↓
dist/ を Cloudflare Pages に公開
```

公開するページ（HTMLは `scraper/build.py` と `scraper/templates.py` が作る）

| URL | 内容 |
|---|---|
| `/` | 全商品の比較表 |
| `/nintendo/`・`/apple/`・`/tcg/` など | ジャンルごとの比較表（シリーズごとに分けて並べる。シリーズが1つだけのジャンルは作らず、シリーズのページを使う） |
| `/switch2/`・`/ps5/`・`/iphone17/` など | シリーズごとの比較表（店舗数は、そのシリーズを扱っている店舗だけで数える） |
| `/item/<JAN>/` | 商品ごとの、店舗別の価格（高い順）と、最近30日の価格の推移のグラフ・前日比 |
| `/cart/` | 比較リスト（検索結果に出さない。サイトマップにも載せない） |
| `/sitemap.xml` | 上のすべてのページの一覧（組み立てるときに自動で作る） |

一覧の上の切り替えボタンは2段で、上の段がジャンル（すべて・Nintendo・PlayStation・Xbox・Apple・Android・トレカ・その他）、
下の段が選んでいるジャンルの中のシリーズ。ジャンルとシリーズの分け方は `catalog/products.json` の
`categories` と、各シリーズの `category` で決める（価格の更新を待たずに、サイトを組み立て直せば反映される）。

一覧はHTMLとして組み立てておく（検索エンジンが JavaScript なしで価格を読めるように）。
一覧の1行は 商品名・定価・最高買取・差益 だけで、行を開く（`<details>`）と店舗ごとの価格が出る（店舗が増えても横に広がらない）。
`public/app.js` は一覧の絞り込み（検索）と並び替え、一覧の切り替え、切れた画像の差し替え、比較リストを行う。
一覧の切り替え: 一覧のページでジャンル・シリーズのボタンを押すと、ページ全体を読み込み直さずに、
次のページのHTMLを読み込んでボタンと一覧（`#content`）だけを入れ替える（URLは変わり、戻るボタンも使える）。
ボタンに指やマウスが乗った時点で先に読み込む。絞り込みの文字と並び順は、切り替えたあとも引き継ぐ。
絞り込みは全角・半角、大文字・小文字、ひらがな・カタカナ、空白や記号の違いを区別しない（空白で区切ると AND）。
英語の名前は読み（`scraper/templates.py` の `READINGS`）でも探せる（例: 「すいっち」「あいふぉん17ぷろ」）。

比較リスト: 一覧や商品ページの「＋」で選んだ商品と数量を、訪問者のブラウザ（localStorage）にだけ保存する。
最後に変更してから1日で自動で消える。比較リストのページでは `data/prices.json` を読み込み、
「商品ごとに最高値の店へ売る場合」と「1店舗にまとめて売る場合」の合計を計算して表示する。

## ファイル構成

| パス | 内容 |
|---|---|
| `catalog/products.json` | 対象商品の一覧（JAN・シリーズ・表示名・型番・定価）と、ジャンル・シリーズの分け方。**手で管理する** |
| `catalog/images.json` | 商品画像のURL（`scraper.images` が自動で作る） |
| `scraper/shops/*.py` | 店舗ごとの取得処理 |
| `scraper/phones.py` | スマホ（iPhone・Pixel・Galaxy・Xperia・AQUOS）の商品名から「機種＋容量（＋キャリア）」と色を読み取る（突き合わせ用） |
| `scraper/cards.py` | トレカの商品名からセット名を取り出す（JAN を載せていない店舗との突き合わせ用） |
| `scraper/update.py` | 全店舗の取得と `prices.json` の書き出し |
| `scraper/images.py` | Yahoo!ショッピングからの商品画像の取得 |
| `scraper/build.py`・`scraper/templates.py` | 公開用のサイトを `dist/` に組み立てる（ページのHTMLのひな形は templates.py） |
| `public/` | そのまま公開するファイル（CSS・JavaScript・画像・robots.txt・404ページ・価格データ） |
| `dist/` | 組み立てたサイト（生成物なので Git には入れない） |
| `data/history/` | 日ごとの店舗別の価格の記録（`scraper/history.py`。商品ページのグラフに使う） |
| `reports/unmatched.json` | カタログにない2万円以上の商品（新しい本体の登録漏れチェック用。公開はしない） |
| `.github/workflows/update-prices.yml` | 15分ごとの価格の更新 |
| `.github/workflows/update-images.yml` | 1日1回の画像の更新 |
| `trigger/` | 決まった時刻に価格と画像の更新を始めさせる Cloudflare Worker |

## 手元で動かす

```bash
python -m venv .venv
.venv/Scripts/python -m pip install -r requirements.txt   # macOS / Linux は .venv/bin/python
.venv/Scripts/python -m scraper.update
.venv/Scripts/python -m scraper.build
python -m http.server 8765 --directory dist
```

ブラウザで http://localhost:8765 を開きます。画面やひな形を変えたら、`scraper.build` を実行し直してください。

## 商品を追加する

1. `reports/unmatched.json` に、カタログにない高額商品が出ていないか確認する
2. 本体なら `catalog/products.json` の `products` に追加する（並び順が表の標準の並びになる）
3. 本体でないもの（コントローラーなど）は `ignore` に追加すると、以後は報告されなくなる

同じ商品が店舗によって別のJAN（新旧のJANなど）で載っているときは、`"aliases": ["<別のJAN>"]` を書くと同じ商品として扱う
（同じ店舗に両方あるときは高い方の価格を使う）。

定価（`msrp`）は**メーカー希望小売価格、またはメーカー公式ストアの販売価格（税込）**です
（Steam Deck・Steam Machine は KOMODO、Meta Quest は Meta ストア、iPhone は Apple の価格）。
値上げがあったら更新してください（2025〜2026年は各社とも何度も値上げしている）。
販売終了した商品は、販売していたときの最後の価格にする。
限定版など定価を決めにくい商品は `null` にしておくと、表では「—」になり差益も出しません。

発売前の商品には発売日（`"release": "2026-10-29"`）を書いておくと、発売日までは「10/29発売」と表示し、
差益は出しません（発売前の買取価格は仮のことが多いため）。発売日を過ぎると自動で通常の表示になります。

### iPhone

iPhone は店舗によって色ごとに別の商品として載っていたり、JAN がなかったりするので、
**機種＋容量**（`scraper/phones.py` の `phone_key`。例: `iPhone 17 Pro 256GB`）と**色**で突き合わせる。

- 1行＝機種＋容量＋色（例: `iPhone 17 Pro 256GB シルバー`）。`jan` はその色の JAN
- 色の名前は店舗ごとに書き方が違うので（orange／コズミックオレンジ／橙 など）、
  `scraper/phones.py` の `COLORS` で公式の日本語名にそろえる。新しい機種が出たら `COLORS` にも色を追加する
- 色を区別していない店舗（同じ価格でどの色も買い取る商品）の価格は、全色に当てはめる
- 対象は SIMフリー版の新品未開封だけ（「開封済未使用」などの価格は使わない）
- カタログの iPhone は、シリーズIDを `iphone` で始める
- 新しい機種が出たら、各店舗モジュールの iPhone のカテゴリ（`IPHONE_SUBS` など）にも追加する

### Google Pixel

- iPhone と同じく、機種＋容量＋色（例: `Pixel 10 Pro 256GB Obsidian`）の SIMフリー版の新品未開封。色は Google の英語の名前
- Pixel 11・10（10a を含む）・9（9a を含む）シリーズ。JAN がわかる組み合わせだけ（Pixel 9 Pro XL などは JAN がわからず入れていない）
- 買取商店はキャリア版（docomo・au など）も別の価格で載せているので、SIMフリーの行だけを使う
- 買取一丁目は Pixel のカテゴリが細かいので、商品名の検索（「Pixel」）でまとめて取る

### Galaxy・Xperia・AQUOS

- SIMフリー版と**キャリア版（docomo・au・SoftBank・楽天モバイル・Y!mobile）を別の商品**として載せる。
  UQ mobile 版は au 版と同じ機種なので au 版として扱う
- 1行＝機種＋容量＋キャリア＋色（例: `Galaxy S26 Ultra 256GB docomo版 ブラック`）。突き合わせのキーは
  `Galaxy S26 Ultra 256GB docomo`（`scraper/phones.py` の `android_key`）。キャリアは店舗のカテゴリでわかるときは
  それを使い、わからないときは商品名（「docomo版」や SC-53G のようなキャリアごとの型番）から読む
- 同じ容量でメモリ違いがある機種（Xperia 1 VIII・1 VII の 512GB）は「512GB（メモリ16GB）」のように区別する（`_RAM_VARIANTS`）
- 容量を書かない店舗の商品は、その機種・キャリアの容量が1種類だけなら、その容量の商品に当てはめる
- 扱う機種は `phones.py` の `COLORS` に載っている機種だけ（古い機種は取らない）。色は各メーカーの公式の書き方
- キャリア版は JAN がわからないものが多いので、その商品の `jan` には `galaxy-s26-ultra-256gb-docomo-2`
  （機種-容量-キャリア-色の番号）のような仮のIDを入れている（URL などの識別にだけ使い、店舗とは名前で突き合わせる）
- 定価は、SIMフリー版はメーカー公式ストアの価格、キャリア版は各キャリアのオンラインショップの価格（割引なし）。
  販売が終わったものは発売時の価格。わからないものは `null`
- どの店舗も買い取っていない組み合わせ（キャリア版の折りたたみなど）は載せていない。買い取りが始まると
  `reports/unmatched.json` に出てくるので、そのときに足す
- 店舗ごとの取り方: ホムラ・ルデヤ（SIMフリーのみ）・森森買取・買取wiki は Galaxy・Xperia・AQUOS のカテゴリ、買取商店・
  海峡通信・買取一丁目・ケータイゴッド・ゲストモバイルは SIMフリー・キャリアごとのカテゴリから、対象の機種だけを取る
  （買取当番・PANDA買取は Pixel 以外の Android を扱っていない）
- 買取wiki のスマホは、同じ買取wiki のスマホ用のサイト（iphonekaitori.tokyo）から取る（ゲーム機は gamekaitori.jp）
- 色の区別がない店舗（ケータイゴッドなど）しか買い取っていない組み合わせも、その機種・キャリアの仕様にある色なら載せる

### iPad・Apple Watch・AirPods

- iPad: Pro（M5・M4）・Air（M4・M3）・iPad（A16）・iPad mini（A17 Pro）。1行＝サイズ・チップ・容量・Wi-Fi/Cellular・
  （Pro の Nano-textureガラス）・色（例: `iPad Pro 11インチ（M5）256GB Wi-Fi スペースブラック`）。`jan` はその JAN
- Apple Watch: Series 12・11、Ultra 4・3、SE 3。1行＝シリーズ・ケースサイズ・GPS/GPS + Cellular・ケースの色と素材
  （例: `Apple Watch Series 12 46mm GPS ブラックアルミニウム`）。バンドは区別しない。`jan` は仮のID
- AirPods: Pro 3・Pro 2・AirPods 5（ワイヤレス充電ケース付きも）・AirPods 4（ノイズキャンセリング搭載も）・AirPods Max 2・Max（USB-C）
- 突き合わせは JAN と Apple の型番（`scraper/apple.py`）。カタログの `"aliases"` に、その商品の型番と、
  Apple Watch はバンド違いの JAN・型番をすべて書いてある。店舗の出品には `"codes": {型番: 価格}` を付ける
  （ケータイゴッドのように1行に全色の型番が書かれていれば、その全部に同じ価格を当てはめる）
- 定価は Apple Store の今の価格（販売が終わったものは最後の価格）。JAN は Apple が公表していないので、
  複数の店舗の載せている JAN の多数決で決めた
- 画像は Apple Store の色ごとの画像（Apple Watch はケースだけの画像）
- 買取当番の iPad、買取wiki の iPad（機種ごとにまとめた価格しかない）、PANDA買取（実際には買い取っていない）は取らない

### PSA 鑑定品

- PSA10 のシングルカード（ポケモンカード・ワンピース・遊戯王）。買取ホムラ・森森買取・トレカラウンジ・トレカクラブ・
  トレカバース（郵送買取の価格）・ゴールデンホビーから取る
  （シンソク・トレカバンク・カードラッシュ・おたちゅう・カーナベルなどは利用規約で情報の商業利用・転載・自動取得を
  禁止しているので、許可が取れるまで載せない）
- JAN がないので、ゲーム・PSA の点数・カード番号・カード名で突き合わせる（`scraper/psa.py` の `psa_key`）。
  カード番号だけでは別のカードとぶつかる（070/066 がシロナとナタネ など）ので、名前もそろえて使う。
  マスターボールミラー・1ED・英語版・ワンピースのコミックパラレルなどは別のカードとして区別する
- カタログの PSA の商品は `python -m scraper.psa_catalog` で、店舗の一覧から作り直す（新しいカードの追加）。
  毎日 9:50 の「商品画像の更新」でも自動で動かし、変化があればコミットする。
  店舗ごとの書き方の違い（「R団のサンダー 25th」と「R団のサンダー(25th)」など）は、同じ番号で名前の片方が
  もう片方で始まるものを同じカードとしてまとめ、その書き方をカタログの `"keys"` に入れておく。
  名前を通称で書く店舗（トレカバースの「ムンクコダック」）や番号を略す店舗（ゴールデンホビーの「BW6F-063」）は、
  候補が1つに決まり価格も近いときだけまとめる（くわしくは `scraper/psa_catalog.py` の先頭）
- 定価がないので差益は出さない。商品画像は、トレカラウンジ → 買取ホムラ → トレカクラブ → トレカバース →
  ゴールデンホビー → 森森買取 の順に、載っている店舗のカード画像
  （`"image_source"` に出典）。森森買取の PSA のケースごと写した画像は、カードの部分だけ切り抜く（`"image_crop": "slab"`）

### トレカ（ポケモンカード・ワンピースカード・遊戯王・ドラゴンボール フュージョンワールド）

- 対象はシュリンク付き・未開封の BOX と、ポケモンカードの特別な BOX・セット（スペシャルBOX、ポケモンセンターセットなど）。
  カートン・スターターセット・スタートデッキは対象外
- ポケモンカードは、サン＆ムーン（SM6 以降）・ソード＆シールドの BOX も載せている（ホムラ・当番が買い取っている）。
  それより前の旧裏面などの BOX・パックは、新品の買取というより骨董品の扱いなので載せていない
- 取得している店舗: 買取ホムラ・買取商店・海峡通信・買取当番・買取ルデヤ・森森買取・ケータイゴッド
  （買取一丁目・買取wiki・ゲストモバイル・PANDA買取はトレカなし）
  - 遊戯王はホムラ・ルデヤ・海峡通信、フュージョンワールドはホムラ・ルデヤだけ
- 買取ホムラと買取当番の一部は JAN を載せていないので、商品名のセット名で突き合わせる。
  カタログの商品に、その店舗での名前を `"names": ["ストームエメラルダ"]` のように書く
  （`scraper/cards.py` の `card_key` で、【BOX】などの飾りや空白を除いてから比べる）
- 定価は 1パックの価格 × 1BOX のパック数（公式の商品ページより）
- JAN がわかっていない古い BOX（サン&ムーンの頃など）は、まだカタログに入れていない

商品を追加したら、画像の更新（`python -m scraper.images`、または Actions の「商品画像の更新」）も実行してください。

## 価格の推移（data/history/）

- 価格の更新のたびに、その日のファイル（`data/history/2026-10-02.json` など）に各店舗の価格を上書きする。
  1日の最後に取得した価格が、その日の価格として残る
- 取得に失敗している店舗は、前回の価格を使い回しているだけなので記録しない
- 商品ページのグラフはサイトを組み立てるときに SVG として作る（JavaScript なし）。2日分以上の記録がある商品だけ表示する
- 記録を始める前の日の分は `python -m scraper.history --backfill` で、Git に残っている prices.json の各版から作れる

## 商品画像

- 見た目をそろえるため、**メーカー公式サイトの本体画像**を使う。カタログの商品に
  `"image_url": "<公式の画像のURL>"`（と、載っているページの `"image_page"`）を書く
  - iPhone は Apple Store の購入ページの色ごとの画像、ゲーム機は各メーカーの公式サイトの画像
  - Galaxy は Samsung、Xperia はソニー、AQUOS はシャープ（COCORO STORE など）の色ごとの画像。
    キャリア版は同じ色の SIMフリー版の画像を使う（`image_from`）
  - Nintendo Switch / Switch 2 と PlayStation は、セット違いなどを見分けやすいようにパッケージ（箱）の画像
    （公式に箱の画像がない PlayStation の一部は Yahoo!ショッピングの箱の画像。箱の画像がどこにもない限定版などは本体の画像）
  - トレカは公式サイトに BOX の画像がほとんどない（パックの画像だけ）ので、Yahoo!ショッピングの BOX の画像を使う
- 画像は `public/images/<JAN>.jpg` に保存して、サイトから直接出す。余白を切り取り、240px の白い正方形の中央に
  同じ大きさで置く。端に離れて書かれた細い文字（著作権表示など）は切り落とす
- `image_url` がない商品だけ、下の Yahoo!ショッピングから探す

### Yahoo!ショッピング（公式画像がない商品）

- Yahoo!デベロッパーネットワークで登録したアプリの **Client ID** を使う
  - 手元: 環境変数 `YAHOO_CLIENT_ID` に設定する
  - GitHub: リポジトリの Settings → Secrets and variables → Actions に `YAHOO_CLIENT_ID` として登録する
  - Client ID はコードやファイルに書かない（公開リポジトリなので誰でも見られてしまう）
- JAN コードで検索し、画像のある**新品の**出品のうちレビュー数が最も多いものの画像を使う
  （中古の出品は実物の写真のことが多いので使わない。新品の出品がない商品は画像なしになる）
- 選んだ画像は 600px の大きさで取り、上と同じように整えて保存する（元の出品が消えても使える）
- 一度保存した画像は使い続ける。毎日の「商品画像の更新」で探すのは、まだ画像がない商品と
  `image_item` を変えた商品だけ（画像を選び直したいときは、その商品の画像ファイルを消して実行してもよい）
- 選ばれた画像が宣伝の文字入りなどでいまいちなときは、出品を指定して差し替える
  1. `python -m scraper.images --candidates <JAN>` で候補（出品コードと画像URL）を一覧表示する
  2. 画像URLをブラウザで開いて見比べ、良い画像の出品コードを選ぶ
  3. `catalog/products.json` のその商品に `"image_item": "<出品コード>"` を書き、画像の更新を実行する
  - 同じ店舗が画像の違う出品を複数出していることがあるので、店舗ではなく出品コードで指定する
  - 指定した出品がなくなったときは、自動で選び直して警告を出す
- ページ下部の「Webサービス by Yahoo! JAPAN」のクレジット表記は**利用条件なので消さない**
  （HTMLの改変、色の変更、極端に小さくすることも禁止されている）

## 店舗を追加する

1. `scraper/shops/` に店舗のモジュールを作る（`ID`・`NAME`・`SHORT`・`URL` と `fetch(http)`）
   - `fetch` は `{"jan", "name", "price", "url"}` のリストを返す。**新品・買取中の商品だけ**にする
   - スマホは `"key": phone_key(name)` と色ごとの価格 `"colors"` も付ける（JAN がなければ `"jan": None`）
   - アクセスは必ず引数の `http.get()` を使う（アクセス間隔と再試行を共通で管理している）
   - robots.txt で Crawl-delay を指定している店舗は、モジュールに `INTERVAL = 5.0` のように書く（森森買取）
   - 古い機種まで載っている店舗は、`phones.phone_colors(key)` が空の機種（扱っていない機種）を取らない
   - 追加する前に、利用規約に「掲載情報の複製・転載の禁止」がないか確かめる
     （携帯空間・買取楽園などは規約で禁止されているので載せていない）
2. `scraper/shops/__init__.py` の `SHOPS` に追加する（並び順が表の列の順になる）

## 公開の仕組み

- サイト: https://kaitori-radar.com （Cloudflare で取得したドメイン。`kaitori-radar-a5l.pages.dev` でも開ける）
  - 検索エンジンには `kaitori-radar.com` が正式なURLだと伝えている（各ページの canonical。`scraper/common.py` の `SITE_URL`）
  - `public/robots.txt` と、組み立てのときに作る `sitemap.xml` は検索エンジン向け（Search Console に登録済み）
  - `public/404.html` がないと、Cloudflare Pages はどのURLでもトップページを返してしまうので消さない
  - 共有用の画像 `public/ogp.png` は `python scripts/make_ogp_image.py` で作る（要 `pip install pillow`）
- リポジトリ: https://github.com/nuvgfdd407/kaitori-radar （公開リポジトリなので GitHub Actions は無料）
- サイトは Cloudflare Pages の `kaitori-radar` プロジェクトに、GitHub Actions から直接アップロードする（Direct Upload）
  - Cloudflare Pages と GitHub を直接つなぐ方式は、コミットのたびにビルドが数えられ、無料プランの月500回を超えるおそれがあるため使わない
  - 価格が変わったときは「買取価格の更新」の最後で、組み立て直して公開する
  - `public/` の中やページのひな形を変えてプッシュしたときは「サイトの公開」が組み立て直して公開する（Actions の画面から手動でも実行できる）
  - CSS と JavaScript は、中身から作った目印を付けたURL（`/style.css?v=…`）で読み込むので、公開し直すとブラウザも新しいファイルを使う
- GitHub の Secrets に登録するもの
  - `YAHOO_CLIENT_ID`: Yahoo!デベロッパーネットワークの Client ID
  - `CLOUDFLARE_API_TOKEN`: Cloudflare の API トークン（権限は Account → Cloudflare Pages → Edit と Account → Workers Scripts → Edit）
  - `CLOUDFLARE_ACCOUNT_ID`: Cloudflare のアカウントID
  - `DISPATCH_TOKEN`: 定期実行の合図に使う GitHub のトークン（上を参照）
- 定期実行の合図は Cloudflare の Worker（`trigger/`）から出す
  - GitHub Actions の定期実行（schedule）は、混んでいると実行が飛ばされることが多く、ほとんど動かなかったため使っていない
  - Worker の Cron Triggers が決まった時刻に GitHub の API でワークフローを開始する（時刻は `trigger/wrangler.toml`）
  - `trigger/` を変えてプッシュすると「定期実行の合図の公開」が Worker を公開し直す
  - Worker が使う GitHub のトークンは Secrets の `DISPATCH_TOKEN`（このリポジトリの Actions: Read and write だけの
    Fine-grained token）。**有効期限が切れると自動更新が止まる**ので、期限前に作り直して Secrets を更新し、
    「定期実行の合図の公開」を実行する
- GitHub Actions はデータセンターからアクセスするため、店舗によっては一時的につながらないことがある
  （つながらなかった店舗は前回の価格を残し、画面にお知らせを出す）
- 自動更新のコミットが GitHub 側に増えていくので、手元で作業するときは先に `git pull` する

## 注意

- 各店舗の利用規約を確認し、アクセス頻度は控えめにする（同じ店舗へは2秒以上の間隔を空けている）
- 表示する価格はあくまで参考。実際の買取価格は申込時点で各店舗が決める
