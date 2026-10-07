"""静态资源托管：页面、主题与脚本能通过 HTTP 取到，旧地址能跳转。

这个文件原来叫 ``test_placeholders.py``，负责"尚未实现的接口必须注册在约定路径上
并返回 501"。阶段 4 把最后两个写接口也实现之后，已经没有占位路由了，那部分随之
删除；只留下与静态托管有关的检查——这些与接口实现无关，长期有效。
"""

from __future__ import annotations

import pytest

PAGES = ("index", "search", "detail", "publish", "success")


def test_旧地址_home_html_跳转到_index_html(client):
    """首页更名为 index.html 之后，旧书签不能变成 404。"""
    response = client.get("/home.html", follow_redirects=False)
    assert response.status_code == 302
    assert response.headers["location"] == "/index.html"


def test_根路径直接命中首页(client):
    """StaticFiles(html=True) 会把目录请求解析到 index.html。"""
    response = client.get("/")
    assert response.status_code == 200
    assert "校园失物招领" in response.text


@pytest.mark.parametrize("page", PAGES)
def test_每个页面都能通过_HTTP_取到(client, page):
    response = client.get("/%s.html" % page)
    assert response.status_code == 200
    assert '<script src="js/api.js">' in response.text, "%s 缺少共用脚本引用" % page


def test_主题样式与共用脚本都能取到(client):
    """主题只有一份、被 5 页共用，取不到就是整站掉样式。"""
    for path in ("/css/visual-theme.css", "/js/api.js", "/js/common.js"):
        assert client.get(path).status_code == 200, path
