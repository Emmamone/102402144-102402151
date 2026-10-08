"""FastAPI 应用：路由声明、依赖装配、静态挂载。

本模块只做「装配」，不写 SQL、不做数据转换（见 docs/coding-standards.md 第 4.1 节）。

路由声明顺序有一处硬性约束：``/api/items/home`` 这类字面量路径必须排在
``/api/items/{item_id}`` 之前，否则会被路径参数捕获并因整型转换失败返回 422。
静态挂载（``/``）是兜底匹配，必须放在最后。

上传的图片走 ``GET /uploads/{filename}`` 这个**接口**而不是 StaticFiles 挂载：
挂载会在**导入时**就把目录固定下来，而数据库路径是**每请求**解析的——
两者不一致会让测试没法各自指向临时目录。接口还能顺手做文件名白名单校验。
"""

from __future__ import annotations

import os
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

# FastAPI 的 Path 与 pathlib.Path 撞名；这里给前者起个别名，
# 因为 pathlib.Path 在本模块里用得更频繁（拼前端资源目录、数据库路径）
from fastapi import Depends, FastAPI, File, HTTPException, Query, Request, UploadFile
from fastapi import Path as PathParam
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles

from . import db, schemas, serialize, uploads


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


def get_uploads_dir() -> Path:
    """上传图片的目录，**每个请求各解析一次**。

    和数据库路径一样按「显式入参 > 环境变量 > 默认位置」解析，所以测试可以用
    ``CLF_UPLOADS_DIR`` 把它指到临时目录，而不用去动仓库里的 ``uploads/``。
    """
    return db.resolve_uploads_dir()


