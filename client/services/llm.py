import json
import logging
from typing import Optional

import httpx

from config import settings

logger = logging.getLogger(__name__)


def _call_llm(prompt: str, endpoint: str = "llm_chat", user_id: Optional[str] = None) -> str:
    """通用 LLM 调用封装。"""
    from services.usage import track_usage as _track
    import time as _time

    logger.info(f"[LLM] 发起调用 | model={settings.LLM_MODEL} | prompt_len={len(prompt)} | endpoint={endpoint}")
    t0 = _time.time()
    try:
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
        body = resp.json()
        content = body["choices"][0]["message"]["content"]
        usage = body.get("usage") or {}
        _track(
            provider="llm",
            model=settings.LLM_MODEL,
            endpoint=endpoint,
            user_id=user_id,
            prompt_tokens=usage.get("prompt_tokens", 0),
            completion_tokens=usage.get("completion_tokens", 0),
            duration_ms=int((_time.time() - t0) * 1000),
            status="SUCCESS",
        )
        logger.info(f"[LLM] 调用成功 | response_len={len(content)} | tokens=p{usage.get('prompt_tokens', 0)}/c{usage.get('completion_tokens', 0)} | preview={content[:200]}")
        return content
    except Exception:
        _track(
            provider="llm", model=settings.LLM_MODEL, endpoint=endpoint, user_id=user_id,
            duration_ms=int((_time.time() - t0) * 1000), status="FAILED",
        )
        raise


def _call_llm_stream(prompt: str, endpoint: str = "llm_chat_stream", user_id: Optional[str] = None):
    """流式 LLM 调用：逐 token yield 文本片段。

    使用 OpenAI 兼容的 SSE 协议（DeepSeek / DashScope 兼容模式都支持）。
    上游异常时直接抛出，让上层处理回退。
    """
    import json as _json
    import time as _time
    from services.usage import track_usage as _track

    logger.info(f"[LLM] 发起流式调用 | model={settings.LLM_MODEL} | prompt_len={len(prompt)} | endpoint={endpoint}")
    t0 = _time.time()
    prompt_tokens = 0
    completion_tokens = 0
    completion_chars = 0
    status = "SUCCESS"
    try:
        with httpx.stream(
            "POST",
            settings.LLM_API_URL,
            headers={"Authorization": f"Bearer {settings.LLM_API_KEY}"},
            json={
                "model": settings.LLM_MODEL,
                "messages": [{"role": "user", "content": prompt}],
                "stream": True,
                "stream_options": {"include_usage": True},
            },
            timeout=120.0,
        ) as resp:
            resp.raise_for_status()
            for raw in resp.iter_lines():
                if not raw:
                    continue
                line = raw.decode() if isinstance(raw, bytes) else raw
                line = line.strip()
                if not line.startswith("data:"):
                    continue
                data = line[5:].strip()
                if data == "[DONE]":
                    break
                try:
                    chunk = _json.loads(data)
                except Exception:
                    continue
                # usage 帧：DeepSeek/Qwen 在最后一帧 choices=[] 时给 usage
                u = chunk.get("usage")
                if u:
                    prompt_tokens = u.get("prompt_tokens", prompt_tokens)
                    completion_tokens = u.get("completion_tokens", completion_tokens)
                choices = chunk.get("choices") or []
                if not choices:
                    continue
                delta = choices[0].get("delta") or {}
                piece = delta.get("content") or ""
                if piece:
                    completion_chars += len(piece)
                    yield piece
        # 兜底：如果上游不给 usage，按字符数粗估（中文约 1 字符 = 1 token）
        if completion_tokens == 0 and completion_chars > 0:
            completion_tokens = completion_chars
        if prompt_tokens == 0:
            prompt_tokens = max(1, len(prompt))  # 粗估
        logger.info(f"[LLM] 流式调用完成 | tokens=p{prompt_tokens}/c{completion_tokens}")
    except Exception:
        status = "FAILED"
        raise
    finally:
        _track(
            provider="llm",
            model=settings.LLM_MODEL,
            endpoint=endpoint,
            user_id=user_id,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            duration_ms=int((_time.time() - t0) * 1000),
            status=status,
        )


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
        content = _call_llm(prompt, endpoint="freshness")
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
                     weather_info: dict = None, history: list = None,
                     user_id: Optional[str] = None) -> str:
    """
    综合推荐食谱。
    入参：库存列表、用户偏好列表、城市、季节、用户消息、天气信息、最近对话历史
    返回：食谱推荐文本
    """
    if not settings.LLM_API_KEY or not settings.LLM_API_URL:
        logger.warning("[LLM] API 未配置，食谱推荐不可用")
        return "推荐服务暂时不可用，请稍后再试。"

    logger.info(
        f"[LLM] 食谱推荐 | inventory_count={len(inventory)} | city={city} | season={season} | "
        f"weather={'有' if weather_info else '无'} | history={len(history) if history else 0} | message={user_message[:50]}"
    )

    prompt = build_recipe_prompt(inventory, preferences, city, season, user_message, weather_info, history)
    try:
        reply = _call_llm(prompt, endpoint="recipe", user_id=user_id)
        logger.info(f"[LLM] 食谱推荐完成 | reply_len={len(reply)}")
        return reply
    except Exception as e:
        logger.error(f"[LLM] 食谱推荐失败 | error={e}")
        return "推荐服务暂时不可用，请稍后再试。"


