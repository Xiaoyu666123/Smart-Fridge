"""
种子数据脚本 - 向数据库插入测试食材数据（含图片）

用法:
    cd client
    python seed_data.py

需要先启动 PostgreSQL 并确保数据库可连接。
会在 uploads/ 目录下生成示例图片（纯色占位图）。
"""

import os
import sys
import uuid
import json
from datetime import datetime, timedelta

# 确保在 client 目录下运行
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from database import SessionLocal, engine, Base
from models import Inventory, Admin, User
from services.auth import hash_password


def create_placeholder_image(filename: str, r: int, g: int, b: int, size: int = 200):
    """生成一个最小的有效 JPEG 占位图（纯色）"""
    upload_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "uploads")
    os.makedirs(upload_dir, exist_ok=True)
    filepath = os.path.join(upload_dir, filename)

    # 生成最小 BMP 然后转为简单 PPM 格式，用 Pillow 生成 JPEG 更好
    # 这里用最简方式：直接写一个小的 PPM 然后重命名为 jpg（浏览器可容忍）
    # 但为了兼容性，我们用 PIL/Pillow 来生成
    try:
        from PIL import Image
        img = Image.new("RGB", (size, size), (r, g, b))
        img.save(filepath, "JPEG", quality=85)
    except ImportError:
        # 没有 Pillow，用 PPM 格式（大多数浏览器支持）
        header = f"P6\n{size} {size}\n255\n".encode()
        pixels = bytes([r, g, b]) * (size * size)
        with open(filepath, "wb") as f:
            f.write(header + pixels)

    return filepath


SEED_DATA = [
    {
        "device_id": "luckfox",
        "category": "西红柿",
        "status": "IN_STOCK",
        "remain_ratio": 0.85,
        "agent_metadata": {
            "brand": "本地农场",
            "expire_at": (datetime.now() + timedelta(days=5)).isoformat(),
            "storage_advice": "冷藏保存",
        },
        "color": (220, 50, 50),
    },
    {
        "device_id": "luckfox",
        "category": "鸡蛋",
        "status": "IN_STOCK",
        "remain_ratio": 0.70,
        "agent_metadata": {
            "brand": "鲜鸡蛋",
            "expire_at": (datetime.now() + timedelta(days=14)).isoformat(),
            "storage_advice": "冷藏保存",
        },
        "color": (255, 240, 200),
    },
    {
        "device_id": "luckfox",
        "category": "牛奶",
        "status": "IN_STOCK",
        "remain_ratio": 0.60,
        "agent_metadata": {
            "brand": "伊利纯牛奶",
            "expire_at": (datetime.now() + timedelta(days=7)).isoformat(),
            "storage_advice": "冷藏保存，开封后3天内饮用",
        },
        "color": (240, 248, 255),
    },
    {
        "device_id": "luckfox",
        "category": "黄瓜",
        "status": "IN_STOCK",
        "remain_ratio": 0.90,
        "agent_metadata": {
            "brand": "有机黄瓜",
            "expire_at": (datetime.now() + timedelta(days=3)).isoformat(),
            "storage_advice": "冷藏保存",
        },
        "color": (50, 180, 50),
    },
    {
        "device_id": "luckfox",
        "category": "猪肉",
        "status": "IN_STOCK",
        "remain_ratio": 0.50,
        "agent_metadata": {
            "brand": "双汇冷鲜猪肉",
            "expire_at": (datetime.now() + timedelta(days=2)).isoformat(),
            "storage_advice": "冷冻保存",
        },
        "color": (255, 180, 180),
    },
    {
        "device_id": "luckfox",
        "category": "苹果",
        "status": "IN_STOCK",
        "remain_ratio": 0.95,
        "agent_metadata": {
            "brand": "红富士苹果",
            "expire_at": (datetime.now() + timedelta(days=10)).isoformat(),
            "storage_advice": "冷藏保存",
        },
        "color": (220, 50, 50),
    },
    {
        "device_id": "luckfox",
        "category": "酸奶",
        "status": "IN_STOCK",
        "remain_ratio": 0.40,
        "agent_metadata": {
            "brand": "蒙牛酸酸乳",
            "expire_at": (datetime.now() + timedelta(days=1)).isoformat(),
            "storage_advice": "冷藏保存，尽快饮用",
        },
        "color": (255, 255, 200),
    },
    {
        "device_id": "luckfox",
        "category": "豆腐",
        "status": "OUT_PENDING",
        "remain_ratio": 0.30,
        "agent_metadata": {
            "brand": "白玉豆腐",
            "expire_at": (datetime.now() + timedelta(days=0)).isoformat(),
            "storage_advice": "冷藏保存，开封后当天食用",
        },
        "color": (255, 255, 240),
    },
    {
        "device_id": "luckfox",
        "category": "白菜",
        "status": "CONSUMED",
        "remain_ratio": 0.00,
        "agent_metadata": {
            "brand": "大白菜",
            "expire_at": (datetime.now() - timedelta(days=1)).isoformat(),
            "storage_advice": "已消耗",
        },
        "color": (180, 220, 180),
    },
    {
        "device_id": "luckfox",
        "category": "三文鱼",
        "status": "IN_STOCK",
        "remain_ratio": 0.80,
        "agent_metadata": {
            "brand": "挪威三文鱼",
            "expire_at": (datetime.now() + timedelta(days=2)).isoformat(),
            "storage_advice": "冷藏保存，生食需在24小时内",
        },
        "color": (250, 128, 114),
    },
]


def seed():
    # 确保表存在
    Base.metadata.create_all(bind=engine)

    db = SessionLocal()
    try:
        # 检查是否已有种子数据
        existing = db.query(Inventory).filter(Inventory.device_id == "luckfox").first()
        if existing:
            print("种子数据已存在，跳过插入。如需重新插入，请先清空 inventory 表。")
            return

        # 确保 admin 用户存在（admins 表）
        admin = db.query(Admin).filter(Admin.username == "admin").first()
        if not admin:
            admin = Admin(username="admin", password_hash=hash_password("admin123"), real_name="系统管理员")
            db.add(admin)
            db.flush()

        # 创建测试普通用户
        test_user = db.query(User).filter(User.username == "testuser").first()
        if not test_user:
            test_user = User(username="testuser", password_hash=hash_password("test123"))
            db.add(test_user)
            db.flush()
            print("创建测试用户: testuser / test123")

        # 插入种子数据
        for i, item_data in enumerate(SEED_DATA):
            color = item_data.pop("color")
            filename = f"seed_{item_data['category']}_{i}.jpg"
            snapshot_path = create_placeholder_image(filename, *color)

            inv = Inventory(
                **item_data,
                snapshot_path=snapshot_path,
            )
            db.add(inv)
            print(f"  插入: {item_data['category']} ({item_data['status']}) -> {snapshot_path}")

        db.commit()
        print(f"\n成功插入 {len(SEED_DATA)} 条种子数据！")
        print("测试账号: admin/admin123 (管理员), testuser/test123 (普通用户)")
    except Exception as e:
        db.rollback()
        print(f"插入种子数据失败: {e}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    seed()
