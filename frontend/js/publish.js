/* 发布信息页。
 *
 * 提交走 **POST /api/items**：成功后带着服务端返回的新 id 跳到
 * `success.html?id=<新id>`，成功页据此查详情。
 *
 * **图片是两步**：先在下面裁好、导出成 JPEG，`POST /api/uploads` 拿到文件名，
 * 再把它放进发布请求的 `image` 字段。裁剪全部在浏览器完成（服务端没有图片库），
 * 详情页展示的比例与裁切视口一致（`.photo-frame`，见 theme），
 * 所以"框里看到的就是详情页看到的"。
 *
 * 随改造删除的旧机制：把数据写进 localStorage 的 `campusNewItem`
 * （发布页与成功页之间的临时传递），以及前端算的 `formatDateTime`
 * ——发布时间由服务端生成，不用客户端时钟。
 *
 * showToast / toastTimer 在 common.js；本页的提示时长是 2000ms（其余页 1800ms），
 * 为不改变行为，调用处显式传入 2000。
 *
 * 校验逻辑与全部错误文案**逐字保留**（这些属于需求，不得"顺手优化"）。
 */

//: 提交中标志：防止连点。一次点击会发出"上传 + 发布"两条请求，重复提交的代价更大
//: （同一张图传两遍、同一条信息插两次），所以这个守卫比没有图片时更重要。
var submitting = false;

/* ---------- 物品图片：选图 → 在图上拖框选 → 随发布一起上传 ---------- */

//: 导出图片的最长边（像素）。压到这个尺寸，一张图通常 100-300KB
var EXPORT_MAX_SIDE = 1280;
//: 导出质量（JPEG）
var EXPORT_QUALITY = 0.85;
//: 原图大小上限，与后端 uploads.MAX_UPLOAD_BYTES 一致（那边是兜底）
var MAX_SOURCE_BYTES = 5 * 1024 * 1024;
//: 框选比例 4:3，与详情页的展示框一致（theme 里的 .photo-frame）。
//: 锁死比例是为了"框里框到的 == 详情页看到的"——自由比例的话，详情页的
//: object-cover 会再裁一次，用户的选择就白做了。
var SELECT_ASPECT = 4 / 3;
//: 框选的最小宽度（原图像素）。比这更小的话导出会糊得没法看
var MIN_SELECT_WIDTH = 60;
//: 角柄的命中半径（**屏幕**像素）。角柄只画了 14px 宽，但手指按不了那么准，
//: 所以热区放宽；按屏幕而不是原图像素算，是因为"好不好按"取决于屏幕上的大小
var HANDLE_HIT_PX = 22;

//: 选中的原图（未选时为 null）
var stagedImage = null;
//: 上面那张图的 objectURL。换图或移除时必须 revoke，否则整张图会一直占着内存
var stagedObjectUrl = null;

//: **框选结果，直接用源图像素表示**：{x, y, w, h}。
//: 用源图坐标而不是屏幕坐标，有两个好处：窗口尺寸一变显示尺寸就变了，而源图坐标
//: 不受影响（重排一下显示位置即可）；导出时它就是 drawImage 要的那块矩形，不用换算。
var selection = null;
//: 当前手势：'draw' = 拖出一个新框，'move' = 挪动现有的框；null 表示没在拖
var dragMode = null;
//: 手势起点：按下时的源图坐标 + 按下时的框（撤回时要用）
var dragOrigin = null;
//: 正在操作的那个指针 id。多指同时按时只认第一个手指——否则第二根手指会把
//: 起点覆盖掉，两根手指互相抢，框会乱跳。别的指针的 move/up 一律忽略
var dragPointerId = null;

var SELECTED = ['border-blue-600', 'bg-blue-50'];
var NORMAL = ['border-slate-200', 'bg-white'];
var CHIP_ON = ['border-blue-600', 'bg-blue-50', 'text-blue-600'];
var CHIP_OFF = ['border-slate-200', 'bg-white', 'text-slate-600'];
var currentType = 'seek';

