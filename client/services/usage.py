"""LLM/Vision/Embedding token 计量与费用估算。

用法：
    track_usage(provider="llm", model="...", endpoint="recipe",
                prompt_tokens=240, completion_tokens=180, duration_ms=1200)

调用方负责拿到 usage 数据后传进来，本服务自己开/关 session，绝不影响业务路径。
"""

import logging
from typing import Optional

from database import SessionLocal
from models import LlmUsage

logger = logging.getLogger(__name__)


# 模型单价表（USD per 1M tokens，估算用，按各家公开定价填）
# DeepSeek: deepseek-chat $0.14 输入 / $0.28 输出
# Qwen-vl-flash: ~$0.15 输入 / $0.30 输出
# multimodal-embedding-v1: ~$0.05 / 1M tokens（按调用次数估）
PRICING = {
    # DeepSeek
    "deepseek-chat":            {"input": 0.14,  "output": 0.28},
    "deepseek-reasoner":        {"input": 0.55,  "output": 2.19},
    "deepseek-v4-flash":        {"input": 0.14,  "output": 0.28},  # 兜底
    # 通义千问视觉
    "qwen-vl-plus":             {"input": 1.50,  "output": 4.50},
    "qwen-vl-max":              {"input": 3.00,  "output": 9.00},
    "qwen3-vl-flash":           {"input": 0.50,  "output": 1.50},
    # Embedding
    "multimodal-embedding-v1":  {"input": 0.05,  "output": 0.0},
}


def estimate_cost(model: str, prompt_tokens: int, completion_tokens: int) -> float:
    """根据 PRICING 表估算本次调用费用（USD）。"""
    p = PRICING.get(model)
    if not p:
        # 未知模型按 deepseek-chat 兜底
        p = PRICING["deepseek-chat"]
    cost = (prompt_tokens * p["input"] + completion_tokens * p["output"]) / 1_000_000.0
    return round(cost, 6)


def track_usage(
    provider: str,
    model: str,
    endpoint: Optional[str] = None,
    user_id: Optional[str] = None,
    prompt_tokens: int = 0,
    completion_tokens: int = 0,
    duration_ms: Optional[int] = None,
    status: str = "SUCCESS",
) -> None:
    """写入一条 token 消耗记录。失败时只记日志，不抛异常影响业务。"""
    total = (prompt_tokens or 0) + (completion_tokens or 0)
    cost = estimate_cost(model, prompt_tokens or 0, completion_tokens or 0)

    db = SessionLocal()
    try:
        row = LlmUsage(
            provider=provider,
            model=model,
            endpoint=endpoint,
            user_id=user_id,
            prompt_tokens=prompt_tokens or 0,
            completion_tokens=completion_tokens or 0,
            total_tokens=total,
            cost_usd=cost,
            duration_ms=duration_ms,
            status=status,
        )
        db.add(row)
        db.commit()
        logger.info(
            f"[Usage] {provider}/{model} endpoint={endpoint} "
            f"user={user_id} pt={prompt_tokens} ct={completion_tokens} "
            f"cost=${cost} status={status}"
        )
    except Exception as e:
        logger.error(f"[Usage] 写入失败 | error={e}")
        try:
            db.rollback()
        except Exception:
            pass
    finally:
        db.close()
