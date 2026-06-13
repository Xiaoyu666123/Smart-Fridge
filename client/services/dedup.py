"""库存入库去重统一服务。

两层防线，按顺序逐层判定：
1) 字节 hash：完全相同的图片直接拒绝（O(1) 等值匹配，最稳）
2) 向量相似度：超过阈值视为同一物品（不限 category，覆盖识别错分场景）

任何创建库存记录的入口（admin POST /inventory、bulk、ITEM_IN agent…）
都应统一调用 check_duplicate 来做拦截。
"""

import logging
from typing import Optional, Tuple

from sqlalchemy.orm import Session
from sqlalchemy import text

from services.embedding import extract_image_vector, SIMILARITY_THRESHOLD
from services.image_hash import compute_image_hash

logger = logging.getLogger(__name__)


def check_duplicate(
    db: Session,
    image_source: Optional[str],
    *,
    category: Optional[str] = None,
) -> Tuple[Optional[str], Optional[list[float]], Optional[dict]]:
    """统一去重检查。

    image_source: base64 字符串或文件路径。可为空（无图片时跳过整段去重）。
    category: 可选；当前不参与匹配，仅用于日志。保留参数以备未来按类内+类外分别策略。

    返回 (image_hash, feature_vector, dup_info)
      - image_hash: 算出的图片哈希（可写入新记录）
      - feature_vector: 提取的向量（可写入新记录）
      - dup_info: 命中重复时返回 {"reason": "hash"|"vector", "matched_id": str, "similarity": float|None}
                  没命中时为 None
    """
    if not image_source:
        return None, None, None

    # ---- 1) 字节 hash 拦截 ----
    img_hash = compute_image_hash(image_source)
    if img_hash:
        row = db.execute(
            text("SELECT id FROM inventory WHERE image_hash = :h LIMIT 1"),
            {"h": img_hash},
        ).fetchone()
        if row:
            matched_id = str(row[0])
            logger.info(f"[Dedup] hash 命中重复 | matched_id={matched_id} | hash={img_hash[:12]}...")
            return img_hash, None, {
                "reason": "hash",
                "matched_id": matched_id,
                "similarity": 1.0,
            }
        logger.info(f"[Dedup] hash 未命中 | hash={img_hash[:12]}...")

    # ---- 2) 向量相似度拦截 ----
    feature_vector = extract_image_vector(image_source)
    if not feature_vector:
        logger.warning("[Dedup] 向量提取失败，跳过相似度比对")
        return img_hash, None, None

    vec_str = "[" + ",".join(str(v) for v in feature_vector) + "]"

    # 强制顺序扫描，避免 HNSW 近似索引漏匹配
    db.execute(text("SET enable_indexscan = off"))
    try:
        row = db.execute(
            text("""
                SELECT id, category, 1 - (CAST(:vec AS vector) <=> feature_vector) AS similarity
                FROM inventory
                WHERE feature_vector IS NOT NULL
                ORDER BY similarity DESC
                LIMIT 1
            """),
            {"vec": vec_str},
        ).fetchone()
    finally:
        db.execute(text("SET enable_indexscan = on"))

    if not row:
        logger.info(f"[Dedup] 向量未命中（库内无向量记录）| category={category}")
        return img_hash, feature_vector, None

    matched_id = str(row[0])
    matched_category = row[1]
    similarity = float(row[2])

    logger.info(
        f"[Dedup] 向量比对 | best_similarity={similarity:.4f} "
        f"| matched_id={matched_id} | matched_category={matched_category} "
        f"| input_category={category} | threshold={SIMILARITY_THRESHOLD}"
    )

    if similarity >= SIMILARITY_THRESHOLD:
        return img_hash, feature_vector, {
            "reason": "vector",
            "matched_id": matched_id,
            "matched_category": matched_category,
            "similarity": similarity,
        }

    return img_hash, feature_vector, None
