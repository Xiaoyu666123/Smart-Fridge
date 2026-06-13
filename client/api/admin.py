"""管理员后台路由 (/api/v1/admin/*)。

仅持有 admin token 的会话可访问，所有路由统一通过 get_current_admin 依赖鉴权。
"""

import os
import time
import uuid
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Response, WebSocket, WebSocketDisconnect, Query
from sqlalchemy.orm import Session

from database import get_db
from models import Admin, Inventory
from schemas import (
    LoginRequest, AdminTokenResponse, AdminInfoResponse,
    ItemEventRequest, InventoryResponse, InventoryCreateRequest, InventoryUpdateRequest,
    EventLogResponse, TraceSummaryResponse, TraceDetailResponse,
    LogEntryResponse, CategoryThresholdResponse, CategoryThresholdUpdateRequest,
    AdminUserListItem, AdminCreateUserRequest, AdminResetPasswordRequest,
    ChangeOwnPasswordRequest,
    BulkInventoryRequest, BulkInventoryResponse,
    RecognizeRequest, DetectResponse,
    AgentConfigResponse, AgentModelConfig, AgentConfigUpdateRequest,
    LabelScanRequest, LabelScanResponse, PendingLabelItem,
    VisionAssistConfigResponse, VisionAssistConfigUpdateRequest,
    DeviceItem, DeviceUpdateRequest, HeartbeatRequest, HeartbeatResponse,
)
from crud import (
    handle_item_event, get_inventory_list, get_inventory_by_id, get_event_logs,
    count_inventory,
    get_trace_list, get_trace_detail, get_unified_logs, save_log,
    get_admin_by_username, get_user_by_username, get_all_thresholds, update_threshold,
    list_users_with_stats, update_user_password, delete_user,
    create_user, get_user_by_id, update_admin_password,
    create_pending_label, list_pending_labels, cleanup_expired_pending_labels,
    get_usage_summary, list_usage_records,
    get_waste_analytics,
    upsert_device_seen, list_devices, get_device, update_device_meta, delete_device,
    restore_device,
    get_device_heartbeat_series,
    get_tool_perf_stats,
    get_nutrition_report,
    get_lifecycle_sankey,
    get_waste_calendar,
)
from agents import FridgeAgent
from services.auth import (
    hash_password, verify_password, create_admin_token, get_current_admin,
    decode_admin_token,
)
from services.upload_security import (
    make_upload_filename, safe_image_extension, save_image_bytes,
)

router = APIRouter(prefix="/admin")

UPLOAD_DIR = "uploads"


# ---- Auth ----

@router.post("/auth/login", response_model=AdminTokenResponse)
def admin_login(req: LoginRequest, db: Session = Depends(get_db)):
    # 拒绝普通用户账号通过管理员入口登录
    if get_user_by_username(db, req.username):
        raise HTTPException(status_code=401, detail="用户名或密码错误")
    admin = get_admin_by_username(db, req.username)
    if not admin or not verify_password(req.password, admin.password_hash):
        raise HTTPException(status_code=401, detail="用户名或密码错误")
    token = create_admin_token(str(admin.id))
    return AdminTokenResponse(token=token, admin_id=str(admin.id), username=admin.username)


@router.get("/auth/me", response_model=AdminInfoResponse)
def admin_me(admin: Admin = Depends(get_current_admin)):
    return AdminInfoResponse(
        id=str(admin.id), username=admin.username,
        real_name=admin.real_name, created_at=admin.created_at,
    )


# ---- 设备事件接收 ----

@router.post("/events/item", response_model=list[InventoryResponse])
def receive_item_event(event: ItemEventRequest, db: Session = Depends(get_db),
                       admin: Admin = Depends(get_current_admin)):
    try:
        # 端侧事件视为设备活跃信号
        try:
            upsert_device_seen(db, event.device_id, event=event.event_type or "item_event",
                                payload={"items": len(event.data) if event.data else 0})
        except Exception:
            pass
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


# ---- Inventory CRUD ----

@router.get("/inventory", response_model=list[InventoryResponse])
def list_inventory(
    response: Response,
    device_id: Optional[str] = None,
    status: Optional[str] = None,
    category: Optional[str] = None,
    q: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    expiring_in_days: Optional[int] = None,
    limit: Optional[int] = Query(None, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    admin: Admin = Depends(get_current_admin),
):
    try:
        total = count_inventory(db, device_id=device_id, status=status, category=category,
                                  q=q, start_date=start_date, end_date=end_date,
                                  expiring_in_days=expiring_in_days)
        rows = get_inventory_list(db, device_id=device_id, status=status, category=category,
                                  limit=limit, offset=offset,
                                  q=q, start_date=start_date, end_date=end_date,
                                  expiring_in_days=expiring_in_days)
        response.headers["X-Total-Count"] = str(total)
        response.headers["Access-Control-Expose-Headers"] = "X-Total-Count"
        return rows
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"查询库存失败: {str(e)}")


@router.get("/inventory/categories")
def list_categories(db: Session = Depends(get_db), admin: Admin = Depends(get_current_admin)):
    try:
        from sqlalchemy import distinct
        rows = db.query(distinct(Inventory.category)).order_by(Inventory.category).all()
        return [r[0] for r in rows if r[0]]
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"查询分类列表失败: {str(e)}")


@router.get("/inventory/{inventory_id}", response_model=InventoryResponse)
def get_inventory_detail(inventory_id: uuid.UUID, db: Session = Depends(get_db),
                         admin: Admin = Depends(get_current_admin)):
    try:
        item = get_inventory_by_id(db, inventory_id)
        if not item:
            raise HTTPException(status_code=404, detail="库存记录不存在")
        return item
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"查询库存详情失败: {str(e)}")


