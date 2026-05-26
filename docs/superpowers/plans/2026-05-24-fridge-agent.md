# 智能冰箱 Agent 系统实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在现有冰箱食材管理系统上构建 Agent 智能体，调用视觉/语言大模型实现食材识别、保鲜期推算、食谱推荐。

**Architecture:** 新增 services 层封装外部 API 调用，agents 层编排业务逻辑，新增 2 张数据库表存储用户偏好和对话历史。现有事件处理流程改为通过 Agent 执行。

**Tech Stack:** FastAPI, SQLAlchemy 2.0, PostgreSQL + pgvector, httpx, pydantic-settings

---

## 文件清单

| 操作 | 文件 | 职责 |
|------|------|------|
| 修改 | `client/config.py` | 新增 API Key 配置 |
| 修改 | `client/.env` | 新增环境变量 |
| 修改 | `client/requirements.txt` | 新增 httpx 依赖 |
| 修改 | `client/models/__init__.py` | 新增 UserPreference, Conversation, Inventory 加 stored_at |
| 修改 | `client/schemas/__init__.py` | 新增 ChatRequest/Response, RecognizeRequest/Response |
| 修改 | `client/crud/__init__.py` | 新增偏好/对话 CRUD |
| 修改 | `client/api/__init__.py` | 新增 agent 路由，改造 events/item |
| 修改 | `client/main.py` | 注册 agent 路由 |
| 新建 | `client/services/__init__.py` | services 包 |
| 新建 | `client/services/vision.py` | 视觉模型 API 调用 |
| 新建 | `client/services/llm.py` | 语言模型 API 调用 |
| 新建 | `client/services/memory.py` | 用户偏好存取 |
| 新建 | `client/agents/__init__.py` | agents 包 |
| 新建 | `client/agents/fridge_agent.py` | 核心 Agent 编排 |

---

### Task 1: 配置与依赖

**Files:**
- Modify: `client/config.py`
- Modify: `client/.env`
- Modify: `client/requirements.txt`

- [ ] **Step 1: 更新 requirements.txt**

在 `client/requirements.txt` 末尾添加 httpx：

```
fastapi==0.115.0
uvicorn[standard]==0.32.0
sqlalchemy==2.0.36
psycopg2-binary==2.9.10
pgvector==0.3.6
pydantic==2.10.0
pydantic-settings==2.7.0
python-dotenv==1.0.1
httpx==0.28.1
```

- [ ] **Step 2: 更新 config.py**

替换 `client/config.py` 全部内容：

```python
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    DATABASE_URL: str = "postgresql://postgres:postgres@localhost:5432/fridge_db"

    VISION_API_KEY: str = ""
    VISION_API_URL: str = ""
    LLM_API_KEY: str = ""
    LLM_API_URL: str = ""
    DEFAULT_CITY: str = "北京"

    class Config:
        env_file = ".env"


settings = Settings()
```

- [ ] **Step 3: 更新 .env**

替换 `client/.env` 全部内容（API Key 留空，用户自行填写）：

```
DATABASE_URL=postgresql://postgres:181511@localhost:5432/fridge_db
VISION_API_KEY=
VISION_API_URL=
LLM_API_KEY=
LLM_API_URL=
DEFAULT_CITY=北京
```

- [ ] **Step 4: 安装依赖**

```bash
cd client && pip install httpx
```

- [ ] **Step 5: Commit**

```bash
git add client/config.py client/.env client/requirements.txt
git commit -m "feat: add API key config and httpx dependency"
```

---

### Task 2: 新增数据库模型

**Files:**
- Modify: `client/models/__init__.py`

- [ ] **Step 1: 更新 models/__init__.py**

替换 `client/models/__init__.py` 全部内容：

