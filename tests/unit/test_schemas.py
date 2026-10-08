"""请求/响应模型校验的单元测试。"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from backend import schemas

VALID_PAYLOAD = {
    "name": "校园卡",
    "type": "seek",
    "category": "证件卡片",
    "time": "2026-10-07 14:30",
    "place": "图书馆二楼自习区",
    "desc": "蓝色卡套，卡面贴有姓名贴。",
    "contact": "13800001234",
}


def test_合法请求通过():
    req = schemas.CreateRequest(**VALID_PAYLOAD)
    assert req.name == "校园卡"
    assert req.type == "seek"


def test_时间里的_T_被归一化为空格():
    payload = dict(VALID_PAYLOAD, time="2026-10-07T14:30")
    assert schemas.CreateRequest(**payload).time == "2026-10-07 14:30"


@pytest.mark.parametrize("field", ["name", "place", "desc", "contact"])
def test_文本字段首尾空格被去除(field):
    payload = dict(VALID_PAYLOAD, **{field: "  内容  "})
    assert getattr(schemas.CreateRequest(**payload), field) == "内容"


@pytest.mark.parametrize("field", ["name", "place", "desc", "contact"])
def test_文本字段不能为空白(field):
    with pytest.raises(ValidationError):
        schemas.CreateRequest(**dict(VALID_PAYLOAD, **{field: "   "}))


def test_类型只能是_seek_或_find():
    with pytest.raises(ValidationError):
        schemas.CreateRequest(**dict(VALID_PAYLOAD, type="lost"))


def test_类别必须是七个选项之一():
    with pytest.raises(ValidationError):
        schemas.CreateRequest(**dict(VALID_PAYLOAD, category="不存在"))

    for category in schemas.CATEGORIES:
        assert schemas.CreateRequest(**dict(VALID_PAYLOAD, category=category)).category == category


@pytest.mark.parametrize("bad_time", ["2026/10/07 14:30", "2026-10-07", "14:30", "昨天"])
def test_时间格式不合法被拒(bad_time):
    with pytest.raises(ValidationError):
        schemas.CreateRequest(**dict(VALID_PAYLOAD, time=bad_time))


def test_缺少必填字段被拒():
    payload = dict(VALID_PAYLOAD)
    payload.pop("contact")
    with pytest.raises(ValidationError):
        schemas.CreateRequest(**payload)


def test_列表项拒绝未知状态():
    with pytest.raises(ValidationError):
        schemas.ListItem(
            id=1, name="校园卡", type="seek", status="unknown", icon="mdi:card",
            desc="描述", time="今天 08:20", place="图书馆", keywords="校园卡",
        )


def test_首页响应要求_count_与_items():
    with pytest.raises(ValidationError):
        schemas.HomeResponse(items=[])


# --------------------------------------------------------------------------
# 图片文件名（选填字段）
# --------------------------------------------------------------------------
def test_图片字段可以不传():
    assert schemas.CreateRequest(**VALID_PAYLOAD).image is None


@pytest.mark.parametrize("blank", ["", "   "])
def test_图片字段传空等同于不配图(blank):
    assert schemas.CreateRequest(**dict(VALID_PAYLOAD, image=blank)).image is None


def test_合法的图片文件名被接受():
    name = "a" * 32 + ".jpg"
    assert schemas.CreateRequest(**dict(VALID_PAYLOAD, image=name)).image == name


def test_图片文件名首尾空格被去掉():
    name = "a" * 32 + ".png"
    assert schemas.CreateRequest(**dict(VALID_PAYLOAD, image="  %s  " % name)).image == name


@pytest.mark.parametrize(
    "bad",
    ["../main.py", "a" * 32 + ".gif", "abc.jpg", "A" * 32 + ".jpg", "not-a-filename"],
)
def test_图片文件名形状不对被拒(bad):
    """形状问题在 schema 层就挡掉 → 422；"文件在不在"由路由查（400）。"""
    with pytest.raises(ValidationError):
        schemas.CreateRequest(**dict(VALID_PAYLOAD, image=bad))
