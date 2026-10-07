/* 发布成功页。
 *
 * 数据来自 **GET /api/items/{id}**（阶段 4 改造完成）：`?id` 由发布页在跳转时带上。
 *
 * 取值优先级（前两级是过渡状态，见下）：
 *   1. URL 里的 `?id` → 向服务端查详情（正常路径）
 *   2. localStorage 的 `campusNewItem` → **过渡分支**：publish.js 还没改成
 *      "提交到接口后带着新 id 跳转"（任务 ④），在那之前发布页跳过来是不带 `?id` 的。
 *      不保留这一级的话，刚发布完的人会看到一份跟自己的信息无关的假摘要——
 *      那比"暂时多一个分支"糟得多。④ 落地后连同它一起删除。
 *   3. 写死的兜底摘要 → 直接打开本页（没带 `?id`、本机也没发布过）时用，保证不空白。
 *
 * 随改造删除的旧机制：把 localStorage 当作唯一数据源。
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
 * 没有 `?id`（或按 `?id` 查询失败）时的退路。
 *
 * @returns {void}
 *
 * 先看本机有没有刚发布的那条（过渡分支，任务 ④ 完成后删除），再没有才用写死的兜底。
 */
function renderFallback() {
  var saved = null;
  try {
    saved = JSON.parse(localStorage.getItem('campusNewItem') || 'null');
  } catch (err) {
    saved = null;
  }
  renderSummary(saved || FALLBACK_SUMMARY, null);
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
