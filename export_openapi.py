"""把服务端的接口定义导出成 OpenAPI 文档（``docs/openapi.json``）。

用法（仓库根目录）::

    .venv/Scripts/python.exe export_openapi.py

**为什么是"导出"而不是"手写"**：FastAPI 会从路由声明与 Pydantic 模型**自动生成**
OpenAPI 文档（运行时挂在 ``/openapi.json``，``/docs`` 那个交互页面也是它渲染的）。
所以 ``docs/openapi.json`` 是**产物**——想改接口描述，改的是代码里的 docstring、
``schemas.py`` 的模型字段、以及路由参数，然后重新导出，**不要直接编辑那个 JSON**。

**防过期**：``tests/contract/test_openapi_document.py`` 会拿仓库里这份文件与
``app.openapi()`` 现场生成的做全量比对，不一致就失败。改了接口忘了导出，CI 会挡住。

导出的两处格式选择：

- ``indent=2``：便于人读、也让 git diff 一次只动几行；
- ``ensure_ascii=False``：中文注释（接口与字段的说明都来自 docstring）保持原样，
  否则会变成一堆 ``\\uXXXX`` 转义，diff 完全没法看。
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent
OUTPUT = REPO_ROOT / "docs" / "openapi.json"


def render_spec() -> str:
    """把当前应用的 OpenAPI 文档渲染成要写入文件的文本。

    返回：格式化后的 JSON 字符串，末尾带一个换行（文件以换行结尾才符合常规）。
    """
    from backend.main import app

    return json.dumps(app.openapi(), indent=2, ensure_ascii=False) + "\n"


def main() -> int:
    """写出 ``docs/openapi.json``，返回进程退出码。

    返回：0 表示成功（没有什么失败路径——导出不会调数据库，也不需要起服务）。
    """
    text = render_spec()
    OUTPUT.write_text(text, encoding="utf-8")

    size_kb = len(text.encode("utf-8")) / 1024
    print("已写出 %s（%.1f KB）" % (OUTPUT.relative_to(REPO_ROOT), size_kb))
    print("提示：这份文件由代码生成，不要直接改它；改完接口跑一遍本脚本即可。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
