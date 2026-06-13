"""一次性测试所有主要 API。

按模块组织：每个测试输出 PASS / FAIL / SKIP，最后一份汇总。
不依赖外部库，只用 stdlib + websockets。
"""
import asyncio
import io
import json
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from contextlib import contextmanager

import websockets

BASE = "http://127.0.0.1:8000/api/v1"
WS_INV = "ws://127.0.0.1:8000/api/v1/admin/ws/inventory"
WS_NOTIF = "ws://127.0.0.1:8000/api/v1/user/ws/notifications"

results: list[tuple[str, str, str]] = []   # (module, name, status)


def http(method, path, body=None, token=None, timeout=120, base=BASE, extra_headers=None):
    url = base + path
    data = json.dumps(body, ensure_ascii=False).encode("utf-8") if body is not None else None
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    if extra_headers:
        headers.update(extra_headers)
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        text = resp.read().decode("utf-8")
        ct = resp.headers.get("Content-Type", "")
        if "json" in ct or text.startswith("[") or text.startswith("{"):
            return json.loads(text) if text else {}, resp
        return text, resp


@contextmanager
def section(name):
    print(f"\n{'='*60}")
    print(f"  {name}")
    print('='*60)
    yield


def record(module, name, ok, detail=""):
    status = "PASS" if ok else "FAIL"
    results.append((module, name, status))
    flag = "✅" if ok else "❌"
    print(f"  {flag} {name}" + (f" — {detail}" if detail else ""))


def skip(module, name, reason=""):
    results.append((module, name, "SKIP"))
    print(f"  ⊘ SKIP {name}" + (f" — {reason}" if reason else ""))


# ============== 1. 认证 ==============

def test_auth():
    with section("1. 认证"):
        # admin login
        try:
            r, _ = http("POST", "/admin/auth/login",
                         body={"username": "admin", "password": "admin123"})
            at = r["token"]
            record("auth", "admin login", True, f"token={at[:18]}...")
        except Exception as e:
            record("auth", "admin login", False, str(e))
            return None, None

        # user login
        try:
            r, _ = http("POST", "/user/auth/login",
                         body={"username": "xiaoyu", "password": "test123"})
            ut = r["token"]
            record("auth", "user login", True, f"token={ut[:18]}...")
        except Exception as e:
            record("auth", "user login", False, str(e))
            return at, None

        # cross-token rejected
        try:
            try:
                http("GET", "/admin/inventory?limit=1", token=ut)
                record("auth", "user token 不能访问 admin", False, "竟然成功了")
            except urllib.error.HTTPError as e:
                if e.code == 401:
                    record("auth", "user token 不能访问 admin", True)
                else:
                    record("auth", "user token 不能访问 admin", False, f"code={e.code}")
        except Exception as e:
            record("auth", "user token 不能访问 admin", False, str(e))

        # invalid token
        try:
            try:
                http("GET", "/admin/inventory?limit=1", token="invalid_token_xxx")
                record("auth", "非法 token 拒绝", False)
            except urllib.error.HTTPError as e:
                record("auth", "非法 token 拒绝", e.code == 401)
        except Exception as e:
            record("auth", "非法 token 拒绝", False, str(e))

        # admin /auth/me
        try:
            r, _ = http("GET", "/admin/auth/me", token=at)
            record("auth", "admin /auth/me", "username" in r, f"username={r.get('username')}")
        except Exception as e:
            record("auth", "admin /auth/me", False, str(e))

        return at, ut


# ============== 2. 库存 CRUD ==============

