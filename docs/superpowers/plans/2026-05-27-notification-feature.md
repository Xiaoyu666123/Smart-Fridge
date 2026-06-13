# 临期食物消息提醒功能 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 为智能冰箱食材管理系统新增临期食物消息提醒功能，用户通过导航栏铃铛查看未读消息。

**Architecture:** 后端新增 `notifications` 和 `category_thresholds` 两张表，提供 CRUD API。前端在 Layout 导航栏添加铃铛图标 + 弹窗组件。消息在用户请求时实时生成，基于库存中 `agent_metadata.expire_at` 字段与类别的临期阈值比对。

**Tech Stack:** FastAPI, SQLAlchemy 2.0, PostgreSQL, Vue 3, Element Plus, Pinia, Axios

---

## File Structure

### Backend (client/)

| File | Action | Responsibility |
|---|---|---|
| `client/models/models.py` | Modify | 新增 `Notification` 和 `CategoryThreshold` 模型 |
| `client/models/__init__.py` | Modify | 导出新模型 |
| `client/schemas/schemas.py` | Modify | 新增通知和阈值的 Pydantic schemas |
| `client/schemas/__init__.py` | Modify | 导出新 schemas |
| `client/crud/crud.py` | Modify | 新增通知和阈值的 CRUD 函数 |
| `client/crud/__init__.py` | Modify | 导出新 CRUD 函数 |
| `client/api/api.py` | Modify | 新增通知和阈值的 API 路由 |
| `client/api/__init__.py` | Modify | 导入新 schemas/crud（如需要） |

### Frontend (web/)

| File | Action | Responsibility |
|---|---|---|
| `web/src/api/notification.ts` | Create | 通知相关 API 调用 |
| `web/src/components/NotificationBell.vue` | Create | 铃铛图标 + 弹窗组件 |
| `web/src/components/Layout.vue` | Modify | 在导航栏右侧嵌入 NotificationBell |

---

### Task 1: 新增数据库模型

**Files:**
- Modify: `client/models/models.py:100-101`（在 User 类之后追加）
- Modify: `client/models/__init__.py`

- [ ] **Step 1: 在 models.py 末尾追加两个新模型**

在 `client/models/models.py` 文件末尾（第 101 行之后）追加：

```python
class Notification(Base):
    __tablename__ = "notifications"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    type: Mapped[str] = mapped_column(String(50), nullable=False, default="expiry_warning")
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    content: Mapped[str] = mapped_column(nullable=False)
    related_item_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("inventory.id", ondelete="CASCADE"), nullable=True)
    is_read: Mapped[bool] = mapped_column(default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=True)

    __table_args__ = (
        UniqueConstraint("user_id", "related_item_id", name="uq_notification_user_item"),
    )


class CategoryThreshold(Base):
    __tablename__ = "category_thresholds"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    category: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    days_before_expiry: Mapped[int] = mapped_column(nullable=False, default=5)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=True)
```

需要在文件顶部 imports 中添加 `UniqueConstraint`：

```python
from sqlalchemy import String, Float, DateTime, ForeignKey, CheckConstraint, UniqueConstraint, func
```

- [ ] **Step 2: 更新 models/__init__.py 导出**

将 `client/models/__init__.py` 替换为：

```python
from models import Inventory, EventLog, AgentTrace, Notification, CategoryThreshold

__all__ = ["Inventory", "EventLog", "AgentTrace", "Notification", "CategoryThreshold"]
```

- [ ] **Step 3: 验证模型能被正确导入**

```bash
cd C:/Users/86134/PycharmProjects/luckfox_web/client && python -c "from models import Notification, CategoryThreshold; print('OK')"
```

- [ ] **Step 4: Commit**

```bash
git add client/models/models.py client/models/__init__.py
git commit -m "feat: add Notification and CategoryThreshold models"
```

---

### Task 2: 新增 Pydantic Schemas

**Files:**
- Modify: `client/schemas/schemas.py:208`（在文件末尾追加）
- Modify: `client/schemas/__init__.py`

- [ ] **Step 1: 在 schemas.py 末尾追加通知和阈值 schemas**

在 `client/schemas/schemas.py` 末尾追加：

```python
# ---- Notification 相关 Schema ----

class NotificationResponse(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    type: str
    title: str
    content: str
    related_item_id: Optional[uuid.UUID] = None
    is_read: bool
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class NotificationCountResponse(BaseModel):
    unread_count: int


class CategoryThresholdResponse(BaseModel):
    id: uuid.UUID
    category: str
    days_before_expiry: int
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class CategoryThresholdUpdateRequest(BaseModel):
    days_before_expiry: int = Field(..., ge=1, le=365)
```