@router.post("/inventory/upload-image")
def upload_inventory_image(file: UploadFile = File(...), admin: Admin = Depends(get_current_admin)):
    allowed_types = {"image/jpeg", "image/png", "image/gif", "image/webp"}
    if file.content_type not in allowed_types:
        raise HTTPException(status_code=400, detail="仅支持 JPG/PNG/GIF/WEBP 格式图片")
    ext = safe_image_extension(file.filename, file.content_type)
    filename = make_upload_filename(f"inv_{int(time.time())}", ext)
    try:
        from config import settings
        data = file.file.read(settings.MAX_IMAGE_BYTES + 1)
        filepath = save_image_bytes(filename, data)
    except ValueError:
        raise HTTPException(status_code=413, detail="图片过大")
    return {"snapshot_path": filepath, "url": f"/uploads/{filename}"}


@router.post("/inventory", response_model=InventoryResponse)
def create_inventory(req: InventoryCreateRequest, db: Session = Depends(get_db),
                     admin: Admin = Depends(get_current_admin)):
    import logging
    from services.dedup import check_duplicate

    logger = logging.getLogger(__name__)

    # 统一去重：hash 优先 + 全表向量比对
    image_hash, feature_vector, dup = check_duplicate(
        db, req.snapshot_path, category=req.category,
    )
    if dup:
        if dup["reason"] == "hash":
            raise HTTPException(status_code=409, detail="该图片已入库（字节完全相同），无需重复添加")
        # vector 命中
        sim = dup["similarity"]
        matched_cat = dup.get("matched_category", "已有")
        raise HTTPException(
            status_code=409,
            detail=f"该物品与「{matched_cat}」的已有库存相似度 {sim:.2f}，判定为同一物品，无需重复入库",
        )

    # 视觉辅助：基于动态区间策略 vision_assist_config 决定是否触发云端复核
    category = req.category
    confidence = req.agent_metadata.get("confidence") if req.agent_metadata else None
    from services.vision_assist import decide as decide_vision_assist
    decision = decide_vision_assist(
        db,
        edge_confidence=float(confidence) if confidence is not None else None,
        has_crop_image=bool(req.snapshot_path),
    )
    logger.info(
        f"[VisionAssist] manual-create decision={decision.decision} | "
        f"edge_conf={decision.edge_confidence} | range=[{decision.lower}, {decision.upper}] | "
        f"category={req.category}"
    )

    if decision.triggered:
        try:
            import base64
            from services.vision import recognize_food
            image_path = req.snapshot_path.replace('\\', '/')
            with open(image_path, "rb") as f:
                image_b64 = base64.b64encode(f.read()).decode()
            vision_result = recognize_food(image_b64)
            original = req.category
            vision_category = vision_result["category"]
            save_log(db, "vision_recognize", "VISION_ASSIST",
                      "SUCCESS" if vision_category != "unknown" else "FAILED",
                      {"original_category": original, "original_confidence": float(confidence),
                       "vision_category": vision_category,
                       "vision_confidence": vision_result.get("confidence", 0),
                       "decision": decision.decision,
                       "lower": decision.lower, "upper": decision.upper})
            if vision_category and vision_category != "unknown":
                category = vision_category
                logger.info(f"[Vision] 采用云端视觉识别结果 | original={original}({confidence}) -> vision={category}({vision_result['confidence']:.2f})")
        except Exception as e:
            logger.error(f"[Vision] 辅助识别异常，保留原始分类 | error={e}")
            try:
                save_log(db, "vision_recognize", "VISION_ASSIST", "FAILED",
                         {"error": str(e), "original_category": req.category})
            except Exception:
                pass

    try:
        metadata = dict(req.agent_metadata) if req.agent_metadata else {}

        # 关联缓冲标签（手动入库也享用同一套机制）
        from crud import find_active_pending_label, consume_pending_label
        from datetime import datetime as _dt
        pending_label = find_active_pending_label(db, req.device_id)
        label_text_val = pending_label.label_text if pending_label else None
        label_data_val = pending_label.label_data if pending_label else None
        label_path_val = pending_label.label_image_path if pending_label else None
        if pending_label and label_data_val and label_data_val.get("expire_date"):
            try:
                metadata["expire_at"] = _dt.fromisoformat(label_data_val["expire_date"]).isoformat()
                metadata["expire_source"] = "label"
            except Exception:
                metadata["expire_source"] = metadata.get("expire_source", "manual")

        item = Inventory(
            device_id=req.device_id,
            category=category,
            status=req.status,
            remain_ratio=req.remain_ratio,
            bbox=req.bbox,
            agent_metadata=metadata,
            snapshot_path=req.snapshot_path,
            feature_vector=feature_vector,
            image_hash=image_hash,
            label_text=label_text_val,
            label_data=label_data_val,
            label_snapshot_path=label_path_val,
        )
        db.add(item)
        db.commit()
        db.refresh(item)
        if pending_label:
            try:
                consume_pending_label(db, pending_label.id, item.id)
            except Exception:
                pass
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"添加库存失败: {str(e)}")

    from services.background import compute_freshness_task
    compute_freshness_task(item.id, item.category)

    # 广播给所有在线用户：库存新增
    try:
        from services.ws_events import broadcast_inventory_created
        broadcast_inventory_created(item, source="manual")
    except Exception:
        pass

    return item