def test_inventory(at):
    with section("2. 库存 CRUD"):
        created_id = None

        # list
        try:
            r, _ = http("GET", "/admin/inventory?limit=5", token=at)
            record("inv", "列表查询", isinstance(r, list))
        except Exception as e:
            record("inv", "列表查询", False, str(e))

        # 搜索 + 临期
        try:
            r, _ = http("GET", "/admin/inventory?q=apple&limit=5", token=at)
            record("inv", "模糊搜索 q=apple", isinstance(r, list))
        except Exception as e:
            record("inv", "模糊搜索 q=apple", False, str(e))

        try:
            r, _ = http("GET", "/admin/inventory?expiring_in_days=3", token=at)
            record("inv", "临期筛选 days=3", isinstance(r, list))
        except Exception as e:
            record("inv", "临期筛选 days=3", False, str(e))

        # X-Total-Count
        try:
            _, resp = http("GET", "/admin/inventory?limit=2&offset=0", token=at)
            total = resp.headers.get("X-Total-Count")
            record("inv", "X-Total-Count header", total is not None, f"total={total}")
        except Exception as e:
            record("inv", "X-Total-Count header", False, str(e))

        # 分类
        try:
            r, _ = http("GET", "/admin/inventory/categories", token=at)
            record("inv", "分类列表", isinstance(r, list))
        except Exception as e:
            record("inv", "分类列表", False, str(e))

        # 创建
        try:
            r, _ = http("POST", "/admin/inventory",
                         body={
                             "category": f"全测试-{int(time.time()) % 100000}",
                             "status": "IN_STOCK",
                             "remain_ratio": 1.0,
                             "agent_metadata": {"confidence": 0.95},
                         },
                         token=at)
            created_id = r["id"]
            record("inv", "创建", True, f"id={created_id[:8]}")
        except Exception as e:
            record("inv", "创建", False, str(e))

        # 更新
        if created_id:
            try:
                r, _ = http("PUT", f"/admin/inventory/{created_id}",
                             body={"remain_ratio": 0.5}, token=at)
                record("inv", "更新", abs(r["remain_ratio"] - 0.5) < 0.01)
            except Exception as e:
                record("inv", "更新", False, str(e))

            # 详情
            try:
                r, _ = http("GET", f"/admin/inventory/{created_id}", token=at)
                record("inv", "详情查询", r["id"] == created_id)
            except Exception as e:
                record("inv", "详情查询", False, str(e))

            # 删除
            try:
                r, _ = http("DELETE", f"/admin/inventory/{created_id}", token=at)
                record("inv", "删除", "detail" in r)
            except Exception as e:
                record("inv", "删除", False, str(e))


# ============== 3. 端侧事件 ==============

def test_events(at):
    with section("3. 端侧事件"):
        dev = f"luckfox-test-{int(time.time()) % 10000}"

        # 心跳 + 自动注册
        try:
            r, _ = http("POST", "/admin/events/heartbeat",
                         body={"device_id": dev, "event": "startup"}, token=at)
            record("events", "心跳 + 自动注册", r.get("auto_registered") is True)
        except Exception as e:
            record("events", "心跳 + 自动注册", False, str(e))

        # ITEM_IN
        try:
            r, _ = http("POST", "/admin/events/item",
                         body={
                             "device_id": dev,
                             "timestamp": int(time.time() * 1000),
                             "event_type": "ITEM_IN",
                             "data": [{
                                 "local_track_id": 1,
                                 "category": f"事件测试-{int(time.time()) % 1000}",
                                 "confidence": 0.92,
                                 "bbox": [10, 20, 30, 40],
                             }],
                         }, token=at)
            assert isinstance(r, list) and len(r) > 0
            inv_id = r[0]["id"]
            record("events", "ITEM_IN 入库", True, f"id={inv_id[:8]}")
        except Exception as e:
            record("events", "ITEM_IN 入库", False, str(e))
            inv_id = None

        # ITEM_OUT
        if inv_id:
            try:
                r, _ = http("POST", "/admin/events/item",
                             body={
                                 "device_id": dev,
                                 "timestamp": int(time.time() * 1000),
                                 "event_type": "ITEM_OUT",
                                 "data": [{
                                     "local_track_id": 1,
                                     "category": "事件测试",
                                     "confidence": 0.91,
                                     "bbox": [10, 20, 30, 40],
                                 }],
                             }, token=at)
                record("events", "ITEM_OUT 取出", isinstance(r, list))
            except Exception as e:
                record("events", "ITEM_OUT 取出", False, str(e))

            # 清理
            try:
                http("DELETE", f"/admin/inventory/{inv_id}", token=at)
                http("DELETE", f"/admin/devices/{dev}", token=at)
            except Exception:
                pass


# ============== 4. 设备管理 ==============