```python
import uuid
from datetime import datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import String, Float, DateTime, ForeignKey, CheckConstraint, func
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column

from database import Base


class Inventory(Base):
    __tablename__ = "inventory"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    device_id: Mapped[str] = mapped_column(String(50), nullable=False)
    category: Mapped[str] = mapped_column(String(50), nullable=False)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="IN_STOCK",
    )
    remain_ratio: Mapped[float] = mapped_column(Float, default=1.0)
    bbox = mapped_column(JSONB, nullable=True)
    feature_vector = mapped_column(Vector(512), nullable=True)
    agent_metadata = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=True)
    update_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=True)
    stored_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=True)

    __table_args__ = (
        CheckConstraint(
            "status IN ('IN_STOCK', 'OUT_PENDING', 'CONSUMED')",
            name="ck_inventory_status",
        ),
    )


class EventLog(Base):
    __tablename__ = "event_logs"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    inventory_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("inventory.id", ondelete="CASCADE"), nullable=False
    )
    event_type: Mapped[str] = mapped_column(String(20), nullable=False)
    confidence: Mapped[float] = mapped_column(Float, nullable=True)
    snapshot_path: Mapped[str] = mapped_column(String(255), nullable=True)
    create_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=True)


class UserPreference(Base):
    __tablename__ = "user_preferences"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[str] = mapped_column(String(50), nullable=False)
    preference_key: Mapped[str] = mapped_column(String(100), nullable=False)
    preference_value: Mapped[str] = mapped_column(nullable=False)
    source: Mapped[str] = mapped_column(String(20), default="chat")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=True)


class Conversation(Base):
    __tablename__ = "conversations"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(String(50), nullable=False)
    role: Mapped[str] = mapped_column(String(20), nullable=False)
    content: Mapped[str] = mapped_column(nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=True)
```

- [ ] **Step 2: 在 PostgreSQL 中执行 DDL**

```sql
-- 新增 stored_at 字段
ALTER TABLE inventory ADD COLUMN IF NOT EXISTS stored_at TIMESTAMP DEFAULT current_timestamp;

-- 用户偏好表
CREATE TABLE IF NOT EXISTS user_preferences (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id VARCHAR(50) NOT NULL,
    preference_key VARCHAR(100) NOT NULL,
    preference_value TEXT NOT NULL,
    source VARCHAR(20) DEFAULT 'chat',
    created_at TIMESTAMP DEFAULT current_timestamp,
    updated_at TIMESTAMP DEFAULT current_timestamp
);

-- 对话历史表
CREATE TABLE IF NOT EXISTS conversations (
    id BIGSERIAL PRIMARY KEY,
    user_id VARCHAR(50) NOT NULL,
    role VARCHAR(20) NOT NULL,
    content TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT current_timestamp
);
```

- [ ] **Step 3: Commit**

```bash
git add client/models/__init__.py
git commit -m "feat: add UserPreference, Conversation models and stored_at field"
```

---

### Task 3: Services 层 — 视觉模型

**Files:**
- New: `client/services/__init__.py`
- New: `client/services/vision.py`

- [ ] **Step 1: 创建 services 包**

新建 `client/services/__init__.py`：

```python
from services.vision import recognize_food
from services.llm import estimate_freshness, recommend_recipe
from services.memory import extract_preferences, save_preferences, get_preferences

__all__ = [
    "recognize_food",
    "estimate_freshness",
    "recommend_recipe",
    "extract_preferences",
    "save_preferences",
    "get_preferences",
]
```

- [ ] **Step 2: 创建 vision.py**

新建 `client/services/vision.py`：

```python
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
        logger.warning("视觉 API 未配置，跳过识别")
        return {"category": "unknown", "confidence": 0.0}

    try:
        resp = httpx.post(
            settings.VISION_API_URL,
            headers={"Authorization": f"Bearer {settings.VISION_API_KEY}"},
            json={
                "model": "qwen-vl-plus",
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
        result = json.loads(content.strip().strip("```json").strip("```").strip())
        return {"category": result.get("category", "unknown"), "confidence": result.get("confidence", 0.0)}
    except Exception as e:
        logger.error(f"视觉识别失败: {e}")
        return {"category": "unknown", "confidence": 0.0}
```

- [ ] **Step 3: Commit**

```bash
git add client/services/__init__.py client/services/vision.py
git commit -m "feat: add vision service for food recognition"
```

---

### Task 4: Services 层 — 语言模型

**Files:**
- New: `client/services/llm.py`

- [ ] **Step 1: 创建 llm.py**

新建 `client/services/llm.py`：