@router.put("/inventory/{inventory_id}", response_model=InventoryResponse)
def update_inventory(inventory_id: uuid.UUID, req: InventoryUpdateRequest,
                     db: Session = Depends(get_db), admin: Admin = Depends(get_current_admin)):
    try:
        item = get_inventory_by_id(db, inventory_id)
        if not item:
            raise HTTPException(status_code=404, detail="库存记录不存在")
        prev_status = item.status
        if req.category is not None:
            item.category = req.category
        if req.status is not None:
            item.status = req.status
        if req.remain_ratio is not None:
            item.remain_ratio = req.remain_ratio
        if req.bbox is not None:
            item.bbox = req.bbox
        if req.agent_metadata is not None:
            item.agent_metadata = req.agent_metadata
        if req.snapshot_path is not None:
            item.snapshot_path = req.snapshot_path
        db.commit()
        db.refresh(item)
        # 广播：库存更新
        try:
            from services.ws_events import broadcast_inventory_updated
            broadcast_inventory_updated(item, source="manual", prev_status=prev_status)
        except Exception:
            pass
        return item
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"更新库存失败: {str(e)}")


@router.delete("/inventory/{inventory_id}")
def delete_inventory(inventory_id: uuid.UUID, db: Session = Depends(get_db),
                     admin: Admin = Depends(get_current_admin)):
    try:
        item = get_inventory_by_id(db, inventory_id)
        if not item:
            raise HTTPException(status_code=404, detail="库存记录不存在")
        deleted_id = str(item.id)
        db.delete(item)
        db.commit()
        # 广播：库存删除
        try:
            from services.ws_events import broadcast_inventory_deleted
            broadcast_inventory_deleted(deleted_id, source="manual")
        except Exception:
            pass
        return {"detail": "删除成功"}
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"删除库存失败: {str(e)}")


# ---- Events ----

@router.get("/events", response_model=list[EventLogResponse])
def list_events(
    inventory_id: Optional[uuid.UUID] = None,
    db: Session = Depends(get_db),
    admin: Admin = Depends(get_current_admin),
):
    try:
        return get_event_logs(db, inventory_id=inventory_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"查询事件日志失败: {str(e)}")


# ---- Agent 配置 ----

@router.get("/agent/config", response_model=AgentConfigResponse)
def get_agent_config(admin: Admin = Depends(get_current_admin)):
    from config import settings as _settings

    vision_ok = bool(_settings.VISION_API_KEY and _settings.VISION_API_URL)
    llm_ok = bool(_settings.LLM_API_KEY and _settings.LLM_API_URL)

    return _agent_config_response(_settings, vision_ok, llm_ok)


@router.put("/agent/config", response_model=AgentConfigResponse)
def update_agent_config(req: AgentConfigUpdateRequest,
                        admin: Admin = Depends(get_current_admin)):
    from config import settings as _settings

    def clean_api_key(v: Optional[str]) -> Optional[str]:
        if v is None:
            return None
        stripped = v.strip()
        return stripped or None

    vision_key = clean_api_key(req.vision.api_key)
    llm_key = clean_api_key(req.llm.api_key)

    _settings.VISION_PROVIDER = req.vision.provider.strip()
    _settings.VISION_MODEL = req.vision.model.strip()
    _settings.VISION_API_URL = req.vision.api_url.strip()
    if vision_key is not None:
        _settings.VISION_API_KEY = vision_key

    _settings.LLM_PROVIDER = req.llm.provider.strip()
    _settings.LLM_MODEL = req.llm.model.strip()
    _settings.LLM_API_URL = req.llm.api_url.strip()
    if llm_key is not None:
        _settings.LLM_API_KEY = llm_key

    try:
        _write_runtime_agent_env(_settings, include_vision_key=vision_key is not None,
                                 include_llm_key=llm_key is not None)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"保存配置失败: {str(e)}")

    return _agent_config_response(
        _settings,
        bool(_settings.VISION_API_KEY and _settings.VISION_API_URL),
        bool(_settings.LLM_API_KEY and _settings.LLM_API_URL),
    )


def _mask_secret(v: str) -> Optional[str]:
    if not v:
        return None
    if len(v) <= 8:
        return "*" * len(v)
    return f"{v[:3]}****{v[-4:]}"


def _infer_provider(api_url: str, fallback: str) -> str:
    if fallback:
        return fallback
    url = (api_url or "").lower()
    if "deepseek" in url:
        return "deepseek"
    if "dashscope" in url or "aliyuncs" in url:
        return "dashscope"
    if "openai" in url:
        return "openai"
    return "custom"


def _agent_config_response(_settings, vision_ok: bool, llm_ok: bool) -> AgentConfigResponse:
    vision_provider = _infer_provider(_settings.VISION_API_URL, getattr(_settings, "VISION_PROVIDER", ""))
    llm_provider = _infer_provider(_settings.LLM_API_URL, getattr(_settings, "LLM_PROVIDER", ""))
    return AgentConfigResponse(
        vision=AgentModelConfig(
            provider=vision_provider,
            model=_settings.VISION_MODEL,
            api_url=_settings.VISION_API_URL,
            api_key_masked=_mask_secret(_settings.VISION_API_KEY),
            status="已连接" if vision_ok else "未配置",
            has_api_key=bool(_settings.VISION_API_KEY),
        ),
        llm=AgentModelConfig(
            provider=llm_provider,
            model=_settings.LLM_MODEL,
            api_url=_settings.LLM_API_URL,
            api_key_masked=_mask_secret(_settings.LLM_API_KEY),
            status="已连接" if llm_ok else "未配置",
            has_api_key=bool(_settings.LLM_API_KEY),
        ),
        vision_model=_settings.VISION_MODEL,
        vision_status="已连接" if vision_ok else "未配置",
        llm_model=_settings.LLM_MODEL,
        llm_status="已连接" if llm_ok else "未配置",
    )


