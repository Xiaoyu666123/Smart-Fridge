import uuid
import os
import time

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlalchemy.orm import Session
from typing import Optional
from database import get_db
from schemas import (
    ItemEventRequest, InventoryResponse, InventoryCreateRequest, InventoryUpdateRequest,
    EventLogResponse,
    ChatRequest, ChatResponse, RecognizeRequest, RecognizeResponse,
    PreferenceResponse, PreferenceAddRequest, TraceSummaryResponse, TraceDetailResponse,
    EnvironmentResponse, LogEntryResponse,
    RegisterRequest, LoginRequest, TokenResponse, UserResponse,
)
from crud import handle_item_event, get_inventory_list, get_inventory_by_id, get_event_logs, get_preferences_list, add_preference, delete_preference, get_trace_list, get_trace_detail, get_unified_logs, get_conversations, create_user, get_user_by_username
from models import Inventory, EventLog, User
from agents import FridgeAgent
from services.auth import hash_password, verify_password, create_token, get_current_user, require_admin

router = APIRouter()


# ---- Auth 路由 ----

@router.post("/auth/register", response_model=TokenResponse)
def register(req: RegisterRequest, db: Session = Depends(get_db)):
    existing = get_user_by_username(db, req.username)
    if existing:
        raise HTTPException(status_code=400, detail="用户名已存在")
    user = create_user(db, req.username, hash_password(req.password))
    token = create_token(str(user.id), user.role)
    return TokenResponse(token=token, user_id=str(user.id), username=user.username, role=user.role)


@router.post("/auth/login", response_model=TokenResponse)
def login(req: LoginRequest, db: Session = Depends(get_db)):
    user = get_user_by_username(db, req.username)
    if not user or not verify_password(req.password, user.password_hash):
        raise HTTPException(status_code=401, detail="用户名或密码错误")
    token = create_token(str(user.id), user.role)
    return TokenResponse(token=token, user_id=str(user.id), username=user.username, role=user.role)


@router.get("/auth/me", response_model=UserResponse)
def get_me(user: User = Depends(get_current_user)):
    return UserResponse(id=str(user.id), username=user.username, role=user.role, created_at=user.created_at)


@router.post("/events/item", response_model=list[InventoryResponse])
def receive_item_event(event: ItemEventRequest, db: Session = Depends(get_db),
                       user: User = Depends(get_current_user)):
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
    category: Optional[str] = None,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    try:
        items = get_inventory_list(db, device_id=device_id, status=status, category=category)
        return items
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"查询库存失败: {str(e)}")


@router.get("/inventory/categories")
def list_categories(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    try:
        from sqlalchemy import distinct
        rows = db.query(distinct(Inventory.category)).order_by(Inventory.category).all()
        return [r[0] for r in rows if r[0]]
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"查询分类列表失败: {str(e)}")


@router.get("/inventory/{inventory_id}", response_model=InventoryResponse)
def get_inventory_detail(inventory_id: uuid.UUID, db: Session = Depends(get_db),
                         user: User = Depends(get_current_user)):
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
def upload_inventory_image(file: UploadFile = File(...), user: User = Depends(require_admin)):
    allowed_types = {"image/jpeg", "image/png", "image/gif", "image/webp"}
    if file.content_type not in allowed_types:
        raise HTTPException(status_code=400, detail="仅支持 JPG/PNG/GIF/WEBP 格式图片")
    os.makedirs(UPLOAD_DIR, exist_ok=True)
    ext = os.path.splitext(file.filename or "image.jpg")[1] or ".jpg"
    filename = f"inv_{int(time.time())}_{uuid.uuid4().hex[:8]}{ext}"
    filepath = os.path.join(UPLOAD_DIR, filename)
    with open(filepath, "wb") as f:
        f.write(file.file.read())
    return {"snapshot_path": filepath, "url": f"/uploads/{filename}"}


UPLOAD_DIR = "uploads"


