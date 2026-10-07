"""前后端字段契约。

前端没有构建工具、也没有 Node 测试环境，业务逻辑又全部在服务端，页面只剩渲染。
所以"接口返回的字段是否还是页面读取的那几个"必须在这里锁住——字段改名在后端
测试里可能全绿，但页面会静默丢内容。

**前端新增对某字段的依赖时，必须同步在本文件加断言。**
"""

from __future__ import annotations

# frontend/js/common.js 的 renderCard 读取的字段
CARD_REQUIRED = {
    "id": int,
    "name": str,
    "type": str,
    "status": str,
    "icon": str,
    "desc": str,
    "time": str,
    "place": str,
    "keywords": str,
}

ITEM_TYPES = {"seek", "find"}
ITEM_STATUSES = {"seeking", "unclaimed", "resolved"}


def test_首页返回的字段与卡片模板所需完全一致(client):
    items = client.get("/api/items/home").json()["items"]
    assert items, "首页至少应有一条数据用于校验契约"

    for item in items:
        assert set(item) == set(CARD_REQUIRED), "字段集合发生变化，前端卡片模板需要同步修改"


def test_字段类型与卡片模板的用法相符(client):
    for item in client.get("/api/items/home").json()["items"]:
        for field, expected_type in CARD_REQUIRED.items():
            assert isinstance(item[field], expected_type), field


def test_枚举取值在设计范围内(client):
    for item in client.get("/api/items/home").json()["items"]:
        assert item["type"] in ITEM_TYPES
        assert item["status"] in ITEM_STATUSES


def test_卡片依赖的文案字段都非空(client):
    for item in client.get("/api/items/home").json()["items"]:
        for field in ("name", "icon", "desc", "time", "place"):
            assert item[field], "卡片渲染依赖 %s 非空" % field


def test_id_是唯一整数且与详情页链接一致(client):
    ids = [item["id"] for item in client.get("/api/items/home").json()["items"]]
    assert all(isinstance(i, int) for i in ids)
    assert len(ids) == len(set(ids))


def test_错误体形状是_code_message(client):
    body = client.get("/api/items/search").json()
    assert set(body) == {"code", "message"}


def test_计数与列表长度一致(client):
    for type_filter in ("all", "seek", "find"):
        payload = client.get("/api/items/home", params={"type": type_filter}).json()
        assert payload["count"] == len(payload["items"])
