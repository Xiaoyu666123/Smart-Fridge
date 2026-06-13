import time
import uuid
import base64
import os

from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import Optional
from models import Inventory, EventLog, UserPreference, Conversation, AgentTrace, User, Admin
from services.upload_security import decode_base64_image, make_upload_filename, save_image_bytes, sanitize_filename_part

UPLOAD_DIR = "uploads"


def _save_crop_image(device_id: str, local_track_id: int, crop_b64: Optional[str] = None) -> Optional[str]:
    if not crop_b64:
        return None
    try:
        image_data = decode_base64_image(crop_b64)
    except Exception:
        return None
    if not image_data:
        return None
    try:
        prefix = f"{sanitize_filename_part(device_id)}_{sanitize_filename_part(local_track_id)}_{int(time.time())}"
        return save_image_bytes(make_upload_filename(prefix, ".jpg"), image_data)
    except Exception:
        return None


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


def _apply_inventory_filters(q, *, device_id=None, status=None, category=None,
                              q_text=None, start_date=None, end_date=None,
                              expiring_in_days=None):
    """统一的库存查询过滤器：用于 list / count，避免逻辑重复。"""
    from datetime import datetime, timedelta
    from sqlalchemy import or_, cast, String

    if device_id:
        q = q.filter(Inventory.device_id == device_id)
    if status:
        q = q.filter(Inventory.status == status)
    if category:
        q = q.filter(Inventory.category == category)
    if start_date:
        try:
            d = datetime.fromisoformat(start_date)
            q = q.filter(Inventory.created_at >= d)
        except Exception:
            pass
    if end_date:
        try:
            d = datetime.fromisoformat(end_date)
            # 包含当天，所以 +1 天
            q = q.filter(Inventory.created_at < d + timedelta(days=1))
        except Exception:
            pass
    if q_text:
        like = f"%{q_text.strip()}%"
        # 在 category / device_id / label_data->>brand / agent_metadata 全文里模糊
        q = q.filter(
            or_(
                Inventory.category.ilike(like),
                Inventory.device_id.ilike(like),
                cast(Inventory.label_data, String).ilike(like),
                cast(Inventory.agent_metadata, String).ilike(like),
            )
        )
    if expiring_in_days is not None and expiring_in_days >= 0:
        # 临期：agent_metadata->>'expire_at' 在 [now, now + N 天] 之间
        from sqlalchemy import func as _f
        cutoff = (datetime.now() + timedelta(days=expiring_in_days)).isoformat()
        now_iso = datetime.now().isoformat()
        q = q.filter(
            _f.coalesce(Inventory.agent_metadata["expire_at"].astext, "") != "",
            Inventory.agent_metadata["expire_at"].astext <= cutoff,
            Inventory.agent_metadata["expire_at"].astext >= now_iso,
        )
    return q


def get_inventory_list(db: Session, device_id: Optional[str] = None, status: Optional[str] = None,
                       category: Optional[str] = None,
                       limit: Optional[int] = None, offset: int = 0,
                       q: Optional[str] = None,
                       start_date: Optional[str] = None,
                       end_date: Optional[str] = None,
                       expiring_in_days: Optional[int] = None):
    """返回库存列表。limit=None 时不分页（向后兼容）。

    新增：
      q                  模糊匹配 category / device_id / label_data / agent_metadata
      start_date         入库时间下界（YYYY-MM-DD）
      end_date           入库时间上界（YYYY-MM-DD），包含当天
      expiring_in_days   只看 N 天内将到期的（>=0）
    """
    query = db.query(Inventory)
    query = _apply_inventory_filters(
        query, device_id=device_id, status=status, category=category,
        q_text=q, start_date=start_date, end_date=end_date,
        expiring_in_days=expiring_in_days,
    )
    query = query.order_by(Inventory.created_at.desc())
    if limit is not None:
        return query.offset(offset).limit(limit).all()
    return query.all()


def count_inventory(db: Session, device_id: Optional[str] = None, status: Optional[str] = None,
                    category: Optional[str] = None,
                    q: Optional[str] = None,
                    start_date: Optional[str] = None,
                    end_date: Optional[str] = None,
                    expiring_in_days: Optional[int] = None) -> int:
    query = db.query(Inventory)
    query = _apply_inventory_filters(
        query, device_id=device_id, status=status, category=category,
        q_text=q, start_date=start_date, end_date=end_date,
        expiring_in_days=expiring_in_days,
    )
    return query.count()


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
    user = User(username=username, password_hash=password_hash)
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def get_user_by_username(db: Session, username: str) -> Optional[User]:
    return db.query(User).filter(User.username == username).first()


def get_admin_by_username(db: Session, username: str) -> Optional[Admin]:
    return db.query(Admin).filter(Admin.username == username).first()


def get_user_by_id(db: Session, user_id) -> Optional[User]:
    return db.query(User).filter(User.id == user_id).first()


def list_users_with_stats(db: Session, search: Optional[str] = None) -> list:
    """管理员视角：列出所有普通用户 + 关联资产数量。

    返回 list[dict]: id, username, created_at, inventory_count,
                     preference_count, conversation_count
    """
    q = db.query(User)
    if search:
        q = q.filter(User.username.ilike(f"%{search}%"))
    rows = q.order_by(User.created_at.desc().nulls_last(), User.username).all()

    result = []
    for u in rows:
        # inventory 表没有 user_id，按设备维度，先记 0；保留字段方便未来扩展
        inv_count = 0
        pref_count = (
            db.query(UserPreference)
            .filter(UserPreference.user_id == str(u.id))
            .count()
        )
        conv_count = (
            db.query(Conversation)
            .filter(Conversation.user_id == str(u.id))
            .count()
        )
        result.append({
            "id": str(u.id),
            "username": u.username,
            "created_at": u.created_at,
            "inventory_count": inv_count,
            "preference_count": pref_count,
            "conversation_count": conv_count,
        })
    return result


def update_user_password(db: Session, user_id, new_password_hash: str) -> Optional[User]:
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        return None
    user.password_hash = new_password_hash
    db.commit()
    db.refresh(user)
    return user


def update_admin_password(db: Session, admin_id, new_password_hash: str) -> Optional[Admin]:
    admin = db.query(Admin).filter(Admin.id == admin_id).first()
    if not admin:
        return None
    admin.password_hash = new_password_hash
    db.commit()
    db.refresh(admin)
    return admin


