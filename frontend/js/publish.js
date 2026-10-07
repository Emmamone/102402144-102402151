/* 发布信息页。
 *
 * 阶段 0 的机械拆分：内容逐字取自本页原先的内联 <script>，**未改变任何行为**。
 * showToast / toastTimer 已移入 common.js；本页原本的提示时长是 2000ms（其余页
 * 是 1800ms），为不改变行为，调用处显式传入 2000。
 *
 * 校验逻辑与全部错误文案**逐字保留**（这些属于需求，不得"顺手优化"）。
 * 本页仍把数据写入 localStorage 的 campusNewItem —— 留待阶段 4 改造为接口调用。
 */

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

/**
 * 把 Date 格式化成 'YYYY-MM-DD HH:mm'。
 *
 * @param {Date} d 时间对象
 * @returns {string} 补零后的本地时间字符串
 *
 * 用于生成"发布时间"。阶段 4 起发布时间由服务端写入，本函数删除；
 * 注意不要用它格式化用户选的时间——那个值直接取自 datetime-local 控件。
 */
function formatDateTime(d) {
  var p = function (n) { return (n < 10 ? '0' : '') + n; };
  return d.getFullYear() + '-' + p(d.getMonth() + 1) + '-' + p(d.getDate()) + ' ' + p(d.getHours()) + ':' + p(d.getMinutes());
}

/* 校验 + 提交。6 条错误文案与滚动到首个错误字段的行为属于需求，必须逐字保留；
   提交成功分支当前写 localStorage（阶段 4 起改为 POST /api/items） */
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

  var item = {
    name: document.getElementById('fName').value.trim(),
    type: currentType,
    category: document.getElementById('fCategory').value,
    time: document.getElementById('fTime').value.replace('T', ' '),
    place: document.getElementById('fPlace').value.trim(),
    desc: document.getElementById('fDesc').value.trim(),
    contact: document.getElementById('fContact').value.trim(),
    publish: formatDateTime(new Date())
  };

  try {
    localStorage.setItem('campusNewItem', JSON.stringify(item));
  } catch (err) {
    showToast('本地存储不可用，仍将进入发布成功页', 2000);
  }
  window.location.href = 'success.html';
}

window.addEventListener('DOMContentLoaded', function () {
  setType('seek');
});
