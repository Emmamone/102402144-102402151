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

import sqlite3
from datetime import datetime
from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException, Query, Request
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles

from . import db, schemas, serialize

FRONTEND_DIR = Path(__file__).resolve().parent.parent / "frontend"

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
@app.get("/api/items/search")
def search_items_placeholder() -> None:
    """搜索接口占位。规则见 docs/system-design.md 第 5.2 节。"""
    raise _not_implemented("搜索接口")


@app.get("/api/items/{item_id}")
def get_item_placeholder(item_id: int) -> None:
    """详情接口占位。见 docs/system-design.md 第 5.3 节。"""
    raise _not_implemented("详情接口")


@app.post("/api/items")
def create_item_placeholder() -> None:
    """发布接口占位。见 docs/system-design.md 第 5.4 节。"""
    raise _not_implemented("发布接口")


@app.post("/api/items/{item_id}/resolve")
def resolve_item_placeholder(item_id: int) -> None:
    """标记已解决接口占位。见 docs/system-design.md 第 5.5 节。"""
    raise _not_implemented("标记已解决接口")


# --------------------------------------------------------------------------
# 旧地址兼容：首页已更名为 index.html，兜住外部书签
# --------------------------------------------------------------------------
@app.get("/home.html")
def legacy_home() -> RedirectResponse:
    return RedirectResponse("/index.html", status_code=302)


# 静态挂载必须最后注册（它是兜底匹配）
app.mount("/", StaticFiles(directory=FRONTEND_DIR, html=True), name="static")
