/* 发布成功页。
 *
 * 数据来自 **GET /api/items/{id}**（阶段 4 改造完成）：`?id` 由发布页在跳转时带上。
 *
 * 取值：
 *   1. URL 里的 `?id` → 向服务端查详情（正常路径）
 *   2. 写死的兜底摘要 → 直接打开本页（没带 `?id`）或查询失败时用，保证不空白。
 *
 * 随改造删除的旧机制：把 localStorage 当作数据源——包括发布页与本页之间用
 * `campusNewItem` 临时传递的那一级过渡分支（发布页已改为带真实 id 跳转）。
 */

//: 无 `?id` 且本机没发布过时展示的兜底摘要。
//: 沿用改造前写死的那份，内容本来就是照着 1 号物品抄的，所以「查看详情」指向它不矛盾。
var FALLBACK_SUMMARY = {
  name: '校园卡',
  type: 'seek',
  time: '2026-09-27 08:20',
  place: '图书馆二楼自习区',
  contact: '13800001234',
  publish: '2026-09-27 08:26'
};

/**
 * 把一条信息渲染进摘要卡片，并设置「查看详情」的跳转目标。
 *
 * @param {Object} item   服务端 DetailItem，或过渡分支/兜底给出的同形对象
 * @param {string} linkId 跳转用的物品 id；缺省（兜底路径）时退回 '1'
 * @returns {void}
 *
 * 联系方式优先用服务端已经脱敏好的 `masked`；过渡分支与兜底里只有原始 `contact`，
 * 这时才用 common.js 的 maskContact 现算。
 */
function renderSummary(item, linkId) {
  var isSeek = (item.type === 'seek');

  document.getElementById('sName').textContent = item.name || '未命名物品';

  var tag = document.getElementById('sType');
  tag.textContent = isSeek ? '寻物' : '招领';
  tag.className = 'shrink-0 px-1.5 py-0.5 rounded text-[10px] font-medium ' +
    (isSeek ? 'bg-blue-50 text-blue-600' : 'bg-emerald-50 text-emerald-600');

  document.getElementById('sTimeLabel').textContent = isSeek ? '丢失时间' : '拾取时间';
  document.getElementById('sTime').textContent = item.time || '—';
  document.getElementById('sPlace').textContent = item.place || '—';
  document.getElementById('sContact').textContent = item.masked || maskContact(item.contact);
  document.getElementById('sPublish').textContent = item.publish || '刚刚';

  // 链接必须动态设置：写死成 detail.html?id=new 的话，详情页已经没有 new 分支了
  document.getElementById('sDetailLink').href = 'detail.html?id=' + (linkId || '1');
}

/**
 * 没有 `?id`（或按 `?id` 查询失败）时的退路：直接用写死的兜底摘要。
 *
 * @returns {void}
 *
 * 兜底只是"别让页面空白"的展示数据，背后没有真实记录；「查看详情」因此指向 1 号
 * ——兜底内容本来就是照着 1 号抄的，指过去不矛盾。
 */
function renderFallback() {
  renderSummary(FALLBACK_SUMMARY, null);
}

/**
 * 页面启动：决定摘要数据从哪来，然后渲染。启动时调用一次。
 *
 * @returns {void}
 *
 * 带 `?id` 就走接口，且**请求失败也退回兜底**——成功页是发布流程的终点，
 * 在这里给用户一个错误提示没有意义，不如照旧显示摘要让他能继续操作。
 */
function fillSummary() {
  var id = new URLSearchParams(window.location.search).get('id');

  if (!id) {
    renderFallback();
    return;
  }

  API.detail(id)
    .then(function (item) {
      renderSummary(item, item.id);
    })
    .catch(function (error) {
      console.error(error);
      renderFallback();
    });
}

window.addEventListener('DOMContentLoaded', fillSummary);
