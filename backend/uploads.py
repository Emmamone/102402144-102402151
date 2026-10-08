"""上传图片的校验与落盘。

本模块只回答两件事：「这堆字节能不能当图片存下来」和「存到哪个文件名」——
不碰数据库、不碰路由（见 docs/coding-standards.md 第 4.1 节的分层约定）。

安全上有三条硬规矩，都不是可选项：

1. **文件名由服务端生成**（``uuid4().hex`` + 白名单扩展名），绝不采用客户端传来的
   名字。否则 ``../../main.py`` 这类名字就是路径穿越。因为文件名结构固定，
   读取时再用正则白名单卡一道，穿越在结构上不可能发生。
2. **类型走白名单，并且校验文件头（魔数）**。只信 ``Content-Type`` 等于让调用方
   自己声明自己合法——把任意文件标成 ``image/png`` 就能绕过。
3. **大小有上限**。前端会先拦一道（免得用户白等上传），这里是兜底：
   接口可以被绕过前端直接调用。
"""

from __future__ import annotations

import re
import uuid
from pathlib import Path

#: 允许的图片类型 → 落盘扩展名。白名单，不在这张表里的一律拒绝
ALLOWED_IMAGE_TYPES = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
}

#: 单张图片的字节上限。前端选图时也会拦，这里是服务端兜底
MAX_UPLOAD_BYTES = 5 * 1024 * 1024

#: 合法文件名的形状：32 位十六进制 + 白名单扩展名。读取时用它挡路径穿越
FILENAME_RE = re.compile(r"^[0-9a-f]{32}\.(?:jpg|png|webp)$")

#: 各类型的文件头判定。WebP 是 RIFF 容器，要同时看 RIFF 与 WEBP 两个标记
_MAGIC_CHECKS = {
    ".jpg": lambda data: data.startswith(b"\xff\xd8\xff"),
    ".png": lambda data: data.startswith(b"\x89PNG\r\n\x1a\n"),
    ".webp": lambda data: data[:4] == b"RIFF" and data[8:12] == b"WEBP",
}


def extension_for(content_type: str) -> str | None:
    """给出该 MIME 类型对应的扩展名。

    参数：content_type —— 请求声明的 MIME（形如 ``image/jpeg``，
        带 ``;charset=…`` 之类的参数也能处理）。
    返回：``.jpg`` / ``.png`` / ``.webp``；不在白名单里返回 ``None``。
    """
    normalized = (content_type or "").lower().split(";")[0].strip()
    return ALLOWED_IMAGE_TYPES.get(normalized)


def new_image_filename(content_type: str) -> str:
    """为一张新上传的图片生成文件名。

    参数：content_type —— 请求声明的 MIME 类型。
    返回：``<32位十六进制><扩展名>``，例如 ``3f2a…9c.jpg``。
    异常：类型不在白名单里时抛 ``ValueError``。

    用随机名而不是原文件名：既避免同名互相覆盖，也让路径穿越无从下手
    （外部输入完全不参与文件名的构成）。
    """
    extension = extension_for(content_type)
    if extension is None:
        raise ValueError("不支持的图片类型")
    return uuid.uuid4().hex + extension


def looks_like_image(content_type: str, data: bytes) -> bool:
    """按文件头判断这堆字节是不是它声称的那种图片。

    参数：
        content_type —— 请求声明的 MIME 类型。
        data —— 文件内容。
    返回：True 表示魔数与声明的类型相符；空内容、类型不支持、魔数不符都返回 False。
    """
    extension = extension_for(content_type)
    check = _MAGIC_CHECKS.get(extension) if extension else None
    return bool(data) and check is not None and check(data)


def is_valid_filename(filename: str) -> bool:
    """文件名是否是本模块生成的那种形状（读取图片时用来挡路径穿越）。"""
    return bool(FILENAME_RE.match(filename or ""))


def save_image(data: bytes, content_type: str, uploads_dir: Path) -> str:
    """把图片写进上传目录，返回刚生成的文件名。

    参数：
        data —— 文件内容。调用方应先用 ``looks_like_image`` 与大小校验筛过。
        content_type —— 请求声明的 MIME 类型（决定扩展名）。
        uploads_dir —— 上传目录，调用方需保证它存在
            （用 ``db.ensure_uploads_dir()``）。
    返回：写入的文件名。

    约束：目录不存在时 ``write_bytes`` 会抛 ``FileNotFoundError``——
    这是有意的，不让"随手写到一个不存在的地方"默默成功。
    """
    filename = new_image_filename(content_type)
    (Path(uploads_dir) / filename).write_bytes(data)
    return filename