```python
import json
import logging

import httpx

from config import settings

logger = logging.getLogger(__name__)


def _call_llm(prompt: str) -> str:
    """通用 LLM 调用封装。"""
    resp = httpx.post(
        settings.LLM_API_URL,
        headers={"Authorization": f"Bearer {settings.LLM_API_KEY}"},
        json={
            "model": "qwen-plus",
            "messages": [{"role": "user", "content": prompt}],
        },
        timeout=60.0,
    )
    resp.raise_for_status()
    return resp.json()["choices"][0]["message"]["content"]


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
        logger.warning("LLM API 未配置，使用默认保鲜期")
        return {"shelf_life_days": 7, "storage_advice": "冷藏保存"}

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
        return {
            "shelf_life_days": result.get("shelf_life_days", 7),
            "storage_advice": result.get("storage_advice", "冷藏保存"),
        }
    except Exception as e:
        logger.error(f"保鲜期推算失败: {e}")
        return {"shelf_life_days": 7, "storage_advice": "冷藏保存"}


def recommend_recipe(inventory: list, preferences: list, city: str, season: str, user_message: str) -> str:
    """
    综合推荐食谱。
    入参：库存列表、用户偏好列表、城市、季节、用户消息
    返回：食谱推荐文本
    """
    if not settings.LLM_API_KEY or not settings.LLM_API_URL:
        return "推荐服务暂时不可用，请稍后再试。"

    inventory_text = "\n".join(
        f"- {item['category']}（剩余保鲜 {item['remain_days']} 天）"
        for item in inventory
    ) if inventory else "冰箱为空"

    preferences_text = "\n".join(f"- {p}" for p in preferences) if preferences else "无特殊偏好"

    prompt = f"""你是一个智能冰箱食材管理助手。

【环境信息】
城市：{city}，当前季节：{season}

【冰箱库存】
{inventory_text}

【用户偏好】
{preferences_text}

【用户消息】
{user_message}

请根据以上信息推荐合适的食谱，优先使用快过期的食材。回复要简洁实用。"""

    try:
        return _call_llm(prompt)
    except Exception as e:
        logger.error(f"食谱推荐失败: {e}")
        return "推荐服务暂时不可用，请稍后再试。"
```

- [ ] **Step 2: Commit**

```bash
git add client/services/llm.py
git commit -m "feat: add LLM service for freshness estimation and recipe recommendation"
```

---

### Task 5: Services 层 — 用户偏好记忆

**Files:**
- New: `client/services/memory.py`

- [ ] **Step 1: 创建 memory.py**

新建 `client/services/memory.py`：

```python
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
    try:
        content = _call_llm(EXTRACT_PROMPT.format(message=user_message))
        result = json.loads(content.strip().strip("```json").strip("```").strip())
        if isinstance(result, list):
            return result
        return []
    except Exception as e:
        logger.error(f"偏好提取失败: {e}")
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
```

- [ ] **Step 2: Commit**

```bash
git add client/services/memory.py
git commit -m "feat: add memory service for user preferences and conversations"
```

---

### Task 6: Agent 编排层

**Files:**
- New: `client/agents/__init__.py`
- New: `client/agents/fridge_agent.py`

- [ ] **Step 1: 创建 agents 包**

新建 `client/agents/__init__.py`：

```python
from agents.fridge_agent import FridgeAgent

__all__ = ["FridgeAgent"]
```

- [ ] **Step 2: 创建 fridge_agent.py**

新建 `client/agents/fridge_agent.py`：

