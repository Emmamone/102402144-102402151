"""FastAPI 应用：路由声明、依赖装配、静态挂载。

本模块只做「装配」，不写 SQL、不做数据转换（见 docs/coding-standards.md 第 4.1 节）。

当前实现进度：**只有首页接口 ``GET /api/items/home`` 是实现的**；搜索、详情、
发布、标记已解决四个路由按 docs/system-design.md 第 5 节的定义注册为 501 占位，
路径与响应形状已固定，后续阶段直接填充实现即可。

路由声明顺序有一处硬性约束：``/api/items/home`` 这类字面量路径必须排在
``/api/items/{item_id}`` 之前，否则会被路径参数捕获并因整型转换失败返回 422。
静态挂载（``/``）是兜底匹配，必须放在最后。
"""

from __future__ import annotations

import os
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException, Query, Request
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles

from . import db, schemas, serialize


def _frontend_dir() -> Path:
    """前端静态文件所在目录，按顺序取第一个存在的。

    1. 环境变量 ``CLF_FRONTEND_DIR`` —— 临时指到别处调试用
    2. **exe 同级的 ``frontend/``** —— 打包后优先用这一份。于是改页面、样式、
       脚本只需要替换这个文件夹，**不用重新打包 exe**（前端资源与后端代码解耦）
    3. 包内的 ``frontend/``（``sys._MEIPASS``）—— 上一份不存在时的兜底，
       保证把 exe 单独拷到别的机器上仍然能跑
    4. 开发时：仓库根目录的 ``frontend/``

    为什么显式判断而不是直接靠 ``__file__`` 往上推：后者在冻结环境里的取值依赖
    PyInstaller 的内部约定，而且**两种**位置（外部目录 / 包内解压目录）都有可能，
    写清楚以后别人才敢动。启动时会把最终生效的是哪一份打出来。
    """
    env_dir = os.environ.get("CLF_FRONTEND_DIR")
    if env_dir:
        return Path(env_dir)

    if getattr(sys, "frozen", False):
        beside_exe = Path(sys.executable).resolve().parent / "frontend"
        if beside_exe.is_dir():
            return beside_exe
        base = Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent))
        return base / "frontend"

    return Path(__file__).resolve().parent.parent / "frontend"


FRONTEND_DIR = _frontend_dir()

app = FastAPI(title="校园失物招领 API", version="0.1.0")


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    """统一错误体为 ``{"code": ..., "message": ...}``。

    FastAPI 默认把 ``HTTPException.detail`` 包在 ``{"detail": ...}`` 里，
    与本项目约定的错误体不一致，这里把它摊平。
    """
    detail = exc.detail
    if isinstance(detail, dict):
        body = detail
    else:
        body = {"code": "error", "message": str(detail)}
    return JSONResponse(status_code=exc.status_code, content=body)


def get_conn():
    """每个请求各开一个连接，请求结束后关闭。"""
    conn = db.connect()
    try:
        yield conn
    finally:
        conn.close()


def _not_implemented(what: str) -> HTTPException:
    """构造"尚未实现"的统一错误响应。

    参数：what —— 接口的中文名，用于拼出「XXX 尚未实现」这句提示。
    返回：一个 501 的 HTTPException，错误体由上面的处理器摊平成 {code, message}。
    约束：占位接口一律走这里，保证 4 个未实现路由的错误体形状完全一致
        （tests/integration/test_placeholders.py 会校验 code 为 not_implemented）。
    """
    return HTTPException(
        status_code=501,
        detail={"code": "not_implemented", "message": "%s 尚未实现" % what},
    )


# --------------------------------------------------------------------------
# 已实现：首页列表
# --------------------------------------------------------------------------
@app.get("/api/items/home", response_model=schemas.HomeResponse)
def list_home(
    type: str = Query("all", pattern="^(all|seek|find)$"),
    conn: sqlite3.Connection = Depends(get_conn),
) -> dict:
    """首页「最新信息」列表。

    只包含演示数据中 ``home_order`` 非空的部分（6 条）加上用户新发布的数据；
    用户新发布的数据排在最前，其后按 ``home_order`` 固定顺序。
    """
    rows = conn.execute(
        """
        SELECT * FROM items
        WHERE (:type = 'all' OR type = :type)
          AND (source = 'user' OR home_order IS NOT NULL)
        ORDER BY (source = 'user') DESC, home_order ASC, id DESC
        """,
        {"type": type},
    ).fetchall()

    now = datetime.now()
    items = [serialize.row_to_list_item(row, now) for row in rows]
    return {"count": len(items), "items": items}


