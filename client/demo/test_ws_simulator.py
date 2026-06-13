"""测试 LuckFox simulator 端侧 ITEM_IN 是否能触发 source=agent 的 WS 广播。

为避免触发去重和云端 vision 调用（耗时），这里发一个不带 crop_image 的
ITEM_IN，agent 会跳过 dedup/vision_assist，直接走 LLM 保鲜期推算 + 入库 + 广播。
"""
import asyncio
import json
import sys
import time
import urllib.parse
import urllib.request

import websockets

BASE = "http://127.0.0.1:8000/api/v1"
WS_URL = "ws://127.0.0.1:8000/api/v1/admin/ws/inventory"


def http(method, path, body=None, token=None, timeout=30):
    url = BASE + path
    data = json.dumps(body).encode() if body is not None else None
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        text = resp.read().decode()
        return json.loads(text) if text else {}


async def listen(token, events, started, stop, max_events):
    url = WS_URL + "?token=" + urllib.parse.quote(token)
    async with websockets.connect(url, open_timeout=10) as ws:
        started.set()
        try:
            while not stop.is_set():
                try:
                    msg = await asyncio.wait_for(ws.recv(), timeout=15)
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
                    src = ev.get("source", "?")
                    cat = ev.get("data", {}).get("category", "?")
                    print(f"[WS] {t} | source={src} | category={cat}")
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
    print("[OK] login")

    events = []
    started = asyncio.Event()
    stop = asyncio.Event()
    # ready + 1 条 ITEM_IN created
    listener = asyncio.create_task(listen(token, events, started, stop, max_events=2))
    await asyncio.wait_for(started.wait(), timeout=10)
    await asyncio.sleep(0.3)
    print("[OK] WS connected")

    # 模拟 LuckFox 端侧 ITEM_IN（不带图，避开 dedup + vision）
    payload = {
        "device_id": "luckfox-sim",
        "timestamp": int(time.time() * 1000),
        "event_type": "ITEM_IN",
        "data": [{
            "local_track_id": int(time.time()) % 9999,
            "category": "模拟苹果-WS-Test",
            "confidence": 0.92,
            "bbox": [120, 80, 160, 200],
            # 故意不带 crop_image
        }],
    }
    print("[step] 发送 ITEM_IN 事件...")
    res = http("POST", "/admin/events/item", body=payload, token=token, timeout=120)
    print(f"[OK] item event accepted | created={len(res)} | first_id={res[0].get('id') if res else None}")

    # 收 WS
    try:
        await asyncio.wait_for(listener, timeout=15)
    except asyncio.TimeoutError:
        stop.set()
        listener.cancel()

    # 收尾：删除测试入库记录，避免污染
    if res:
        try:
            http("DELETE", f"/admin/inventory/{res[0]['id']}", token=token)
            print("[cleanup] 已删除测试入库")
        except Exception:
            pass

    # 校验
    agent_events = [e for e in events
                    if e.get("type") == "inventory.created"
                    and e.get("source") == "agent"]
    print(f"\n[Result] events={len(events)} | source=agent created={len(agent_events)}")
    if agent_events:
        print("[PASS] agent ITEM_IN 广播 OK")
        sys.exit(0)
    else:
        print("[FAIL] 没收到 source=agent 的事件")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