```python
import time
import base64
import os
import logging
from datetime import datetime, timedelta
from typing import Optional

from sqlalchemy.orm import Session

from models import Inventory, EventLog
from services.vision import recognize_food
from services.llm import estimate_freshness, recommend_recipe, get_season
from services.memory import (
    extract_preferences,
    save_preferences,
    get_preferences,
    save_conversation,
    get_recent_conversations,
)
from config import settings

logger = logging.getLogger(__name__)

UPLOAD_DIR = "uploads"


def _save_crop_image(device_id: str, local_track_id: int, crop_b64: Optional[str] = None) -> Optional[str]:
    if not crop_b64:
        return None
    try:
        image_data = base64.b64decode(crop_b64)
    except Exception:
        return None
    os.makedirs(UPLOAD_DIR, exist_ok=True)
    filename = f"{device_id}_{local_track_id}_{int(time.time())}.jpg"
    filepath = os.path.join(UPLOAD_DIR, filename)
    with open(filepath, "wb") as f:
        f.write(image_data)
    return filepath


class FridgeAgent:
    def handle_item_in(self, db: Session, event, item) -> Optional[Inventory]:
        """
        事件驱动：食材入库。
        1. 保存图片
        2. 调 vision 识别食材
        3. 调 LLM 推算保鲜期
        4. 写入 inventory + event_logs
        """
        snapshot_path = _save_crop_image(event.device_id, item.local_track_id, item.crop_image)

        # 视觉识别
        if item.crop_image:
            vision_result = recognize_food(item.crop_image)
            category = vision_result["category"] if vision_result["confidence"] > 0.5 else item.category
        else:
            category = item.category
            vision_result = {"category": category, "confidence": item.confidence}

        # 保鲜期推算
        city = settings.DEFAULT_CITY
        season = get_season()
        freshness = estimate_freshness(category, city, season)

        expire_at = datetime.now() + timedelta(days=freshness["shelf_life_days"])

        inv = Inventory(
            device_id=event.device_id,
            category=category,
            status="IN_STOCK",
            remain_ratio=1.0,
            bbox=item.bbox,
            agent_metadata={
                "shelf_life_days": freshness["shelf_life_days"],
                "storage_advice": freshness["storage_advice"],
                "expire_at": expire_at.isoformat(),
                "vision_confidence": vision_result["confidence"],
            },
        )
        db.add(inv)
        db.flush()

        log = EventLog(
            inventory_id=inv.id,
            event_type="ITEM_IN",
            confidence=item.confidence,
            snapshot_path=snapshot_path,
        )
        db.add(log)
        db.commit()
        db.refresh(inv)
        return inv

    def handle_item_out(self, db: Session, event, item) -> Optional[Inventory]:
        """
        事件驱动：食材取出。
        1. 保存图片
        2. 按 category 匹配入库记录
        3. 更新状态为 OUT_PENDING
        """
        snapshot_path = _save_crop_image(event.device_id, item.local_track_id, item.crop_image)

        inv = (
            db.query(Inventory)
            .filter(
                Inventory.device_id == event.device_id,
                Inventory.category == item.category,
                Inventory.status == "IN_STOCK",
            )
            .order_by(Inventory.created_at.desc())
            .first()
        )
        if inv:
            inv.status = "OUT_PENDING"
            log = EventLog(
                inventory_id=inv.id,
                event_type="ITEM_OUT",
                confidence=item.confidence,
                snapshot_path=snapshot_path,
            )
            db.add(log)
            db.commit()
            db.refresh(inv)
        return inv

    def chat(self, db: Session, user_id: str, message: str, city: Optional[str] = None) -> dict:
        """
        用户请求驱动：对话式食谱推荐。
        1. 提取并保存偏好
        2. 查库存 + 保鲜期
        3. 查偏好 + 对话历史
        4. 组装 prompt → 调 LLM
        5. 保存对话记录
        返回: {"reply": "...", "detected_preferences": [...]}
        """
        city = city or settings.DEFAULT_CITY
        season = get_season()

        # 提取偏好
        new_prefs = extract_preferences(message)
        if new_prefs:
            save_preferences(db, user_id, new_prefs)

        # 保存用户消息
        save_conversation(db, user_id, "user", message)

        # 查库存
        items = db.query(Inventory).filter(Inventory.status == "IN_STOCK").all()
        inventory_list = []
        for item in items:
            metadata = item.agent_metadata or {}
            shelf_life = metadata.get("shelf_life_days", 7)
            expire_at_str = metadata.get("expire_at")
            if expire_at_str:
                expire_at = datetime.fromisoformat(expire_at_str)
                remain_days = max(0, (expire_at - datetime.now()).days)
            else:
                remain_days = shelf_life
            inventory_list.append({"category": item.category, "remain_days": remain_days})

        # 查偏好 + 对话历史
        preferences = get_preferences(db, user_id)
        recent_convs = get_recent_conversations(db, user_id, limit=10)

        # 调 LLM 推荐
        reply = recommend_recipe(inventory_list, preferences, city, season, message)

        # 保存助手回复
        save_conversation(db, user_id, "assistant", reply)

        return {"reply": reply, "detected_preferences": new_prefs}
```

- [ ] **Step 3: Commit**

