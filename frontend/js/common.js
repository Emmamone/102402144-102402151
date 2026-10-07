/* 跨页共用的展示层工具与常量。
 *
 * 这里的函数都是**全局函数声明**，不要包进立即执行函数、也不要用
 * <script type="module">：页面里保留了行内事件属性（onclick / onsubmit），
 * 模块作用域下这些函数不存在，按钮会集体失效。
 */

var TAB_ON = ['bg-blue-600', 'text-white', 'border-blue-600'];
var TAB_OFF = ['bg-white', 'text-slate-500', 'border-slate-200'];

var TYPE_TEXT = { seek: '寻物', find: '招领' };
var STATUS_TEXT = { seeking: '寻找中', unclaimed: '待认领', resolved: '已解决' };
var STATUS_CLASS = {
  seeking: 'bg-orange-50 text-orange-600',
  unclaimed: 'bg-amber-50 text-amber-600',
  resolved: 'bg-emerald-50 text-emerald-600'
};
var TYPE_TAG_CLASS = { seek: 'bg-blue-50 text-blue-600', find: 'bg-emerald-50 text-emerald-600' };
var TYPE_ICON_BOX_CLASS = { seek: 'bg-blue-50', find: 'bg-emerald-50' };
var TYPE_ICON_CLASS = { seek: 'text-blue-600', find: 'text-emerald-600' };

var toastTimer = null;

function setTabClass(btn, on) {
  TAB_ON.forEach(function (c) { btn.classList.toggle(c, on); });
  TAB_OFF.forEach(function (c) { btn.classList.toggle(c, !on); });
}

/**
 * 提示条。duration 可省略，默认 1800ms。
 * 发布页的提示原本是 2000ms，为避免"提取共用代码顺手改了行为"，用参数保留差异。
 */
function showToast(msg, duration) {
  var toast = document.getElementById('toast');
  if (!toast) { return; }
  toast.textContent = msg;
  toast.classList.remove('hidden');
  if (toastTimer) { clearTimeout(toastTimer); }
  toastTimer = setTimeout(function () { toast.classList.add('hidden'); }, duration || 1800);
}

function escapeHtml(value) {
  return String(value === null || value === undefined ? '' : value).replace(/[&<>"']/g, function (ch) {
    return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[ch];
  });
}

/* 仅供发布成功页在"无参数/请求失败"时展示兜底摘要使用；
 * 正常路径下脱敏由服务端完成（返回 masked 字段）。 */
function maskContact(c) {
  if (!c) { return '—'; }
  if (/^1\d{10}$/.test(c)) { return c.slice(0, 3) + '****' + c.slice(7); }
  if (c.length > 4) { return c.slice(0, 2) + '****' + c.slice(-2); }
  return c;
}

/**
 * 渲染一张列表卡片，返回 HTML 字符串。
 *
 * variant: 'home'   → 输出 data-card 属性（首页）
 *          'search' → 输出 data-result 与 data-keywords 属性（搜索页）
 *
 * 这两个属性不是摆设：主题 CSS 用 `#list > a, #resultList [data-result]`
 * 选中卡片，漏掉属性会让卡片静默丢掉左侧金线与圆角，且不会报错。
 *
 * 所有来自接口的值都经 escapeHtml 转义后再写入 innerHTML
 * （见 docs/coding-standards.md 第 5.4 节）。
 */
function renderCard(item, variant) {
  var type = item.type === 'find' ? 'find' : 'seek';
  var resolved = item.status === 'resolved';
  var attrs = ' data-id="' + escapeHtml(item.id) + '"';
  if (variant === 'search') {
    attrs += ' data-result="' + type + '" data-keywords="' + escapeHtml(item.keywords) + '"';
  } else {
    attrs += ' data-card="' + type + '"';
  }

  return (
    '<a class="rounded-2xl bg-white p-4 border border-slate-100 shadow-sm transition active:scale-[0.99]' +
      (resolved ? ' opacity-80' : '') + '"' + attrs +
      ' href="detail.html?id=' + encodeURIComponent(item.id) + '">' +
      '<div class="flex items-start gap-3">' +
        '<div class="w-11 h-11 shrink-0 rounded-xl ' + TYPE_ICON_BOX_CLASS[type] + ' flex items-center justify-center">' +
          '<iconify-icon class="text-[22px] ' + TYPE_ICON_CLASS[type] + '" icon="' + escapeHtml(item.icon) + '"></iconify-icon>' +
        '</div>' +
        '<div class="min-w-0 flex-1">' +
          '<div class="flex items-center gap-1.5">' +
            '<h3 class="min-w-0 text-[15px] font-semibold text-slate-800 truncate">' + escapeHtml(item.name) + '</h3>' +
            '<span class="shrink-0 px-1.5 py-0.5 rounded text-[10px] font-medium ' + TYPE_TAG_CLASS[type] + '">' + TYPE_TEXT[type] + '</span>' +
            '<span class="ml-auto shrink-0 px-1.5 py-0.5 rounded text-[10px] font-medium ' + STATUS_CLASS[item.status] + '" data-status="">' +
              escapeHtml(STATUS_TEXT[item.status]) + '</span>' +
          '</div>' +
          '<div class="mt-1.5 flex items-center gap-3 text-[11px] text-slate-400">' +
            '<span class="shrink-0 flex items-center gap-0.5">' +
              '<iconify-icon class="text-[13px]" icon="mdi:clock-outline"></iconify-icon>' + escapeHtml(item.time) +
            '</span>' +
            '<span class="flex items-center gap-0.5 min-w-0">' +
              '<iconify-icon class="text-[13px] shrink-0" icon="mdi:map-marker-outline"></iconify-icon>' +
              '<span class="truncate">' + escapeHtml(item.place) + '</span>' +
            '</span>' +
          '</div>' +
          '<p class="mt-1.5 text-[12px] leading-relaxed text-slate-500 line-clamp-2">' + escapeHtml(item.desc) + '</p>' +
        '</div>' +
      '</div>' +
    '</a>'
  );
}
