"""后端稳定性 / 健壮性测试。

和 test_all.py（功能正确性）互补，这里专门压：
  1. 并发压测       —— 多线程同时打同一批接口，看吞吐 / 错误率 / 延迟分布
  2. 异常输入       —— 畸形 JSON / 缺字段 / 超长字符串 / 错类型 / 注入串，期望 4xx 而不是 5xx
  3. 鉴权边界       —— 无 token / 过期格式 / 越权，期望 401
  4. 端侧事件健壮性 —— 缺 device_id / 空 data / 非法 event_type / 超大 bbox
  5. 顺序去重压力   —— 同一物品狂发 ITEM_IN，验证去重不崩
  6. WebSocket 抖动 —— 反复快速连接/断开，验证没有连接泄漏
  7. 持续负载       —— 持续打一段时间，看错误率是否随时间上升（内存/连接泄漏迹象）

只用 stdlib + websockets。
运行：python demo/test_stability.py
"""
import asyncio
import json
import statistics
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed

import websockets

BASE = "http://127.0.0.1:8000/api/v1"
WS_INV = "ws://127.0.0.1:8000/api/v1/admin/ws/inventory"

results = []   # (module, name, status, detail)


def record(module, name, ok, detail=""):
    status = "PASS" if ok else "FAIL"
    results.append((module, name, status, detail))
    flag = "✅" if ok else "❌"
    print(f"  {flag} {name}" + (f" — {detail}" if detail else ""))


def warn(module, name, detail=""):
    results.append((module, name, "WARN", detail))
    print(f"  ⚠️  {name}" + (f" — {detail}" if detail else ""))


def section(name):
    print(f"\n{'='*64}\n  {name}\n{'='*64}")


def raw_request(method, path, body=None, token=None, timeout=30, raw_body=None,
                headers=None):
    """返回 (status_code, elapsed_ms, body_text)。不抛异常。"""
    url = BASE + path
    if raw_body is not None:
        data = raw_body.encode("utf-8") if isinstance(raw_body, str) else raw_body
    elif body is not None:
        data = json.dumps(body, ensure_ascii=False).encode("utf-8")
    else:
        data = None
    h = {"Content-Type": "application/json"}
    if token:
        h["Authorization"] = f"Bearer {token}"
    if headers:
        h.update(headers)
    req = urllib.request.Request(url, data=data, headers=h, method=method)
    t0 = time.time()
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            txt = resp.read().decode("utf-8", errors="replace")
            return resp.status, (time.time() - t0) * 1000, txt
    except urllib.error.HTTPError as e:
        return e.code, (time.time() - t0) * 1000, e.read().decode("utf-8", errors="replace")
    except Exception as e:
        return -1, (time.time() - t0) * 1000, str(e)


def login():
    code, _, txt = raw_request("POST", "/admin/auth/login",
                                body={"username": "admin", "password": "admin123"})
    if code != 200:
        print(f"❌ admin 登录失败 code={code} body={txt[:200]}")
        sys.exit(1)
    at = json.loads(txt)["token"]
    code, _, txt = raw_request("POST", "/user/auth/login",
                                body={"username": "xiaoyu", "password": "test123"})
    ut = json.loads(txt)["token"] if code == 200 else None
    return at, ut


# ============== 1. 并发压测 ==============

def test_concurrency(at, ut):
    section("1. 并发压测（只读接口）")

    endpoints = [
        ("/admin/inventory?limit=20", "库存列表", at),
        ("/admin/stats/waste?days=30", "浪费分析", at),
        ("/admin/stats/nutrition?days=30", "营养报告", at),
        ("/user/stats/cooking?days=180", "烹饪日历", ut),
    ]

    for path, name, tok in endpoints:
        N = 60          # 总请求数
        WORKERS = 20    # 并发线程
        latencies = []
        errors = 0

        def worker(_):
            code, ms, _txt = raw_request("GET", path, token=tok, timeout=30)
            return code, ms

        t0 = time.time()
        with ThreadPoolExecutor(max_workers=WORKERS) as ex:
            futures = [ex.submit(worker, i) for i in range(N)]
            for f in as_completed(futures):
                code, ms = f.result()
                latencies.append(ms)
                if code != 200:
                    errors += 1
        total_s = time.time() - t0

        latencies.sort()
        p50 = statistics.median(latencies)
        p95 = latencies[int(len(latencies) * 0.95) - 1]
        p99 = latencies[int(len(latencies) * 0.99) - 1]
        qps = N / total_s
        ok = errors == 0
        record("concurrency", f"{name} ({WORKERS}并发x{N})", ok,
               f"err={errors} qps={qps:.0f} p50={p50:.0f}ms p95={p95:.0f}ms p99={p99:.0f}ms")


