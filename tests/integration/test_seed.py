"""建表与播种的集成测试（真实 SQLite 文件，但用临时路径）。"""

from __future__ import annotations

from backend import seed


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
