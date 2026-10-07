"""把服务端打包成单文件 Windows exe，**产物直接放在仓库根目录**。

用法（在仓库根目录执行，需要已装好开发依赖）::

    .venv/Scripts/python.exe build_exe.py

产物：``./campus-lost-found.exe``（就在项目根目录，双击即可）

双击后的行为：启动后端 → 自动建库（首次）→ 用 **Google Chrome** 打开
``/index.html``。（没装 Chrome 时退回系统默认浏览器，并在控制台说明。）

## exe 与后续代码改动的关系

- **前端改动不需要重新打包**。exe 放在仓库根目录，它启动时会优先使用
  **同级目录的 ``frontend/``**（也就是仓库里那份），改 HTML / CSS / JS 立刻生效。
  包内还打了一份 ``frontend/`` 作为兜底：把 exe 单独拷到别的机器上（旁边没有
  ``frontend/``）时仍然能跑。
- **数据库也不在包里**：``db.sqlite3`` 落在 exe 同级目录，删掉它再双击就是全新一份。
- **后端 Python 代码改动需要重新打包**——代码是编译进 exe 的，这部分无法解耦。
  所以开发时用 ``python -m backend``，交付时才打包。

## 下面这些参数都不是随手写的

- ``--onefile``：单文件交付。代价是每次启动要把内容解压到临时目录，首次慢 2-5 秒；
  部分杀毒软件对单文件 exe 也会格外警惕（误报时选"仍要运行"）。
- ``--console``：保留控制台窗口。使用者需要看到地址、端口和请求日志；
  ``--windowed`` 会把这些全藏起来，出问题只能干瞪眼。
- ``--add-data frontend``：给"把 exe 拷走单独用"准备的兜底副本。
- ``--hidden-import uvicorn.*``：uvicorn 的 loop / protocol / lifespan 是按名字
  **动态导入**的，PyInstaller 的静态分析看不到，漏了会在运行时报 ImportError。
- ``--distpath``：产物落在仓库根目录，而不是默认的 ``dist/``。
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent
ENTRY_SCRIPT = REPO_ROOT / "run_server.py"
APP_NAME = "campus-lost-found"

#: uvicorn 里那些靠名字动态导入、静态分析发现不了的模块
HIDDEN_IMPORTS = (
    "uvicorn.logging",
    "uvicorn.loops.auto",
    "uvicorn.loops.asyncio",
    "uvicorn.protocols.http.auto",
    "uvicorn.protocols.http.h11_impl",
    "uvicorn.protocols.websockets.auto",
    "uvicorn.lifespan.on",
    "uvicorn.lifespan.off",
)


def exe_path() -> Path:
    """产物的完整路径（单独拆出来，方便调用方与测试引用同一处定义）。"""
    return REPO_ROOT / ("%s.exe" % APP_NAME)


def build_args() -> list[str]:
    """组装 PyInstaller 的命令行参数。"""
    return [
        str(ENTRY_SCRIPT),
        "--name", APP_NAME,
        "--onefile",
        "--console",
        "--noconfirm",
        "--clean",
        # 产物直接落到仓库根目录，方便双击；默认的 dist/ 只会多出一份副本
        "--distpath", str(REPO_ROOT),
        # Windows 上 --add-data 的分隔符是 ';'，用 os.pathsep 让脚本在别的平台也能跑
        "--add-data", "frontend%sfrontend" % os.pathsep,
        *[arg for module in HIDDEN_IMPORTS for arg in ("--hidden-import", module)],
    ]


def main() -> int:
    """检查前置条件并执行打包，返回进程退出码。"""
    if not (REPO_ROOT / "frontend" / "index.html").is_file():
        print("找不到 frontend/，请在仓库根目录执行本脚本。", file=sys.stderr)
        return 1

    try:
        import PyInstaller.__main__
    except ImportError:
        print("缺少 PyInstaller，请先安装：pip install -r requirements-dev.txt", file=sys.stderr)
        return 1

    print("开始打包（首次约 30-60 秒）…")
    PyInstaller.__main__.run(build_args())

    target = exe_path()
    if not target.is_file():
        print("打包似乎没有成功，没有找到 %s" % target, file=sys.stderr)
        return 1

    size_mb = target.stat().st_size / 1024 / 1024
    print()
    print("完成：%s（%.1f MB）" % (target, size_mb))
    print()
    print("双击它即可：自动建库 → 启动服务 → 用 Chrome 打开首页。")
    print("它同级目录下的 frontend/ 就是仓库里这份，所以改前端不用重新打包；")
    print("把 exe 单独拷到别的机器上也能跑（用的是包内的那份前端）。")
    print("中间产物 build/ 与 %s.spec 可以删掉。" % APP_NAME)
    return 0


if __name__ == "__main__":
    sys.exit(main())