def test_devices(at):
    with section("4. 设备管理"):
        try:
            r, _ = http("GET", "/admin/devices", token=at)
            record("device", "列表", isinstance(r, list), f"count={len(r)}")
        except Exception as e:
            record("device", "列表", False, str(e))

        # 创建临时设备测各操作
        dev = f"test-dev-{int(time.time()) % 10000}"
        try:
            http("POST", "/admin/events/heartbeat",
                  body={"device_id": dev}, token=at)
        except Exception:
            pass

        # 编辑
        try:
            r, _ = http("PUT", f"/admin/devices/{dev}",
                         body={"name": "测试设备", "location": "测试机房"}, token=at)
            record("device", "编辑", r.get("name") == "测试设备")
        except Exception as e:
            record("device", "编辑", False, str(e))

        # 心跳曲线
        try:
            r, _ = http("GET", f"/admin/devices/{dev}/heartbeats?hours=1&bucket=10", token=at)
            record("device", "心跳曲线", "series" in r)
        except Exception as e:
            record("device", "心跳曲线", False, str(e))

        # 删除 + 恢复
        try:
            http("DELETE", f"/admin/devices/{dev}", token=at)
            r, _ = http("POST", "/admin/devices/restore",
                         body={"device_id": dev, "name": "恢复后"}, token=at)
            record("device", "删除 + 恢复", r["device_id"] == dev)
        except Exception as e:
            record("device", "删除 + 恢复", False, str(e))

        # 收尾
        try:
            http("DELETE", f"/admin/devices/{dev}", token=at)
        except Exception:
            pass


# ============== 5. Trace + AI 解释 ==============

def test_trace(at):
    with section("5. 工具链 Trace + AI 解释"):
        # 列表
        try:
            traces, _ = http("GET", "/admin/traces?limit=3", token=at)
            record("trace", "列表", isinstance(traces, list))
        except Exception as e:
            record("trace", "列表", False, str(e))
            return

        if not traces:
            skip("trace", "详情", "没有 trace 记录")
            skip("trace", "AI 解释", "没有 trace 记录")
            return

        tid = traces[0]["trace_id"]
        # 详情
        try:
            r, _ = http("GET", f"/admin/traces/{tid}", token=at)
            record("trace", "详情", "steps" in r, f"steps={len(r.get('steps', []))}")
        except Exception as e:
            record("trace", "详情", False, str(e))

        # AI 解释
        try:
            r, _ = http("GET", f"/admin/traces/{tid}/explain", token=at, timeout=120)
            ok = len(r.get("explanation", "")) > 30
            record("trace", "AI 解释 trace", ok, f"len={len(r.get('explanation', ''))}")
        except Exception as e:
            record("trace", "AI 解释 trace", False, str(e))


# ============== 6. 统计聚合 ==============

def test_stats(at):
    with section("6. 数据统计"):
        for path, name in [
            ("/admin/stats/waste?days=30", "浪费分析"),
            ("/admin/stats/waste-calendar?days=180", "浪费日历"),
            ("/admin/stats/lifecycle?days=30", "生命周期 Sankey"),
            ("/admin/stats/perf?hours=24", "性能监控"),
            ("/admin/stats/nutrition?days=30", "营养报告"),
            ("/admin/usage/summary?days=7", "用量汇总"),
            ("/admin/usage/records?limit=10", "用量明细"),
        ]:
            try:
                r, _ = http("GET", path, token=at)
                record("stats", name, isinstance(r, (dict, list)))
            except Exception as e:
                record("stats", name, False, str(e))


# ============== 7. 视觉辅助识别配置 ==============

def test_vac(at):
    with section("7. 视觉辅助识别配置"):
        try:
            r, _ = http("GET", "/admin/agent/vision-assist-config", token=at)
            old_lo, old_hi = r["lower"], r["upper"]
            record("vac", "查询配置", True, f"[{old_lo}, {old_hi}]")
        except Exception as e:
            record("vac", "查询配置", False, str(e))
            return

        # 更新
        try:
            new_lo, new_hi = 0.25, 0.75
            r, _ = http("PUT", "/admin/agent/vision-assist-config",
                         body={"lower": new_lo, "upper": new_hi}, token=at)
            record("vac", "更新配置", abs(r["lower"] - new_lo) < 0.01)
        except Exception as e:
            record("vac", "更新配置", False, str(e))

        # 还原
        try:
            http("PUT", "/admin/agent/vision-assist-config",
                  body={"lower": old_lo, "upper": old_hi}, token=at)
        except Exception:
            pass

        # lower >= upper 应该 400
        try:
            try:
                http("PUT", "/admin/agent/vision-assist-config",
                      body={"lower": 0.8, "upper": 0.5}, token=at)
                record("vac", "拒绝 lower>=upper", False, "竟然成功了")
            except urllib.error.HTTPError as e:
                record("vac", "拒绝 lower>=upper", e.code in (400, 422))
        except Exception as e:
            record("vac", "拒绝 lower>=upper", False, str(e))