/**
 * 切换发布类型（寻物 / 招领）。绑在两个类型按钮的 onclick 上。
 *
 * @param {string} type 'seek' 或 'find'
 * @returns {void}
 *
 * 除了按钮选中态，还要连带改写四样东西，因为它们都随类型变：
 * 时间与地点的标签文案、地点输入框的占位提示、以及这两项的错误提示文案。
 * 漏改任何一处，用户就会看到"招领"表单上写着"丢失时间"。
 */
function setType(type) {
  currentType = type;
  document.querySelectorAll('[data-type]').forEach(function (btn) {
    var on = btn.getAttribute('data-type') === type;
    SELECTED.forEach(function (c) { btn.classList.toggle(c, on); });
    NORMAL.forEach(function (c) { btn.classList.toggle(c, !on); });
  });
  var isSeek = type === 'seek';
  document.getElementById('timeLabel').innerHTML = (isSeek ? '丢失时间' : '拾取时间') + ' <span class="text-rose-500">*</span>';
  document.getElementById('placeLabel').innerHTML = (isSeek ? '丢失地点' : '拾取地点') + ' <span class="text-rose-500">*</span>';
  document.getElementById('fPlace').setAttribute('placeholder', isSeek ? '例如：图书馆二楼自习区' : '例如：第二食堂一楼靠窗餐位');
  document.getElementById('eTime').textContent = isSeek ? '请选择丢失时间' : '请选择拾取时间';
  document.getElementById('ePlace').textContent = isSeek ? '请填写丢失地点' : '请填写拾取地点';
}

/**
 * 选中物品类别。绑在 7 个类别标签的 onclick 上。
 *
 * @param {HTMLElement} btn 被点击的类别按钮
 * @returns {void}
 *
 * 类别值取的是按钮**文案**（去空格后写进隐藏字段 fCategory），所以改标签文字
 * 就等于改提交值，必须与后端 schemas.py 的 CATEGORIES 保持一致。
 */
function setCat(btn) {
  document.querySelectorAll('#catWrap button').forEach(function (b) {
    var on = (b === btn);
    CHIP_ON.forEach(function (c) { b.classList.toggle(c, on); });
    CHIP_OFF.forEach(function (c) { b.classList.toggle(c, !on); });
  });
  document.getElementById('fCategory').value = btn.textContent.trim();
  clearError('fCategory', 'eCategory');
}

/**
 * 清掉某个字段的错误态：恢复边框颜色、隐藏错误文案。
 *
 * @param {string} inputId 输入框的 id
 * @param {string} errId   该字段错误提示 <p> 的 id
 * @returns {void}
 *
 * 目前只在选类别时调用（选完就不该还标红）。隐藏字段（fCategory 是 input[type=hidden]）
 * 没有边框可恢复，所以跳过边框处理。
 */
function clearError(inputId, errId) {
  var input = document.getElementById(inputId);
  if (input && input.type !== 'hidden') {
    input.classList.remove('border-rose-400');
    input.classList.add('border-slate-200');
  }
  document.getElementById(errId).classList.add('hidden');
}

/* ---------- 框选：坐标换算与框的摆放 ---------- */

/**
 * 取框选舞台（也就是图片显示区域）的尺寸。
 *
 * @returns {{width: number, height: number}} CSS 像素。
 *
 * 图片用 `block w-full h-auto` 摆放，所以舞台的框**就是**图片本身——不存在
 * "图比容器小、上下留白"那种 letterbox 情况，坐标换算因此只有一个比例因子。
 * 每次现取而不缓存：手机画布是响应式的（`min(393px, 100vw)`），窗口一变就不同了。
 */
function stageSize() {
  var box = document.getElementById('cropStage').getBoundingClientRect();
  return { width: box.width, height: box.height };
}

/**
 * 把指针的屏幕坐标换算成**原图像素坐标**。
 *
 * @param {PointerEvent} event
 * @returns {{x: number, y: number}} 可能落在图片之外，由调用方负责夹取。
 */
function toSourcePoint(event) {
  var box = document.getElementById('cropStage').getBoundingClientRect();
  return {
    x: (event.clientX - box.left) * (stagedImage.naturalWidth / box.width),
    y: (event.clientY - box.top) * (stagedImage.naturalHeight / box.height)
  };
}

