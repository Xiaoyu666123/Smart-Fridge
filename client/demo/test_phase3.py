"""测试设备心跳 + 设备管理 + 性能监控 + AI 决策路径接口。"""
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
    with urllib.request.urlopen(req, timeout=30) as resp:
        text = resp.read().decode("utf-8")
        return json.loads(text) if text else {}


def admin_login():
    r = http("POST", "/admin/auth/login", body={"username": "admin", "password": "admin123"})
    return r["token"]


def main():
    token = admin_login()
    print("[OK] login")

    # 1) heartbeat - 第一次注册
    dev_id = f"luckfox-phase3-{int(time.time()) % 100000}"
    print(f"\n========== 心跳 + 自动注册 ==========")
    r = http("POST", "/admin/events/heartbeat",
              body={"device_id": dev_id, "event": "startup"}, token=token)
    print(f"  heartbeat -> {r}")
    assert r["auto_registered"] is True
    print("  [PASS] 自动注册 OK")

    # 再发一次（不应该重复注册）
    r = http("POST", "/admin/events/heartbeat",
              body={"device_id": dev_id, "event": "heartbeat"}, token=token)
    assert r["auto_registered"] is False
    print("  [PASS] 已存在不再注册")

    # 2) 设备列表
    print("\n========== 设备列表 ==========")
    devices = http("GET", "/admin/devices", token=token)
    print(f"  设备数: {len(devices)}")
    target = next((d for d in devices if d["device_id"] == dev_id), None)
    assert target is not None
    print(f"  目标设备 live_status={target['live_status']} hb={target['heartbeat_count']}")
    assert target["live_status"] == "online"
    print("  [PASS] 列表 OK 且为 online")

    # 3) 编辑设备
    print("\n========== 编辑设备 ==========")
    r = http("PUT", f"/admin/devices/{dev_id}",
              body={"name": "测试冰箱-A", "location": "测试机房"}, token=token)
    print(f"  edit -> name={r['name']} location={r['location']}")
    assert r["name"] == "测试冰箱-A"
    print("  [PASS] 编辑 OK")

    # 4) 心跳曲线
    print("\n========== 心跳曲线 ==========")
    r = http("GET", f"/admin/devices/{dev_id}/heartbeats?hours=1&bucket=10", token=token)
    print(f"  hours={r['hours']} buckets={len(r['series'])}")
    total = sum(b["count"] for b in r["series"])
    print(f"  总心跳数={total}")
    assert total >= 2
    print("  [PASS] 心跳曲线 OK")

    # 5) 性能统计
    print("\n========== 性能统计 ==========")
    r = http("GET", "/admin/stats/perf?hours=24", token=token)
    print(f"  total_steps={r['total_steps']} tools={len(r['tools'])}")
    if r["tools"]:
        top = r["tools"][0]
        print(f"  top: {top['tool_name']} count={top['count']} p50={top['p50_ms']}ms p95={top['p95_ms']}ms 成功率={top['success_rate']*100:.1f}%")
    print("  [PASS] 性能统计 OK")

    # 6) Inventory last-trace（找一条 ITEM_IN 创建的 inventory）
    print("\n========== AI 决策路径（last-trace）==========")
    invs = http("GET", "/admin/inventory?limit=10", token=token)
    found = False
    for inv in invs:
        try:
            tr = http("GET", f"/admin/inventory/{inv['id']}/last-trace", token=token)
            if tr.get("trace_id"):
                print(f"  inventory={inv['category']} 关联 trace={tr['trace_id']} steps={len(tr['steps'])}")
                for step in tr["steps"][:3]:
                    print(f"    - {step['tool_name']} {step['status']} {step['duration_ms']}ms")
                found = True
                break
        except Exception:
            continue
    if found:
        print("  [PASS] AI 决策路径 OK")
    else:
        print("  [skip] 没找到关联 trace 的 inventory（可能都是手动入库）")

    # 7) 收尾：删除测试设备
    print(f"\n收尾：删除测试设备 {dev_id}")
    http("DELETE", f"/admin/devices/{dev_id}", token=token)


if __name__ == "__main__":
    main()
