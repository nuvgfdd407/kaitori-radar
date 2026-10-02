'use strict';

// 表や商品ページのHTMLは scraper/build.py が作っている。
// ここでは、一覧の絞り込みと並び替え、一覧の切り替え、切れた商品画像の差し替え、比較リストだけを行う。

document.documentElement.classList.add('js');

const $ = (id) => document.getElementById(id);
const yen = (n) => '¥' + n.toLocaleString('ja-JP');
const esc = (s) => String(s).replace(/[&<>"']/g, (c) => ({
  '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;',
}[c]));
// 店舗サイトなどから取ってきたURLなので、http(s) 以外は使わない
const safeUrl = (u) => (/^https?:\/\//.test(u || '') ? u : null);

// ---- 切れた画像の差し替え -------------------------------------------------------

document.addEventListener('error', (e) => {
  const thumb = e.target instanceof HTMLImageElement && e.target.closest('.thumb');
  if (!thumb) return;
  const large = thumb.classList.contains('thumb--large') ? ' thumb--large' : '';
  thumb.outerHTML = `<span class="thumb${large} thumb-empty" aria-hidden="true"></span>`;
}, true);

// ---- 一覧の絞り込み ---------------------------------------------------------------
// 全角・半角、大文字・小文字、ひらがな・カタカナ、空白や記号の違いは区別しない。
// 空白で区切ると、すべての言葉を含む商品だけを出す。

const fold = (s) => s.normalize('NFKC').toLowerCase()
  .replace(/[ぁ-ゖ]/g, (c) => String.fromCharCode(c.charCodeAt(0) + 0x60))
  .replace(/[\s\-‐－―・/()「」『』.,、。]/g, '');
const searchTexts = new WeakMap();  // 行 → 比較用に変換した検索用の文字

const searchInput = $('search');
if (searchInput) {
  searchInput.addEventListener('input', filterRows);
  if (searchInput.value) filterRows();  // ブラウザが前の入力を残しているとき
}

function filterRows() {
  const words = searchInput.value.normalize('NFKC').split(/\s+/).map(fold).filter(Boolean);
  // トップページ・ジャンルのページは各シリーズの先頭しか出していないので、全商品の索引から探す
  const partial = document.querySelector('.price-list[data-partial]');
  if (partial) {
    searchAll(words, partial);
    return;
  }
  let shown = 0;
  document.querySelectorAll('.price-list .item').forEach((row) => {
    if (!searchTexts.has(row)) searchTexts.set(row, fold(row.dataset.search || ''));
    const hit = words.every((w) => searchTexts.get(row).includes(w));
    row.hidden = !hit;
    if (hit) shown += 1;
  });
  // シリーズのまとまりは、そのシリーズの商品が1つも出ていなければ見出しごと隠す
  document.querySelectorAll('.price-list .list-group').forEach((group) => {
    group.hidden = ![...group.querySelectorAll('.item')].some((row) => !row.hidden);
  });
  const count = document.querySelector('.count');
  if (count) {
    const total = count.dataset.total;
    count.textContent = words.length ? `${total}商品中 ${shown}件` : `${total}商品`;
  }
  const noResults = document.querySelector('.no-results');
  if (noResults) noResults.hidden = shown > 0;
}

// ---- 全商品からの検索（トップページ・ジャンルのページ） ------------------------------
// 索引（data/search.json）は、検索欄に入力したときに初めて読み込む。結果は最大 MAX_RESULTS 件まで出す。

const MAX_RESULTS = 100;
let searchIndex = null;  // Promise

function loadSearchIndex() {
  if (!searchIndex) {
    searchIndex = fetch('/data/search.json')
      .then((res) => {
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        return res.json();
      })
      .then((items) => items.map((it) => ({ ...it, f: fold(it.s) })))
      .catch((e) => {
        searchIndex = null;
        throw e;
      });
  }
  return searchIndex;
}

async function searchAll(words, list) {
  const box = $('search-results');
  const count = document.querySelector('.count');
  const noResults = document.querySelector('.no-results');
  const total = count ? count.dataset.total : '';
  if (!words.length) {
    list.hidden = false;
    if (box) box.hidden = true;
    if (count) count.textContent = `${total}商品`;
    if (noResults) noResults.hidden = true;
    return;
  }
  const query = searchInput.value;
  let items;
  try {
    items = await loadSearchIndex();
  } catch (e) {
    if (count) count.textContent = '検索の準備ができませんでした。時間をおいてもう一度お試しください。';
    return;
  }
  if (searchInput.value !== query || !box) return;  // 読み込み中に入力が変わった
  const scope = list.dataset.scope ? list.dataset.scope.split(' ') : null;
  const hits = items.filter((it) => (!scope || scope.includes(it.g)) && words.every((w) => it.f.includes(w)));
  list.hidden = true;
  box.hidden = false;
  box.innerHTML = hits.slice(0, MAX_RESULTS).map((it) => `<li><a class="result" href="/item/${encodeURIComponent(it.j)}/">`
    + (it.i ? `<img src="${esc(it.i)}" alt="" width="44" height="44" loading="lazy" decoding="async">`
      : '<span class="thumb-empty" aria-hidden="true"></span>')
    + `<span class="result-name">${esc(it.n)}<small>${esc(it.gn)}</small></span>`
    + `<span class="result-price">${it.b ? yen(it.b) : '—'}<small>${esc(it.h)}</small></span></a></li>`).join('');
  if (count) {
    count.textContent = hits.length > MAX_RESULTS
      ? `${total}商品中 ${hits.length}件（先頭の${MAX_RESULTS}件を表示。言葉を足すと絞り込めます）`
      : `${total}商品中 ${hits.length}件`;
  }
  if (noResults) noResults.hidden = hits.length > 0;
}

// ---- 表の並び替え ---------------------------------------------------------------

const SORT_KEYS = ['default', 'best', 'profit', 'ratio'];
const SORT_STORAGE_KEY = 'kaitori-radar:sort';

const sortSelect = $('sort');
if (sortSelect) {
  // 並び順は、次に開いたときも同じにしておく（保存できない環境では何もしない）
  try {
    const saved = localStorage.getItem(SORT_STORAGE_KEY);
    if (SORT_KEYS.includes(saved)) sortSelect.value = saved;
  } catch (e) { /* 使えなくても表示には影響しない */ }

  sortSelect.addEventListener('change', () => {
    try {
      localStorage.setItem(SORT_STORAGE_KEY, sortSelect.value);
    } catch (e) { /* 同上 */ }
    sortRows(sortSelect.value);
  });
  sortRows(sortSelect.value);
}

// シリーズごとのまとまり（.rows）の中で行を並べ替える
function sortRows(key) {
  document.querySelectorAll('.price-list .rows').forEach((rows) => {
    [...rows.children]
      .sort((a, b) => compareRows(a, b, key))
      .forEach((row) => rows.appendChild(row));
  });
}

// 値がない商品（定価不明など）は常に後ろに回す
function compareRows(a, b, key) {
  const byIndex = Number(a.dataset.index) - Number(b.dataset.index);
  if (key === 'default') return byIndex;
  const va = a.dataset[key] === '' ? null : Number(a.dataset[key]);
  const vb = b.dataset[key] === '' ? null : Number(b.dataset[key]);
  if (va === null && vb === null) return byIndex;
  if (va === null) return 1;
  if (vb === null) return -1;
  return vb - va || byIndex;
}

// ---- 一覧の切り替え ---------------------------------------------------------------
// ジャンル・シリーズのボタンを押したとき、ページ全体を読み込み直さずに、ボタンと一覧の部分だけを
// 次のページのものに入れ替える（URLは変わるので、戻る・共有・検索エンジンはふつうのページと同じ）。
// ボタンに指やマウスが乗った時点で先に読み込んでおく。読み込めないときは、ふつうにページを開く。

const SWAP_LINKS = '.nav a, .group-title a, .more-link';
const pageCache = new Map();  // URL → 読み込み中または読み込んだ HTML（Promise）

if (searchInput) {
  history.replaceState({ swap: true }, '');
  document.addEventListener('pointerover', (e) => prefetchPage(e.target.closest && e.target.closest(SWAP_LINKS)));
  document.addEventListener('focusin', (e) => prefetchPage(e.target.closest(SWAP_LINKS)));
  document.addEventListener('click', (e) => {
    const link = e.target.closest(SWAP_LINKS);
    if (!link || e.defaultPrevented || e.button !== 0 || e.metaKey || e.ctrlKey || e.shiftKey || e.altKey) return;
    if (link.origin !== location.origin) return;
    e.preventDefault();
    if (link.pathname === location.pathname) return;
    showPage(link.pathname, { push: true, focus: link.pathname });
  });
  window.addEventListener('popstate', () => showPage(location.pathname, { push: false }));
}

function prefetchPage(link) {
  if (link && link.origin === location.origin) loadPage(link.pathname);
}

function loadPage(path) {
  if (!pageCache.has(path)) {
    const request = fetch(path).then((res) => {
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      return res.text();
    });
    request.catch(() => pageCache.delete(path));
    pageCache.set(path, request);
  }
  return pageCache.get(path);
}

async function showPage(path, { push, focus }) {
  const content = $('content');
  content.setAttribute('aria-busy', 'true');
  let doc;
  try {
    doc = new DOMParser().parseFromString(await loadPage(path), 'text/html');
  } catch (e) {
    location.href = path;  // 読み込めないときは、ふつうにページを開く
    return;
  }
  const nextContent = doc.getElementById('content');
  const nextNav = doc.querySelector('.nav');
  if (!nextContent || !nextNav || !doc.getElementById('search')) {
    location.href = path;
    return;
  }
  if (push) history.pushState({ swap: true }, '', path);
  document.title = doc.title;
  ['link[rel="canonical"]', 'meta[name="description"]'].forEach((selector) => {
    const now = document.querySelector(selector);
    const next = doc.querySelector(selector);
    if (now && next) now.replaceWith(next);
  });
  document.querySelector('.nav').replaceWith(nextNav);
  content.replaceWith(nextContent);
  // 入力中の絞り込みと、選んでいる並び順は、切り替えたあとの一覧にもそのまま使う
  filterRows();
  if (sortSelect) sortRows(sortSelect.value);
  updateCartUi();
  if (focus) {
    const chip = [...nextNav.querySelectorAll('a')].find((a) => a.pathname === focus);
    if (chip) chip.focus({ preventScroll: true });
  }
}

// ---- 比較リスト -----------------------------------------------------------------
// 選んだ商品と数量を、このブラウザにだけ保存する（最後に変更してから1日で消える）

const CART_KEY = 'kaitori-radar:cart';
const CART_TTL = 24 * 60 * 60 * 1000;
// 右下の比較リストのボタンのアイコン（カート）
const CART_ICON = '<svg viewBox="0 0 24 24" width="24" height="24" aria-hidden="true"><path fill="currentColor" '
  + 'd="M7 18a2 2 0 1 0 0 4 2 2 0 0 0 0-4Zm10 0a2 2 0 1 0 0 4 2 2 0 0 0 0-4ZM5.2 4l.6 3H21l-2 8H7.4L4.4 2H1v2h3.4l'
  + '2.9 13H19v-2H8.6l-.4-2H20l2.6-10H6.2L5.6 2Z"/></svg>';
const MAX_QTY = 99;

let cart = loadCart();   // { JAN: 数量 }
let priceData = null;    // 比較リストのページでだけ読み込む
const cartRoot = $('cart-root');

document.addEventListener('click', (e) => {
  const add = e.target.closest('[data-add]');
  if (add) {
    e.preventDefault();  // 一覧の行（<details>）の中にあるので、行が開かないようにする
    const jan = add.dataset.add;
    if (cart[jan]) delete cart[jan];
    else cart[jan] = 1;
    saveCart();
    return;
  }
  const qty = e.target.closest('[data-qty]');
  if (qty) {
    const jan = qty.dataset.jan;
    cart[jan] = Math.min(MAX_QTY, Math.max(1, (cart[jan] || 1) + Number(qty.dataset.qty)));
    saveCart();
    return;
  }
  const remove = e.target.closest('[data-remove]');
  if (remove) {
    delete cart[remove.dataset.remove];
    saveCart();
  }
});

// 別のタブで変えたときも、表示をそろえる
window.addEventListener('storage', (e) => {
  if (e.key !== CART_KEY) return;
  cart = loadCart();
  updateCartUi();
});

if (cartRoot) {
  fetch('/data/prices.json', { cache: 'no-cache' })
    .then((res) => {
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      return res.json();
    })
    .then((data) => {
      priceData = data;
      renderCartPage();
    })
    .catch(() => {
      cartRoot.innerHTML = '<p class="alert">価格データを読み込めませんでした。時間をおいて再読み込みしてください。</p>';
    });
}
updateCartUi();

function loadCart() {
  try {
    const saved = JSON.parse(localStorage.getItem(CART_KEY) || 'null');
    if (!saved || Date.now() - saved.savedAt > CART_TTL) {
      localStorage.removeItem(CART_KEY);
      return {};
    }
    return saved.items || {};
  } catch (e) {
    return {};
  }
}

function saveCart() {
  try {
    if (Object.keys(cart).length) {
      localStorage.setItem(CART_KEY, JSON.stringify({ items: cart, savedAt: Date.now() }));
    } else {
      localStorage.removeItem(CART_KEY);
    }
  } catch (e) { /* 保存できなくても、開いている間は使える */ }
  updateCartUi();
}

function updateCartUi() {
  document.querySelectorAll('[data-add]').forEach((button) => {
    const added = Boolean(cart[button.dataset.add]);
    button.setAttribute('aria-pressed', String(added));
    button.title = added ? '比較リストから外す' : '比較リストに追加';
    const label = button.querySelector('.add-label');
    if (label) label.textContent = added ? '比較リストに追加済み' : '比較リストに追加';
  });
  renderCartBar();
  renderCartPage();
}

// 画面の右下にいつも出しておく比較リストのボタン（カートのアイコンと、入っている数）
function renderCartBar() {
  const count = Object.values(cart).reduce((sum, qty) => sum + qty, 0);
  let bar = $('cart-bar');
  if (cartRoot) {
    if (bar) bar.remove();
    return;
  }
  if (!bar) {
    bar = document.createElement('a');
    bar.id = 'cart-bar';
    bar.className = 'cart-bar';
    bar.href = '/cart/';
    document.body.appendChild(bar);
  }
  const previous = Number(bar.dataset.count || 0);
  bar.dataset.count = String(count);
  bar.setAttribute('aria-label', count ? `比較リスト（${count}点）を見る` : '比較リスト（空）');
  bar.title = count ? '比較リストを見る' : '「＋」で商品を追加すると、どの店舗に売ると一番高いかを比較できます';
  bar.innerHTML = `${CART_ICON}<span class="cart-bar-label">比較リスト</span>`
    + (count ? `<span class="cart-badge">${count}</span>` : '');
  // 追加したときに、ボタンを少し弾ませて場所を知らせる
  if (bar.dataset.ready && count > previous) {
    bar.classList.remove('cart-bar--bump');
    void bar.offsetWidth;
    bar.classList.add('cart-bar--bump');
  }
  bar.dataset.ready = '1';
}

function renderCartPage() {
  if (!cartRoot || !priceData) return;
  const products = priceData.products.filter((p) => cart[p.jan]);
  if (!products.length) {
    cartRoot.innerHTML = '<p class="empty">比較リストに商品がありません。'
      + '<a href="/">一覧</a>や商品ページの「＋」ボタンから追加できます。</p>';
    return;
  }
  const result = summarize(priceData.shops, products);
  cartRoot.innerHTML = renderItems(products) + renderPlan(result) + renderByShop(result, products.length)
    + `<p class="count">価格は${esc(formatTime(priceData.updated_at))}時点です。実際の買取価格は、申込の時点で各店舗が決めます。</p>`;
}

// 「商品ごとに最高値の店へ売る」場合と「1店舗にまとめて売る」場合を計算する
function summarize(shops, products) {
  const byShop = shops.map((shop) => {
    let total = 0;
    const missing = [];
    products.forEach((p) => {
      const offer = p.prices[shop.id];
      if (offer && offer.price > 0) total += offer.price * cart[p.jan];
      else missing.push(p);
    });
    return { shop, total, missing };
  });
  // 全商品を買い取れる店舗を先に、その中で合計が高い順
  byShop.sort((a, b) => (a.missing.length > 0) - (b.missing.length > 0) || b.total - a.total);

  const groups = new Map();
  const unsellable = [];
  let bestTotal = 0;
  products.forEach((p) => {
    let best = null;
    shops.forEach((shop) => {
      const offer = p.prices[shop.id];
      if (offer && offer.price > 0 && (!best || offer.price > best.price)) best = { shop, ...offer };
    });
    if (!best) {
      unsellable.push(p);
      return;
    }
    const qty = cart[p.jan];
    bestTotal += best.price * qty;
    if (!groups.has(best.shop.id)) groups.set(best.shop.id, { shop: best.shop, items: [], subtotal: 0 });
    const group = groups.get(best.shop.id);
    group.items.push({ p, qty, price: best.price, url: best.url });
    group.subtotal += best.price * qty;
  });
  const plan = [...groups.values()].sort((a, b) => b.subtotal - a.subtotal);
  return { byShop, plan, bestTotal, unsellable };
}

function renderItems(products) {
  const rows = products.map((p) => {
    const qty = cart[p.jan];
    const best = Math.max(0, ...Object.values(p.prices).map((o) => o.price || 0));
    return `<tr>
      <th scope="row"><a href="/item/${esc(p.jan)}/">${esc(p.name)}</a></th>
      <td class="num">${best ? yen(best) : '—'}</td>
      <td class="qty">
        <button type="button" class="qty-btn" data-qty="-1" data-jan="${esc(p.jan)}" aria-label="1つ減らす"${qty <= 1 ? ' disabled' : ''}>−</button>
        <span class="qty-value">${qty}</span>
        <button type="button" class="qty-btn" data-qty="1" data-jan="${esc(p.jan)}" aria-label="1つ増やす"${qty >= MAX_QTY ? ' disabled' : ''}>＋</button>
      </td>
      <td><button type="button" class="link-btn" data-remove="${esc(p.jan)}">削除</button></td>
    </tr>`;
  }).join('');
  return `<h2 class="section-title">選んだ商品</h2>
    <div class="table-wrap table-wrap--auto"><table class="shop-table cart-table">
      <thead><tr><th scope="col">商品</th><th scope="col" class="num">最高値（1点）</th><th scope="col">数量</th><th scope="col"></th></tr></thead>
      <tbody>${rows}</tbody>
    </table></div>`;
}

function renderPlan({ plan, bestTotal, unsellable, byShop }) {
  const single = byShop.find((s) => !s.missing.length);
  const diff = single ? bestTotal - single.total : null;
  const compare = diff > 0
    ? `<p class="cart-note">1つの店舗にまとめて売るより <strong>${yen(diff)}</strong> 高くなります（申込と発送は店舗ごとに必要です）。</p>`
    : single ? '<p class="cart-note">1つの店舗にまとめて売っても、合計は同じです。</p>' : '';
  const groups = plan.map((g) => `<div class="plan-shop">
      <h3>${esc(g.shop.name)}<span class="plan-subtotal">${yen(g.subtotal)}</span></h3>
      <ul>${g.items.map((it) => {
        const label = `${esc(it.p.name)} × ${it.qty}`;
        const url = safeUrl(it.url);
        const name = url ? `<a href="${esc(url)}" target="_blank" rel="noopener">${label}</a>` : label;
        const stale = g.shop.ok ? '' : '<span class="tag">前回取得時の価格</span>';
        return `<li>${name}<span>${yen(it.price * it.qty)}${stale}</span></li>`;
      }).join('')}</ul>
    </div>`).join('');
  const none = unsellable.length
    ? `<p class="alert">次の商品は、今どの店舗も買取価格を出していません: ${unsellable.map((p) => esc(p.name)).join('、')}</p>`
    : '';
  return `<h2 class="section-title">いちばん高くなる売り方（商品ごとに最高値の店へ）</h2>
    <p class="cart-total">合計 <strong>${yen(bestTotal)}</strong></p>
    ${compare}${none}
    <div class="plan">${groups}</div>`;
}

function renderByShop({ byShop }, itemCount) {
  const top = byShop[0] && !byShop[0].missing.length ? byShop[0].total : null;
  const rows = byShop.map((s, i) => {
    const note = s.missing.length
      ? `<span class="tag">${s.missing.length}点は取扱なし</span>`
      : '<span class="tag">全商品OK</span>';
    const best = i === 0 && top !== null ? ' class="is-best"' : '';
    const stale = s.shop.ok ? '' : '<span class="tag">前回取得時の価格</span>';
    return `<tr${best}><th scope="row">${esc(s.shop.name)} ${note}${stale}</th>
      <td class="num price">${s.total ? yen(s.total) : '—'}</td>
      <td class="num diff">${top !== null && !s.missing.length && i > 0 ? '−' + yen(top - s.total) : ''}</td></tr>`;
  }).join('');
  return `<h2 class="section-title">1つの店舗にまとめて売る場合</h2>
    <p class="cart-note">${itemCount}商品をまとめて1店舗に売った場合の合計です。申込と発送が1回で済みます。</p>
    <div class="table-wrap table-wrap--auto"><table class="shop-table">
      <thead><tr><th scope="col">店舗</th><th scope="col" class="num">合計</th><th scope="col" class="num">1位との差</th></tr></thead>
      <tbody>${rows}</tbody>
    </table></div>`;
}

function formatTime(iso) {
  return new Intl.DateTimeFormat('ja-JP', {
    timeZone: 'Asia/Tokyo', month: 'numeric', day: 'numeric', hour: '2-digit', minute: '2-digit',
  }).format(new Date(iso));
}
