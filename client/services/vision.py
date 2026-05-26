import json
import logging

import httpx

from config import settings

logger = logging.getLogger(__name__)

RECOGNIZE_PROMPT = """请识别这张图片中的食材，返回 JSON 格式：
{"category": "食材名称", "confidence": 0.95}
只返回 JSON，不要其他文字。"""


def recognize_food(image_base64: str) -> dict:
    """
    调用视觉大模型 API 识别食材。
    返回: {"category": "西红柿", "confidence": 0.92}
    识别失败时返回: {"category": "unknown", "confidence": 0.0}
    """
    if not settings.VISION_API_KEY or not settings.VISION_API_URL:
        logger.warning("[Vision] API 未配置，跳过识别")
        return {"category": "unknown", "confidence": 0.0}

    logger.info(f"[Vision] 发起识别 | model={settings.VISION_MODEL} | image_len={len(image_base64)}")
    try:
        resp = httpx.post(
            settings.VISION_API_URL,
            headers={"Authorization": f"Bearer {settings.VISION_API_KEY}"},
            json={
                "model": settings.VISION_MODEL,
                "messages": [
                    {
                        "role": "user",
                        "content": [
                            {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{image_base64}"}},
                            {"type": "text", "text": RECOGNIZE_PROMPT},
                        ],
                    }
                ],
            },
            timeout=30.0,
        )
        resp.raise_for_status()
        content = resp.json()["choices"][0]["message"]["content"]
        logger.info(f"[Vision] 识别原始返回 | content={content[:300]}")
        result = json.loads(content.strip().strip("```json").strip("```").strip())
        recognized = {"category": result.get("category", "unknown"), "confidence": result.get("confidence", 0.0)}
        logger.info(f"[Vision] 识别完成 | category={recognized['category']} | confidence={recognized['confidence']}")
        return recognized
    except Exception as e:
        logger.error(f"[Vision] 识别失败 | error={e}")
        return {"category": "unknown", "confidence": 0.0}