- [ ] **Step 2: 更新 schemas/__init__.py 导出**

在 `client/schemas/__init__.py` 的 import 中追加新 schemas。当前文件只有一个 re-export，需要改为显式导入。查看当前内容后，替换为：

```python
from schemas.schemas import (
    ItemData, ItemEventRequest,
    InventoryResponse, InventoryCreateRequest, InventoryUpdateRequest,
    EventLogResponse,
    ChatRequest, ChatResponse, RecognizeRequest, RecognizeResponse,
    PreferenceResponse, PreferenceAddRequest,
    TraceStepResponse, TraceSummaryResponse, TraceDetailResponse,
    EnvironmentResponse, LogEntryResponse,
    RegisterRequest, LoginRequest, TokenResponse, UserResponse,
    NotificationResponse, NotificationCountResponse,
    CategoryThresholdResponse, CategoryThresholdUpdateRequest,
)

__all__ = [
    "ItemData", "ItemEventRequest",
    "InventoryResponse", "InventoryCreateRequest", "InventoryUpdateRequest",
    "EventLogResponse",
    "ChatRequest", "ChatResponse", "RecognizeRequest", "RecognizeResponse",
    "PreferenceResponse", "PreferenceAddRequest",
    "TraceStepResponse", "TraceSummaryResponse", "TraceDetailResponse",
    "EnvironmentResponse", "LogEntryResponse",
    "RegisterRequest", "LoginRequest", "TokenResponse", "UserResponse",
    "NotificationResponse", "NotificationCountResponse",
    "CategoryThresholdResponse", "CategoryThresholdUpdateRequest",
]
```

- [ ] **Step 3: Commit**

```bash
git add client/schemas/schemas.py client/schemas/__init__.py
git commit -m "feat: add notification and threshold Pydantic schemas"
```

---

### Task 3: 新增 CRUD 函数

**Files:**
- Modify: `client/crud/crud.py:339`（在文件末尾追加）
- Modify: `client/crud/__init__.py`

- [ ] **Step 1: 在 crud.py 末尾追加通知和阈值 CRUD 函数**

在 `client/crud/crud.py` 末尾追加：

