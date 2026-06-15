import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field, field_validator, computed_field

MAX_BASE64_IMAGE_CHARS = 7 * 1024 * 1024
MAX_EVENT_ITEMS = 100


class ItemData(BaseModel):
    local_track_id: int
    category: str = Field(..., min_length=1, max_length=50)
    confidence: float = Field(..., ge=0.0, le=1.0)
    bbox: list[int] = Field(..., min_length=4, max_length=4)
    crop_image: Optional[str] = Field(None, max_length=MAX_BASE64_IMAGE_CHARS)


def _default_device_id() -> str:
    from config import settings as _s
    return _s.DEVICE_ID


class ItemEventRequest(BaseModel):
    device_id: str = Field(default_factory=_default_device_id, min_length=1, max_length=50)
    timestamp: int
    event_type: str = Field(..., pattern="^(ITEM_IN|ITEM_OUT|ITEM_MOVED|AGENT_UPDATE)$")
    data: list[ItemData] = Field(..., min_length=1, max_length=MAX_EVENT_ITEMS)

    @field_validator('device_id', mode='before')
    @classmethod
    def fill_default_device_id(cls, v):
        if not v:
            return _default_device_id()
        return v


class InventoryResponse(BaseModel):
    id: uuid.UUID
    device_id: str
    category: str
    status: str
    remain_ratio: float
    bbox: Optional[list] = None
    feature_vector: Optional[list[float]] = None
    agent_metadata: Optional[dict] = None
    snapshot_path: Optional[str] = None
    label_text: Optional[str] = None
    label_data: Optional[dict] = None
    label_snapshot_path: Optional[str] = None
    created_at: Optional[datetime] = None
    update_at: Optional[datetime] = None
    stored_at: Optional[datetime] = None

    class Config:
        from_attributes = True

    @field_validator('feature_vector', mode='before')
    @classmethod
    def convert_numpy(cls, v):
        if v is None:
            return None
        return [float(x) for x in v]

    # ---- 计算字段：方便前端 / 调试时一眼看出标签状态 ----

    @computed_field
    @property
    def has_label(self) -> bool:
        """是否带标签（label_data 或 label_text 非空即视为有）。"""
        return bool(self.label_data) or bool(self.label_text)

    @computed_field
    @property
    def label_status(self) -> str:
        """label / no_label，便于过滤和断言。"""
        return "label" if self.has_label else "no_label"

    @computed_field
    @property
    def expire_source(self) -> Optional[str]:
        """保质期来源：label / llm_estimate / manual / None。从 agent_metadata 提取。"""
        if not self.agent_metadata:
            return None
        return self.agent_metadata.get("expire_source")

    @computed_field
    @property
    def expire_at(self) -> Optional[str]:
        """ISO 格式过期时间，从 agent_metadata 提取。"""
        if not self.agent_metadata:
            return None
        return self.agent_metadata.get("expire_at")

    @computed_field
    @property
    def brand(self) -> Optional[str]:
        """品牌（从 label_data 提取，无则 None）。"""
        if not self.label_data:
            return None
        v = self.label_data.get("brand")
        return v if v else None


class InventoryCreateRequest(BaseModel):
    device_id: str = Field(default_factory=_default_device_id, min_length=1, max_length=50)
    category: str = Field(..., min_length=1, max_length=50)
    status: str = Field("IN_STOCK", pattern="^(IN_STOCK|OUT_PENDING|CONSUMED|EXPIRED)$")
    remain_ratio: float = Field(1.0, ge=0.0, le=1.0)
    bbox: Optional[list] = None
    agent_metadata: Optional[dict] = None
    snapshot_path: Optional[str] = Field(None, max_length=255)

    @field_validator('device_id', mode='before')
    @classmethod
    def fill_default_device_id(cls, v):
        if not v:
            return _default_device_id()
        return v


class InventoryUpdateRequest(BaseModel):
    category: Optional[str] = Field(None, min_length=1, max_length=50)
    status: Optional[str] = Field(None, pattern="^(IN_STOCK|OUT_PENDING|CONSUMED|EXPIRED)$")
    remain_ratio: Optional[float] = Field(None, ge=0.0, le=1.0)
    bbox: Optional[list] = None
    agent_metadata: Optional[dict] = None
    snapshot_path: Optional[str] = Field(None, max_length=255)


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
    message: str = Field(..., min_length=1, max_length=2000)
    city: Optional[str] = Field(None, max_length=50)


class ChatResponse(BaseModel):
    reply: str
    detected_preferences: list


class RecognizeRequest(BaseModel):
    image: str = Field(..., min_length=1, max_length=MAX_BASE64_IMAGE_CHARS)


class RecognizeResponse(BaseModel):
    category: str
    confidence: float
    shelf_life_days: int
    storage_advice: str


class DetectedFoodItem(BaseModel):
    category: str
    confidence: float
    bbox: list[float] = Field(..., min_length=4, max_length=4)


class DetectResponse(BaseModel):
    items: list[DetectedFoodItem]


class AgentModelConfig(BaseModel):
    provider: str = Field("", max_length=50)
    model: str = Field("", max_length=100)
    api_url: str = Field("", max_length=500)
    api_key_masked: Optional[str] = None
    status: str = "未配置"
    has_api_key: bool = False