def _write_runtime_agent_env(_settings, include_vision_key: bool, include_llm_key: bool) -> None:
    env_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), ".env")
    updates = {
        "VISION_PROVIDER": _settings.VISION_PROVIDER,
        "VISION_API_URL": _settings.VISION_API_URL,
        "VISION_MODEL": _settings.VISION_MODEL,
        "LLM_PROVIDER": _settings.LLM_PROVIDER,
        "LLM_API_URL": _settings.LLM_API_URL,
        "LLM_MODEL": _settings.LLM_MODEL,
    }
    if include_vision_key:
        updates["VISION_API_KEY"] = _settings.VISION_API_KEY
    if include_llm_key:
        updates["LLM_API_KEY"] = _settings.LLM_API_KEY

    lines: list[str] = []
    if os.path.exists(env_path):
        with open(env_path, "r", encoding="utf-8") as f:
            lines = f.read().splitlines()

    seen: set[str] = set()
    new_lines: list[str] = []
    for line in lines:
        if not line or line.lstrip().startswith("#") or "=" not in line:
            new_lines.append(line)
            continue
        key = line.split("=", 1)[0].strip()
        if key in updates:
            new_lines.append(f"{key}={updates[key]}")
            seen.add(key)
        else:
            new_lines.append(line)
    for key, value in updates.items():
        if key not in seen:
            new_lines.append(f"{key}={value}")
    with open(env_path, "w", encoding="utf-8") as f:
        f.write("\n".join(new_lines) + "\n")


# ---- 系统日志 ----

@router.get("/logs", response_model=list[LogEntryResponse])
def list_logs(
    source: Optional[str] = None,
    event_type: Optional[str] = None,
    status: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
    db: Session = Depends(get_db),
    admin: Admin = Depends(get_current_admin),
):
    try:
        return get_unified_logs(db, source=source, event_type=event_type,
                                status=status, limit=limit, offset=offset)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"查询系统日志失败: {str(e)}")


# ---- Trace ----

@router.get("/traces", response_model=list[TraceSummaryResponse])
def list_traces(
    agent_type: Optional[str] = None,
    device_id: Optional[str] = None,
    limit: int = 20,
    offset: int = 0,
    db: Session = Depends(get_db),
    admin: Admin = Depends(get_current_admin),
):
    try:
        rows = get_trace_list(db, agent_type=agent_type, device_id=device_id, limit=limit, offset=offset)
        return [
            TraceSummaryResponse(
                trace_id=str(r.trace_id),
                agent_type=r.agent_type,
                device_id=r.device_id,
                step_count=r.step_count,
                total_duration_ms=r.total_duration_ms,
                created_at=r.created_at,
            )
            for r in rows
        ]
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"查询追踪列表失败: {str(e)}")


@router.get("/traces/{trace_id}", response_model=TraceDetailResponse)
def get_trace_detail_api(trace_id: uuid.UUID, db: Session = Depends(get_db),
                         admin: Admin = Depends(get_current_admin)):
    try:
        result = get_trace_detail(db, trace_id)
        if not result:
            raise HTTPException(status_code=404, detail="追踪记录不存在")
        return TraceDetailResponse(
            trace_id=result["trace_id"],
            agent_type=result["agent_type"],
            device_id=result["device_id"],
            steps=result["steps"],
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"查询追踪详情失败: {str(e)}")


@router.get("/traces/{trace_id}/explain")
def explain_trace_api(trace_id: uuid.UUID, db: Session = Depends(get_db),
                      admin: Admin = Depends(get_current_admin)):
    """让 AI 把这条 trace 翻译成一段自然语言解释。"""
    from services.llm import explain_trace
    result = get_trace_detail(db, trace_id)
    if not result:
        raise HTTPException(status_code=404, detail="追踪记录不存在")
    # steps 里 ORM 对象转 dict
    steps_data = []
    for s in result["steps"]:
        steps_data.append({
            "tool_name": s.tool_name,
            "tool_input": s.tool_input,
            "tool_output": s.tool_output,
            "status": s.status,
            "duration_ms": s.duration_ms,
        })
    explanation = explain_trace(
        steps_data,
        agent_type=result.get("agent_type"),
        device_id=result.get("device_id"),
    )
    return {
        "trace_id": str(result["trace_id"]),
        "agent_type": result.get("agent_type"),
        "device_id": result.get("device_id"),
        "step_count": len(steps_data),
        "explanation": explanation,
    }


# ---- 类别临期阈值 ----

@router.get("/category-thresholds", response_model=list[CategoryThresholdResponse])
def list_thresholds(db: Session = Depends(get_db), admin: Admin = Depends(get_current_admin)):
    try:
        return get_all_thresholds(db)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"查询阈值失败: {str(e)}")


@router.put("/category-thresholds/{threshold_id}", response_model=CategoryThresholdResponse)
def update_threshold_api(threshold_id: uuid.UUID, req: CategoryThresholdUpdateRequest,
                        db: Session = Depends(get_db), admin: Admin = Depends(get_current_admin)):
    try:
        # 取旧值用于审计
        from models import CategoryThreshold
        old = db.query(CategoryThreshold).filter(CategoryThreshold.id == threshold_id).first()
        if not old:
            raise HTTPException(status_code=404, detail="阈值记录不存在")
        old_days = old.days_before_expiry
        old_price = float(old.unit_price) if old.unit_price is not None else None

        threshold = update_threshold(
            db, threshold_id,
            days_before_expiry=req.days_before_expiry,
            unit_price=req.unit_price,
        )
        if not threshold:
            raise HTTPException(status_code=404, detail="阈值记录不存在")

        # 写一条审计
        try:
            save_log(db, "admin", "CATEGORY_CONFIG_UPDATE", "SUCCESS", {
                "category": threshold.category,
                "old_days": old_days,
                "new_days": threshold.days_before_expiry,
                "old_unit_price": old_price,
                "new_unit_price": float(threshold.unit_price) if threshold.unit_price is not None else None,
                "admin_id": str(admin.id),
                "admin_username": admin.username,
            })
            db.commit()
        except Exception:
            db.rollback()

        return threshold
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"更新阈值失败: {str(e)}")


# ---- 管理员自身改密 ----

