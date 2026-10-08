"""前端静态检查：页面与脚本必须保持"只发请求、只负责渲染"的形态。

这些检查**不需要浏览器、也不需要 Node**——只读源码文本，却正好挡住改造过程中
最容易发生的几类回归：

- 页面又长回了自己的数据（内嵌卡片、内嵌数据集）
- 脚本里重新出现内联逻辑，或引用了根本不存在的资源
- 已改造的页面悄悄退回读 localStorage
- 有人改完了页面却忘了同步迁移进度

对应《代码规范》第 3.8 节里"前端遗留物扫描"那条待办——以前靠人工 grep，
现在固化进测试层，随 CI 一起跑。

**一个反复踩到的坑**：断言"某个函数/字符串已经被删掉"时，**不要查裸词**。
文件头注释里往往会写"随改造删除了 xxx"，裸词会被自己的注释绊倒。
统一改成查**定义或调用**的形式（如 ``insertLocalPost\\s*\\(``、
``setItem\\(\\s*['\"]campus``），只匹配代码、不匹配说明。
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

FRONTEND = Path(__file__).resolve().parent.parent.parent / "frontend"
PAGES = ["index", "search", "detail", "publish", "success"]

#: 各页"是否已接到后端接口"。阶段 4 之后**全部为 True**，这张表就成了回归保护：
#: 哪天有人新增页面却忘了接接口，或者把某个页面的脚本改回写死数据，这里会失败。
#: 改造期间它是迁移进度的记录（逐页从 False 改成 True）。
WIRED = {
    "index": True,      # 阶段 2 / 3 已接
    "search": True,     # 阶段 3 已接
    "detail": True,     # 阶段 3 读 + 阶段 4 写
    "publish": True,    # 阶段 4 已接
    "success": True,    # 阶段 4 已接（按 ?id 查询）
}

#: 各页**是否还允许**出现 localStorage。阶段 4 之后**全部为 False**：
#: 五个页面都只通过接口读写，localStorage 那套（`campusNewItem` / `campusResolved`）
#: 已彻底退场。改造期间它记录的是"哪几页还欠清理"。
LOCAL_STORAGE_ALLOWED = {
    "index": False,     # 阶段 2 / 3 已清理
    "search": False,    # 阶段 3 已清理
    "detail": False,    # 阶段 4 已清理
    "publish": False,   # 阶段 4 已清理
    "success": False,   # 阶段 4 已清理
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


# --------------------------------------------------------------------------
# 写路径（阶段 4 之后的检查）
# 断言一律查"定义或调用"的形式，不查裸词——原因见模块开头的说明
# --------------------------------------------------------------------------
def test_发布页把数据交给接口而不是本地存储():
    js = page_js("publish")
    assert "API.create(" in js, "发布页应通过 API.create 提交"
    assert "success.html?id=" in js, "成功后应带着新 id 跳到成功页"


def test_发布页不再往本地存储写东西():
    assert not re.search(r"setItem\(\s*['\"]campus", page_js("publish"))


def test_成功页不再依赖本机暂存():
    """`?id` 由发布页带上，campusNewItem 那一级过渡已随发布改造一起删除。"""
    js = page_js("success")
    assert "API.detail(" in js
    assert not re.search(r"getItem\(\s*['\"]campusNewItem", js)


def test_详情页的写路径已改走接口():
    assert "API.resolve(" in page_js("detail")


def test_详情页不再有_new_特殊值与内嵌数据():
    js = page_js("detail")
    assert not re.search(r"\bbuildNewItem\s*\(", js), "buildNewItem 应已删除"
    assert not re.search(r"===\s*['\"]new['\"]", js), "?id=new 这个特殊值应已取消"
    assert "var ITEMS" not in js, "内嵌演示数据应已删除"


def test_全站不再有本机插入那一条的逻辑():
    """阶段 3 删掉了 insertLocalPost（列表改为只认服务端数据），这里是全站确认。"""
    for page in PAGES:
        assert not re.search(r"\binsertLocalPost\s*\(", page_js(page)), page


# --------------------------------------------------------------------------
# 图片上传（新增需求：发布页可上传一张图并裁切，详情页展示）
# --------------------------------------------------------------------------
@pytest.mark.parametrize(
    "element_id",
    ["fImage", "imagePicker", "cropPanel", "cropStage", "cropImage", "cropBox", "eImage"],
)
def test_发布页有图片选择与框选控件(element_id):
    assert 'id="%s"' % element_id in page_html("publish"), "发布页缺少 #%s" % element_id


@pytest.mark.parametrize(
    "handle_id", ["cropHandleNw", "cropHandleNe", "cropHandleSw", "cropHandleSe"]
)
def test_框选有四个角柄(handle_id):
    """四个角柄是"拖角等比例缩放"的视觉提示。

    命中的判定不靠这些元素（它们在 CSS 里是 `pointer-events: none`），
    而是在脚本里按坐标算热区——手指比 14px 的点大得多，热区要按屏幕像素放宽。
    """
    assert 'id="%s"' % handle_id in page_html("publish")


def test_文件选择限定图片类型():
    """`accept` 只是给选择器的提示，真正拦截在后端；但没有它用户会先选到一堆不可用的文件。"""
    assert 'accept="image/jpeg,image/png,image/webp"' in page_html("publish")


def test_框选比例与详情页展示比例一致():
    """**跨文件的不变量**：详情页展示框的比例写在主题里（`.photo-frame` 的
    `aspect-ratio: 4 / 3`），而发布页锁定框选比例的是 `publish.js` 的
    `SELECT_ASPECT = 4 / 3`。两处必须相同——不一致的话，用户在发布页框到的内容
    会在详情页被 object-cover 再裁一次，"所见即所得"就没了。

    改比例时要同时改这两处（各自的注释里也互相指了）。
    """
    theme = (FRONTEND / "css" / "visual-theme.css").read_text(encoding="utf-8")

    assert "aspect-ratio: 4 / 3" in theme, "主题里的展示框比例变了"
    assert "SELECT_ASPECT = 4 / 3" in page_js("publish"), "发布页的框选比例没跟着改"
    assert "photo-frame" in page_html("detail"), "详情页应使用主题里的展示框类"


def test_框选是自己算的而不是引第三方库():
    """项目的约束之一是零依赖（只有 CDN 的 Tailwind 与 Iconify）。"""
    js = page_js("publish")
    for fn in ("exportCroppedImage", "defaultSelection", "layoutSelection",
               "startSelect", "moveSelect", "endSelect", "resetSelection",
               "cornerAt", "resizeSelection"):
        assert fn in js, "缺少框选函数 %s" % fn


def test_框选时捕获指针并兜底检测松手():
    """钉住一个真出现过的 bug。

    没有捕获指针时：按住鼠标拖到图片**外面**松手，`pointerup` 落在别的元素上，
    舞台收不到这个事件 → `dragMode` 永远清不掉 → 之后**不用按键**、只把鼠标移回
    图内就会继续拖动选择框。

    两道防线都要在：`pointerdown` 时捕获指针（框外也收得到 up），
    以及 `pointermove` 里发现"鼠标键已松开"就直接结束手势。
    """
    js = page_js("publish")
    assert "setPointerCapture" in js, "缺少指针捕获，框外松手会导致拖动态清不掉"
    assert "event.buttons === 0" in js, "缺少松手兜底判断"
    # 同类问题：多指同时按时第二根手指会覆盖手势起点，两根手指互相抢
    assert "dragPointerId" in js, "缺少指针 id 守卫，多指操作会互相抢"


def test_实现了缩放移动重选三种手势():
    """拖角缩放 / 框内移动 / 框外重新框——三种手势都要在。

    优先级（角柄 > 框内 > 框外）由 startSelect 保证：角柄的热区压在框边上，
    若判在"框内"之后，贴着角按下去会被当成移动而不是缩放。
    """
    js = page_js("publish")
    for mode in ("'resize'", "'move'", "'draw'"):
        assert "dragMode = " + mode in js, "缺少手势 %s" % mode

    corner_branch = js.index("dragMode = 'resize'")
    move_branch = js.index("dragMode = 'move'")
    assert corner_branch < move_branch, "角柄必须先于框内判定"


def test_框选用的是源图像素坐标():
    """框存成源图坐标（而不是屏幕坐标）才能扛住窗口缩放，导出时也不用再换算。"""
    js = page_js("publish")
    assert "naturalWidth" in js and "naturalHeight" in js
    assert "toSourcePoint" in js


def test_发布页把裁切结果交给上传接口():
    js = page_js("publish")
    assert "API.upload(" in js, "发布页应通过 API.upload 上传裁切结果"
    assert "payload.image" in js, "上传拿到的文件名应放进发布请求的 image 字段"


def test_详情页按_image_决定是否显示图片():
    assert 'id="dImage"' in page_html("detail")
    js = page_js("detail")
    assert "it.image" in js
    assert "'/uploads/'" in js, "图片地址应由文件名拼出"


def test_图片按钮的错误态样式在占位里():
    """脚本会切换这两个类（选图失败时标红），必须让 Tailwind 生成它们。"""
    html = page_html("publish")
    placeholder = html[html.rfind('<div class="hidden'):]
    for cls in ("border-rose-400", "border-slate-200"):
        assert cls in placeholder, cls