/**
 * 算出图片内**最大的、居中的 4:3 框**——选完图之后的初始框。
 *
 * @returns {{x: number, y: number, w: number, h: number}} 源图像素。
 *
 * 比 4:3 宽的图受高度限制，比 4:3 高的图受宽度限制——两种情况的"最大能有多大"
 * 不一样，得分开算，否则会算出超出图片边界的框。
 */
function defaultSelection() {
  var nw = stagedImage.naturalWidth;
  var nh = stagedImage.naturalHeight;
  var width, height;

  if (nw / nh > SELECT_ASPECT) {
    height = nh;
    width = nh * SELECT_ASPECT;
  } else {
    width = nw;
    height = nw / SELECT_ASPECT;
  }
  return { x: (nw - width) / 2, y: (nh - height) / 2, w: width, h: height };
}

/**
 * 把框摆到界面上：源图坐标 → 显示坐标。
 *
 * @returns {void}
 *
 * 整个模块里只有这一处需要换算。`selection` 存的是源图坐标，所以窗口尺寸变化时
 * 只要重新调一次它就够了，框的数据本身不用动。
 */
function layoutSelection() {
  if (!selection || !stagedImage) { return; }

  var size = stageSize();
  var scaleX = size.width / stagedImage.naturalWidth;
  var scaleY = size.height / stagedImage.naturalHeight;
  var box = document.getElementById('cropBox');

  box.style.left = (selection.x * scaleX) + 'px';
  box.style.top = (selection.y * scaleY) + 'px';
  box.style.width = (selection.w * scaleX) + 'px';
  box.style.height = (selection.h * scaleY) + 'px';
}

/**
 * 数值夹取（比 Math.max/min 套用清晰一点）。
 *
 * @param {number} value 待夹的值
 * @param {number} low 下界
 * @param {number} high 上界
 * @returns {number}
 */
function clamp(value, low, high) {
  return Math.max(low, Math.min(high, value));
}

/* ---------- 裁切：交互 ---------- */

/** 打开系统文件选择器。绑在「选择图片」按钮上。 */
function pickImage() {
  document.getElementById('fImage').click();
}

/**
 * 用户选完文件：校验 → 读进 Image → 展开裁切面板。
 *
 * @param {Event} event 文件输入框的 change 事件。
 * @returns {void}
 *
 * 两道前置校验（类型、大小）放在这里，是为了**别让用户白等**：选了个 30MB 的
 * 文件再上传被拒，比当场被告知要糟得多。后端有同样的校验作为兜底。
 *
 * 读取失败（浏览器解不开的格式，比如 HEIC）走 onerror，给一句能照做的提示，
 * 而不是留一个空框。
 */
function onPickImage(event) {
  var file = event.target.files && event.target.files[0];
  if (!file) { return; }

  if (!/^image\/(jpeg|png|webp)$/.test(file.type)) {
    setImageError('仅支持 JPG / PNG / WebP 图片');
    return;
  }
  if (file.size > MAX_SOURCE_BYTES) {
    setImageError('图片不能超过 5MB');
    return;
  }

  var url = URL.createObjectURL(file);
  var image = new Image();

  image.onload = function () {
    revokeStagedUrl();
    stagedImage = image;
    stagedObjectUrl = url;
    selection = defaultSelection();          // 先给一个最大居中的 4:3 框

    var stageImg = document.getElementById('cropImage');
    // 框的显示位置要按图片**实际布局后**的尺寸算，所以等 img 自己 load 完再摆；
    // 紧接着设 src 就立刻量尺寸的话，可能量到高度 0（布局还没发生）
    stageImg.onload = layoutSelection;
    stageImg.src = url;

    document.getElementById('imagePicker').classList.add('hidden');
    document.getElementById('cropPanel').classList.remove('hidden');
    clearImageError();
  };

  image.onerror = function () {
    URL.revokeObjectURL(url);
    setImageError('这张图片读不出来，请换一张（HEIC 等格式浏览器打不开）');
  };

  image.src = url;
}

