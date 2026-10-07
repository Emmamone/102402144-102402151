/* 信息详情页。
 *
 * 阶段 0 的机械拆分：内容逐字取自本页原先的内联 <script>，**未改变任何行为**。
 * 移入 common.js 的部分：maskContact、showToast、toastTimer、STATUS_TEXT
 * （实现逐字相同；注意 STATUS_STYLE 是详情页专属的 rounded-full 变体，与列表卡片
 * 的不同，因此保留在本页）。
 *
 * 本页仍使用内嵌数据、localStorage 与 ?id=new 特殊值 —— 留待阶段 3 / 4 改造。
 */

/* 内嵌演示数据（阶段 0 原样保留；阶段 3 起改为 GET /api/items/{id} 返回）。
   注意各条目的 masked 与 contact 不同源——masked 是写死的展示值，不能由 contact 推导 */
var ITEMS = {
  '1': {
    name: '校园卡', type: 'seek', status: 'seeking', icon: 'mdi:card-account-details-outline',
    category: '证件卡片', timeLabel: '丢失时间', time: '2026-09-27 08:20',
    place: '图书馆二楼自习区', publish: '2026-09-27 08:26',
    desc: '蓝色卡套，卡面右下角贴有姓名贴，昨天下午在图书馆二楼自习时还用过，离开时遗忘在桌面上。卡内余额不多，主要是补办很麻烦，拾到的同学麻烦联系我，非常感谢。',
    publisher: '张同学 · 计算机学院', masked: '138****6621', contact: '微信：zhang_cc2024', avatar: '张'
  },
  '2': {
    name: '黑色雨伞', type: 'find', status: 'unclaimed', icon: 'mdi:umbrella-outline',
    category: '雨伞', timeLabel: '拾取时间', time: '2026-09-27 09:40',
    place: '教学楼A座 201', publish: '2026-09-27 09:52',
    desc: '伞骨完好，伞面带卡通小熊图案，伞柄处有一道浅划痕。下课后在教室最后一排座位下捡到，暂时放在教学楼A座一楼值班室，可凭描述认领。',
    publisher: '李同学 · 外国语学院', masked: '159****3382', contact: '手机号：15900003382', avatar: '李'
  },
  '3': {
    name: '白色保温杯', type: 'find', status: 'unclaimed', icon: 'mdi:cup-outline',
    category: '水杯', timeLabel: '拾取时间', time: '2026-09-26 18:05',
    place: '第二食堂一楼', publish: '2026-09-26 18:20',
    desc: '杯身贴着「考研加油」贴纸，容量 500ml，杯盖内侧有一圈浅蓝色密封圈。吃完饭后落在了靠窗的餐桌上，现放在第二食堂一楼服务台。',
    publisher: '王同学 · 数学学院', masked: '136****7754', contact: 'QQ：136000077',
    avatar: '王'
  },
  '4': {
    name: '无线耳机', type: 'seek', status: 'resolved', icon: 'mdi:headphones',
    category: '电子产品', timeLabel: '丢失时间', time: '2026-09-26 15:30',
    place: '宿舍区 3 号楼', publish: '2026-09-26 15:48',
    desc: '白色充电盒，右耳外壳有细小划痕。晚上在宿舍区 3 号楼架空层附近锻炼，回来发现耳机不见了。已在室友帮助下找回，信息保留供参考。',
    publisher: '陈同学 · 土木工程学院', masked: '188****1209', contact: '手机号：18800001209', avatar: '陈'
  },
  '5': {
    name: '宿舍钥匙', type: 'seek', status: 'seeking', icon: 'mdi:key-variant',
    category: '钥匙', timeLabel: '丢失时间', time: '2026-09-25 12:10',
    place: '体育馆篮球场', publish: '2026-09-25 12:35',
    desc: '两把钥匙配一只蓝色钥匙扣，上面挂着校徽挂件。上午在体育馆篮球场打球，可能落在场边长椅上，钥匙扣有明显磨损。',
    publisher: '刘同学 · 体育学院', masked: '137****4415', contact: '微信：liu_qiuzhi', avatar: '刘'
  },
  '6': {
    name: '帆布笔袋', type: 'find', status: 'unclaimed', icon: 'mdi:bag-personal-outline',
    category: '书籍文具', timeLabel: '拾取时间', time: '2026-09-24 20:15',
    place: '图书馆四楼阅览室', publish: '2026-09-24 20:31',
    desc: '灰色帆布笔袋，里面有一支黑色中性笔和一把钢尺，笔袋拉链头挂着小挂饰。已交到图书馆一楼前台，说明颜色和内部物品即可领取。',
    publisher: '赵同学 · 经济管理学院', masked: '135****8876', contact: '手机号：13500008876', avatar: '赵'
  },
  '7': {
    name: '校园卡', type: 'find', status: 'unclaimed', icon: 'mdi:card-account-details-outline',
    category: '证件卡片', timeLabel: '拾取时间', time: '2026-09-27 10:15',
    place: '第三教学楼 B202', publish: '2026-09-27 10:22',
    desc: '课间在教室抽屉里捡到一张校园卡，卡面姓名有磨损，能看到姓氏为「李」。已交到图书馆一楼前台，请本人携带学生证前往认领。',
    publisher: '李同学 · 外国语学院', masked: '159****3382', contact: '电话：15900003382', avatar: '李'
  },
  '8': {
    name: '学生证', type: 'find', status: 'unclaimed', icon: 'mdi:badge-account-horizontal-outline',
    category: '证件卡片', timeLabel: '拾取时间', time: '2026-09-23 16:40',
    place: '大学生活动中心', publish: '2026-09-23 16:55',
    desc: '外套透明保护套，内页姓名首字为「李」。社团招新结束后在活动中心门口台阶上捡到，目前由活动中心值班室保管。',
    publisher: '赵同学 · 经济管理学院', masked: '135****8876', contact: '手机号：13500008876', avatar: '赵'
  }
};

