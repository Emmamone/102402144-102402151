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

/**
 * 读出本机标记为已解决的物品 id 列表。
 *
 * @returns {Array<string>} id 数组；localStorage 不可用或内容损坏时返回空数组
 *
 * 这是阶段 0 保留的旧机制，只影响本机显示。阶段 3 起状态由服务端 status 字段
 * 决定，届时本函数与 applyResolved 一并删除。
 */
function getResolvedIds() {
  try {
    return JSON.parse(localStorage.getItem('campusResolved') || '[]');
  } catch (err) {
    return [];
  }
}

/**
 * 把本机标记过已解决的那些卡片，状态徽标改成灰色「已解决」。
 *
 * @returns {void}
 *
 * 只改徽标的文字与类名，不动卡片的其它部分（所以被本机标记的卡片不会有
 * 服务端数据里那种整体弱化效果）。阶段 3 起由服务端 status 决定，本函数删除。
 */
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

/* 把本机刚发布的那条插到结果最上面（阶段 0 原样保留；阶段 3 起由服务端返回，届时整个函数删除） */
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

/* 前端筛选：对每张卡片的 data-keywords 做子串匹配，再按 data-result 过滤类型（阶段 3 起改为请求后端） */
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

/**
 * 切换结果页的类型筛选。绑在三个标签按钮的 onclick 上。
 *
 * @param {string} type 'all' / 'seek' / 'find'
 * @returns {void}
 *
 * 与首页不同，这里不重新请求后端（搜索页仍是阶段 0 的实现），
 * 只是改 currentType 后重跑一次前端筛选。阶段 3 起改为请求接口。
 */
function setFilter(type) {
  currentType = type;
  document.querySelectorAll('[data-tab]').forEach(function (btn) {
    setTabClass(btn, btn.getAttribute('data-tab') === type);
  });
  runSearch();
}

/**
 * 提交搜索：按当前输入框内容重搜，并把类型重置为「全部」。
 *
 * @param {Event} e 表单提交事件（可为 null，quickSearch 会这样调用）
 * @returns {boolean} 恒为 false，保持行内 onsubmit 的返回值语义
 *
 * 重置类型是既有行为：换关键词时先把筛选放回「全部」，避免"上次筛了招领、
 * 这次搜出来啥也没有"的困惑。
 */
function onSubmitSearch(e) {
  if (e) { e.preventDefault(); }
  currentType = 'all';
  document.querySelectorAll('[data-tab]').forEach(function (btn) {
    setTabClass(btn, btn.getAttribute('data-tab') === 'all');
  });
  runSearch();
  return false;
}

/**
 * 快捷搜索：无结果时点下方的常见关键词标签。
 *
 * @param {string} kw 要填入搜索框的关键词
 * @returns {void}
 *
 * 先把词写进输入框（让用户看得见搜的是什么），再复用提交逻辑重搜。
 */
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