def build_recipe_prompt(inventory: list, preferences: list, city: str, season: str,
                        user_message: str, weather_info: dict = None,
                        history: list = None) -> str:
    """提取出来给流式接口复用。

    history: list[{"role": "user"|"assistant", "content": str}]，最近若干轮对话
    """
    # 按剩余保鲜天数升序，方便 LLM 优先使用快过期的
    sorted_inv = sorted(inventory, key=lambda i: i.get("remain_days", 999))
    inventory_text = "\n".join(
        f"- {item['category']}（剩余保鲜 {item['remain_days']} 天）"
        for item in sorted_inv
    ) if sorted_inv else "冰箱为空"

    # 单独标出 3 天内过期的，作为强提示
    expiring = [i for i in sorted_inv if i.get("remain_days", 999) <= 3]
    expiring_section = ""
    if expiring:
        names = "、".join(f"{i['category']}({i['remain_days']}天)" for i in expiring[:8])
        expiring_section = f"\n【⚠️ 临期食材 - 优先使用】\n以下食材 3 天内将过期，请优先在食谱中使用：{names}\n"

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

    history_section = ""
    if history:
        # 过滤掉与本次 user_message 重复的最后一条 user（避免在 prompt 里重复出现）
        filtered = []
        for h in history:
            content = (h.get("content") or "").strip()
            role = h.get("role")
            if role == "user" and content == (user_message or "").strip():
                continue
            filtered.append({"role": role, "content": content})
        rendered = []
        for h in filtered[-6:]:  # 最近 6 条（3 轮）够用
            role = "用户" if h.get("role") == "user" else "助手"
            content = h.get("content", "").strip()
            if not content:
                continue
            # 助手长文本截短，避免 prompt 爆炸
            if role == "助手" and len(content) > 200:
                content = content[:200] + "..."
            rendered.append(f"{role}: {content}")
        if rendered:
            history_section = "【最近对话】\n" + "\n".join(rendered) + "\n"

    return f"""你是一个智能冰箱食材管理助手。

【环境信息】
城市：{city}，当前季节：{season}
{weather_section}
【冰箱库存】（按剩余保鲜天数升序）
{inventory_text}
{expiring_section}
【用户偏好】
{preferences_text}

{history_section}【用户消息】
{user_message}

请根据以上信息和最近对话推荐合适的食谱，**优先使用临期食材**（如果有的话）。回复要简洁实用。
若用户消息是对前一轮回复的追问（如"那再来一个"、"换个清淡的"），请理解上下文。"""