# --------------------------------------------------------------------------
# 读接口：首页列表、搜索、详情
# --------------------------------------------------------------------------
@app.get("/api/items/home", response_model=schemas.HomeResponse, summary="首页最新信息列表")
def list_home(
    type: str = Query("all", pattern="^(all|seek|find)$", description="筛选类型，默认 all"),
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
# 读接口（续）：搜索
# --------------------------------------------------------------------------
@app.get("/api/items/search", response_model=schemas.HomeResponse, summary="搜索物品")
def search_items(
    q: str = Query("", description="关键词，空串表示不按关键词过滤"),
    type: str = Query("all", pattern="^(all|seek|find)$", description="筛选类型，默认 all"),
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


@app.get("/api/items/{item_id}", response_model=schemas.DetailItem, summary="物品详情")
def get_item(
    item_id: int = PathParam(description="物品 id"),
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


# --------------------------------------------------------------------------
# 上传接口
# --------------------------------------------------------------------------
@app.post("/api/uploads", status_code=201, summary="上传图片")
async def upload_image(
    file: UploadFile = File(..., description="图片文件（JPG / PNG / WebP，不超过 5MB）"),
    uploads_dir: Path = Depends(get_uploads_dir),
) -> dict:
    """接收一张图片存到上传目录，返回文件名与可访问地址。

    请求：``multipart/form-data``，字段名 ``file``，一次一个文件。

    返回：201 + ``{"filename": "<32位十六进制>.<ext>", "url": "/uploads/<filename>"}``
        —— 前端把 ``filename`` 放进发布请求的 ``image`` 字段（见 5.4 节）。

    校验（依次进行，任一条不过就 400）：
        1. MIME 在白名单内（jpg / png / webp）；
        2. 内容非空；
        3. 不超过 5MB；
        4. **文件头魔数与声明的类型相符**——只信 ``Content-Type`` 等于让调用方
           自证合法，把任意文件标成 ``image/png`` 就能混进来。

    异常：错误体是项目统一的 ``{code, message}``；422 仍留给 Pydantic 的字段校验。

    约束：本接口**不做鉴权**（与全站一致），文件名由服务端生成、客户端传什么都不作数。
    """
    content_type = file.content_type or ""
    if uploads.extension_for(content_type) is None:
        raise HTTPException(
            status_code=400,
            detail={"code": "invalid_image", "message": "仅支持 JPG / PNG / WebP 图片"},
        )

    data = await file.read()
    if not data:
        raise HTTPException(
            status_code=400,
            detail={"code": "invalid_image", "message": "图片内容为空"},
        )
    if len(data) > uploads.MAX_UPLOAD_BYTES:
        # 文案跟着常量走：改了上限，提示自动跟着改，不会留在"5MB"上对不上
        raise HTTPException(
            status_code=400,
            detail={
                "code": "invalid_image",
                "message": "图片不能超过 %dMB" % (uploads.MAX_UPLOAD_BYTES // 1024 // 1024),
            },
        )
    if not uploads.looks_like_image(content_type, data):
        raise HTTPException(
            status_code=400,
            detail={"code": "invalid_image", "message": "文件内容不是有效的图片"},
        )

    filename = uploads.save_image(data, content_type, db.ensure_uploads_dir(uploads_dir))
    return {"filename": filename, "url": "/uploads/" + filename}


# --------------------------------------------------------------------------
# 写接口：发布、标记已解决
# --------------------------------------------------------------------------
@app.post("/api/items", response_model=schemas.DetailItem, status_code=201, summary="发布信息")
def create_item(
    payload: schemas.CreateRequest,
    conn: sqlite3.Connection = Depends(get_conn),
    uploads_dir: Path = Depends(get_uploads_dir),
) -> dict:
    """发布一条信息。

    请求体：``CreateRequest``（name / type / category / time / place / desc / contact）。
    前端已先校验一遍必填，这里是二次兜底——防止绕过前端直接调接口。

    返回：201 + 完整的 DetailItem，含服务端生成的 id 与编号（LF-00N）。

    服务端补全的字段（前端**不提供**，也不要让它提供）：

    - ``status``：寻物 → seeking，招领 → unclaimed。新发布的一律**不是**已解决。
    - ``icon``：寻物/招领各一个通用图标，与原前端 buildNewItem 的取值一致。
    - ``card_desc``：取 ``desc``。卡片用 line-clamp-2 截断，不必另写一份短描述。
    - ``time_display``：留 NULL → 读取时按"今天/昨天"推导，让新数据随时间自然变化
      （演示数据那一列是写死的文案，见 serialize.format_card_time）。
    - ``published_at``：服务端当前时间，不用客户端时钟（客户端时间可能不准）。
    - ``publisher`` / ``avatar``：固定「我（本机发布）」/「我」——没有账号体系。
    - ``masked``：由 ``contact`` 现算。新数据不存在"写死的脱敏串"这回事。
    - ``keywords``：name + category + place + desc + 类型同义词，供搜索用。
    - ``source`` / ``home_order`` / ``search_order``：'user' / NULL / NULL，
      排序时因此排在最前（见 system-design 第 4.3 节）。

    例外：``image`` 是**前端提供**的（上传接口返回的文件名），服务端只负责校验它
    确实存在于上传目录（不在就 400）；不传或传空表示这条信息没有配图。
    """
    # 文件名形状已由 schemas 的校验器挡过（纯函数、不碰文件系统）；
    # "这个文件到底在不在"只有到这里才知道，而且这属于请求内容有问题 → 400 而非 422
    if payload.image is not None and not (Path(uploads_dir) / payload.image).is_file():
        raise HTTPException(
            status_code=400,
            detail={"code": "invalid_image", "message": "图片不存在，请重新上传"},
        )

    now = datetime.now()
    values = {
        "name": payload.name,
        "type": payload.type,
        "status": serialize.DEFAULT_STATUS[payload.type],
        "category": payload.category,
        "icon": serialize.DEFAULT_ICON[payload.type],
        "card_desc": payload.desc,
        "desc": payload.desc,
        "happened_at": payload.time,
        "time_display": None,
        "place": payload.place,
        "published_at": now.strftime("%Y-%m-%d %H:%M"),
        "publisher": serialize.DEFAULT_PUBLISHER,
        "avatar": serialize.DEFAULT_AVATAR,
        "masked": serialize.mask_contact(payload.contact),
        "contact": payload.contact,
        "keywords": serialize.build_keywords(
            payload.name, payload.category, payload.place, payload.desc, payload.type
        ),
        "image": payload.image,
        "source": "user",
        "home_order": None,
        "search_order": None,
    }

    # 列名与占位符都来自上面这个固定字典，值一律参数化传入
    with conn:
        cursor = conn.execute(
            "INSERT INTO items (%s) VALUES (%s)"
            % (", ".join(values), ", ".join("?" for _ in values)),
            tuple(values.values()),
        )
        new_id = cursor.lastrowid

    row = conn.execute("SELECT * FROM items WHERE id = ?", (new_id,)).fetchone()
    return serialize.row_to_detail_item(row)


@app.post("/api/items/{item_id}/resolve", response_model=schemas.DetailItem, summary="标记已解决")
def resolve_item(
    item_id: int = PathParam(description="物品 id"),
    conn: sqlite3.Connection = Depends(get_conn),
) -> dict:
    """把一条信息标记为已解决。

    路径参数：
        item_id —— 物品 id。

    返回：200 + 更新后的 DetailItem（``status`` 为 ``resolved``）。

    异常：id 不存在时 404，错误体与详情接口一致。

    幂等：对已解决的条目重复调用不报错，仍返回 resolved——前端按钮被点两次、
    或者两个人同时点，结果都一样。

    约束：**不做发布者归属校验**（与改造前一致：任何访客都能点这个按钮），
    而且生效范围是**全局**的，不再像过去那样只影响本机浏览器。
    """
    row = conn.execute("SELECT * FROM items WHERE id = ?", (item_id,)).fetchone()
    if row is None:
        raise HTTPException(
            status_code=404,
            detail={"code": "not_found", "message": "物品不存在"},
        )

    if row["status"] != "resolved":
        with conn:
            conn.execute("UPDATE items SET status = 'resolved' WHERE id = ?", (item_id,))
        row = conn.execute("SELECT * FROM items WHERE id = ?", (item_id,)).fetchone()

    return serialize.row_to_detail_item(row)


# --------------------------------------------------------------------------
# 读取上传的图片
# --------------------------------------------------------------------------
@app.get("/uploads/{filename}", summary="读取上传的图片")
def get_uploaded_image(
    filename: str,
    uploads_dir: Path = Depends(get_uploads_dir),
) -> FileResponse:
    """按文件名返回上传的图片。

    路径参数：``filename`` —— 上传接口返回的那个文件名。

    返回：200 + 图片字节（``Content-Type`` 按扩展名推断）。

    异常：文件名形状不合法、或文件不存在，都返回 404 + ``{code, message}``。
        两种情况**故意用同一个响应**：不告诉调用方"这个名字格式对但文件不在"，
        免得能被用来探测哪些文件存在。

    约束：文件名必须匹配服务端生成的形状（32 位十六进制 + 白名单扩展名），
        路径穿越因此不可能发生——外部输入压根参与不了路径拼接。
    """
    if not uploads.is_valid_filename(filename) or not (Path(uploads_dir) / filename).is_file():
        raise HTTPException(
            status_code=404,
            detail={"code": "not_found", "message": "图片不存在"},
        )
    return FileResponse(Path(uploads_dir) / filename)


# --------------------------------------------------------------------------
# 旧地址兼容：首页已更名为 index.html，兜住外部书签
# --------------------------------------------------------------------------
@app.get("/home.html", summary="旧地址跳转（首页已更名为 index.html）")
def legacy_home() -> RedirectResponse:
    """旧地址兼容：首页由 home.html 更名为 index.html 后，把旧链接跳过去。

    返回：302 跳转到 /index.html。
    约束：必须注册在静态挂载之前，否则会被 StaticFiles 兜底匹配成 404。
        用 302（临时）而不是 301，避免浏览器把旧地址永久缓存住。
    """
    return RedirectResponse("/index.html", status_code=302)


# 静态挂载必须最后注册（它是兜底匹配）
app.mount("/", StaticFiles(directory=FRONTEND_DIR, html=True), name="static")
