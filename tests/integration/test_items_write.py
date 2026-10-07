"""两个写接口的集成测试：发布（``POST /api/items``）与标记已解决（``/resolve``）。

对应验收 4-A1 ~ 4-A11 里与接口有关的部分。重点盯三件事：

1. **服务端补全的每个字段**逐项断言——这些字段前端不提供，只在这里产生，
   而且详情页会直接拿去渲染，少一个页面就空一块；
2. **发布后立刻出现在首页与搜索的第一位**——这是本次改造的核心收益：
   旧版只写在本机 localStorage，列表里根本看不到；
3. **标记已解决的幂等性**——按钮被点两次、或者两个人同时点，结果必须一致。
"""

from __future__ import annotations

import pytest

PUBLISH = "/api/items"

#: 详情接口的字段全集。发布与标记已解决的返回值都必须是这一套
#: （前端拿它直接渲染详情页，见 tests/contract/test_api_contract.py）
DETAIL_FIELDS = {
    "id", "code", "name", "type", "status", "icon", "category", "timeLabel",
    "time", "place", "publish", "desc", "publisher", "avatar", "masked", "contact",
}


def publish(client, payload, **overrides):
    """发一条信息，返回响应对象。

    参数：
        client  —— TestClient。
        payload —— conftest 的 create_payload fixture（合法请求体）。
        overrides —— 覆盖其中某个字段，例如 ``type="seek"``。
    """
    return client.post(PUBLISH, json=dict(payload, **overrides))


# --------------------------------------------------------------------------
# 发布：HTTP 层
# --------------------------------------------------------------------------
def test_发布成功返回_201_与完整详情(client, create_payload):
    response = publish(client, create_payload)

    assert response.status_code == 201
    body = response.json()
    assert set(body) == DETAIL_FIELDS
    assert body["id"] == 9, "演示数据占 1~8，第一条用户数据应是 9"
    assert body["code"] == "LF-009"


def test_发布时缺少字段返回_422(client, create_payload):
    payload = dict(create_payload)
    payload.pop("contact")

    assert client.post(PUBLISH, json=payload).status_code == 422


@pytest.mark.parametrize(
    "field, bad_value",
    [
        ("type", "lost"),                 # 类型只允许 seek / find
        ("category", "不存在的类别"),       # 类别只允许那 7 个
        ("name", "   "),                  # 去掉空格后为空
        ("time", "2026/10/07 15:30"),     # 时间格式
    ],
)
def test_发布的非法字段返回_422(client, create_payload, field, bad_value):
    assert publish(client, create_payload, **{field: bad_value}).status_code == 422


def test_时间里的_T_被归一化(client, create_payload):
    """datetime-local 控件提交的是 '2026-10-07T15:30'，落库要统一成空格分隔。"""
    body = publish(client, create_payload, time="2026-10-07T15:30").json()

    assert body["time"] == "2026-10-07 15:30"


def test_文本字段的首尾空格被去掉(client, create_payload):
    assert publish(client, create_payload, name="  测试水杯  ").json()["name"] == "测试水杯"


# --------------------------------------------------------------------------
# 发布：服务端补全的字段（前端不提供，逐项断言）
# --------------------------------------------------------------------------
def test_补全_状态按类型给(client, create_payload):
    assert publish(client, create_payload, type="seek").json()["status"] == "seeking"
    assert publish(client, create_payload, type="find").json()["status"] == "unclaimed"


def test_补全_新发布的一律不是已解决(client, create_payload):
    """刚发布就标成"已解决"是说不通的。"""
    for item_type in ("seek", "find"):
        assert publish(client, create_payload, type=item_type).json()["status"] != "resolved"


def test_补全_图标按类型给(client, create_payload):
    assert publish(client, create_payload, type="seek").json()["icon"] == "mdi:help-circle-outline"
    assert publish(client, create_payload, type="find").json()["icon"] == "mdi:hand-heart-outline"


def test_补全_发布者与头像固定(client, create_payload):
    body = publish(client, create_payload).json()

    assert body["publisher"] == "我（本机发布）"
    assert body["avatar"] == "我"


def test_补全_脱敏串由联系方式现算(client, create_payload):
    """新数据不存在"写死的脱敏串"，必须由 contact 算出来。"""
    body = publish(client, create_payload).json()

    assert body["masked"] == "138****1234"
    assert body["contact"] == "13800001234"


def test_补全_发布时间来自服务端(client, create_payload):
    body = publish(client, create_payload).json()

    assert len(body["publish"]) == 16 and body["publish"][:2] == "20"