```bash
git add client/agents/__init__.py client/agents/fridge_agent.py
git commit -m "feat: add FridgeAgent for event handling and recipe recommendation"
```

---

### Task 7: 新增 Schemas

**Files:**
- Modify: `client/schemas/__init__.py`

- [ ] **Step 1: 更新 schemas/__init__.py**

替换 `client/schemas/__init__.py` 全部内容：

```python
import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class ItemData(BaseModel):
    local_track_id: int
    category: str
    confidence: float
    bbox: list[int] = Field(..., min_length=4, max_length=4)
    crop_image: Optional[str] = None


class ItemEventRequest(BaseModel):
    device_id: str
    timestamp: int
    event_type: str = Field(..., pattern="^(ITEM_IN|ITEM_OUT|ITEM_MOVED|AGENT_UPDATE)$")
    data: list[ItemData]


class InventoryResponse(BaseModel):
    id: uuid.UUID
    device_id: str
    category: str
    status: str
    remain_ratio: float
    bbox: Optional[list] = None
    agent_metadata: Optional[dict] = None
    created_at: Optional[datetime] = None
    update_at: Optional[datetime] = None
    stored_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class EventLogResponse(BaseModel):
    id: int
    inventory_id: uuid.UUID
    event_type: str
    confidence: Optional[float] = None
    snapshot_path: Optional[str] = None
    create_at: Optional[datetime] = None

    class Config:
        from_attributes = True


# ---- Agent 相关 Schema ----

class ChatRequest(BaseModel):
    user_id: str
    message: str
    city: Optional[str] = None


class ChatResponse(BaseModel):
    reply: str
    detected_preferences: list


class RecognizeRequest(BaseModel):
    image: str


class RecognizeResponse(BaseModel):
    category: str
    confidence: float
    shelf_life_days: int
    storage_advice: str


class PreferenceResponse(BaseModel):
    id: uuid.UUID
    user_id: str
    preference_key: str
    preference_value: str
    source: Optional[str] = None
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True
```

- [ ] **Step 2: Commit**

```bash
git add client/schemas/__init__.py
git commit -m "feat: add Chat/Recognize/Preference schemas"
```

---

### Task 8: 新增 CRUD 操作

**Files:**
- Modify: `client/crud/__init__.py`

- [ ] **Step 1: 更新 crud/__init__.py**

替换 `client/crud/__init__.py` 全部内容：