# ============== 8. 类别配置 + 单价 ==============

def test_categories(at):
    with section("8. 品类配置（单价）"):
        try:
            rows, _ = http("GET", "/admin/category-thresholds", token=at)
            record("cat", "列表", isinstance(rows, list), f"count={len(rows)}")
        except Exception as e:
            record("cat", "列表", False, str(e))
            return

        if not rows:
            skip("cat", "更新单价", "没有阈值记录")
            return

        target = rows[0]
        old_price = target.get("unit_price")
        try:
            r, _ = http("PUT", f"/admin/category-thresholds/{target['id']}",
                         body={"unit_price": 9.99}, token=at)
            record("cat", "更新单价", abs(float(r.get("unit_price") or 0) - 9.99) < 0.01)
        except Exception as e:
            record("cat", "更新单价", False, str(e))

        # 还原
        try:
            http("PUT", f"/admin/category-thresholds/{target['id']}",
                  body={"unit_price": old_price}, token=at)
        except Exception:
            pass


# ============== 9. 用户路由 ==============

def test_user_routes(ut):
    with section("9. 用户路由"):
        if not ut:
            skip("user", "all", "user token 缺失")
            return

        for path, name in [
            ("/user/inventory?limit=5", "库存查看"),
            ("/user/inventory/categories", "分类列表"),
            ("/user/agent/preferences", "偏好查询"),
            ("/user/agent/conversations", "对话历史"),
            ("/user/notifications/count", "通知数"),
            ("/user/notifications", "通知列表"),
            ("/user/recipes?limit=10", "食谱列表"),
            ("/user/category-thresholds", "类别阈值"),
            ("/user/stats/nutrition?days=7", "营养报告"),
            ("/user/environment", "环境信息"),
        ]:
            try:
                r, _ = http("GET", path, token=ut)
                ok = isinstance(r, (dict, list))
                record("user", name, ok)
            except Exception as e:
                record("user", name, False, str(e)[:80])


# ============== 10. 食谱评分笔记 + 打卡 ==============

def test_recipes(ut):
    with section("10. 食谱"):
        if not ut:
            skip("recipe", "all", "user token 缺失")
            return

        rid = None
        # 收藏
        try:
            r, _ = http("POST", "/user/recipes",
                         body={
                             "name": f"测试食谱-{int(time.time()) % 10000}",
                             "summary": "test_all",
                             "ingredients": [{"name": "番茄", "amount": "2 个"}],
                             "steps": ["切", "炒", "出锅"],
                         }, token=ut)
            rid = r["id"]
            record("recipe", "收藏", True, f"id={rid[:8]}")
        except Exception as e:
            record("recipe", "收藏", False, str(e))

        if rid:
            # 评分
            try:
                r, _ = http("PUT", f"/user/recipes/{rid}",
                             body={"rating": 4, "notes": "番茄要先翻炒到软"}, token=ut)
                record("recipe", "评分 + 笔记", r.get("rating") == 4 and "番茄" in (r.get("notes") or ""))
            except Exception as e:
                record("recipe", "评分 + 笔记", False, str(e))

            # rating 越界
            try:
                try:
                    http("PUT", f"/user/recipes/{rid}",
                          body={"rating": 10}, token=ut)
                    record("recipe", "拒绝越界 rating", False)
                except urllib.error.HTTPError as e:
                    record("recipe", "拒绝越界 rating", e.code in (400, 422))
            except Exception as e:
                record("recipe", "拒绝越界 rating", False, str(e))

            # 打卡（不带库存）
            try:
                r, _ = http("POST", f"/user/recipes/{rid}/cook",
                             body={"consumed_inventory_ids": []}, token=ut)
                record("recipe", "打卡", r["recipe"]["cooked_count"] >= 1)
            except Exception as e:
                record("recipe", "打卡", False, str(e))

            # 删除
            try:
                http("DELETE", f"/user/recipes/{rid}", token=ut)
                record("recipe", "删除", True)
            except Exception as e:
                record("recipe", "删除", False, str(e))


