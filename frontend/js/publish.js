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

function setCat(btn) {
  document.querySelectorAll('#catWrap button').forEach(function (b) {
    var on = (b === btn);
    CHIP_ON.forEach(function (c) { b.classList.toggle(c, on); });
    CHIP_OFF.forEach(function (c) { b.classList.toggle(c, !on); });
  });
  document.getElementById('fCategory').value = btn.textContent.trim();
  clearError('fCategory', 'eCategory');
}

function clearError(inputId, errId) {
  var input = document.getElementById(inputId);
  if (input && input.type !== 'hidden') {
    input.classList.remove('border-rose-400');
    input.classList.add('border-slate-200');
  }
  document.getElementById(errId).classList.add('hidden');
}

function formatDateTime(d) {
  var p = function (n) { return (n < 10 ? '0' : '') + n; };
  return d.getFullYear() + '-' + p(d.getMonth() + 1) + '-' + p(d.getDate()) + ' ' + p(d.getHours()) + ':' + p(d.getMinutes());
}

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
