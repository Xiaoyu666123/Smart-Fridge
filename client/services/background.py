"""后台保鲜期计算任务"""

import logging
import threading
from datetime import datetime, timedelta

from database import SessionLocal
from models import Inventory
from services.llm import estimate_freshness, get_season
from config import settings

logger = logging.getLogger(__name__)


def compute_freshness_task(inventory_id, category: str):
    """在后台线程中计算保鲜期并更新数据库。"""
    def _worker():
        db = SessionLocal()
        try:
            item = db.query(Inventory).filter(Inventory.id == inventory_id).first()
            if not item:
                logger.warning(f"[LLM] 后台保鲜计算 | inventory_id={inventory_id} 未找到记录")
                return

            city = settings.DEFAULT_CITY
            season = get_season()
            logger.info(f"[LLM] 后台保鲜计算开始 | inventory_id={inventory_id} | category={category} | city={city} | season={season}")
            try:
                freshness = estimate_freshness(category, city, season)
            except Exception as e:
                logger.error(f"[LLM] 后台保鲜计算失败 | inventory_id={inventory_id} | category={category} | error={e}")
                freshness = {"shelf_life_days": 7, "storage_advice": "冷藏保存"}

            metadata = dict(item.agent_metadata) if item.agent_metadata else {}
            metadata["shelf_life_days"] = freshness["shelf_life_days"]
            metadata["storage_advice"] = freshness["storage_advice"]
            expire_at = datetime.now() + timedelta(days=freshness["shelf_life_days"])
            metadata["expire_at"] = expire_at.isoformat()

            item.agent_metadata = metadata
            db.commit()
            logger.info(f"[LLM] 后台保鲜计算完成 | inventory_id={inventory_id} | category={category} | shelf_life={freshness['shelf_life_days']}天 | expire_at={metadata['expire_at']}")
        except Exception as e:
            logger.error(f"[LLM] 后台保鲜任务异常 | inventory_id={inventory_id} | error={e}")
        finally:
            db.close()

    t = threading.Thread(target=_worker, daemon=True)
    t.start()