# ============== 11. 偏好 ==============

def test_preferences(ut):
    with section("11. 用户偏好"):
        if not ut:
            skip("pref", "all", "user token 缺失")
            return

        # 列表
        try:
            r, _ = http("GET", "/user/agent/preferences", token=ut)
            record("pref", "列表", isinstance(r, list))
        except Exception as e:
            record("pref", "列表", False, str(e))

        pid = None
        # 添加
        try:
            r, _ = http("POST", "/user/agent/preferences",
                         body={"preference_key": "taste", "preference_value": f"测试-{int(time.time())}"}, token=ut)
            pid = r["id"]
            record("pref", "添加", True)
        except Exception as e:
            record("pref", "添加", False, str(e))

        # 删除
        if pid:
            try:
                http("DELETE", f"/user/agent/preferences/{pid}", token=ut)
                record("pref", "删除", True)
            except Exception as e:
                record("pref", "删除", False, str(e))


# ============== 12. 导出 CSV ==============

def test_export(at):
    with section("12. 导出 CSV"):
        for path, name in [
            ("/admin/export/inventory", "导出库存"),
            ("/admin/export/events", "导出事件"),
            ("/admin/export/usage", "导出用量"),
        ]:
            try:
                _, resp = http("GET", path, token=at)
                cd = resp.headers.get("Content-Disposition", "")
                record("export", name, "filename" in cd, f"cd={cd[:50]}")
            except Exception as e:
                record("export", name, False, str(e))


# ============== 13. 标签缓冲 ==============

def test_pending_labels(at):
    with section("13. 标签缓冲"):
        try:
            r, _ = http("GET", "/admin/pending-labels?limit=5", token=at)
            record("label", "列表", isinstance(r, list))
        except Exception as e:
            record("label", "列表", False, str(e))


# ============== 14. AI 营养教练 ==============

def test_coach(ut):
    with section("14. AI 营养教练"):
        if not ut:
            skip("coach", "advice", "user token 缺失")
            return
        try:
            r, _ = http("GET", "/user/agent/coach?days=30", token=ut, timeout=120)
            ok = "advice" in r and "summary" in r["advice"]
            record("coach", "教练建议", ok)
        except Exception as e:
            record("coach", "教练建议", False, str(e))


# ============== 14b. AI 每日一句话 + 烹饪日历 ==============

