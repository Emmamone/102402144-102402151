"""前后端字段契约。

前端没有构建工具、也没有 Node 测试环境，业务逻辑又全部在服务端，页面只剩渲染。
所以"接口返回的字段是否还是页面读取的那几个"必须在这里锁住——字段改名在后端
测试里可能全绿，但页面会静默丢内容。

覆盖前端的三处渲染：
- 列表卡片（首页与搜索页共用 ``renderCard``）→ ``CARD_REQUIRED``
- 详情页 ``render(it)`` → ``DETAIL_REQUIRED``
- 错误体形状 → ``{code, message}``

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
    """前端 api.js 靠 body.message 给用户提示，所以"业务错误"必须是这个形状。

    覆盖 404 的两处（详情、标记已解决）。**故意不含 422**：字段校验失败走的是
    FastAPI 原生形状 ``{detail: [...]}``，设计如此——前端本地校验先拦一道，
    真出现 422 说明有人在绕过前端直接调接口。
    """
    for method, path in (("GET", "/api/items/999"), ("POST", "/api/items/999/resolve")):
        response = client.request(method, path)
        assert response.status_code == 404
        assert set(response.json()) == {"code", "message"}


def test_计数与列表长度一致(client):
    for type_filter in ("all", "seek", "find"):
        payload = client.get("/api/items/home", params={"type": type_filter}).json()
        assert payload["count"] == len(payload["items"])


def test_搜索结果也用同一套卡片字段(client):
    """搜索页与首页共用 renderCard，字段集合必须一致。"""
    items = client.get("/api/items/search").json()["items"]
    assert items
    for item in items:
        assert set(item) == set(CARD_REQUIRED)
        for field, expected_type in CARD_REQUIRED.items():
            assert isinstance(item[field], expected_type), field


# --------------------------------------------------------------------------
# 详情页 render(it) 读取的字段
# --------------------------------------------------------------------------
DETAIL_REQUIRED = {
    "id": int,
    "code": str,
    "name": str,
    "type": str,
    "status": str,
    "icon": str,
    "category": str,
    "timeLabel": str,
    "time": str,
    "place": str,
    "publish": str,
    "desc": str,
    "publisher": str,
    "avatar": str,
    "masked": str,
    "contact": str,
}


def test_详情返回的字段与详情页渲染所需完全一致(client):
    body = client.get("/api/items/1").json()
    assert set(body) == set(DETAIL_REQUIRED), "字段集合发生变化，详情页 render 需要同步修改"


def test_详情字段类型正确(client):
    body = client.get("/api/items/1").json()
    for field, expected_type in DETAIL_REQUIRED.items():
        assert isinstance(body[field], expected_type), field


def test_详情的时间标签只有两种取值(client):
    labels = {client.get("/api/items/%d" % i).json()["timeLabel"] for i in range(1, 9)}
    assert labels == {"丢失时间", "拾取时间"}


def test_详情与列表共用同一套编号规则(client):
    for item_id in (1, 8):
        assert client.get("/api/items/%d" % item_id).json()["code"] == "LF-%03d" % item_id
