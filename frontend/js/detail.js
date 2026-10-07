/* 信息详情页。
 *
 * 数据来自 **GET /api/items/{id}**（阶段 3 改造完成）：页面不再内嵌演示数据，
 * 编号、脱敏串、发布时间等全部由服务端给出。
 *
 * 唯一还读 localStorage 的地方是 `?id=new` 分支：那是本机发布流程的产物
 * （见 publish.js），等阶段 4 把发布改成接口、成功页改为带真实 id 之后，
 * 该分支与 buildNewItem 一并删除。
 *
 * 移入 common.js 的部分：maskContact、showToast、toastTimer、STATUS_TEXT
 * （实现逐字相同；注意 STATUS_STYLE 是详情页专属的 rounded-full 变体，与列表卡片
 * 的不同，因此保留在本页）。
 */

var STATUS_STYLE = {
  seeking: 'shrink-0 px-2 py-0.5 rounded-full text-[10px] font-medium bg-orange-50 text-orange-600',
  unclaimed: 'shrink-0 px-2 py-0.5 rounded-full text-[10px] font-medium bg-amber-50 text-amber-600',
  resolved: 'shrink-0 px-2 py-0.5 rounded-full text-[10px] font-medium bg-emerald-50 text-emerald-600'
};

var currentId = '1';
var currentItem = null;

/**
 * 读出本机标记为已解决的物品 id 列表。
 *
 * @returns {Array<string>} id 数组；localStorage 不可用或内容损坏时返回空数组
 *
 * 这是"标记已解决"这个**写路径**还没改成接口之前的过渡机制（阶段 4 处理）。
 * 读路径已不再依赖它——服务端会返回 status。
 */
function getResolvedIds() {
  try {
    return JSON.parse(localStorage.getItem('campusResolved') || '[]');
  } catch (err) {
    return [];
  }
}

/**
 * 把"已解决"的 id 列表写回 localStorage。
 *
 * @param {Array<string>} list 完整的 id 列表（调用方负责先 push 再传进来）
 * @returns {void}
 *
 * 写入失败（隐私模式、配额满）时静默忽略：状态更新不是关键路径，
 * 为了它弹一个错误提示反而打扰用户。
 */
function saveResolvedIds(list) {
  try {
    localStorage.setItem('campusResolved', JSON.stringify(list));
  } catch (err) { /* 本地存储不可用时忽略 */ }
}

/**
 * 把发布页存在本机的那条数据，补全成详情页渲染需要的形状。
 *
 * @param {Object} s localStorage 里的 campusNewItem：{name, type, category, time,
 *                     place, desc, contact, publish}
 * @returns {Object} 与接口返回的详情同一套字段名（缺 code，渲染时会兜底）
 *
 * 补全规则：状态按类型给（寻物=寻找中、招领=待认领，**永远不是已解决**）、
 * 图标取通用的问号/手形图标、发布者固定为「我（本机发布）」、头像固定为「我」、
 * 脱敏串由 contact 现算。其余字段为空时套一组兜底值，保证页面不出现空白。
 *
 * 只服务于 `?id=new`（本机发布流程）。阶段 4 起这些补全改由服务端在发布时完成，
 * 本函数与 loadItem 里的 new 分支一并删除。
 */
function buildNewItem(s) {
  var isSeek = s.type === 'seek';
  return {
    name: s.name || '校园卡',
    type: isSeek ? 'seek' : 'find',
    status: isSeek ? 'seeking' : 'unclaimed',
    icon: isSeek ? 'mdi:help-circle-outline' : 'mdi:hand-heart-outline',
    category: s.category || '其他',
    timeLabel: isSeek ? '丢失时间' : '拾取时间',
    time: s.time || '—',
    place: s.place || '第二教学楼',
    publish: s.publish || '刚刚',
    desc: s.desc || '暂未填写补充描述。',
    publisher: '我（本机发布）',
    masked: maskContact(s.contact),
    contact: s.contact || '—',
    avatar: '我'
  };
}

/* 状态徽标与下方按钮的联动：已解决时按钮置灰禁用，文案改为「已标记为已解决」 */
function applyStatus(state) {
  var badge = document.getElementById('dStatus');
  badge.textContent = STATUS_TEXT[state] || '寻找中';
  badge.className = STATUS_STYLE[state] || STATUS_STYLE.seeking;

  var done = (state === 'resolved');
  var btn = document.getElementById('dResolveBtn');
  btn.disabled = done;
  btn.className = 'flex items-center justify-center gap-1.5 w-full h-11 mt-3 rounded-xl border text-[14px] font-semibold ' +
    (done ? 'border-slate-200 bg-slate-100 text-slate-400' : 'border-blue-200 bg-blue-50 text-blue-600 active:bg-blue-100');

  var label = document.getElementById('dResolveText');
  if (done) {
    label.textContent = '已标记为已解决';
  } else {
    label.textContent = (currentItem && currentItem.type === 'seek') ? '标记为已找回' : '标记为已归还';
  }
}

/**
 * 把一条物品的全部字段写进详情页的各个占位元素。
 *
 * @param {Object} it 服务端 DetailItem 的产物，或 buildNewItem 的产物
 * @returns {void}
 *
 * 除了填字段，还做两件事：
 * 1. 每次渲染都把联系方式面板复原成"未展开"——展开是看一眼就够的动作，
 *    不该跨条目残留。
 * 2. 计算最终状态：本机 localStorage 标记过（写路径的过渡机制），
 *    或数据自身 status 就是已解决，都算已解决。
 *
 * 约束：这里逐个 `getElementById` 写 textContent，元素 id 与页面严重耦合，
 * 改 HTML 时要一起改（见 docs/system-design.md 第 7.2 节的 id 清单）。
 */