@router.post("/inventory", response_model=InventoryResponse)
def create_inventory(req: InventoryCreateRequest, db: Session = Depends(get_db),
                     user: User = Depends(require_admin)):
    import logging
    from services.embedding import extract_image_vector, SIMILARITY_THRESHOLD
    from sqlalchemy import text

    logger = logging.getLogger(__name__)

    # 向量去重：如果有图片，提取向量并和同类别已有库存比对
    feature_vector = None
    if req.snapshot_path:
        logger.info(f"[Dedup] 开始向量去重 | snapshot_path={req.snapshot_path}")
        feature_vector = extract_image_vector(req.snapshot_path)
        logger.info(f"[Dedup] 向量提取结果 | feature_vector={'有(' + str(len(feature_vector)) + '维)' if feature_vector else 'None'}")
        if feature_vector:
            vec_str = "[" + ",".join(str(v) for v in feature_vector) + "]"

            # 先检查同类别有多少条有向量的记录
            count_row = db.execute(
                text("SELECT count(*) FROM inventory WHERE category = :category AND feature_vector IS NOT NULL"),
                {"category": req.category},
            ).fetchone()
            total_with_vec = count_row[0]
            logger.info(f"[Dedup] 同类别有向量记录数 | category={req.category} | count={total_with_vec}")

            # 强制顺序扫描，避免 HNSW 近似索引漏掉记录
            db.execute(text("SET enable_indexscan = off"))

            # 诊断：列出所有同类别记录的相似度
            all_rows = db.execute(
                text("""
                    SELECT id, 1 - (CAST(:vec AS vector) <=> feature_vector) AS similarity
                    FROM inventory
                    WHERE category = :category
                      AND feature_vector IS NOT NULL
                    ORDER BY similarity DESC
                """),
                {"vec": vec_str, "category": req.category},
            ).fetchall()
            for r in all_rows:
                logger.info(f"[Dedup] 候选记录 | id={r[0]} | similarity={r[1]:.6f}")

            # 恢复索引扫描
            db.execute(text("SET enable_indexscan = on"))

            if all_rows and all_rows[0][1] >= SIMILARITY_THRESHOLD:
                best_sim = all_rows[0][1]
                best_id = all_rows[0][0]
                logger.info(f"[Dedup] 判定为同一物品 | matched_id={best_id} | similarity={best_sim:.4f} | threshold={SIMILARITY_THRESHOLD}")
                raise HTTPException(status_code=409, detail=f"该物品与已有库存相似度 {best_sim:.2f}，判定为同一物品，无需重复入库")
            else:
                best_sim = all_rows[0][1] if all_rows else 0.0
                logger.info(f"[Dedup] 非同一物品，继续入库 | best_similarity={best_sim:.4f} | threshold={SIMILARITY_THRESHOLD}")
        else:
            logger.warning(f"[Dedup] 向量提取失败，跳过去重 | snapshot_path={req.snapshot_path}")
    else:
        logger.info("[Dedup] 无图片，跳过去重")

    try:
        metadata = dict(req.agent_metadata) if req.agent_metadata else {}

        item = Inventory(
            device_id=req.device_id,
            category=req.category,
            status=req.status,
            remain_ratio=req.remain_ratio,
            bbox=req.bbox,
            agent_metadata=metadata,
            snapshot_path=req.snapshot_path,
            feature_vector=feature_vector,
        )
        db.add(item)
        db.commit()
        db.refresh(item)
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"添加库存失败: {str(e)}")

    # 后台异步计算保鲜期
    from services.background import compute_freshness_task
    compute_freshness_task(item.id, item.category)

    return item


@router.put("/inventory/{inventory_id}", response_model=InventoryResponse)
def update_inventory(inventory_id: uuid.UUID, req: InventoryUpdateRequest,
                     db: Session = Depends(get_db), user: User = Depends(require_admin)):
    try:
        item = get_inventory_by_id(db, inventory_id)
        if not item:
            raise HTTPException(status_code=404, detail="库存记录不存在")
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
        return item
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"更新库存失败: {str(e)}")


@router.delete("/inventory/{inventory_id}")
def delete_inventory(inventory_id: uuid.UUID, db: Session = Depends(get_db),
                     user: User = Depends(require_admin)):
    try:
        item = get_inventory_by_id(db, inventory_id)
        if not item:
            raise HTTPException(status_code=404, detail="库存记录不存在")
        db.delete(item)
        db.commit()
        return {"detail": "删除成功"}
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"删除库存失败: {str(e)}")