# ============== 2. 异常输入（期望 4xx，不能 5xx）==============

def test_malformed(at):
    section("2. 异常 / 畸形输入（期望 4xx，绝不能 5xx）")

    cases = [
        # (method, path, raw_body/body, 描述)
        ("POST", "/admin/inventory", "raw", "{not valid json", "畸形 JSON"),
        ("POST", "/admin/inventory", "body", {}, "缺必填 category"),
        ("POST", "/admin/inventory", "body", {"category": 12345}, "category 类型错误(int)"),
        ("POST", "/admin/inventory", "body", {"category": "x" * 5000}, "category 超长 5000 字"),
        ("POST", "/admin/inventory", "body",
         {"category": "test", "remain_ratio": "abc"}, "remain_ratio 非数字"),
        ("POST", "/admin/events/item", "body",
         {"timestamp": 1, "event_type": "BOGUS", "data": []}, "非法 event_type"),
        ("POST", "/admin/events/item", "body",
         {"timestamp": "notint", "event_type": "ITEM_IN", "data": []}, "timestamp 类型错误"),
        ("POST", "/admin/events/item", "body",
         {"timestamp": 1, "event_type": "ITEM_IN",
          "data": [{"local_track_id": 1, "category": "x", "confidence": 0.5,
                    "bbox": [1, 2]}]}, "bbox 长度不足"),
        ("POST", "/admin/events/item", "body",
         {"timestamp": 1, "event_type": "ITEM_IN",
          "data": [{"local_track_id": 1, "category": "x", "confidence": 2.5,
                    "bbox": [1, 2, 3, 4]}]}, "confidence 越界(>1)"),
        ("GET", "/admin/inventory?limit=-5", None, None, "负数 limit"),
        ("GET", "/admin/inventory?limit=abc", None, None, "limit 非数字"),
        ("GET", "/admin/inventory/not-a-uuid", None, None, "非法 UUID 路径"),
        ("PUT", "/admin/agent/vision-assist-config", "body",
         {"lower": "x", "upper": "y"}, "区间配置类型错误"),
        ("POST", "/admin/events/label_scan", "body", {}, "label_scan 缺 label_image"),
    ]

    for method, path, kind, payload, desc in cases:
        if kind == "raw":
            code, ms, txt = raw_request(method, path, raw_body=payload, token=at)
        elif kind == "body":
            code, ms, txt = raw_request(method, path, body=payload, token=at)
        else:
            code, ms, txt = raw_request(method, path, token=at)

        # 期望 4xx（400/422/404），绝不能 500 或连接错误
        if code == 500:
            record("malformed", desc, False, f"返回 500（应 4xx）：{txt[:80]}")
        elif code == -1:
            record("malformed", desc, False, f"连接异常：{txt[:80]}")
        elif 400 <= code < 500:
            record("malformed", desc, True, f"{code}")
        else:
            warn("malformed", desc, f"返回 {code}（预期 4xx，可能服务端宽松处理）")


# ============== 3. 鉴权边界 ==============

