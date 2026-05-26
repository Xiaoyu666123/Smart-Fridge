import time
import uuid
import base64
import os
import logging
from datetime import datetime, timedelta
from typing import Optional

from sqlalchemy.orm import Session

from models import Inventory, EventLog
from crud import save_trace
from services.vision import recognize_food
from services.llm import estimate_freshness, recommend_recipe, get_season
from services.embedding import extract_image_vector, SIMILARITY_THRESHOLD
from services.memory import (
    extract_preferences,
    save_preferences,
    get_preferences,
    save_conversation,
    get_recent_conversations,
)
from services.weather import get_current_weather
from config import settings

logger = logging.getLogger(__name__)

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
        2. 提取图片向量 + 同类别向量相似度去重
        3. 置信度低于阈值时调 vision 辅助识别
        4. 调 LLM 推算保鲜期
        5. 写入 inventory + event_logs
        """
        trace_id = uuid.uuid4()
        step = 0
        device_id = event.device_id
        CONFIDENCE_THRESHOLD = 0.5

        logger.info(f"[Agent] ITEM_IN 开始 | device={device_id} | category={item.category} | confidence={item.confidence} | has_image={bool(item.crop_image)}")

        # 保存图片
        snapshot_path = _save_crop_image(event.device_id, item.local_track_id, item.crop_image)

        # 向量相似度去重：提取新图片向量，和同类别已有库存比对
        feature_vector = None
        if item.crop_image:
            step += 1
            t0 = time.time()
            try:
                feature_vector = extract_image_vector(item.crop_image)
                _trace_tool(db, trace_id, step, "ITEM_IN", "embedding_extract",
                            {"has_image": True},
                            {"dim": len(feature_vector) if feature_vector else 0},
                            "SUCCESS", int((time.time() - t0) * 1000), device_id)
                logger.info(f"[Embedding] 新图片向量提取 | dim={len(feature_vector) if feature_vector else 0} | duration={int((time.time() - t0) * 1000)}ms")
            except Exception as e:
                _trace_tool(db, trace_id, step, "ITEM_IN", "embedding_extract",
                            {"has_image": True},
                            {"error": str(e)}, "FAILED", int((time.time() - t0) * 1000), device_id)
                logger.error(f"[Embedding] 向量提取失败 | error={e}")

            # 向量相似度去重
            if feature_vector:
                step += 1
                t0 = time.time()
                try:
                    from pgvector.sqlalchemy import Vector as PgVector
                    from sqlalchemy import text, func, cast, String
                    # 提高 HNSW 搜索精度
                    db.execute(text("SET hnsw.ef_search = 1000"))
                    # 查同类别+在库+有向量的记录，用单条SQL取最相似
                    vec_str = "[" + ",".join(str(v) for v in feature_vector) + "]"
                    row = db.execute(
                        text("""
                            SELECT id, 1 - (CAST(:vec AS vector) <=> feature_vector) AS similarity
                            FROM inventory
                            WHERE category = :category
                              AND status = 'IN_STOCK'
                              AND feature_vector IS NOT NULL
                            ORDER BY similarity DESC
                            LIMIT 1
                        """),
                        {"vec": vec_str, "category": item.category},
                    ).fetchone()
                    max_similarity = row[1] if row else 0.0
                    matched_id = str(row[0]) if row else None

                    logger.info(f"[Embedding] 向量相似度比对 | category={item.category} | best_similarity={max_similarity:.4f} | threshold={SIMILARITY_THRESHOLD} | matched_id={matched_id}")
                    _trace_tool(db, trace_id, step, "ITEM_IN", "vector_dedup",
                                {"category": item.category},
                                {"max_similarity": round(max_similarity, 4), "is_duplicate": max_similarity >= SIMILARITY_THRESHOLD},
                                "SUCCESS", int((time.time() - t0) * 1000), device_id)

                    if max_similarity >= SIMILARITY_THRESHOLD:
                        logger.info(f"[Embedding] 判定为同一物品，跳过入库 | category={item.category} | similarity={max_similarity:.4f} | matched={matched_id}")
                        return None
                    else:
                        logger.info(f"[Embedding] 非同一物品，继续入库 | category={item.category} | similarity={max_similarity:.4f}")
                except Exception as e:
                    _trace_tool(db, trace_id, step, "ITEM_IN", "vector_dedup",
                                {"category": item.category},
                                {"error": str(e)}, "FAILED", int((time.time() - t0) * 1000), device_id)
                    logger.error(f"[Embedding] 向量去重异常，继续入库 | error={e}")

        # 视觉识别（仅低置信度时调用）
        category = item.category
        vision_confidence = item.confidence
        if item.confidence < CONFIDENCE_THRESHOLD and item.crop_image:
            logger.info(f"[Vision] 置信度 {item.confidence} 低于阈值 {CONFIDENCE_THRESHOLD}，调用视觉辅助识别 | device={device_id}")
            step += 1
            t0 = time.time()
            try:
                vision_result = recognize_food(item.crop_image)
                if vision_result["confidence"] > item.confidence:
                    category = vision_result["category"]
                    vision_confidence = vision_result["confidence"]
                    logger.info(f"[Vision] 辅助识别结果优于原始 | original={item.category}({item.confidence}) -> vision={vision_result['category']}({vision_result['confidence']})")
                else:
                    logger.info(f"[Vision] 原始置信度更高，保留原始 | original={item.category}({item.confidence}) -> vision={vision_result['category']}({vision_result['confidence']})")
                _trace_tool(db, trace_id, step, "ITEM_IN", "vision_recognize",
                            {"reason": "low_confidence", "original_confidence": item.confidence},
                            {"category": vision_result["category"], "confidence": vision_result["confidence"]},
                            "SUCCESS", int((time.time() - t0) * 1000), device_id)
            except Exception as e:
                logger.error(f"[Vision] 辅助识别异常 | device={device_id} | error={e}")
                _trace_tool(db, trace_id, step, "ITEM_IN", "vision_recognize",
                            {"reason": "low_confidence", "original_confidence": item.confidence},
                            {"error": str(e)}, "FAILED", int((time.time() - t0) * 1000), device_id)
        else:
            if item.confidence >= CONFIDENCE_THRESHOLD:
                logger.info(f"[Vision] 置信度 {item.confidence} 高于阈值 {CONFIDENCE_THRESHOLD}，跳过视觉识别 | device={device_id}")
            elif not item.crop_image:
                logger.info(f"[Vision] 无图片数据，跳过视觉识别 | device={device_id}")

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
                agent_metadata={
                    "shelf_life_days": freshness["shelf_life_days"],
                    "storage_advice": freshness["storage_advice"],
                    "expire_at": expire_at.isoformat(),
                    "vision_confidence": vision_confidence,
                },
            )
            db.add(inv)
            db.flush()
            _trace_tool(db, trace_id, step, "ITEM_IN", "db_write_inventory",
                        {"category": category, "device_id": event.device_id},
                        {"inventory_id": str(inv.id)},
                        "SUCCESS", int((time.time() - t0) * 1000), device_id)
            logger.info(f"[Agent] 写入 inventory 成功 | id={inv.id} | category={category}")
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
            reply = recommend_recipe(inventory_list, preferences, city, season, message, weather_info)
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
