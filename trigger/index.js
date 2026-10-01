// 価格と画像の更新を、決まった時刻に GitHub Actions で始めさせる Cloudflare Worker。
//
// GitHub Actions の定期実行（schedule）は、混んでいると実行が飛ばされることが多い。
// Cloudflare の Cron Triggers は時刻どおりに動くので、ここから GitHub の API で
// ワークフローを手動実行（workflow_dispatch）と同じ形で開始する。
//
// - 時刻は wrangler.toml の crons で決める（UTC）。下の WORKFLOWS と同じ文字列にする
// - GitHub のトークンは Worker のシークレット DISPATCH_TOKEN に入っている
//   （このリポジトリの Actions を開始する権限だけを持つトークン。.github/workflows/deploy-trigger.yml が登録する）

const REPO = "nuvgfdd407/kaitori-radar";

const WORKFLOWS = {
  "7,22,37,52 1-11 * * *": "update-prices.yml", // 日本時間 10:07〜20:52 に15分ごと
  "50 0 * * *": "update-images.yml", // 日本時間 9:50
};

export default {
  async scheduled(event, env) {
    const workflow = WORKFLOWS[event.cron];
    if (!workflow) {
      throw new Error(`WORKFLOWS にない時刻の設定です: ${event.cron}`);
    }
    const res = await fetch(`https://api.github.com/repos/${REPO}/actions/workflows/${workflow}/dispatches`, {
      method: "POST",
      headers: {
        Authorization: `Bearer ${env.DISPATCH_TOKEN}`,
        Accept: "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "kaitori-radar-trigger",
      },
      body: JSON.stringify({ ref: "main" }),
    });
    // 成功すると 204 が返る。失敗は Cloudflare の画面（Worker のログ）で確認できるように例外にする
    if (res.status !== 204) {
      throw new Error(`${workflow} を開始できませんでした: HTTP ${res.status} ${await res.text()}`);
    }
  },
};
