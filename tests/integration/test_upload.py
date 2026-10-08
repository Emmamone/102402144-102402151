"""上传接口（``POST /api/uploads``）与图片读取接口（``GET /uploads/{filename}``）。

对应新增需求「发布页要能上传图片」。重点盯三件事：

1. 上传成功能拿到文件名，并且**文件真的落在上传目录里**；
2. **存下来的图片能通过 HTTP 取回**——这条同时证明"上传"与"读取"用的是同一个目录
   （它们各自解析路径，不一致的话这里就会 404）；
3. 各类非法输入都被拒（类型、空内容、超限、伪造的文件头）。

上传目录由 conftest 的 autouse fixture ``uploads_dir`` 指到临时目录，
所以跑测试不会往仓库里写图片。
"""

from __future__ import annotations

import pytest

from backend import uploads

UPLOAD = "/api/uploads"

#: 够过魔数校验的最小字节；内容本身无所谓（服务端不解码图片）
JPEG_BYTES = b"\xff\xd8\xff\xe0" + b"\x00" * 32
PNG_BYTES = b"\x89PNG\r\n\x1a\n" + b"\x00" * 32
WEBP_BYTES = b"RIFF" + b"\x00" * 4 + b"WEBP" + b"\x00" * 8
BY_TYPE = {"image/jpeg": JPEG_BYTES, "image/png": PNG_BYTES, "image/webp": WEBP_BYTES}


def post_image(client, data=JPEG_BYTES, content_type="image/jpeg", filename="photo.jpg"):
    """发一个 multipart 上传请求（模拟浏览器的 FormData）。"""
    return client.post(UPLOAD, files={"file": (filename, data, content_type)})


# --------------------------------------------------------------------------
# 正常路径
# --------------------------------------------------------------------------
def test_上传成功返回文件名与地址(client):
    response = post_image(client)

    assert response.status_code == 201
    body = response.json()
    assert set(body) == {"filename", "url"}
    assert uploads.is_valid_filename(body["filename"])
    assert body["url"] == "/uploads/" + body["filename"]


def test_上传的文件真的落在上传目录里(client, uploads_dir):
    body = post_image(client).json()

    written = uploads_dir / body["filename"]
    assert written.is_file()
    assert written.read_bytes() == JPEG_BYTES


def test_存下来的图片能通过_HTTP_取回(client):
    """两个接口必须共用同一个目录——不一致的话这里会 404。"""
    body = post_image(client, data=PNG_BYTES, content_type="image/png").json()

    response = client.get(body["url"])

    assert response.status_code == 200
    assert response.content == PNG_BYTES


def test_上传的字节原样保存(client, uploads_dir):
    """服务端不做任何图片处理（没有 Pillow），字节应当一模一样。"""
    data = JPEG_BYTES + b"extra-payload"
    body = post_image(client, data=data).json()

    assert (uploads_dir / body["filename"]).read_bytes() == data


@pytest.mark.parametrize("content_type, extension", [
    ("image/jpeg", ".jpg"), ("image/png", ".png"), ("image/webp", ".webp"),
])
def test_三种类型都能上传(client, content_type, extension):
    body = post_image(client, data=BY_TYPE[content_type], content_type=content_type).json()

    assert body["filename"].endswith(extension)


def test_每次都生成不同的文件名(client):
    first = post_image(client).json()["filename"]
    second = post_image(client).json()["filename"]

    assert first != second


def test_客户端传的文件名不被采用(client, uploads_dir):
    """文件名一律由服务端生成——不然客户端就能决定写到哪里。"""
    body = post_image(client, filename="../../evil.jpg").json()

    assert (uploads_dir / body["filename"]).is_file()
    assert "evil" not in body["filename"]


# --------------------------------------------------------------------------
# 拒绝路径
# --------------------------------------------------------------------------
def test_不支持的类型被拒(client):
    response = post_image(client, content_type="image/gif")

    assert response.status_code == 400
    assert response.json() == {"code": "invalid_image", "message": "仅支持 JPG / PNG / WebP 图片"}


def test_空文件被拒(client):
    response = post_image(client, data=b"")

    assert response.status_code == 400
    assert response.json() == {"code": "invalid_image", "message": "图片内容为空"}


def test_超过上限被拒(client, monkeypatch):
    """把上限临时改小，免得真造一个 5MB 的请求体。"""
    monkeypatch.setattr(uploads, "MAX_UPLOAD_BYTES", 16)

    response = post_image(client, data=JPEG_BYTES + b"x" * 64)

    assert response.status_code == 400
    assert response.json()["code"] == "invalid_image"
    assert "0MB" in response.json()["message"] or "不能超过" in response.json()["message"]


def test_魔数不符被拒(client):
    """文本冒充 PNG —— 只信 content-type 的接口会放它过去。"""
    response = post_image(client, data="这不是图片".encode(), content_type="image/png")

    assert response.status_code == 400
    assert response.json() == {"code": "invalid_image", "message": "文件内容不是有效的图片"}


def test_不带文件返回_422(client):
    """字段缺失属于请求形状问题，交给 FastAPI/Pydantic 的 422。"""
    assert client.post(UPLOAD).status_code == 422


def test_被拒时不留下文件(client, uploads_dir):
    post_image(client, data=b"not an image", content_type="image/png")

    assert not uploads_dir.exists() or not list(uploads_dir.iterdir())


# --------------------------------------------------------------------------
# 读取接口
# --------------------------------------------------------------------------
def test_读取不存在的图片返回_404(client):
    response = client.get("/uploads/" + "a" * 32 + ".jpg")

    assert response.status_code == 404
    assert response.json() == {"code": "not_found", "message": "图片不存在"}


@pytest.mark.parametrize("name", ["main.py", "abc.jpg", "3f2a" * 8 + ".gif"])
def test_文件名形状不对的一律_404(client, name):
    """路径穿越在单元层已穷举（test_uploads.py）；这里确认接口层也不放行。"""
    assert client.get("/uploads/" + name).status_code == 404
