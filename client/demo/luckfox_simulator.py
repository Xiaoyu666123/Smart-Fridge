"""LuckFox Pico Pro Max 模拟客户端

模拟硬件端侧的两类事件上报：
  1. 标签扫描：先把食品标签照片传到 /events/label_scan（云端 OCR + 解析）
  2. 物品入库：把物品 + bbox 通过 /events/item ITEM_IN 上报，后端会自动配对
     最近未消费的标签

整个项目假设端侧只有一台 LuckFox，所以**所有上报请求都不传 device_id**，
后端会用 settings.DEVICE_ID（默认 'luckfox'）兜底。

用法：
    python luckfox_simulator.py demo            # 跑完整演示流程
    python luckfox_simulator.py label <图片路径> # 仅扫描标签
    python luckfox_simulator.py item   <图片路径> <category>  # 仅上报物品
    python luckfox_simulator.py loop --interval 30 --probability 0.5
                                                # 持续模式：每 N 秒按概率随机
                                                # 发送 heartbeat / ITEM_IN / ITEM_OUT
    python luckfox_simulator.py heartbeat       # 单次心跳

环境变量（可选）：
    BACKEND_URL  默认 http://127.0.0.1:8000
    ADMIN_USER   默认 admin
    ADMIN_PASS   默认 admin123
"""

import argparse
import base64
import os
import random
import sys
import time
from pathlib import Path

import httpx


BACKEND_URL = os.environ.get("BACKEND_URL", "http://127.0.0.1:8000")
ADMIN_USER = os.environ.get("ADMIN_USER", "admin")
ADMIN_PASS = os.environ.get("ADMIN_PASS", "admin123")


def login() -> str:
    """登录 admin，返回 token。端侧用 admin 上报事件。"""
    r = httpx.post(
        f"{BACKEND_URL}/api/v1/admin/auth/login",
        json={"username": ADMIN_USER, "password": ADMIN_PASS},
        timeout=10,
    )
    r.raise_for_status()
    token = r.json()["token"]
    print(f"[auth] 登录成功 -> token={token[:24]}...")
    return token


def b64_image(path: str) -> str:
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"图片不存在: {path}")
    return base64.b64encode(p.read_bytes()).decode()


def scan_label(token: str, image_path: str) -> dict:
    """模拟端侧扫描标签。"""
    print(f"\n[step1] 扫描标签: {image_path}")
    img = b64_image(image_path)
    r = httpx.post(
        f"{BACKEND_URL}/api/v1/admin/events/label_scan",
        headers={"Authorization": f"Bearer {token}"},
        json={"label_image": img, "ttl_seconds": 300},
        timeout=120,
    )
    r.raise_for_status()
    data = r.json()
    print(f"[step1] 标签解析完成 | pending_id={data.get('pending_label_id')}")
    print(f"        brand        = {data['label_data'].get('brand') or '(未识别)'}")
    print(f"        product_name = {data['label_data'].get('product_name') or '(未识别)'}")
    print(f"        expire_date  = {data['label_data'].get('expire_date') or '(未识别)'}")
    return data


def report_item_in(token: str, image_path: str, category: str,
                   bbox: list = None, confidence: float = 0.92) -> list:
    """模拟端侧 YOLOv5n 检测到物品入库。"""
    print(f"\n[step2] 物品入库: category={category}")
    img = b64_image(image_path)
    if bbox is None:
        # 模拟一个随机的位置
        x = random.randint(50, 400)
        y = random.randint(50, 300)
        bbox = [x, y, 160, 200]

    payload = {
        "timestamp": int(time.time() * 1000),
        "event_type": "ITEM_IN",
        "data": [{
            "local_track_id": random.randint(1, 9999),
            "category": category,
            "confidence": confidence,
            "bbox": bbox,
            "crop_image": img,
        }],
    }
    r = httpx.post(
        f"{BACKEND_URL}/api/v1/admin/events/item",
        headers={"Authorization": f"Bearer {token}"},
        json=payload,
        timeout=180,  # vision/embedding 可能慢
    )
    r.raise_for_status()
    items = r.json()
    if not items:
        print("[step2] 入库被去重命中（图片或向量重复）")
        return []
    inv = items[0]
    print(f"[step2] 入库成功 | inventory_id={inv['id']}")
    print(f"        category     = {inv['category']}")
    print(f"        bbox         = {inv['bbox']}")
    print(f"        has_label    = {inv.get('has_label', False)}")
    if inv.get("has_label"):
        ld = inv.get("label_data") or {}
        print(f"        brand        = {ld.get('brand')}")
        print(f"        expire_at    = {inv.get('expire_at')}（来源 {inv.get('expire_source')}）")
    else:
        print(f"        expire_at    = {inv.get('expire_at')}（AI 估算）")
    return items


