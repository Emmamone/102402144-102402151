/* 搜索结果页。
 *
 * 数据来自 **GET /api/items/search**（阶段 3 改造完成）：关键词匹配与类型筛选都由
 * 服务端完成，结果顺序也是服务端排好的（演示数据为 1、7、5、3、2、4、6、8，
 * 用户新发布的排在最前）。本页只负责渲染，不再遍历 DOM 做匹配。
 *
 * 随改造删除的旧机制（阶段 0 曾原样保留）：
 *   - runSearch 里对每张卡片 data-keywords 的前端子串匹配
 *   - insertLocalPost：把本机发布的那条插到结果顶部
 *   - getResolvedIds / applyResolved：已解决状态改由服务端的 status 字段给出
 *
 * 注意本页**没有提示条元素**（`#toast` 只存在于首页/详情页/发布页），所以
 * showToast 在这里是空操作，请求失败只会在控制台留痕——这是既有设计的取舍，
 * 见 docs/system-design.md 第 7.2 节。
 */

var currentType = 'all';

/**
 * 按当前关键词与类型重新搜索并渲染。
 *
 * @returns {void}
 *
 * 关键词取输入框的当前值（空串表示不按关键词过滤），类型取 currentType，
 * 两者都作为查询参数发给服务端，前端不做任何过滤或排序。
 *
 * 失败时只往控制台打日志：本页没有提示条，也不新增错误 UI。
 */
function runSearch() {
  var kw = document.getElementById('kw').value.trim();
  API.search(kw, currentType)
    .then(function (payload) {
      renderResults(kw, payload);
    })
    .catch(function (error) {
      console.error(error);
      showToast('加载失败，请稍后重试');
    });
}

/**
 * 把搜索结果渲染进列表，并更新条数、关键词回显与空状态。
 *
 * @param {string} kw 当前关键词，用于回显；空串时回显「全部物品」
 * @param {{count: number, items: Array}} payload GET /api/items/search 的响应
 * @returns {void}
 *
 * 条数取服务端返回的 count，而不是数一数渲染了几张卡片。
 * 卡片用 renderCard(item, 'search') 生成——它会带上 data-result 与 data-keywords，
 * 主题 CSS 靠 `#resultList [data-result]` 选中卡片，漏掉属性会静默丢掉左侧金线。
 */
function renderResults(kw, payload) {
  document.getElementById('resultItems').innerHTML = payload.items
    .map(function (item) {
      return renderCard(item, 'search');
    })
    .join('');
  document.getElementById('resultCount').textContent = payload.count;
  document.getElementById('kwEcho').textContent = kw || '全部物品';
  document.getElementById('resultList').classList.toggle('hidden', payload.count === 0);
  document.getElementById('emptyState').classList.toggle('hidden', payload.count > 0);
}

/**
 * 切换结果页的类型筛选。绑在三个标签按钮的 onclick 上。
 *
 * @param {string} type 'all' / 'seek' / 'find'
 * @returns {void}
 *
 * 只更新 currentType 与标签选中态，随后重新请求后端——类型过滤在服务端做，
 * 不是把已渲染的卡片藏起来。
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
  setFilter('all');
});
