# 智能冰箱 Agent 系统设计文档

## 概述

在现有冰箱食材管理系统（FastAPI + PostgreSQL + pgvector）上构建 Agent 智能体，调用国产视觉大模型和语言大模型，实现食材自动识别、保鲜期推算、基于用户偏好的食谱推荐。

## 技术选型

| 组件 | 选型 | 说明 |
|------|------|------|
| 语言模型 | 国产大模型（Qwen/DeepSeek） | 食谱推荐、保鲜期推算、偏好提取 |
| 视觉模型 | 国产视觉大模型（Qwen-VL） | 食材识别 |
| 数据库 | PostgreSQL + pgvector | 已有，新增 2 张表 |
| 框架 | FastAPI | 已有 |

## 架构

```
设备/前端
    │
    ▼
┌─────────────────────────────────────────┐
│  API Layer (api/)                       │
│  ├── events/item  ← 设备回传事件        │
│  ├── agent/chat   ← 用户对话推荐        │
│  └── agent/recognize ← 手动识别         │
└────────────┬────────────────────────────┘
             │
             ▼
┌─────────────────────────────────────────┐
│  Agent Layer (agents/)                  │
│  └── fridge_agent.py                    │
│      ├── ITEM_IN → vision 识别 + 存储   │
│      ├── 对话 → LLM 推荐食谱            │
│      └── 管理用户偏好记忆               │
└────────────┬────────────────────────────┘
             │
             ▼
┌─────────────────────────────────────────┐
│  Services Layer (services/)             │
│  ├── vision.py   → 调国产视觉 API       │
│  ├── llm.py      → 调国产语言 API       │
│  └── memory.py   → 偏好存取             │
└────────────┬────────────────────────────┘
             │
             ▼
┌─────────────────────────────────────────┐
│  Data Layer                             │
│  ├── inventory (已有)                   │
│  ├── event_logs (已有)                  │
│  ├── user_preferences (新增)            │
│  └── conversations (新增)               │
└─────────────────────────────────────────┘
```

## 目录结构

```
client/
├── agents/
│   ├── __init__.py
│   └── fridge_agent.py      # 核心 Agent 编排
├── services/
│   ├── __init__.py
│   ├── vision.py            # 视觉模型 API 调用
│   ├── llm.py               # 语言模型 API 调用
│   └── memory.py            # 用户偏好存取
├── models/                  # 新增 UserPreference, Conversation
├── schemas/                 # 新增 ChatRequest/Response 等
├── api/                     # 新增 agent 相关接口
├── crud/                    # 新增 agent 相关 CRUD
├── config.py                # 新增 API Key 配置
├── database.py
└── main.py
```

## 新增数据库表

### user_preferences（用户偏好表）

```sql
create table user_preferences (
    id uuid primary key default uuid_generate_v4(),
    user_id varchar(50) not null,
    preference_key varchar(100) not null,   -- taste/allergy/dislike/prefer
    preference_value text not null,         -- 如 "不吃辣" "花生过敏"
    source varchar(20) default 'chat',      -- chat(对话学习)/manual(手动设置)
    created_at timestamp default current_timestamp,
    updated_at timestamp default current_timestamp
);
```

偏好类型：
- `taste`：口味偏好（喜欢清淡、爱吃辣）
- `allergy`：过敏信息（花生过敏、海鲜过敏）
- `dislike`：忌口（不吃香菜、不吃内脏）
- `prefer`：饮食偏好（素食、低碳水）

### conversations（对话历史表）

```sql
create table conversations (
    id bigserial primary key,
    user_id varchar(50) not null,
    role varchar(20) not null,              -- 'user' / 'assistant'
    content text not null,
    created_at timestamp default current_timestamp
);
```

### inventory 表新增字段

```sql
alter table inventory add column stored_at timestamp default current_timestamp;
```

用于记录入库时间，配合保鲜期计算。

## Services 层

### services/vision.py

```python
async def recognize_food(image_base64: str) -> dict:
    """
    调用国产视觉大模型 API
    入参：base64 图片
    返回：{ "category": "西红柿", "confidence": 0.92 }
    """
```

### services/llm.py

```python
async def estimate_freshness(category: str, city: str, season: str) -> dict:
    """
    推算食材保鲜期
    返回：{ "shelf_life_days": 7, "storage_advice": "冷藏保存" }
    """

async def recommend_recipe(inventory: list, preferences: list,
                           city: str, season: str, user_message: str) -> str:
    """
    综合推荐食谱
    入参：库存列表、用户偏好、城市、季节、用户消息
    返回：食谱推荐文本
    """
```

Prompt 模板：

```
你是一个智能冰箱食材管理助手。

【环境信息】
城市：{city}，当前季节：{season}

【冰箱库存】
{inventory_list}  -- 包含食材名、剩余保鲜天数

【用户偏好】
{preferences}     -- 如：不吃辣、花生过敏

【对话历史】
{recent_messages}  -- 最近10条

【用户消息】
{user_message}

请根据以上信息推荐合适的食谱，优先使用快过期的食材。回复要简洁实用。
```

