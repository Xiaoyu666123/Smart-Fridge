"""验证：ITEM_IN 后立刻能通过 inventory.last-trace 查到完整工具链。"""
import json
import sys
import time
import urllib.request

BASE = "http://127.0.0.1:8000/api/v1"


def http(method, path, body=None, token=None):
    url = BASE + path
    data = json.dumps(body, ensure_ascii=False).encode("utf-8") if body is not None else None
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    with urllib.request.urlopen(req, timeout=60) as resp:
        return json.loads(resp.read().decode("utf-8") or "{}")


t = http("POST", "/admin/auth/login", body={"username": "admin", "password": "admin123"})["token"]

dev = f"luckfox-trace-{int(time.time())%10000}"
cat = f"AI测试食材-{int(time.time())%10000}"
print(f"device={dev} category={cat}")

# 1) ITEM_IN 入库
res = http("POST", "/admin/events/item",
            body={
                "device_id": dev,
                "timestamp": int(time.time() * 1000),
                "event_type": "ITEM_IN",
                "data": [{
                    "local_track_id": 1,
                    "category": cat,
                    "confidence": 0.92,
                    "bbox": [10, 20, 30, 40],
                }],
            }, token=t)
inv_id = res[0]["id"]
print(f"[OK] inventory id={inv_id}")

time.sleep(0.5)

# 2) last-trace
tr = http("GET", f"/admin/inventory/{inv_id}/last-trace", token=t)
print(f"trace_id={tr.get('trace_id')}")
print(f"steps={len(tr.get('steps', []))}")
for s in tr.get("steps", []):
    print(f"  #{s['step_order']} {s['tool_name']} | {s['status']} | {s['duration_ms']}ms")

# 收尾
http("DELETE", f"/admin/inventory/{inv_id}", token=t)

if tr.get("trace_id") and len(tr.get("steps", [])) >= 2:
    print("\n[PASS] AI 决策路径 OK")
else:
    print("\n[FAIL] 关联 trace 失败")
    sys.exit(1)
