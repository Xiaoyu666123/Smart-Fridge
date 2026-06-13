# 端侧模拟客户端

模拟 LuckFox Pico Pro Max 端侧设备，向后端上报两类事件：

1. **标签扫描** — 端侧 YOLOv5n 检测到食品标签 → 拍照 → POST 给后端 → 后端调云端 vision OCR 解析 → 写入 `pending_labels` 缓冲表
2. **物品入库** — 端侧 YOLOv5n 检测到物品 → POST 给后端 → 后端 `handle_item_in` 自动找最近 5 分钟未消费的标签关联

端侧两个事件之间是**完全独立**的，关联工作全在后端做。

## 用法

```bash
# 完整演示：自动从 uploads/ 挑两张图，按"先扫标签 → 等 2 秒 → 上报物品"流程跑
python luckfox_simulator.py demo

# 只扫描标签
python luckfox_simulator.py label /path/to/label.jpg

# 只上报物品入库
python luckfox_simulator.py item /path/to/item.jpg apple

# 单次心跳（自动注册到 devices 表）
python luckfox_simulator.py heartbeat

# 持续模式：每 30 秒发心跳，30% 概率随机插入 ITEM_IN/ITEM_OUT
# 用于演示/压测/Dashboard 实时数据源
python luckfox_simulator.py loop --interval 30 --probability 0.3
```

## 环境变量

| 变量 | 默认 | 说明 |
|---|---|---|
| `BACKEND_URL` | `http://127.0.0.1:8000` | 后端地址 |
| `ADMIN_USER` | `admin` | 端侧用 admin 上报事件 |
| `ADMIN_PASS` | `admin123` | 仅开发环境默认；生产环境使用 `.env` 中的 `ADMIN_INITIAL_PASSWORD` 初始化 |
| `DEVICE_ID` | `luckfox` | 设备 ID（标签和物品要一致才能配对） |

## 演示效果

跑完 `demo` 命令后：

- `/admin/pending-labels` 缓冲条目 status 从 `pending` 变成 `consumed`
- `/admin/inventory` 列表多一条带 📦 徽标的库存，过期时间用真实保质期
- `/admin/usage` 看到本次 vision OCR + 物品识别 + 保鲜估算消耗的 token
- `/admin/workflow` 选最新一条 trace，能看到完整工具链：embedding → vector_dedup → label_associate → llm_freshness → db_write_inventory
- 在线的 user 端 `NotificationBell` 如果食材临期，弹出实时通知 toast
