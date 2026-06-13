"""API 路由聚合入口。

挂载两个完全独立的子路由：
- /api/v1/admin/*  -> 管理员后台
- /api/v1/user/*   -> 普通用户端

注意 main.py 已为根路由设置 prefix="/api/v1"，
因此本文件内只暴露 /admin 与 /user 前缀。
"""

from fastapi import APIRouter

from api.admin import router as admin_router
from api.user import router as user_router

router = APIRouter()
router.include_router(admin_router)
router.include_router(user_router)

__all__ = ["router"]