```python
# ---- Notification CRUD ----

def generate_expiry_notifications(db: Session, user_id: uuid.UUID) -> list:
    """为指定用户生成临期食物通知。扫描库存中临期和已过期的食物，为用户创建通知记录。"""
    from datetime import datetime, timedelta
    from models import Notification, CategoryThreshold

    now = datetime.now()

    # 获取所有类别的临期阈值
    thresholds = db.query(CategoryThreshold).all()
    threshold_map = {t.category: t.days_before_expiry for t in thresholds}
    default_threshold = threshold_map.get("other", 5)

    # 查询所有在库且有 expire_at 的食材
    items = (
        db.query(Inventory)
        .filter(Inventory.status == "IN_STOCK")
        .all()
    )

    new_notifications = []
    for item in items:
        metadata = item.agent_metadata or {}
        expire_at_str = metadata.get("expire_at")
        if not expire_at_str:
            continue

        try:
            expire_at = datetime.fromisoformat(expire_at_str)
        except (ValueError, TypeError):
            continue

        days_remaining = (expire_at - now).days
        threshold = threshold_map.get(item.category, default_threshold)

        if days_remaining <= threshold:
            # 检查是否已存在该用户对该食材的通知
            existing = (
                db.query(Notification)
                .filter(
                    Notification.user_id == user_id,
                    Notification.related_item_id == item.id,
                )
                .first()
            )
            if existing:
                continue

            if days_remaining < 0:
                title = f"{item.category} 已过期"
                content = f"该食材已过期 {-days_remaining} 天，请及时处理"
            elif days_remaining == 0:
                title = f"{item.category} 今天过期"
                content = f"该食材今天过期，请尽快使用"
            else:
                title = f"{item.category} 即将过期"
                content = f"该食材还有 {days_remaining} 天过期"

            notification = Notification(
                user_id=user_id,
                type="expiry_warning",
                title=title,
                content=content,
                related_item_id=item.id,
            )
            db.add(notification)
            new_notifications.append(notification)

    if new_notifications:
        db.commit()
        for n in new_notifications:
            db.refresh(n)

    return new_notifications


def get_user_notifications(db: Session, user_id: uuid.UUID) -> list:
    """获取用户的所有通知，按创建时间降序排列。"""
    from models import Notification
    return (
        db.query(Notification)
        .filter(Notification.user_id == user_id)
        .order_by(Notification.created_at.desc())
        .all()
    )


def get_unread_count(db: Session, user_id: uuid.UUID) -> int:
    """获取用户未读通知数量。"""
    from models import Notification
    return (
        db.query(Notification)
        .filter(Notification.user_id == user_id, Notification.is_read == False)
        .count()
    )


def mark_notification_read(db: Session, notification_id: uuid.UUID, user_id: uuid.UUID) -> bool:
    """标记单条通知为已读。"""
    from models import Notification
    notification = (
        db.query(Notification)
        .filter(Notification.id == notification_id, Notification.user_id == user_id)
        .first()
    )
    if not notification:
        return False
    notification.is_read = True
    db.commit()
    return True


def mark_all_read(db: Session, user_id: uuid.UUID) -> int:
    """标记用户所有未读通知为已读，返回更新数量。"""
    from models import Notification
    count = (
        db.query(Notification)
        .filter(Notification.user_id == user_id, Notification.is_read == False)
        .update({"is_read": True})
    )
    db.commit()
    return count


# ---- CategoryThreshold CRUD ----

def get_all_thresholds(db: Session) -> list:
    """获取所有类别的临期阈值。"""
    from models import CategoryThreshold
    return db.query(CategoryThreshold).order_by(CategoryThreshold.category).all()


def update_threshold(db: Session, threshold_id: uuid.UUID, days_before_expiry: int):
    """更新指定类别的临期阈值。"""
    from models import CategoryThreshold
    threshold = db.query(CategoryThreshold).filter(CategoryThreshold.id == threshold_id).first()
    if not threshold:
        return None
    threshold.days_before_expiry = days_before_expiry
    db.commit()
    db.refresh(threshold)
    return threshold


def seed_default_thresholds(db: Session):
    """初始化默认的类别临期阈值（如表为空）。"""
    from models import CategoryThreshold
    existing = db.query(CategoryThreshold).count()
    if existing > 0:
        return
    defaults = [
        ("vegetables", 3),
        ("fruit", 3),
        ("meat", 2),
        ("seafood", 2),
        ("dairy", 3),
        ("grains", 7),
        ("other", 5),
    ]
    for category, days in defaults:
        db.add(CategoryThreshold(category=category, days_before_expiry=days))
    db.commit()
```

- [ ] **Step 2: 更新 crud/__init__.py 导出**

将 `client/crud/__init__.py` 替换为：