def recommend_recipe_stream(inventory: list, preferences: list, city: str, season: str,
                            user_message: str, weather_info: dict = None,
                            history: list = None, user_id: Optional[str] = None):
    """流式食谱推荐：yield 每个文本片段。"""
    if not settings.LLM_API_KEY or not settings.LLM_API_URL:
        yield "推荐服务暂时不可用，请稍后再试。"
        return

    prompt = build_recipe_prompt(inventory, preferences, city, season, user_message, weather_info, history)
    try:
        for piece in _call_llm_stream(prompt, endpoint="recipe_stream", user_id=user_id):
            yield piece
    except Exception as e:
        logger.error(f"[LLM] 流式食谱推荐失败 | error={e}")
        yield "推荐服务暂时不可用，请稍后再试。"


# ===== 食谱结构化输出（专为前端卡片渲染） =====

STRUCTURED_RECIPE_PROMPT = """你是一个智能冰箱食材管理助手。请根据用户的需求和现有库存，**推荐 1-3 个食谱**。

【环境】城市：{city} 季节：{season}{weather_section}
【冰箱库存】
{inventory_text}

【用户偏好】
{preferences_text}

{history_section}【用户消息】
{user_message}

输出格式（极其严格）：
1. 先一两句中文寒暄/解释，开头自然，不要带 JSON。
2. 然后**每个食谱**用一个独立 JSON 块包裹，前后用 ===RECIPE=== 标记：

===RECIPE===
{{
  "name": "番茄炒蛋",
  "summary": "国民下饭菜，10 分钟搞定",
  "prep_time": 10,
  "difficulty": "简单",
  "tags": ["快手", "下饭", "家常"],
  "ingredients": [
    {{"name": "番茄", "amount": "2个"}},
    {{"name": "鸡蛋", "amount": "3个"}},
    {{"name": "盐", "amount": "适量"}}
  ],
  "steps": [
    "鸡蛋打散加少许盐，番茄切块",
    "热锅冷油炒蛋至刚凝固即盛出",
    "另起锅炒番茄出汁，倒回鸡蛋翻炒断生即可"
  ]
}}
===RECIPE===

要求：
- prep_time 单位是分钟，integer
- difficulty 必须是 "简单"/"中等"/"困难" 之一
- ingredients 优先用冰箱已有的食材，缺失的常备调料也要列出
- steps 控制在 3-5 步，每步一句话
- 1-3 个食谱，**别多别少**
- 食谱之间可以有简短过渡文字（"再来一个清淡的："等）
- 不要把 JSON 写在 markdown 代码块里，直接用 ===RECIPE=== 包裹"""


def build_structured_recipe_prompt(inventory: list, preferences: list, city: str, season: str,
                                   user_message: str, weather_info: dict = None,
                                   history: list = None) -> str:
    sorted_inv = sorted(inventory, key=lambda i: i.get("remain_days", 999))
    inventory_text = "\n".join(
        f"- {item['category']}（剩余保鲜 {item['remain_days']} 天）"
        for item in sorted_inv
    ) if sorted_inv else "冰箱为空"

    # 临期食材（3 天内）单独提示
    expiring = [i for i in sorted_inv if i.get("remain_days", 999) <= 3]
    if expiring:
        names = "、".join(f"{i['category']}({i['remain_days']}天)" for i in expiring[:8])
        inventory_text += f"\n\n⚠️ 临期食材（3 天内过期）：{names}\n请优先在食谱里使用这些食材。"

    preferences_text = "\n".join(f"- {p}" for p in preferences) if preferences else "无特殊偏好"

    weather_section = ""
    if weather_info and weather_info.get("temperature") is not None:
        weather_section = f"\n温度 {weather_info.get('temperature')}°C / {weather_info.get('weather_desc', '未知')}"

    history_section = ""
    if history:
        filtered = []
        for h in history:
            content = (h.get("content") or "").strip()
            role = h.get("role")
            if role == "user" and content == (user_message or "").strip():
                continue
            filtered.append({"role": role, "content": content})
        rendered = []
        for h in filtered[-6:]:
            role = "用户" if h.get("role") == "user" else "助手"
            content = h.get("content", "").strip()
            if not content:
                continue
            if role == "助手" and len(content) > 200:
                content = content[:200] + "..."
            rendered.append(f"{role}: {content}")
        if rendered:
            history_section = "【最近对话】\n" + "\n".join(rendered) + "\n"

    return STRUCTURED_RECIPE_PROMPT.format(
        city=city, season=season,
        weather_section=weather_section,
        inventory_text=inventory_text,
        preferences_text=preferences_text,
        history_section=history_section,
        user_message=user_message,
    )


