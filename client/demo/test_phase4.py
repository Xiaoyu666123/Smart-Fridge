"""验证库存分页 + 食谱评分笔记 + 设备恢复。"""
import json
import sys
import time
import urllib.request

BASE = "http://127.0.0.1:8000/api/v1"


def http(method, path, body=None, token=None, return_resp=False):
    url = BASE + path
    data = json.dumps(body, ensure_ascii=False).encode("utf-8") if body is not None else None
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    resp = urllib.request.urlopen(req, timeout=30)
    text = resp.read().decode("utf-8")
    parsed = json.loads(text) if text else {}
    if return_resp:
        return parsed, resp
    return parsed


def admin_login():
    return http("POST", "/admin/auth/login", body={"username": "admin", "password": "admin123"})["token"]


def user_login():
    return http("POST", "/user/auth/login", body={"username": "xiaoyu", "password": "test123"})["token"]


def main():
    at = admin_login()
    ut = user_login()
    print("[OK] login")

    # 1) 库存分页：limit + X-Total-Count
    print("\n========== 1) 库存分页 ==========")
    rows, resp = http("GET", "/admin/inventory?limit=5&offset=0", token=at, return_resp=True)
    total = resp.headers.get("X-Total-Count")
    print(f"  返回 {len(rows)} 条 / 总数 {total}")
    assert int(total) >= len(rows)
    print("  [PASS] 分页 + 总数 OK")

    # 2) 食谱评分 + 笔记
    print("\n========== 2) 食谱评分 + 笔记 ==========")
    saved = http("POST", "/user/recipes",
                  body={"name": f"测试食谱-{int(time.time()) % 10000}",
                        "summary": "phase4 测试",
                        "ingredients": [{"name": "番茄", "amount": "1个"}],
                        "steps": ["切", "炒"]},
                  token=ut)
    rid = saved["id"]
    print(f"  收藏 id={rid}")

    # 评分
    res = http("PUT", f"/user/recipes/{rid}", body={"rating": 4}, token=ut)
    print(f"  rating 后: rating={res['rating']}")
    assert res["rating"] == 4

    # 笔记
    res = http("PUT", f"/user/recipes/{rid}",
                body={"notes": "番茄要先翻炒到软"}, token=ut)
    print(f"  notes 后: notes={res['notes']}")
    assert res["notes"] == "番茄要先翻炒到软"

    # 同时
    res = http("PUT", f"/user/recipes/{rid}",
                body={"rating": 5, "notes": "完美"}, token=ut)
    print(f"  rating+notes: {res['rating']} / {res['notes']}")
    assert res["rating"] == 5

    # 边界：rating 6 应该 422
    try:
        http("PUT", f"/user/recipes/{rid}", body={"rating": 6}, token=ut)
        print("  [FAIL] rating=6 没被拒绝")
        sys.exit(1)
    except urllib.error.HTTPError as e:
        if e.code in (400, 422):
            print(f"  rating=6 被拒绝（{e.code}）")
        else:
            print(f"  [FAIL] 期望 4xx，实际 {e.code}")
            sys.exit(1)
    print("  [PASS] 评分笔记 OK")

    # 收尾
    http("DELETE", f"/user/recipes/{rid}", token=ut)

    # 3) 设备恢复
    print("\n========== 3) 设备恢复 ==========")
    dev_id = f"luckfox-undo-{int(time.time()) % 10000}"
    http("POST", "/admin/events/heartbeat",
          body={"device_id": dev_id, "event": "startup"}, token=at)
    http("PUT", f"/admin/devices/{dev_id}",
          body={"name": "测试-A", "location": "测试机房"}, token=at)
    http("DELETE", f"/admin/devices/{dev_id}", token=at)

    devices = http("GET", "/admin/devices", token=at)
    assert not any(d["device_id"] == dev_id for d in devices)
    print("  设备已删除")

    # 撤销恢复
    res = http("POST", "/admin/devices/restore",
                body={"device_id": dev_id, "name": "测试-A", "location": "测试机房"},
                token=at)
    print(f"  restore -> name={res['name']} status={res['live_status']}")
    assert res["device_id"] == dev_id
    print("  [PASS] 设备恢复 OK")

    # 收尾
    http("DELETE", f"/admin/devices/{dev_id}", token=at)
    print("\n全部通过 ✅")


if __name__ == "__main__":
    main()