```python
import time
import uuid
import base64
import os

from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import Optional
from models import Inventory, EventLog, UserPreference, Conversation, AgentTrace, User

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


def get_inventory_list(db: Session, device_id: Optional[str] = None, status: Optional[str] = None, category: Optional[str] = None):
    q = db.query(Inventory)
    if device_id:
        q = q.filter(Inventory.device_id == device_id)
    if status:
        q = q.filter(Inventory.status == status)
    if category:
        q = q.filter(Inventory.category == category)
    return q.order_by(Inventory.update_at.desc()).all()


def get_inventory_by_id(db: Session, inventory_id: uuid.UUID):
    return db.query(Inventory).filter(Inventory.id == inventory_id).first()


def get_event_logs(db: Session, inventory_id: Optional[uuid.UUID] = None):
    q = db.query(EventLog)
    if inventory_id:
        q = q.filter(EventLog.inventory_id == inventory_id)
    return q.order_by(EventLog.create_at.desc()).all()


def get_conversations(db: Session, user_id: str, limit: int = 100, offset: int = 0):
    """获取用户对话历史。"""
    return (
        db.query(Conversation)
        .filter(Conversation.user_id == user_id)
        .order_by(Conversation.created_at.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )


def create_user(db: Session, username: str, password_hash: str, role: str = "user") -> User:
    user = User(username=username, password_hash=password_hash, role=role)
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def get_user_by_username(db: Session, username: str) -> Optional[User]:
    return db.query(User).filter(User.username == username).first()


def get_preferences_list(db: Session, user_id: str):
    return db.query(UserPreference).filter(UserPreference.user_id == user_id).all()


def add_preference(db: Session, user_id: str, preference_key: str, preference_value: str):
    exists = (
        db.query(UserPreference)
        .filter(
            UserPreference.user_id == user_id,
            UserPreference.preference_key == preference_key,
            UserPreference.preference_value == preference_value,
        )
        .first()
    )
    if exists:
        return exists
    pref = UserPreference(
        user_id=user_id,
        preference_key=preference_key,
        preference_value=preference_value,
        source="manual",
    )
    db.add(pref)
    db.commit()
    db.refresh(pref)
    return pref


def delete_preference(db: Session, preference_id: uuid.UUID):
    pref = db.query(UserPreference).filter(UserPreference.id == preference_id).first()
    if pref:
        db.delete(pref)
        db.commit()
    return pref


# ---- Trace CRUD ----

def save_trace(db: Session, trace_id: uuid.UUID, agent_type: str, step_order: int,
               tool_name: str, tool_input: Optional[dict], tool_output: Optional[dict],
               status: str, duration_ms: Optional[int], device_id: Optional[str] = None):
    trace = AgentTrace(
        trace_id=trace_id,
        agent_type=agent_type,
        step_order=step_order,
        tool_name=tool_name,
        tool_input=tool_input,
        tool_output=tool_output,
        status=status,
        duration_ms=duration_ms,
        device_id=device_id,
    )
    db.add(trace)
    db.flush()


def get_trace_list(db: Session, agent_type: Optional[str] = None,
                   device_id: Optional[str] = None,
                   limit: int = 20, offset: int = 0):
    subq = (
        db.query(
            AgentTrace.trace_id,
            AgentTrace.agent_type,
            AgentTrace.device_id,
            func.count(AgentTrace.id).label("step_count"),
            func.sum(AgentTrace.duration_ms).label("total_duration_ms"),
            func.min(AgentTrace.created_at).label("created_at"),
        )
        .group_by(AgentTrace.trace_id, AgentTrace.agent_type, AgentTrace.device_id)
    )
    if agent_type:
        subq = subq.filter(AgentTrace.agent_type == agent_type)
    if device_id:
        subq = subq.filter(AgentTrace.device_id == device_id)
    subq = subq.order_by(func.min(AgentTrace.created_at).desc())
    subq = subq.offset(offset).limit(limit)
    return subq.all()


def save_log(db: Session, source: str, event_type: str, status: str, detail: dict = None):
    """写入系统日志到 agent_traces 表（作为通用日志记录）。"""
    trace_id = uuid.uuid4()
    log = AgentTrace(
        trace_id=trace_id,
        agent_type=event_type,
        step_order=1,
        tool_name=source,
        tool_input=None,
        tool_output=detail,
        status=status,
        duration_ms=None,
        device_id=None,
    )
    db.add(log)
    db.flush()


def get_unified_logs(db: Session, source: Optional[str] = None,
                     event_type: Optional[str] = None,
                     status: Optional[str] = None,
                     limit: int = 50, offset: int = 0):
    """合并 event_logs 和 agent_traces 为统一时间线。"""
    results = []

    if source is None or source == "event":
        q = db.query(EventLog)
        if event_type:
            q = q.filter(EventLog.event_type == event_type)
        rows = q.order_by(EventLog.create_at.desc()).offset(offset).limit(limit).all()
        for r in rows:
            results.append({
                "id": f"evt-{r.id}",
                "source": "event",
                "event_type": r.event_type,
                "status": "SUCCESS",
                "detail": {
                    "inventory_id": str(r.inventory_id),
                    "confidence": r.confidence,
                    "snapshot_path": r.snapshot_path,
                },
                "created_at": r.create_at.isoformat() if r.create_at else None,
            })

    if source is None or source == "trace":
        q = db.query(AgentTrace)
        if event_type:
            q = q.filter(AgentTrace.agent_type == event_type)
        if status:
            q = q.filter(AgentTrace.status == status)
        rows = q.order_by(AgentTrace.created_at.desc()).offset(offset).limit(limit).all()
        for r in rows:
            results.append({
                "id": f"trc-{r.id}",
                "source": "trace",
                "event_type": r.agent_type,
                "status": r.status,
                "detail": {
                    "trace_id": str(r.trace_id),
                    "step_order": r.step_order,
                    "tool_name": r.tool_name,
                    "tool_input": r.tool_input,
                    "tool_output": r.tool_output,
                    "duration_ms": r.duration_ms,
                    "device_id": r.device_id,
                },
                "created_at": r.created_at.isoformat() if r.created_at else None,
            })

    results.sort(key=lambda x: x["created_at"] or "", reverse=True)
    return results[offset:offset + limit]


def get_trace_detail(db: Session, trace_id: uuid.UUID):
    rows = (
        db.query(AgentTrace)
        .filter(AgentTrace.trace_id == trace_id)
        .order_by(AgentTrace.step_order)
        .all()
    )
    if not rows:
        return None
    return {
        "trace_id": str(trace_id),
        "agent_type": rows[0].agent_type,
        "device_id": rows[0].device_id,
        "steps": rows,
    }


# ---- Notification CRUD ----

def generate_expiry_notifications(db: Session, user_id: uuid.UUID) -> list:
    """为指定用户生成临期食物通知。扫描库存中临期和已过期的食物，为用户创建通知记录。"""
    from datetime import datetime, timedelta
    from models import Notification, CategoryThreshold

    now = datetime.now()

    # 获取所有类别的临期阈值
    thresholds = db.query(CategoryThreshold).all()
    threshold_map = {t.category: t.days_before_expiry for t in thresholds}
    default_threshold = threshold_map.get("other", 5)

    # 查询所有在库且有 expire_at 的食材
    items = (
        db.query(Inventory)
        .filter(Inventory.status == "IN_STOCK")
        .all()
    )

    new_notifications = []
    for item in items:
        metadata = item.agent_metadata or {}
        expire_at_str = metadata.get("expire_at")
        if not expire_at_str:
            continue

        try:
            expire_at = datetime.fromisoformat(expire_at_str)
        except (ValueError, TypeError):
            continue

        days_remaining = (expire_at - now).days
        threshold = threshold_map.get(item.category, default_threshold)

        if days_remaining <= threshold:
            # 检查是否已存在该用户对该食材的通知
            existing = (
                db.query(Notification)
                .filter(
                    Notification.user_id == user_id,
                    Notification.related_item_id == item.id,
                )
                .first()
            )
            if existing:
                continue

            if days_remaining < 0:
                title = f"{item.category} 已过期"
                content = f"该食材已过期 {-days_remaining} 天，请及时处理"
            elif days_remaining == 0:
                title = f"{item.category} 今天过期"
                content = f"该食材今天过期，请尽快使用"
            else:
                title = f"{item.category} 即将过期"
                content = f"该食材还有 {days_remaining} 天过期"

            notification = Notification(
                user_id=user_id,
                type="expiry_warning",
                title=title,
                content=content,
                related_item_id=item.id,
            )
            db.add(notification)
            new_notifications.append(notification)

    if new_notifications:
        db.commit()
        for n in new_notifications:
            db.refresh(n)

    return new_notifications


def get_user_notifications(db: Session, user_id: uuid.UUID) -> list:
    """获取用户的所有通知，按创建时间降序排列。"""
    from models import Notification
    return (
        db.query(Notification)
        .filter(Notification.user_id == user_id)
        .order_by(Notification.created_at.desc())
        .all()
    )


def get_unread_count(db: Session, user_id: uuid.UUID) -> int:
    """获取用户未读通知数量。"""
    from models import Notification
    return (
        db.query(Notification)
        .filter(Notification.user_id == user_id, Notification.is_read == False)
        .count()
    )


def mark_notification_read(db: Session, notification_id: uuid.UUID, user_id: uuid.UUID) -> bool:
    """标记单条通知为已读。"""
    from models import Notification
    notification = (
        db.query(Notification)
        .filter(Notification.id == notification_id, Notification.user_id == user_id)
        .first()
    )
    if not notification:
        return False
    notification.is_read = True
    db.commit()
    return True


def mark_all_read(db: Session, user_id: uuid.UUID) -> int:
    """标记用户所有未读通知为已读，返回更新数量。"""
    from models import Notification
    count = (
        db.query(Notification)
        .filter(Notification.user_id == user_id, Notification.is_read == False)
        .update({"is_read": True})
    )
    db.commit()
    return count


# ---- CategoryThreshold CRUD ----

def get_all_thresholds(db: Session) -> list:
    """获取所有类别的临期阈值。"""
    from models import CategoryThreshold
    return db.query(CategoryThreshold).order_by(CategoryThreshold.category).all()


def update_threshold(db: Session, threshold_id: uuid.UUID, days_before_expiry: int):
    """更新指定类别的临期阈值。"""
    from models import CategoryThreshold
    threshold = db.query(CategoryThreshold).filter(CategoryThreshold.id == threshold_id).first()
    if not threshold:
        return None
    threshold.days_before_expiry = days_before_expiry
    db.commit()
    db.refresh(threshold)
    return threshold


def seed_default_thresholds(db: Session):
    """初始化默认的类别临期阈值（如表为空）。"""
    from models import CategoryThreshold
    existing = db.query(CategoryThreshold).count()
    if existing > 0:
        return
    defaults = [
        ("vegetables", 3),
        ("fruit", 3),
        ("meat", 2),
        ("seafood", 2),
        ("dairy", 3),
        ("grains", 7),
        ("other", 5),
    ]
    for category, days in defaults:
        db.add(CategoryThreshold(category=category, days_before_expiry=days))
    db.commit()
```