def test_auth_boundary():
    section("3. 鉴权边界（期望 401）")

    cases = [
        (None, "无 token"),
        ("", "空 token"),
        ("garbage", "垃圾 token"),
        ("Bearer xxx", "格式错误 token"),
        ("eyJ" + "a" * 200, "伪造长 token"),
        ("a.b.c", "伪 JWT 三段"),
    ]
    for tok, desc in cases:
        code, _, _ = raw_request("GET", "/admin/inventory?limit=1", token=tok)
        record("auth", desc, code == 401, f"code={code}")

    # 错误密码不能泄露用户是否存在（都应 401）
    code1, _, _ = raw_request("POST", "/admin/auth/login",
                               body={"username": "admin", "password": "wrong"})
    code2, _, _ = raw_request("POST", "/admin/auth/login",
                               body={"username": "nonexistent_user_xyz", "password": "wrong"})
    record("auth", "错误密码 / 不存在用户都返回 401", code1 == 401 and code2 == 401,
           f"existing={code1} nonexistent={code2}")


# ============== 4. 端侧事件健壮性 ==============

def test_device_events(at):
    section("4. 端侧事件健壮性")

    # 缺 device_id 应自动填默认值并成功
    code, _, txt = raw_request("POST", "/admin/events/heartbeat",
                                body={"event": "stability_test"}, token=at)
    record("device", "心跳缺 device_id 自动兜底", code == 200,
           f"code={code} device={json.loads(txt).get('device_id') if code == 200 else '?'}")

    # 空 data 数组应该被接受（返回空列表）
    code, _, txt = raw_request("POST", "/admin/events/item",
                                body={"timestamp": int(time.time()*1000),
                                      "event_type": "ITEM_IN", "data": []}, token=at)
    record("device", "空 data 数组不崩", code == 200, f"code={code}")

    # ITEM_OUT 一个不存在的类别（找不到匹配）应优雅处理，不报错
    code, _, txt = raw_request("POST", "/admin/events/item",
                                body={"timestamp": int(time.time()*1000),
                                      "event_type": "ITEM_OUT",
                                      "data": [{"local_track_id": 99999,
                                                "category": "不存在的类别_xyz",
                                                "confidence": 0.9,
                                                "bbox": [0, 0, 10, 10]}]}, token=at)
    record("device", "ITEM_OUT 无匹配项优雅处理", code == 200, f"code={code}")

    # 超大 bbox 值
    code, _, _ = raw_request("POST", "/admin/events/item",
                              body={"timestamp": int(time.time()*1000),
                                    "event_type": "ITEM_MOVED",
                                    "data": [{"local_track_id": 1,
                                              "category": "test",
                                              "confidence": 0.9,
                                              "bbox": [999999, 999999, 999999, 999999]}]},
                              token=at)
    record("device", "超大 bbox 值不崩", code in (200, 400, 422), f"code={code}")


# ============== 5. 顺序去重压力 ==============

def test_dedup_pressure(at):
    section("5. 重复入库去重压力")

    # 同一个手动库存项狂建 10 次（无图片 → 不触发图像去重，但验证不会 5xx）
    cat = f"压测去重-{int(time.time())}"
    created = 0
    errors = 0
    ids = []
    for i in range(10):
        code, _, txt = raw_request("POST", "/admin/inventory",
                                    body={"category": cat, "status": "IN_STOCK",
                                          "remain_ratio": 1.0,
                                          "agent_metadata": {"confidence": 0.9}},
                                    token=at)
        if code == 200:
            created += 1
            ids.append(json.loads(txt)["id"])
        elif code == 409:
            pass  # 去重命中也算正常
        else:
            errors += 1

    record("dedup", "重复建库存无 5xx", errors == 0, f"created={created} errors={errors}")

    # 清理
    for iid in ids:
        raw_request("DELETE", f"/admin/inventory/{iid}", token=at)


# ============== 6. WebSocket 抖动 ==============

async def test_ws_churn(at):
    section("6. WebSocket 快速连接 / 断开（连接泄漏检查）")

    url = WS_INV + "?token=" + urllib.parse.quote(at)
    ok_count = 0
    fail_count = 0
    N = 30
    for i in range(N):
        try:
            async with websockets.connect(url, open_timeout=8) as ws:
                msg = await asyncio.wait_for(ws.recv(), timeout=5)
                ev = json.loads(msg)
                if ev.get("type") == "ready":
                    ok_count += 1
            # with 块退出即断开
        except Exception:
            fail_count += 1
        await asyncio.sleep(0.05)

    record("ws", f"快速连断 {N} 次", fail_count == 0,
           f"成功={ok_count} 失败={fail_count}")

    # 抖动后服务仍能正常响应 HTTP
    code, _, _ = raw_request("GET", "/admin/inventory?limit=1", token=at)
    record("ws", "抖动后 HTTP 仍正常", code == 200, f"code={code}")