def delete_user(db: Session, user_id) -> bool:
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        return False
    # 清掉关联资产，避免悬挂数据
    db.query(UserPreference).filter(UserPreference.user_id == str(user.id)).delete()
    db.query(Conversation).filter(Conversation.user_id == str(user.id)).delete()
    db.delete(user)
    db.commit()
    return True


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
    """合并 event_logs 和 agent_traces 为统一时间线。

    source 语义：
      - 'event' / 'trace'：限定从哪张表取
      - 'admin' 等其它值：解释成 agent_traces.tool_name 过滤（save_log 写的就是 tool_name）
    """
    results = []
    use_event = source is None or source == "event"
    use_trace = source is None or source != "event"     # admin / trace / 其它都从 traces 取
    tool_filter = source if source not in (None, "event", "trace") else None

    if use_event and not tool_filter:
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

    if use_trace:
        q = db.query(AgentTrace)
        if event_type:
            q = q.filter(AgentTrace.agent_type == event_type)
        if status:
            q = q.filter(AgentTrace.status == status)
        if tool_filter:
            q = q.filter(AgentTrace.tool_name == tool_filter)
        rows = q.order_by(AgentTrace.created_at.desc()).offset(offset).limit(limit).all()
        for r in rows:
            results.append({
                "id": f"trc-{r.id}",
                "source": r.tool_name if tool_filter else "trace",
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
                    # save_log 写的 detail 在 tool_output 里，前端用 detail 字段最直接
                    **(r.tool_output or {}),
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
    """为指定用户生成临期食物通知。

    去重粒度：(user_id, related_item_id, 今天日期)。
    每天对同一食材至多一条通知，新的一天会重新生成（达到"持续提醒"效果）。
    """
    from datetime import datetime, timedelta, date as _date
    from models import Notification, CategoryThreshold

    now = datetime.now()
    today = _date.today()

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
            # 检查今天是否已经为该食材生成过通知
            existing = (
                db.query(Notification)
                .filter(
                    Notification.user_id == user_id,
                    Notification.related_item_id == item.id,
                    Notification.notice_date == today,
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
                notice_date=today,
            )
            db.add(notification)
            new_notifications.append(notification)

    if new_notifications:
        db.commit()
        for n in new_notifications:
            db.refresh(n)

        # WS 推送给该用户（如果在线）
        try:
            from services.ws_manager import manager
            for n in new_notifications:
                manager.broadcast_to_user_sync(str(user_id), {
                    "type": "notification.new",
                    "data": {
                        "id": str(n.id),
                        "type": n.type,
                        "title": n.title,
                        "content": n.content,
                        "related_item_id": str(n.related_item_id) if n.related_item_id else None,
                        "is_read": n.is_read,
                        "created_at": n.created_at.isoformat() if n.created_at else None,
                    },
                })
            # 顺手再推一次未读总数
            unread = (
                db.query(Notification)
                .filter(Notification.user_id == user_id, Notification.is_read == False)
                .count()
            )
            manager.broadcast_to_user_sync(str(user_id), {
                "type": "notification.count",
                "unread_count": unread,
            })
        except Exception as e:
            import logging as _logging
            _logging.getLogger(__name__).warning(f"[WS] push notification failed | error={e}")

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


def update_threshold(db: Session, threshold_id: uuid.UUID,
                      days_before_expiry: Optional[int] = None,
                      unit_price: Optional[float] = None):
    """更新指定类别的临期阈值 / 单价。任一参数为 None 表示不修改。"""
    from models import CategoryThreshold
    threshold = db.query(CategoryThreshold).filter(CategoryThreshold.id == threshold_id).first()
    if not threshold:
        return None
    if days_before_expiry is not None:
        threshold.days_before_expiry = days_before_expiry
    if unit_price is not None:
        threshold.unit_price = unit_price
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


# ---- PendingLabel CRUD ----

def create_pending_label(db: Session, device_id: str, label_image_path: Optional[str],
                         label_text: str, label_data: dict, ttl_seconds: int = 300):
    """新建一条标签缓冲记录。"""
    from datetime import datetime, timedelta
    from models import PendingLabel

    expires_at = datetime.now() + timedelta(seconds=ttl_seconds)
    pending = PendingLabel(
        device_id=device_id,
        label_image_path=label_image_path,
        label_text=label_text or None,
        label_data=label_data or None,
        expires_at=expires_at,
    )
    db.add(pending)
    db.commit()
    db.refresh(pending)
    return pending


def find_active_pending_label(db: Session, device_id: str):
    """找该设备最近一条未消费、未过期的标签。"""
    from datetime import datetime
    from models import PendingLabel

    return (
        db.query(PendingLabel)
        .filter(
            PendingLabel.device_id == device_id,
            PendingLabel.consumed_at.is_(None),
            PendingLabel.expires_at > datetime.now(),
        )
        .order_by(PendingLabel.created_at.desc())
        .first()
    )


def consume_pending_label(db: Session, pending_id, inventory_id) -> None:
    """标记缓冲记录已被某条 inventory 消费。"""
    from datetime import datetime
    from models import PendingLabel

    pending = db.query(PendingLabel).filter(PendingLabel.id == pending_id).first()
    if not pending:
        return
    pending.consumed_at = datetime.now()
    pending.consumed_by_inventory_id = inventory_id
    db.commit()


def list_pending_labels(db: Session, device_id: Optional[str] = None,
                         status: Optional[str] = None, limit: int = 50):
    """管理员视角列出所有标签缓冲记录。

    status: pending / consumed / expired / None(全部)
    """
    from datetime import datetime
    from models import PendingLabel

    q = db.query(PendingLabel)
    if device_id:
        q = q.filter(PendingLabel.device_id == device_id)
    now = datetime.now()
    if status == "pending":
        q = q.filter(PendingLabel.consumed_at.is_(None), PendingLabel.expires_at > now)
    elif status == "consumed":
        q = q.filter(PendingLabel.consumed_at.isnot(None))
    elif status == "expired":
        q = q.filter(PendingLabel.consumed_at.is_(None), PendingLabel.expires_at <= now)
    return q.order_by(PendingLabel.created_at.desc()).limit(limit).all()


def cleanup_expired_pending_labels(db: Session, older_than_hours: int = 24) -> int:
    """懒清理：删除过期且早于 N 小时的未消费记录。"""
    from datetime import datetime, timedelta
    from models import PendingLabel

    threshold = datetime.now() - timedelta(hours=older_than_hours)
    deleted = (
        db.query(PendingLabel)
        .filter(
            PendingLabel.consumed_at.is_(None),
            PendingLabel.expires_at < threshold,
        )
        .delete()
    )
    db.commit()
    return deleted


# ---- LLM Usage 统计 ----

def get_usage_summary(db: Session, days: int = 30) -> dict:
    """近 N 天的整体用量与费用统计。"""
    from datetime import datetime, timedelta
    from models import LlmUsage
    from sqlalchemy import func as _func

    since = datetime.now() - timedelta(days=days)
    base = db.query(LlmUsage).filter(LlmUsage.created_at >= since)

    total_calls = base.count()
    total_tokens = base.with_entities(_func.coalesce(_func.sum(LlmUsage.total_tokens), 0)).scalar() or 0
    total_cost = base.with_entities(_func.coalesce(_func.sum(LlmUsage.cost_usd), 0)).scalar() or 0
    failed_calls = base.filter(LlmUsage.status == "FAILED").count()

    # 按 provider 分组
    by_provider = (
        db.query(
            LlmUsage.provider,
            _func.count(LlmUsage.id),
            _func.coalesce(_func.sum(LlmUsage.total_tokens), 0),
            _func.coalesce(_func.sum(LlmUsage.cost_usd), 0),
        )
        .filter(LlmUsage.created_at >= since)
        .group_by(LlmUsage.provider)
        .all()
    )

    # 按 endpoint 分组（Top 10）
    by_endpoint = (
        db.query(
            LlmUsage.endpoint,
            _func.count(LlmUsage.id),
            _func.coalesce(_func.sum(LlmUsage.total_tokens), 0),
            _func.coalesce(_func.sum(LlmUsage.cost_usd), 0),
        )
        .filter(LlmUsage.created_at >= since)
        .group_by(LlmUsage.endpoint)
        .order_by(_func.sum(LlmUsage.total_tokens).desc().nulls_last())
        .limit(10)
        .all()
    )

    # 每日趋势
    daily = (
        db.query(
            _func.date(LlmUsage.created_at).label("d"),
            _func.count(LlmUsage.id),
            _func.coalesce(_func.sum(LlmUsage.total_tokens), 0),
            _func.coalesce(_func.sum(LlmUsage.cost_usd), 0),
        )
        .filter(LlmUsage.created_at >= since)
        .group_by(_func.date(LlmUsage.created_at))
        .order_by(_func.date(LlmUsage.created_at))
        .all()
    )

    return {
        "since": since.isoformat(),
        "total_calls": total_calls,
        "failed_calls": failed_calls,
        "total_tokens": int(total_tokens),
        "total_cost_usd": float(total_cost),
        "by_provider": [
            {"provider": p, "calls": c, "tokens": int(t), "cost_usd": float(co)}
            for p, c, t, co in by_provider
        ],
        "by_endpoint": [
            {"endpoint": e or "unknown", "calls": c, "tokens": int(t), "cost_usd": float(co)}
            for e, c, t, co in by_endpoint
        ],
        "daily": [
            {"date": d.isoformat() if d else None, "calls": c, "tokens": int(t), "cost_usd": float(co)}
            for d, c, t, co in daily
        ],
    }


def list_usage_records(db: Session, limit: int = 50, offset: int = 0,
                       provider: Optional[str] = None,
                       endpoint: Optional[str] = None,
                       status: Optional[str] = None) -> list:
    from models import LlmUsage
    q = db.query(LlmUsage)
    if provider:
        q = q.filter(LlmUsage.provider == provider)
    if endpoint:
        q = q.filter(LlmUsage.endpoint == endpoint)
    if status:
        q = q.filter(LlmUsage.status == status)
    return q.order_by(LlmUsage.created_at.desc()).offset(offset).limit(limit).all()


# ---- 食谱收藏 ----

def save_recipe(db: Session, user_id: str, data: dict):
    """保存一个收藏食谱。如已有同名记录则视为再次收藏（cooked_count 不变，但更新内容）。"""
    from models import SavedRecipe

    # 简单去重：同 user_id 同 name 视为同一条
    existing = (
        db.query(SavedRecipe)
        .filter(SavedRecipe.user_id == user_id, SavedRecipe.name == data["name"])
        .first()
    )
    if existing:
        # 更新内容（用户可能改了食谱）
        existing.summary = data.get("summary") or existing.summary
        existing.prep_time = data.get("prep_time") if data.get("prep_time") is not None else existing.prep_time
        existing.difficulty = data.get("difficulty") or existing.difficulty
        if data.get("ingredients") is not None:
            existing.ingredients = data["ingredients"]
        if data.get("steps") is not None:
            existing.steps = data["steps"]
        if data.get("tags") is not None:
            existing.tags = data["tags"]
        db.commit()
        db.refresh(existing)
        return existing

    rec = SavedRecipe(
        user_id=user_id,
        name=data["name"],
        summary=data.get("summary"),
        prep_time=data.get("prep_time"),
        difficulty=data.get("difficulty"),
        ingredients=data.get("ingredients"),
        steps=data.get("steps"),
        tags=data.get("tags"),
        source=data.get("source", "chat"),
    )
    db.add(rec)
    db.commit()
    db.refresh(rec)
    return rec


def list_saved_recipes(db: Session, user_id: str, limit: int = 50, offset: int = 0):
    from models import SavedRecipe
    return (
        db.query(SavedRecipe)
        .filter(SavedRecipe.user_id == user_id)
        .order_by(SavedRecipe.last_cooked_at.desc().nulls_last(), SavedRecipe.created_at.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )


def delete_saved_recipe(db: Session, user_id: str, recipe_id) -> bool:
    from models import SavedRecipe
    r = db.query(SavedRecipe).filter(
        SavedRecipe.id == recipe_id, SavedRecipe.user_id == user_id
    ).first()
    if not r:
        return False
    db.delete(r)
    db.commit()
    return True


def update_recipe_meta(db: Session, user_id: str, recipe_id, *,
                        rating: Optional[int] = None,
                        notes: Optional[str] = None):
    """更新食谱评分 / 笔记。任一为 None 表示不修改对应字段。"""
    from models import SavedRecipe
    r = db.query(SavedRecipe).filter(
        SavedRecipe.id == recipe_id, SavedRecipe.user_id == user_id
    ).first()
    if not r:
        return None
    if rating is not None:
        if rating < 1 or rating > 5:
            raise ValueError("rating must be in [1, 5]")
        r.rating = rating
    if notes is not None:
        r.notes = notes
    db.commit()
    db.refresh(r)
    return r


def mark_recipe_cooked(db: Session, user_id: str, recipe_id, consumed_inventory_ids: Optional[list] = None):
    """打卡：cooked_count +1，可选地把指定库存置 OUT_PENDING。

    返回 (recipe, consumed_ids, skipped_ids)：
      consumed_ids 是真的被改成 OUT_PENDING 的；
      skipped_ids 是要么找不到要么本来就不在库的。
    """
    from models import SavedRecipe, Inventory, EventLog
    from datetime import datetime
    r = db.query(SavedRecipe).filter(
        SavedRecipe.id == recipe_id, SavedRecipe.user_id == user_id
    ).first()
    if not r:
        return None, [], []

    consumed_ids: list = []
    skipped_ids: list = []
    if consumed_inventory_ids:
        for inv_id in consumed_inventory_ids:
            try:
                inv = db.query(Inventory).filter(Inventory.id == inv_id).first()
            except Exception:
                inv = None
            if not inv or inv.status != "IN_STOCK":
                skipped_ids.append(str(inv_id))
                continue
            inv.status = "OUT_PENDING"
            db.add(EventLog(
                inventory_id=inv.id,
                event_type="ITEM_OUT",
                confidence=1.0,
                snapshot_path=None,
            ))
            consumed_ids.append(str(inv.id))

    r.cooked_count = (r.cooked_count or 0) + 1
    r.last_cooked_at = datetime.now()
    db.commit()
    db.refresh(r)
    return r, consumed_ids, skipped_ids


# ---- 浪费分析（基于 inventory + event_logs）----

def get_waste_analytics(db: Session, days: int = 30) -> dict:
    """统计食材消耗与浪费。

    定义：
    - 浪费(wasted)：库存的 expire_at 已过 + 状态仍是 IN_STOCK
    - 按时消耗(consumed_in_time)：状态为 OUT_PENDING/CONSUMED
    - 还在库(in_stock)：状态 IN_STOCK 且未过期

    新增金额估算：
    - 从 category_thresholds.unit_price 取每个品类的单价
    - wasted_value = sum(品类浪费数量 * 单价)
    - consumed_value 同理
    """
    from datetime import datetime, timedelta
    from models import CategoryThreshold

    now = datetime.now()
    since = now - timedelta(days=days)

    # 加载单价表
    price_rows = db.query(CategoryThreshold.category, CategoryThreshold.unit_price).all()
    price_map = {r[0]: float(r[1]) for r in price_rows if r[1] is not None}

    inv_rows = (
        db.query(Inventory)
        .filter(Inventory.created_at >= since)
        .all()
    )

    total = len(inv_rows)
    wasted = 0
    consumed_in_time = 0
    in_stock = 0
    waste_by_cat: dict = {}
    consumed_by_cat: dict = {}

    for inv in inv_rows:
        md = inv.agent_metadata or {}
        expire_at_str = md.get("expire_at")
        try:
            expire_at = datetime.fromisoformat(expire_at_str) if expire_at_str else None
        except Exception:
            expire_at = None

        cat = inv.category or "未知"

        if inv.status == "CONSUMED":
            consumed_in_time += 1
            consumed_by_cat[cat] = consumed_by_cat.get(cat, 0) + 1
            continue

        if inv.status == "OUT_PENDING":
            consumed_in_time += 1
            consumed_by_cat[cat] = consumed_by_cat.get(cat, 0) + 1
            continue

        # IN_STOCK
        if expire_at and expire_at < now:
            wasted += 1
            waste_by_cat[cat] = waste_by_cat.get(cat, 0) + 1
        else:
            in_stock += 1

    waste_rate = round(wasted / total, 4) if total else 0.0

    # 金额估算：没有单价的品类按 0 算（前端会提示"未配置"）
    wasted_value = sum(cnt * price_map.get(cat, 0) for cat, cnt in waste_by_cat.items())
    consumed_value = sum(cnt * price_map.get(cat, 0) for cat, cnt in consumed_by_cat.items())
    priced_categories = len(price_map)
    total_categories = len(set(waste_by_cat.keys()) | set(consumed_by_cat.keys()))

    top_wasted = sorted(waste_by_cat.items(), key=lambda x: x[1], reverse=True)[:8]
    top_consumed = sorted(consumed_by_cat.items(), key=lambda x: x[1], reverse=True)[:8]

    # 补货建议：消耗多但当前在库少（<=1）
    current_in_stock = (
        db.query(Inventory.category, func.count(Inventory.id))
        .filter(Inventory.status == "IN_STOCK")
        .group_by(Inventory.category)
        .all()
    )
    cur_map = {row[0]: row[1] for row in current_in_stock}

    suggestions = []
    for cat, cnt in top_consumed[:10]:
        cur = cur_map.get(cat, 0)
        if cur <= 1 and cnt >= 2:
            suggestions.append({
                "category": cat,
                "consumed_count": cnt,
                "current_stock": cur,
                "suggested_qty": max(2, cnt // max(1, days // 7)),  # 每周大约消耗一份就建议一份
                "unit_price": price_map.get(cat),
                "estimated_cost": round(price_map.get(cat, 0) * max(2, cnt // max(1, days // 7)), 2)
                                    if cat in price_map else None,
                "reason": "近期消耗较多但库存不足",
            })

    return {
        "window_days": days,
        "total": total,
        "wasted": wasted,
        "consumed_in_time": consumed_in_time,
        "in_stock": in_stock,
        "waste_rate": waste_rate,
        "wasted_value": round(wasted_value, 2),
        "consumed_value": round(consumed_value, 2),
        "priced_categories": priced_categories,
        "total_categories_seen": total_categories,
        "top_wasted": [
            {"category": c, "count": n,
             "unit_price": price_map.get(c),
             "estimated_value": round(n * price_map.get(c, 0), 2) if c in price_map else None}
            for c, n in top_wasted
        ],
        "top_consumed": [
            {"category": c, "count": n,
             "unit_price": price_map.get(c),
             "estimated_value": round(n * price_map.get(c, 0), 2) if c in price_map else None}
            for c, n in top_consumed
        ],
        "restock_suggestions": suggestions,
    }


# ---- 设备管理 ----

ONLINE_THRESHOLD_SEC = 90      # 90 秒内有心跳 = 在线
IDLE_THRESHOLD_SEC   = 300     # 5 分钟内有心跳 = 空闲，超过即离线


def upsert_device_seen(db: Session, device_id: str, *,
                        event: str = "heartbeat",
                        payload: Optional[dict] = None,
                        auto_register: bool = True):
    """端侧任意上报都该调一次：
       - 找不到记录就自动注册（如果 auto_register）
       - 更新 last_seen_at / last_event_type / heartbeat_count
       - 写一条 device_heartbeats 流水
    """
    from datetime import datetime
    from models import Device, DeviceHeartbeat
    if not device_id:
        return None
    dev = db.query(Device).filter(Device.device_id == device_id).first()
    now = datetime.now()
    if not dev:
        if not auto_register:
            return None
        dev = Device(
            device_id=device_id,
            name=device_id,        # 默认显示名 = device_id，后台可改
            status="online",
            last_seen_at=now,
            last_event_type=event,
            heartbeat_count=1,
        )
        db.add(dev)
    else:
        dev.status = "online"
        dev.last_seen_at = now
        dev.last_event_type = event
        dev.heartbeat_count = (dev.heartbeat_count or 0) + 1

    db.add(DeviceHeartbeat(device_id=device_id, event=event, payload=payload))
    db.commit()
    db.refresh(dev)
    return dev


def list_devices(db: Session):
    """列出所有设备，根据 last_seen_at 推算实时状态。"""
    from datetime import datetime
    from models import Device
    rows = db.query(Device).order_by(Device.registered_at.desc()).all()
    now = datetime.now()
    result = []
    for d in rows:
        if d.last_seen_at:
            age = (now - d.last_seen_at).total_seconds()
        else:
            age = 9_999_999
        if age <= ONLINE_THRESHOLD_SEC:
            live = "online"
        elif age <= IDLE_THRESHOLD_SEC:
            live = "idle"
        else:
            live = "offline"
        result.append({
            "id": str(d.id),
            "device_id": d.device_id,
            "name": d.name or d.device_id,
            "location": d.location,
            "description": d.description,
            "status": d.status,
            "live_status": live,
            "last_seen_at": d.last_seen_at.isoformat() if d.last_seen_at else None,
            "last_event_type": d.last_event_type,
            "heartbeat_count": d.heartbeat_count or 0,
            "registered_at": d.registered_at.isoformat() if d.registered_at else None,
            "seconds_since_last_seen": int(age) if age < 9_000_000 else None,
        })
    return result


def get_device(db: Session, device_id: str):
    from models import Device
    return db.query(Device).filter(Device.device_id == device_id).first()


def update_device_meta(db: Session, device_id: str, *,
                        name: Optional[str] = None,
                        location: Optional[str] = None,
                        description: Optional[str] = None):
    dev = get_device(db, device_id)
    if not dev:
        return None
    if name is not None:
        dev.name = name
    if location is not None:
        dev.location = location
    if description is not None:
        dev.description = description
    db.commit()
    db.refresh(dev)
    return dev


def delete_device(db: Session, device_id: str) -> bool:
    dev = get_device(db, device_id)
    if not dev:
        return False
    db.delete(dev)
    db.commit()
    return True


def restore_device(db: Session, *, device_id: str, name: Optional[str] = None,
                    location: Optional[str] = None, description: Optional[str] = None):
    """重新创建一个设备记录（用于撤销删除）。已存在则忽略。"""
    from datetime import datetime
    from models import Device
    existed = db.query(Device).filter(Device.device_id == device_id).first()
    if existed:
        return existed
    dev = Device(
        device_id=device_id,
        name=name or device_id,
        location=location,
        description=description,
        status="offline",
        last_seen_at=None,
        heartbeat_count=0,
    )
    db.add(dev)
    db.commit()
    db.refresh(dev)
    return dev


def get_device_heartbeat_series(db: Session, device_id: str, *, hours: int = 24, bucket_minutes: int = 30):
    """返回该设备近 N 小时的心跳频率（按 bucket_minutes 桶聚合）。"""
    from datetime import datetime, timedelta
    from models import DeviceHeartbeat
    if hours <= 0 or bucket_minutes <= 0:
        return []
    now = datetime.now()
    since = now - timedelta(hours=hours)
    rows = (
        db.query(DeviceHeartbeat.created_at)
        .filter(DeviceHeartbeat.device_id == device_id,
                DeviceHeartbeat.created_at >= since)
        .all()
    )
    bucket_count = (hours * 60) // bucket_minutes
    buckets = [0] * bucket_count
    labels: list[str] = []
    bucket_starts: list[datetime] = []
    for i in range(bucket_count):
        start = since + timedelta(minutes=i * bucket_minutes)
        bucket_starts.append(start)
        labels.append(start.strftime("%H:%M"))
    for (ts,) in rows:
        delta = (ts - since).total_seconds()
        idx = int(delta // (bucket_minutes * 60))
        if 0 <= idx < bucket_count:
            buckets[idx] += 1
    return [
        {"label": labels[i], "ts": bucket_starts[i].isoformat(), "count": buckets[i]}
        for i in range(bucket_count)
    ]


def cleanup_old_heartbeats(db: Session, keep_hours: int = 48):
    """清理 keep_hours 小时之前的心跳流水，避免膨胀。"""
    from datetime import datetime, timedelta
    from models import DeviceHeartbeat
    cutoff = datetime.now() - timedelta(hours=keep_hours)
    n = db.query(DeviceHeartbeat).filter(DeviceHeartbeat.created_at < cutoff).delete()
    db.commit()
    return n


# ---- 工具链性能聚合 ----

def get_tool_perf_stats(db: Session, hours: int = 24) -> dict:
    """按 tool_name 聚合近 N 小时的执行统计：
    count / success_count / fail_count / success_rate
    avg_ms / p50 / p95 / max
    """
    from datetime import datetime, timedelta
    since = datetime.now() - timedelta(hours=hours)
    rows = (
        db.query(AgentTrace.tool_name, AgentTrace.status, AgentTrace.duration_ms,
                 AgentTrace.created_at)
        .filter(AgentTrace.created_at >= since)
        .all()
    )
    by_tool: dict = {}
    for tn, st, ms, _ts in rows:
        b = by_tool.setdefault(tn, {"durations": [], "ok": 0, "fail": 0})
        if st == "SUCCESS":
            b["ok"] += 1
        else:
            b["fail"] += 1
        if ms is not None:
            b["durations"].append(ms)

    def percentile(data, p):
        if not data:
            return 0
        s = sorted(data)
        k = int(round((p / 100) * (len(s) - 1)))
        return s[max(0, min(k, len(s) - 1))]

    tools = []
    for tn, b in by_tool.items():
        d = b["durations"]
        total = b["ok"] + b["fail"]
        avg = round(sum(d) / len(d), 1) if d else 0
        tools.append({
            "tool_name": tn,
            "count": total,
            "success_count": b["ok"],
            "fail_count": b["fail"],
            "success_rate": round(b["ok"] / total, 4) if total else 0,
            "avg_ms": avg,
            "p50_ms": percentile(d, 50),
            "p95_ms": percentile(d, 95),
            "max_ms": max(d) if d else 0,
        })
    tools.sort(key=lambda x: x["count"], reverse=True)

    # 整体趋势（按小时桶聚合 step 数）
    trend_buckets = []
    bucket_count = max(1, hours)
    for i in range(bucket_count):
        bucket_start = since + timedelta(hours=i)
        cnt = sum(
            1 for tn, st, ms, ts in rows
            if (ts is not None) and (bucket_start <= ts < bucket_start + timedelta(hours=1))
        )
        trend_buckets.append({
            "label": bucket_start.strftime("%H:00"),
            "count": cnt,
        })

    # 周-小时热力图：[hour 0-23][weekday 0-6] = count
    # 注意 Python weekday: 0=Mon ... 6=Sun
    heatmap_data = []
    weekday_hour: dict = {}
    for tn, st, ms, ts in rows:
        if ts is None:
            continue
        wd = ts.weekday()
        hr = ts.hour
        weekday_hour[(hr, wd)] = weekday_hour.get((hr, wd), 0) + 1
    for hr in range(24):
        for wd in range(7):
            heatmap_data.append([hr, wd, weekday_hour.get((hr, wd), 0)])

    return {
        "window_hours": hours,
        "total_steps": len(rows),
        "tools": tools,
        "trend": trend_buckets,
        "weekday_hour_heatmap": heatmap_data,
    }


# ---- 健康饮食评分 ----

def get_nutrition_report(db: Session, days: int = 30) -> dict:
    """计算近 N 天饮食营养结构 + 健康评分 + 建议。

    把所有库存（含已消耗 / 仍在库）按品类映射到营养类别（蔬菜/肉/水果/...），
    统计分布，再用 nutrition.assess_health 给出评分。
    """
    from datetime import datetime, timedelta
    from services.nutrition import classify, get_category_info, assess_health

    since = datetime.now() - timedelta(days=days)
    rows = (
        db.query(Inventory.category, Inventory.status)
        .filter(Inventory.created_at >= since)
        .all()
    )

    distribution: dict = {}
    consumed_distribution: dict = {}
    by_category: dict = {}

    for cat, status in rows:
        tag = classify(cat)
        distribution[tag] = distribution.get(tag, 0) + 1
        if status in ("OUT_PENDING", "CONSUMED"):
            consumed_distribution[tag] = consumed_distribution.get(tag, 0) + 1
        # 按 category 维度打回标签，前端能展示明细
        if cat not in by_category:
            by_category[cat] = {"category": cat, "tag": tag, "count": 0}
        by_category[cat]["count"] += 1

    health = assess_health(distribution)
    consumed_health = assess_health(consumed_distribution) if consumed_distribution else None

    return {
        "window_days": days,
        "total": sum(distribution.values()),
        "consumed_total": sum(consumed_distribution.values()),
        "distribution": [
            {"tag": tag, "count": cnt, **get_category_info(tag)}
            for tag, cnt in sorted(distribution.items(), key=lambda x: x[1], reverse=True)
        ],
        "consumed_distribution": [
            {"tag": tag, "count": cnt, **get_category_info(tag)}
            for tag, cnt in sorted(consumed_distribution.items(), key=lambda x: x[1], reverse=True)
        ],
        "by_category": [
            {"category": item["category"], "tag": item["tag"],
             **{k: v for k, v in get_category_info(item["tag"]).items() if k != "label"},
             "label": get_category_info(item["tag"])["label"],
             "count": item["count"]}
            for item in sorted(by_category.values(), key=lambda x: x["count"], reverse=True)[:30]
        ],
        "health_overall": health,
        "health_consumed": consumed_health,
    }


# ---- 食材生命周期 Sankey 数据 ----

def get_lifecycle_sankey(db: Session, days: int = 30, top_n: int = 8) -> dict:
    """构造 Sankey 流图数据：进货来源 → 品类 → 终态。

    nodes: [{name}]
    links: [{source, target, value}]
    流：
      入库来源（端侧 / 手动 / 批量 / 标签关联）→ 品类（Top N + 其他）→ 终态（在库 / 临期 / 已消耗 / 浪费）
    """
    from datetime import datetime, timedelta
    from collections import Counter

    now = datetime.now()
    since = now - timedelta(days=days)

    inv_rows = (
        db.query(Inventory)
        .filter(Inventory.created_at >= since)
        .all()
    )

    # 第 1 列：来源（推断）
    def infer_source(inv):
        md = inv.agent_metadata or {}
        # ITEM_IN agent 写的 metadata 里有 confidence，手动入库走 InventoryCreateRequest 也会传 confidence
        # 用 expire_source 区分相对靠谱：来自标签 / LLM 估算 / 手动
        es = md.get("expire_source")
        if es == "label":
            return "📦 带标签入库"
        if es == "llm_estimate":
            return "🤖 端侧识别"
        if es == "manual":
            return "✍️ 手动录入"
        return "🤖 端侧识别"   # 兜底

    # 第 2 列：品类（Top N + 其他）
    cat_counter = Counter(inv.category for inv in inv_rows)
    top_cats = set(c for c, _ in cat_counter.most_common(top_n))

    def cat_label(c):
        return c if c in top_cats else "其他"

    # 第 3 列：终态
    def final_state(inv):
        if inv.status == "CONSUMED":
            return "✅ 已消耗"
        if inv.status == "OUT_PENDING":
            return "🔄 取出中"
        # IN_STOCK
        md = inv.agent_metadata or {}
        es = md.get("expire_at")
        if es:
            try:
                exp = datetime.fromisoformat(es)
            except Exception:
                exp = None
            if exp and exp < now:
                return "❌ 已浪费"
            if exp and (exp - now).days <= 3:
                return "⚠️ 临期在库"
        return "🟢 充足在库"

    # 统计 link
    link_a_to_b: Counter = Counter()  # (source, cat)
    link_b_to_c: Counter = Counter()  # (cat, state)

    for inv in inv_rows:
        s = infer_source(inv)
        c = cat_label(inv.category or "未知")
        f = final_state(inv)
        link_a_to_b[(s, c)] += 1
        link_b_to_c[(c, f)] += 1

    # 节点保持显示顺序
    sources = [n for n in [
        "📦 带标签入库", "🤖 端侧识别", "✍️ 手动录入"
    ] if any(s == n for (s, _) in link_a_to_b.keys())]
    cats_in_order = [c for c, _ in cat_counter.most_common(top_n)]
    if any(cat_label(inv.category or "未知") == "其他" for inv in inv_rows):
        cats_in_order.append("其他")
    states = [n for n in [
        "🟢 充足在库", "⚠️ 临期在库", "🔄 取出中", "✅ 已消耗", "❌ 已浪费"
    ] if any(f == n for (_, f) in link_b_to_c.keys())]

    nodes = [{"name": n, "depth": 0} for n in sources] + \
            [{"name": n, "depth": 1} for n in cats_in_order] + \
            [{"name": n, "depth": 2} for n in states]

    links = []
    for (s, c), v in link_a_to_b.items():
        links.append({"source": s, "target": c, "value": v})
    for (c, f), v in link_b_to_c.items():
        links.append({"source": c, "target": f, "value": v})

    return {
        "window_days": days,
        "total": len(inv_rows),
        "nodes": nodes,
        "links": links,
        "categories": {
            "sources": sources,
            "categories": cats_in_order,
            "states": states,
        },
    }


# ---- 浪费金额日历热力图（365 天）----

def get_waste_calendar(db: Session, days: int = 365) -> dict:
    """每天浪费金额（按品类单价计算），用于 GitHub 风格日历热图。

    返回 [["YYYY-MM-DD", value], ...] + 总览。
    判定：库存的 expire_at 落在某天 + 状态仍是 IN_STOCK → 该天被记为浪费。
    """
    from datetime import datetime, timedelta
    from collections import defaultdict
    from models import CategoryThreshold

    now = datetime.now()
    start = (now - timedelta(days=days - 1)).date()

    # 单价
    price_rows = db.query(CategoryThreshold.category, CategoryThreshold.unit_price).all()
    price_map = {r[0]: float(r[1]) for r in price_rows if r[1] is not None}

    # 拉所有还在库的、且 expire_at 落在窗口内的（这些就是浪费）
    rows = (
        db.query(Inventory)
        .filter(Inventory.status == "IN_STOCK")
        .all()
    )

    by_day: dict = defaultdict(float)
    by_day_count: dict = defaultdict(int)
    for inv in rows:
        md = inv.agent_metadata or {}
        es = md.get("expire_at")
        if not es:
            continue
        try:
            exp = datetime.fromisoformat(es)
        except Exception:
            continue
        if exp >= now:
            continue   # 还没过期，不算浪费
        d = exp.date()
        if d < start:
            continue
        # 兼容超过今天的边界
        if d > now.date():
            continue
        price = price_map.get(inv.category, 0)
        by_day[d.isoformat()] += price
        by_day_count[d.isoformat()] += 1

    # 输出 [date, value, count]
    series = []
    cur = start
    end = now.date()
    max_value = 0.0
    while cur <= end:
        key = cur.isoformat()
        v = round(by_day.get(key, 0), 2)
        if v > max_value:
            max_value = v
        series.append([key, v, by_day_count.get(key, 0)])
        cur += timedelta(days=1)

    total_value = round(sum(by_day.values()), 2)
    total_count = sum(by_day_count.values())
    days_with_waste = sum(1 for v in by_day.values() if v > 0)

    return {
        "window_days": days,
        "start": start.isoformat(),
        "end": end.isoformat(),
        "max_value": round(max_value, 2),
        "total_value": total_value,
        "total_count": total_count,
        "days_with_waste": days_with_waste,
        "series": series,
    }


# ---- 烹饪日历（用户视角）----

def get_cooking_calendar(db: Session, user_id: str, days: int = 365) -> dict:
    """近 N 天每天打卡了几道菜，用于 GitHub 风格热图。

    返回 [["YYYY-MM-DD", count, [recipe_name, ...]], ...]
    判定：saved_recipes.last_cooked_at 落在那天的就算（注意：cooked_count > 1 时
    我们也只计为 1 次，因为没有完整的打卡历史，只有最后一次时间。
    更准确的方案需要新建一张 cooking_log 表，这里用现有数据近似）。

    更精确的做法：扫描 last_cooked_at 的日期分布，按 "做过多少不同的菜" 来反映活跃度。
    """
    from datetime import datetime, timedelta
    from collections import defaultdict
    from models import SavedRecipe

    now = datetime.now()
    start = (now - timedelta(days=days - 1)).date()

    rows = (
        db.query(SavedRecipe.name, SavedRecipe.last_cooked_at, SavedRecipe.cooked_count)
        .filter(SavedRecipe.user_id == user_id,
                SavedRecipe.last_cooked_at != None,
                SavedRecipe.last_cooked_at >= datetime.combine(start, datetime.min.time()))
        .all()
    )

    by_day: dict = defaultdict(list)   # date_str -> [recipe_name]
    by_day_count: dict = defaultdict(int)  # 总打卡数（含同一菜多次）
    for name, last, cnt in rows:
        if not last:
            continue
        d = last.date().isoformat()
        by_day[d].append(name)
        by_day_count[d] += cnt or 1

    # 顶部统计
    total_recipes = len(rows)
    total_cooks = sum(r[2] or 0 for r in rows)
    days_with_cook = len(by_day)

    # 连续打卡天数（往前推到第一天没打卡为止）
    streak = 0
    cur = now.date()
    while cur.isoformat() in by_day and streak < days:
        streak += 1
        cur = cur - timedelta(days=1)

    # 最爱做的菜（按 cooked_count 排）
    top = sorted(rows, key=lambda x: x[2] or 0, reverse=True)[:5]
    top_recipes = [
        {"name": name, "cooked_count": cnt or 0,
         "last_cooked_at": last.isoformat() if last else None}
        for name, last, cnt in top
    ]

    # 序列化
    series = []
    cur_d = start
    end = now.date()
    max_count = 0
    while cur_d <= end:
        key = cur_d.isoformat()
        c = len(by_day.get(key, []))
        if c > max_count:
            max_count = c
        series.append([key, c, by_day.get(key, [])])
        cur_d += timedelta(days=1)

    return {
        "window_days": days,
        "start": start.isoformat(),
        "end": end.isoformat(),
        "total_recipes": total_recipes,
        "total_cooks": total_cooks,
        "days_with_cook": days_with_cook,
        "current_streak": streak,
        "max_per_day": max_count,
        "top_recipes": top_recipes,
        "series": series,
    }


# ---- 用户成就 / 个人档案 ----

def get_user_achievements(db: Session, user_id: str) -> dict:
    """汇总用户的成就徽章 + 个人档案 + 近 30 天每日有效消耗趋势。

    数据来源（不新建表）：
      - users：注册天数
      - saved_recipes：收藏数 / 累计打卡 / 评分 / 笔记数
      - inventory：累计入库 / 已消耗（CONSUMED）/ 浪费 (WASTED) / 不同品类数
      - user_preferences：偏好条数
      - notifications：历史关注次数

    返回：
      {
        "profile": {...个人档案字段},
        "achievements": [{"id","name","desc","emoji","unlocked","progress","total"}],
        "consume_trend": [["YYYY-MM-DD", count], ...]   # 近 30 天
      }
    """
    from datetime import datetime, timedelta
    from collections import defaultdict
    from sqlalchemy import func as _func
    from models import (
        User as _User, SavedRecipe as _SR, Inventory as _Inv,
        EventLog as _EL, UserPreference as _UP, Notification as _Notif,
    )

    user = db.query(_User).filter(_User.id == user_id).first()
    register_days = 0
    register_at = None
    if user and user.created_at:
        register_at = user.created_at
        register_days = max(1, (datetime.now() - user.created_at).days + 1)

    # ---- saved_recipes 聚合 ----
    sr_rows = db.query(_SR.cooked_count, _SR.rating, _SR.notes, _SR.last_cooked_at) \
                .filter(_SR.user_id == user_id).all()
    saved_count = len(sr_rows)
    total_cooks = sum((r[0] or 0) for r in sr_rows)
    rated_count = sum(1 for r in sr_rows if r[1])
    note_count = sum(1 for r in sr_rows if r[2] and r[2].strip())
    distinct_cooked_days = len(set(
        r[3].date().isoformat() for r in sr_rows if r[3]
    ))

    # ---- inventory 聚合（不限 user，整库共享，但端到端 demo 是单用户） ----
    inv_total = db.query(_func.count(_Inv.id)).scalar() or 0
    inv_consumed = db.query(_func.count(_Inv.id)).filter(_Inv.status == "CONSUMED").scalar() or 0
    inv_wasted = db.query(_func.count(_Inv.id)).filter(_Inv.status == "WASTED").scalar() or 0
    inv_categories = db.query(_func.count(_func.distinct(_Inv.category))).scalar() or 0

    # ---- user_preferences ----
    pref_count = db.query(_func.count(_UP.id)).filter(_UP.user_id == user_id).scalar() or 0

    # ---- notifications 总数 ----
    notif_count = db.query(_func.count(_Notif.id)).filter(_Notif.user_id == user_id).scalar() or 0

    # ---- 近 30 天消耗趋势：以 EventLog ITEM_OUT 为准 ----
    end_date = datetime.now().date()
    start_date = end_date - timedelta(days=29)
    trend_rows = db.query(_EL.create_at) \
        .filter(_EL.event_type == "ITEM_OUT",
                _EL.create_at >= datetime.combine(start_date, datetime.min.time())) \
        .all()
    by_day_consume: dict = defaultdict(int)
    for (ts,) in trend_rows:
        if ts:
            by_day_consume[ts.date().isoformat()] += 1
    trend = []
    cur = start_date
    while cur <= end_date:
        key = cur.isoformat()
        trend.append([key, by_day_consume.get(key, 0)])
        cur += timedelta(days=1)
    consume_30d = sum(v for _, v in trend)

    # ---- 计算「等级」：累计打卡 + 入库消耗合计映射 ----
    score = total_cooks * 3 + inv_consumed * 2 + saved_count
    if score < 10:
        level_name, level_idx = "厨房新手", 1
    elif score < 30:
        level_name, level_idx = "试菜达人", 2
    elif score < 80:
        level_name, level_idx = "家庭主厨", 3
    elif score < 200:
        level_name, level_idx = "美食家", 4
    else:
        level_name, level_idx = "大厨", 5

    # 下一档剩余分数
    next_thresholds = [10, 30, 80, 200, 500]
    next_score = next_thresholds[min(level_idx - 1, 4)]

    # ---- 徽章列表 ----
    def make(id_, name, desc, emoji, current, total):
        return {
            "id": id_, "name": name, "desc": desc, "emoji": emoji,
            "unlocked": current >= total,
            "progress": min(current, total), "total": total,
        }

    achievements = [
        make("first_recipe", "初入厨房", "收藏第一个食谱", "📚", saved_count, 1),
        make("recipes_5", "食谱收藏家", "累计收藏 5 个食谱", "📖", saved_count, 5),
        make("recipes_20", "美食宝典", "累计收藏 20 个食谱", "📕", saved_count, 20),
        make("first_cook", "我是大厨", "完成第一次打卡", "🍳", total_cooks, 1),
        make("cook_10", "厨艺精进", "累计打卡 10 次", "👨‍🍳", total_cooks, 10),
        make("cook_50", "百炼成钢", "累计打卡 50 次", "🏆", total_cooks, 50),
        make("rate_3", "美食评论员", "为 3 个食谱评分", "⭐", rated_count, 3),
        make("note_3", "厨房笔记", "为 3 个食谱写笔记", "📝", note_count, 3),
        make("first_pref", "了解你自己", "添加第一条饮食偏好", "💚", pref_count, 1),
        make("first_inv", "初识冰箱", "完成第一次入库", "🥬", inv_total, 1),
        make("inv_20", "充实冰箱", "累计入库 20 件食材", "🧊", inv_total, 20),
        make("consumed_50", "光盘行动", "累计有效消耗 50 件", "✨", inv_consumed, 50),
        make("category_10", "百味厨房", "管理过 10 种不同品类", "🌈", inv_categories, 10),
        make("week_user", "一周老友", "注册满 7 天", "📅", register_days, 7),
        make("month_user", "月度厨友", "注册满 30 天", "🎂", register_days, 30),
        make("notification", "细心管家", "收到 5 条临期通知", "🔔", notif_count, 5),
    ]

    unlocked_count = sum(1 for a in achievements if a["unlocked"])
    total_count = len(achievements)

    profile = {
        "username": user.username if user else "",
        "register_at": register_at.isoformat() if register_at else None,
        "register_days": register_days,
        "saved_count": saved_count,
        "total_cooks": total_cooks,
        "distinct_cooked_days": distinct_cooked_days,
        "rated_count": rated_count,
        "note_count": note_count,
        "pref_count": pref_count,
        "inv_total": inv_total,
        "inv_consumed": inv_consumed,
        "inv_wasted": inv_wasted,
        "inv_categories": inv_categories,
        "notif_count": notif_count,
        "level_name": level_name,
        "level_idx": level_idx,
        "level_score": score,
        "level_next_score": next_score,
        "consume_30d": consume_30d,
        "unlocked_count": unlocked_count,
        "total_count": total_count,
    }

    return {
        "profile": profile,
        "achievements": achievements,
        "consume_trend": trend,
    }


# ---- 购物清单（shopping_items）----

def list_shopping_items(db: Session, user_id: str) -> list:
    """返回用户购物清单，未勾选在前、按创建时间倒序。"""
    from models import ShoppingItem
    return (
        db.query(ShoppingItem)
        .filter(ShoppingItem.user_id == user_id)
        .order_by(ShoppingItem.checked.asc(), ShoppingItem.created_at.desc())
        .all()
    )


def add_shopping_item(db: Session, user_id: str, name: str, qty: int = 1,
                      source: str = "manual"):
    """添加一项。同名已存在则只增加数量（manual 优先级高，不覆盖 source）。"""
    from models import ShoppingItem
    name = (name or "").strip()
    if not name:
        return None
    existing = (
        db.query(ShoppingItem)
        .filter(ShoppingItem.user_id == user_id, ShoppingItem.name == name)
        .first()
    )
    if existing:
        existing.qty = (existing.qty or 1) + max(0, qty - 1)
        if existing.checked:
            existing.checked = False  # 重新加入视为未购
        db.commit()
        db.refresh(existing)
        return existing
    item = ShoppingItem(user_id=user_id, name=name, qty=max(1, qty), source=source)
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


def update_shopping_item(db: Session, user_id: str, item_id,
                         checked: Optional[bool] = None,
                         qty: Optional[int] = None):
    from models import ShoppingItem
    item = (
        db.query(ShoppingItem)
        .filter(ShoppingItem.id == item_id, ShoppingItem.user_id == user_id)
        .first()
    )
    if not item:
        return None
    if checked is not None:
        item.checked = checked
    if qty is not None:
        item.qty = max(1, qty)
    db.commit()
    db.refresh(item)
    return item


def delete_shopping_item(db: Session, user_id: str, item_id) -> bool:
    from models import ShoppingItem
    item = (
        db.query(ShoppingItem)
        .filter(ShoppingItem.id == item_id, ShoppingItem.user_id == user_id)
        .first()
    )
    if not item:
        return False
    db.delete(item)
    db.commit()
    return True


def clear_checked_shopping_items(db: Session, user_id: str) -> int:
    """清掉所有已勾选（已买）的项，返回删除数量。"""
    from models import ShoppingItem
    n = (
        db.query(ShoppingItem)
        .filter(ShoppingItem.user_id == user_id, ShoppingItem.checked == True)
        .delete()
    )
    db.commit()
    return n


def generate_shopping_suggestions(db: Session, user_id: str, days: int = 30) -> list:
    """根据"近期常消耗但当前库存不足"自动生成建议，写入清单（source=auto）。

    规则：统计窗口内 OUT_PENDING/CONSUMED 的品类频次，若某品类消耗 >= 2 次
    且当前在库 <= 1，则建议补货。已存在同名项则跳过。
    返回新增的建议项列表。
    """
    from datetime import datetime, timedelta
    from collections import Counter
    from models import Inventory, ShoppingItem

    since = datetime.now() - timedelta(days=days)
    consumed_rows = (
        db.query(Inventory.category)
        .filter(Inventory.created_at >= since,
                Inventory.status.in_(["OUT_PENDING", "CONSUMED"]))
        .all()
    )
    consumed = Counter(c[0] for c in consumed_rows if c[0])

    # 当前在库各品类数量
    stock_rows = (
        db.query(Inventory.category)
        .filter(Inventory.status == "IN_STOCK")
        .all()
    )
    stock = Counter(s[0] for s in stock_rows if s[0])

    # 已在清单里的名字（避免重复）
    existing_names = {
        r.name for r in db.query(ShoppingItem.name)
        .filter(ShoppingItem.user_id == user_id).all()
    }

    added = []
    for cat, cnt in consumed.most_common(20):
        if cnt >= 2 and stock.get(cat, 0) <= 1 and cat not in existing_names:
            qty = max(1, cnt // max(1, days // 7))   # 约按周消耗量
            item = ShoppingItem(user_id=user_id, name=cat, qty=qty, source="auto")
            db.add(item)
            added.append(item)
            existing_names.add(cat)

    if added:
        db.commit()
        for it in added:
            db.refresh(it)
    return added