### services/memory.py

```python
async def extract_preferences(user_message: str, llm) -> list[dict]:
    """
    从对话中提取偏好（调 LLM 判断）
    如 "我不吃辣" → [{ "key": "dislike", "value": "辣味" }]
    """

async def save_preferences(db, user_id: str, preferences: list): ...

async def get_preferences(db, user_id: str) -> list[str]:
    """
    返回该用户所有偏好，组装为 prompt 片段
    如 ["不吃辣", "花生过敏", "偏好清淡"]
    """
```

## Agent 编排

### agents/fridge_agent.py

```python
class FridgeAgent:
    async def handle_item_in(self, db, event, item):
        """
        事件驱动：食材入库
        1. 调 vision 识别食材类别
        2. 调 LLM 推算保鲜期
        3. 写入 inventory（feature_vector + agent_metadata）
        """

    async def handle_item_out(self, db, event, item):
        """
        事件驱动：食材取出
        1. 调 vision 识别
        2. 向量匹配找到对应入库记录
        3. 更新状态为 OUT_PENDING
        """

    async def chat(self, db, user_id: str, message: str, city: str) -> str:
        """
        用户请求驱动：对话式食谱推荐
        1. 提取并保存用户偏好（如有新偏好）
        2. 查库存 + 保鲜期
        3. 查用户偏好
        4. 查对话历史（最近 10 条）
        5. 组装 prompt → 调 LLM → 返回推荐
        """
```

## API 接口

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/v1/events/item` | 设备回传事件（已有，内部改调 Agent） |
| POST | `/api/v1/agent/chat` | 对话式食谱推荐 |
| POST | `/api/v1/agent/recognize` | 手动上传图片识别食材 |
| GET | `/api/v1/agent/preferences` | 获取用户偏好列表 |

### POST /api/v1/agent/chat

请求：
```json
{
    "user_id": "user_001",
    "message": "今晚吃什么？",
    "city": "上海"
}
```

响应：
```json
{
    "reply": "你冰箱里的西红柿还有3天就过期了，上海最近闷热，建议做个西红柿蛋花汤，清淡又营养。",
    "detected_preferences": []
}
```

### POST /api/v1/agent/recognize

请求：
```json
{
    "image": "base64_string..."
}
```

响应：
```json
{
    "category": "西红柿",
    "confidence": 0.92,
    "shelf_life_days": 7,
    "storage_advice": "冷藏保存"
}
```

### Schema 定义

```python
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
```

## 配置（config.py 新增）

```python
VISION_API_KEY: str
VISION_API_URL: str
LLM_API_KEY: str
LLM_API_URL: str
DEFAULT_CITY: str = "北京"
```

通过 `.env` 文件管理。

## 环境信息

| 信息 | 获取方式 |
|------|---------|
| 城市 | 前端传入 / config.py 默认值 |
| 季节 | 根据当前日期自动推算（春/夏/秋/冬） |
| 保鲜期 | LLM 根据食材类型 + 城市 + 季节动态推算 |

## 错误处理

| 场景 | 处理方式 |
|------|---------|
| 视觉 API 调用失败 | 记录日志，category 标记为 "unknown"，不阻塞入库 |
| 语言 API 调用失败 | 返回友好提示 "推荐服务暂时不可用，请稍后再试" |
| 向量匹配无结果 | 退化为按 category 匹配 |
| 对话上下文过长 | 只保留最近 10 条，截断早期对话 |

## 完整数据流

### 食材入库

```
设备 POST /api/v1/events/item (ITEM_IN)
    ↓
API 层接收，创建 FridgeAgent
    ↓
Agent.handle_item_in()
    ├── 保存 crop_image 文件
    ├── 调 vision API → 识别为 "西红柿" (0.92)
    ├── 调 LLM 推算保鲜期 → 7天
    ├── 写入 inventory: {
    │       category: "西红柿",
    │       feature_vector: [视觉向量],
    │       agent_metadata: { shelf_life_days: 7, expire_at: "2026-05-31" }
    │   }
    └── 写入 event_logs
    ↓
返回 [inventory] 给设备
```

### 食谱推荐

```
前端 POST /api/v1/agent/chat { user_id, message, city }
    ↓
Agent.chat()
    ├── 从 message 提取偏好 → 存入 user_preferences
    ├── 查 inventory (IN_STOCK)
    ├── 计算保鲜: 西红柿剩3天, 鸡蛋剩10天...
    ├── 查 user_preferences: ["不吃辣", "偏好清淡"]
    ├── 查 conversations 最近10条
    ├── 组装 prompt → 调 LLM API
    ├── 存入 conversations (user + assistant)
    └── 返回回复
    ↓
前端展示推荐结果
```
