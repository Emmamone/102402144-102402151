"""请求与响应模型。

响应模型的字段名以**前端渲染实际读取的名字为准**（例如 ``timeLabel``、
``code``），不做前后端命名风格转换；请求模型的校验规则是前端校验之外的
二次兜底（见 docs/system-design.md 第 5.4 节）。
"""

from __future__ import annotations

import re
from typing import Literal

from pydantic import BaseModel, field_validator

TIME_RE = re.compile(r"^\d{4}-\d{2}-\d{2} \d{2}:\d{2}$")

# 发布页的 7 个类别选项
CATEGORIES = (
    "证件卡片",
    "电子产品",
    "钥匙",
    "雨伞",
    "水杯",
    "书籍文具",
    "其他",
)

ItemType = Literal["seek", "find"]
ItemStatus = Literal["seeking", "unclaimed", "resolved"]


class ListItem(BaseModel):
    """列表项（首页与搜索页共用）。

    ``keywords`` 不参与前端筛选（筛选在服务端做），但前端渲染卡片时需要把它
    原样写进 ``data-keywords`` 属性——主题样式与 DOM 结构都依赖该属性存在。
    """

    id: int
    name: str
    type: ItemType
    status: ItemStatus
    icon: str
    desc: str
    time: str
    place: str
    keywords: str


class HomeResponse(BaseModel):
    count: int
    items: list[ListItem]


class DetailItem(BaseModel):
    id: int
    code: str
    name: str
    type: ItemType
    status: ItemStatus
    icon: str
    category: str
    timeLabel: str
    time: str
    place: str
    publish: str
    desc: str
    publisher: str
    avatar: str
    masked: str
    contact: str


class CreateRequest(BaseModel):
    """发布请求（``POST /api/items`` 的请求体）。"""

    name: str
    type: ItemType
    category: str
    time: str
    place: str
    desc: str
    contact: str

    @field_validator("name", "place", "desc", "contact")
    @classmethod
    def _not_blank(cls, value: str) -> str:
        text = (value or "").strip()
        if not text:
            raise ValueError("不能为空")
        return text

    @field_validator("category")
    @classmethod
    def _known_category(cls, value: str) -> str:
        text = (value or "").strip()
        if text not in CATEGORIES:
            raise ValueError("未知的类别")
        return text

    @field_validator("time")
    @classmethod
    def _normalized_time(cls, value: str) -> str:
        # 浏览器 datetime-local 控件提交的是 'YYYY-MM-DDTHH:mm'，归一化为空格分隔
        text = (value or "").strip().replace("T", " ")
        if not TIME_RE.match(text):
            raise ValueError("时间格式应为 YYYY-MM-DD HH:mm")
        return text
