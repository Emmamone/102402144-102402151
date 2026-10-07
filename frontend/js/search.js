/* 搜索结果页。
 *
 * 阶段 0 的机械拆分：内容逐字取自本页原先的内联 <script>，**未改变任何行为**。
 * 原先各页重复定义的 shared 部分已移入 common.js（实现逐字相同）：
 *   TAB_ON / TAB_OFF / setTabClass / escapeHtml
 *
 * 本页仍使用 localStorage（campusResolved / campusNewItem），并仍从 DOM 的
 * data-keywords / data-result 做前端筛选 —— 这两件事留待阶段 3 改造为接口调用。
 */

var currentType = 'all';

function getResolvedIds() {
  try {
    return JSON.parse(localStorage.getItem('campusResolved') || '[]');
  } catch (err) {
    return [];
  }
}

function applyResolved() {
  getResolvedIds().forEach(function (id) {
    var card = document.querySelector('[data-id="' + id + '"]');
    if (!card) { return; }
    var badge = card.querySelector('[data-status]');
    if (!badge) { return; }
    badge.textContent = '已解决';
    badge.className = 'ml-auto shrink-0 px-1.5 py-0.5 rounded text-[10px] font-medium bg-slate-100 text-slate-500';
  });
}

function insertLocalPost() {
  var item;
  try { item = JSON.parse(localStorage.getItem('campusNewItem') || 'null'); } catch (err) { item = null; }
  if (!item || !item.name) { return; }
  var isSeek = item.type === 'seek';
  var type = isSeek ? 'seek' : 'find';
  var typeName = isSeek ? '寻物' : '招领';
  var tagClass = isSeek ? 'bg-blue-50 text-blue-600' : 'bg-emerald-50 text-emerald-600';
  var statusText = isSeek ? '寻找中' : '待认领';
  var statusClass = isSeek ? 'bg-orange-50 text-orange-600' : 'bg-amber-50 text-amber-600';
  var card = document.createElement('a');
  card.className = 'rounded-2xl bg-white p-4 border border-blue-100 shadow-sm transition active:scale-[0.99]';
  card.setAttribute('data-id', 'new');
  card.setAttribute('data-result', type);
  card.setAttribute('data-keywords', [item.name, item.category, item.place, item.desc, typeName].join(' '));
  card.href = 'detail.html?id=new';
  card.innerHTML = '<div class="flex items-start gap-3"><div class="w-11 h-11 shrink-0 rounded-xl ' + (isSeek ? 'bg-blue-50' : 'bg-emerald-50') + ' flex items-center justify-center"><iconify-icon class="text-[22px] ' + (isSeek ? 'text-blue-600' : 'text-emerald-600') + '" icon="' + (isSeek ? 'mdi:help-circle-outline' : 'mdi:hand-heart-outline') + '"></iconify-icon></div><div class="min-w-0 flex-1"><div class="flex items-center gap-1.5"><h3 class="min-w-0 text-[15px] font-semibold text-slate-800 truncate">' + escapeHtml(item.name) + '</h3><span class="shrink-0 px-1.5 py-0.5 rounded text-[10px] font-medium ' + tagClass + '">' + typeName + '</span><span class="ml-auto shrink-0 px-1.5 py-0.5 rounded text-[10px] font-medium ' + statusClass + '" data-status="">' + statusText + '</span></div><div class="mt-1.5 flex items-center gap-3 text-[11px] text-slate-400"><span>' + escapeHtml((item.time || '').slice(0, 16) || '刚刚') + '</span><span class="truncate">' + escapeHtml(item.place) + '</span></div><p class="mt-1.5 text-[12px] leading-relaxed text-slate-500 line-clamp-2">' + escapeHtml(item.desc) + '</p></div></div>';
  document.querySelector('#resultList .flex.flex-col').insertBefore(card, document.querySelector('#resultList .flex.flex-col').firstChild);
}

function runSearch() {
  var kw = document.getElementById('kw').value.trim();
  var key = kw.toLowerCase();
  var count = 0;

  document.querySelectorAll('[data-result]').forEach(function (card) {
    var text = (card.getAttribute('data-keywords') || '').toLowerCase();
    var nameMatch = !key || text.indexOf(key) !== -1;
    var typeMatch = (currentType === 'all') || (card.getAttribute('data-result') === currentType);
    var show = nameMatch && typeMatch;
    card.classList.toggle('hidden', !show);
    if (show) { count++; }
  });

  document.getElementById('resultCount').textContent = count;
  document.getElementById('kwEcho').textContent = kw || '全部物品';
  document.getElementById('resultList').classList.toggle('hidden', count === 0);
  document.getElementById('emptyState').classList.toggle('hidden', count > 0);
}

function setFilter(type) {
  currentType = type;
  document.querySelectorAll('[data-tab]').forEach(function (btn) {
    setTabClass(btn, btn.getAttribute('data-tab') === type);
  });
  runSearch();
}

function onSubmitSearch(e) {
  if (e) { e.preventDefault(); }
  currentType = 'all';
  document.querySelectorAll('[data-tab]').forEach(function (btn) {
    setTabClass(btn, btn.getAttribute('data-tab') === 'all');
  });
  runSearch();
  return false;
}

function quickSearch(kw) {
  document.getElementById('kw').value = kw;
  onSubmitSearch(null);
}

window.addEventListener('DOMContentLoaded', function () {
  var params = new URLSearchParams(window.location.search);
  var q = params.get('q');
  if (q) { document.getElementById('kw').value = q; }
  insertLocalPost();
  applyResolved();
  setFilter('all');
});
