"""验证 bulk_create_inventory 也会广播。"""
import asyncio
import base64
import json
import os
import time
import urllib.parse
import urllib.request
import websockets

BASE = "http://127.0.0.1:8000/api/v1"
WS_URL = "ws://127.0.0.1:8000/api/v1/admin/ws/inventory"


def http(method, path, body=None, token=None):
    url = BASE + path
    data = json.dumps(body).encode() if body is not None else None
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    with urllib.request.urlopen(req, timeout=20) as resp:
        text = resp.read().decode()
        return json.loads(text) if text else {}


async def listen(token, events, started, stop, max_events=4):
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
                ev = json.loads(msg)
                events.append(ev)
                t = ev.get("type")
                if t == "ready":
                    print("[WS] ready")
                else:
                    print(f"[WS] {t} | source={ev.get('source')} | category={ev.get('data', {}).get('category')}")
                if len(events) >= max_events:
                    break
        finally:
            try:
                await ws.close()
            except Exception:
                pass


async def main():
    # 登录
    login = http("POST", "/admin/auth/login",
                  body={"username": "admin", "password": "admin123"})
    token = login["token"]
    print(f"[OK] login")

    # 准备 3 张占位图（直接写 1 字节）
    snapshot_paths = []
    for i in range(3):
        p = f"uploads/_bulk_test_{int(time.time())}_{i}.jpg"
        os.makedirs("uploads", exist_ok=True)
        # 写一个唯一的 1-byte 文件，避免去重
        with open(p, "wb") as f:
            f.write(bytes([i, 0xff, 0xfe]))
        snapshot_paths.append(p)

    events = []
    started = asyncio.Event()
    stop = asyncio.Event()
    # ready + 3 条 created
    listener = asyncio.create_task(listen(token, events, started, stop, max_events=4))

    await asyncio.wait_for(started.wait(), timeout=10)
    await asyncio.sleep(0.3)
    print("[OK] WS connected")

    # 触发 bulk
    items = []
    for i, p in enumerate(snapshot_paths):
        items.append({
            "category": f"批量测试-{i}",
            "confidence": 0.9,
            "bbox": [0, 0, 0, 0],
            "snapshot_path": p,
        })
    res = http("POST", "/admin/inventory/bulk",
                body={"device_id": "bulk-test-dev", "items": items},
                token=token)
    print(f"[OK] bulk created | created={res.get('created_count')} skipped={res.get('skipped_count')}")
    created_ids = res.get("inventory_ids", [])

    try:
        await asyncio.wait_for(listener, timeout=10)
    except asyncio.TimeoutError:
        stop.set()
        listener.cancel()

    # 收尾删除测试库存
    for cid in created_ids:
        try:
            http("DELETE", f"/admin/inventory/{cid}", token=token)
        except Exception:
            pass
    for p in snapshot_paths:
        try:
            os.remove(p)
        except Exception:
            pass

    # 校验：应收到 ready + 3 条 inventory.created (source=bulk)
    bulk_events = [e for e in events if e.get("type") == "inventory.created" and e.get("source") == "bulk"]
    print(f"\n[Result] events={len(events)} | bulk-created={len(bulk_events)}")
    if len(bulk_events) >= 3:
        print("[PASS] bulk 广播 OK")
    else:
        print("[FAIL] bulk 广播缺失")


if __name__ == "__main__":
    asyncio.run(main())