```python
import time
import uuid
import base64
import os

from sqlalchemy.orm import Session
from typing import Optional
from models import Inventory, EventLog, UserPreference, Conversation

UPLOAD_DIR = "uploads"


def _save_crop_image(device_id: str, local_track_id: int, crop_b64: Optional[str] = None) -> Optional[str]:
    if not crop_b64:
        return None
    try:
        image_data = base64.b64decode(crop_b64)
    except Exception:
        return None
    os.makedirs(UPLOAD_DIR, exist_ok=True)
    filename = f"{device_id}_{local_track_id}_{int(time.time())}.jpg"
    filepath = os.path.join(UPLOAD_DIR, filename)
    with open(filepath, "wb") as f:
        f.write(image_data)
    return filepath


def handle_item_event(db: Session, event) -> list[Inventory]:
    results = []

    for item in event.data:
        snapshot_path = _save_crop_image(event.device_id, item.local_track_id, item.crop_image)

        if event.event_type == "ITEM_IN":
            inv = Inventory(
                device_id=event.device_id,
                category=item.category,
                status="IN_STOCK",
                remain_ratio=1.0,
                bbox=item.bbox,
            )
            db.add(inv)
            db.flush()

            log = EventLog(
                inventory_id=inv.id,
                event_type="ITEM_IN",
                confidence=item.confidence,
                snapshot_path=snapshot_path,
            )
            db.add(log)
            results.append(inv)

        elif event.event_type == "ITEM_OUT":
            inv = (
                db.query(Inventory)
                .filter(
                    Inventory.device_id == event.device_id,
                    Inventory.category == item.category,
                    Inventory.status == "IN_STOCK",
                )
                .order_by(Inventory.created_at.desc())
                .first()
            )
            if inv:
                inv.status = "OUT_PENDING"
                log = EventLog(
                    inventory_id=inv.id,
                    event_type="ITEM_OUT",
                    confidence=item.confidence,
                    snapshot_path=snapshot_path,
                )
                db.add(log)
                results.append(inv)

        elif event.event_type == "ITEM_MOVED":
            inv = (
                db.query(Inventory)
                .filter(
                    Inventory.device_id == event.device_id,
                    Inventory.category == item.category,
                    Inventory.status == "IN_STOCK",
                )
                .order_by(Inventory.created_at.desc())
                .first()
            )
            if inv:
                inv.bbox = item.bbox
                log = EventLog(
                    inventory_id=inv.id,
                    event_type="ITEM_MOVED",
                    confidence=item.confidence,
                    snapshot_path=snapshot_path,
                )
                db.add(log)
                results.append(inv)

        elif event.event_type == "AGENT_UPDATE":
            inv = (
                db.query(Inventory)
                .filter(
                    Inventory.device_id == event.device_id,
                    Inventory.category == item.category,
                    Inventory.status == "IN_STOCK",
                )
                .order_by(Inventory.created_at.desc())
                .first()
            )
            if inv:
                log = EventLog(
                    inventory_id=inv.id,
                    event_type="AGENT_UPDATE",
                    confidence=item.confidence,
                    snapshot_path=snapshot_path,
                )
                db.add(log)
                results.append(inv)

    db.commit()
    for inv in results:
        db.refresh(inv)
    return results


def get_inventory_list(db: Session, device_id: Optional[str] = None, status: Optional[str] = None):
    q = db.query(Inventory)
    if device_id:
        q = q.filter(Inventory.device_id == device_id)
    if status:
        q = q.filter(Inventory.status == status)
    return q.order_by(Inventory.update_at.desc()).all()


def get_inventory_by_id(db: Session, inventory_id: uuid.UUID):
    return db.query(Inventory).filter(Inventory.id == inventory_id).first()


def get_event_logs(db: Session, inventory_id: Optional[uuid.UUID] = None):
    q = db.query(EventLog)
    if inventory_id:
        q = q.filter(EventLog.inventory_id == inventory_id)
    return q.order_by(EventLog.create_at.desc()).all()


def get_preferences_list(db: Session, user_id: str):
    return db.query(UserPreference).filter(UserPreference.user_id == user_id).all()
```

- [ ] **Step 2: Commit**

```bash
git add client/crud/__init__.py
git commit -m "feat: add preferences CRUD function"
```

---

### Task 9: 新增 API 路由

**Files:**
- Modify: `client/api/__init__.py`

- [ ] **Step 1: 更新 api/__init__.py**

替换 `client/api/__init__.py` 全部内容：

```python
import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import Optional
from database import get_db
from schemas import (
    ItemEventRequest, InventoryResponse, EventLogResponse,
    ChatRequest, ChatResponse, RecognizeRequest, RecognizeResponse,
    PreferenceResponse,
)
from crud import handle_item_event, get_inventory_list, get_inventory_by_id, get_event_logs, get_preferences_list
from models import Inventory, EventLog
from agents import FridgeAgent

router = APIRouter()


@router.post("/events/item", response_model=list[InventoryResponse])
def receive_item_event(event: ItemEventRequest, db: Session = Depends(get_db)):
    try:
        agent = FridgeAgent()
        results = []
        for item in event.data:
            if event.event_type == "ITEM_IN":
                inv = agent.handle_item_in(db, event, item)
                if inv:
                    results.append(inv)
            elif event.event_type == "ITEM_OUT":
                inv = agent.handle_item_out(db, event, item)
                if inv:
                    results.append(inv)
            else:
                results_list = handle_item_event(db, event)
                results.extend(results_list)
                break
        return results
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"处理事件失败: {str(e)}")


@router.get("/inventory", response_model=list[InventoryResponse])
def list_inventory(
    device_id: Optional[str] = None,
    status: Optional[str] = None,
    db: Session = Depends(get_db),
):
    try:
        items = get_inventory_list(db, device_id=device_id, status=status)
        return items
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"查询库存失败: {str(e)}")


@router.get("/inventory/{inventory_id}", response_model=InventoryResponse)
def get_inventory_detail(inventory_id: uuid.UUID, db: Session = Depends(get_db)):
    try:
        item = get_inventory_by_id(db, inventory_id)
        if not item:
            raise HTTPException(status_code=404, detail="库存记录不存在")
        return item
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"查询库存详情失败: {str(e)}")


@router.get("/events", response_model=list[EventLogResponse])
def list_events(
    inventory_id: Optional[uuid.UUID] = None,
    db: Session = Depends(get_db),
):
    try:
        logs = get_event_logs(db, inventory_id=inventory_id)
        return logs
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"查询事件日志失败: {str(e)}")


# ---- Agent 路由 ----

@router.post("/agent/chat", response_model=ChatResponse)
def agent_chat(req: ChatRequest, db: Session = Depends(get_db)):
    try:
        agent = FridgeAgent()
        result = agent.chat(db, user_id=req.user_id, message=req.message, city=req.city)
        return result
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"对话失败: {str(e)}")


@router.post("/agent/recognize", response_model=RecognizeResponse)
def agent_recognize(req: RecognizeRequest, db: Session = Depends(get_db)):
    try:
        from services.vision import recognize_food
        from services.llm import estimate_freshness, get_season
        from config import settings

        vision_result = recognize_food(req.image)
        category = vision_result["category"]
        confidence = vision_result["confidence"]

        season = get_season()
        freshness = estimate_freshness(category, settings.DEFAULT_CITY, season)

        return RecognizeResponse(
            category=category,
            confidence=confidence,
            shelf_life_days=freshness["shelf_life_days"],
            storage_advice=freshness["storage_advice"],
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"识别失败: {str(e)}")


@router.get("/agent/preferences", response_model=list[PreferenceResponse])
def get_user_preferences(user_id: str, db: Session = Depends(get_db)):
    try:
        return get_preferences_list(db, user_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"查询偏好失败: {str(e)}")
```

