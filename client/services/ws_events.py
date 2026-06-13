"""库存类事件的 WebSocket 广播辅助函数。

把 ORM Inventory 转成精简 dict（不带 feature_vector 避免数据爆炸），
按 inventory.created/updated/deleted/status_changed 的语义广播。
"""

import logging
from typing import Optional

from services.ws_manager import manager

logger = logging.getLogger(__name__)


def _serialize_inventory(inv) -> dict:
    """把 Inventory ORM 转成 ws 友好的简化 dict（不含 feature_vector）。"""
    if inv is None:
        return {}
    md = inv.agent_metadata or {}
    label = inv.label_data or {}
    return {
        "id": str(inv.id),
        "device_id": inv.device_id,
        "category": inv.category,
        "status": inv.status,
        "remain_ratio": float(inv.remain_ratio) if inv.remain_ratio is not None else 1.0,
        "bbox": inv.bbox,
        "agent_metadata": md,
        "snapshot_path": inv.snapshot_path,
        "label_text": inv.label_text,
        "label_data": label,
        "label_snapshot_path": inv.label_snapshot_path,
        "has_label": bool(inv.label_data) or bool(inv.label_text),
        "label_status": "label" if (inv.label_data or inv.label_text) else "no_label",
        "expire_source": md.get("expire_source"),
        "expire_at": md.get("expire_at"),
        "brand": label.get("brand") if label else None,
        "created_at": inv.created_at.isoformat() if inv.created_at else None,
        "update_at": inv.update_at.isoformat() if inv.update_at else None,
        "stored_at": inv.stored_at.isoformat() if getattr(inv, "stored_at", None) else None,
    }


def broadcast_inventory_created(inv, *, source: str = "agent"):
    """物品入库事件。source: agent / manual / bulk"""
    try:
        manager.broadcast_all_sync({
            "type": "inventory.created",
            "source": source,
            "data": _serialize_inventory(inv),
        })
    except Exception as e:
        logger.warning(f"[WS] broadcast inventory.created failed | error={e}")


def broadcast_inventory_updated(inv, *, source: str = "manual",
                                  prev_status: Optional[str] = None):
    """物品状态变化（编辑 / OUT_PENDING / CONSUMED）。"""
    try:
        manager.broadcast_all_sync({
            "type": "inventory.updated",
            "source": source,
            "prev_status": prev_status,
            "data": _serialize_inventory(inv),
        })
    except Exception as e:
        logger.warning(f"[WS] broadcast inventory.updated failed | error={e}")


def broadcast_inventory_deleted(inventory_id, *, source: str = "manual"):
    """物品被删除。"""
    try:
        manager.broadcast_all_sync({
            "type": "inventory.deleted",
            "source": source,
            "id": str(inventory_id),
        })
    except Exception as e:
        logger.warning(f"[WS] broadcast inventory.deleted failed | error={e}")
