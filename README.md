# 買取レーダー

Nintendo Switch 2・Nintendo Switch・PlayStation 5・Xbox Series X|S・Steam Deck などのゲーミングPC・VRヘッドセットと、
iPhone 18・17・16シリーズ（SIMフリー版）の**新品（未開封）買取価格**を、買取店ごとに比較するサイトです。

- 対象店舗: 買取ホムラ・買取商店・海峡通信・買取一丁目・買取当番・買取ルデヤ・買取wiki（7店舗）
- 店舗ごとの価格、最高値、定価との差益を一覧表示
- 日本時間 10:00〜21:00 に15分ごとに価格を確認（GitHub Actions）
- 商品画像は Yahoo!ショッピングの商品検索APIから取得（1日1回）

## 仕組み

```
GitHub Actions（毎日 9:50）
  └ python -m scraper.images
      └ JAN コードで Yahoo!ショッピングを検索し、画像のURLを catalog/images.json に保存

GitHub Actions（15分ごと）
  └ python -m scraper.update
      ├ 各店舗のサイトから価格を取得（店舗ごとに並行して実行）
      ├ catalog/products.json の商品と JAN コード（iPhone は機種＋容量）で突き合わせ、画像も載せる
      └ 価格が変わったときだけ public/data/prices.json を更新してコミット
  └ python -m scraper.build（価格が変わったときだけ）
      └ public/ と prices.json から、公開用のサイトを dist/ に組み立てる
            ↓
dist/ を Cloudflare Pages に公開
```

公開するページ（HTMLは `scraper/build.py` と `scraper/templates.py` が作る）

| URL | 内容 |
|---|---|
| `/` | 全商品の比較表 |
| `/switch2/`・`/ps5/`・`/iphone17/` など | シリーズごとの比較表（そのシリーズを扱っている店舗だけの列にする） |
| `/item/<JAN>/` | 商品ごとの、店舗別の価格（高い順） |
| `/cart/` | 比較リスト（検索結果に出さない。サイトマップにも載せない） |
| `/sitemap.xml` | 上のすべてのページの一覧（組み立てるときに自動で作る） |

表はHTMLとして組み立てておく（検索エンジンが JavaScript なしで価格を読めるように）。
`public/app.js` は表の並び替え、切れた画像の差し替え、比較リストを行う。

比較リスト: 一覧や商品ページの「＋」で選んだ商品と数量を、訪問者のブラウザ（localStorage）にだけ保存する。
最後に変更してから1日で自動で消える。比較リストのページでは `data/prices.json` を読み込み、
「商品ごとに最高値の店へ売る場合」と「1店舗にまとめて売る場合」の合計を計算して表示する。

## ファイル構成

| パス | 内容 |
|---|---|
| `catalog/products.json` | 対象商品の一覧（JAN・シリーズ・表示名・型番・定価）。**手で管理する** |
| `catalog/images.json` | 商品画像のURL（`scraper.images` が自動で作る） |
| `scraper/shops/*.py` | 店舗ごとの取得処理 |
| `scraper/iphone.py` | iPhone の商品名から「機種＋容量」を読み取る（突き合わせ用） |
| `scraper/update.py` | 全店舗の取得と `prices.json` の書き出し |
| `scraper/images.py` | Yahoo!ショッピングからの商品画像の取得 |
| `scraper/build.py`・`scraper/templates.py` | 公開用のサイトを `dist/` に組み立てる（ページのHTMLのひな形は templates.py） |
| `public/` | そのまま公開するファイル（CSS・JavaScript・画像・robots.txt・404ページ・価格データ） |
| `dist/` | 組み立てたサイト（生成物なので Git には入れない） |
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

定価（`msrp`）は**メーカー希望小売価格（税込）**です。値上げがあったら更新してください。
限定版など現在の定価がない商品は `null` にしておくと、表では「—」になり差益も出しません。
iPhone の定価は Apple の販売価格（税込）で、販売終了したモデルは発売時の価格にしています。

発売前の商品には発売日（`"release": "2026-10-29"`）を書いておくと、発売日までは「10/29発売」と表示し、
差益は出しません（発売前の買取価格は仮のことが多いため）。発売日を過ぎると自動で通常の表示になります。

### iPhone

iPhone は店舗によって色ごとに別の商品として載っていたり、JAN がなかったりするので、
**機種＋容量**（`scraper/iphone.py` の `iphone_key`。例: `iPhone 17 Pro 256GB`）で突き合わせる。

- 1行＝機種＋容量。色違いはまとめ、色で価格が違う店舗では**いちばん高い色の価格**を使う
- 対象は SIMフリー版の新品未開封だけ（「開封済未使用」などの価格は使わない）
- カタログの iPhone は、シリーズIDを `iphone` で始め、商品名を `iphone_key` の結果と同じ文字列にする
  （`jan` はどれか1色のJAN。画像の検索に使う）
- 新しい機種が出たら、各店舗モジュールの iPhone のカテゴリ（`IPHONE_SUBS` など）にも追加する

商品を追加したら、画像の更新（`python -m scraper.images`、または Actions の「商品画像の更新」）も実行してください。

## 商品画像（Yahoo!ショッピング）

- Yahoo!デベロッパーネットワークで登録したアプリの **Client ID** を使う
  - 手元: 環境変数 `YAHOO_CLIENT_ID` に設定する
  - GitHub: リポジトリの Settings → Secrets and variables → Actions に `YAHOO_CLIENT_ID` として登録する
  - Client ID はコードやファイルに書かない（公開リポジトリなので誰でも見られてしまう）
- JAN コードで検索し、画像のある**新品の**出品のうちレビュー数が最も多いものの画像を使う
  （中古の出品は実物の写真のことが多いので使わない。新品の出品がない商品は画像なしになる）
- 画像ファイルはコピーせず、Yahoo!が配信している画像のURLをそのまま表示する
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
   - iPhone は `"key": iphone_key(name)` も付ける（JAN がなければ `"jan": None`）
   - アクセスは必ず引数の `http.get()` を使う（アクセス間隔と再試行を共通で管理している）
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
  - GitHub Actions の定期実行（schedule）は、混んでいると実行が飛ばされることが多く、ほとんど動かなかったため
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