# --------------------------------------------------------------------------
# 占位：待后续阶段实现（路径与响应形状已按设计固定）
# --------------------------------------------------------------------------
@app.get("/api/items/search", response_model=schemas.HomeResponse)
def search_items(
    q: str = Query("", description="关键词，空串表示不按关键词过滤"),
    type: str = Query("all", pattern="^(all|seek|find)$"),
    conn: sqlite3.Connection = Depends(get_conn),
) -> dict:
    """搜索物品：对搜索索引文本做不区分大小写的子串匹配，再按类型筛选。

    查询参数：
        q —— 关键词，默认空串（返回全部 8 条演示数据 + 用户新发布的数据）。
        type —— all / seek / find，默认 all。

    返回：200 + {count, items[]}，顺序为「用户新发布的在前，其次按 search_order」。

    实现要点：
        - 匹配用 instr(lower(keywords), lower(:q))，等价于改造前的
          `data-keywords.toLowerCase().indexOf(keyword) !== -1`。SQLite 的 lower()
          只处理 ASCII，中文不受影响，所以与前端行为一致。
        - 与首页不同，搜索**包含 7、8 号**——它们只在搜索页与详情页出现，
          所以这里没有 home_order 那道过滤。
    """
    rows = conn.execute(
        """
        SELECT * FROM items
        WHERE (:type = 'all' OR type = :type)
          AND (:q = '' OR instr(lower(keywords), lower(:q)) > 0)
        ORDER BY (source = 'user') DESC, search_order ASC, id DESC
        """,
        {"type": type, "q": q},
    ).fetchall()

    now = datetime.now()
    items = [serialize.row_to_list_item(row, now) for row in rows]
    return {"count": len(items), "items": items}


@app.get("/api/items/{item_id}", response_model=schemas.DetailItem)
def get_item(
    item_id: int,
    conn: sqlite3.Connection = Depends(get_conn),
) -> dict:
    """取单条物品的完整详情。

    路径参数：
        item_id —— 物品 id，正整数。

    返回：200 + DetailItem（含 code / publisher / masked / contact 等只在这里才
        出现的字段；详情页的「时间」是绝对时间，与卡片上的相对文案不同）。

    异常：id 不存在时 404，错误体 {code: "not_found", message: "物品不存在"}。
        前端收到 404 应回落去取 1 号，沿用改造前的容错行为。

    约束：本路由是路径参数，必须注册在 /api/items/home 与 /api/items/search
        这两个字面量路径**之后**，否则会把它们吃掉、并因整型转换失败返回 422。
    """
    row = conn.execute("SELECT * FROM items WHERE id = ?", (item_id,)).fetchone()
    if row is None:
        raise HTTPException(
            status_code=404,
            detail={"code": "not_found", "message": "物品不存在"},
        )
    return serialize.row_to_detail_item(row)


@app.post("/api/items")
def create_item_placeholder() -> None:
    """发布接口占位。

    请求体（待实现）：CreateRequest —— name / type / category / time / place / desc / contact。
    返回（待实现）：201 + DetailItem，并在服务端补全状态、图标、发布者、头像、
        脱敏串、搜索索引与发布时间（前端不提供这些）。
    当前：抛 501。前端 publish.js 因此仍写 localStorage。
    规则见 docs/system-design.md 第 5.4 节。
    """
    raise _not_implemented("发布接口")


@app.post("/api/items/{item_id}/resolve")
def resolve_item_placeholder(item_id: int) -> None:
    """标记已解决接口占位。

    路径参数：item_id —— 物品 id。
    返回（待实现）：200 + DetailItem（status 变为 resolved）；id 不存在时 404；
        重复调用**幂等**，不报错。
    当前：抛 501。前端 detail.js 的 markResolved 因此仍写 localStorage。
    约束：本接口不做发布者归属校验（与现状一致），且生效范围是全局的。
    规则见 docs/system-design.md 第 5.5 节。
    """
    raise _not_implemented("标记已解决接口")


# --------------------------------------------------------------------------
# 旧地址兼容：首页已更名为 index.html，兜住外部书签
# --------------------------------------------------------------------------
@app.get("/home.html")
def legacy_home() -> RedirectResponse:
    """旧地址兼容：首页由 home.html 更名为 index.html 后，把旧链接跳过去。

    返回：302 跳转到 /index.html。
    约束：必须注册在静态挂载之前，否则会被 StaticFiles 兜底匹配成 404。
        用 302（临时）而不是 301，避免浏览器把旧地址永久缓存住。
    """
    return RedirectResponse("/index.html", status_code=302)


# 静态挂载必须最后注册（它是兜底匹配）
app.mount("/", StaticFiles(directory=FRONTEND_DIR, html=True), name="static")