def test_daily_and_calendar(ut):
    with section("14b. 每日一句话 + 烹饪日历"):
        if not ut:
            skip("daily", "tip", "user token 缺失")
            skip("calendar", "cooking", "user token 缺失")
            return
        # daily-tip：默认走缓存
        try:
            r, _ = http("GET", "/user/agent/daily-tip", token=ut, timeout=120)
            ok = isinstance(r, dict) and isinstance(r.get("tip"), str) and len(r["tip"]) > 0
            record("daily", "每日一句话", ok, f"tip长度={len(r.get('tip', ''))}")
        except Exception as e:
            record("daily", "每日一句话", False, str(e))

        # daily-tip：refresh=true 强制刷新
        try:
            r, _ = http("GET", "/user/agent/daily-tip?refresh=true", token=ut, timeout=120)
            ok = isinstance(r.get("tip"), str) and len(r["tip"]) > 0
            record("daily", "强制刷新", ok)
        except Exception as e:
            record("daily", "强制刷新", False, str(e))

        # 烹饪日历
        try:
            r, _ = http("GET", "/user/stats/cooking?days=180", token=ut)
            ok = (isinstance(r, dict)
                  and "series" in r
                  and isinstance(r["series"], list)
                  and "current_streak" in r
                  and "top_recipes" in r)
            record("calendar", "烹饪日历", ok,
                    f"series={len(r.get('series', []))}天 streak={r.get('current_streak')}")
        except Exception as e:
            record("calendar", "烹饪日历", False, str(e))

        # 成就墙
        try:
            r, _ = http("GET", "/user/stats/achievements", token=ut)
            ok = (isinstance(r, dict)
                  and isinstance(r.get("achievements"), list)
                  and len(r["achievements"]) > 0
                  and "profile" in r
                  and "level_idx" in r["profile"]
                  and isinstance(r.get("consume_trend"), list))
            unlocked = sum(1 for a in r.get("achievements", []) if a.get("unlocked"))
            record("ach", "成就墙", ok,
                    f"badges={len(r.get('achievements', []))} unlocked={unlocked}")
        except Exception as e:
            record("ach", "成就墙", False, str(e))

        # 自然语言库存查询
        try:
            r, _ = http("POST", "/user/agent/inventory-query",
                         body={"question": "冰箱里现在一共有多少件食材？"}, token=ut, timeout=90)
            ok = (isinstance(r, dict)
                  and isinstance(r.get("answer"), str)
                  and len(r["answer"]) > 0
                  and "in_stock_count" in r
                  and isinstance(r.get("matched"), list))
            record("invq", "库存问答", ok, f"answer长度={len(r.get('answer', ''))}")
        except Exception as e:
            record("invq", "库存问答", False, str(e))

        # 库存查询缺 question 应 400
        try:
            try:
                http("POST", "/user/agent/inventory-query", body={}, token=ut)
                record("invq", "拒绝空问题", False, "竟然成功了")
            except urllib.error.HTTPError as e:
                record("invq", "拒绝空问题", e.code in (400, 422))
        except Exception as e:
            record("invq", "拒绝空问题", False, str(e))

        # 购物清单：增 → 查 → 勾选 → 建议 → 清除已购 → 删
        try:
            r, _ = http("POST", "/user/shopping", body={"name": f"测试购物-{int(time.time()) % 10000}", "qty": 2}, token=ut)
            sid = r["id"]
            ok_add = r["qty"] == 2 and r["source"] == "manual"
            r2, _ = http("GET", "/user/shopping", token=ut)
            ok_list = isinstance(r2.get("items"), list) and "total" in r2
            r3, _ = http("PUT", f"/user/shopping/{sid}", body={"checked": True}, token=ut)
            ok_check = r3["checked"] is True
            http("POST", "/user/shopping/suggest", token=ut)             # 不强求有建议
            http("POST", "/user/shopping/clear-checked", token=ut)       # 清掉刚勾的
            record("shop", "购物清单增改查", ok_add and ok_list and ok_check)
        except Exception as e:
            record("shop", "购物清单增改查", False, str(e))

        # 购物清单空名 400
        try:
            try:
                http("POST", "/user/shopping", body={"name": ""}, token=ut)
                record("shop", "拒绝空名", False, "竟然成功了")
            except urllib.error.HTTPError as e:
                record("shop", "拒绝空名", e.code in (400, 422))
        except Exception as e:
            record("shop", "拒绝空名", False, str(e))


# ============== 15. WebSocket ==============