var STATUS_STYLE = {
  seeking: 'shrink-0 px-2 py-0.5 rounded-full text-[10px] font-medium bg-orange-50 text-orange-600',
  unclaimed: 'shrink-0 px-2 py-0.5 rounded-full text-[10px] font-medium bg-amber-50 text-amber-600',
  resolved: 'shrink-0 px-2 py-0.5 rounded-full text-[10px] font-medium bg-emerald-50 text-emerald-600'
};

var currentId = '1';
var currentItem = null;

function getResolvedIds() {
  try {
    return JSON.parse(localStorage.getItem('campusResolved') || '[]');
  } catch (err) {
    return [];
  }
}

function saveResolvedIds(list) {
  try {
    localStorage.setItem('campusResolved', JSON.stringify(list));
  } catch (err) { /* 本地存储不可用时忽略 */ }
}

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

  document.getElementById('dCode').textContent = (currentId === 'new') ? 'LF-NEW' : ('LF-00' + currentId);

  document.getElementById('dContactRevealed').classList.add('hidden');
  document.getElementById('dContactBtnWrap').classList.remove('hidden');

  var resolved = (getResolvedIds().indexOf(currentId) !== -1) || (it.status === 'resolved');
  applyStatus(resolved ? 'resolved' : it.status);
}

function loadItem() {
  var params = new URLSearchParams(window.location.search);
  var id = params.get('id') || '1';
  var item = null;

  if (id === 'new') {
    var saved = null;
    try {
      saved = JSON.parse(localStorage.getItem('campusNewItem') || 'null');
    } catch (err) {
      saved = null;
    }
    if (saved) {
      currentId = 'new';
      item = buildNewItem(saved);
    } else {
      id = '1';
    }
  }

  if (!item) {
    currentId = id;
    item = ITEMS[id] || ITEMS['1'];
  }

  currentItem = item;
  render(item);
}

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
