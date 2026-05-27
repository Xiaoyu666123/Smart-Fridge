from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from database import engine, Base, SessionLocal
from api import router
from models import User

app = FastAPI(title="智能冰箱食材管理系统", version="2.0.0")

app.include_router(router, prefix="/api/v1")

import os
UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)
app.mount("/uploads", StaticFiles(directory=UPLOAD_DIR), name="uploads")


@app.on_event("startup")
def on_startup():
    Base.metadata.create_all(bind=engine)
    _seed_admin()
    _seed_thresholds()


def _seed_thresholds():
    db = SessionLocal()
    try:
        from crud import seed_default_thresholds
        seed_default_thresholds(db)
    finally:
        db.close()


def _seed_admin():
    db = SessionLocal()
    try:
        existing = db.query(User).filter(User.username == "admin").first()
        if not existing:
            from services.auth import hash_password
            admin = User(
                username="admin",
                password_hash=hash_password("admin123"),
                role="admin",
            )
            db.add(admin)
            db.commit()
    finally:
        db.close()


@app.get("/health")
def health_check():
    return {"status": "ok"}