- [ ] **Step 3: Commit**

```bash
git add client/crud/crud.py client/crud/__init__.py
git commit -m "feat: add notification and threshold CRUD functions"
```

---

### Task 4: 新增 API 路由

**Files:**
- Modify: `client/api/api.py:494`（在文件末尾追加）

- [ ] **Step 1: 更新 api.py 的 imports**

在 `client/api/api.py` 第 9-16 行的 schemas import 中追加新 schemas：

```python
from schemas import (
    ItemEventRequest, InventoryResponse, InventoryCreateRequest, InventoryUpdateRequest,
    EventLogResponse,
    ChatRequest, ChatResponse, RecognizeRequest, RecognizeResponse,
    PreferenceResponse, PreferenceAddRequest, TraceSummaryResponse, TraceDetailResponse,
    EnvironmentResponse, LogEntryResponse,
    RegisterRequest, LoginRequest, TokenResponse, UserResponse,
    NotificationResponse, NotificationCountResponse,
    CategoryThresholdResponse, CategoryThresholdUpdateRequest,
)
```

在第 17 行的 crud import 中追加新函数：

```python
from crud import (
    handle_item_event, get_inventory_list, get_inventory_by_id, get_event_logs,
    get_preferences_list, add_preference, delete_preference, get_trace_list,
    get_trace_detail, get_unified_logs, get_conversations, create_user,
    get_user_by_username, save_log,
    generate_expiry_notifications, get_user_notifications, get_unread_count,
    mark_notification_read, mark_all_read,
    get_all_thresholds, update_threshold, seed_default_thresholds,
)
```

