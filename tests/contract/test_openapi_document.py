"""``docs/openapi.json`` 必须与当前接口保持一致。

这份文件是**产物**：FastAPI 从路由声明与 Pydantic 模型自动生成它，
``export_openapi.py`` 只是把它写下来。手写、或者改了接口忘了重新导出，都会让
文档与实现脱节——而**一份说过时话的接口文档比没有文档更糟**，照着它写的前端
会调错字段。所以这里做一次现场比对。

不一致时的处理：跑一遍 ``python export_openapi.py``，然后连带一起提交。
"""

from __future__ import annotations

import json
import re
from pathlib import Path

from backend.main import app

#: CJK 统一表意文字，用来判断 summary 是不是中文
_CJK = re.compile(r"[一-鿿]")

DOC = Path(__file__).resolve().parent.parent.parent / "docs" / "openapi.json"

#: 业务接口清单。写死是为了防止"某个路由被误设成不出现在文档里"——
#: 比如给某个端点加了 include_in_schema=False，这条会立刻失败。
EXPECTED_PATHS = (
    "/api/items/home",
    "/api/items/search",
    "/api/items/{item_id}",
    "/api/items",
    "/api/items/{item_id}/resolve",
    "/api/uploads",
)


def load_document() -> dict:
    """读出仓库里那份 OpenAPI 文档。"""
    return json.loads(DOC.read_text(encoding="utf-8"))


def test_openapi_文档存在():
    assert DOC.is_file(), "缺少 docs/openapi.json，请执行 python export_openapi.py"


def test_openapi_文档与当前接口完全一致():
    """全量比对：字段、参数、响应码、模型，任何一处改过都会在这里暴露。"""
    assert load_document() == app.openapi(), (
        "docs/openapi.json 已过期——改了接口之后请重新执行 `python export_openapi.py`，"
        "并把生成的文件一起提交"
    )


def test_openapi_包含全部五个业务接口():
    paths = load_document()["paths"]
    for path in EXPECTED_PATHS:
        assert path in paths, "接口文档里缺少 %s" % path


def test_openapi_每个业务接口都有中文说明():
    """summary 默认取函数名（英文），所以路由上都显式写了 summary；这条防止漏写。"""
    paths = load_document()["paths"]
    for path in EXPECTED_PATHS:
        for method, operation in paths[path].items():
            summary = operation.get("summary") or ""
            assert summary, "%s %s 缺少 summary" % (method.upper(), path)
            assert _CJK.search(summary), (
                "%s %s 的 summary 不是中文：%r" % (method.upper(), path, summary)
            )


def test_openapi_用的是_openapi_3():
    assert load_document()["openapi"].startswith("3.")


def test_openapi_描述了请求体与响应模型():
    """发布接口的请求体、以及详情类接口的响应，都应该指向具名模型而不是裸对象。"""
    schemas = load_document()["components"]["schemas"]

    assert "CreateRequest" in schemas, "发布请求体应该有独立的模型"
    assert schemas["CreateRequest"]["properties"]["type"]["enum"] == ["seek", "find"]

    ref = load_document()["paths"]["/api/items"]["post"]["requestBody"]
    assert ref["content"]["application/json"]["schema"]["$ref"].endswith("/CreateRequest")

    detail_ref = load_document()["paths"]["/api/items/{item_id}"]["get"]["responses"]["200"]
    assert detail_ref["content"]["application/json"]["schema"]["$ref"].endswith("/DetailItem")