def recommend_structured_stream(inventory: list, preferences: list, city: str, season: str,
                                user_message: str, weather_info: dict = None,
                                history: list = None, user_id: Optional[str] = None):
    """流式产出结构化食谱：raw 流。前端按 ===RECIPE=== 拆分卡片。"""
    if not settings.LLM_API_KEY or not settings.LLM_API_URL:
        yield "推荐服务暂时不可用，请稍后再试。"
        return

    prompt = build_structured_recipe_prompt(
        inventory, preferences, city, season, user_message, weather_info, history
    )
    try:
        for piece in _call_llm_stream(prompt, endpoint="recipe_struct_stream", user_id=user_id):
            yield piece
    except Exception as e:
        logger.error(f"[LLM] 结构化食谱推荐失败 | error={e}")
        yield "推荐服务暂时不可用，请稍后再试。"


# ===== AI 营养教练 =====

def coach_advice(report: dict, preferences: list, recent_consumed: list,
                  expiring: list, user_id: Optional[str] = None) -> dict:
    """基于健康评分 + 偏好 + 近期消耗 + 临期食材，让 LLM 给出营养教练建议。

    返回 {summary: str, week_plan: [str], action_items: [str], avoid: [str]}
    任一段失败时安全降级为提示文字。
    """
    if not settings.LLM_API_KEY or not settings.LLM_API_URL:
        return {
            "summary": "AI 教练暂时不可用，请稍后再试。",
            "week_plan": [],
            "action_items": [],
            "avoid": [],
        }

    # 拼装紧凑的数据摘要
    h = report.get("health_overall", {})
    dist_lines = [f"- {d['emoji']} {d['label']}: {d['count']} 件"
                  for d in (report.get("distribution") or [])[:8]]
    consumed_lines = [f"- {c['category']}（{c['count']} 次）"
                      for c in recent_consumed[:8]]
    expiring_lines = [f"- {e['category']}（剩 {e['days']} 天）"
                      for e in expiring[:8]]
    pref_lines = [f"- {p}" for p in preferences[:10]]

    prompt = f"""你是一位经验丰富的营养教练，请为用户给出本周饮食建议。

【健康评分】{h.get('score', '?')} 分（{h.get('level', '?')}）
- 蔬果占比：{int(h.get('veg_fruit_ratio', 0) * 100)}%
- 蛋白质占比：{int(h.get('meat_ratio', 0) * 100)}%
- 零食占比：{int(h.get('snack_ratio', 0) * 100)}%

【冰箱当前类别分布】
{chr(10).join(dist_lines) if dist_lines else "（暂无）"}

【临期食材】（这些必须本周用掉）
{chr(10).join(expiring_lines) if expiring_lines else "（无）"}

【近期消耗较多的品类】
{chr(10).join(consumed_lines) if consumed_lines else "（暂无消耗记录）"}

【用户饮食偏好】
{chr(10).join(pref_lines) if pref_lines else "（无特殊偏好）"}

请按以下格式严格输出 JSON（不要包裹 markdown，直接输出 JSON）：

{{
  "summary": "用一句话点评本周饮食结构（不超过 50 字）",
  "week_plan": [
    "周一：xxx",
    "周二：xxx",
    "周三：xxx"
  ],
  "action_items": [
    "建议 1（具体可执行）",
    "建议 2",
    "建议 3"
  ],
  "avoid": [
    "本周尽量少吃的食物 1",
    "本周尽量少吃的食物 2"
  ]
}}

要求：
- summary 客观又鼓励，不要说教
- week_plan 必须 3-5 项，要利用临期食材，避开过敏忌口
- action_items 必须 3-5 条，每条具体（"早餐加一杯酸奶"而不是"多吃乳制品"）
- avoid 1-3 条，不超过偏好里的过敏忌口范围"""

    try:
        text = _call_llm(prompt, endpoint="coach", user_id=user_id)
    except Exception as e:
        logger.error(f"[Coach] LLM 调用失败 | error={e}")
        return {
            "summary": "AI 教练暂时不可用，请稍后再试。",
            "week_plan": [],
            "action_items": [],
            "avoid": [],
        }

    # 解析 JSON（容忍 markdown ```json 包裹）
    import json as _json
    import re as _re
    cleaned = text.strip()
    m = _re.search(r"\{[\s\S]*\}", cleaned)
    if m:
        cleaned = m.group(0)
    try:
        parsed = _json.loads(cleaned)
        return {
            "summary": str(parsed.get("summary", "")).strip(),
            "week_plan": [str(x) for x in (parsed.get("week_plan") or [])],
            "action_items": [str(x) for x in (parsed.get("action_items") or [])],
            "avoid": [str(x) for x in (parsed.get("avoid") or [])],
        }
    except Exception as e:
        logger.warning(f"[Coach] JSON 解析失败，返回原始文本 | error={e}")
        return {
            "summary": text[:200],
            "week_plan": [],
            "action_items": [],
            "avoid": [],
        }