- [ ] **Step 2: 在 api.py 末尾追加通知和阈值路由**

在 `client/api/api.py` 末尾追加：

```python
# ---- Notification 路由 ----

@router.get("/notifications", response_model=list[NotificationResponse])
def list_notifications(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    try:
        generate_expiry_notifications(db, user.id)
        notifications = get_user_notifications(db, user.id)
        return notifications
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"查询通知失败: {str(e)}")


@router.get("/notifications/count", response_model=NotificationCountResponse)
def notification_count(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    try:
        generate_expiry_notifications(db, user.id)
        count = get_unread_count(db, user.id)
        return NotificationCountResponse(unread_count=count)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"查询通知数量失败: {str(e)}")


@router.put("/notifications/{notification_id}/read")
def read_notification(notification_id: uuid.UUID, db: Session = Depends(get_db),
                     user: User = Depends(get_current_user)):
    try:
        success = mark_notification_read(db, notification_id, user.id)
        if not success:
            raise HTTPException(status_code=404, detail="通知不存在")
        return {"detail": "已标记已读"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"标记已读失败: {str(e)}")


@router.put("/notifications/read-all")
def read_all_notifications(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    try:
        count = mark_all_read(db, user.id)
        return {"detail": f"已标记 {count} 条通知为已读"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"全部标记已读失败: {str(e)}")


# ---- CategoryThreshold 路由 ----

@router.get("/category-thresholds", response_model=list[CategoryThresholdResponse])
def list_thresholds(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    try:
        return get_all_thresholds(db)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"查询阈值失败: {str(e)}")


@router.put("/category-thresholds/{threshold_id}", response_model=CategoryThresholdResponse)
def update_threshold_api(threshold_id: uuid.UUID, req: CategoryThresholdUpdateRequest,
                        db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    try:
        threshold = update_threshold(db, threshold_id, req.days_before_expiry)
        if not threshold:
            raise HTTPException(status_code=404, detail="阈值记录不存在")
        return threshold
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"更新阈值失败: {str(e)}")
```

- [ ] **Step 3: 在 main.py 的 startup 中添加默认阈值初始化**

