import time
import uuid
import logging
from datetime import datetime, timedelta
from typing import Optional

from sqlalchemy.orm import Session

from models import Inventory, EventLog
from crud import save_trace
from services.vision import recognize_food
from services.llm import estimate_freshness, recommend_recipe, get_season, recommend_recipe_stream, recommend_structured_stream
from services.embedding import extract_image_vector, SIMILARITY_THRESHOLD
from services.memory import (
    extract_preferences,
    save_preferences,
    get_preferences,
    save_conversation,
    get_recent_conversations,
)
from services.weather import get_current_weather
from crud import find_active_pending_label, consume_pending_label
from config import settings
from services.upload_security import decode_base64_image, make_upload_filename, save_image_bytes, sanitize_filename_part

logger = logging.getLogger(__name__)

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


def _trace_tool(db: Session, trace_id: uuid.UUID, step_order: int, agent_type: str,
                tool_name: str, tool_input: Optional[dict], tool_output: Optional[dict],
                status: str, duration_ms: Optional[int], device_id: Optional[str] = None):
    save_trace(db, trace_id, agent_type, step_order, tool_name,
               tool_input, tool_output, status, duration_ms, device_id)


class FridgeAgent:
    def handle_item_in(self, db: Session, event, item) -> Optional[Inventory]:
        """
        事件驱动：食材入库。
        1. 保存图片
        2. 提取图片向量 + 全表去重（hash + 向量相似度）
        3. 置信度低于阈值时调 vision 辅助识别
        4. 调 LLM 推算保鲜期
        5. 写入 inventory + event_logs
        """
        from services.dedup import check_duplicate
        from services.vision_assist import decide as decide_vision_assist

        trace_id = uuid.uuid4()
        step = 0
        device_id = event.device_id

        logger.info(f"[Agent] ITEM_IN 开始 | device={device_id} | category={item.category} | confidence={item.confidence} | has_image={bool(item.crop_image)}")

        # 保存图片
        snapshot_path = _save_crop_image(event.device_id, item.local_track_id, item.crop_image)

        # 统一去重
        feature_vector = None
        image_hash = None
        if item.crop_image:
            step += 1
            t0 = time.time()
            try:
                image_hash, feature_vector, dup = check_duplicate(
                    db, item.crop_image, category=item.category,
                )
                _trace_tool(db, trace_id, step, "ITEM_IN", "vector_dedup",
                            {"category": item.category},
                            {
                                "is_duplicate": bool(dup),
                                "reason": dup["reason"] if dup else None,
                                "matched_id": dup["matched_id"] if dup else None,
                                "similarity": dup.get("similarity") if dup else None,
                            },
                            "SUCCESS", int((time.time() - t0) * 1000), device_id)
                if dup:
                    logger.info(f"[Agent] ITEM_IN 命中重复，跳过入库 | reason={dup['reason']} | matched={dup['matched_id']}")
                    return None
            except Exception as e:
                _trace_tool(db, trace_id, step, "ITEM_IN", "vector_dedup",
                            {"category": item.category},
                            {"error": str(e)}, "FAILED", int((time.time() - t0) * 1000), device_id)
                logger.error(f"[Agent] 去重异常，继续入库 | error={e}")

        # 视觉识别（基于动态区间策略 vision_assist_config 决定是否触发云端复核）
        category = item.category
        vision_confidence = item.confidence

        # 决策步骤本身写一条 trace，方便排查"为什么没/为什么有调"
        step += 1
        t0 = time.time()
        decision = decide_vision_assist(
            db,
            edge_confidence=item.confidence,
            has_crop_image=bool(item.crop_image),
        )
        _trace_tool(db, trace_id, step, "ITEM_IN", "vision_assist_decide",
                    decision.trace_input(), decision.trace_output(),
                    "SUCCESS", int((time.time() - t0) * 1000), device_id)
        logger.info(
            f"[VisionAssist] decision={decision.decision} | "
            f"edge_conf={decision.edge_confidence} | range=[{decision.lower}, {decision.upper}] | "
            f"has_image={decision.has_crop_image} | device={device_id}"
        )

        if decision.triggered:
            step += 1
            t0 = time.time()
            try:
                vision_result = recognize_food(item.crop_image)
                if vision_result["confidence"] > item.confidence and vision_result["category"] != "unknown":
                    category = vision_result["category"]
                    vision_confidence = vision_result["confidence"]
                    logger.info(f"[Vision] 辅助识别结果优于原始 | original={item.category}({item.confidence}) -> vision={vision_result['category']}({vision_result['confidence']})")
                else:
                    logger.info(f"[Vision] 原始更优或云端 unknown，保留原始 | original={item.category}({item.confidence}) -> vision={vision_result['category']}({vision_result['confidence']})")
                _trace_tool(db, trace_id, step, "ITEM_IN", "vision_recognize",
                            {"reason": "in_range", "original_confidence": item.confidence,
                             "lower": decision.lower, "upper": decision.upper},
                            {"category": vision_result["category"], "confidence": vision_result["confidence"]},
                            "SUCCESS", int((time.time() - t0) * 1000), device_id)
            except Exception as e:
                logger.error(f"[Vision] 辅助识别异常 | device={device_id} | error={e}")
                _trace_tool(db, trace_id, step, "ITEM_IN", "vision_recognize",
                            {"reason": "in_range", "original_confidence": item.confidence},
                            {"error": str(e)}, "FAILED", int((time.time() - t0) * 1000), device_id)

        # 保鲜期推算
        step += 1
        t0 = time.time()
        logger.info(f"[LLM] 保鲜期推算 | category={category} | device={device_id}")
        try:
            city = settings.DEFAULT_CITY
            season = get_season()
            freshness = estimate_freshness(category, city, season)
            _trace_tool(db, trace_id, step, "ITEM_IN", "llm_freshness",
                        {"category": category, "city": city, "season": season},
                        {"shelf_life_days": freshness["shelf_life_days"], "storage_advice": freshness["storage_advice"]},
                        "SUCCESS", int((time.time() - t0) * 1000), device_id)
            logger.info(f"[LLM] 保鲜期推算成功 | category={category} | shelf_life={freshness['shelf_life_days']}天 | duration={int((time.time() - t0) * 1000)}ms")
        except Exception as e:
            freshness = {"shelf_life_days": 7, "storage_advice": "冷藏保存"}
            _trace_tool(db, trace_id, step, "ITEM_IN", "llm_freshness",
                        {"category": category},
                        {"error": str(e)}, "FAILED", int((time.time() - t0) * 1000), device_id)
            logger.error(f"[LLM] 保鲜期推算失败 | category={category} | error={e} | 使用默认值7天")

        expire_at = datetime.now() + timedelta(days=freshness["shelf_life_days"])
        expire_source = "llm_estimate"

        # ---- 关联缓冲标签（如有）----
        # 找该设备最近一条未消费的 pending_label，挂到这条 inventory
        step += 1
        t0 = time.time()
        pending_label = None
        label_text_val = None
        label_data_val = None
        label_path_val = None
        try:
            pending_label = find_active_pending_label(db, event.device_id)
            if pending_label:
                label_text_val = pending_label.label_text
                label_data_val = pending_label.label_data
                label_path_val = pending_label.label_image_path
                # 真实保质期覆盖 LLM 估算
                if label_data_val and label_data_val.get("expire_date"):
                    try:
                        real_expire = datetime.fromisoformat(label_data_val["expire_date"])
                        expire_at = real_expire
                        expire_source = "label"
                        logger.info(f"[Agent] 标签真实保质期覆盖 LLM 估算 | expire_at={real_expire.isoformat()}")
                    except Exception as e:
                        logger.warning(f"[Agent] 标签 expire_date 解析失败 | value={label_data_val.get('expire_date')} | error={e}")
                _trace_tool(db, trace_id, step, "ITEM_IN", "label_associate",
                            {"device_id": event.device_id},
                            {
                                "pending_label_id": str(pending_label.id),
                                "brand": (label_data_val or {}).get("brand"),
                                "expire_source": expire_source,
                            },
                            "SUCCESS", int((time.time() - t0) * 1000), device_id)
            else:
                _trace_tool(db, trace_id, step, "ITEM_IN", "label_associate",
                            {"device_id": event.device_id},
                            {"pending_label_id": None},
                            "SUCCESS", int((time.time() - t0) * 1000), device_id)
        except Exception as e:
            _trace_tool(db, trace_id, step, "ITEM_IN", "label_associate",
                        {"device_id": event.device_id},
                        {"error": str(e)}, "FAILED", int((time.time() - t0) * 1000), device_id)
            logger.error(f"[Agent] 关联标签缓冲异常 | error={e}")

        # 写入 inventory
        step += 1
        t0 = time.time()
        try:
            inv = Inventory(
                device_id=event.device_id,
                category=category,
                status="IN_STOCK",
                remain_ratio=1.0,
                bbox=item.bbox,
                feature_vector=feature_vector,
                image_hash=image_hash,
                label_text=label_text_val,
                label_data=label_data_val,
                label_snapshot_path=label_path_val,
                agent_metadata={
                    "shelf_life_days": freshness["shelf_life_days"],
                    "storage_advice": freshness["storage_advice"],
                    "expire_at": expire_at.isoformat(),
                    "expire_source": expire_source,
                    "vision_confidence": vision_confidence,
                },
            )
            db.add(inv)
            db.flush()
            # 标签消费
            if pending_label:
                try:
                    consume_pending_label(db, pending_label.id, inv.id)
                except Exception as e:
                    logger.warning(f"[Agent] 标记 pending_label 消费失败 | error={e}")
            _trace_tool(db, trace_id, step, "ITEM_IN", "db_write_inventory",
                        {"category": category, "device_id": event.device_id,
                         "label_attached": bool(pending_label)},
                        {"inventory_id": str(inv.id)},
                        "SUCCESS", int((time.time() - t0) * 1000), device_id)
            logger.info(f"[Agent] 写入 inventory 成功 | id={inv.id} | category={category} | label_attached={bool(pending_label)}")
        except Exception as e:
            _trace_tool(db, trace_id, step, "ITEM_IN", "db_write_inventory",
                        {"category": category},
                        {"error": str(e)}, "FAILED", int((time.time() - t0) * 1000), device_id)
            db.rollback()
            logger.error(f"[Agent] 写入 inventory 失败 | category={category} | error={e}")
            return None

        # 写入 event_log
        step += 1
        t0 = time.time()
        try:
            log = EventLog(
                inventory_id=inv.id,
                event_type="ITEM_IN",
                confidence=item.confidence,
                snapshot_path=snapshot_path,
            )
            db.add(log)
            db.commit()
            db.refresh(inv)
            _trace_tool(db, trace_id, step, "ITEM_IN", "db_write_event_log",
                        {"inventory_id": str(inv.id)},
                        {"event_log_id": log.id},
                        "SUCCESS", int((time.time() - t0) * 1000), device_id)
            logger.info(f"[Agent] ITEM_IN 完成 | id={inv.id} | category={category} | expire_at={expire_at.isoformat()}")
        except Exception as e:
            db.rollback()
            _trace_tool(db, trace_id, step, "ITEM_IN", "db_write_event_log",
                        {"inventory_id": str(inv.id)},
                        {"error": str(e)}, "FAILED", int((time.time() - t0) * 1000), device_id)
            logger.error(f"[Agent] 写入 event_log 失败 | inventory_id={inv.id} | error={e}")
            return None

        # 广播给所有在线用户：库存新增
        try:
            from services.ws_events import broadcast_inventory_created
            broadcast_inventory_created(inv, source="agent")
        except Exception as _e:
            logger.warning(f"[WS] inventory.created broadcast failed | error={_e}")

        return inv

    def handle_item_out(self, db: Session, event, item) -> Optional[Inventory]:
        """
        事件驱动：食材取出。
        1. 保存图片
        2. 按 category 匹配入库记录
        3. 更新状态为 OUT_PENDING
        """
        trace_id = uuid.uuid4()
        step = 0
        device_id = event.device_id

        logger.info(f"[Agent] ITEM_OUT 开始 | device={device_id} | category={item.category} | confidence={item.confidence}")

        snapshot_path = _save_crop_image(event.device_id, item.local_track_id, item.crop_image)

        # 查询库存
        step += 1
        t0 = time.time()
        try:
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
            _trace_tool(db, trace_id, step, "ITEM_OUT", "db_query_inventory",
                        {"device_id": event.device_id, "category": item.category},
                        {"found": inv is not None, "inventory_id": str(inv.id) if inv else None},
                        "SUCCESS", int((time.time() - t0) * 1000), device_id)
            logger.info(f"[Agent] ITEM_OUT 查询库存 | found={inv is not None} | id={str(inv.id) if inv else None}")
        except Exception as e:
            _trace_tool(db, trace_id, step, "ITEM_OUT", "db_query_inventory",
                        {"device_id": event.device_id, "category": item.category},
                        {"error": str(e)}, "FAILED", int((time.time() - t0) * 1000), device_id)
            logger.error(f"[Agent] ITEM_OUT 查询库存失败 | error={e}")
            return None

        if inv:
            # 写入 event_log
            step += 1
            t0 = time.time()
            try:
                inv.status = "OUT_PENDING"
                log = EventLog(
                    inventory_id=inv.id,
                    event_type="ITEM_OUT",
                    confidence=item.confidence,
                    snapshot_path=snapshot_path,
                )
                db.add(log)
                db.commit()
                db.refresh(inv)
                _trace_tool(db, trace_id, step, "ITEM_OUT", "db_write_event_log",
                            {"inventory_id": str(inv.id)},
                            {"event_log_id": log.id},
                            "SUCCESS", int((time.time() - t0) * 1000), device_id)
                logger.info(f"[Agent] ITEM_OUT 完成 | id={inv.id} | category={item.category} | status=OUT_PENDING")
                # 广播：状态变化（IN_STOCK -> OUT_PENDING）
                try:
                    from services.ws_events import broadcast_inventory_updated
                    broadcast_inventory_updated(inv, source="agent", prev_status="IN_STOCK")
                except Exception as _e:
                    logger.warning(f"[WS] inventory.updated broadcast failed | error={_e}")
            except Exception as e:
                db.rollback()
                _trace_tool(db, trace_id, step, "ITEM_OUT", "db_write_event_log",
                            {"inventory_id": str(inv.id)},
                            {"error": str(e)}, "FAILED", int((time.time() - t0) * 1000), device_id)
                logger.error(f"[Agent] ITEM_OUT 写入事件日志失败 | error={e}")
                return None
        else:
            logger.warning(f"[Agent] ITEM_OUT 未找到匹配库存 | device={device_id} | category={item.category}")

        return inv

    def chat(self, db: Session, user_id: str, message: str, city: Optional[str] = None) -> dict:
        """
        用户请求驱动：对话式食谱推荐。
        1. 提取并保存偏好
        2. 查库存 + 保鲜期
        3. 查偏好 + 对话历史
        4. 获取天气
        5. 组装 prompt → 调 LLM
        6. 保存对话记录
        """
        trace_id = uuid.uuid4()
        step = 0
        city = city or settings.DEFAULT_CITY
        season = get_season()

        logger.info(f"[Agent] CHAT 开始 | user={user_id} | city={city} | season={season} | message={message[:50]}")

        # 提取偏好
        step += 1
        t0 = time.time()
        try:
            new_prefs = extract_preferences(message)
            _trace_tool(db, trace_id, step, "CHAT", "preference_extract",
                        {"message": message[:100]},
                        {"preferences_count": len(new_prefs), "preferences": new_prefs},
                        "SUCCESS", int((time.time() - t0) * 1000))
        except Exception as e:
            new_prefs = []
            _trace_tool(db, trace_id, step, "CHAT", "preference_extract",
                        {"message": message[:100]},
                        {"error": str(e)}, "FAILED", int((time.time() - t0) * 1000))
            logger.error(f"[LLM] 偏好提取异常 | error={e}")

        # 保存偏好
        if new_prefs:
            step += 1
            t0 = time.time()
            try:
                save_preferences(db, user_id, new_prefs)
                _trace_tool(db, trace_id, step, "CHAT", "db_save_preferences",
                            {"user_id": user_id, "count": len(new_prefs)},
                            {"saved": True},
                            "SUCCESS", int((time.time() - t0) * 1000))
            except Exception as e:
                _trace_tool(db, trace_id, step, "CHAT", "db_save_preferences",
                            {"user_id": user_id},
                            {"error": str(e)}, "FAILED", int((time.time() - t0) * 1000))
                logger.error(f"[Agent] 保存偏好失败 | error={e}")

        # 保存用户消息
        save_conversation(db, user_id, "user", message)

        # 查库存
        step += 1
        t0 = time.time()
        try:
            items = db.query(Inventory).filter(Inventory.status == "IN_STOCK").all()
            inventory_list = []
            for item in items:
                metadata = item.agent_metadata or {}
                shelf_life = metadata.get("shelf_life_days", 7)
                expire_at_str = metadata.get("expire_at")
                if expire_at_str:
                    expire_at = datetime.fromisoformat(expire_at_str)
                    remain_days = max(0, (expire_at - datetime.now()).days)
                else:
                    remain_days = shelf_life
                inventory_list.append({"category": item.category, "remain_days": remain_days})
            _trace_tool(db, trace_id, step, "CHAT", "db_query_inventory",
                        {"user_id": user_id},
                        {"item_count": len(inventory_list)},
                        "SUCCESS", int((time.time() - t0) * 1000))
        except Exception as e:
            inventory_list = []
            _trace_tool(db, trace_id, step, "CHAT", "db_query_inventory",
                        {"user_id": user_id},
                        {"error": str(e)}, "FAILED", int((time.time() - t0) * 1000))
            logger.error(f"[Agent] 查询库存失败 | error={e}")

        # 查偏好 + 对话历史
        preferences = get_preferences(db, user_id)
        recent_convs = get_recent_conversations(db, user_id, limit=10)

        # 获取实时天气
        step += 1
        t0 = time.time()
        try:
            weather_info = get_current_weather(city)
            _trace_tool(db, trace_id, step, "CHAT", "weather_query",
                        {"city": city},
                        {"temperature": weather_info.get("temperature"),
                         "weather_desc": weather_info.get("weather_desc")},
                        "SUCCESS", int((time.time() - t0) * 1000))
        except Exception as e:
            weather_info = None
            _trace_tool(db, trace_id, step, "CHAT", "weather_query",
                        {"city": city},
                        {"error": str(e)}, "FAILED", int((time.time() - t0) * 1000))

        # 调 LLM 推荐
        step += 1
        t0 = time.time()
        logger.info(f"[LLM] 食谱推荐 | inventory_count={len(inventory_list)} | city={city} | season={season}")
        try:
            reply = recommend_recipe(
                inventory_list, preferences, city, season, message, weather_info,
                history=recent_convs, user_id=user_id,
            )
            _trace_tool(db, trace_id, step, "CHAT", "llm_recipe",
                        {"inventory_count": len(inventory_list), "city": city, "season": season},
                        {"reply_length": len(reply)},
                        "SUCCESS", int((time.time() - t0) * 1000))
            logger.info(f"[LLM] 食谱推荐成功 | reply_len={len(reply)} | duration={int((time.time() - t0) * 1000)}ms")
        except Exception as e:
            reply = "推荐服务暂时不可用，请稍后再试。"
            _trace_tool(db, trace_id, step, "CHAT", "llm_recipe",
                        {"inventory_count": len(inventory_list)},
                        {"error": str(e)}, "FAILED", int((time.time() - t0) * 1000))
            logger.error(f"[LLM] 食谱推荐失败 | error={e}")

        # 保存助手回复
        step += 1
        t0 = time.time()
        try:
            save_conversation(db, user_id, "assistant", reply)
            _trace_tool(db, trace_id, step, "CHAT", "db_save_conversation",
                        {"user_id": user_id, "role": "assistant"},
                        {"saved": True},
                        "SUCCESS", int((time.time() - t0) * 1000))
        except Exception as e:
            _trace_tool(db, trace_id, step, "CHAT", "db_save_conversation",
                        {"user_id": user_id},
                        {"error": str(e)}, "FAILED", int((time.time() - t0) * 1000))
            logger.error(f"[Agent] 保存助手回复失败 | error={e}")

        logger.info(f"[Agent] CHAT 完成 | user={user_id} | prefs_detected={len(new_prefs)}")
        return {"reply": reply, "detected_preferences": new_prefs}


    def chat_stream(self, db: Session, user_id: str, message: str, city: Optional[str] = None,
                     structured: bool = False):
        """流式版 chat：yield 文本片段，结束时副作用（保存偏好/对话/trace）一并完成。

        structured=True 时使用结构化食谱 prompt（前端会把 ===RECIPE=== 块解析成卡片）。
        """
        trace_id = uuid.uuid4()
        step = 0
        city = city or settings.DEFAULT_CITY
        season = get_season()

        logger.info(f"[Agent] CHAT_STREAM 开始 | user={user_id} | city={city} | message={message[:50]}")

        # 1) 偏好提取 + 保存
        step += 1
        t0 = time.time()
        try:
            new_prefs = extract_preferences(message)
            _trace_tool(db, trace_id, step, "CHAT", "preference_extract",
                        {"message": message[:100]},
                        {"preferences_count": len(new_prefs), "preferences": new_prefs},
                        "SUCCESS", int((time.time() - t0) * 1000))
        except Exception as e:
            new_prefs = []
            _trace_tool(db, trace_id, step, "CHAT", "preference_extract",
                        {"message": message[:100]}, {"error": str(e)},
                        "FAILED", int((time.time() - t0) * 1000))
            logger.error(f"[LLM] 偏好提取异常 | error={e}")

        if new_prefs:
            step += 1
            t0 = time.time()
            try:
                save_preferences(db, user_id, new_prefs)
                _trace_tool(db, trace_id, step, "CHAT", "db_save_preferences",
                            {"user_id": user_id, "count": len(new_prefs)},
                            {"saved": True},
                            "SUCCESS", int((time.time() - t0) * 1000))
            except Exception as e:
                _trace_tool(db, trace_id, step, "CHAT", "db_save_preferences",
                            {"user_id": user_id}, {"error": str(e)},
                            "FAILED", int((time.time() - t0) * 1000))

        save_conversation(db, user_id, "user", message)

        # 2) 库存
        step += 1
        t0 = time.time()
        try:
            items = db.query(Inventory).filter(Inventory.status == "IN_STOCK").all()
            inventory_list = []
            for item in items:
                metadata = item.agent_metadata or {}
                shelf_life = metadata.get("shelf_life_days", 7)
                expire_at_str = metadata.get("expire_at")
                if expire_at_str:
                    expire_at = datetime.fromisoformat(expire_at_str)
                    remain_days = max(0, (expire_at - datetime.now()).days)
                else:
                    remain_days = shelf_life
                inventory_list.append({"category": item.category, "remain_days": remain_days})
            _trace_tool(db, trace_id, step, "CHAT", "db_query_inventory",
                        {"user_id": user_id}, {"item_count": len(inventory_list)},
                        "SUCCESS", int((time.time() - t0) * 1000))
        except Exception as e:
            inventory_list = []
            _trace_tool(db, trace_id, step, "CHAT", "db_query_inventory",
                        {"user_id": user_id}, {"error": str(e)},
                        "FAILED", int((time.time() - t0) * 1000))

        preferences = get_preferences(db, user_id)
        # 拉最近对话作为上下文（用户刚发的这条还没存，所以正好是"上一轮"）
        recent_convs = get_recent_conversations(db, user_id, limit=10)

        # 3) 天气
        step += 1
        t0 = time.time()
        try:
            weather_info = get_current_weather(city)
            _trace_tool(db, trace_id, step, "CHAT", "weather_query",
                        {"city": city},
                        {"temperature": weather_info.get("temperature"),
                         "weather_desc": weather_info.get("weather_desc")},
                        "SUCCESS", int((time.time() - t0) * 1000))
        except Exception as e:
            weather_info = None
            _trace_tool(db, trace_id, step, "CHAT", "weather_query",
                        {"city": city}, {"error": str(e)},
                        "FAILED", int((time.time() - t0) * 1000))

        # 4) 流式 LLM
        step += 1
        t0 = time.time()
        full_reply_parts: list[str] = []
        try:
            stream_fn = recommend_structured_stream if structured else recommend_recipe_stream
            for piece in stream_fn(
                inventory_list, preferences, city, season, message, weather_info,
                history=recent_convs, user_id=user_id,
            ):
                full_reply_parts.append(piece)
                yield {"type": "delta", "content": piece}
            full_reply = "".join(full_reply_parts) or "推荐服务暂时不可用，请稍后再试。"
            _trace_tool(db, trace_id, step, "CHAT",
                        "llm_recipe_struct_stream" if structured else "llm_recipe_stream",
                        {"inventory_count": len(inventory_list), "city": city, "season": season,
                         "structured": structured},
                        {"reply_length": len(full_reply)},
                        "SUCCESS", int((time.time() - t0) * 1000))
        except Exception as e:
            full_reply = "推荐服务暂时不可用，请稍后再试。"
            yield {"type": "delta", "content": full_reply}
            _trace_tool(db, trace_id, step, "CHAT", "llm_recipe_stream",
                        {"inventory_count": len(inventory_list)}, {"error": str(e)},
                        "FAILED", int((time.time() - t0) * 1000))
            logger.error(f"[LLM] 流式食谱推荐失败 | error={e}")

        # 5) 保存助手回复
        try:
            save_conversation(db, user_id, "assistant", full_reply)
        except Exception as e:
            logger.error(f"[Agent] 保存助手回复失败 | error={e}")

        # 6) 结束帧（带偏好信息）
        yield {
            "type": "done",
            "detected_preferences": new_prefs,
            "trace_id": str(trace_id),
        }
        logger.info(f"[Agent] CHAT_STREAM 完成 | user={user_id}")
