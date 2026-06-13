"""验证：单价配置 + 浪费金额 + 营养报告 + 审计日志。"""
import json
import sys
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
    return http("POST", "/admin/auth/login", body={"username": "admin", "password": "admin123"})["token"]


def user_login():
    return http("POST", "/user/auth/login", body={"username": "xiaoyu", "password": "test123"})["token"]


def main():
    at = admin_login()
    ut = user_login()
    print("[OK] login")

    # 1) 单价配置
    print("\n========== 1) 单价配置 ==========")
    thresholds = http("GET", "/admin/category-thresholds", token=at)
    print(f"  总品类: {len(thresholds)}")
    if not thresholds:
        print("  [skip] 没有 category_thresholds 记录")
        return
    target = thresholds[0]
    print(f"  目标品类: {target['category']} 当前单价: {target.get('unit_price')}")
    res = http("PUT", f"/admin/category-thresholds/{target['id']}",
                body={"unit_price": 8.5}, token=at)
    print(f"  改后单价: {res['unit_price']}")
    assert float(res["unit_price"]) == 8.5
    print("  [PASS] 单价配置 OK")

    # 2) 浪费分析含金额
    print("\n========== 2) 浪费分析金额估算 ==========")
    waste = http("GET", "/admin/stats/waste?days=30", token=at)
    print(f"  浪费金额: ¥{waste.get('wasted_value')}")
    print(f"  消耗金额: ¥{waste.get('consumed_value')}")
    print(f"  单价覆盖: {waste.get('priced_categories')} / {waste.get('total_categories_seen')}")
    assert "wasted_value" in waste
    print("  [PASS] 浪费金额估算 OK")

    # 3) 审计日志（CATEGORY_CONFIG_UPDATE 应该已经被记录）
    print("\n========== 3) 审计日志 ==========")
    logs = http("GET", "/admin/logs?source=admin&limit=20", token=at)
    cat_logs = [l for l in logs if l.get("event_type") == "CATEGORY_CONFIG_UPDATE"]
    print(f"  审计记录: {len(logs)} 条 | 其中品类配置: {len(cat_logs)}")
    if cat_logs:
        latest = cat_logs[0]
        print(f"  最新一条: {latest.get('detail', {}).get('category')} | "
              f"old_price={latest.get('detail', {}).get('old_unit_price')} → "
              f"new_price={latest.get('detail', {}).get('new_unit_price')}")
    assert len(cat_logs) >= 1
    print("  [PASS] 审计日志 OK")

    # 4) 营养报告（用户端）
    print("\n========== 4) 健康饮食报告 ==========")
    nutri = http("GET", "/user/stats/nutrition?days=30", token=ut)
    print(f"  窗口: {nutri['window_days']} 天")
    print(f"  入库总数: {nutri['total']}")
    print(f"  分布:")
    for d in nutri["distribution"][:5]:
        print(f"    {d['emoji']} {d['label']}: {d['count']}")
    h = nutri["health_overall"]
    print(f"  评分: {h['score']} ({h['level']})")
    print(f"  建议:")
    for tip in h["tips"][:3]:
        print(f"    - {tip}")
    print(f"  蔬果占比 {h['veg_fruit_ratio']*100:.0f}% | 肉类 {h['meat_ratio']*100:.0f}% | 零食 {h['snack_ratio']*100:.0f}%")
    assert 0 <= h["score"] <= 100
    print("  [PASS] 营养报告 OK")

    print("\n全部通过 ✅")


if __name__ == "__main__":
    main()
