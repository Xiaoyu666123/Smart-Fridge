"""端到端测试库存 WS 实时推送。

流程：
  1. admin 登录
  2. 开 WS 监听 /admin/ws/inventory
  3. POST/PUT/DELETE /admin/inventory
  4. 验证 WS 收到 ready / inventory.created / inventory.updated / inventory.deleted
"""
import asyncio
import json
import sys
import urllib.parse
import urllib.request

import websockets

BASE = "http://127.0.0.1:8000/api/v1"
WS_URL = "ws://127.0.0.1:8000/api/v1/admin/ws/inventory"


def http(method: str, path: str, body=None, token=None):
    url = BASE + path
    data = json.dumps(body).encode() if body is not None else None
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    with urllib.request.urlopen(req, timeout=20) as resp:
        text = resp.read().decode()
        return json.loads(text) if text else {}


async def listen(token: str, events: list, started: asyncio.Event, stop: asyncio.Event):
    url = WS_URL + "?token=" + urllib.parse.quote(token)
    async with websockets.connect(url, open_timeout=10) as ws:
        started.set()
        try:
            while not stop.is_set():
                try:
                    msg = await asyncio.wait_for(ws.recv(), timeout=10)
                except asyncio.TimeoutError:
                    if stop.is_set():
                        break
                    continue
                events.append(msg)
                print(f"[WS] recv: {msg}")
                if len(events) >= 4:
                    break
        finally:
            try:
                await ws.close()
            except Exception:
                pass


async def main():
    # 1. 登录
    login = http("POST", "/admin/auth/login",
                  body={"username": "admin", "password": "admin123"})
    token = login["token"]
    print(f"[OK] admin login | token={token[:20]}...")

    events = []
    started = asyncio.Event()
    stop = asyncio.Event()
    listener = asyncio.create_task(listen(token, events, started, stop))

    # 等 WS 连上
    await asyncio.wait_for(started.wait(), timeout=10)
    await asyncio.sleep(0.5)
    print("[OK] WS connected")

    # 2. 创建
    inv = http("POST", "/admin/inventory",
                body={
                    "device_id": "ws-test-device",
                    "category": "WS测试食材",
                    "status": "IN_STOCK",
                    "remain_ratio": 1.0,
                    "agent_metadata": {"confidence": 0.95},
                },
                token=token)
    inv_id = inv["id"]
    print(f"[OK] created inventory | id={inv_id}")
    await asyncio.sleep(0.8)

    # 3. 更新
    http("PUT", f"/admin/inventory/{inv_id}",
          body={"remain_ratio": 0.5, "status": "OUT_PENDING"},
          token=token)
    print("[OK] updated inventory")
    await asyncio.sleep(0.8)

    # 4. 删除
    http("DELETE", f"/admin/inventory/{inv_id}", token=token)
    print("[OK] deleted inventory")

    # 5. 等收齐 WS 事件
    try:
        await asyncio.wait_for(listener, timeout=8)
    except asyncio.TimeoutError:
        stop.set()
        try:
            await asyncio.wait_for(listener, timeout=3)
        except Exception:
            listener.cancel()

    # 6. 校验
    print("\n========== Summary ==========")
    print(f"events received: {len(events)}")
    types = []
    for e in events:
        try:
            ev = json.loads(e)
            types.append(ev.get("type"))
        except Exception:
            types.append("?")
    print("types:", types)

    expect = {"ready", "inventory.created", "inventory.updated", "inventory.deleted"}
    got = set(types)
    missing = expect - got
    if missing:
        print(f"[FAIL] missing event types: {missing}")
        sys.exit(1)
    print("[PASS] all 4 expected event types received")


if __name__ == "__main__":
    asyncio.run(main())
