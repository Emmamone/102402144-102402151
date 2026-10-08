"""上传模块的纯函数：类型白名单、文件名生成、文件名形状、文件头（魔数）校验。

这些函数是上传接口的第一道防线，而且**不依赖 FastAPI、不碰文件系统**，
所以放在单元层——边界情况（空内容、伪造的 content-type、路径穿越形状）
在这里穷举，比在接口层便宜得多，也更容易看懂失败原因。
"""

from __future__ import annotations

import pytest

from backend import uploads

#: 各类型的真实文件头，用来构造"看起来像真的"的字节
JPEG_HEAD = b"\xff\xd8\xff\xe0" + b"\x00" * 12
PNG_HEAD = b"\x89PNG\r\n\x1a\n" + b"\x00" * 12
WEBP_HEAD = b"RIFF" + b"\x00" * 4 + b"WEBP" + b"\x00" * 8


# --------------------------------------------------------------------------
# 类型白名单
# --------------------------------------------------------------------------
@pytest.mark.parametrize(
    "content_type, extension",
    [("image/jpeg", ".jpg"), ("image/png", ".png"), ("image/webp", ".webp")],
)
def test_支持的类型给出对应扩展名(content_type, extension):
    assert uploads.extension_for(content_type) == extension


@pytest.mark.parametrize(
    "content_type",
    ["image/gif", "image/heic", "text/plain", "application/pdf", "", "image/jpeg2"],
)
def test_不在白名单的类型返回_None(content_type):
    assert uploads.extension_for(content_type) is None


def test_带参数的类型也能识别():
    """有些客户端会发 'image/jpeg; charset=binary'。"""
    assert uploads.extension_for("image/jpeg; charset=binary") == ".jpg"
    assert uploads.extension_for("IMAGE/PNG") == ".png"


# --------------------------------------------------------------------------
# 文件名生成
# --------------------------------------------------------------------------
def test_文件名是随机十六进制加白名单扩展名():
    name = uploads.new_image_filename("image/png")

    assert uploads.is_valid_filename(name)
    assert name.endswith(".png")
    assert len(name) == 32 + len(".png")


def test_两次生成的文件名不同():
    """同名会互相覆盖，所以名字必须随机。"""
    assert uploads.new_image_filename("image/jpeg") != uploads.new_image_filename("image/jpeg")


def test_不支持的类型拒绝生成文件名():
    with pytest.raises(ValueError):
        uploads.new_image_filename("image/gif")


# --------------------------------------------------------------------------
# 文件头（魔数）校验
# --------------------------------------------------------------------------
@pytest.mark.parametrize(
    "content_type, data",
    [("image/jpeg", JPEG_HEAD), ("image/png", PNG_HEAD), ("image/webp", WEBP_HEAD)],
)
def test_魔数相符时判定为图片(content_type, data):
    assert uploads.looks_like_image(content_type, data) is True


def test_内容为空一律不是图片():
    assert uploads.looks_like_image("image/png", b"") is False


def test_魔数与声明类型不符时拒绝():
    """把文本文件标成 image/png 是最典型的绕过手法。"""
    assert uploads.looks_like_image("image/png", "这不是图片，只是文本".encode()) is False
    assert uploads.looks_like_image("image/jpeg", PNG_HEAD) is False


def test_不支持的类型直接判否():
    assert uploads.looks_like_image("image/gif", JPEG_HEAD) is False


def test_webp_要求_RIFF_与_WEBP_两个标记都在():
    """只匹配前 4 字节的话，任何 RIFF 容器（比如 wav）都会被放进来。"""
    not_webp = b"RIFF" + b"\x00" * 4 + b"XXXX" + b"\x00" * 8
    assert uploads.looks_like_image("image/webp", not_webp) is False


# --------------------------------------------------------------------------
# 文件名形状（读取图片时用它挡路径穿越）
# --------------------------------------------------------------------------
@pytest.mark.parametrize(
    "name",
    [
        "../../main.py",           # 路径穿越
        "..\\..\\main.py",         # Windows 分隔符
        "a" * 32 + ".jpg.exe",     # 双扩展名
        "A" * 32 + ".jpg",         # 大写（服务端只生成小写）
        "0123456789abcdef.jpg",    # 长度不对
        "zzzz" * 8 + ".jpg",       # 不是十六进制
        "3f2a" * 8 + ".gif",       # 扩展名不在白名单
        "",
        None,
    ],
)
def test_非法文件名被拒(name):
    assert uploads.is_valid_filename(name) is False


def test_自己生成的文件名一定通过形状校验():
    for content_type in uploads.ALLOWED_IMAGE_TYPES:
        assert uploads.is_valid_filename(uploads.new_image_filename(content_type))


def test_大小上限是_5MB():
    assert uploads.MAX_UPLOAD_BYTES == 5 * 1024 * 1024
