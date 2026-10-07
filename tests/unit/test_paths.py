"""路径解析：数据库位置与前端资源目录，含"冻结成 exe 之后会变成什么"。

打包环境本身没法在测试里跑（要真的构建一次 exe），所以用 monkeypatch 模拟
``sys.frozen`` / ``sys.executable`` / ``sys._MEIPASS``，把各个分支单独测出来——
这正是最容易被改坏、又在开发时看不出来的地方：开发时路径永远对，一打包
数据就丢、或者页面全 404。
"""

from __future__ import annotations

import sys

from backend import db
from backend import main as backend_main


def test_开发时数据库在仓库根目录(monkeypatch):
    monkeypatch.delattr(sys, "frozen", raising=False)
    monkeypatch.delenv("CLF_DB_PATH", raising=False)
    assert db.default_db_path() == db.REPO_ROOT / "db.sqlite3"


def test_打包后数据库落在_exe_同级目录(monkeypatch, tmp_path):
    """冻结环境下 __file__ 指向临时解压目录，退出即删——不能拿它推数据库位置。"""
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "executable", str(tmp_path / "campus-lost-found.exe"))
    monkeypatch.delenv("CLF_DB_PATH", raising=False)

    assert db.default_db_path().resolve() == (tmp_path / "db.sqlite3").resolve()


def test_显式入参优先于环境变量与默认路径(monkeypatch, tmp_path):
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setenv("CLF_DB_PATH", str(tmp_path / "from-env.sqlite3"))

    explicit = tmp_path / "custom.sqlite3"
    assert db.resolve_db_path(explicit) == explicit


def test_环境变量优先于默认路径(monkeypatch, tmp_path):
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setenv("CLF_DB_PATH", str(tmp_path / "from-env.sqlite3"))

    assert db.resolve_db_path() == tmp_path / "from-env.sqlite3"


def test_冻结时不会把数据库放进临时解压目录(monkeypatch, tmp_path):
    """回归保护：曾经写成 __file__ 往上两级，打包后数据库会落在 _MEIPASS 里。"""
    meipass = tmp_path / "_MEI123456"
    meipass.mkdir()
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "_MEIPASS", str(meipass), raising=False)
    monkeypatch.setattr(sys, "executable", str(tmp_path / "campus-lost-found.exe"))
    monkeypatch.delenv("CLF_DB_PATH", raising=False)

    assert not str(db.default_db_path()).startswith(str(meipass))


# --------------------------------------------------------------------------
# 前端资源目录（main._frontend_dir）
# 这里的第一条测试就是"改前端不用重新打包 exe"的实现基础
# --------------------------------------------------------------------------
def test_开发时用仓库里的前端目录(monkeypatch):
    monkeypatch.delattr(sys, "frozen", raising=False)
    monkeypatch.delenv("CLF_FRONTEND_DIR", raising=False)

    assert backend_main._frontend_dir() == db.REPO_ROOT / "frontend"


def test_打包后优先用_exe_同级的前端目录(monkeypatch, tmp_path):
    """exe 旁边有 frontend/ 就用它——于是替换该文件夹即可生效，无需重新打包。"""
    beside = tmp_path / "frontend"
    beside.mkdir()
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "executable", str(tmp_path / "campus-lost-found.exe"))
    monkeypatch.delenv("CLF_FRONTEND_DIR", raising=False)

    assert backend_main._frontend_dir().resolve() == beside.resolve()


def test_exe_旁边没有前端目录时退回包内那份(monkeypatch, tmp_path):
    """把 exe 单独拷到别的机器上也得能跑，所以包里留了一份兜底。"""
    bundle = tmp_path / "_MEI123456"
    (bundle / "frontend").mkdir(parents=True)
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "_MEIPASS", str(bundle), raising=False)
    monkeypatch.setattr(sys, "executable", str(tmp_path / "campus-lost-found.exe"))
    monkeypatch.delenv("CLF_FRONTEND_DIR", raising=False)

    assert backend_main._frontend_dir().resolve() == (bundle / "frontend").resolve()


def test_环境变量可以临时指定前端目录(monkeypatch, tmp_path):
    monkeypatch.setenv("CLF_FRONTEND_DIR", str(tmp_path / "elsewhere"))

    assert backend_main._frontend_dir() == tmp_path / "elsewhere"
