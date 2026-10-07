"""尚未实现的接口：必须按设计注册在约定路径上，并返回 501。

这条测试的意义是**锁住接口契约**：后续阶段填实现时，路径与错误体形状不该再变；
同时它也防止"路由忘了注册"被误判成 404。
"""

from __future__ import annotations

import pytest

PLACEHOLDER_REQUESTS = [
    ("GET", "/api/items/search", None),
    ("GET", "/api/items/1", None),
    ("POST", "/api/items", None),
    ("POST", "/api/items/1/resolve", None),
]


@pytest.mark.parametrize("method, path, body", PLACEHOLDER_REQUESTS)
def test_占位接口返回_501(client, method, path, body):
    response = client.request(method, path, json=body)
    assert response.status_code == 501


@pytest.mark.parametrize("method, path, body", PLACEHOLDER_REQUESTS)
def test_占位接口的错误体是_code_message_形状(client, method, path, body):
    body = client.request(method, path).json()
    assert body["code"] == "not_implemented"
    assert isinstance(body["message"], str) and body["message"]


def test_旧地址_home_html_跳转到_index_html(client):
    response = client.get("/home.html", follow_redirects=False)
    assert response.status_code == 302
    assert response.headers["location"] == "/index.html"


def test_首页可以由静态挂载提供(client):
    response = client.get("/index.html")
    assert response.status_code == 200
    assert "校园失物招领" in response.text
