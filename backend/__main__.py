"""服务端启动入口：``python -m backend``，以及打包后的 exe 都走这里。

与 ``uvicorn backend.main:app --reload`` 的差别：

- **不用 ``--reload``**：它在冻结成 exe 之后无法工作（要 spawn 子进程去监视文件）。
- **启动前确保数据库存在**：不存在（或还是空表）就建表并写入演示数据，
  这样双击 exe 的人不用先去跑一遍 ``python -m backend.seed``。
- **默认自动打开浏览器**：交出去的程序不该让人自己去猜地址。
- 端口被占用之类的问题给出人话提示，而不是一屏 traceback 然后窗口秒退。

打包方式见仓库根目录的 ``build_exe.py``。
"""

from __future__ import annotations

import argparse
import os
import sqlite3
import subprocess
import sys
import threading
import webbrowser
from pathlib import Path

import uvicorn

from . import db, seed
from .main import FRONTEND_DIR, app

DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8000

#: 启动后隔多久去开浏览器。服务器起来需要一点时间，太早打开会看到"无法连接"。
_BROWSER_DELAY_SECONDS = 1.2

#: Chrome 常见的安装位置，按顺序找第一个存在的
_CHROME_PATHS = (
    r"%ProgramFiles%\Google\Chrome\Application\chrome.exe",
    r"%ProgramFiles(x86)%\Google\Chrome\Application\chrome.exe",
    r"%LocalAppData%\Google\Chrome\Application\chrome.exe",
)


def ensure_database(path: str | Path | None = None) -> bool:
    """确保数据库可用：不存在、没建表、或表是空的，就建表并写入演示数据。

    参数：
        path —— 数据库文件位置。省略时按 ``db.resolve_db_path()`` 解析
            （打包成 exe 后是 exe 同级目录，见 ``db.default_db_path()``）。

    返回：``True`` 表示这次做了初始化；``False`` 表示库里已经有数据、什么都没动。

    为什么按"行数"判断而不是"文件在不在"：文件可能是上次半途中断留下的空壳
    （建了表没数据），只判断存在性会让用户面对一个空列表却看不出哪里错了。

    异常：表不存在时会正常补建；但文件本身不是有效的 SQLite（损坏、或被别的
    程序占用写坏）时，播种会抛出 ``sqlite3.DatabaseError``——这里**不静默删除**
    用户的文件，由 ``main()`` 把原因和处置办法讲清楚。
    """
    resolved = db.resolve_db_path(path)

    if Path(resolved).exists():
        try:
            conn = sqlite3.connect(resolved)
            try:
                rows = conn.execute("SELECT COUNT(*) FROM items").fetchone()[0]
            finally:
                conn.close()
            if rows > 0:
                return False
        except sqlite3.Error:
            # 表不存在（老文件、半成品）→ 交给下面的播种补建
            pass

    seed.seed_demo_data(resolved)
    return True


def open_browser(url: str) -> str:
    """打开浏览器访问 url，优先使用 Google Chrome。

    参数：
        url —— 要打开的完整地址。

    返回：实际使用的浏览器，供调用方打印：
        ``'chrome'``  —— 用 Chrome 打开了；
        ``'default'`` —— 没找到 Chrome，退而用系统默认浏览器打开的。

    查找顺序是「已知安装路径 → webbrowser 注册的 chrome → 默认浏览器」：
    前两步覆盖绝大多数情况，最后一步保证"哪怕没装 Chrome 也总得打开个什么"，
    而不是什么都不做让使用者以为程序没反应。
    """
    for pattern in _CHROME_PATHS:
        chrome = Path(os.path.expandvars(pattern))
        if chrome.is_file():
            subprocess.Popen([str(chrome), url])
            return "chrome"

    try:
        webbrowser.get("chrome").open(url)
        return "chrome"
    except (webbrowser.Error, OSError):
        webbrowser.open(url)
        return "default"


def _print_banner(base_url: str, page_url: str, created: bool) -> None:
    """在控制台打出地址等信息，方便使用者知道该开哪个网址。

    参数：
        base_url —— 形如 ``http://127.0.0.1:8000``，不带结尾斜杠。
        page_url —— 首页完整地址（``base_url`` + ``/index.html``）。
        created  —— 本次是否初始化了数据库，用于多打一行提示。
    """
    print("校园失物招领 —— 本地演示服务")
    if created:
        print("  已初始化数据库，写入 8 条演示数据")
    print("  数据库    : %s" % db.resolve_db_path())
    # 前端资源可能来自 exe 同级目录（改页面不用重新打包）或包内，必须让人看得见用的是哪份
    print("  前端资源  : %s" % FRONTEND_DIR)
    print("  首页      : %s" % page_url)
    print("  接口文档  : %s/docs" % base_url)
    print("  按 Ctrl+C 停止")
    print()
    # 立刻刷出去：输出被重定向到文件时 stdout 是块缓冲的，否则这段横幅会跑到
    # uvicorn 的启动日志后面，看起来像是没打印
    sys.stdout.flush()


def main(argv: list[str] | None = None) -> int:
    """解析参数、准备数据库、启动服务，并按需打开浏览器。

    参数：
        argv —— 命令行参数；省略时取 ``sys.argv[1:]``（测试可以显式传入）。

    返回：进程退出码。正常停止（Ctrl+C）返回 0；启动失败返回 1。
    """
    parser = argparse.ArgumentParser(
        prog="campus-lost-found",
        description="校园失物招领本地演示服务",
    )
    parser.add_argument("--host", default=DEFAULT_HOST, help="监听地址，默认 127.0.0.1")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT, help="监听端口，默认 8000")
    parser.add_argument("--no-browser", action="store_true", help="启动后不自动打开浏览器")
    args = parser.parse_args(argv)

    try:
        created = ensure_database()
    except sqlite3.DatabaseError as exc:
        # 数据库文件损坏或不是 SQLite。给出能照做的提示，别丢一屏 traceback。
        print("数据库无法使用：%s" % exc, file=sys.stderr)
        print("文件位置：%s" % db.resolve_db_path(), file=sys.stderr)
        print("如果不需要保留里面的数据，删掉这个文件再启动即可。", file=sys.stderr)
        if getattr(sys, "frozen", False):
            input("按回车键退出…")
        return 1

    # 监听 0.0.0.0 时浏览器不能访问 0.0.0.0，换成回环地址
    host_for_url = "127.0.0.1" if args.host in ("0.0.0.0", "::") else args.host
    base_url = "http://%s:%d" % (host_for_url, args.port)
    page_url = "%s/index.html" % base_url

    _print_banner(base_url, page_url, created)

    if not args.no_browser:
        # uvicorn.run 会阻塞，所以放进延迟线程：等服务器就绪再开，否则会看到"无法连接"
        def _open() -> None:
            if open_browser(page_url) == "default":
                print("未找到 Google Chrome，已改用系统默认浏览器打开。")

        threading.Timer(_BROWSER_DELAY_SECONDS, _open).start()

    try:
        uvicorn.run(app, host=args.host, port=args.port, log_level="info")
    except OSError as exc:
        # 最常见的是端口被占用；直接把原因和下一步说清楚
        print("启动失败：%s" % exc, file=sys.stderr)
        print("端口 %d 可能已被占用，换一个试试：--port 8001" % args.port, file=sys.stderr)
        if getattr(sys, "frozen", False):
            # 双击运行的话窗口会立刻消失，等用户看完再退
            input("按回车键退出…")
        return 1
    except KeyboardInterrupt:
        print("\n已停止")
    return 0


if __name__ == "__main__":
    sys.exit(main())