@router.post("/auth/change-password")
def admin_change_password(req: ChangeOwnPasswordRequest, db: Session = Depends(get_db),
                          admin: Admin = Depends(get_current_admin)):
    if not verify_password(req.old_password, admin.password_hash):
        raise HTTPException(status_code=400, detail="原密码不正确")
    update_admin_password(db, admin.id, hash_password(req.new_password))
    return {"detail": "密码修改成功"}


# ---- 普通用户管理（管理员视角）----

@router.get("/users", response_model=list[AdminUserListItem])
def list_users(search: Optional[str] = None, db: Session = Depends(get_db),
               admin: Admin = Depends(get_current_admin)):
    rows = list_users_with_stats(db, search=search)
    return [AdminUserListItem(**r) for r in rows]


@router.post("/users", response_model=AdminUserListItem)
def admin_create_user(req: AdminCreateUserRequest, db: Session = Depends(get_db),
                      admin: Admin = Depends(get_current_admin)):
    if get_admin_by_username(db, req.username):
        raise HTTPException(status_code=400, detail="用户名已被管理员占用")
    if get_user_by_username(db, req.username):
        raise HTTPException(status_code=400, detail="用户名已存在")
    user = create_user(db, req.username, hash_password(req.password))
    return AdminUserListItem(
        id=str(user.id), username=user.username, created_at=user.created_at,
        inventory_count=0, preference_count=0, conversation_count=0,
    )


@router.put("/users/{user_id}/password")
def admin_reset_user_password(user_id: uuid.UUID, req: AdminResetPasswordRequest,
                              db: Session = Depends(get_db),
                              admin: Admin = Depends(get_current_admin)):
    user = update_user_password(db, user_id, hash_password(req.new_password))
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")
    return {"detail": "密码已重置"}


@router.delete("/users/{user_id}")
def admin_delete_user(user_id: uuid.UUID, db: Session = Depends(get_db),
                      admin: Admin = Depends(get_current_admin)):
    user = get_user_by_id(db, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")
    delete_user(db, user_id)
    return {"detail": "用户已删除"}


# ---- 整柜批量入库（识别后一次性写入）----

@router.post("/inventory/bulk", response_model=BulkInventoryResponse)
def bulk_create_inventory(req: BulkInventoryRequest, db: Session = Depends(get_db),
                          admin: Admin = Depends(get_current_admin)):
    """批量入库：识别已确定 category/bbox。
    每项独立做去重（hash + 向量），命中重复的跳过，结果里报告 skipped。"""
    from services.background import compute_freshness_task
    from services.dedup import check_duplicate

    created_ids: list[str] = []
    skipped: list[dict] = []
    try:
        for it in req.items:
            image_hash, feature_vector, dup = check_duplicate(
                db, it.snapshot_path, category=it.category,
            )
            if dup:
                skipped.append({
                    "category": it.category,
                    "reason": dup["reason"],
                    "matched_id": dup["matched_id"],
                    "similarity": dup.get("similarity"),
                })
                continue

            metadata = {"confidence": it.confidence}
            item = Inventory(
                device_id=req.device_id,
                category=it.category,
                status="IN_STOCK",
                remain_ratio=1.0,
                bbox=it.bbox,
                agent_metadata=metadata,
                snapshot_path=it.snapshot_path,
                feature_vector=feature_vector,
                image_hash=image_hash,
            )
            db.add(item)
            db.flush()
            created_ids.append(str(item.id))
        db.commit()

        # 后台异步算每个的保鲜期 + WS 广播
        from services.ws_events import broadcast_inventory_created
        for cid in created_ids:
            try:
                inv = db.query(Inventory).filter(Inventory.id == cid).first()
                if inv:
                    compute_freshness_task(inv.id, inv.category)
                    try:
                        broadcast_inventory_created(inv, source="bulk")
                    except Exception:
                        pass
            except Exception:
                pass

        return BulkInventoryResponse(
            created_count=len(created_ids),
            inventory_ids=created_ids,
            skipped_count=len(skipped),
            skipped=skipped,
        )
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"批量入库失败: {str(e)}")


# ---- 整柜批量识别（仅管理员）----

@router.post("/agent/detect", response_model=DetectResponse)
def admin_detect(req: RecognizeRequest, admin: Admin = Depends(get_current_admin)):
    """整柜批量识别：返回图片中所有食材的 category / confidence / bbox(相对坐标)。"""
    try:
        from services.vision import detect_foods
        items = detect_foods(req.image)
        return DetectResponse(items=items)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"批量识别失败: {str(e)}")


# ---- 标签缓冲（pending_labels）----

@router.post("/events/label_scan", response_model=LabelScanResponse)
def receive_label_scan(req: LabelScanRequest, db: Session = Depends(get_db),
                       admin: Admin = Depends(get_current_admin)):
    """端侧扫描到食品标签后调用：服务端做 OCR + 结构化解析，写入 pending_labels 缓冲。

    后续端侧上报 ITEM_IN 时，handle_item_in 会自动找该 device 最近一条未消费的
    pending_label 关联到 inventory。
    """
    from services.label_parser import parse_label, save_label_image

    # 标签扫描也算设备活跃
    try:
        upsert_device_seen(db, req.device_id, event="label_scan")
    except Exception:
        pass

    # 1) 保存标签图
    label_path = save_label_image(req.label_image, req.device_id)

    # 2) 调云端 vision 一次完成 OCR + 结构化
    parsed = parse_label(req.label_image)
    label_text = parsed.pop("label_text", "")
    label_data = parsed  # brand / product_name / expire_date / ...

    # 3) 写入缓冲表
    pending = create_pending_label(
        db,
        device_id=req.device_id,
        label_image_path=label_path,
        label_text=label_text,
        label_data=label_data,
        ttl_seconds=req.ttl_seconds,
    )

    # 4) 顺手懒清理 24h 以前的过期记录
    try:
        cleanup_expired_pending_labels(db, older_than_hours=24)
    except Exception:
        pass

    return LabelScanResponse(
        pending_label_id=str(pending.id),
        label_text=label_text or "",
        label_data=label_data,
        expires_at=pending.expires_at,
    )


