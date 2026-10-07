"""三个读接口的集成测试（真实 HTTP 请求，走临时数据库）。

覆盖首页列表、搜索、详情，对应验收 2-A1 ~ 2-A8。
"""

from __future__ import annotations

import pytest

HOME = "/api/items/home"
SEARCH = "/api/items/search"


def _ids(payload):
    return [item["id"] for item in payload["items"]]


def test_默认返回六条演示数据并按固定顺序(client):
    response = client.get(HOME)
    assert response.status_code == 200
    assert response.json()["count"] == 6
    assert _ids(response.json()) == [1, 2, 3, 4, 5, 6]


def test_count_与_items_长度一致(client):
    payload = client.get(HOME, params={"type": "seek"}).json()
    assert payload["count"] == len(payload["items"])


def test_寻物筛选返回三条(client):
    payload = client.get(HOME, params={"type": "seek"}).json()
    assert payload["count"] == 3
    assert _ids(payload) == [1, 4, 5]


def test_招领筛选返回三条(client):
    payload = client.get(HOME, params={"type": "find"}).json()
    assert payload["count"] == 3
    assert _ids(payload) == [2, 3, 6]


def test_首页不含只在搜索页出现的数据(client):
    """7、8 号只出现在搜索页与详情页，这是现状。"""
    assert 7 not in _ids(client.get(HOME).json())
    assert 8 not in _ids(client.get(HOME).json())


def test_用户新发布的数据排在最前(client, make_user_item):
    user_id = make_user_item(name="刚发布的物品")

    payload = client.get(HOME).json()

    assert payload["count"] == 7
    assert _ids(payload)[0] == user_id


def test_用户新发布的数据也能被类型筛选命中(client, make_user_item):
    make_user_item(name="刚发布的书", type="find")
    payload = client.get(HOME, params={"type": "find"}).json()
    assert payload["count"] == 4
    assert payload["items"][0]["type"] == "find"


def test_列表路径未被详情路由抢占(client):
    """字面量路径必须排在 /api/items/{id} 之前，否则会返回 422。"""
    response = client.get(HOME)
    assert response.status_code == 200


def test_非法的_type_参数返回_422(client):
    assert client.get(HOME, params={"type": "anything"}).status_code == 422


def test_卡片时间文案来自演示数据字面量(client):
    item = next(i for i in client.get(HOME).json()["items"] if i["id"] == 1)
    assert item["time"] == "今天 08:20"


def test_已解决的数据带着状态返回(client):
    item = next(i for i in client.get(HOME).json()["items"] if i["id"] == 4)
    assert item["status"] == "resolved"


# --------------------------------------------------------------------------
# 搜索接口
# --------------------------------------------------------------------------
def _search_ids(client, **params):
    return [item["id"] for item in client.get(SEARCH, params=params).json()["items"]]


def test_搜索空关键词返回全部八条并按固定顺序(client):
    """搜索页的顺序是 1、7、5、3、2、4、6、8，与原内嵌卡片顺序一致。"""
    payload = client.get(SEARCH).json()
    assert payload["count"] == 8
    assert [item["id"] for item in payload["items"]] == [1, 7, 5, 3, 2, 4, 6, 8]


def test_搜索包含只在搜索页出现的条目(client):
    """7、8 号不在首页，但必须在搜索结果里。"""
    ids = _search_ids(client)
    assert 7 in ids
    assert 8 in ids


def test_搜索按关键词子串匹配(client):
    assert _search_ids(client, q="校园卡") == [1, 7]
    assert _search_ids(client, q="钥匙") == [5]


@pytest.mark.parametrize(
    "keyword, expected_id",
    [
        ("蓝色卡套", 1),      # 只在搜索索引里，名称与描述都没有
        ("3号楼", 4),
        ("考研加油", 3),
        ("大学生活动中心", 8),
    ],
)
def test_搜索能命中索引里的同义词(client, keyword, expected_id):
    assert _search_ids(client, q=keyword) == [expected_id]


def test_搜索的关键词与类型组合生效(client):
    assert _search_ids(client, q="校园卡", type="find") == [7]
    assert _search_ids(client, q="校园卡", type="seek") == [1]


def test_搜索的_type_可单独筛选(client):
    assert _search_ids(client, type="seek") == [1, 5, 4]
    assert len(_search_ids(client, type="find")) == 5


def test_搜索无结果时返回空列表(client):
    payload = client.get(SEARCH, params={"q": "不存在的物品"}).json()
    assert payload["count"] == 0
    assert payload["items"] == []


def test_搜索的_count_与_items_长度一致(client):
    payload = client.get(SEARCH, params={"q": "校园卡"}).json()
    assert payload["count"] == len(payload["items"])


def test_用户新发布的数据在搜索结果里排最前(client, make_user_item):
    user_id = make_user_item(name="刚发布的东西")
    payload = client.get(SEARCH).json()
    assert payload["count"] == 9
    assert payload["items"][0]["id"] == user_id


def test_搜索的非法_type_返回_422(client):
    assert client.get(SEARCH, params={"type": "anything"}).status_code == 422


def test_搜索路径未被详情路由抢占(client):
    """与 /api/items/home 同理：字面量路径必须排在 /{item_id} 之前。"""
    assert client.get(SEARCH).status_code == 200


# --------------------------------------------------------------------------
# 详情接口
# --------------------------------------------------------------------------
def test_详情返回编号与完整字段(client):
    body = client.get("/api/items/1").json()
    assert body["code"] == "LF-001"
    assert body["name"] == "校园卡"
    assert body["category"] == "证件卡片"
    assert body["timeLabel"] == "丢失时间"
    assert body["time"] == "2026-09-27 08:20"       # 详情页用绝对时间
    assert body["publish"] == "2026-09-27 08:26"
    assert body["publisher"] == "张同学 · 计算机学院"
    assert body["avatar"] == "张"


def test_详情的脱敏串与联系方式不同源(client):
    """masked 是写死的展示值，不能由 contact 推导——这是数据保真的关键一条。"""
    body = client.get("/api/items/1").json()
    assert body["masked"] == "138****6621"
    assert body["contact"] == "微信：zhang_cc2024"


def test_详情给的是完整描述而非卡片短描述(client):
    body = client.get("/api/items/1").json()
    assert body["desc"].startswith("蓝色卡套")
    assert "卡内余额不多" in body["desc"]


def test_详情的时间标签随类型变化(client):
    assert client.get("/api/items/2").json()["timeLabel"] == "拾取时间"


def test_已解决的详情状态为_resolved(client):
    assert client.get("/api/items/4").json()["status"] == "resolved"


def test_详情不存在的_id_返回_404_与约定错误体(client):
    response = client.get("/api/items/999")
    assert response.status_code == 404
    assert response.json() == {"code": "not_found", "message": "物品不存在"}


def test_用户新发布的条目也能按_id_取到详情(client, make_user_item):
    user_id = make_user_item(name="刚发布的东西")
    body = client.get("/api/items/%d" % user_id).json()
    assert body["id"] == user_id
    assert body["code"] == "LF-009"
