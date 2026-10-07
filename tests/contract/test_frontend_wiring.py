"""前端静态检查：页面与脚本必须保持"只发请求、只负责渲染"的形态。

这些检查**不需要浏览器、也不需要 Node**——只读源码文本，却正好挡住改造过程中
最容易发生的几类回归：

- 页面又长回了自己的数据（内嵌卡片、内嵌数据集）
- 脚本里重新出现内联逻辑，或引用了根本不存在的资源
- 已改造的页面悄悄退回读 localStorage
- 有人改完了页面却忘了同步迁移进度

对应《代码规范》第 3.8 节里"前端遗留物扫描"那条待办——以前靠人工 grep，
现在固化进测试层，随 CI 一起跑。
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

FRONTEND = Path(__file__).resolve().parent.parent.parent / "frontend"
PAGES = ["index", "search", "detail", "publish", "success"]

#: 各页"是否已接到后端接口"的当前状态。
#: **这就是迁移进度本身**，写死在这里是为了让"改了代码忘了改记录"立刻暴露。
#: 页面完成改造（阶段 3 / 4）后，必须同步改这张表，否则下面的测试会失败。
WIRED = {
    "index": True,      # 阶段 2 / 3 已接
    "search": True,     # 阶段 3 已接
    "detail": True,     # 阶段 3 已接
    "publish": False,   # 待阶段 4
    "success": False,   # 待阶段 4
}

#: 各页**是否还允许**出现 localStorage。
#: 已经接到接口的页面不该再依赖本地存储；detail 是唯一的例外，它的两处
#: （`?id=new` 过渡分支、标记已解决的写路径）都随阶段 4 一并移除——
#: 移除后把这里的 True 改成 False，测试会盯着这件事。
LOCAL_STORAGE_ALLOWED = {
    "index": False,
    "search": False,    # 阶段 3 已清理
    "detail": True,     # 阶段 4 移除
    "publish": True,    # 阶段 4 移除
    "success": True,    # 阶段 4 移除
}


def page_html(page: str) -> str:
    """读一个页面的 HTML 源码。"""
    return (FRONTEND / f"{page}.html").read_text(encoding="utf-8")


def page_js(page: str) -> str:
    """读一个页面对应的脚本源码。"""
    return (FRONTEND / "js" / f"{page}.js").read_text(encoding="utf-8")


@pytest.mark.parametrize("page", PAGES)
def test_页面没有内联样式与内联脚本逻辑(page):
    """主题样式只有一份、脚本一页一个文件，HTML 里不该再有内联块。"""
    html = page_html(page)
    assert "<style>" not in html, "内联 <style> 主题块必须移到 css/visual-theme.css"
    assert not re.search(r"^\s*<script>\s*$", html, re.M), \
        "内联 <script> 逻辑块必须外置为 js/<页面>.js"


@pytest.mark.parametrize("page", PAGES)
def test_页面引用的本地资源都存在(page):
    """引用了写错的路径时，页面会静默少一个脚本——静态页测试不了，这里先兜住。"""
    for ref in re.findall(r'(?:src|href)="((?:js|css)/[^"]+)"', page_html(page)):
        assert (FRONTEND / ref).is_file(), "引用了不存在的资源: %s" % ref


@pytest.mark.parametrize("page", PAGES)
def test_页面都引用了三个脚本且顺序正确(page):
    """顺序固定为「api.js → common.js → 本页 js」：本页脚本要在共用文件之后加载。

    位置必须锚定在 ``<script src="...">`` 标签上——页面顶部注释里也会提到
    ``js/<页面>.js``（注明"渲染见…"），直接搜文件名会命中注释，量错位置。
    """
    html = page_html(page)
    expected = ["js/api.js", "js/common.js", "js/%s.js" % page]
    positions = [html.find('<script src="%s">' % ref) for ref in expected]
    assert all(p != -1 for p in positions), "缺少 script 标签: %s" % expected
    assert positions == sorted(positions), "脚本顺序必须是 %s" % expected


@pytest.mark.parametrize("page", PAGES)
def test_没有页面还指向旧地址_home_html(page):
    """首页已更名为 index.html，残留引用会让"返回首页"打不开。"""
    assert "home.html" not in page_html(page)
    assert "home.html" not in page_js(page)


def test_首页的卡片全部由脚本渲染():
    """首页列表容器里不得再写死卡片，否则改接口后会出现新旧两份数据。"""
    assert "data-card=" not in page_html("index")


def test_详情页不再内嵌演示数据():
    """详情页的数据只应来自 GET /api/items/{id}。"""
    js = page_js("detail")
    assert "var ITEMS" not in js
    assert "ITEMS[" not in js
    assert "API.detail(" in js


@pytest.mark.parametrize("page", PAGES)
def test_页面脚本的接口接入状态与进度表一致(page):
    """已接接口的页面必须真的在调 API，未接的必须还没调。"""
    wired = "API." in page_js(page)
    assert wired is WIRED[page], (
        "%s 页的接口接入状态与 WIRED 表不符：改完页面记得同步更新本文件的 WIRED" % page)


@pytest.mark.parametrize("page", PAGES)
def test_localStorage_残留与迁移进度一致(page):
    """已完成改造的页面不许再依赖本地存储。

    这是"改造是不是真做完了"最容易被糊弄过去的一条：页面看着是调接口了，
    旧状态却还偷偷留在 localStorage 里，于是同一个东西既有服务端的一份、
    又有本机的一份。
    """
    used = "localStorage." in page_js(page)
    assert used is LOCAL_STORAGE_ALLOWED[page], (
        "%s 页的 localStorage 残留与进度表不符：清理完成后请同步更新 LOCAL_STORAGE_ALLOWED" % page)


# --------------------------------------------------------------------------
# 搜索页（阶段 3 改造后新增的检查）
# --------------------------------------------------------------------------
def test_搜索页的卡片全部由脚本渲染():
    """8 张硬编码卡片已删除，卡片改由 renderCard 渲染进 #resultItems。"""
    html = page_html("search")
    assert "data-result=" not in html, "搜索结果里不得再写死卡片"
    assert 'id="resultItems"' in html, "渲染容器 #resultItems 不见了"