# ============== 7. 持续负载（错误率随时间）==============

def test_sustained_load(at, ut):
    section("7. 持续负载（20 秒，检查错误率是否随时间漂移）")

    DURATION = 20
    WORKERS = 8
    endpoints = [
        ("/admin/inventory?limit=10", at),
        ("/admin/stats/perf?hours=24", at),
        ("/user/stats/cooking?days=90", ut),
        ("/admin/devices", at),
    ]

    stop_at = time.time() + DURATION
    counters = {"total": 0, "errors": 0}
    # 分两个窗口对比错误率：前半段 vs 后半段
    window = {"first_total": 0, "first_err": 0, "second_total": 0, "second_err": 0}
    half = time.time() + DURATION / 2
    lock = __import__("threading").Lock()

    def worker():
        idx = 0
        while time.time() < stop_at:
            ep, tok = endpoints[idx % len(endpoints)]
            idx += 1
            code, _, _ = raw_request("GET", ep, token=tok, timeout=15)
            is_err = code != 200
            with lock:
                counters["total"] += 1
                if is_err:
                    counters["errors"] += 1
                if time.time() < half:
                    window["first_total"] += 1
                    if is_err:
                        window["first_err"] += 1
                else:
                    window["second_total"] += 1
                    if is_err:
                        window["second_err"] += 1

    threads = [__import__("threading").Thread(target=worker) for _ in range(WORKERS)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    err_rate = counters["errors"] / max(1, counters["total"]) * 100
    first_rate = window["first_err"] / max(1, window["first_total"]) * 100
    second_rate = window["second_err"] / max(1, window["second_total"]) * 100

    record("sustained", "总错误率 < 1%", err_rate < 1.0,
           f"{counters['total']} 请求 错误率={err_rate:.2f}%")
    # 后半段错误率不应明显高于前半段（泄漏/退化迹象）
    drift_ok = second_rate <= first_rate + 2.0
    record("sustained", "错误率无明显时间漂移", drift_ok,
           f"前半={first_rate:.2f}% 后半={second_rate:.2f}%")
    qps = counters["total"] / DURATION
    print(f"  ℹ️  持续吞吐 ≈ {qps:.0f} req/s")


# ============== 主流程 ==============

def main():
    started = time.time()
    print("\n" + "="*64)
    print("  智能冰箱后端 - 稳定性 / 健壮性测试")
    print(f"  目标: {BASE}")
    print(f"  时间: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*64)

    at, ut = login()
    print(f"  admin token = {at[:20]}...  user token = {(ut or 'N/A')[:20]}...")

    test_concurrency(at, ut)
    test_malformed(at)
    test_auth_boundary()
    test_device_events(at)
    test_dedup_pressure(at)
    asyncio.run(test_ws_churn(at))
    test_sustained_load(at, ut)

    # 汇总
    dur = time.time() - started
    total = len(results)
    passed = sum(1 for *_, s, _ in [(r[0], r[1], r[2], r[3]) for r in results] if s == "PASS")
    passed = sum(1 for r in results if r[2] == "PASS")
    failed = sum(1 for r in results if r[2] == "FAIL")
    warned = sum(1 for r in results if r[2] == "WARN")

    print("\n" + "="*64)
    print(f"  汇总（{dur:.1f}s）")
    print("="*64)
    print(f"  总计 {total}  | ✅ PASS {passed}  | ❌ FAIL {failed}  | ⚠️ WARN {warned}")

    if failed:
        print("\n  失败项：")
        for m, n, s, d in results:
            if s == "FAIL":
                print(f"    [{m}] {n} — {d}")
    if warned:
        print("\n  警告项（非致命，建议关注）：")
        for m, n, s, d in results:
            if s == "WARN":
                print(f"    [{m}] {n} — {d}")

    print()
    sys.exit(0 if failed == 0 else 1)


if __name__ == "__main__":
    main()
