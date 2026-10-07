"""SQLite 连接管理与建表 DDL。

本模块只负责「连接」与「表结构」，不含任何业务规则、也不做序列化
（见 docs/coding-standards.md 第 4.1 节）。

数据库路径按以下优先级解析：

1. 调用方显式传入的 ``path``（测试用临时文件走这条）
2. 环境变量 ``CLF_DB_PATH``
3. ``default_db_path()`` —— 开发时是仓库根目录的 ``db.sqlite3``，
   打包成 exe 后是 exe 同级目录（见该函数的说明）
"""

from __future__ import annotations

import os
import sqlite3
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

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
    """建表与建索引（可重复执行）。"""
    conn = connect(path)
    try:
        conn.executescript(SCHEMA)
        conn.commit()
    finally:
        conn.close()
