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
