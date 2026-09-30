# 買取レーダー

Nintendo Switch 2・Nintendo Switch・PlayStation 5・Xbox Series X|S の本体の**新品買取価格**を、買取店ごとに比較するサイトです。

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
      ├ catalog/products.json の商品と JAN コードで突き合わせ、画像も載せる
      └ 価格が変わったときだけ public/data/prices.json を更新してコミット
            ↓
public/ をそのまま公開（Cloudflare Pages など）
  └ index.html が data/prices.json を読み込んで表を表示
```

## ファイル構成

| パス | 内容 |
|---|---|
| `catalog/products.json` | 対象商品の一覧（JAN・シリーズ・表示名・型番・定価）。**手で管理する** |
| `catalog/images.json` | 商品画像のURL（`scraper.images` が自動で作る） |
| `scraper/shops/*.py` | 店舗ごとの取得処理 |
| `scraper/update.py` | 全店舗の取得と `prices.json` の書き出し |
| `scraper/images.py` | Yahoo!ショッピングからの商品画像の取得 |
| `public/` | 公開するページ（HTML・CSS・JavaScript・価格データ） |
| `reports/unmatched.json` | カタログにない2万円以上の商品（新しい本体の登録漏れチェック用。公開はしない） |
| `.github/workflows/update-prices.yml` | 15分ごとの価格の更新 |
| `.github/workflows/update-images.yml` | 1日1回の画像の更新 |

## 手元で動かす

```bash
python -m venv .venv
.venv/Scripts/python -m pip install -r requirements.txt   # macOS / Linux は .venv/bin/python
.venv/Scripts/python -m scraper.update
python -m http.server 8765 --directory public
```

ブラウザで http://localhost:8765 を開きます（`index.html` を直接開くと、データを読み込めません）。

## 商品を追加する

1. `reports/unmatched.json` に、カタログにない高額商品が出ていないか確認する
2. 本体なら `catalog/products.json` の `products` に追加する（並び順が表の標準の並びになる）
3. 本体でないもの（コントローラーなど）は `ignore` に追加すると、以後は報告されなくなる

定価（`msrp`）は**メーカー希望小売価格（税込）**です。値上げがあったら更新してください。
限定版など現在の定価がない商品は `null` にしておくと、表では「—」になり差益も出しません。

発売前の商品には発売日（`"release": "2026-10-29"`）を書いておくと、発売日までは「10/29発売」と表示し、
差益は出しません（発売前の買取価格は仮のことが多いため）。発売日を過ぎると自動で通常の表示になります。

商品を追加したら、画像の更新（`python -m scraper.images`、または Actions の「商品画像の更新」）も実行してください。

## 商品画像（Yahoo!ショッピング）

- Yahoo!デベロッパーネットワークで登録したアプリの **Client ID** を使う
  - 手元: 環境変数 `YAHOO_CLIENT_ID` に設定する
  - GitHub: リポジトリの Settings → Secrets and variables → Actions に `YAHOO_CLIENT_ID` として登録する
  - Client ID はコードやファイルに書かない（公開リポジトリなので誰でも見られてしまう）
- JAN コードで検索し、画像のある出品のうちレビュー数が最も多いものの画像を使う
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
   - アクセスは必ず引数の `http.get()` を使う（アクセス間隔と再試行を共通で管理している）
2. `scraper/shops/__init__.py` の `SHOPS` に追加する（並び順が表の列の順になる）

## 公開の仕組み

- リポジトリ: https://github.com/nuvgfdd407/kaitori-radar （公開リポジトリなので GitHub Actions は無料）
- サイトは Cloudflare Pages の `kaitori-radar` プロジェクトに、GitHub Actions から直接アップロードする（Direct Upload）
  - Cloudflare Pages と GitHub を直接つなぐ方式は、コミットのたびにビルドが数えられ、無料プランの月500回を超えるおそれがあるため使わない
  - 価格が変わったときは「買取価格の更新」の最後で公開し直す
  - `public/` の中を変えてプッシュしたときは「サイトの公開」が公開し直す（Actions の画面から手動でも実行できる）
- GitHub の Secrets に登録するもの
  - `YAHOO_CLIENT_ID`: Yahoo!デベロッパーネットワークの Client ID
  - `CLOUDFLARE_API_TOKEN`: Cloudflare の API トークン（権限は Account → Cloudflare Pages → Edit）
  - `CLOUDFLARE_ACCOUNT_ID`: Cloudflare のアカウントID
- GitHub Actions はデータセンターからアクセスするため、店舗によっては一時的につながらないことがある
  （つながらなかった店舗は前回の価格を残し、画面にお知らせを出す）
- 自動更新のコミットが GitHub 側に増えていくので、手元で作業するときは先に `git pull` する

## 注意

- 各店舗の利用規約を確認し、アクセス頻度は控えめにする（同じ店舗へは2秒以上の間隔を空けている）
- 表示する価格はあくまで参考。実際の買取価格は申込時点で各店舗が決める