/**
 * 判断指针是否落在某个角柄上。
 *
 * @param {{x: number, y: number}} point 指针相对舞台左上角的**屏幕**坐标。
 * @param {{width: number, height: number}} size 舞台尺寸（屏幕像素）。
 * @returns {string|null} `'nw'` / `'ne'` / `'sw'` / `'se'`；都不在热区内时返回 `null`。
 *
 * 取**最近的**那个角：框小的时候四个热区会互相压住，按最近判定才符合直觉。
 * 距离用横竖两个方向里较大的那个（方形热区），比欧氏距离更贴合"手指按在角上"的感觉。
 */
function cornerAt(point, size) {
  if (!selection || !stagedImage) { return null; }

  var scaleX = size.width / stagedImage.naturalWidth;
  var scaleY = size.height / stagedImage.naturalHeight;
  var left = selection.x * scaleX;
  var top = selection.y * scaleY;
  var right = (selection.x + selection.w) * scaleX;
  var bottom = (selection.y + selection.h) * scaleY;

  var corners = [
    { id: 'nw', x: left, y: top },
    { id: 'ne', x: right, y: top },
    { id: 'sw', x: left, y: bottom },
    { id: 'se', x: right, y: bottom }
  ];

  var nearest = null;
  var nearestDistance = HANDLE_HIT_PX;
  corners.forEach(function (corner) {
    var distance = Math.max(Math.abs(point.x - corner.x), Math.abs(point.y - corner.y));
    if (distance <= nearestDistance) {
      nearestDistance = distance;
      nearest = corner.id;
    }
  });
  return nearest;
}

/**
 * 按下：判断这次手势是"拖角缩放 / 挪动框 / 重新框选"里的哪一种。
 *
 * @param {PointerEvent} event
 * @returns {void}
 *
 * 优先级是 **角柄 > 框内 > 框外**：
 * 角柄的热区压在框边上，必须最先判定，否则贴着角按下去会被当成"移动"；
 * 框内是移动；框外是重新框一块。
 *
 * 用 Pointer Events 而不是 mouse/touch 两套，一套代码同时覆盖鼠标与触摸；
 * `preventDefault` 配合舞台上的 `touch-none`，保证拖动时不滚页面。
 */
function startSelect(event) {
  if (!stagedImage) { return; }
  event.preventDefault();

  // 已经在拖了就别再起一次（多指同时按时只认第一个手指）
  if (dragPointerId !== null && event.pointerId !== dragPointerId) { return; }

  // **必须捕获这个指针**：捕获之后，即使鼠标/手指拖到图片外面，舞台仍然收得到
  // move 与 up。不捕获的话，在框外松手时 pointerup 落在别的元素上，舞台收不到，
  // dragMode 就永远清不掉——之后不用按键、只把指针移回图内就会继续拖动（真踩过）。
  if (event.currentTarget.setPointerCapture) {
    event.currentTarget.setPointerCapture(event.pointerId);
  }

  var box = document.getElementById('cropStage').getBoundingClientRect();
  var size = { width: box.width, height: box.height };
  var screen = { x: event.clientX - box.left, y: event.clientY - box.top };
  var point = {
    x: screen.x * (stagedImage.naturalWidth / box.width),
    y: screen.y * (stagedImage.naturalHeight / box.height)
  };

  var corner = cornerAt(screen, size);
  var inside = selection &&
    point.x >= selection.x && point.x <= selection.x + selection.w &&
    point.y >= selection.y && point.y <= selection.y + selection.h;

  if (corner) {
    dragMode = 'resize';
  } else if (inside) {
    dragMode = 'move';
  } else {
    dragMode = 'draw';
  }
  dragOrigin = { x: point.x, y: point.y, selection: selection, corner: corner };
  dragPointerId = event.pointerId;
}

/**
 * 拖角缩放：**对角固定**，被拖的那个角跟着指针走，比例锁 4:3。
 *
 * @param {{x: number, y: number}} point 指针的源图坐标。
 * @returns {void}
 *
 * 锚点（不动的那一角）取当前框的对角——拖右下角时左上角固定，反之亦然，
 * 这样缩放时框不会整体漂移。
 *
 * 宽度取指针到锚点两个方向位移里**较大的那个**，再夹到"锚点到图片边缘"能容下的
 * 最大值：所以往边上拖到底就停住，既不会把框推出图片，也不会因为某个方向空间小
 * 就缩成一条。
 */