- [ ] **Step 2: Commit**

```bash
git add client/api/__init__.py
git commit -m "feat: add agent chat/recognize/preferences routes"
```

---

### Task 10: 更新 main.py 和导出

**Files:**
- Modify: `client/main.py`

- [ ] **Step 1: 更新 main.py**

替换 `client/main.py` 全部内容：

```python
from fastapi import FastAPI

from database import engine, Base
from api import router

app = FastAPI(title="智能冰箱食材管理系统", version="2.0.0")

app.include_router(router, prefix="/api/v1")


@app.on_event("startup")
def on_startup():
    Base.metadata.create_all(bind=engine)


@app.get("/health")
def health_check():
    return {"status": "ok"}
```

- [ ] **Step 2: 验证服务启动**

```bash
cd client && python -m uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

访问 http://localhost:8000/docs 确认新增接口出现在文档中。

- [ ] **Step 3: Commit**

```bash
git add client/main.py
git commit -m "feat: update main.py for agent system"
```

---

### Task 11: 端到端验证

- [ ] **Step 1: 测试食材入库（ITEM_IN）**

```bash
curl -X POST http://localhost:8000/api/v1/events/item \
  -H "Content-Type: application/json" \
  -d '{
    "device_id": "luckfox_pico_pro_max",
    "timestamp": 1748044800000,
    "event_type": "ITEM_IN",
    "data": [
      {
        "local_track_id": 1,
        "category": "Apple",
        "confidence": 0.95,
        "bbox": [123, 124, 124, 511]
      }
    ]
  }'
```

预期：返回 inventory 列表，`agent_metadata` 包含 `shelf_life_days` 和 `expire_at`。

- [ ] **Step 2: 测试对话推荐**

```bash
curl -X POST http://localhost:8000/api/v1/agent/chat \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "user_001",
    "message": "我不吃辣，今晚吃什么？",
    "city": "上海"
  }'
```

预期：返回食谱推荐，`detected_preferences` 包含提取到的偏好。

- [ ] **Step 3: 测试偏好查询**

```bash
curl http://localhost:8000/api/v1/agent/preferences?user_id=user_001
```

预期：返回上一步提取到的偏好列表。

- [ ] **Step 4: 测试手动识别**

```bash
curl -X POST http://localhost:8000/api/v1/agent/recognize \
  -H "Content-Type: application/json" \
  -d '{"image": "base64_string_here"}'
```

预期：返回食材类别、置信度、保鲜期。

- [ ] **Step 5: Final Commit**

```bash
git add -A
git commit -m "feat: complete fridge agent system implementation"
```
