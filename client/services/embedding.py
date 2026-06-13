"""图片向量提取服务 — 调用 DashScope multimodal-embedding-v1"""

import base64
import logging
from typing import Optional

import dashscope
from dashscope import MultiModalEmbedding

from config import settings
from services.upload_security import resolve_upload_path

logger = logging.getLogger(__name__)

SIMILARITY_THRESHOLD = 0.90


def extract_image_vector(image_source: str) -> Optional[list[float]]:
    """
    提取图片的 1024 维向量。
    image_source: base64 字符串（不含前缀）或本地文件路径
    返回: 1024 维浮点列表，失败返回 None
    """
    if not settings.VISION_API_KEY:
        logger.warning("[Embedding] API KEY 未配置，跳过向量提取")
        return None

    dashscope.api_key = settings.VISION_API_KEY

    # 判断是 base64 还是文件路径
    if len(image_source) > 200 and '/' not in image_source[:10]:
        if len(image_source) > settings.MAX_BASE64_IMAGE_CHARS:
            logger.warning("[Embedding] base64 超过大小限制，跳过向量提取")
            return None
        # 大概率是 base64 数据
        image_url = f"data:image/jpeg;base64,{image_source}"
        logger.info(f"[Embedding] 识别为 base64 数据 | len={len(image_source)}")
    else:
        # 文件路径
        filepath = resolve_upload_path(image_source)
        if not filepath:
            logger.warning("[Embedding] 拒绝读取 uploads 目录之外的路径")
            return None
        logger.info(f"[Embedding] 识别为文件路径 | raw={image_source} | normalized={filepath}")
        try:
            with open(filepath, "rb") as f:
                raw = f.read(settings.MAX_IMAGE_BYTES + 1)
            if len(raw) > settings.MAX_IMAGE_BYTES:
                logger.warning(f"[Embedding] 文件超过大小限制 | path={filepath}")
                return None
            b64 = base64.b64encode(raw).decode()
            image_url = f"data:image/jpeg;base64,{b64}"
            logger.info(f"[Embedding] 文件读取成功 | base64_len={len(b64)}")
        except Exception as e:
            logger.error(f"[Embedding] 读取图片文件失败 | path={filepath} | error={e}")
            return None

    logger.info(f"[Embedding] 发起向量提取 | image_len={len(image_url)}")
    from services.usage import track_usage as _track
    import time as _time
    t0 = _time.time()
    status = "SUCCESS"
    try:
        result = MultiModalEmbedding.call(
            model="multimodal-embedding-v1",
            input=[{"image": image_url}],
            dimension=1024,
        )
        if result.status_code == 200:
            embedding = result.output["embeddings"][0]["embedding"]
            embedding = [float(x) for x in embedding]
            logger.info(f"[Embedding] 向量提取成功 | dim={len(embedding)}")
            return embedding
        else:
            status = "FAILED"
            logger.error(f"[Embedding] 向量提取失败 | code={result.code} | msg={result.message}")
            return None
    except Exception as e:
        status = "FAILED"
        logger.error(f"[Embedding] 向量提取异常 | error={e}")
        return None
    finally:
        # multimodal-embedding 不返回 token 数；按"1 次调用"占位（用 1 token 表示发生过）
        # PRICING 表里这个模型也是按调用次数估算
        _track(
            provider="embedding",
            model="multimodal-embedding-v1",
            endpoint="image_vector",
            prompt_tokens=1,
            completion_tokens=0,
            duration_ms=int((_time.time() - t0) * 1000),
            status=status,
        )
