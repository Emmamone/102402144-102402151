"""建表与播种的集成测试（真实 SQLite 文件，但用临时路径）。"""

from __future__ import annotations

import sqlite3

import pytest

import backend.__main__ as main_entry
from backend import db, seed


def _rows(conn):
    return conn.execute("SELECT * FROM items ORDER BY id").fetchall()


def test_播种写入八条固定_id(conn):
    rows = _rows(conn)
    assert [row["id"] for row in rows] == [1, 2, 3, 4, 5, 6, 7, 8]


def test_播种后全部为演示数据(conn):
    assert {row["source"] for row in _rows(conn)} == {"demo"}


def test_首页顺序字段只有前六条有值(conn):
    home = [row["home_order"] for row in _rows(conn)]
    assert home == [1, 2, 3, 4, 5, 6, None, None]


def test_搜索顺序字段覆盖八条(conn):
    assert [row["search_order"] for row in _rows(conn)] == [1, 5, 4, 6, 3, 7, 2, 8]


def test_重复播种幂等(db_path, conn):
    conn.execute("UPDATE items SET name = '被改坏了' WHERE id = 1")
    conn.commit()

    seed.seed_demo_data(db_path)

    assert len(_rows(conn)) == 8
    assert conn.execute("SELECT name FROM items WHERE id = 1").fetchone()["name"] == "校园卡"


def test_重复播种不覆盖用户数据(db_path, conn, make_user_item):
    user_id = make_user_item(name="用户发布物")
    assert user_id == 9, "自增序列应推进到 8，第一条用户数据是 id 9"

    seed.seed_demo_data(db_path)

    row = conn.execute("SELECT * FROM items WHERE id = 9").fetchone()
    assert row is not None
    assert row["name"] == "用户发布物"
    assert row["source"] == "user"


def test_脱敏串不由联系方式推导(conn):
    """1 号的 contact 是微信号，masked 却是手机号形态——两者不同源，必须各自保真。"""
    row = conn.execute("SELECT * FROM items WHERE id = 1").fetchone()
    assert row["contact"] == "微信：zhang_cc2024"
    assert row["masked"] == "138****6621"


def test_卡片描述与详情描述是两段不同文字(conn):
    for row in _rows(conn):
        assert row["card_desc"] != row["desc"]
        assert row["card_desc"] not in row["desc"]


def test_卡片时间文案保持字面量(conn):
    """'今天 08:20' 冻结在演示数据设定的日期，不随真实日期重算。"""
    first = conn.execute("SELECT time_display FROM items WHERE id = 1").fetchone()
    fifth = conn.execute("SELECT time_display FROM items WHERE id = 5").fetchone()
    assert first[0] == "今天 08:20"
    assert fifth[0] == "09-25 12:10"


def test_详情页时间用绝对时间(conn):
    row = conn.execute("SELECT happened_at FROM items WHERE id = 1").fetchone()
    assert row["happened_at"] == "2026-09-27 08:20"


def test_搜索索引逐字保存(conn):
    row = conn.execute("SELECT keywords FROM items WHERE id = 4").fetchone()
    assert row["keywords"] == "耳机 无线耳机 白色 宿舍区 3号楼 寻物 丢了"


# --------------------------------------------------------------------------
# 启动时的自动建库（backend/__main__.py 的 ensure_database）
# 让双击 exe 的人不必先去跑一遍 seed
# --------------------------------------------------------------------------
def _count(path):
    conn = db.connect(path)
    try:
        return conn.execute("SELECT COUNT(*) FROM items").fetchone()[0]
    finally:
        conn.close()


def test_首次运行会自动建库并写入演示数据(tmp_path):
    path = tmp_path / "fresh.sqlite3"
    assert not path.exists()

    assert main_entry.ensure_database(path) is True

    assert _count(path) == 8


def test_库里已有数据时什么都不做(tmp_path):
    path = tmp_path / "fresh.sqlite3"
    main_entry.ensure_database(path)

    assert main_entry.ensure_database(path) is False
    assert _count(path) == 8


def test_表在但没有数据时会补上(tmp_path):
    """上次半途中断留下的空壳：只判断"文件在不在"会让用户看到一个空列表。"""
    path = tmp_path / "empty.sqlite3"
    db.init_db(path)                       # 建了表，一条数据都没有

    assert main_entry.ensure_database(path) is True

    assert _count(path) == 8


def test_数据库文件损坏时抛出明确异常(tmp_path):
    """不静默删用户的文件——抛出 sqlite3.DatabaseError，由 main() 给出处置提示。"""
    path = tmp_path / "broken.sqlite3"
    path.write_text("这不是一个 SQLite 文件", encoding="utf-8")

    with pytest.raises(sqlite3.DatabaseError):
        main_entry.ensure_database(path)
