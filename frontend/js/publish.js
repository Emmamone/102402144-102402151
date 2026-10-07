/* 发布信息页。
 *
 * 提交走 **POST /api/items**（阶段 4 改造完成）：成功后带着服务端返回的新 id
 * 跳到 `success.html?id=<新id>`，成功页据此查详情。
 *
 * 随改造删除的旧机制：把刚发布的那条写进 localStorage 的 `campusNewItem`
 * （发布页与成功页之间的临时传递），以及前端算的 `formatDateTime`
 * ——发布时间由服务端生成，不用客户端时钟。
 *
 * showToast / toastTimer 在 common.js；本页的提示时长是 2000ms（其余页 1800ms），
 * 为不改变行为，调用处显式传入 2000。
 *
 * 校验逻辑与全部错误文案**逐字保留**（这些属于需求，不得"顺手优化"）。
 */

//: 提交中标志：防止连点。一次点击发两条请求会插进两条记录，且没有幂等保护。
var submitting = false;

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

  API.create(payload)
    .then(function (created) {
      // 带真实 id 跳转；详情页已经没有 ?id=new 这个特殊值了
      window.location.href = 'success.html?id=' + encodeURIComponent(created.id);
    })
    .catch(function (error) {
      console.error(error);
      submitting = false;                 // 失败后允许重试
      showToast('发布失败，请稍后重试', 2000);
    });
}

window.addEventListener('DOMContentLoaded', function () {
  setType('seek');
});
