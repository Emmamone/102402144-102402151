/* 发布成功页。
 *
 * 阶段 0 的机械拆分：内容逐字取自本页原先的内联 <script>，**未改变任何行为**。
 * maskContact 已移入 common.js（实现逐字相同）。
 *
 * 本页仍从 localStorage 的 campusNewItem 读数据、并保留写死的兜底摘要 ——
 * 留待阶段 4 改造为按 ?id 向服务端查询。
 */

function fillSummary() {
  var saved = null;
  try {
    saved = JSON.parse(localStorage.getItem('campusNewItem') || 'null');
  } catch (err) {
    saved = null;
  }

  var item = saved || {
    name: '校园卡',
    type: 'seek',
    time: '2026-09-27 08:20',
    place: '图书馆二楼自习区',
    contact: '13800001234',
    publish: '2026-09-27 08:26'
  };

  var isSeek = (item.type === 'seek');

  document.getElementById('sName').textContent = item.name || '未命名物品';
  var tag = document.getElementById('sType');
  tag.textContent = isSeek ? '寻物' : '招领';
  tag.className = 'shrink-0 px-1.5 py-0.5 rounded text-[10px] font-medium ' +
    (isSeek ? 'bg-blue-50 text-blue-600' : 'bg-emerald-50 text-emerald-600');

  document.getElementById('sTimeLabel').textContent = isSeek ? '丢失时间' : '拾取时间';
  document.getElementById('sTime').textContent = item.time || '—';
  document.getElementById('sPlace').textContent = item.place || '—';
  document.getElementById('sContact').textContent = maskContact(item.contact);
  document.getElementById('sPublish').textContent = item.publish || '刚刚';
}

window.addEventListener('DOMContentLoaded', fillSummary);
