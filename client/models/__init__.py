import uuid
from datetime import datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import String, Float, DateTime, ForeignKey, CheckConstraint, UniqueConstraint, func
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
    role: Mapped[str] = mapped_column(String(20), nullable=False, default="user")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=True)

    __table_args__ = (
        CheckConstraint("role IN ('user', 'admin')", name="ck_user_role"),
    )


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
