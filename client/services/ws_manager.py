"""WebSocket 连接管理器（按 user_id 推送通知）。

设计：
- 每个用户可能有多个浏览器 tab → 一个 user_id 对应多条 ws 连接
- broadcast_to_user(user_id, event) 给该用户所有连接发同一条消息
- 这是后台单进程内存方案；多 worker / 多机要换 Redis pub/sub，这里够用
"""

import asyncio
import json
import logging
from typing import Dict, Set
from fastapi import WebSocket

logger = logging.getLogger(__name__)


class ConnectionManager:
    def __init__(self):
        # user_id -> set of websockets
        self._conns: Dict[str, Set[WebSocket]] = {}
        self._lock = asyncio.Lock()

    async def connect(self, user_id: str, ws: WebSocket):
        await ws.accept()
        async with self._lock:
            self._conns.setdefault(user_id, set()).add(ws)
        logger.info(f"[WS] connect | user={user_id} | total={len(self._conns[user_id])}")

    async def disconnect(self, user_id: str, ws: WebSocket):
        async with self._lock:
            conns = self._conns.get(user_id)
            if conns and ws in conns:
                conns.discard(ws)
                if not conns:
                    self._conns.pop(user_id, None)
        logger.info(f"[WS] disconnect | user={user_id}")

    async def send_to_user(self, user_id: str, event: dict):
        """异步给用户的所有连接发一条 JSON 消息。"""
        conns = list(self._conns.get(user_id, set()))
        if not conns:
            return
        text = json.dumps(event, ensure_ascii=False, default=str)
        dead = []
        for ws in conns:
            try:
                await ws.send_text(text)
            except Exception as e:
                logger.warning(f"[WS] send failed | user={user_id} | error={e}")
                dead.append(ws)
        # 清理失效连接
        for ws in dead:
            await self.disconnect(user_id, ws)

    def broadcast_to_user_sync(self, user_id: str, event: dict):
        """同步上下文里调（如普通 def 路由处理器中），把 send_to_user 调度到事件循环。"""
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = None
        coro = self.send_to_user(user_id, event)
        if loop and loop.is_running():
            asyncio.ensure_future(coro)
        else:
            # 兜底：直接 run（一般不会走到，因为 FastAPI 总有 loop）
            try:
                asyncio.run(coro)
            except Exception as e:
                logger.warning(f"[WS] broadcast_sync fallback failed | error={e}")

    async def broadcast_all(self, event: dict):
        """广播给所有在线连接（不区分用户）。

        用于"全局事件"——库存增删、设备上下线等所有人都该看到的事。
        """
        text = json.dumps(event, ensure_ascii=False, default=str)
        all_conns: list = []
        for conns in self._conns.values():
            all_conns.extend(list(conns))
        if not all_conns:
            return
        dead = []
        for ws in all_conns:
            try:
                await ws.send_text(text)
            except Exception as e:
                logger.warning(f"[WS] broadcast failed | error={e}")
                dead.append(ws)
        # 清理失效连接（按 user_id 反查较麻烦，这里直接尝试断开）
        for ws in dead:
            for uid, conns in list(self._conns.items()):
                if ws in conns:
                    await self.disconnect(uid, ws)
                    break

    def broadcast_all_sync(self, event: dict):
        """同步上下文里调 broadcast_all 的入口。"""
        coro = self.broadcast_all(event)
        try:
            loop = asyncio.get_event_loop()
            if loop and loop.is_running():
                asyncio.ensure_future(coro)
                return
        except RuntimeError:
            pass
        try:
            asyncio.run(coro)
        except Exception as e:
            logger.warning(f"[WS] broadcast_all_sync fallback failed | error={e}")


manager = ConnectionManager()