function resizeSelection(point) {
  var nw = stagedImage.naturalWidth;
  var nh = stagedImage.naturalHeight;
  var before = dragOrigin.selection;
  var east = dragOrigin.corner.indexOf('e') !== -1;
  var south = dragOrigin.corner.indexOf('s') !== -1;

  var anchor = {
    x: east ? before.x : before.x + before.w,
    y: south ? before.y : before.y + before.h
  };

  var roomX = east ? nw - anchor.x : anchor.x;
  var roomY = south ? nh - anchor.y : anchor.y;
  var limit = Math.min(roomX, roomY * SELECT_ASPECT);

  var wanted = Math.max(Math.abs(point.x - anchor.x),
                        Math.abs(point.y - anchor.y) * SELECT_ASPECT);
  var width = clamp(wanted, Math.min(MIN_SELECT_WIDTH, limit), limit);
  var height = width / SELECT_ASPECT;

  selection = {
    x: east ? anchor.x : anchor.x - width,
    y: south ? anchor.y : anchor.y - height,
    w: width,
    h: height
  };
  layoutSelection();
}

/**
 * 拖动中：按当前手势更新框。绑在舞台的 pointermove 上。
 *
 * @param {PointerEvent} event
 * @returns {void}
 *
 * **缩放**（`'resize'`）：交给 `resizeSelection` —— 对角固定，比例锁 4:3。
 *
 * **挪动**（`'move'`）：按位移增量平移，再夹回图片范围内（框不会跑出去）。
 *
 * **框选**（`'draw'`）：以按下点为锚点，朝指针所在的一侧张出一个 **4:3** 的框。
 * 宽度取两个方向位移里**较大的那个**（横着拖按横向算，竖着拖按纵向算），
 * 这样斜着拖也顺手，不会因为某个方向拖得少就缩成一条。四个方向的可用空间不同，
 * 所以还要把宽度夹到"锚点到图片边缘"能容下的最大值。
 */
function moveSelect(event) {
  if (!dragMode || !stagedImage) { return; }

  // 只认当前手势的那个指针：多指同时按时，别的手指的移动不该动这个框
  if (event.pointerId !== undefined && event.pointerId !== dragPointerId) { return; }

  // 兜底：鼠标键已经松开了（比如拖到窗口外松手、up 事件丢了），直接把这次手势结束掉。
  // 上面虽然捕获了指针，但让"按着鼠标才能拖"这条不变量在任何情况下都成立更稳——
  // 这个判断正是为了掐掉"不用按键也能拖"的怪状态。
  // 只对鼠标判断：触摸时 buttons 恒为 1，用不到这条。
  if (event.pointerType === 'mouse' && event.buttons === 0) {
    endSelect();
    return;
  }

  var nw = stagedImage.naturalWidth;
  var nh = stagedImage.naturalHeight;
  var point = toSourcePoint(event);

  if (dragMode === 'resize') {
    resizeSelection(point);
    return;
  }

  if (dragMode === 'move') {
    var before = dragOrigin.selection;
    selection = {
      x: clamp(before.x + (point.x - dragOrigin.x), 0, nw - before.w),
      y: clamp(before.y + (point.y - dragOrigin.y), 0, nh - before.h),
      w: before.w,
      h: before.h
    };
    layoutSelection();
    return;
  }

  var signX = point.x >= dragOrigin.x ? 1 : -1;
  var signY = point.y >= dragOrigin.y ? 1 : -1;
  var roomX = signX > 0 ? nw - dragOrigin.x : dragOrigin.x;
  var roomY = signY > 0 ? nh - dragOrigin.y : dragOrigin.y;
  var limit = Math.min(roomX, roomY * SELECT_ASPECT);

  var wanted = Math.max(Math.abs(point.x - dragOrigin.x),
                        Math.abs(point.y - dragOrigin.y) * SELECT_ASPECT);
  var width = clamp(wanted, Math.min(MIN_SELECT_WIDTH, limit), limit);
  var height = width / SELECT_ASPECT;

  selection = {
    x: signX > 0 ? dragOrigin.x : dragOrigin.x - width,
    y: signY > 0 ? dragOrigin.y : dragOrigin.y - height,
    w: width,
    h: height
  };
  layoutSelection();
}

