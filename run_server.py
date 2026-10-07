"""打包入口脚本（PyInstaller 的起点）。

为什么需要这么一层转接：PyInstaller 要求入口是一个**顶层脚本**，而
`backend/__main__.py` 是包内模块、用的是相对导入，直接拿它当入口会让
`from . import db` 之类的导入失效。

这里只做一件事——把真正的 main 取出来执行；所有逻辑都在
`backend/__main__.py` 里，所以开发时 `python -m backend` 和打包后的 exe
跑的是同一份代码，不会出现"exe 行为和开发时不一样"。
"""

from backend.__main__ import main

if __name__ == "__main__":
    raise SystemExit(main())
