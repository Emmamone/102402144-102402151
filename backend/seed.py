"""演示数据的幂等播种。

数据来源（逐字转抄，不重写）：

- ``card_desc``：首页与搜索页卡片上的两行描述（两页逐字相同）
- ``desc``、``publisher``、``masked``、``contact``、``avatar``、``icon``、
  ``status``、``happened_at``、``published_at``：详情页内嵌数据的对应字段
- ``keywords``：搜索页卡片的 ``data-keywords`` 属性
- ``time_display``：卡片上的相对时间文案（``今天 08:20`` 等）

三条**不可推导**的字面量，务必不要"顺手推导"（见 docs/system-design.md 第 4.2 节）：

1. ``masked`` 与 ``contact`` 不同源——例如 1 号的 ``contact`` 是微信号，
   而 ``masked`` 是手机号形态的 ``138****6621``，无法由 contact 算出。
2. ``card_desc`` 与 ``desc`` 是两段不同的文字，不是前缀关系。
3. ``time_display`` 的"今天/昨天"冻结在演示数据设定的 2026-09-27，
   按真实日期推导会立刻变成 ``09-27``。

幂等性：以固定 id 1~8 执行 upsert，重复执行只覆盖这 8 条，
不会产生重复；``ON CONFLICT`` 的 SET 列表不含 ``created_at``。
"""

from __future__ import annotations

from pathlib import Path

from . import db

# fmt: off
RECORDS = [
    {
        "id": 1,
        "name": "校园卡",
        "type": "seek",
        "status": "seeking",
        "category": "证件卡片",
        "icon": "mdi:card-account-details-outline",
        "card_desc": "蓝色卡套，卡面右下角贴有姓名贴，昨天下午在图书馆自习时遗落在桌面。",
        "desc": "蓝色卡套，卡面右下角贴有姓名贴，昨天下午在图书馆二楼自习时还用过，离开时遗忘在桌面上。卡内余额不多，主要是补办很麻烦，拾到的同学麻烦联系我，非常感谢。",
        "happened_at": "2026-09-27 08:20",
        "time_display": "今天 08:20",
        "place": "图书馆二楼自习区",
        "published_at": "2026-09-27 08:26",
        "publisher": "张同学 · 计算机学院",
        "avatar": "张",
        "masked": "138****6621",
        "contact": "微信：zhang_cc2024",
        "keywords": "校园卡 证件卡片 蓝色卡套 图书馆 自习区 寻物 丢了",
        "home_order": 1,
        "search_order": 1,
    },
    {
        "id": 2,
        "name": "黑色雨伞",
        "type": "find",
        "status": "unclaimed",
        "category": "雨伞",
        "icon": "mdi:umbrella-outline",
        "card_desc": "伞骨完好，伞面带卡通小熊图案，下课后在教室最后一排捡到。",
        "desc": "伞骨完好，伞面带卡通小熊图案，伞柄处有一道浅划痕。下课后在教室最后一排座位下捡到，暂时放在教学楼A座一楼值班室，可凭描述认领。",
        "happened_at": "2026-09-27 09:40",
        "time_display": "今天 09:40",
        "place": "教学楼A座 201",
        "published_at": "2026-09-27 09:52",
        "publisher": "李同学 · 外国语学院",
        "avatar": "李",
        "masked": "159****3382",
        "contact": "手机号：15900003382",
        "keywords": "雨伞 黑色 小熊 教学楼 教室 招领 捡到",
        "home_order": 2,
        "search_order": 5,
    },
    {
        "id": 3,
        "name": "白色保温杯",
        "type": "find",
        "status": "unclaimed",
        "category": "水杯",
        "icon": "mdi:cup-outline",
        "card_desc": "杯身贴着「考研加油」贴纸，容量 500ml，吃完饭后落在了餐桌上。",
        "desc": "杯身贴着「考研加油」贴纸，容量 500ml，杯盖内侧有一圈浅蓝色密封圈。吃完饭后落在了靠窗的餐桌上，现放在第二食堂一楼服务台。",
        "happened_at": "2026-09-26 18:05",
        "time_display": "昨天 18:05",
        "place": "第二食堂一楼",
        "published_at": "2026-09-26 18:20",
        "publisher": "王同学 · 数学学院",
        "avatar": "王",
        "masked": "136****7754",
        "contact": "QQ：136000077",
        "keywords": "水杯 保温杯 白色 食堂 考研加油 招领 捡到",
        "home_order": 3,
        "search_order": 4,
    },
    {
        "id": 4,
        "name": "无线耳机",
        "type": "seek",
        "status": "resolved",
        "category": "电子产品",
        "icon": "mdi:headphones",
        "card_desc": "白色充电盒，右耳外壳有细小划痕，晚上锻炼回来发现不见了，已找回。",
        "desc": "白色充电盒，右耳外壳有细小划痕。晚上在宿舍区 3 号楼架空层附近锻炼，回来发现耳机不见了。已在室友帮助下找回，信息保留供参考。",
        "happened_at": "2026-09-26 15:30",
        "time_display": "昨天 15:30",
        "place": "宿舍区 3 号楼",
        "published_at": "2026-09-26 15:48",
        "publisher": "陈同学 · 土木工程学院",
        "avatar": "陈",
        "masked": "188****1209",
        "contact": "手机号：18800001209",
        "keywords": "耳机 无线耳机 白色 宿舍区 3号楼 寻物 丢了",
        "home_order": 4,
        "search_order": 6,
    },
    {
        "id": 5,
        "name": "宿舍钥匙",
        "type": "seek",
        "status": "seeking",
        "category": "钥匙",
        "icon": "mdi:key-variant",
        "card_desc": "两把钥匙配一只蓝色钥匙扣，上面挂着校徽挂件，打完球后发现钥匙不见了。",
        "desc": "两把钥匙配一只蓝色钥匙扣，上面挂着校徽挂件。上午在体育馆篮球场打球，可能落在场边长椅上，钥匙扣有明显磨损。",
        "happened_at": "2026-09-25 12:10",
        "time_display": "09-25 12:10",
        "place": "体育馆篮球场",
        "published_at": "2026-09-25 12:35",
        "publisher": "刘同学 · 体育学院",
        "avatar": "刘",
        "masked": "137****4415",
        "contact": "微信：liu_qiuzhi",
        "keywords": "钥匙 宿舍钥匙 蓝色钥匙扣 校徽 体育馆 篮球场 寻物 丢了",
        "home_order": 5,
        "search_order": 3,
    },
    {
        "id": 6,
        "name": "帆布笔袋",
        "type": "find",
        "status": "unclaimed",
        "category": "书籍文具",
        "icon": "mdi:bag-personal-outline",
        "card_desc": "灰色帆布笔袋，里面有一支黑色中性笔和一把钢尺，已交到图书馆前台。",
        "desc": "灰色帆布笔袋，里面有一支黑色中性笔和一把钢尺，笔袋拉链头挂着小挂饰。已交到图书馆一楼前台，说明颜色和内部物品即可领取。",
        "happened_at": "2026-09-24 20:15",
        "time_display": "09-24 20:15",
        "place": "图书馆四楼阅览室",
        "published_at": "2026-09-24 20:31",
        "publisher": "赵同学 · 经济管理学院",
        "avatar": "赵",
        "masked": "135****8876",
        "contact": "手机号：13500008876",
        "keywords": "笔袋 帆布 文具 图书馆 阅览室 招领 捡到",
        "home_order": 6,
        "search_order": 7,
    },
    {
        # 7、8 号只出现在搜索页与详情页，不在首页「最新信息」里：
        # home_order 为 NULL，首页查询按 source='demo' AND home_order IS NOT NULL 排除它们。
        "id": 7,
        "name": "校园卡",
        "type": "find",
        "status": "unclaimed",
        "category": "证件卡片",
        "icon": "mdi:card-account-details-outline",
        "card_desc": "课间在教室抽屉里捡到一张校园卡，卡面姓名有磨损，请本人持学生证到图书馆前台认领。",
        "desc": "课间在教室抽屉里捡到一张校园卡，卡面姓名有磨损，能看到姓氏为「李」。已交到图书馆一楼前台，请本人携带学生证前往认领。",
        "happened_at": "2026-09-27 10:15",
        "time_display": "今天 10:15",
        "place": "第三教学楼 B202",
        "published_at": "2026-09-27 10:22",
        "publisher": "李同学 · 外国语学院",
        "avatar": "李",
        "masked": "159****3382",
        "contact": "电话：15900003382",
        "keywords": "校园卡 证件卡片 第三教学楼 教室 抽屉 招领 捡到",
        "home_order": None,
        "search_order": 2,
    },
    {
        "id": 8,
        "name": "学生证",
        "type": "find",
        "status": "unclaimed",
        "category": "证件卡片",
        "icon": "mdi:badge-account-horizontal-outline",
        "card_desc": "外套透明保护套，内页姓名首字为「李」，社团招新结束后在门口台阶上捡到。",
        "desc": "外套透明保护套，内页姓名首字为「李」。社团招新结束后在活动中心门口台阶上捡到，目前由活动中心值班室保管。",
        "happened_at": "2026-09-23 16:40",
        "time_display": "09-23 16:40",
        "place": "大学生活动中心",
        "published_at": "2026-09-23 16:55",
        "publisher": "赵同学 · 经济管理学院",
        "avatar": "赵",
        "masked": "135****8876",
        "contact": "手机号：13500008876",
        "keywords": "学生证 证件卡片 大学生活动中心 招领 捡到",
        "home_order": None,
        "search_order": 8,
    },
]
# fmt: on

