"""行 → 响应对象的转换。

本模块内的函数**全部是纯函数**：不访问数据库、不在内部读时钟。
凡与「当前时间」有关的函数都把 ``now`` 作为参数传入，这样单元测试可以
固定时间、结果可重复（见 docs/coding-standards.md 第 4.2 节）。
"""

from __future__ import annotations

import re
from datetime import datetime
from typing import Any, Mapping

MOBILE_RE = re.compile(r"^1\d{10}$")

TYPE_TEXT = {"seek": "寻物", "find": "招领"}
STATUS_TEXT = {"seeking": "寻找中", "unclaimed": "待认领", "resolved": "已解决"}
TIME_LABEL = {"seek": "丢失时间", "find": "拾取时间"}

# publish 时按类型补全的默认图标（与原前端 buildNewItem 的取值一致）
DEFAULT_ICON = {"seek": "mdi:help-circle-outline", "find": "mdi:hand-heart-outline"}
# 新发布数据的初始状态
DEFAULT_STATUS = {"seek": "seeking", "find": "unclaimed"}


def mask_contact(value: Any) -> str:
    """联系方式脱敏（与前端既有的 maskContact 规则一致）。"""
    text = ("" if value is None else str(value)).strip()
    if not text:
        return "—"
    if MOBILE_RE.match(text):
        return text[:3] + "****" + text[7:]
    if len(text) > 4:
        return text[:2] + "****" + text[-2:]
    return text


def item_code(item_id: Any) -> str:
    """物品编号：LF-001、LF-009 …"""
    return "LF-%03d" % int(item_id)


def time_label(item_type: str) -> str:
    return TIME_LABEL.get(item_type, TIME_LABEL["seek"])


def parse_happened_at(value: Any) -> datetime | None:
    """解析 'YYYY-MM-DD HH:mm'；格式不符时返回 None。"""
    if not isinstance(value, str):
        return None
    try:
        return datetime.strptime(value, "%Y-%m-%d %H:%M")
    except ValueError:
        return None


def format_card_time(
    time_display: Any, happened_at: Any, now: datetime
) -> str:
    """列表卡片上的时间文案。

    演示数据的 ``time_display`` 是**固定的展示文案**（如 ``今天 08:20``），
    必须原样返回——它的"今天"冻结在演示数据设定的日期上，不能按真实日期重算，
    否则页面展示会随日期漂移。只有 ``time_display`` 为空（用户新发布的数据）
    时才由 ``happened_at`` 相对 ``now`` 推导。
    """
    if time_display:
        return str(time_display)
    happened = parse_happened_at(happened_at)
    if happened is None:
        return str(happened_at) if happened_at else "—"
    days = (now.date() - happened.date()).days
    if days == 0:
        return "今天 " + happened.strftime("%H:%M")
    if days == 1:
        return "昨天 " + happened.strftime("%H:%M")
    return happened.strftime("%m-%d %H:%M")


def build_keywords(
    name: str, category: str, place: str, desc: str, item_type: str
) -> str:
    """拼装搜索索引文本（用户新发布的数据用）。"""
    tail = "寻物 丢了" if item_type == "seek" else "招领 捡到"
    parts = [name, category, place, desc, tail]
    return " ".join(part for part in parts if part)


def row_to_list_item(row: Mapping[str, Any], now: datetime) -> dict:
    """行 → 列表项（首页与搜索页共用）。"""
    return {
        "id": row["id"],
        "name": row["name"],
        "type": row["type"],
        "status": row["status"],
        "icon": row["icon"],
        "desc": row["card_desc"],
        "time": format_card_time(row["time_display"], row["happened_at"], now),
        "place": row["place"],
        "keywords": row["keywords"],
    }


def row_to_detail_item(row: Mapping[str, Any]) -> dict:
    """行 → 详情项。"""
    return {
        "id": row["id"],
        "code": item_code(row["id"]),
        "name": row["name"],
        "type": row["type"],
        "status": row["status"],
        "icon": row["icon"],
        "category": row["category"],
        "timeLabel": time_label(row["type"]),
        "time": row["happened_at"],
        "place": row["place"],
        "publish": row["published_at"],
        "desc": row["desc"],
        "publisher": row["publisher"],
        "avatar": row["avatar"],
        "masked": row["masked"],
        "contact": row["contact"],
    }