class AgentConfigResponse(BaseModel):
    vision: AgentModelConfig
    llm: AgentModelConfig
    # 兼容旧前端字段
    vision_model: str = ""
    vision_status: str = "未配置"
    llm_model: str = ""
    llm_status: str = "未配置"


class AgentModelConfigUpdate(BaseModel):
    provider: str = Field(..., min_length=1, max_length=50)
    model: str = Field(..., min_length=1, max_length=100)
    api_url: str = Field(..., min_length=1, max_length=500)
    api_key: Optional[str] = Field(None, max_length=500)


class AgentConfigUpdateRequest(BaseModel):
    vision: AgentModelConfigUpdate
    llm: AgentModelConfigUpdate


class BulkInventoryItem(BaseModel):
    category: str = Field(..., min_length=1, max_length=50)
    confidence: float = 0.9
    bbox: Optional[list[float]] = None
    snapshot_path: Optional[str] = Field(None, max_length=255)


class BulkInventoryRequest(BaseModel):
    device_id: str = Field(default_factory=_default_device_id, min_length=1, max_length=50)
    items: list[BulkInventoryItem] = Field(..., min_length=1, max_length=MAX_EVENT_ITEMS)

    @field_validator('device_id', mode='before')
    @classmethod
    def fill_default_device_id(cls, v):
        if not v:
            return _default_device_id()
        return v


class BulkInventoryResponse(BaseModel):
    created_count: int
    inventory_ids: list[str]
    skipped_count: int = 0
    skipped: list[dict] = []


class PreferenceResponse(BaseModel):
    id: uuid.UUID
    user_id: str
    preference_key: str
    preference_value: str
    source: Optional[str] = None
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class PreferenceAddRequest(BaseModel):
    preference_key: str = Field(..., min_length=1, max_length=100)
    preference_value: str = Field(..., min_length=1, max_length=500)


# ---- Trace 相关 Schema ----

class TraceStepResponse(BaseModel):
    id: int
    step_order: int
    tool_name: str
    tool_input: Optional[dict] = None
    tool_output: Optional[dict] = None
    status: str
    duration_ms: Optional[int] = None

    class Config:
        from_attributes = True


class TraceSummaryResponse(BaseModel):
    trace_id: str
    agent_type: str
    device_id: Optional[str] = None
    step_count: int
    total_duration_ms: Optional[int] = None
    created_at: Optional[datetime] = None


class TraceDetailResponse(BaseModel):
    trace_id: str
    agent_type: str
    device_id: Optional[str] = None
    steps: list[TraceStepResponse]


# ---- Environment 相关 Schema ----

class EnvironmentResponse(BaseModel):
    city: str
    region: Optional[str] = None
    temperature: Optional[float] = None
    feels_like: Optional[float] = None
    humidity: Optional[float] = None
    wind_speed: Optional[float] = None
    wind_dir: Optional[str] = None
    weather_code: Optional[str] = None
    weather_desc: str
    cloudcover: Optional[float] = None
    visibility: Optional[float] = None
    pressure: Optional[float] = None
    precip: Optional[float] = None
    uv_index: Optional[float] = None
    season: str
    sunrise: Optional[str] = None
    sunset: Optional[str] = None
    updated_at: str


# ---- Logs 相关 Schema ----

class LogEntryResponse(BaseModel):
    id: str
    source: str
    event_type: str
    status: str
    detail: Optional[dict] = None
    created_at: Optional[str] = None


# ---- Auth 相关 Schema ----

class RegisterRequest(BaseModel):
    username: str = Field(..., min_length=3, max_length=50)
    password: str = Field(..., min_length=6)


class LoginRequest(BaseModel):
    username: str
    password: str


class UserTokenResponse(BaseModel):
    """普通用户登录返回"""
    token: str
    user_id: str
    username: str
    user_type: str = "user"


class AdminTokenResponse(BaseModel):
    """管理员登录返回"""
    token: str
    admin_id: str
    username: str
    user_type: str = "admin"


class UserInfoResponse(BaseModel):
    id: str
    username: str
    user_type: str = "user"
    created_at: Optional[datetime] = None


class AdminInfoResponse(BaseModel):
    id: str
    username: str
    user_type: str = "admin"
    real_name: Optional[str] = None
    created_at: Optional[datetime] = None


class AdminUserListItem(BaseModel):
    """管理员视角下的普通用户条目"""
    id: str
    username: str
    created_at: Optional[datetime] = None
    inventory_count: int = 0
    preference_count: int = 0
    conversation_count: int = 0


class AdminCreateUserRequest(BaseModel):
    username: str = Field(..., min_length=3, max_length=50)
    password: str = Field(..., min_length=6)


class AdminResetPasswordRequest(BaseModel):
    new_password: str = Field(..., min_length=6)


class ChangeOwnPasswordRequest(BaseModel):
    old_password: str
    new_password: str = Field(..., min_length=6)


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
    unit_price: Optional[float] = None
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class CategoryThresholdUpdateRequest(BaseModel):
    days_before_expiry: Optional[int] = Field(None, ge=1, le=365)
    unit_price: Optional[float] = Field(None, ge=0, le=100000)