@router.get("/events", response_model=list[EventLogResponse])
def list_events(
    inventory_id: Optional[uuid.UUID] = None,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    try:
        logs = get_event_logs(db, inventory_id=inventory_id)
        return logs
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"查询事件日志失败: {str(e)}")


# ---- Agent 路由 ----

@router.get("/agent/conversations")
def list_conversations(limit: int = 100, offset: int = 0, db: Session = Depends(get_db),
                       user: User = Depends(get_current_user)):
    try:
        rows = get_conversations(db, str(user.id), limit=limit, offset=offset)
        return [
            {"id": r.id, "role": r.role, "content": r.content, "created_at": r.created_at.isoformat() if r.created_at else None}
            for r in reversed(rows)
        ]
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"查询对话历史失败: {str(e)}")


@router.post("/agent/chat", response_model=ChatResponse)
def agent_chat(req: ChatRequest, db: Session = Depends(get_db),
               user: User = Depends(get_current_user)):
    try:
        agent = FridgeAgent()
        result = agent.chat(db, user_id=str(user.id), message=req.message, city=req.city)
        return result
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"对话失败: {str(e)}")


@router.post("/agent/recognize", response_model=RecognizeResponse)
def agent_recognize(req: RecognizeRequest, db: Session = Depends(get_db),
                    user: User = Depends(get_current_user)):
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
def get_user_preferences(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    try:
        return get_preferences_list(db, str(user.id))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"查询偏好失败: {str(e)}")


@router.post("/agent/preferences", response_model=PreferenceResponse)
def add_user_preference(req: PreferenceAddRequest, db: Session = Depends(get_db),
                        user: User = Depends(get_current_user)):
    try:
        return add_preference(db, user_id=str(user.id), preference_key=req.preference_key, preference_value=req.preference_value)
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"添加偏好失败: {str(e)}")


@router.delete("/agent/preferences/{preference_id}")
def delete_user_preference(preference_id: uuid.UUID, db: Session = Depends(get_db),
                           user: User = Depends(get_current_user)):
    try:
        pref = delete_preference(db, preference_id)
        if not pref:
            raise HTTPException(status_code=404, detail="偏好记录不存在")
        return {"detail": "删除成功"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"删除偏好失败: {str(e)}")


@router.get("/agent/config")
def get_agent_config(user: User = Depends(require_admin)):
    from config import settings

    vision_ok = bool(settings.VISION_API_KEY and settings.VISION_API_URL)
    llm_ok = bool(settings.LLM_API_KEY and settings.LLM_API_URL)

    return {
        "vision_model": settings.VISION_MODEL,
        "vision_status": "已连接" if vision_ok else "未配置",
        "llm_model": settings.LLM_MODEL,
        "llm_status": "已连接" if llm_ok else "未配置",
    }


# ---- Environment 路由 ----

@router.get("/environment", response_model=EnvironmentResponse)
def get_environment(city: Optional[str] = None, user: User = Depends(get_current_user)):
    from config import settings
    from services.weather import get_current_weather

    target = city or settings.DEFAULT_CITY
    try:
        return get_current_weather(target)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取环境信息失败: {str(e)}")


# ---- Logs 路由 ----

@router.get("/logs", response_model=list[LogEntryResponse])
def list_logs(
    source: Optional[str] = None,
    event_type: Optional[str] = None,
    status: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
    db: Session = Depends(get_db),
    user: User = Depends(require_admin),
):
    try:
        return get_unified_logs(db, source=source, event_type=event_type,
                                status=status, limit=limit, offset=offset)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"查询系统日志失败: {str(e)}")


# ---- Trace 路由 ----

@router.get("/traces", response_model=list[TraceSummaryResponse])
def list_traces(
    agent_type: Optional[str] = None,
    device_id: Optional[str] = None,
    limit: int = 20,
    offset: int = 0,
    db: Session = Depends(get_db),
    user: User = Depends(require_admin),
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
                         user: User = Depends(require_admin)):
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
