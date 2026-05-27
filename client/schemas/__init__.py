import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field, field_validator


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
    feature_vector: Optional[list[float]] = None
    agent_metadata: Optional[dict] = None
    snapshot_path: Optional[str] = None
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


class InventoryCreateRequest(BaseModel):
    device_id: str
    category: str
    status: str = "IN_STOCK"
    remain_ratio: float = 1.0
    bbox: Optional[list] = None
    agent_metadata: Optional[dict] = None
    snapshot_path: Optional[str] = None


class InventoryUpdateRequest(BaseModel):
    category: Optional[str] = None
    status: Optional[str] = None
    remain_ratio: Optional[float] = None
    bbox: Optional[list] = None
    agent_metadata: Optional[dict] = None
    snapshot_path: Optional[str] = None


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


class PreferenceAddRequest(BaseModel):
    preference_key: str
    preference_value: str


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


class TokenResponse(BaseModel):
    token: str
    user_id: str
    username: str
    role: str


class UserResponse(BaseModel):
    id: str
    username: str
    role: str
    created_at: Optional[datetime] = None


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