@router.get("/pending-labels", response_model=list[PendingLabelItem])
def list_pending_labels_api(
    device_id: Optional[str] = None,
    status: Optional[str] = None,  # pending / consumed / expired
    limit: int = 50,
    db: Session = Depends(get_db),
    admin: Admin = Depends(get_current_admin),
):
    from datetime import datetime
    rows = list_pending_labels(db, device_id=device_id, status=status, limit=limit)
    now = datetime.now()
    result = []
    for r in rows:
        if r.consumed_at:
            st = "consumed"
        elif r.expires_at and r.expires_at <= now:
            st = "expired"
        else:
            st = "pending"
        result.append(PendingLabelItem(
            id=str(r.id),
            device_id=r.device_id,
            label_image_path=r.label_image_path,
            label_text=r.label_text,
            label_data=r.label_data,
            created_at=r.created_at,
            expires_at=r.expires_at,
            consumed_at=r.consumed_at,
            consumed_by_inventory_id=str(r.consumed_by_inventory_id) if r.consumed_by_inventory_id else None,
            status=st,
        ))
    return result


@router.delete("/pending-labels/{pending_id}")
def delete_pending_label_api(pending_id: uuid.UUID, db: Session = Depends(get_db),
                              admin: Admin = Depends(get_current_admin)):
    from models import PendingLabel
    row = db.query(PendingLabel).filter(PendingLabel.id == pending_id).first()
    if not row:
        raise HTTPException(status_code=404, detail="缓冲记录不存在")
    db.delete(row)
    db.commit()
    return {"detail": "已删除"}


# ---- LLM Token 用量统计 ----

@router.get("/usage/summary")
def usage_summary(days: int = 30, db: Session = Depends(get_db),
                  admin: Admin = Depends(get_current_admin)):
    """近 N 天的用量汇总（含按 provider/endpoint 分组、每日趋势）。"""
    try:
        return get_usage_summary(db, days=days)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"查询用量统计失败: {str(e)}")


@router.get("/usage/records")
def usage_records(
    limit: int = 50,
    offset: int = 0,
    provider: Optional[str] = None,
    endpoint: Optional[str] = None,
    status: Optional[str] = None,
    db: Session = Depends(get_db),
    admin: Admin = Depends(get_current_admin),
):
    """每条调用明细。用于"用量明细"页或调试。"""
    try:
        rows = list_usage_records(db, limit=limit, offset=offset,
                                   provider=provider, endpoint=endpoint, status=status)
        return [
            {
                "id": r.id,
                "provider": r.provider,
                "model": r.model,
                "endpoint": r.endpoint,
                "user_id": r.user_id,
                "prompt_tokens": r.prompt_tokens,
                "completion_tokens": r.completion_tokens,
                "total_tokens": r.total_tokens,
                "cost_usd": float(r.cost_usd or 0),
                "duration_ms": r.duration_ms,
                "status": r.status,
                "created_at": r.created_at.isoformat() if r.created_at else None,
            }
            for r in rows
        ]
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"查询用量明细失败: {str(e)}")


# ---- 视觉辅助识别策略（区间触发）----

@router.get("/agent/vision-assist-config", response_model=VisionAssistConfigResponse)
def get_vision_assist_config(db: Session = Depends(get_db),
                              admin: Admin = Depends(get_current_admin)):
    """读取当前视觉辅助识别策略。无记录时自动 seed 默认值 0.30 / 0.70。"""
    from services.vision_assist import get_or_create_config, is_default
    cfg = get_or_create_config(db)
    return VisionAssistConfigResponse(
        id=str(cfg.id),
        lower=float(cfg.lower_bound),
        upper=float(cfg.upper_bound),
        updated_at=cfg.updated_at,
        updated_by_admin_id=str(cfg.updated_by_admin_id) if cfg.updated_by_admin_id else None,
        is_default=is_default(cfg),
    )


@router.put("/agent/vision-assist-config", response_model=VisionAssistConfigResponse)
def update_vision_assist_config(req: VisionAssistConfigUpdateRequest,
                                  db: Session = Depends(get_db),
                                  admin: Admin = Depends(get_current_admin)):
    """更新视觉辅助识别策略。校验 lower < upper；变更后写一条审计日志。"""
    from services.vision_assist import update_config, get_or_create_config, is_default

    if req.lower >= req.upper:
        raise HTTPException(status_code=400, detail="lower must be strictly less than upper")

    # 取旧值用于审计
    old = get_or_create_config(db)
    old_lower, old_upper = float(old.lower_bound), float(old.upper_bound)

    try:
        cfg = update_config(db, req.lower, req.upper, admin.id)
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"更新视觉辅助配置失败: {str(e)}")

    # 审计日志（写到统一日志通道）
    try:
        save_log(db, "admin", "VISION_ASSIST_CONFIG_UPDATE", "SUCCESS", {
            "old_lower": old_lower,
            "old_upper": old_upper,
            "new_lower": float(cfg.lower_bound),
            "new_upper": float(cfg.upper_bound),
            "admin_id": str(admin.id),
            "admin_username": admin.username,
        })
        db.commit()
    except Exception:
        db.rollback()

    return VisionAssistConfigResponse(
        id=str(cfg.id),
        lower=float(cfg.lower_bound),
        upper=float(cfg.upper_bound),
        updated_at=cfg.updated_at,
        updated_by_admin_id=str(cfg.updated_by_admin_id) if cfg.updated_by_admin_id else None,
        is_default=is_default(cfg),
    )


# ---- WebSocket: 库存实时事件 ----