/**
 * 抬手：结束当前手势。绑在舞台的 pointerup / pointercancel 上。
 *
 * @returns {void}
 *
 * 如果"框选"只拖出针尖大的一块（点一下、或者手一抖），**撤回到按下之前那个框**，
 * 而不是留下一个几乎看不见的选区——那会让人以为图没了。
 */
function endSelect(event) {
  // 别的指针抬起来不该结束本手势（也只有本手势那个指针的 up 才算数）
  if (event && event.pointerId !== undefined && dragPointerId !== null &&
      event.pointerId !== dragPointerId) {
    return;
  }

  if (dragMode === 'draw' && selection && selection.w < MIN_SELECT_WIDTH) {
    selection = (dragOrigin && dragOrigin.selection) || defaultSelection();
    layoutSelection();
  }
  dragMode = null;
  dragOrigin = null;
  dragPointerId = null;
}

/**
 * 恢复成"最大的居中 4:3 框"。绑在「重新框选」按钮上。
 *
 * @returns {void}
 */
function resetSelection() {
  if (!stagedImage) { return; }
  selection = defaultSelection();
  layoutSelection();
}

/**
 * 把框选的那块画到 canvas 上，导出成 JPEG。
 *
 * @returns {Promise<Blob|null>} 没选图或还没框好时 resolve(null)。
 *
 * 这一步**没有任何坐标换算**：`selection` 本身就是源图像素下的矩形，
 * 直接交给 drawImage 即可。（这也正是把它存成源图坐标而不是屏幕坐标的原因。）
 *
 * 输出最长边压到 EXPORT_MAX_SIDE 以内、比例不变——因为框被锁成 4:3，
 * 导出的图正好 4:3，详情页用 object-cover 摆放不会再裁掉任何内容，
 * 所以"框里框到的"就是"详情页看到的"。
 */
function exportCroppedImage() {
  return new Promise(function (resolve) {
    if (!stagedImage || !selection) { resolve(null); return; }

    var sourceX = selection.x;
    var sourceY = selection.y;
    var sourceW = selection.w;
    var sourceH = selection.h;

    var shrink = Math.min(1, EXPORT_MAX_SIDE / Math.max(sourceW, sourceH));
    var outputW = Math.round(sourceW * shrink);
    var outputH = Math.round(sourceH * shrink);

    var canvas = document.createElement('canvas');
    canvas.width = outputW;
    canvas.height = outputH;
    canvas.getContext('2d').drawImage(
      stagedImage, sourceX, sourceY, sourceW, sourceH, 0, 0, outputW, outputH
    );
    canvas.toBlob(function (blob) { resolve(blob); }, 'image/jpeg', EXPORT_QUALITY);
  });
}

/* ---------- 裁切：状态与错误提示 ---------- */

/** 释放已占用 objectURL（不释放的话整张原图会一直留在内存里）。 */
function revokeStagedUrl() {
  if (stagedObjectUrl) {
    URL.revokeObjectURL(stagedObjectUrl);
    stagedObjectUrl = null;
  }
}

/**
 * 把图片相关的状态与界面恢复成"还没选图"的样子。
 * @returns {void}
 */
function resetImageState() {
  revokeStagedUrl();
  stagedImage = null;
  selection = null;
  dragMode = null;
  dragOrigin = null;
  document.getElementById('fImage').value = '';   // 清空才能再次选同一个文件
  document.getElementById('cropPanel').classList.add('hidden');
  document.getElementById('imagePicker').classList.remove('hidden');
}

/**
 * 移除已选的图片。绑在「移除图片」按钮上。
 * @returns {void}
 */
function removeImage() {
  resetImageState();
  clearImageError();
}

