"""SQLite 连接管理与建表 DDL。

本模块只负责「连接」与「表结构」，不含任何业务规则、也不做序列化
（见 docs/coding-standards.md 第 4.1 节）。

数据库路径按以下优先级解析：

1. 调用方显式传入的 ``path``（测试用临时文件走这条）
2. 环境变量 ``CLF_DB_PATH``
3. ``default_db_path()`` —— 开发时是仓库根目录的 ``db.sqlite3``，
   打包成 exe 后是 exe 同级目录（见该函数的说明）

**上传图片的目录**（``uploads/``）也在这里解析，用的是同一套"开发时在仓库里、
打包后在 exe 旁边"的规则——它和数据库一样属于**运行时数据**，两者必须待在一起，
否则备份/删除时会只搬走一半。
"""

from __future__ import annotations

import os
import sqlite3
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

#: 上传图片的目录名（与数据库同级）
UPLOADS_DIRNAME = "uploads"

SCHEMA = """
CREATE TABLE IF NOT EXISTS items (
  id           INTEGER PRIMARY KEY AUTOINCREMENT,
  name         TEXT    NOT NULL,
  type         TEXT    NOT NULL CHECK (type IN ('seek','find')),
  status       TEXT    NOT NULL CHECK (status IN ('seeking','unclaimed','resolved')),
  category     TEXT    NOT NULL,
  icon         TEXT    NOT NULL,
  card_desc    TEXT    NOT NULL,
  desc         TEXT    NOT NULL,
  happened_at  TEXT    NOT NULL,
  time_display TEXT,
  place        TEXT    NOT NULL,
  published_at TEXT    NOT NULL,
  publisher    TEXT    NOT NULL,
  avatar       TEXT    NOT NULL,
  masked       TEXT    NOT NULL,
  contact      TEXT    NOT NULL,
  keywords     TEXT    NOT NULL,
  image        TEXT,                          -- 上传的图片文件名；没有图时为 NULL
  source       TEXT    NOT NULL DEFAULT 'demo' CHECK (source IN ('demo','user')),
  home_order   INTEGER,
  search_order INTEGER,
  created_at   TEXT    NOT NULL DEFAULT (datetime('now','localtime'))
);

CREATE INDEX IF NOT EXISTS idx_items_home   ON items(home_order);
CREATE INDEX IF NOT EXISTS idx_items_search ON items(search_order);
"""


def default_db_path() -> Path:
    """默认的数据库位置。

    开发时是仓库根目录的 ``db.sqlite3``；**打包成 exe 后是 exe 的同级目录**。

    为什么不沿用 ``__file__``：单文件模式下 ``__file__`` 指向的是进程启动时
    解压出来的临时目录，进程一退就被删——数据库放那儿等于每次启动都像第一次运行，
    用户发布的数据、标记过的已解决状态全都不留痕。放在 exe 旁边才是"可持久化"
    的位置（也方便直接看到、备份、删除重来）。
    """
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent / "db.sqlite3"
    return REPO_ROOT / "db.sqlite3"


def resolve_db_path(path: str | Path | None = None) -> Path:
    """按 显式入参 > 环境变量 ``CLF_DB_PATH`` > ``default_db_path()`` 的顺序解析。"""
    if path is not None:
        return Path(path)
    env_path = os.environ.get("CLF_DB_PATH")
    return Path(env_path) if env_path else default_db_path()


def default_uploads_dir() -> Path:
    """默认的上传图片目录：与数据库同级（开发时在仓库根，打包后在 exe 旁边）。

    规则和 ``default_db_path()`` 完全一致，理由也一样——见该函数的说明。
    """
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent / UPLOADS_DIRNAME
    return REPO_ROOT / UPLOADS_DIRNAME


def resolve_uploads_dir(path: str | Path | None = None) -> Path:
    """按 显式入参 > 环境变量 ``CLF_UPLOADS_DIR`` > ``default_uploads_dir()`` 解析。

    测试用环境变量把它指到临时目录，这样跑测试不会往仓库里塞图片。
    """
    if path is not None:
        return Path(path)
    env_path = os.environ.get("CLF_UPLOADS_DIR")
    return Path(env_path) if env_path else default_uploads_dir()


def ensure_uploads_dir(path: str | Path | None = None) -> Path:
    """确保上传目录存在并返回它。

    必须**在构造 StaticFiles 之前**调用：Starlette 在构造时就校验目录是否存在，
    目录不在会直接抛错（表现为应用起不来，而不是某个请求 404）。
    """
    target = resolve_uploads_dir(path)
    target.mkdir(parents=True, exist_ok=True)
    return target


def connect(path: str | Path | None = None) -> sqlite3.Connection:
    """打开一个连接。

    每个请求各开一个连接（不共享全局连接对象），启用 WAL 以便并发读写；
    行工厂用 ``sqlite3.Row``，使 serialize 层可以按下标名取值。
    """
    conn = sqlite3.connect(resolve_db_path(path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def init_db(path: str | Path | None = None) -> None:
    """建表、建索引，并补齐后加的列（可重复执行）。

    **为什么要单独做迁移**：``CREATE TABLE IF NOT EXISTS`` 对已存在的表是空操作，
    所以老库（比如仓库根目录那个 ``db.sqlite3``）不会因为 SCHEMA 里多了一列就自动
    获得该列——之后任何 ``SELECT *`` + 按列名取值的地方都会 KeyError。
    这里用 ``PRAGMA table_info`` 查一遍，缺了就 ``ALTER TABLE`` 补上；
    新库由 SCHEMA 直接建好，这段相当于空转。
    """
    conn = connect(path)
    try:
        conn.executescript(SCHEMA)
        _migrate(conn)
        conn.commit()
    finally:
        conn.close()


def _migrate(conn: sqlite3.Connection) -> None:
    """把后加的列补进已存在的表里。只增列，不改类型、不删列。

    参数：conn —— 已打开的连接（由调用方负责提交）。
    返回：无。

    注意：``ALTER TABLE ADD COLUMN`` 加的列**必须可空**（或带默认值）——
    否则已有行无法满足约束。``image`` 正是可空的：演示数据与不支持图片的旧数据
    都靠 NULL 表示"没有图"。
    """
    existing = {row[1] for row in conn.execute("PRAGMA table_info(items)")}
    if "image" not in existing:
        conn.execute("ALTER TABLE items ADD COLUMN image TEXT")