@router.websocket("/ws/inventory")
async def ws_admin_inventory(ws: WebSocket, token: str):
    """管理员后台实时订阅库存事件。

    前端用 ?token=<admin_token> 建立连接，服务端按消息类型推：
      {"type": "inventory.created", "source": "agent|manual|bulk", "data": {...}}
      {"type": "inventory.updated", "source": "...", "prev_status": "...", "data": {...}}
      {"type": "inventory.deleted", "source": "...", "id": "..."}
    """
    from services.ws_manager import manager

    payload = decode_admin_token(token)
    if not payload:
        await ws.close(code=4401)
        return
    # 用 admin: 前缀避免和普通用户 user_id 冲突
    conn_key = f"admin:{payload['sub']}"
    await manager.connect(conn_key, ws)
    try:
        await ws.send_json({"type": "ready", "scope": "admin", "admin_id": payload["sub"]})
        while True:
            msg = await ws.receive_text()
            if msg == "ping":
                await ws.send_text("pong")
    except WebSocketDisconnect:
        pass
    except Exception as e:
        import logging as _logging
        _logging.getLogger(__name__).warning(f"[WS] admin connection error | admin={conn_key} | error={e}")
    finally:
        await manager.disconnect(conn_key, ws)


# ---- 浪费分析与购物建议 ----

@router.get("/stats/waste")
def stats_waste(days: int = 30, db: Session = Depends(get_db),
                 admin: Admin = Depends(get_current_admin)):
    """近 N 天的浪费/消耗分析 + 补货建议。"""
    try:
        return get_waste_analytics(db, days=days)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"查询浪费分析失败: {str(e)}")


# ---- 设备心跳 + 设备管理 ----

@router.post("/events/heartbeat", response_model=HeartbeatResponse)
def receive_heartbeat(req: HeartbeatRequest, db: Session = Depends(get_db),
                       admin: Admin = Depends(get_current_admin)):
    """端侧设备每 30s 调一次。第一次会自动注册到 devices 表。"""
    existed = bool(get_device(db, req.device_id))
    dev = upsert_device_seen(db, req.device_id, event=req.event or "heartbeat",
                              payload=req.payload)
    if dev is None:
        raise HTTPException(status_code=400, detail="device_id 不能为空")
    return HeartbeatResponse(
        device_id=dev.device_id,
        name=dev.name or dev.device_id,
        status=dev.status or "online",
        last_seen_at=dev.last_seen_at.isoformat() if dev.last_seen_at else None,
        auto_registered=not existed,
    )


@router.get("/devices", response_model=list[DeviceItem])
def list_devices_api(db: Session = Depends(get_db),
                      admin: Admin = Depends(get_current_admin)):
    return [DeviceItem(**d) for d in list_devices(db)]


@router.put("/devices/{device_id}", response_model=DeviceItem)
def update_device_api(device_id: str, req: DeviceUpdateRequest,
                       db: Session = Depends(get_db),
                       admin: Admin = Depends(get_current_admin)):
    dev = update_device_meta(db, device_id, name=req.name,
                              location=req.location, description=req.description)
    if not dev:
        raise HTTPException(status_code=404, detail="设备不存在")
    # 复用 list_devices 的字段映射
    rows = [d for d in list_devices(db) if d["device_id"] == device_id]
    return DeviceItem(**rows[0]) if rows else DeviceItem(
        id=str(dev.id), device_id=dev.device_id, name=dev.name or dev.device_id,
        status=dev.status or "online", live_status="online",
        heartbeat_count=dev.heartbeat_count or 0,
    )


@router.delete("/devices/{device_id}")
def delete_device_api(device_id: str, db: Session = Depends(get_db),
                       admin: Admin = Depends(get_current_admin)):
    if not delete_device(db, device_id):
        raise HTTPException(status_code=404, detail="设备不存在")
    return {"detail": "已删除"}


@router.post("/devices/restore", response_model=DeviceItem)
def restore_device_api(req: dict, db: Session = Depends(get_db),
                        admin: Admin = Depends(get_current_admin)):
    """撤销删除：用原 device_id / name / location 重新创建一个设备记录。"""
    device_id = req.get("device_id")
    if not device_id:
        raise HTTPException(status_code=400, detail="device_id 必填")
    restore_device(
        db,
        device_id=device_id,
        name=req.get("name"),
        location=req.get("location"),
        description=req.get("description"),
    )
    rows = [d for d in list_devices(db) if d["device_id"] == device_id]
    if not rows:
        raise HTTPException(status_code=500, detail="恢复失败")
    return DeviceItem(**rows[0])


@router.get("/devices/{device_id}/heartbeats")
def device_heartbeats_api(device_id: str, hours: int = 24, bucket: int = 30,
                           db: Session = Depends(get_db),
                           admin: Admin = Depends(get_current_admin)):
    """返回该设备近 N 小时的心跳频率（按 bucket 分钟桶聚合）。"""
    dev = get_device(db, device_id)
    if not dev:
        raise HTTPException(status_code=404, detail="设备不存在")
    return {
        "device_id": device_id,
        "hours": hours,
        "bucket_minutes": bucket,
        "series": get_device_heartbeat_series(db, device_id, hours=hours, bucket_minutes=bucket),
    }


# ---- 工具链性能监控 ----

@router.get("/stats/perf")
def stats_perf(hours: int = 24, db: Session = Depends(get_db),
                admin: Admin = Depends(get_current_admin)):
    """近 N 小时各 tool 的 P50 / P95 / 成功率聚合统计。"""
    try:
        return get_tool_perf_stats(db, hours=hours)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"查询性能统计失败: {str(e)}")


# ---- 库存最近一条 trace（用于"AI 是怎么决定的"展示）----

