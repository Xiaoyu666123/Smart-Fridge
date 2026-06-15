import uuid
from datetime import datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import String, Float, Date, DateTime, ForeignKey, CheckConstraint, UniqueConstraint, Text, func
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
    feature_vector = mapped_column(Vector(1024), nullable=True)
    agent_metadata = mapped_column(JSONB, nullable=True)
    snapshot_path = mapped_column(String(255), nullable=True)
    image_hash: Mapped[str] = mapped_column(String(64), nullable=True)
    label_text: Mapped[str] = mapped_column(Text, nullable=True)
    label_data = mapped_column(JSONB, nullable=True)
    label_snapshot_path = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=True)
    update_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=True)
    stored_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=True)

    __table_args__ = (
        CheckConstraint(
            "status IN ('IN_STOCK', 'OUT_PENDING', 'CONSUMED', 'EXPIRED')",
            name="inventory_status_check",
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


class AgentTrace(Base):
    __tablename__ = "agent_traces"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    trace_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    agent_type: Mapped[str] = mapped_column(String(30), nullable=False)
    step_order: Mapped[int] = mapped_column(nullable=False)
    tool_name: Mapped[str] = mapped_column(String(50), nullable=False)
    tool_input = mapped_column(JSONB, nullable=True)
    tool_output = mapped_column(JSONB, nullable=True)
    status: Mapped[str] = mapped_column(String(10), nullable=False, default="SUCCESS")
    duration_ms: Mapped[int] = mapped_column(nullable=True)
    device_id: Mapped[str] = mapped_column(String(50), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=True)


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    username: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=True)


class Admin(Base):
    __tablename__ = "admins"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    username: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    real_name: Mapped[str] = mapped_column(String(50), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=True)


class Notification(Base):
    __tablename__ = "notifications"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    type: Mapped[str] = mapped_column(String(50), nullable=False, default="expiry_warning")
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    related_item_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("inventory.id", ondelete="CASCADE"), nullable=True)
    notice_date = mapped_column(Date, nullable=True)  # 当天生成的通知日期，配合每日去重
    is_read: Mapped[bool] = mapped_column(default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=True)

    # 同一用户、同一食材、同一天 只生成一条通知
    __table_args__ = (
        UniqueConstraint("user_id", "related_item_id", "notice_date",
                         name="uq_notification_user_item_date"),
    )


class CategoryThreshold(Base):
    __tablename__ = "category_thresholds"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    category: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    days_before_expiry: Mapped[int] = mapped_column(nullable=False, default=5)
    unit_price: Mapped[float] = mapped_column(Float, nullable=True)   # 该品类单件参考价（CNY）
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=True)


class PendingLabel(Base):
    """端侧扫描标签后的临时缓冲。

    生命周期：
      1) 端侧 POST /events/label_scan -> 后端 OCR 解析 -> 写一行（consumed_at = NULL）
      2) 端侧 POST /events/item (ITEM_IN) -> handle_item_in 找到该 device 最近未消费的标签
         -> 写到 inventory 的 label_* 字段 -> 把 consumed_at 标为 now()
      3) 没人消费的记录会在 expires_at 之后被懒清理
    """
    __tablename__ = "pending_labels"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    device_id: Mapped[str] = mapped_column(String(50), nullable=False)
    label_image_path: Mapped[str] = mapped_column(String(255), nullable=True)
    label_text: Mapped[str] = mapped_column(Text, nullable=True)
    label_data = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    consumed_at: Mapped[datetime] = mapped_column(DateTime, nullable=True)
    consumed_by_inventory_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("inventory.id", ondelete="SET NULL"),
        nullable=True,
    )


class LlmUsage(Base):
    """云端 API 调用 token 消耗与费用追踪。

    每一次 LLM/Vision/Embedding 的调用（成功或失败）都写一行，
    用于统计 dashboard 的"今日 token 消耗"和"按模型/按用户分布"。
    """
    __tablename__ = "llm_usage"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    provider: Mapped[str] = mapped_column(String(20), nullable=False)        # llm / vision / embedding
    model: Mapped[str] = mapped_column(String(100), nullable=False)
    endpoint: Mapped[str] = mapped_column(String(50), nullable=True)
    user_id: Mapped[str] = mapped_column(String(50), nullable=True)
    prompt_tokens: Mapped[int] = mapped_column(default=0)
    completion_tokens: Mapped[int] = mapped_column(default=0)
    total_tokens: Mapped[int] = mapped_column(default=0)
    cost_usd: Mapped[float] = mapped_column(Float, default=0.0)
    duration_ms: Mapped[int] = mapped_column(nullable=True)
    status: Mapped[str] = mapped_column(String(10), default="SUCCESS")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=True)


