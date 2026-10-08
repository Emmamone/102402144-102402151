"""测试层公共 fixture。

两个硬性约束（见 docs/coding-standards.md 第 3.3 节）：

1. **一律使用临时数据库**——每个测试拿到自己的 ``tmp_path`` 下的 SQLite 文件，
   绝不连仓库里的 ``db.sqlite3``，跑测试不会污染演示数据。
2. **每个测试自己准备数据**——不依赖"另一个测试先跑过"，测试之间没有顺序依赖。
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    # 让测试可以 `import backend`，不额外配置 pythonpath
    sys.path.insert(0, str(REPO_ROOT))

from backend import db, main, seed  # noqa: E402


@pytest.fixture(autouse=True)
def uploads_dir(tmp_path, monkeypatch) -> Path:
    """把上传目录指到临时目录——**任何测试都不许往仓库里写图片**。

    自动生效（autouse）：漏加这个 fixture 的测试会悄悄把文件写进仓库的 uploads/，
    而这种污染不会有任何报错提示，只会让下次 `git status` 多出一堆没用的图。
    需要断言文件内容的测试可以直接把这个 fixture 当参数拿到路径。
    """
    target = tmp_path / "uploads"
    monkeypatch.setenv("CLF_UPLOADS_DIR", str(target))
    return target


@pytest.fixture
def db_path(tmp_path) -> Path:
    """一个建好表、播好演示数据的临时数据库文件。"""
    path = tmp_path / "test.sqlite3"
    seed.seed_demo_data(path)
    return path


@pytest.fixture
def conn(db_path):
    connection = db.connect(db_path)
    try:
        yield connection
    finally:
        connection.close()


@pytest.fixture
def client(db_path):
    """接上临时数据库的 TestClient（通过覆盖依赖，不改全局状态）。"""

    def override():
        connection = db.connect(db_path)
        try:
            yield connection
        finally:
            connection.close()

    main.app.dependency_overrides[main.get_conn] = override
    try:
        with TestClient(main.app) as test_client:
            yield test_client
    finally:
        main.app.dependency_overrides.clear()


@pytest.fixture
def create_payload():
    """一份合法的发布请求体，供写路径的集成测试与契约测试共用。

    单独放这里是为了只定义一次——两处测试各抄一份的话，改动字段时容易只改一边。
    """
    return {
        "name": "测试水杯",
        "type": "find",
        "category": "水杯",
        "time": "2026-10-07 15:30",
        "place": "第二食堂一楼",
        "desc": "蓝色保温杯，杯盖有小熊图案。",
        "contact": "13800001234",
    }


@pytest.fixture
def make_user_item(conn):
    """插入一条"用户新发布"的数据，返回其 id。

    ``source='user'`` 且 ``home_order``/``search_order`` 均为 NULL —— 这正是
    用户新发布数据的特征，用它验证排序规则。
    """

    def _make(**overrides):
        row = {
            "name": "测试物品",
            "type": "seek",
            "status": "seeking",
            "category": "其他",
            "icon": "mdi:help-circle-outline",
            "card_desc": "测试用的卡片描述。",
            "desc": "测试用的完整描述。",
            "happened_at": "2026-10-07 09:00",
            "time_display": None,
            "place": "测试地点",
            "published_at": "2026-10-07 09:05",
            "publisher": "我（本机发布）",
            "avatar": "我",
            "masked": "138****1234",
            "contact": "13800001234",
            "keywords": "测试物品 其他 测试地点 测试用的完整描述。 寻物 丢了",
            "source": "user",
            "home_order": None,
            "search_order": None,
        }
        row.update(overrides)
        columns = ", ".join(row)
        marks = ", ".join("?" for _ in row)
        with conn:
            cursor = conn.execute(
                "INSERT INTO items (%s) VALUES (%s)" % (columns, marks),
                tuple(row.values()),
            )
        return cursor.lastrowid

    return _make