在 `client/main.py` 的 `on_startup` 函数中，在 `_seed_admin()` 之后追加：

```python
@app.on_event("startup")
def on_startup():
    Base.metadata.create_all(bind=engine)
    _seed_admin()
    _seed_thresholds()


def _seed_thresholds():
    db = SessionLocal()
    try:
        from crud import seed_default_thresholds
        seed_default_thresholds(db)
    finally:
        db.close()
```

- [ ] **Step 4: Commit**

```bash
git add client/api/api.py client/main.py
git commit -m "feat: add notification and threshold API routes"
```

---

### Task 5: 前端 API 模块

**Files:**
- Create: `web/src/api/notification.ts`

- [ ] **Step 1: 创建 notification.ts API 模块**

```typescript
import api from './index'

export interface NotificationItem {
  id: string
  user_id: string
  type: string
  title: string
  content: string
  related_item_id: string | null
  is_read: boolean
  created_at: string | null
}

export interface NotificationCount {
  unread_count: number
}

export function getNotifications() {
  return api.get<any, NotificationItem[]>('/notifications')
}

export function getNotificationCount() {
  return api.get<any, NotificationCount>('/notifications/count')
}

export function markAsRead(notificationId: string) {
  return api.put<any, { detail: string }>(`/notifications/${notificationId}/read`)
}

export function markAllAsRead() {
  return api.put<any, { detail: string }>('/notifications/read-all')
}
```

- [ ] **Step 2: Commit**

```bash
git add web/src/api/notification.ts
git commit -m "feat: add notification API module"
```

---

### Task 6: NotificationBell 组件

**Files:**
- Create: `web/src/components/NotificationBell.vue`

- [ ] **Step 1: 创建 NotificationBell.vue 组件**

```vue
<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import {
  getNotifications,
  getNotificationCount,
  markAsRead,
  markAllAsRead,
  type NotificationItem,
} from '@/api/notification'

const router = useRouter()
const unreadCount = ref(0)
const notifications = ref<NotificationItem[]>([])
const loading = ref(false)
const popoverVisible = ref(false)

async function fetchCount() {
  try {
    const res = await getNotificationCount()
    unreadCount.value = res.unread_count
  } catch {
    // 静默失败
  }
}

async function fetchNotifications() {
  loading.value = true
  try {
    notifications.value = await getNotifications()
  } catch {
    ElMessage.error('获取通知失败')
  } finally {
    loading.value = false
  }
}

async function handleMarkRead(item: NotificationItem) {
  try {
    await markAsRead(item.id)
    item.is_read = true
    unreadCount.value = Math.max(0, unreadCount.value - 1)
  } catch {
    ElMessage.error('标记已读失败')
  }
}

async function handleMarkAllRead() {
  try {
    await markAllAsRead()
    notifications.value.forEach((n) => (n.is_read = true))
    unreadCount.value = 0
    ElMessage.success('已全部标记已读')
  } catch {
    ElMessage.error('操作失败')
  }
}

function handleItemClick(item: NotificationItem) {
  if (!item.is_read) {
    handleMarkRead(item)
  }
  if (item.related_item_id) {
    popoverVisible.value = false
    router.push('/')
  }
}

function handlePopoverShow() {
  fetchNotifications()
}

onMounted(() => {
  fetchCount()
})

defineExpose({ fetchCount })
</script>

<template>
  <el-popover
    v-model:visible="popoverVisible"
    placement="bottom-end"
    :width="360"
    trigger="click"
    @show="handlePopoverShow"
  >
    <template #reference>
      <el-badge :value="unreadCount" :hidden="unreadCount === 0" :max="99">
        <el-icon style="font-size: 20px; cursor: pointer; color: var(--text-secondary)">
          <Bell />
        </el-icon>
      </el-badge>
    </template>

    <div class="notification-panel">
      <div class="notification-header">
        <span class="notification-title">消息通知</span>
        <el-button
          v-if="unreadCount > 0"
          type="primary"
          link
          size="small"
          @click="handleMarkAllRead"
        >
          全部已读
        </el-button>
      </div>

      <div v-loading="loading" class="notification-list">
        <div v-if="notifications.length === 0" class="notification-empty">
          暂无通知
        </div>
        <div
          v-for="item in notifications"
          :key="item.id"
          class="notification-item"
          :class="{ 'is-read': item.is_read }"
          @click="handleItemClick(item)"
        >
          <div class="notification-item-header">
            <el-tag v-if="!item.is_read" type="danger" size="small" round>未读</el-tag>
            <span class="notification-item-title">{{ item.title }}</span>
          </div>
          <div class="notification-item-content">{{ item.content }}</div>
          <div class="notification-item-time">
            {{ item.created_at ? new Date(item.created_at).toLocaleString('zh-CN') : '' }}
          </div>
        </div>
      </div>
    </div>
  </el-popover>
</template>

<style scoped>
.notification-panel {
  margin: -12px;
}

.notification-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 12px 16px;
  border-bottom: 1px solid var(--border-color);
}

.notification-title {
  font-size: 15px;
  font-weight: 600;
  color: var(--text-primary);
}

.notification-list {
  max-height: 400px;
  overflow-y: auto;
}

.notification-empty {
  padding: 40px 0;
  text-align: center;
  color: var(--text-placeholder);
  font-size: 14px;
}

.notification-item {
  padding: 12px 16px;
  cursor: pointer;
  transition: background 0.2s;
  border-bottom: 1px solid var(--border-color);
}

.notification-item:hover {
  background: var(--bg-color);
}

.notification-item.is-read {
  opacity: 0.5;
}

.notification-item-header {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 4px;
}

.notification-item-title {
  font-size: 14px;
  font-weight: 500;
  color: var(--text-primary);
}

.notification-item-content {
  font-size: 13px;
  color: var(--text-secondary);
  margin-bottom: 4px;
}

.notification-item-time {
  font-size: 12px;
  color: var(--text-placeholder);
}
</style>
```