# ---- 标签缓冲（pending_labels）相关 Schema ----

class LabelScanRequest(BaseModel):
    """端侧扫描标签后上传"""
    device_id: str = Field(default_factory=_default_device_id, min_length=1, max_length=50)
    label_image: str = Field(
        ...,
        min_length=1,
        max_length=MAX_BASE64_IMAGE_CHARS,
        description="标签裁剪图 base64（不含 data: 前缀）",
    )
    ttl_seconds: int = Field(300, ge=10, le=3600, description="缓冲存活时间，默认 5 分钟")

    @field_validator('device_id', mode='before')
    @classmethod
    def fill_default_device_id(cls, v):
        if not v:
            return _default_device_id()
        return v


class LabelScanResponse(BaseModel):
    pending_label_id: str
    label_text: str = ""
    label_data: dict
    expires_at: datetime


class PendingLabelItem(BaseModel):
    id: str
    device_id: str
    label_image_path: Optional[str] = None
    label_text: Optional[str] = None
    label_data: Optional[dict] = None
    created_at: Optional[datetime] = None
    expires_at: Optional[datetime] = None
    consumed_at: Optional[datetime] = None
    consumed_by_inventory_id: Optional[str] = None
    status: str = "pending"  # pending / consumed / expired


# ---- 食谱收藏 ----

class RecipeIngredient(BaseModel):
    name: str
    amount: Optional[str] = ""


class SavedRecipeRequest(BaseModel):
    name: str
    summary: Optional[str] = ""
    prep_time: Optional[int] = None
    difficulty: Optional[str] = None
    ingredients: Optional[list[RecipeIngredient]] = None
    steps: Optional[list[str]] = None
    tags: Optional[list[str]] = None


class SavedRecipeResponse(BaseModel):
    id: str
    user_id: str
    name: str
    summary: Optional[str] = None
    prep_time: Optional[int] = None
    difficulty: Optional[str] = None
    ingredients: Optional[list] = None
    steps: Optional[list] = None
    tags: Optional[list] = None
    source: Optional[str] = None
    cooked_count: int = 0
    last_cooked_at: Optional[datetime] = None
    rating: Optional[int] = None
    notes: Optional[str] = None
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class RecipeUpdateRequest(BaseModel):
    rating: Optional[int] = Field(None, ge=1, le=5)
    notes: Optional[str] = None


class CookRecipeRequest(BaseModel):
    """打卡时声明用了哪些库存项。"""
    consumed_inventory_ids: list[str] = Field(default_factory=list)


class CookRecipeResponse(BaseModel):
    recipe: SavedRecipeResponse
    consumed_count: int = 0
    consumed_inventory_ids: list[str] = Field(default_factory=list)
    skipped_inventory_ids: list[str] = Field(default_factory=list)


# ---- 视觉辅助识别策略 ----

class VisionAssistConfigResponse(BaseModel):
    id: str
    lower: float = Field(..., ge=0, le=1)
    upper: float = Field(..., ge=0, le=1)
    updated_at: Optional[datetime] = None
    updated_by_admin_id: Optional[str] = None
    is_default: bool = False


class VisionAssistConfigUpdateRequest(BaseModel):
    lower: float = Field(..., ge=0, le=1, description="下界，闭区间 [0,1]，必须严格小于 upper")
    upper: float = Field(..., ge=0, le=1, description="上界，闭区间 [0,1]，必须严格大于 lower")


# ---- 设备 ----

class DeviceItem(BaseModel):
    id: str
    device_id: str
    name: str
    location: Optional[str] = None
    description: Optional[str] = None
    status: str
    live_status: str           # online / idle / offline
    last_seen_at: Optional[str] = None
    last_event_type: Optional[str] = None
    heartbeat_count: int = 0
    registered_at: Optional[str] = None
    seconds_since_last_seen: Optional[int] = None


class DeviceUpdateRequest(BaseModel):
    name: Optional[str] = None
    location: Optional[str] = None
    description: Optional[str] = None


class HeartbeatRequest(BaseModel):
    device_id: str = Field(default_factory=_default_device_id)
    event: Optional[str] = "heartbeat"
    payload: Optional[dict] = None

    @field_validator('device_id', mode='before')
    @classmethod
    def fill_default_device_id(cls, v):
        if not v:
            return _default_device_id()
        return v


class HeartbeatResponse(BaseModel):
    device_id: str
    name: str
    status: str
    last_seen_at: Optional[str] = None
    auto_registered: bool = False


class DeviceRawEventResponse(BaseModel):
    id: uuid.UUID
    device_id: Optional[str] = None
    event_type: Optional[str] = None
    raw_payload: Optional[dict] = None
    normalized_payload: Optional[dict] = None
    status: str
    error_message: Optional[str] = None
    related_inventory_ids: Optional[list[str]] = None
    trace_id: Optional[uuid.UUID] = None
    created_at: Optional[datetime] = None
    processed_at: Optional[datetime] = None

    class Config:
        from_attributes = True
