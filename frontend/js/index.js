/* 首页。
 *
 * 页面只做三件事：发请求、把响应渲染进 DOM、给出与改造前一致的交互反馈。
 * 分类筛选改为**重新请求后端**（不再读 DOM 上的 data-card 做前端过滤）；
 * 原先"读 localStorage 往列表顶部插卡片"的逻辑已整体移除——列表内容唯一来源
 * 是服务端，否则同一件物品会出现两张卡片。
 */

var currentHomeType = 'all';

/**
 * 切换分类并重新拉取列表。绑在三个标签按钮的 onclick 上。
 *
 * @param {string} type 'all' / 'seek' / 'find'
 * @returns {void}
 *
 * 注意这里只是把类型发给后端**重新请求**，不再像改造前那样遍历 DOM 上的
 * data-card 做前端显隐——筛选是服务端的事，前端只管渲染返回的结果。
 */
function filterList(type) {
  currentHomeType = type;
  document.querySelectorAll('[data-tab]').forEach(function (btn) {
    setTabClass(btn, btn.getAttribute('data-tab') === type);
  });
  loadHomeList();
}

/**
 * 按当前分类向后端要列表数据。
 *
 * @returns {void}（结果通过 renderHomeList 写入 DOM）
 *
 * 失败时弹一句「加载失败，请稍后重试」并留在原样，不抛到页面上——
 * 页面里没有专门的错误区域，也不新增错误 UI。
 */
function loadHomeList() {
  API.home(currentHomeType)
    .then(renderHomeList)
    .catch(function (error) {
      console.error(error);
      showToast('加载失败，请稍后重试');
    });
}

/**
 * 把接口返回的列表渲染进 #list，并更新条数。
 *
 * @param {{count: number, items: Array}} payload GET /api/items/home 的响应
 * @returns {void}
 *
 * 约束：#list 的直接子元素必须仍是 <a>（卡片模板产出），因为主题 CSS 用
 * `#list > a` 选中卡片；包一层 div 会让卡片静默失去左侧金线与圆角。
 * 条数取服务端返回的 count，而不是数一数渲染了几张卡片。
 */
function renderHomeList(payload) {
  var list = document.getElementById('list');
  list.innerHTML = payload.items
    .map(function (item) {
      return renderCard(item, 'home');
    })
    .join('');
  document.getElementById('listCount').textContent = payload.count;
}

/**
 * 首页搜索入口：把关键词带到搜索结果页。
 *
 * @param {Event} e 表单提交事件（用于阻止默认提交）
 * @returns {boolean} 恒为 false，保持行内 onsubmit 的返回值语义
 *
 * 关键词为空时不跳转，弹提示。这一段与改造前逐字一致，属于需求，不要"顺手优化"。
 */
function goSearch(e) {
  if (e) { e.preventDefault(); }
  var kw = document.getElementById('kw').value.trim();
  if (!kw) {
    showToast('请输入物品名称或关键词');
    return false;
  }
  window.location.href = 'search.html?q=' + encodeURIComponent(kw);
  return false;
}

window.addEventListener('DOMContentLoaded', function () {
  filterList('all');
});
