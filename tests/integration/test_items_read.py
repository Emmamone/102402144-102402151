"""首页列表接口的集成测试（真实 HTTP 请求，走临时数据库）。"""

from __future__ import annotations

HOME = "/api/items/home"


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