async def test_ws(at, ut):
    print(f"\n{'='*60}")
    print("  15. WebSocket")
    print('='*60)

    # admin ws/inventory
    try:
        url = WS_INV + "?token=" + urllib.parse.quote(at)
        async with websockets.connect(url, open_timeout=10) as ws:
            msg = await asyncio.wait_for(ws.recv(), timeout=5)
            ev = json.loads(msg)
            record("ws", "admin /ws/inventory connect", ev.get("type") == "ready")
    except Exception as e:
        record("ws", "admin /ws/inventory connect", False, str(e))

    # admin ws 鉴权拒绝
    try:
        url = WS_INV + "?token=invalid"
        try:
            async with websockets.connect(url, open_timeout=5) as ws:
                await asyncio.wait_for(ws.recv(), timeout=3)
                record("ws", "admin ws 拒绝非法 token", False, "竟然连上了")
        except (websockets.exceptions.InvalidStatusCode, websockets.ConnectionClosedError, asyncio.TimeoutError, Exception):
            record("ws", "admin ws 拒绝非法 token", True)
    except Exception as e:
        record("ws", "admin ws 拒绝非法 token", False, str(e))

    # user ws/notifications
    if ut:
        try:
            url = WS_NOTIF + "?token=" + urllib.parse.quote(ut)
            async with websockets.connect(url, open_timeout=10) as ws:
                msg = await asyncio.wait_for(ws.recv(), timeout=5)
                ev = json.loads(msg)
                record("ws", "user /ws/notifications connect", ev.get("type") == "ready")
        except Exception as e:
            record("ws", "user /ws/notifications connect", False, str(e))

    # broadcast：建一条 inventory，看 ws 收到推送
    try:
        url = WS_INV + "?token=" + urllib.parse.quote(at)
        async with websockets.connect(url, open_timeout=10) as ws:
            await asyncio.wait_for(ws.recv(), timeout=5)   # ready

            # 起一个并行任务：等下一条事件
            recv_task = asyncio.create_task(ws.recv())
            await asyncio.sleep(0.2)

            # 同步发起 HTTP 创建
            inv_data = {
                "category": f"广播测试-{int(time.time()) % 1000}",
                "status": "IN_STOCK",
                "remain_ratio": 1.0,
                "agent_metadata": {"confidence": 0.95},
            }
            req = urllib.request.Request(
                BASE + "/admin/inventory",
                data=json.dumps(inv_data, ensure_ascii=False).encode("utf-8"),
                headers={
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {at}",
                },
                method="POST",
            )
            inv_resp = json.loads(urllib.request.urlopen(req, timeout=30).read())

            # 等 ws 推送
            msg = await asyncio.wait_for(recv_task, timeout=8)
            ev = json.loads(msg)
            record("ws", "broadcast inventory.created",
                    ev.get("type") == "inventory.created" and ev.get("data", {}).get("id") == inv_resp["id"])

            # 清理
            try:
                req2 = urllib.request.Request(
                    BASE + f"/admin/inventory/{inv_resp['id']}",
                    headers={"Authorization": f"Bearer {at}"},
                    method="DELETE",
                )
                urllib.request.urlopen(req2, timeout=10)
            except Exception:
                pass
    except Exception as e:
        record("ws", "broadcast inventory.created", False, str(e))


# ============== 主流程 ==============

def main():
    started = time.time()
    print("\n" + "="*60)
    print("  智能冰箱系统 - 全功能测试")
    print(f"  目标: {BASE}")
    print(f"  时间: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*60)

    at, ut = test_auth()
    if not at:
        print("\n❌ admin 登录失败，无法继续")
        return

    test_inventory(at)
    test_events(at)
    test_devices(at)
    test_trace(at)
    test_stats(at)
    test_vac(at)
    test_categories(at)
    test_user_routes(ut)
    test_recipes(ut)
    test_preferences(ut)
    test_export(at)
    test_pending_labels(at)
    test_coach(ut)
    test_daily_and_calendar(ut)

    asyncio.run(test_ws(at, ut))

    # 汇总
    duration = time.time() - started
    total = len(results)
    passed = sum(1 for _, _, s in results if s == "PASS")
    failed = sum(1 for _, _, s in results if s == "FAIL")
    skipped = sum(1 for _, _, s in results if s == "SKIP")

    print("\n" + "="*60)
    print(f"  汇总（{duration:.1f}s）")
    print("="*60)
    print(f"  总计: {total}  | ✅ PASS: {passed}  | ❌ FAIL: {failed}  | ⊘ SKIP: {skipped}")

    if failed > 0:
        print("\n  失败项：")
        for m, n, s in results:
            if s == "FAIL":
                print(f"    [{m}] {n}")

    # 按模块统计
    modules: dict = {}
    for m, n, s in results:
        modules.setdefault(m, [0, 0, 0])
        idx = {"PASS": 0, "FAIL": 1, "SKIP": 2}[s]
        modules[m][idx] += 1
    print("\n  分模块：")
    for m, (p, f, sk) in sorted(modules.items()):
        line = f"    [{m:8}] PASS={p} FAIL={f} SKIP={sk}"
        if f > 0:
            line += "  ⚠️"
        print(line)

    sys.exit(0 if failed == 0 else 1)


if __name__ == "__main__":
    main()
