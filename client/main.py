from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from database import engine, Base, SessionLocal
from api import router
from models import Admin
from config import settings

app = FastAPI(title="智能冰箱食材管理系统", version="2.0.0")

cors_origins = settings.cors_origin_list()
if not cors_origins and not settings.is_production:
    cors_origins = ["*"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router, prefix="/api/v1")

import asyncio
import logging
import os

logger = logging.getLogger(__name__)

UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)
app.mount("/uploads", StaticFiles(directory=UPLOAD_DIR), name="uploads")


@app.on_event("startup")
def on_startup():
    Base.metadata.create_all(bind=engine)
    _seed_admin()
    _seed_thresholds()
    _seed_vision_assist_config()


@app.on_event("startup")
async def _start_device_sweeper():
    """后台任务：定时刷新设备 offline 状态 + 清理旧心跳流水。"""
    async def loop():
        while True:
            try:
                await asyncio.sleep(60)
                db = SessionLocal()
                try:
                    _sweep_offline_devices(db)
                finally:
                    db.close()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.warning(f"[DeviceSweeper] tick failed | error={e}")
    asyncio.create_task(loop())


def _sweep_offline_devices(db):
    """超过 IDLE 阈值的设备置为 offline；每小时整点顺手清理 48h 之前的心跳流水。"""
    from datetime import datetime, timedelta
    from models import Device
    from crud import IDLE_THRESHOLD_SEC, cleanup_old_heartbeats
    cutoff = datetime.now() - timedelta(seconds=IDLE_THRESHOLD_SEC)
    rows = db.query(Device).filter(
        (Device.last_seen_at == None) | (Device.last_seen_at < cutoff)
    ).all()
    changed = 0
    for d in rows:
        if d.status != "offline":
            d.status = "offline"
            changed += 1
    if changed:
        db.commit()
    # 整点清理一次旧流水
    if datetime.now().minute < 1:
        try:
            n = cleanup_old_heartbeats(db, keep_hours=48)
            if n:
                logger.info(f"[DeviceSweeper] 清理旧心跳 {n} 条")
        except Exception as e:
            logger.warning(f"[DeviceSweeper] cleanup_old_heartbeats failed | error={e}")


def _seed_vision_assist_config():
    """视觉辅助识别区间策略默认值。表为空时插入 0.30 / 0.70。"""
    db = SessionLocal()
    try:
        from services.vision_assist import get_or_create_config
        get_or_create_config(db)
    finally:
        db.close()


def _seed_thresholds():
    db = SessionLocal()
    try:
        from crud import seed_default_thresholds
        seed_default_thresholds(db)
    finally:
        db.close()


def _seed_admin():
    """初始化管理员账户（仅当 admins 表为空且配置了初始密码时）。"""
    db = SessionLocal()
    try:
        existing = db.query(Admin).filter(Admin.username == "admin").first()
        if not existing:
            initial_password = settings.ADMIN_INITIAL_PASSWORD
            if not initial_password and not settings.is_production:
                initial_password = "admin123"
                logger.warning(
                    "[Security] using development default admin password; "
                    "set ADMIN_INITIAL_PASSWORD before deploying"
                )
            if not initial_password:
                logger.warning(
                    "[Security] no admin exists and ADMIN_INITIAL_PASSWORD is empty; "
                    "skipping admin seed"
                )
                return
            from services.auth import hash_password
            admin = Admin(
                username="admin",
                password_hash=hash_password(initial_password),
                real_name="系统管理员",
            )
            db.add(admin)
            db.commit()
    finally:
        db.close()


@app.get("/health")
def health_check():
    return {"status": "ok"}
