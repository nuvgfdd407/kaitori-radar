'use strict';

// 並び替えのキー。値がない商品（定価不明など）は常に後ろに回す
const SORT_KEYS = {
  default: null,
  best: (p) => p.bestPrice,
  profit: (p) => p.profit,
  ratio: (p) => p.ratio,
};

const $ = (id) => document.getElementById(id);
const yen = (n) => '¥' + n.toLocaleString('ja-JP');
const signedYen = (n) => (n > 0 ? '+' : n < 0 ? '−' : '±') + yen(Math.abs(n));
const signedPct = (r) => {
  const pct = Math.round((r - 1) * 100);
  return (pct > 0 ? '+' : pct < 0 ? '−' : '±') + Math.abs(pct) + '%';
};
const jstFormat = new Intl.DateTimeFormat('ja-JP', {
  timeZone: 'Asia/Tokyo', month: 'numeric', day: 'numeric', hour: '2-digit', minute: '2-digit',
});
const formatTime = (iso) => jstFormat.format(new Date(iso));
// 日本時間の今日の日付（YYYY-MM-DD）。発売日と比べるのに使う
const todayJst = new Intl.DateTimeFormat('sv-SE', { timeZone: 'Asia/Tokyo' }).format(new Date());

const esc = (s) => String(s).replace(/[&<>"']/g, (c) => ({
  '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;',
}[c]));
// 店舗サイトから取ってきたURLなので、http(s) 以外は使わない
const safeUrl = (u) => (/^https?:\/\//.test(u || '') ? u : null);

const EMPTY_THUMB = '<span class="thumb thumb-empty" aria-hidden="true"></span>';

const state = { series: 'all', sort: 'default' };
let data;
let products;

// 画像のURLが切れていたら、空の枠に差し替える
document.addEventListener('error', (e) => {
  const thumb = e.target instanceof HTMLImageElement && e.target.closest('.thumb');
  if (thumb) thumb.outerHTML = EMPTY_THUMB;
}, true);

main();

async function main() {
  restoreState();
  try {
    const res = await fetch('data/prices.json', { cache: 'no-cache' });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    data = await res.json();
  } catch (e) {
    $('updated').textContent = '価格データを読み込めませんでした';
    $('alerts').innerHTML = '<div class="alert">価格データを読み込めませんでした。時間をおいて再読み込みしてください。</div>';
    return;
  }
  products = data.products.map((p, index) => enrich(p, index));

  $('shop-count').textContent = data.shops.length;
  $('updated').textContent = '価格更新 ' + formatTime(data.updated_at);
  $('sources').innerHTML = data.shops
    .map((s) => `<a href="${esc(s.url)}" target="_blank" rel="noopener">${esc(s.name)}</a>`)
    .join('');
  renderAlerts();
  renderFilters();
  $('sort').value = state.sort;
  $('sort').addEventListener('change', (e) => {
    state.sort = e.target.value;
    saveState();
    renderTable();
  });
  renderTable();
}

// 最高値・差益・定価比を計算しておく
function enrich(p, index) {
  const prices = data.shops.map((s) => p.prices[s.id]?.price).filter((v) => v > 0);
  const bestPrice = prices.length ? Math.max(...prices) : null;
  const bestShops = bestPrice ? data.shops.filter((s) => p.prices[s.id]?.price === bestPrice) : [];
  // 発売前の買取価格は仮のことが多いので、差益は出さない
  const hasMsrp = bestPrice && p.msrp && !(p.release > todayJst);
  return {
    ...p,
    index,
    bestPrice,
    bestShops,
    profit: hasMsrp ? bestPrice - p.msrp : null,
    ratio: hasMsrp ? bestPrice / p.msrp : null,
  };
}

function renderAlerts() {
  $('alerts').innerHTML = data.shops
    .filter((s) => !s.ok)
    .map((s) => `<div class="alert">⚠ ${esc(s.name)}の価格を取得できていません`
      + `（${esc(formatTime(s.failing_since))}から）。前回取得した価格を表示しています。</div>`)
    .join('');
}

function renderFilters() {
  const options = [{ id: 'all', name: 'すべて' }, ...data.series];
  if (!options.some((o) => o.id === state.series)) state.series = 'all';
  const box = $('series-filter');
  box.innerHTML = options
    .map((o) => `<button type="button" class="chip" data-series="${esc(o.id)}"`
      + ` aria-pressed="${o.id === state.series}">${esc(o.name)}</button>`)
    .join('');
  box.addEventListener('click', (e) => {
    const button = e.target.closest('.chip');
    if (!button) return;
    state.series = button.dataset.series;
    saveState();
    box.querySelectorAll('.chip').forEach((b) => {
      b.setAttribute('aria-pressed', String(b.dataset.series === state.series));
    });
    renderTable();
  });
}

function sortProducts(list) {
  const key = SORT_KEYS[state.sort];
  if (!key) return [...list].sort((a, b) => a.index - b.index);
  return [...list].sort((a, b) => {
    const va = key(a);
    const vb = key(b);
    if (va == null && vb == null) return a.index - b.index;
    if (va == null) return 1;
    if (vb == null) return -1;
    return vb - va || a.index - b.index;
  });
}

function renderTable() {
  const shops = data.shops;
  const columns = 4 + shops.length;

  $('thead').innerHTML = '<tr>'
    + '<th scope="col" class="col-name">商品名</th>'
    + '<th scope="col">定価</th>'
    + '<th scope="col">最高買取</th>'
    + '<th scope="col">差益</th>'
    + shops.map((s) => `<th scope="col" class="shop-head" title="${esc(s.name)}">`
      + `<a href="${esc(s.url)}" target="_blank" rel="noopener">${esc(s.short)}</a>`
      + (s.ok ? '' : '<span class="warn-mark" aria-label="取得エラー">⚠</span>')
      + '</th>').join('')
    + '</tr>';

  const visible = products.filter((p) => state.series === 'all' || p.series === state.series);
  const sorted = sortProducts(visible);
  const groups = state.series === 'all'
    ? data.series.map((s) => ({ name: s.name, items: sorted.filter((p) => p.series === s.id) }))
    : [{ name: null, items: sorted }];

  let html = '';
  for (const group of groups) {
    if (!group.items.length) continue;
    if (group.name) {
      html += `<tr class="group"><th colspan="${columns}" scope="rowgroup"><span>${esc(group.name)}</span></th></tr>`;
    }
    html += group.items.map((p) => renderRow(p, shops)).join('');
  }
  $('tbody').innerHTML = html || `<tr><td class="empty" colspan="${columns}">該当する商品がありません</td></tr>`;
  $('count').textContent = `${visible.length}商品`;
}

function renderRow(p, shops) {
  // 発売前の商品には発売日を出す（発売日を過ぎたら出なくなる）
  const release = p.release > todayJst
    && `<span class="tag">${Number(p.release.slice(5, 7))}/${Number(p.release.slice(8, 10))}発売</span>`;
  const sub = [p.model && esc(p.model), p.note && `<span class="tag">${esc(p.note)}</span>`, release]
    .filter(Boolean).join(' ');
  const name = `<th scope="row" class="col-name"><div class="name-wrap">${renderThumb(p)}<div>`
    + `<span class="product">${esc(p.name)}</span>`
    + (sub ? `<span class="sub">${sub}</span>` : '') + '</div></div></th>';

  const msrp = p.msrp ? `<td class="num">${yen(p.msrp)}</td>` : '<td class="num none">—</td>';

  const best = p.bestPrice
    ? `<td class="num col-best">${yen(p.bestPrice)}<span class="sub">${esc(p.bestShops.map((s) => s.short).join('・'))}</span></td>`
    : '<td class="num none">—</td>';

  let profit = '<td class="num none">—</td>';
  if (p.profit != null) {
    const cls = p.profit > 0 ? 'pos' : p.profit < 0 ? 'neg' : '';
    profit = `<td class="num profit ${cls}">${signedYen(p.profit)}<span class="sub">${signedPct(p.ratio)}</span></td>`;
  }

  const cells = shops.map((s) => {
    const offer = p.prices[s.id];
    if (!offer || !(offer.price > 0)) return '<td class="num shop none" aria-label="取扱なし">—</td>';
    const classes = ['num', 'shop'];
    if (offer.price === p.bestPrice) classes.push('is-best');
    if (!s.ok) classes.push('is-stale');
    const url = safeUrl(offer.url);
    const label = yen(offer.price);
    const title = s.ok ? `${s.name}で見る` : `${s.name}（前回取得時の価格）`;
    const content = url
      ? `<a href="${esc(url)}" target="_blank" rel="noopener" title="${esc(title)}">${label}</a>`
      : label;
    return `<td class="${classes.join(' ')}">${content}</td>`;
  }).join('');

  return `<tr>${name}${msrp}${best}${profit}${cells}</tr>`;
}

// 商品画像（Yahoo!ショッピングの出品の画像）。クリックすると、画像の出典の出品ページが開く
function renderThumb(p) {
  const src = safeUrl(p.image?.src);
  if (!src) return EMPTY_THUMB;
  const img = `<img src="${esc(src)}" alt="" width="44" height="44" loading="lazy" decoding="async" referrerpolicy="no-referrer">`;
  const url = safeUrl(p.image.url);
  if (!url) return `<span class="thumb">${img}</span>`;
  const title = '画像の出典: Yahoo!ショッピング' + (p.image.seller ? `（${p.image.seller}）` : '');
  return `<a class="thumb" href="${esc(url)}" target="_blank" rel="noopener" title="${esc(title)}"`
    + ` aria-label="${esc(p.name)}の画像の出典（Yahoo!ショッピング）">${img}</a>`;
}

// 絞り込みと並び順は、次に開いたときも同じにしておく（保存できない環境では何もしない）
function restoreState() {
  try {
    const saved = JSON.parse(localStorage.getItem('kaitori-radar:view') || '{}');
    if (typeof saved.series === 'string') state.series = saved.series;
    if (saved.sort in SORT_KEYS) state.sort = saved.sort;
  } catch (e) { /* 使えなくても表示には影響しない */ }
}

function saveState() {
  try {
    localStorage.setItem('kaitori-radar:view', JSON.stringify(state));
  } catch (e) { /* 同上 */ }
}