def test_搜索页不再把本机发布的那条插进结果():
    """insertLocalPost 是"同一件东西既有服务端一份、又有本机一份"的来源，随改造删除。

    断言匹配的是**定义或调用**的形式而不是裸词：文件头注释里会说明"这个函数已被
    删除"，只查裸词会被自己的注释绊倒（这个坑真踩过一次）。
    """
    assert not re.search(r"\binsertLocalPost\s*\(", page_js("search")), \
        "不应再定义或调用 insertLocalPost"


def test_搜索页不再做前端关键词匹配():
    """匹配已移到服务端；前端再读一次 data-keywords 会变成双重过滤。"""
    js = page_js("search")
    assert not re.search(r"getAttribute\(\s*['\"]data-keywords", js), \
        "前端不应再读 data-keywords 做匹配"
    assert not re.search(r"getAttribute\(\s*['\"]data-result", js), \
        "前端不应再读 data-result 做类型过滤"
    assert "API.search(" in js


def test_搜索页用共用的卡片模板渲染():
    """卡片必须走 common.js 的 renderCard——它负责带上主题样式依赖的 data-* 属性。"""
    js = page_js("search")
    assert "renderCard(item, 'search')" in js


@pytest.mark.parametrize("page", ["index", "search"])
def test_渲染卡片的页面在占位里声明了卡片模板的类(page):
    """Tailwind 运行时按源码生成样式类，卡片改由脚本渲染后只能靠占位 div 兜住。

    ``opacity-80``（已解决卡片的弱化）是最容易漏掉的一个：漏了不报错，
    只是样式悄悄不对——所以专门盯着它。
    """
    placeholder = page_html(page)[page_html(page).rfind('<div class="hidden'):]
    for cls in ("opacity-80", "line-clamp-2", "active:scale-[0.99]",
                "bg-emerald-50", "text-amber-600"):
        assert cls in placeholder, "%s 的占位 div 缺少 %s" % (page, cls)