class SavedRecipe(Base):
    """用户收藏的结构化食谱。

    LLM 流式产出的食谱解析成结构化字段后，用户点"收藏"会写到这张表。
    支持"做过了"打卡（cooked_count 自增 + last_cooked_at 更新）。
    """
    __tablename__ = "saved_recipes"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[str] = mapped_column(String(50), nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    summary: Mapped[str] = mapped_column(Text, nullable=True)
    prep_time: Mapped[int] = mapped_column(nullable=True)
    difficulty: Mapped[str] = mapped_column(String(20), nullable=True)
    ingredients = mapped_column(JSONB, nullable=True)
    steps = mapped_column(JSONB, nullable=True)
    tags = mapped_column(JSONB, nullable=True)
    source: Mapped[str] = mapped_column(String(20), default="chat")
    cooked_count: Mapped[int] = mapped_column(default=0)
    last_cooked_at: Mapped[datetime] = mapped_column(DateTime, nullable=True)
    rating: Mapped[int] = mapped_column(nullable=True)            # 1-5 星，未评分时 NULL
    notes: Mapped[str] = mapped_column(Text, nullable=True)       # 自由备注
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=True)


class VisionAssistConfig(Base):
    """云端视觉辅助识别触发区间策略（全局单行）。

    端侧 ITEM_IN 上报置信度 落入 [lower_bound, upper_bound] 时才触发云端 vision 辅助识别。
    手动入库 POST /admin/inventory 复用同一区间。
    """
    __tablename__ = "vision_assist_config"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    # 数据库列名是 PG 保留字 lower / upper，加引号；Python 端用 lower_bound / upper_bound 避免和内建冲突
    lower_bound: Mapped[float] = mapped_column("lower", Float, nullable=False, default=0.30)
    upper_bound: Mapped[float] = mapped_column("upper", Float, nullable=False, default=0.70)
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=True)
    updated_by_admin_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("admins.id", ondelete="SET NULL"), nullable=True
    )


class Device(Base):
    """端侧设备表。
    第一次上报时自动注册。后台可改名 / 改位置 / 标注离线策略。
    """
    __tablename__ = "devices"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    device_id: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=True)         # 显示名："厨房冰箱"
    location: Mapped[str] = mapped_column(String(100), nullable=True)     # 位置标签："客厅"
    description: Mapped[str] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="online")     # online / idle / offline
    last_seen_at: Mapped[datetime] = mapped_column(DateTime, nullable=True)
    last_event_type: Mapped[str] = mapped_column(String(30), nullable=True)
    heartbeat_count: Mapped[int] = mapped_column(default=0)
    registered_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=True)


class DeviceHeartbeat(Base):
    """设备心跳流水（保留近 24 小时即可，定期清理）。"""
    __tablename__ = "device_heartbeats"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    device_id: Mapped[str] = mapped_column(String(50), nullable=False)
    event: Mapped[str] = mapped_column(String(30), default="heartbeat")  # heartbeat / startup / item_in / item_out / label_scan
    payload = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=True)


class DeviceRawEvent(Base):
    """端侧联调收件箱。

    保存端侧上报的原始结构和后端规范化后的结构，方便排查字段不匹配、
    识别失败、图片缺失等对接问题。base64 图片不长期入库，只保留摘要。
    """
    __tablename__ = "device_raw_events"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    device_id: Mapped[str] = mapped_column(String(50), nullable=True)
    event_type: Mapped[str] = mapped_column(String(30), nullable=True)
    raw_payload = mapped_column(JSONB, nullable=True)
    normalized_payload = mapped_column(JSONB, nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="received")
    error_message: Mapped[str] = mapped_column(Text, nullable=True)
    related_inventory_ids = mapped_column(JSONB, nullable=True)
    trace_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=True)
    processed_at: Mapped[datetime] = mapped_column(DateTime, nullable=True)

    __table_args__ = (
        CheckConstraint(
            "status IN ('received', 'processing', 'success', 'failed', 'ignored')",
            name="device_raw_events_status_check",
        ),
    )


class ShoppingItem(Base):
    """用户购物清单项。

    source:
      - auto    系统根据"近期常消耗但库存不足"自动建议生成
      - manual  用户手动添加
    checked: 是否已购买（前端勾选）。
    """
    __tablename__ = "shopping_items"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[str] = mapped_column(String(50), nullable=False)
    name: Mapped[str] = mapped_column(String(50), nullable=False)
    qty: Mapped[int] = mapped_column(default=1)
    checked: Mapped[bool] = mapped_column(default=False)
    source: Mapped[str] = mapped_column(String(20), default="manual")  # auto / manual
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=True)

    __table_args__ = (
        UniqueConstraint("user_id", "name", name="uq_shopping_user_name"),
    )