COLUMNS = (
    "id",
    "name",
    "type",
    "status",
    "category",
    "icon",
    "card_desc",
    "desc",
    "happened_at",
    "time_display",
    "place",
    "published_at",
    "publisher",
    "avatar",
    "masked",
    "contact",
    "keywords",
    "home_order",
    "search_order",
)

# 冲突时更新哪些列；刻意不含 created_at，保留首次写入时间
UPDATE_COLUMNS = tuple(c for c in COLUMNS if c != "id")

_UPSERT = (
    "INSERT INTO items (source, {cols}) VALUES ('demo', {marks}) "
    "ON CONFLICT(id) DO UPDATE SET {sets}"
).format(
    cols=", ".join(COLUMNS),
    marks=", ".join("?" for _ in COLUMNS),
    sets=", ".join("%s = excluded.%s" % (c, c) for c in UPDATE_COLUMNS),
)


def seed_demo_data(path: str | Path | None = None) -> int:
    """建表并写入 8 条演示数据；返回写入的记录数。

    可重复执行：以固定 id upsert，不会产生重复，也不会覆盖 id ≥ 9 的用户数据。
    """
    db.init_db(path)
    conn = db.connect(path)
    try:
        with conn:  # 单事务
            for record in RECORDS:
                conn.execute(_UPSERT, tuple(record[c] for c in COLUMNS))
        return len(RECORDS)
    finally:
        conn.close()


if __name__ == "__main__":  # pragma: no cover - 手工执行入口
    count = seed_demo_data()
    print("已写入 %d 条演示数据 -> %s" % (count, db.resolve_db_path()))
