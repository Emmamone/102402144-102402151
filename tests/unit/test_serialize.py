"""serialize 层纯函数的单元测试。

不依赖数据库、网络、文件系统，也不依赖当前时间——凡涉及时间的断言都把
``now`` 显式传进去，因此结果可重复。
"""

from __future__ import annotations

from datetime import datetime

import pytest

from backend import serialize


# --------------------------------------------------------------------------
# 联系方式脱敏
# --------------------------------------------------------------------------
@pytest.mark.parametrize(
    "raw, expected",
    [
        ("13800001234", "138****1234"),          # 11 位手机号：前三后四
        ("微信：zhang_cc2024", "微信****24"),      # 长度 > 4：前二后二
        ("abcd", "abcd"),                        # 恰好 4 位：原样返回
        ("abc", "abc"),                          # 短于 4 位：原样返回
        ("  ", "—"),                             # 空白：占位符
        ("", "—"),
        (None, "—"),
    ],
)
def test_mask_contact(raw, expected):
    assert serialize.mask_contact(raw) == expected


def test_mask_contact_只把_1_开头的_11_位当手机号():
    # 12 位以 1 开头但不是 11 位手机号 → 走"长度 > 4"的分支
    assert serialize.mask_contact("138000012345") == "13****45"


# --------------------------------------------------------------------------
# 编号与时间标签
# --------------------------------------------------------------------------
@pytest.mark.parametrize(
    "item_id, expected",
    [(1, "LF-001"), (8, "LF-008"), (9, "LF-009"), (10, "LF-010"), (123, "LF-123")],
)
def test_item_code(item_id, expected):
    assert serialize.item_code(item_id) == expected


def test_time_label_按类型给出时间行标题():
    assert serialize.time_label("seek") == "丢失时间"
    assert serialize.time_label("find") == "拾取时间"


# --------------------------------------------------------------------------
# 卡片时间文案
# --------------------------------------------------------------------------
NOW = datetime(2026, 10, 7, 14, 30)


def test_卡片时间_time_display_非空时原样返回():
    """演示数据的相对时间文案是固定文案，不得按真实日期重算。"""
    assert serialize.format_card_time("今天 08:20", "2026-09-27 08:20", NOW) == "今天 08:20"
    assert serialize.format_card_time("09-25 12:10", "2026-09-25 12:10", NOW) == "09-25 12:10"


def test_卡片时间_当天推导为今天():
    assert serialize.format_card_time(None, "2026-10-07 08:20", NOW) == "今天 08:20"


def test_卡片时间_前一天推导为昨天():
    assert serialize.format_card_time(None, "2026-10-06 18:05", NOW) == "昨天 18:05"


def test_卡片时间_更早的日期用月日():
    assert serialize.format_card_time(None, "2026-09-25 12:10", NOW) == "09-25 12:10"


def test_卡片时间_跨天判断按日期而非小时():
    # 同一日期但时间更晚（未来时刻的当天）仍算"今天"
    assert serialize.format_card_time(None, "2026-10-07 23:59", NOW) == "今天 23:59"


def test_卡片时间_格式不合法时原样返回():
    assert serialize.format_card_time(None, "刚刚", NOW) == "刚刚"
    assert serialize.format_card_time(None, None, NOW) == "—"


# --------------------------------------------------------------------------
# 搜索索引拼装
# --------------------------------------------------------------------------
def test_build_keywords_寻物带丢了():
    text = serialize.build_keywords("校园卡", "证件卡片", "图书馆", "蓝色卡套", "seek")
    assert text == "校园卡 证件卡片 图书馆 蓝色卡套 寻物 丢了"


def test_build_keywords_招领带捡到():
    text = serialize.build_keywords("雨伞", "雨伞", "教学楼", "小熊图案", "find")
    assert text.endswith("招领 捡到")


def test_build_keywords_跳过空片段():
    text = serialize.build_keywords("钥匙", "", "", "", "seek")
    assert "  " not in text
    assert text == "钥匙 寻物 丢了"


# --------------------------------------------------------------------------
# 行 → 响应对象（保真规则）
# --------------------------------------------------------------------------
ROW = {
    "id": 1,
    "name": "校园卡",
    "type": "seek",
    "status": "seeking",
    "category": "证件卡片",
    "icon": "mdi:card-account-details-outline",
    "card_desc": "卡片上的短描述。",
    "desc": "详情页的完整描述，比卡片描述长得多。",
    "happened_at": "2026-09-27 08:20",
    "time_display": "今天 08:20",
    "place": "图书馆二楼自习区",
    "published_at": "2026-09-27 08:26",
    "publisher": "张同学 · 计算机学院",
    "avatar": "张",
    "masked": "138****6621",
    "contact": "微信：zhang_cc2024",
    "keywords": "校园卡 证件卡片 蓝色卡套 图书馆 自习区 寻物 丢了",
    "image": None,
}


def test_列表项的_desc_取卡片短描述而不是详情长描述():
    item = serialize.row_to_list_item(ROW, NOW)
    assert item["desc"] == ROW["card_desc"]
    assert item["desc"] != ROW["desc"]


def test_列表项不含详情字段():
    item = serialize.row_to_list_item(ROW, NOW)
    expected = {"id", "name", "type", "status", "icon", "desc", "time", "place", "keywords"}
    assert set(item) == expected


def test_详情项的_masked_与_contact_各自原样返回():
    item = serialize.row_to_detail_item(ROW)
    # 这两列不同源：masked 无法由 contact 算出，必须各自保真
    assert item["masked"] == "138****6621"
    assert item["contact"] == "微信：zhang_cc2024"
    assert item["masked"] != serialize.mask_contact(ROW["contact"])


def test_详情项的时间用绝对时间而非卡片文案():
    item = serialize.row_to_detail_item(ROW)
    assert item["time"] == "2026-09-27 08:20"
    assert item["timeLabel"] == "丢失时间"
    assert item["code"] == "LF-001"
    assert item["publish"] == "2026-09-27 08:26"
