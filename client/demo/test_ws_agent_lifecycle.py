"""端到端测试：ITEM_IN -> ITEM_OUT 完整生命周期通过 WS 广播。

期望事件：
  ready
  inventory.created  source=agent  (来自 ITEM_IN)
  inventory.updated  source=agent  prev_status=IN_STOCK  (来自 ITEM_OUT)
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

UNIQUE_CATEGORY = f"WS生命周期测试-{int(time.time()) % 100000}"
DEVICE_ID = f"luckfox-lifecycle-{int(time.time()) % 100000}"


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
                src = ev.get("source", "?")
                cat = ev.get("data", {}).get("category", "?")
                prev = ev.get("prev_status", "")
                extra = f" prev={prev}" if prev else ""
                if t == "ready":
                    print("[WS] ready")
                else:
                    print(f"[WS] {t} | source={src} | category={cat}{extra}")
                if len(events) >= max_events:
                    break
        finally:
            try:
                await ws.close()
            except Exception:
                pass


async def main():
    login = http("POST", "/admin/auth/login",
                  body={"username": "admin", "password": "admin123"})
    token = login["token"]
    print("[OK] login")

    events = []
    started = asyncio.Event()
    stop = asyncio.Event()
    # ready + created + updated
    listener = asyncio.create_task(listen(token, events, started, stop, max_events=3))
    await asyncio.wait_for(started.wait(), timeout=10)
    await asyncio.sleep(0.3)
    print("[OK] WS connected")

    # 1) ITEM_IN
    item_in_payload = {
        "device_id": DEVICE_ID,
        "timestamp": int(time.time() * 1000),
        "event_type": "ITEM_IN",
        "data": [{
            "local_track_id": 1,
            "category": UNIQUE_CATEGORY,
            "confidence": 0.92,
            "bbox": [120, 80, 160, 200],
        }],
    }
    print(f"[step] ITEM_IN | category={UNIQUE_CATEGORY} | device={DEVICE_ID}")
    res_in = http("POST", "/admin/events/item", body=item_in_payload, token=token, timeout=60)
    if not res_in:
        print("[FAIL] ITEM_IN 没返回 inventory（可能被 dedup 命中）")
        sys.exit(1)
    inv_id = res_in[0]["id"]
    print(f"[OK] inventory created | id={inv_id}")

    await asyncio.sleep(0.6)

    # 2) ITEM_OUT
    item_out_payload = {
        "device_id": DEVICE_ID,
        "timestamp": int(time.time() * 1000),
        "event_type": "ITEM_OUT",
        "data": [{
            "local_track_id": 1,
            "category": UNIQUE_CATEGORY,
            "confidence": 0.91,
            "bbox": [120, 80, 160, 200],
        }],
    }
    print(f"[step] ITEM_OUT | category={UNIQUE_CATEGORY}")
    http("POST", "/admin/events/item", body=item_out_payload, token=token, timeout=30)
    print("[OK] ITEM_OUT accepted")

    try:
        await asyncio.wait_for(listener, timeout=15)
    except asyncio.TimeoutError:
        stop.set()
        listener.cancel()

    # 收尾
    try:
        http("DELETE", f"/admin/inventory/{inv_id}", token=token)
        print("[cleanup] deleted test inventory")
    except Exception:
        pass

    types_seen = [e.get("type") for e in events]
    has_created_agent = any(
        e.get("type") == "inventory.created" and e.get("source") == "agent"
        for e in events
    )
    has_updated_agent = any(
        e.get("type") == "inventory.updated" and e.get("source") == "agent"
        and e.get("prev_status") == "IN_STOCK"
        for e in events
    )
    print(f"\n[Result] events={len(events)} | types={types_seen}")
    if has_created_agent and has_updated_agent:
        print("[PASS] ITEM_IN 与 ITEM_OUT 全部通过 WS 推送")
        sys.exit(0)
    else:
        print(f"[FAIL] created_agent={has_created_agent} updated_agent={has_updated_agent}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
