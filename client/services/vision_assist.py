"""视觉辅助识别决策服务。

中心化"是否调云端 vision 复核"的逻辑，供 ITEM_IN agent 与手动入库 POST /admin/inventory 共用。

设计：
- 区间 [lower_bound, upper_bound] 来自数据库 vision_assist_config 表，全局单行
- 表为空时按默认 0.3/0.7 自动 seed
- 每次决策实时读取（不缓存），保证 admin 改了立即生效
- 决策结果以 4 种枚举返回，便于上层写 trace
"""

import logging
from dataclasses import dataclass
from typing import Optional

from sqlalchemy.orm import Session

from models import VisionAssistConfig

logger = logging.getLogger(__name__)

DEFAULT_LOWER = 0.30
DEFAULT_UPPER = 0.70


# ---- 决策枚举 ----

DECISION_TRIGGERED = "TRIGGERED"
DECISION_SKIPPED_BELOW_LOWER = "SKIPPED_BELOW_LOWER"
DECISION_SKIPPED_ABOVE_UPPER = "SKIPPED_ABOVE_UPPER"
DECISION_SKIPPED_NO_CROP_IMAGE = "SKIPPED_NO_CROP_IMAGE"
DECISION_SKIPPED_INVALID_CONFIDENCE = "SKIPPED_INVALID_CONFIDENCE"


@dataclass
class VisionAssistDecision:
    """单次决策结果。"""
    triggered: bool
    decision: str            # 上面 5 种枚举之一
    edge_confidence: float
    lower: float
    upper: float
    has_crop_image: bool

    def trace_input(self) -> dict:
        return {
            "edge_confidence": self.edge_confidence,
            "lower": self.lower,
            "upper": self.upper,
            "has_crop_image": self.has_crop_image,
        }

    def trace_output(self) -> dict:
        return {"decision": self.decision, "triggered": self.triggered}


# ---- 配置读写 ----

def get_or_create_config(db: Session) -> VisionAssistConfig:
    """读取唯一一行 vision_assist_config，没有就插入默认值。

    每次都查 DB（不缓存），让 admin 修改后立即生效。
    """
    cfg = db.query(VisionAssistConfig).first()
    if cfg is not None:
        return cfg
    cfg = VisionAssistConfig(
        lower_bound=DEFAULT_LOWER,
        upper_bound=DEFAULT_UPPER,
        updated_by_admin_id=None,
    )
    db.add(cfg)
    db.commit()
    db.refresh(cfg)
    logger.info(f"[VisionAssist] seeded default config | lower={DEFAULT_LOWER} | upper={DEFAULT_UPPER}")
    return cfg


def update_config(db: Session, lower: float, upper: float, admin_id) -> VisionAssistConfig:
    """更新配置。已经在路由层做过校验，这里只做持久化。"""
    cfg = get_or_create_config(db)
    cfg.lower_bound = float(lower)
    cfg.upper_bound = float(upper)
    cfg.updated_by_admin_id = admin_id
    db.commit()
    db.refresh(cfg)
    return cfg


def is_default(cfg: VisionAssistConfig) -> bool:
    """是否为系统默认值且从未被修改。"""
    return (
        cfg.updated_by_admin_id is None
        and abs(float(cfg.lower_bound) - DEFAULT_LOWER) < 1e-9
        and abs(float(cfg.upper_bound) - DEFAULT_UPPER) < 1e-9
    )


# ---- 决策入口 ----

def decide(db: Session, edge_confidence: Optional[float], has_crop_image: bool) -> VisionAssistDecision:
    """根据当前配置和事件信息，决定是否触发云端复核。

    edge_confidence: 端侧上报的置信度，可能为 None 或非法值
    has_crop_image: 是否带了裁剪图（None / 空串都算 False）
    """
    cfg = get_or_create_config(db)
    lower = float(cfg.lower_bound)
    upper = float(cfg.upper_bound)

    # 1) 置信度非法
    try:
        if edge_confidence is None:
            raise ValueError("missing")
        ec = float(edge_confidence)
        if ec != ec:  # NaN
            raise ValueError("nan")
        if ec < 0 or ec > 1:
            raise ValueError(f"out of range: {ec}")
    except (TypeError, ValueError):
        return VisionAssistDecision(
            triggered=False,
            decision=DECISION_SKIPPED_INVALID_CONFIDENCE,
            edge_confidence=float(edge_confidence) if edge_confidence is not None else -1.0,
            lower=lower,
            upper=upper,
            has_crop_image=has_crop_image,
        )

    # 2) 区间外
    if ec < lower:
        return VisionAssistDecision(
            triggered=False, decision=DECISION_SKIPPED_BELOW_LOWER,
            edge_confidence=ec, lower=lower, upper=upper, has_crop_image=has_crop_image,
        )
    if ec > upper:
        return VisionAssistDecision(
            triggered=False, decision=DECISION_SKIPPED_ABOVE_UPPER,
            edge_confidence=ec, lower=lower, upper=upper, has_crop_image=has_crop_image,
        )

    # 3) 区间内但没有 crop_image
    if not has_crop_image:
        return VisionAssistDecision(
            triggered=False, decision=DECISION_SKIPPED_NO_CROP_IMAGE,
            edge_confidence=ec, lower=lower, upper=upper, has_crop_image=False,
        )

    # 4) 触发
    return VisionAssistDecision(
        triggered=True, decision=DECISION_TRIGGERED,
        edge_confidence=ec, lower=lower, upper=upper, has_crop_image=True,
    )