- [ ] **Step 2: Commit**

```bash
git add web/src/components/NotificationBell.vue
git commit -m "feat: add NotificationBell component"
```

---

### Task 7: 集成到 Layout 导航栏

**Files:**
- Modify: `web/src/components/Layout.vue:76-84`

- [ ] **Step 1: 在 Layout.vue 中导入并使用 NotificationBell**

在 `<script setup>` 中添加导入（第 4 行之后）：

```typescript
import NotificationBell from './NotificationBell.vue'
```

在 `<el-header>` 中添加铃铛组件。将第 76-84 行：

```vue
      <el-header class="top-header">
        <div style="display: flex; align-items: center; gap: 12px">
          <el-icon style="cursor: pointer; font-size: 20px; color: var(--text-secondary)" @click="isCollapse = !isCollapse">
            <Fold v-if="!isCollapse" />
            <Expand v-else />
          </el-icon>
          <span class="page-title">{{ pageTitle }}</span>
        </div>
      </el-header>
```

替换为：

```vue
      <el-header class="top-header">
        <div style="display: flex; align-items: center; gap: 12px">
          <el-icon style="cursor: pointer; font-size: 20px; color: var(--text-secondary)" @click="isCollapse = !isCollapse">
            <Fold v-if="!isCollapse" />
            <Expand v-else />
          </el-icon>
          <span class="page-title">{{ pageTitle }}</span>
        </div>
        <div style="display: flex; align-items: center; gap: 16px">
          <NotificationBell />
        </div>
      </el-header>
```

- [ ] **Step 2: 验证前端编译通过**

```bash
cd C:/Users/86134/PycharmProjects/luckfox_web/web && npm run build
```

- [ ] **Step 3: Commit**

```bash
git add web/src/components/Layout.vue
git commit -m "feat: integrate NotificationBell into Layout navbar"
```

---

### Task 8: 端到端验证

- [ ] **Step 1: 启动后端，验证表自动创建**

```bash
cd C:/Users/86134/PycharmProjects/luckfox_web/client && python main.py
```

检查日志中 `category_thresholds` 表被创建且默认数据被插入。

- [ ] **Step 2: 测试通知 API**

```bash
# 获取未读数量
curl -H "Authorization: Bearer <token>" http://localhost:8000/api/v1/notifications/count

# 获取通知列表
curl -H "Authorization: Bearer <token>" http://localhost:8000/api/v1/notifications

# 获取阈值列表
curl -H "Authorization: Bearer <token>" http://localhost:8000/api/v1/category-thresholds
```

- [ ] **Step 3: 启动前端，验证铃铛显示**

```bash
cd C:/Users/86134/PycharmProjects/luckfox_web/web && npm run dev
```

在浏览器中验证：
1. 导航栏右侧出现铃铛图标
2. 有临期食物时显示红点数字
3. 点击铃铛弹出通知列表
4. 可以标记已读和全部已读
5. 已读消息样式变淡