# ===== AI 决策可解释性：把工具链 trace 翻成自然语言 =====

def explain_trace(steps: list, agent_type: str, device_id: Optional[str],
                   user_id: Optional[str] = None) -> str:
    """让 LLM 用一段中文把 agent 工具链翻译成"AI 是怎么做这个决定的"。

    steps: list of {tool_name, tool_input, tool_output, status, duration_ms}
    返回一段不超过 300 字的解释（含决策原因 / 关键数据 / 最终结论）。
    """
    if not settings.LLM_API_KEY or not settings.LLM_API_URL:
        return "AI 解释暂不可用（未配置 LLM）。"
    if not steps:
        return "该追踪记录没有可解释的步骤。"

    # 工具中文名映射，让 LLM 输出更人类化
    label_map = {
        "vector_dedup": "向量去重",
        "vision_assist_decide": "视觉辅助识别决策",
        "vision_recognize": "云端视觉识别",
        "embedding_extract": "向量提取",
        "llm_freshness": "保鲜期推算",
        "label_associate": "标签关联",
        "db_write_inventory": "写入库存",
        "db_write_event_log": "写入事件流水",
        "db_query_inventory": "查询库存",
        "preference_extract": "偏好提取",
        "db_save_preferences": "保存偏好",
        "llm_recipe": "食谱推荐",
        "llm_recipe_stream": "食谱推荐(流式)",
        "llm_recipe_struct_stream": "结构化食谱推荐(流式)",
        "weather_query": "天气查询",
    }

    lines = []
    for i, s in enumerate(steps, 1):
        name = label_map.get(s.get("tool_name", ""), s.get("tool_name", ""))
        status = s.get("status", "")
        dur = s.get("duration_ms")
        out = s.get("tool_output") or {}
        # 把 output 里关键字段挑出来（避免整 JSON 喂进去）
        kv = []
        for k, v in out.items():
            if v is None or v == "":
                continue
            if isinstance(v, (dict, list)):
                continue
            kv.append(f"{k}={v}")
        line = f"{i}. {name}（{status}, {dur}ms）" + ("｜" + "；".join(kv) if kv else "")
        lines.append(line)

    prompt = f"""你是一位向用户解释 AI 决策过程的助手。下面是一次 agent 工具链的执行记录，请用一段 200-280 字的中文，按时间顺序把决策过程讲清楚，重点说明：

- 每一步做了什么、用到的关键数据
- 关键判断和分支（如：为什么调云端识别 / 为什么用标签数据覆盖 LLM 估算）
- 最终得出的结论

不要逐条复述步骤名，要让普通人看懂"AI 是怎么做这个决定的"。不要用 markdown，不要换行符过多，只输出一整段流畅的中文。

【场景】Agent 类型：{agent_type}{(' / 设备：' + device_id) if device_id else ''}
【步骤】
{chr(10).join(lines)}
"""

    try:
        text = _call_llm(prompt, endpoint="trace_explain", user_id=user_id)
        return text.strip()
    except Exception as e:
        logger.error(f"[ExplainTrace] LLM 调用失败 | error={e}")
        return f"AI 解释暂时不可用，请稍后再试。"


