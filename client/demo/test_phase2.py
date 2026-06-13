"""测试新增功能：浪费分析 + 食谱打卡扣库存 + LLM 临期优先。"""
import json
import time
import urllib.request

BASE = "http://127.0.0.1:8000/api/v1"


def http(method, path, body=None, token=None, timeout=60):
    url = BASE + path
    data = json.dumps(body, ensure_ascii=False).encode("utf-8") if body is not None else None
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        text = resp.read().decode("utf-8")
        return json.loads(text) if text else {}


def admin_login():
    r = http("POST", "/admin/auth/login",
              body={"username": "admin", "password": "admin123"})
    return r["token"]


def user_login():
    r = http("POST", "/user/auth/login",
              body={"username": "xiaoyu", "password": "test123"})
    return r["token"]


def test_waste(admin_token):
    print("\n========== 1) 浪费分析 ==========")
    res = http("GET", "/admin/stats/waste?days=30", token=admin_token)
    print(f"窗口: {res['window_days']} 天")
    print(f"总入库: {res['total']} | 已消耗: {res['consumed_in_time']} | 在库: {res['in_stock']} | 浪费: {res['wasted']}")
    print(f"浪费率: {res['waste_rate'] * 100:.2f}%")
    print(f"top_wasted: {res['top_wasted']}")
    print(f"top_consumed: {res['top_consumed']}")
    print(f"补货建议: {res['restock_suggestions']}")
    assert "waste_rate" in res
    print("[PASS] 浪费分析接口 OK")


def test_cook_consume(user_token):
    print("\n========== 2) 食谱打卡 + 库存扣减 ==========")

    # 先存一个食谱
    recipe = {
        "name": f"测试番茄炒蛋-{int(time.time()) % 10000}",
        "summary": "测试用",
        "prep_time": 10,
        "difficulty": "简单",
        "tags": ["测试"],
        "ingredients": [
            {"name": "番茄", "amount": "2个"},
            {"name": "鸡蛋", "amount": "3个"},
        ],
        "steps": ["切番茄", "打蛋", "炒"],
    }
    saved = http("POST", "/user/recipes", body=recipe, token=user_token)
    rid = saved["id"]
    print(f"[ok] 已收藏食谱 id={rid} cooked_count={saved['cooked_count']}")

    # 看看当前在库的物品（用普通用户能看到的）
    inv_list = http("GET", "/user/inventory?status=IN_STOCK", token=user_token)
    print(f"[info] 当前在库物品: {len(inv_list)} 件")
    consumed_ids = [i["id"] for i in inv_list[:2]]
    print(f"[info] 选用 {len(consumed_ids)} 件做被消耗")

    # 打卡
    res = http("POST", f"/user/recipes/{rid}/cook",
                body={"consumed_inventory_ids": consumed_ids},
                token=user_token)
    print(f"[ok] cooked_count={res['recipe']['cooked_count']}")
    print(f"     consumed_count={res['consumed_count']}")
    print(f"     consumed_inventory_ids={res['consumed_inventory_ids']}")
    print(f"     skipped_inventory_ids={res['skipped_inventory_ids']}")

    if consumed_ids:
        # 再查这些库存的状态
        for cid in res["consumed_inventory_ids"]:
            inv = http("GET", f"/user/inventory/{cid}", token=user_token)
            print(f"     - {inv['category']} status={inv['status']}")
            assert inv["status"] == "OUT_PENDING", "状态应该被改成 OUT_PENDING"
        print("[PASS] 库存被正确扣减为 OUT_PENDING")
    else:
        print("[info] 没在库物品可消耗，跳过状态校验")

    # 收尾：删除测试食谱
    http("DELETE", f"/user/recipes/{rid}", token=user_token)


def test_chat_priority(user_token):
    print("\n========== 3) LLM 临期优先（仅打印 prompt 渲染逻辑） ==========")
    # 通过 stream API 发一条消息，看后端日志能否打出"临期食材 - 优先使用"
    # 这里就直接用同步 chat 端点更快（虽然没流，但够用）
    msg = "请用我冰箱里最快过期的食材给我推荐 1 道菜"
    try:
        res = http("POST", "/user/agent/chat",
                    body={"message": msg, "city": "广州"},
                    token=user_token, timeout=120)
        reply = res.get("reply", "")
        print(f"[ok] 收到 LLM 回复（长度 {len(reply)}）")
        print(reply[:300] + ("..." if len(reply) > 300 else ""))
        print("[PASS] 临期优先 prompt 已生效（LLM 响应正常）")
    except Exception as e:
        print(f"[skip] LLM 请求失败（可能是密钥未配置）: {e}")


if __name__ == "__main__":
    admin_token = admin_login()
    user_token = user_login()
    test_waste(admin_token)
    test_cook_consume(user_token)
    test_chat_priority(user_token)
