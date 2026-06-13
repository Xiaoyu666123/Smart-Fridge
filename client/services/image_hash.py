"""图片字节级哈希工具。

用 SHA256 对图片二进制取摘要，作为完全相同图片的兜底去重手段。
向量相似度只能识别"看起来很像"的物品，对于完全相同的图片字节，
hash 是 O(1) 级的等值匹配，比向量更稳。
"""

import base64
import hashlib
import logging
from typing import Optional

from config import settings
from services.upload_security import resolve_upload_path

logger = logging.getLogger(__name__)


def compute_image_hash(image_source: Optional[str]) -> Optional[str]:
    """根据 base64 字符串或文件路径计算 SHA256 摘要。

    image_source:
      - base64 字符串（不含 data: 前缀）
      - 本地文件路径
    返回 64 位十六进制 SHA256，失败返回 None。
    """
    if not image_source:
        return None

    raw = None
    # 简易判别：长字符串视为 base64
    if len(image_source) > 200 and "/" not in image_source[:10]:
        if len(image_source) > settings.MAX_BASE64_IMAGE_CHARS:
            logger.warning("[ImageHash] base64 超过大小限制")
            return None
        try:
            raw = base64.b64decode(image_source, validate=True)
        except Exception as e:
            logger.warning(f"[ImageHash] base64 解码失败 | error={e}")
            return None
    else:
        path = resolve_upload_path(image_source)
        if not path:
            logger.warning("[ImageHash] 拒绝读取 uploads 目录之外的路径")
            return None
        try:
            with open(path, "rb") as f:
                raw = f.read(settings.MAX_IMAGE_BYTES + 1)
            if len(raw) > settings.MAX_IMAGE_BYTES:
                logger.warning(f"[ImageHash] 文件超过大小限制 | path={path}")
                return None
        except Exception as e:
            logger.warning(f"[ImageHash] 文件读取失败 | path={path} | error={e}")
            return None

    if not raw:
        return None
    return hashlib.sha256(raw).hexdigest()