# ===== 食材替换助手 =====

def suggest_substitute(target_ingredient: str, recipe_name: Optional[str],
                        available_ingredients: list, preferences: list,
                        user_id: Optional[str] = None) -> dict:
    """根据当前库存和偏好，推荐 2-3 个 target_ingredient 的替代方案。

    返回 {summary: str, options: [{name, reason, in_stock}]}
    """
    if not settings.LLM_API_KEY or not settings.LLM_API_URL:
        return {"summary": "AI 替换暂不可用", "options": []}

    avail_text = "、".join(available_ingredients[:30]) if available_ingredients else "（冰箱当前没有库存）"
    pref_text = "、".join(preferences[:8]) if preferences else "（无）"

    prompt = f"""你是一个智能厨房助手。用户在做"{recipe_name or '一道菜'}"，原方需要"{target_ingredient}"，但是冰箱里没有或它已经过期了。

【冰箱当前可用的食材】
{avail_text}

【用户饮食偏好/禁忌】
{pref_text}

请给出 2-3 个**实用的替代方案**，按以下格式严格返回 JSON（不要 markdown 包裹）：

{{
  "summary": "用一句话简单点评（不超过 30 字）",
  "options": [
    {{"name": "替代食材名", "reason": "为什么能替代（不超过 25 字）", "in_stock": true}},
    {{"name": "替代食材名", "reason": "理由", "in_stock": false}}
  ]
}}

要求：
- options 必须 2-3 项
- 优先用冰箱已有食材（in_stock=true）
- 如果没合适的库存替代，可以推荐用户去买（in_stock=false）
- 必须避开偏好里的过敏忌口
- reason 要具体（"风味相似"或"质地接近"或"补充蛋白质"）"""

    try:
        text = _call_llm(prompt, endpoint="substitute", user_id=user_id)
    except Exception as e:
        logger.error(f"[Substitute] LLM 失败 | error={e}")
        return {"summary": "AI 替换暂时不可用", "options": []}

    import json as _json
    import re as _re
    cleaned = text.strip()
    m = _re.search(r"\{[\s\S]*\}", cleaned)
    if m:
        cleaned = m.group(0)
    try:
        parsed = _json.loads(cleaned)
        return {
            "summary": str(parsed.get("summary", "")).strip(),
            "options": [
                {
                    "name": str(o.get("name", "")).strip(),
                    "reason": str(o.get("reason", "")).strip(),
                    "in_stock": bool(o.get("in_stock", False)),
                }
                for o in (parsed.get("options") or [])
                if o.get("name")
            ][:5],
        }
    except Exception as e:
        logger.warning(f"[Substitute] JSON 解析失败 | error={e}")
        return {"summary": text[:80], "options": []}


# ===== AI 每日一句话 =====

