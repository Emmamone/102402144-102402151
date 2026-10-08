/* 信息详情页。
 *
 * 数据来自 **GET /api/items/{id}**，标记已解决走 **POST /api/items/{id}/resolve**
 * （阶段 3 / 4 改造完成）：页面既不自带数据，也不用 localStorage 记状态——
 * 状态由服务端保存，因此所有人看到的是同一份。
 *
 * 随改造删除的旧机制：
 *   - 页面内嵌的演示数据与 `buildNewItem`（新发布的数据改由服务端在发布时补全）
 *   - `?id=new` 这个特殊值（发布页现在带真实 id 跳转）
 *   - `campusResolved`（本机记"已解决"，已由服务端 status 取代）
 *
 * 移入 common.js 的部分：showToast、toastTimer、STATUS_TEXT（实现逐字相同；
 * 注意 STATUS_STYLE 是详情页专属的 rounded-full 变体，与列表卡片的不同，保留在本页）。
 * maskContact 也在 common.js，但本页已不再需要它（原本只有 buildNewItem 用）。
 */

var STATUS_STYLE = {
  seeking: 'shrink-0 px-2 py-0.5 rounded-full text-[10px] font-medium bg-orange-50 text-orange-600',
  unclaimed: 'shrink-0 px-2 py-0.5 rounded-full text-[10px] font-medium bg-amber-50 text-amber-600',
  resolved: 'shrink-0 px-2 py-0.5 rounded-full text-[10px] font-medium bg-emerald-50 text-emerald-600'
};

var currentId = '1';
var currentItem = null;

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
 * @param {Object} it 服务端返回的 DetailItem
 * @returns {void}
 *
 * 除了填字段，还做三件事：
 * 1. 每次渲染都把联系方式面板复原成"未展开"——展开是看一眼就够的动作，
 *    不该跨条目残留。
 * 2. 状态直接取数据自身的 `status`：服务端是状态的唯一来源。
 * 3. 按 `image` 决定图片区显示还是隐藏。无图时必须**移除 src**，
 *    否则切到下一条时浏览器会继续显示上一条的图。
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

  // 配图：有就显示，没有（或文件已不在）就整块隐藏
  var imageWrap = document.getElementById('dImageWrap');
  var image = document.getElementById('dImage');
  if (it.image) {
    image.src = '/uploads/' + it.image;
    image.alt = (it.name || '物品') + '的照片';
    imageWrap.classList.remove('hidden');
  } else {
    image.removeAttribute('src');     // 清掉上一条的图，避免切条目时残留
    imageWrap.classList.add('hidden');
  }

  document.getElementById('dAvatar').textContent = it.avatar;
  document.getElementById('dPublisher').textContent = it.publisher;
  document.getElementById('dContactMask').textContent = '联系方式：' + it.masked + '（点击下方按钮查看）';
  document.getElementById('dContactFull').textContent = it.contact;

  // 编号由服务端生成（LF-001 这种）；不再有 LF-NEW —— 新发布的数据也有真实编号
  document.getElementById('dCode').textContent = it.code;

  document.getElementById('dContactRevealed').classList.add('hidden');
  document.getElementById('dContactBtnWrap').classList.remove('hidden');

  applyStatus(it.status);
}

/**
 * 按 id 向服务端要一条详情并渲染。
 *
 * @param {string} id 物品 id
 * @returns {Promise<void>}
 *
 * 成功后把 currentId 记为服务端返回的 id（标记已解决时要用它拼接口路径），
 * 数字的字符串形式，与其它页面 data-id 的写法一致。
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
 * id 的两种情况：
 * - 带了 `?id`：请求 GET /api/items/{id}；**服务端返回 404 时回落去取 1 号**
 *   （沿用改造前的容错行为，让错误链接也有内容可看）。
 * - 缺参数：按 1 号处理。
 *
 * 不再有 `'new'` 这个特殊值——那是本机发布流程的产物，现在发布页带真实 id 跳转。
 */
function loadItem() {
  var id = new URLSearchParams(window.location.search).get('id') || '1';

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

/**
 * 标记已解决。绑在「标记为已找回 / 标记为已归还」按钮上。
 *
 * @returns {void}
 *
 * 调 POST /api/items/{id}/resolve，成功后用**服务端返回的数据**重新渲染；
 * 该接口在服务端是幂等的，重复点不会出错。
 *
 * 这里不做本地"乐观更新"（先改界面再等服务端）：万一请求失败，界面显示已解决、
 * 刷新后又变回去，反而更让人困惑。所以一律以服务端返回为准。
 */
function markResolved() {
  if (!currentItem) { return; }
  API.resolve(currentId)
    .then(function (updated) {
      currentItem = updated;
      render(updated);
      showToast('状态已更新为「已解决」');
    })
    .catch(function (error) {
      console.error(error);
      showToast('操作失败，请稍后重试');
    });
}

window.addEventListener('DOMContentLoaded', function () {
  // 图片加载失败（文件被删、地址失效）时隐藏整块，而不是留一个破图占位。
  // 只在启动时绑一次：render 每次渲染都会重设 src，重复绑定没必要
  document.getElementById('dImage').addEventListener('error', function () {
    document.getElementById('dImageWrap').classList.add('hidden');
  });
  loadItem();
});