/**
 * 显示图片相关的错误：**先清掉已选的图**，再在按钮上标红并说明原因。
 *
 * @param {string} message 给用户看的中文原因。
 * @returns {void}
 *
 * 为什么要清掉旧图：留着旧图却显示"这张图片读不出来"，用户会以为自己选的图还在，
 * 结果发布用的是上一张——不如干脆退回"没选图"的干净状态。
 */
function setImageError(message) {
  resetImageState();
  var error = document.getElementById('eImage');
  error.textContent = message;
  error.classList.remove('hidden');
  var picker = document.getElementById('imagePicker');
  picker.classList.add('border-rose-400');
  picker.classList.remove('border-slate-200');
}

/** 清掉图片相关的错误提示。 */
function clearImageError() {
  document.getElementById('eImage').classList.add('hidden');
  var picker = document.getElementById('imagePicker');
  picker.classList.remove('border-rose-400');
  picker.classList.add('border-slate-200');
}

/* 校验 + 提交。6 条错误文案与滚动到首个错误字段的行为属于需求，必须逐字保留；
   校验通过后交给 POST /api/items，发布时间与其它补全字段都由服务端负责 */
function submitForm() {
  var fields = [
    { id: 'fName', err: 'eName' },
    { id: 'fCategory', err: 'eCategory' },
    { id: 'fTime', err: 'eTime' },
    { id: 'fPlace', err: 'ePlace' },
    { id: 'fDesc', err: 'eDesc' },
    { id: 'fContact', err: 'eContact' }
  ];
  var ok = true;
  var firstBad = null;

  fields.forEach(function (f) {
    var input = document.getElementById(f.id);
    var err = document.getElementById(f.err);
    var valid = (input.value || '').trim() !== '';
    if (input.type !== 'hidden') {
      input.classList.toggle('border-rose-400', !valid);
      input.classList.toggle('border-slate-200', valid);
    }
    err.classList.toggle('hidden', valid);
    if (!valid && !firstBad) { firstBad = err; }
    if (!valid) { ok = false; }
  });

  if (!ok) {
    showToast('请完善标红的必填项', 2000);
    if (firstBad) { firstBad.scrollIntoView({ behavior: 'smooth', block: 'center' }); }
    return;
  }

  // 只发服务端要的 7 个字段：状态、图标、发布者、脱敏串、搜索索引、发布时间
  // 全由后端补全，前端不要自己造（见 docs/system-design.md 第 5.4 节）
  var payload = {
    name: document.getElementById('fName').value.trim(),
    type: currentType,
    category: document.getElementById('fCategory').value,
    time: document.getElementById('fTime').value.replace('T', ' '),
    place: document.getElementById('fPlace').value.trim(),
    desc: document.getElementById('fDesc').value.trim(),
    contact: document.getElementById('fContact').value.trim()
  };

  if (submitting) { return; }
  submitting = true;

  // 两步：先传图（选了才传），再发布。stage 用来在失败时给对提示——
  // "图片上传失败"和"发布失败"对用户的下一步动作是不一样的
  var stage = 'upload';
  var uploading = stagedImage
    ? exportCroppedImage().then(function (blob) {
        if (!blob) { throw new Error('图片导出失败'); }
        return API.upload(blob);
      })
    : Promise.resolve(null);

  uploading
    .then(function (uploaded) {
      if (uploaded) { payload.image = uploaded.filename; }
      stage = 'create';
      return API.create(payload);
    })
    .then(function (created) {
      // 带真实 id 跳转；详情页已经没有 ?id=new 这个特殊值了
      window.location.href = 'success.html?id=' + encodeURIComponent(created.id);
    })
    .catch(function (error) {
      console.error(error);
      submitting = false;                 // 失败后允许重试
      showToast(stage === 'upload' ? '图片上传失败，请重试' : '发布失败，请稍后重试', 2000);
    });
}

window.addEventListener('DOMContentLoaded', function () {
  setType('seek');
  // 窗口尺寸变化时框的显示位置要重算。因为 selection 存的是**源图坐标**，
  // 这里只要重新摆一次就够了，框本身的数据不用动——这正是当初不存屏幕坐标的原因
  window.addEventListener('resize', layoutSelection);
});
