"""食品标签 OCR + 结构化解析。

一次 vision API 调用同时完成 OCR 和结构化提取，避免两次往返。
模型沿用 settings.VISION_API_URL / VISION_MODEL（qwen-vl-flash 即可胜任）。
"""

import json
import logging
from typing import Optional

import httpx

from config import settings

logger = logging.getLogger(__name__)


LABEL_PROMPT = """你是一个食品标签信息提取助手。请识别这张食品包装/标签的图片，把内容整理成 JSON。

返回字段（缺失就用空字符串或空值）：
{
  "label_text": "图中能看到的所有文字（按合理顺序拼接，保留换行符）",
  "brand": "品牌名（如 伊利、蒙牛、农夫山泉）",
  "product_name": "产品名（如 纯牛奶、原味酸奶）",
  "manufacture_date": "生产日期 YYYY-MM-DD（找不到就空字符串）",
  "expire_date": "保质期截止日期 YYYY-MM-DD（找不到就空字符串）",
  "shelf_life_days": 保质期天数 整数（如标签写"保质期 12 个月"则换算成 365；找不到就 0）,
  "net_weight": "净含量（如 250ml、500g）",
  "ingredients": "配料表（一段文字）",
  "storage": "储存条件（如 冷藏 0~4℃）"
}

规则：
1. 只返回 JSON，不要附加说明、Markdown 代码块或注释。
2. 中文字段保留中文，日期统一格式化为 YYYY-MM-DD。
3. 若 expire_date 没直接给但有 manufacture_date + shelf_life_days，请自行计算 expire_date。
4. 若图中无标签或完全模糊，返回所有字段为空字符串和 0。"""


def parse_label(image_base64: str) -> dict:
    """传入标签图 base64，返回结构化解析结果。

    返回 dict 至少包含:
      label_text (str), brand (str), product_name (str),
      manufacture_date (str), expire_date (str),
      shelf_life_days (int), net_weight (str),
      ingredients (str), storage (str)

    出错或 API 未配置时返回所有字段为空的兜底字典。
    """
    empty = {
        "label_text": "",
        "brand": "",
        "product_name": "",
        "manufacture_date": "",
        "expire_date": "",
        "shelf_life_days": 0,
        "net_weight": "",
        "ingredients": "",
        "storage": "",
    }

    if not settings.VISION_API_KEY or not settings.VISION_API_URL:
        logger.warning("[LabelParser] Vision API 未配置，返回空结果")
        return empty
    if not image_base64:
        return empty

    logger.info(f"[LabelParser] 发起标签解析 | image_len={len(image_base64)}")
    from services.usage import track_usage as _track
    import time as _time
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
                            {
                                "type": "image_url",
                                "image_url": {"url": f"data:image/jpeg;base64,{image_base64}"},
                            },
                            {"type": "text", "text": LABEL_PROMPT},
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
        logger.info(f"[LabelParser] 原始返回 | {content[:300]}")

        cleaned = content.strip()
        # 兜底剥掉 ```json 或 ``` 包裹
        if cleaned.startswith("```"):
            cleaned = cleaned.strip("`")
            if cleaned.lower().startswith("json"):
                cleaned = cleaned[4:].strip()
        result = json.loads(cleaned)
        # 字段补齐 + 类型矫正
        out = {**empty}
        for k in empty.keys():
            v = result.get(k, empty[k])
            if k == "shelf_life_days":
                try:
                    out[k] = int(v) if v else 0
                except Exception:
                    out[k] = 0
            else:
                out[k] = str(v) if v is not None else ""
        logger.info(
            f"[LabelParser] 解析完成 | brand={out['brand']} | "
            f"product={out['product_name']} | expire={out['expire_date']}"
        )
        return out
    except Exception as e:
        status = "FAILED"
        logger.error(f"[LabelParser] 解析失败 | error={e}")
        return empty
    finally:
        _track(
            provider="vision",
            model=settings.VISION_MODEL,
            endpoint="label_parse",
            prompt_tokens=pt,
            completion_tokens=ct,
            duration_ms=int((_time.time() - t0) * 1000),
            status=status,
        )


def save_label_image(image_base64: str, device_id: str) -> Optional[str]:
    """把标签 base64 图保存到 uploads/，返回相对路径。"""
    import time
    from services.upload_security import (
        decode_base64_image, make_upload_filename, save_image_bytes,
        sanitize_filename_part,
    )

    if not image_base64:
        return None

    try:
        data = decode_base64_image(image_base64)
        if not data:
            return None
        prefix = f"label_{sanitize_filename_part(device_id)}_{int(time.time())}"
        return save_image_bytes(make_upload_filename(prefix, ".jpg"), data)
    except Exception as e:
        logger.error(f"[LabelParser] 保存标签图失败 | error={e}")
        return None
