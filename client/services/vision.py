import json
import logging
from typing import Optional

import httpx

from config import settings

logger = logging.getLogger(__name__)

RECOGNIZE_PROMPT = """请识别这张图片中的食材，返回 JSON 格式：
{"category": "英文食材名称", "confidence": 0.95}
要求：
1. category 必须是英文，如 apple, banana, tomato, egg, milk, beef, carrot, onion, potato, chicken, fish, rice, bread, cheese, butter, yogurt, orange, grape, strawberry, watermelon, cucumber, pepper, mushroom, corn, celery, garlic, ginger, lemon, pork, shrimp, tofu, cabbage, lettuce, broccoli, pea, bean, eggplant, zucchini, pumpkin, pear, peach, cherry, kiwi, mango, pineapple, coconut, spinach, radish
2. 只返回 JSON，不要其他文字。"""


def recognize_food(image_base64: str, user_id: Optional[str] = None) -> dict:
    """
    调用视觉大模型 API 识别食材。
    返回: {"category": "西红柿", "confidence": 0.92}
    识别失败时返回: {"category": "unknown", "confidence": 0.0}
    """
    from services.usage import track_usage as _track
    import time as _time

    if not settings.VISION_API_KEY or not settings.VISION_API_URL:
        logger.warning("[Vision] API 未配置，跳过识别")
        return {"category": "unknown", "confidence": 0.0}

    logger.info(f"[Vision] 发起识别 | model={settings.VISION_MODEL} | image_len={len(image_base64)}")
    t0 = _time.time()
    pt = ct = 0
    status = "SUCCESS"
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
        body = resp.json()
        content = body["choices"][0]["message"]["content"]
        u = body.get("usage") or {}
        pt = u.get("prompt_tokens", 0)
        ct = u.get("completion_tokens", 0)
        logger.info(f"[Vision] 识别原始返回 | content={content[:300]}")
        result = json.loads(content.strip().strip("```json").strip("```").strip())
        recognized = {"category": result.get("category", "unknown"), "confidence": result.get("confidence", 0.0)}
        logger.info(f"[Vision] 识别完成 | category={recognized['category']} | confidence={recognized['confidence']}")
        return recognized
    except Exception as e:
        status = "FAILED"
        logger.error(f"[Vision] 识别失败 | error={e}")
        return {"category": "unknown", "confidence": 0.0}
    finally:
        _track(
            provider="vision",
            model=settings.VISION_MODEL,
            endpoint="recognize",
            user_id=user_id,
            prompt_tokens=pt,
            completion_tokens=ct,
            duration_ms=int((_time.time() - t0) * 1000),
            status=status,
        )


DETECT_PROMPT = """请识别图片中所有食材，并给出每个食材的位置框。
图片左上角为原点 (0,0)，向右 x 增大，向下 y 增大。

返回 JSON 数组：
[{"category": "英文食材名", "confidence": 0.95, "bbox": [x, y, w, h]}, ...]

规则：
1. category 必须是英文常见食材名（如 apple, tomato, egg, milk, beef, carrot, onion 等）
2. bbox 用相对坐标，范围 [0, 1]，[x, y, w, h] 中 x/y 是左上角，w/h 是宽高
3. 同种食材若有多个明显个体，分别返回多条记录
4. 不识别非食材物体（容器、餐具等）
5. 只返回 JSON 数组，不要其他文字"""


def detect_foods(image_base64: str, user_id: Optional[str] = None) -> list[dict]:
    """整柜批量识别：调用视觉大模型识别图片中所有食材。

    返回 list[{"category": str, "confidence": float, "bbox": [x, y, w, h]}]
    bbox 是相对坐标 [0, 1]
    """
    from services.usage import track_usage as _track
    import time as _time

    if not settings.VISION_API_KEY or not settings.VISION_API_URL:
        logger.warning("[Vision] API 未配置，跳过批量识别")
        return []

    logger.info(f"[Vision] 发起批量识别 | model={settings.VISION_MODEL} | image_len={len(image_base64)}")
    t0 = _time.time()
    pt = ct = 0
    status = "SUCCESS"
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
                            {"type": "text", "text": DETECT_PROMPT},
                        ],
                    }
                ],
            },
            timeout=60.0,
        )
        resp.raise_for_status()
        body = resp.json()
        content = body["choices"][0]["message"]["content"]
        u = body.get("usage") or {}
        pt = u.get("prompt_tokens", 0)
        ct = u.get("completion_tokens", 0)
        logger.info(f"[Vision] 批量识别原始返回 | content={content[:500]}")
        cleaned = content.strip().strip("```json").strip("```").strip()
        result = json.loads(cleaned)
        if not isinstance(result, list):
            logger.warning("[Vision] 批量识别返回非数组，已忽略")
            return []
        # 规范化字段
        normalized = []
        for r in result:
            cat = r.get("category", "unknown")
            conf = float(r.get("confidence", 0.0))
            bbox = r.get("bbox") or [0, 0, 0, 0]
            if isinstance(bbox, list) and len(bbox) == 4:
                normalized.append({
                    "category": cat,
                    "confidence": conf,
                    "bbox": [float(x) for x in bbox],
                })
        logger.info(f"[Vision] 批量识别完成 | 个体数={len(normalized)}")
        return normalized
    except Exception as e:
        status = "FAILED"
        logger.error(f"[Vision] 批量识别失败 | error={e}")
        return []
    finally:
        _track(
            provider="vision",
            model=settings.VISION_MODEL,
            endpoint="detect",
            user_id=user_id,
            prompt_tokens=pt,
            completion_tokens=ct,
            duration_ms=int((_time.time() - t0) * 1000),
            status=status,
        )
