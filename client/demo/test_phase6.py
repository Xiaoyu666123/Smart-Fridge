"""验证：Sankey 生命周期、浪费日历、性能热图、AI 解释 trace。"""
import json
import sys
import urllib.request

BASE = "http://127.0.0.1:8000/api/v1"


def http(method, path, body=None, token=None, timeout=120):
    url = BASE + path
    data = json.dumps(body, ensure_ascii=False).encode("utf-8") if body is not None else None
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        text = resp.read().decode("utf-8")
        return json.loads(text) if text else {}


t = http("POST", "/admin/auth/login",
          body={"username": "admin", "password": "admin123"})["token"]
print("[OK] login")

# 1) Sankey
print("\n========== 1) 生命周期 Sankey ==========")
res = http("GET", "/admin/stats/lifecycle?days=30&top_n=8", token=t)
print(f"  total={res['total']} | nodes={len(res['nodes'])} | links={len(res['links'])}")
print(f"  sources={res['categories']['sources']}")
print(f"  states={res['categories']['states']}")
assert "nodes" in res and "links" in res
print("  [PASS]")

# 2) 浪费日历
print("\n========== 2) 浪费日历 ==========")
res = http("GET", "/admin/stats/waste-calendar?days=180", token=t)
print(f"  window={res['window_days']} | series_len={len(res['series'])}")
print(f"  total_value=¥{res['total_value']} | days_with_waste={res['days_with_waste']}")
assert isinstance(res["series"], list)
assert len(res["series"]) <= 181
print("  [PASS]")

# 3) 性能热图
print("\n========== 3) 性能周-小时热图 ==========")
res = http("GET", "/admin/stats/perf?hours=168", token=t)
hm = res.get("weekday_hour_heatmap", [])
print(f"  total_steps={res['total_steps']} | heatmap_cells={len(hm)}")
assert len(hm) == 7 * 24
nonzero = sum(1 for _, _, v in hm if v > 0)
print(f"  非零格子: {nonzero}")
print("  [PASS]")

# 4) AI 解释 trace（找一条最近的 trace 试）
print("\n========== 4) AI 解释 trace ==========")
traces = http("GET", "/admin/traces?limit=5", token=t)
if not traces:
    print("  [skip] 没有 trace")
else:
    tr_id = traces[0]["trace_id"]
    print(f"  解释 trace_id={tr_id} agent_type={traces[0]['agent_type']}")
    r = http("GET", f"/admin/traces/{tr_id}/explain", token=t, timeout=120)
    print(f"  step_count={r['step_count']}")
    print(f"  explanation: {r['explanation'][:200]}")
    assert len(r["explanation"]) > 20
    print("  [PASS]")

print("\n全部通过 ✅")
