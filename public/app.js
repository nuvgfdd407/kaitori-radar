'use strict';

// 表や商品ページのHTMLは scraper/build.py が作っている。
// ここでは、表の並び替えと、切れた商品画像の差し替えだけを行う。

const SORT_KEYS = ['default', 'best', 'profit', 'ratio'];
const STORAGE_KEY = 'kaitori-radar:sort';
const EMPTY_THUMB = '<span class="thumb thumb-empty" aria-hidden="true"></span>';

// 画像のURLが切れていたら、空の枠に差し替える
document.addEventListener('error', (e) => {
  const thumb = e.target instanceof HTMLImageElement && e.target.closest('.thumb');
  if (!thumb) return;
  const large = thumb.classList.contains('thumb--large');
  thumb.outerHTML = large ? EMPTY_THUMB.replace('thumb ', 'thumb thumb--large ') : EMPTY_THUMB;
}, true);

const select = document.getElementById('sort');
if (select) {
  // 並び順は、次に開いたときも同じにしておく（保存できない環境では何もしない）
  try {
    const saved = localStorage.getItem(STORAGE_KEY);
    if (SORT_KEYS.includes(saved)) select.value = saved;
  } catch (e) { /* 使えなくても表示には影響しない */ }

  select.addEventListener('change', () => {
    try {
      localStorage.setItem(STORAGE_KEY, select.value);
    } catch (e) { /* 同上 */ }
    sortRows(select.value);
  });
  sortRows(select.value);
}

// シリーズごとのまとまり（tbody.rows）の中で行を並べ替える
function sortRows(key) {
  document.querySelectorAll('.price-table tbody.rows').forEach((tbody) => {
    [...tbody.rows]
      .sort((a, b) => compareRows(a, b, key))
      .forEach((row) => tbody.appendChild(row));
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