def demo(token: str):
    """完整演示：找一张本地图片当标签 + 物品图，按"先扫标签 → 再入库"流程跑。"""
    here = Path(__file__).resolve().parent
    candidates = sorted((here.parent / "uploads").glob("*.jpg"))
    if not candidates:
        print("⚠️  uploads 目录没图片，请提供一张图作演示")
        print(f"用法: python {sys.argv[0]} label <标签图路径>")
        print(f"      python {sys.argv[0]} item  <物品图路径> <category>")
        return

    label_img = str(candidates[0])
    item_img = str(candidates[-1] if len(candidates) > 1 else candidates[0])
    print("=" * 60)
    print("LuckFox 模拟客户端 — 完整演示流程")
    print(f"标签图: {label_img}")
    print(f"物品图: {item_img}")
    print("=" * 60)

    scan_label(token, label_img)

    print("\n... 等待 2 秒（模拟用户从扫描到放进冰箱的时间） ...")
    time.sleep(2)

    report_item_in(token, item_img, category="apple")

    print("\n" + "=" * 60)
    print("✅ 演示完成。打开 http://localhost:3000 看后台变化：")
    print("   /admin/pending-labels   → 标签缓冲应该是 'consumed' 状态")
    print("   /admin/inventory        → 列表里多了一条带 📦 徽标的库存")
    print("   /admin/usage            → token 消耗已记录")
    print("=" * 60)


def send_heartbeat(token: str, event: str = "heartbeat") -> dict:
    """单次心跳上报。"""
    r = httpx.post(
        f"{BACKEND_URL}/api/v1/admin/events/heartbeat",
        headers={"Authorization": f"Bearer {token}"},
        json={"event": event, "payload": {"ts": int(time.time())}},
        timeout=10,
    )
    r.raise_for_status()
    data = r.json()
    print(f"💓 [{time.strftime('%H:%M:%S')}] heartbeat | "
          f"device={data['device_id']} | status={data['status']}"
          f"{' (新注册)' if data.get('auto_registered') else ''}")
    return data


def run_loop(token: str, *, interval: int = 30, probability: float = 0.3):
    """持续模式：固定间隔发心跳，按概率穿插发送 ITEM_IN / ITEM_OUT。"""
    here = Path(__file__).resolve().parent
    candidates = sorted((here.parent / "uploads").glob("*.jpg"))

    sample_categories = [
        "番茄", "鸡蛋", "牛奶", "苹果", "酸奶", "胡萝卜", "土豆",
        "芒果", "黄瓜", "西兰花", "豆腐", "白菜",
    ]

    print("=" * 60)
    print(f"🚀 LuckFox 持续模式启动")
    print(f"  心跳间隔: {interval} 秒")
    print(f"  事件概率: {probability * 100:.0f}%")
    print(f"  按 Ctrl+C 退出")
    print("=" * 60)

    tick = 0
    try:
        while True:
            tick += 1
            try:
                send_heartbeat(token, event="heartbeat")
            except Exception as e:
                print(f"  [warn] 心跳失败: {e}")

            if random.random() < probability:
                op = random.choice(["item_in", "item_in", "item_out"])  # IN 多一些
                if op == "item_in" and candidates:
                    img = random.choice(candidates)
                    cat = random.choice(sample_categories)
                    try:
                        report_item_in(token, str(img), cat,
                                        bbox=[random.randint(50, 400),
                                              random.randint(50, 300), 160, 200],
                                        confidence=round(random.uniform(0.65, 0.95), 2))
                    except Exception as e:
                        print(f"  [warn] ITEM_IN 失败: {e}")
                elif op == "item_out":
                    try_item_out(token)

            time.sleep(interval)
    except KeyboardInterrupt:
        print("\n👋 已退出持续模式")


def try_item_out(token: str):
    """随机挑一个 IN_STOCK 物品发 ITEM_OUT。"""
    r = httpx.get(
        f"{BACKEND_URL}/api/v1/admin/inventory",
        headers={"Authorization": f"Bearer {token}"},
        params={"status": "IN_STOCK", "limit": 50},
        timeout=10,
    )
    r.raise_for_status()
    items = r.json()
    if not items:
        return
    target = random.choice(items)
    payload = {
        "timestamp": int(time.time() * 1000),
        "event_type": "ITEM_OUT",
        "data": [{
            "local_track_id": random.randint(1, 9999),
            "category": target["category"],
            "confidence": 0.92,
            "bbox": target.get("bbox") or [0, 0, 0, 0],
        }],
    }
    rr = httpx.post(
        f"{BACKEND_URL}/api/v1/admin/events/item",
        headers={"Authorization": f"Bearer {token}"},
        json=payload,
        timeout=30,
    )
    if rr.status_code == 200:
        print(f"📤 [{time.strftime('%H:%M:%S')}] ITEM_OUT | category={target['category']}")


def main():
    parser = argparse.ArgumentParser(description="LuckFox 模拟客户端")
    parser.add_argument("cmd", choices=["demo", "label", "item", "loop", "heartbeat"], help="运行模式")
    parser.add_argument("path", nargs="?", help="图片路径（label/item 模式必需）")
    parser.add_argument("category", nargs="?", help="类别（item 模式必需）")
    parser.add_argument("--interval", type=int, default=30, help="loop 模式心跳/事件间隔（秒）")
    parser.add_argument("--probability", type=float, default=0.3,
                        help="loop 模式每个 tick 发送 ITEM 事件的概率（0-1）")
    args = parser.parse_args()

    token = login()

    if args.cmd == "demo":
        demo(token)
    elif args.cmd == "label":
        if not args.path:
            parser.error("label 模式需要图片路径")
        scan_label(token, args.path)
    elif args.cmd == "item":
        if not args.path or not args.category:
            parser.error("item 模式需要图片路径和 category")
        report_item_in(token, args.path, args.category)
    elif args.cmd == "heartbeat":
        send_heartbeat(token, event="manual")
    elif args.cmd == "loop":
        run_loop(token, interval=args.interval, probability=args.probability)


if __name__ == "__main__":
    main()