function render(it) {
  var isSeek = (it.type === 'seek');

  document.getElementById('dName').textContent = it.name;

  var typeTag = document.getElementById('dType');
  typeTag.textContent = isSeek ? '寻物' : '招领';
  typeTag.className = 'shrink-0 px-1.5 py-0.5 rounded text-[10px] font-medium ' +
    (isSeek ? 'bg-blue-50 text-blue-600' : 'bg-emerald-50 text-emerald-600');

  document.getElementById('dIcon').setAttribute('icon', it.icon);
  document.getElementById('dIcon').className = 'text-[28px] ' + (isSeek ? 'text-blue-600' : 'text-emerald-600');
  document.getElementById('dIconBox').className = 'w-14 h-14 rounded-2xl flex items-center justify-center shrink-0 ' +
    (isSeek ? 'bg-blue-50' : 'bg-emerald-50');

  document.getElementById('dPublish').textContent = '发布于 ' + it.publish;
  document.getElementById('dPublishRow').textContent = it.publish;
  document.getElementById('dCategory').textContent = it.category;
  document.getElementById('dTimeLabel').textContent = it.timeLabel;
  document.getElementById('dTime').textContent = it.time;
  document.getElementById('dPlace').textContent = it.place;
  document.getElementById('dDesc').textContent = it.desc;

  document.getElementById('dAvatar').textContent = it.avatar;
  document.getElementById('dPublisher').textContent = it.publisher;
  document.getElementById('dContactMask').textContent = '联系方式：' + it.masked + '（点击下方按钮查看）';
  document.getElementById('dContactFull').textContent = it.contact;

  // 编号由服务端生成（LF-001 这种）；本机刚发布的那条还没有真实编号，沿用旧的 LF-NEW
  document.getElementById('dCode').textContent = it.code || 'LF-NEW';

  document.getElementById('dContactRevealed').classList.add('hidden');
  document.getElementById('dContactBtnWrap').classList.remove('hidden');

  var resolved = (getResolvedIds().indexOf(currentId) !== -1) || (it.status === 'resolved');
  applyStatus(resolved ? 'resolved' : it.status);
}

/**
 * 按 id 向服务端要一条详情并渲染。
 *
 * @param {string} id 物品 id
 * @returns {Promise<void>}
 *
 * 成功后把 currentId 记为服务端返回的 id（markResolved 与 getResolvedIds 的
 * 比较都依赖它，必须与其它页面 data-id 的写法一致，即数字的字符串形式）。
 * 失败时原样抛出，由 loadItem 决定是回落还是提示。
 */
function loadItemById(id) {
  return API.detail(id).then(function (item) {
    currentId = String(item.id);
    currentItem = item;
    render(item);
  });
}

/**
 * 取 ?id 参数，加载并渲染对应物品。页面启动时调用一次。
 *
 * @returns {void}
 *
 * id 的三种情况：
 * - 正常 id：请求 GET /api/items/{id}；**服务端返回 404 时回落去取 1 号**
 *   （沿用改造前的容错行为，让错误链接也有内容可看）。
 * - 'new'：本机发布流程的过渡分支，读 localStorage 里刚发布的那条；
 *   本机没有记录时同样回落到 1 号。
 * - 缺参数：按 1 号处理。
 */
function loadItem() {
  var params = new URLSearchParams(window.location.search);
  var id = params.get('id') || '1';

  if (id === 'new') {
    var saved = null;
    try {
      saved = JSON.parse(localStorage.getItem('campusNewItem') || 'null');
    } catch (err) {
      saved = null;
    }
    if (saved) {
      currentId = 'new';
      currentItem = buildNewItem(saved);
      render(currentItem);
      return;
    }
    id = '1';
  }

  loadItemById(id).catch(function (error) {
    console.error(error);
    if (error.status === 404 && String(id) !== '1') {
      loadItemById('1').catch(function (fallbackError) {
        console.error(fallbackError);
        showToast('加载失败，请稍后重试');
      });
      return;
    }
    showToast('加载失败，请稍后重试');
  });
}

/**
 * 展开完整联系方式。绑在「联系发布者」按钮上。
 *
 * @returns {void}
 *
 * 做的是"换一块"而不是"展开一段"：隐藏按钮、显示下方面板，避免按钮和已展开的
 * 内容同时出现。完整联系方式随接口一起返回、已在页面里，这一步只是从隐藏变成
 * 可见，没有二次请求，也不做权限校验（与改造前一致，属已知限制）。
 */
function revealContact() {
  document.getElementById('dContactRevealed').classList.remove('hidden');
  document.getElementById('dContactBtnWrap').classList.add('hidden');
  showToast('已显示发布者联系方式');
}

/* 标记已解决：当前把 id 写进 localStorage（阶段 4 起改为 POST /api/items/{id}/resolve） */
function markResolved() {
  if (!currentItem) { return; }
  var ids = getResolvedIds();
  if (ids.indexOf(currentId) === -1) { ids.push(currentId); }
  saveResolvedIds(ids);
  applyStatus('resolved');
  showToast('状态已更新为「已解决」');
}

window.addEventListener('DOMContentLoaded', function () {
  loadItem();
});
