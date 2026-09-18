from __future__ import annotations

import base64
import binascii

from stnp_editor.errors import LoadingError


def decode_base64_content(content: str, *, owner: str = "base64 content") -> bytes:
    """Decode Base64 strictly while allowing insignificant whitespace.

    解码失败按错误码注册表映射为加载期 ``E1004``（嵌入文件 Base64 内容无效）；
    ``owner`` 用于指认具体嵌入文件。不再抛裸 ``ValueError``。
    """
    normalized = "".join(content.split())
    try:
        return base64.b64decode(normalized, validate=True)
    except (binascii.Error, ValueError) as exc:
        raise LoadingError("E1004", message=f"嵌入文件 Base64 内容无效: {owner}") from exc
