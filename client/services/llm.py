import json
import logging

import httpx

from config import settings

logger = logging.getLogger(__name__)


def _call_llm(prompt: str) -> str:
    """通用 LLM 调用封装。"""
    logger.info(f"[LLM] 发起调用 | model={settings.LLM_MODEL} | prompt_len={len(prompt)}")
    resp = httpx.post(
        settings.LLM_API_URL,
        headers={"Authorization": f"Bearer {settings.LLM_API_KEY}"},
        json={
            "model": settings.LLM_MODEL,
            "messages": [{"role": "user", "content": prompt}],
        },
        timeout=60.0,
    )
    resp.raise_for_status()
    content = resp.json()["choices"][0]["message"]["content"]
    logger.info(f"[LLM] 调用成功 | response_len={len(content)} | preview={content[:200]}")
    return content


def get_season() -> str:
    """根据当前月份推算季节。"""
    from datetime import datetime
    month = datetime.now().month
    if month in (3, 4, 5):
        return "春季"
    elif month in (6, 7, 8):
        return "夏季"
    elif month in (9, 10, 11):
        return "秋季"
    else:
        return "冬季"


def estimate_freshness(category: str, city: str, season: str) -> dict:
    """
    推算食材保鲜期。
    返回: {"shelf_life_days": 7, "storage_advice": "冷藏保存"}
    """
    if not settings.LLM_API_KEY or not settings.LLM_API_URL:
        logger.warning(f"[LLM] API 未配置，使用默认保鲜期 | category={category}")
        return {"shelf_life_days": 7, "storage_advice": "冷藏保存"}

    logger.info(f"[LLM] 保鲜期推算 | category={category} | city={city} | season={season}")
    prompt = f"""你是一个食材保鲜专家。请根据以下信息推算食材的保鲜期。

食材：{category}
城市：{city}
季节：{season}

请返回 JSON 格式：
{{"shelf_life_days": 天数, "storage_advice": "存储建议"}}
只返回 JSON，不要其他文字。"""

    try:
        content = _call_llm(prompt)
        result = json.loads(content.strip().strip("```json").strip("```").strip())
        freshness = {
            "shelf_life_days": result.get("shelf_life_days", 7),
            "storage_advice": result.get("storage_advice", "冷藏保存"),
        }
        logger.info(f"[LLM] 保鲜期推算完成 | category={category} | result={freshness}")
        return freshness
    except Exception as e:
        logger.error(f"[LLM] 保鲜期推算失败 | category={category} | error={e}")
        return {"shelf_life_days": 7, "storage_advice": "冷藏保存"}


def recommend_recipe(inventory: list, preferences: list, city: str, season: str, user_message: str,
                     weather_info: dict = None) -> str:
    """
    综合推荐食谱。
    入参：库存列表、用户偏好列表、城市、季节、用户消息、天气信息
    返回：食谱推荐文本
    """
    if not settings.LLM_API_KEY or not settings.LLM_API_URL:
        logger.warning("[LLM] API 未配置，食谱推荐不可用")
        return "推荐服务暂时不可用，请稍后再试。"

    inventory_text = "\n".join(
        f"- {item['category']}（剩余保鲜 {item['remain_days']} 天）"
        for item in inventory
    ) if inventory else "冰箱为空"

    preferences_text = "\n".join(f"- {p}" for p in preferences) if preferences else "无特殊偏好"

    weather_section = ""
    if weather_info and weather_info.get("temperature") is not None:
        weather_section = f"""
【实时天气】
城市：{weather_info.get('city', city)}
天气：{weather_info.get('weather_desc', '未知')}
温度：{weather_info.get('temperature')}°C
湿度：{weather_info.get('humidity')}%
风速：{weather_info.get('wind_speed')} km/h
请根据当前天气环境推荐适合的食谱，例如高温天气推荐清淡解暑的菜品，低温天气推荐暖身菜品。"""

    logger.info(f"[LLM] 食谱推荐 | inventory_count={len(inventory)} | city={city} | season={season} | weather={'有' if weather_info else '无'} | message={user_message[:50]}")

    prompt = f"""你是一个智能冰箱食材管理助手。

【环境信息】
城市：{city}，当前季节：{season}
{weather_section}
【冰箱库存】
{inventory_text}

【用户偏好】
{preferences_text}

【用户消息】
{user_message}

请根据以上信息推荐合适的食谱，优先使用快过期的食材。回复要简洁实用。"""

    try:
        reply = _call_llm(prompt)
        logger.info(f"[LLM] 食谱推荐完成 | reply_len={len(reply)}")
        return reply
    except Exception as e:
        logger.error(f"[LLM] 食谱推荐失败 | error={e}")
        return "推荐服务暂时不可用，请稍后再试。"
