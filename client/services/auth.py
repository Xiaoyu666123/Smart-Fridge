"""管理员与普通用户独立的认证体系。

设计原则：
1. 两套 JWT 密钥，互相不通用。
2. Token 载荷必须包含 user_type 字段，分别为 'admin' / 'user'。
3. 解码时严格校验密钥与 user_type，任一不匹配都视为非法 Token。
4. get_current_admin / get_current_user 各自只查对应的表，杜绝跨表越权。
"""

import bcrypt
from datetime import datetime, timedelta
from jose import jwt, JWTError
from fastapi import Depends, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from typing import Optional

from config import settings
from database import get_db
from models import User, Admin

security = HTTPBearer()

ADMIN_USER_TYPE = "admin"
USER_USER_TYPE = "user"


# ---- 密码哈希 ----

def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(password: str, password_hash: str) -> bool:
    return bcrypt.checkpw(password.encode(), password_hash.encode())


# ---- 管理员 Token ----

def create_admin_token(admin_id: str) -> str:
    expire = datetime.utcnow() + timedelta(hours=settings.ADMIN_JWT_EXPIRE_HOURS)
    payload = {"sub": admin_id, "user_type": ADMIN_USER_TYPE, "exp": expire}
    return jwt.encode(payload, settings.ADMIN_JWT_SECRET, algorithm="HS256")


def decode_admin_token(token: str) -> Optional[dict]:
    try:
        payload = jwt.decode(token, settings.ADMIN_JWT_SECRET, algorithms=["HS256"])
    except JWTError:
        return None
    if payload.get("user_type") != ADMIN_USER_TYPE:
        return None
    return payload


def get_current_admin(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db),
) -> Admin:
    payload = decode_admin_token(credentials.credentials)
    if not payload:
        raise HTTPException(status_code=401, detail="管理员登录凭证无效")
    admin = db.query(Admin).filter(Admin.id == payload["sub"]).first()
    if not admin:
        raise HTTPException(status_code=401, detail="管理员不存在")
    return admin


# ---- 普通用户 Token ----

def create_user_token(user_id: str) -> str:
    expire = datetime.utcnow() + timedelta(hours=settings.USER_JWT_EXPIRE_HOURS)
    payload = {"sub": user_id, "user_type": USER_USER_TYPE, "exp": expire}
    return jwt.encode(payload, settings.USER_JWT_SECRET, algorithm="HS256")


def decode_user_token(token: str) -> Optional[dict]:
    try:
        payload = jwt.decode(token, settings.USER_JWT_SECRET, algorithms=["HS256"])
    except JWTError:
        return None
    if payload.get("user_type") != USER_USER_TYPE:
        return None
    return payload


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db),
) -> User:
    payload = decode_user_token(credentials.credentials)
    if not payload:
        raise HTTPException(status_code=401, detail="用户登录凭证无效")
    user = db.query(User).filter(User.id == payload["sub"]).first()
    if not user:
        raise HTTPException(status_code=401, detail="用户不存在")
    return user
