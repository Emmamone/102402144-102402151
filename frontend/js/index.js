/* 首页。
 *
 * 页面只做三件事：发请求、把响应渲染进 DOM、给出与改造前一致的交互反馈。
 * 分类筛选改为**重新请求后端**（不再读 DOM 上的 data-card 做前端过滤）；
 * 原先"读 localStorage 往列表顶部插卡片"的逻辑已整体移除——列表内容唯一来源
 * 是服务端，否则同一件物品会出现两张卡片。
 */

var currentHomeType = 'all';

function filterList(type) {
  currentHomeType = type;
  document.querySelectorAll('[data-tab]').forEach(function (btn) {
    setTabClass(btn, btn.getAttribute('data-tab') === type);
  });
  loadHomeList();
}

function loadHomeList() {
  API.home(currentHomeType)
    .then(renderHomeList)
    .catch(function (error) {
      console.error(error);
      showToast('加载失败，请稍后重试');
    });
}

function renderHomeList(payload) {
  var list = document.getElementById('list');
  list.innerHTML = payload.items
    .map(function (item) {
      return renderCard(item, 'home');
    })
    .join('');
  document.getElementById('listCount').textContent = payload.count;
}

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
