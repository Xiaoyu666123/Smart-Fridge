import json
import logging

from sqlalchemy.orm import Session

from models import UserPreference, Conversation
from services.llm import _call_llm

logger = logging.getLogger(__name__)

EXTRACT_PROMPT = """分析以下用户消息，提取饮食偏好信息。返回 JSON 数组格式：
[{{"key": "偏好类型", "value": "偏好值"}}]

偏好类型包括：taste(口味), allergy(过敏), dislike(忌口), prefer(饮食方式)

如果没有提取到偏好信息，返回空数组：[]

用户消息：{message}

只返回 JSON，不要其他文字。"""


def extract_preferences(user_message: str) -> list[dict]:
    """
    从对话中提取偏好。
    如 "我不吃辣" → [{"key": "dislike", "value": "辣味"}]
    """
    logger.info(f"[LLM] 偏好提取 | message={user_message[:80]}")
    try:
        content = _call_llm(EXTRACT_PROMPT.format(message=user_message), endpoint="preference_extract")
        result = json.loads(content.strip().strip("```json").strip("```").strip())
        if isinstance(result, list):
            logger.info(f"[LLM] 偏好提取完成 | count={len(result)} | prefs={result}")
            return result
        logger.warning(f"[LLM] 偏好提取返回非数组 | content={content[:200]}")
        return []
    except Exception as e:
        logger.error(f"[LLM] 偏好提取失败 | error={e}")
        return []


def save_preferences(db: Session, user_id: str, preferences: list[dict]):
    """保存用户偏好到数据库（去重）。"""
    for pref in preferences:
        key = pref.get("key", "")
        value = pref.get("value", "")
        if not key or not value:
            continue

        exists = (
            db.query(UserPreference)
            .filter(
                UserPreference.user_id == user_id,
                UserPreference.preference_key == key,
                UserPreference.preference_value == value,
            )
            .first()
        )
        if not exists:
            db.add(UserPreference(
                user_id=user_id,
                preference_key=key,
                preference_value=value,
                source="chat",
            ))
    db.commit()


def get_preferences(db: Session, user_id: str) -> list[str]:
    """
    返回该用户所有偏好，组装为 prompt 片段。
    如 ["不吃辣", "花生过敏", "偏好清淡"]
    """
    prefs = db.query(UserPreference).filter(UserPreference.user_id == user_id).all()
    return [p.preference_value for p in prefs]


def save_conversation(db: Session, user_id: str, role: str, content: str):
    """保存一条对话记录。"""
    db.add(Conversation(user_id=user_id, role=role, content=content))
    db.commit()


def get_recent_conversations(db: Session, user_id: str, limit: int = 10) -> list[dict]:
    """获取最近 N 条对话历史。"""
    convs = (
        db.query(Conversation)
        .filter(Conversation.user_id == user_id)
        .order_by(Conversation.created_at.desc())
        .limit(limit)
        .all()
    )
    return [{"role": c.role, "content": c.content} for c in reversed(convs)]