@router.get("/inventory/{inventory_id}/last-trace")
def inventory_last_trace(inventory_id: uuid.UUID, db: Session = Depends(get_db),
                          admin: Admin = Depends(get_current_admin)):
    """根据 inventory.id 找到这条记录入库时关联的 trace（按 device_id + 时间窗口启发式匹配）。
    返回完整 steps 用于"AI 决策路径"展示。
    """
    inv = get_inventory_by_id(db, inventory_id)
    if not inv:
        raise HTTPException(status_code=404, detail="库存不存在")
    try:
        from datetime import timedelta
        from models import AgentTrace
        if not inv.created_at:
            return {"trace_id": None, "steps": []}
        # 在 inventory.created_at 之前 60 秒内的同 device_id 的 ITEM_IN trace
        window_start = inv.created_at - timedelta(seconds=60)
        candidate = (
            db.query(AgentTrace)
            .filter(
                AgentTrace.device_id == inv.device_id,
                AgentTrace.agent_type == "ITEM_IN",
                AgentTrace.created_at >= window_start,
                AgentTrace.created_at <= inv.created_at + timedelta(seconds=5),
            )
            .order_by(AgentTrace.created_at.desc())
            .first()
        )
        if not candidate:
            return {"trace_id": None, "steps": []}
        result = get_trace_detail(db, candidate.trace_id)
        if not result:
            return {"trace_id": None, "steps": []}
        return {
            "trace_id": str(result["trace_id"]),
            "agent_type": result["agent_type"],
            "device_id": result["device_id"],
            "steps": result["steps"],
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"查询 trace 失败: {str(e)}")


# ---- 数据导出（CSV）----

from fastapi.responses import StreamingResponse  # noqa: E402

@router.get("/export/inventory")
def export_inventory(
    device_id: Optional[str] = None,
    status: Optional[str] = None,
    category: Optional[str] = None,
    db: Session = Depends(get_db),
    admin: Admin = Depends(get_current_admin),
):
    """导出当前库存清单为 CSV（带 UTF-8 BOM，可直接 Excel 打开）。"""
    from services.export_csv import to_csv_bytes, filename_with_ts
    rows_db = get_inventory_list(db, device_id=device_id, status=status, category=category)
    headers = [
        "id", "device_id", "category", "status", "remain_ratio",
        "expire_at", "expire_source", "brand", "created_at",
    ]
    out = []
    for r in rows_db:
        md = r.agent_metadata or {}
        ld = r.label_data or {}
        out.append([
            str(r.id), r.device_id, r.category, r.status, r.remain_ratio,
            md.get("expire_at"), md.get("expire_source"),
            ld.get("brand") if isinstance(ld, dict) else None,
            r.created_at,
        ])
    body = to_csv_bytes(headers, out)
    fname = filename_with_ts("inventory")
    return StreamingResponse(
        iter([body]),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f"attachment; filename={fname}",
                 "Access-Control-Expose-Headers": "Content-Disposition"},
    )


@router.get("/export/events")
def export_events(db: Session = Depends(get_db),
                   admin: Admin = Depends(get_current_admin)):
    """导出事件流水为 CSV。"""
    from services.export_csv import to_csv_bytes, filename_with_ts
    rows = get_event_logs(db)
    headers = ["id", "inventory_id", "event_type", "confidence", "create_at"]
    out = [
        [r.id, str(r.inventory_id), r.event_type, r.confidence, r.create_at]
        for r in rows
    ]
    body = to_csv_bytes(headers, out)
    fname = filename_with_ts("events")
    return StreamingResponse(
        iter([body]),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f"attachment; filename={fname}",
                 "Access-Control-Expose-Headers": "Content-Disposition"},
    )


@router.get("/export/usage")
def export_usage(db: Session = Depends(get_db),
                  admin: Admin = Depends(get_current_admin)):
    """导出 LLM 用量明细为 CSV。"""
    from services.export_csv import to_csv_bytes, filename_with_ts
    rows = list_usage_records(db, limit=10000, offset=0)
    headers = [
        "id", "provider", "model", "endpoint", "user_id",
        "prompt_tokens", "completion_tokens", "total_tokens",
        "cost_usd", "duration_ms", "status", "created_at",
    ]
    out = [
        [r.id, r.provider, r.model, r.endpoint, r.user_id,
         r.prompt_tokens, r.completion_tokens, r.total_tokens,
         float(r.cost_usd or 0), r.duration_ms, r.status, r.created_at]
        for r in rows
    ]
    body = to_csv_bytes(headers, out)
    fname = filename_with_ts("usage")
    return StreamingResponse(
        iter([body]),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f"attachment; filename={fname}",
                 "Access-Control-Expose-Headers": "Content-Disposition"},
    )


# ---- 健康饮食评分 ----

@router.get("/stats/nutrition")
def stats_nutrition(days: int = 30, db: Session = Depends(get_db),
                     admin: Admin = Depends(get_current_admin)):
    """近 N 天饮食营养结构 + 健康评分。"""
    try:
        return get_nutrition_report(db, days=days)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"查询营养报告失败: {str(e)}")


@router.get("/stats/lifecycle")
def stats_lifecycle(days: int = 30, top_n: int = 8,
                     db: Session = Depends(get_db),
                     admin: Admin = Depends(get_current_admin)):
    """食材生命周期 Sankey 数据：来源 → 品类 → 终态。"""
    try:
        return get_lifecycle_sankey(db, days=days, top_n=top_n)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"查询生命周期失败: {str(e)}")


@router.get("/stats/waste-calendar")
def stats_waste_calendar(days: int = 365, db: Session = Depends(get_db),
                          admin: Admin = Depends(get_current_admin)):
    """浪费金额日历热图：近 N 天每天浪费的金额（按品类单价估算）。"""
    try:
        return get_waste_calendar(db, days=days)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"查询浪费日历失败: {str(e)}")