def test_补全_卡片描述取完整描述(client, create_payload):
    """卡片用 line-clamp-2 截断，不必另写一份短描述。"""
    body = publish(client, create_payload).json()

    item = next(i for i in client.get("/api/items/home").json()["items"] if i["id"] == body["id"])
    assert item["desc"] == create_payload["desc"]


def test_补全_卡片时间按日期推导而不是写死(client, create_payload):
    """演示数据的 time_display 是固定文案；新数据那一列留 NULL，读取时按今天/昨天推导。"""
    body = publish(client, create_payload).json()

    item = next(i for i in client.get("/api/items/home").json()["items"] if i["id"] == body["id"])
    assert item["time"].startswith(("今天 ", "昨天 ")) or "-" in item["time"]


@pytest.mark.parametrize("keyword", ["小熊", "第二食堂一楼", "水杯"])
def test_补全_搜索索引包含名称类别地点描述(client, create_payload, keyword):
    body = publish(client, create_payload).json()

    payload = client.get("/api/items/search", params={"q": keyword}).json()
    assert body["id"] in [i["id"] for i in payload["items"]]


def test_补全_索引里带类型同义词(client, create_payload):
    """招领的新数据能被"捡到"搜到，寻物的能被"丢了"搜到。"""
    find_id = publish(client, create_payload, type="find", name="找主的雨伞").json()["id"]
    seek_id = publish(client, create_payload, type="seek", name="丢了的钥匙扣").json()["id"]

    def ids(keyword):
        payload = client.get("/api/items/search", params={"q": keyword}).json()
        return [i["id"] for i in payload["items"]]

    assert find_id in ids("捡到")
    assert seek_id in ids("丢了")


# --------------------------------------------------------------------------
# 发布后立刻可见（本次改造的核心收益）
# --------------------------------------------------------------------------
def test_发布后出现在首页第一位(client, create_payload):
    new_id = publish(client, create_payload).json()["id"]

    payload = client.get("/api/items/home").json()
    assert payload["count"] == 7
    assert payload["items"][0]["id"] == new_id


def test_发布后出现在搜索第一位(client, create_payload):
    new_id = publish(client, create_payload).json()["id"]

    payload = client.get("/api/items/search").json()
    assert payload["count"] == 9
    assert payload["items"][0]["id"] == new_id


def test_连续发布时后发的排更前(client, create_payload):
    """同一分钟内连续发布，靠 id 倒序保证顺序稳定。"""
    first = publish(client, create_payload, name="先发布的").json()["id"]
    second = publish(client, create_payload, name="后发布的").json()["id"]

    ids = [i["id"] for i in client.get("/api/items/home").json()["items"]]
    assert ids[:2] == [second, first]


def test_发布后计数与类型筛选一致(client, create_payload):
    publish(client, create_payload, type="find")

    assert client.get("/api/items/home").json()["count"] == 7
    assert client.get("/api/items/home", params={"type": "find"}).json()["count"] == 4
    assert client.get("/api/items/home", params={"type": "seek"}).json()["count"] == 3


# --------------------------------------------------------------------------
# 标记已解决
# --------------------------------------------------------------------------
def test_标记已解决返回_resolved_与完整详情(client):
    response = client.post("/api/items/5/resolve")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "resolved"
    assert set(body) == DETAIL_FIELDS


def test_标记已解决是幂等的(client):
    """按钮点两次、两个人同时点，结果必须一样，且不报错。"""
    first = client.post("/api/items/5/resolve")
    second = client.post("/api/items/5/resolve")

    assert first.status_code == second.status_code == 200
    assert first.json()["status"] == second.json()["status"] == "resolved"


def test_对本来就已解决的条目重复标记也不报错(client):
    """4 号演示数据在种子数据里就是已解决。"""
    response = client.post("/api/items/4/resolve")

    assert response.status_code == 200
    assert response.json()["status"] == "resolved"


def test_标记不存在的_id_返回_404(client):
    response = client.post("/api/items/99999/resolve")

    assert response.status_code == 404
    assert response.json() == {"code": "not_found", "message": "物品不存在"}


def test_标记后状态已持久化(client):
    """不是只改了返回值——重新查一次仍是已解决。"""
    client.post("/api/items/5/resolve")

    assert client.get("/api/items/5").json()["status"] == "resolved"


def test_标记后的状态也反映在列表里(client):
    """首页与搜索读的是同一行数据，列表上的状态徽标也该跟着变。"""
    client.post("/api/items/5/resolve")

    item = next(i for i in client.get("/api/items/home").json()["items"] if i["id"] == 5)
    assert item["status"] == "resolved"