def daily_tip(weather: Optional[dict], expiring: list, preferences: list,
               health_score: Optional[int], recent_consumed: list,
               user_id: Optional[str] = None) -> str:
    """每天一条 60 字以内的 AI 主动消息。综合天气 + 临期 + 偏好 + 健康 + 消耗。"""
    if not settings.LLM_API_KEY or not settings.LLM_API_URL:
        return "今天也要好好吃饭呀～"

    parts = []
    if weather and weather.get("temperature") is not None:
        parts.append(f"今天 {weather.get('city', '')} {weather.get('temperature')}°C，{weather.get('weather_desc', '')}")
    if expiring:
        names = "、".join(f"{e['category']}({e['days']}天)" for e in expiring[:3])
        parts.append(f"快过期：{names}")
    if recent_consumed:
        names = "、".join(c["category"] for c in recent_consumed[:3])
        parts.append(f"近期常消耗：{names}")
    if preferences:
        parts.append(f"偏好：{ '、'.join(preferences[:5]) }")
    if health_score is not None:
        parts.append(f"近期健康评分 {health_score}/100")

    if not parts:
        return "今天和 AI 聊聊想吃什么吧～"

    prompt = "你是用户的私人厨房助手，给一句**不超过 60 字**的中文小贴士。" \
             "要像朋友一样亲切，用上下面的事实，但不要罗列：\n\n" + \
             "\n".join(parts) + \
             "\n\n直接输出那句话，不要带引号、不要带 AI: 前缀。"

    try:
        text = _call_llm(prompt, endpoint="daily_tip", user_id=user_id)
        cleaned = text.strip().strip('"').strip("\u201c").strip("\u201d").strip("'")
        # 去掉可能的"AI："前缀
        for prefix in ("AI：", "AI:", "助手：", "助手:"):
            if cleaned.startswith(prefix):
                cleaned = cleaned[len(prefix):].strip()
        return cleaned[:120] if len(cleaned) <= 120 else cleaned[:120] + "…"
    except Exception as e:
        logger.error(f"[DailyTip] LLM 失败 | error={e}")
        return "今天的食材都很新鲜，记得按时吃饭～"


# ===== 自然语言库存查询 =====

def answer_inventory_query(question: str, inventory: list,
                            user_id: Optional[str] = None) -> dict:
    """用自然语言回答用户对冰箱库存的提问。

    inventory: list[{category, status, remain_days, brand, expire_at}]
    返回 {answer: str, matched: [category...]}（matched 可空）。
    纯问答，不下结论让用户做菜（那是 /agent/chat 的活）。
    """
    if not settings.LLM_API_KEY or not settings.LLM_API_URL:
        return {"answer": "库存问答暂时不可用（未配置 LLM）。", "matched": []}

    if not inventory:
        return {"answer": "你的冰箱现在是空的，还没有任何在库食材。", "matched": []}

    # 拼装紧凑的库存事实表（按剩余天数升序，临期优先）
    rows = sorted(inventory, key=lambda x: x.get("remain_days", 999))
    lines = []
    for it in rows:
        parts = [it["category"]]
        if it.get("brand"):
            parts.append(f"品牌:{it['brand']}")
        rd = it.get("remain_days")
        if rd is None:
            parts.append("保鲜期未计算")
        elif rd < 0:
            parts.append(f"已过期{-rd}天")
        else:
            parts.append(f"剩{rd}天")
        lines.append("- " + "，".join(parts))
    inventory_text = "\n".join(lines)

    prompt = f"""你是用户的冰箱管家。下面是冰箱里**当前在库**的全部食材（已按剩余保鲜天数升序）：

{inventory_text}

用户的问题：{question}

要求：
- 只根据上面的库存事实回答，**不要编造没有的食材**。
- 回答简洁口语化，**不超过 80 字**。
- 如果用户问的食材不在库存里，明确说"没有"。
- 如果问临期/过期，把符合条件的列出来。
- 不要做菜推荐（那是另一个功能），只回答库存事实。
- 直接给答案，不要加"根据库存"之类的废话开头。"""

    try:
        answer = _call_llm(prompt, endpoint="inventory_query", user_id=user_id)
        answer = answer.strip()
    except Exception as e:
        logger.error(f"[InventoryQuery] LLM 失败 | error={e}")
        return {"answer": "库存问答暂时不可用，请稍后再试。", "matched": []}

    # 简单匹配：答案里提到了哪些库存品类
    matched = [it["category"] for it in inventory
               if it["category"] and it["category"] in answer]
    return {"answer": answer[:300], "matched": list(dict.fromkeys(matched))}
