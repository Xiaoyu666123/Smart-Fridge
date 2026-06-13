# 端侧 → 云端 上报数据格式

端侧需要发给后端的 4 个接口，每个都给出**完整 JSON 请求体**和字段说明。

- 基地址：`http://<云端 IP>:8000`
- 所有路由前缀：`/api/v1/admin`
- Header（除登录外都要带）：
  ```
  Authorization: Bearer <token>
  Content-Type: application/json
  ```

---

## 1. 登录拿 token

`POST /api/v1/admin/auth/login`

### 请求体

```json
{
  "username": "admin",
  "password": "<ADMIN_INITIAL_PASSWORD>"
}
```

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `username` | string | ✅ | 当前演示协议使用管理员账号，默认 `admin` |
| `password` | string | ✅ | 生产环境由 `.env` 的 `ADMIN_INITIAL_PASSWORD` 初始化；开发环境未配置时才兼容 `admin123` |

### 响应

```json
{
  "token": "eyJhbGciOiJIUzI1Ni....",
  "admin_id": "8e3a1c0b-...",
  "username": "admin",
  "real_name": null
}
```

端侧只需要保存 `token`。

> 安全说明：当前端侧演示协议仍复用 admin token 上报事件。正式部署建议改为设备专用凭证（例如 device API key 或 device-scoped JWT），避免端侧 token 泄露后获得完整管理权限。

---

## 2. 心跳

`POST /api/v1/admin/events/heartbeat`

每 30 秒发一次。第一次发的 `device_id` 会被后端自动注册成新设备。**只有一台设备时连 `device_id` 都不用传**，后端默认填 `luckfox`。

### 请求体（最简版）

```json
{}
```

### 请求体（完整版）

```json
{
  "device_id": "luckfox",
  "event": "heartbeat",
  "payload": {
    "ts": 1716466178
  }
}
```

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `device_id` | string | ❌ | 端侧只有一台 LuckFox 时可省略，后端会用配置里的 `DEVICE_ID`（默认 `luckfox`）填充。如果传也行 |
| `event` | string | ❌ | 默认 `heartbeat`，也可写 `startup` 等任意短字符串 |
| `payload` | object | ❌ | 任意自定义诊断字段，原样存档 |

---

## 3. 扫描食品标签

`POST /api/v1/admin/events/label_scan`

用户把商品标签放到镜头前时调用。后端做 OCR + 结构化解析。**5 分钟内**同一设备的下一次 `events/item` 入库会自动关联这条标签。

### 请求体

```json
{
  "label_image": "<base64 of label crop>",
  "ttl_seconds": 300
}
```

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `device_id` | string | ❌ | 同上，可省略；只有一台 LuckFox 时不用传 |
| `label_image` | string | ✅ | 标签图 base64，**不带** `data:image/...` 前缀，JPEG 格式 |
| `ttl_seconds` | int | ❌ | 缓冲存活秒数，默认 300，范围 10 ~ 3600 |

---

## 4. 物品事件（核心）

`POST /api/v1/admin/events/item`

YOLO 检测到入库 / 出库 / 移动时发。一次请求可带多个物体。

### 请求体

```json
{
  "timestamp": 1716466178000,
  "event_type": "ITEM_IN",
  "data": [
    {
      "local_track_id": 1024,
      "category": "番茄",
      "confidence": 0.87,
      "bbox": [120, 80, 160, 200],
      "crop_image": "<base64 of crop>"
    }
  ]
}
```

### 顶层字段

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `device_id` | string | ❌ | 同上，可省略；只有一台 LuckFox 时不用传 |
| `timestamp` | int | ✅ | 端侧时间戳，**毫秒** |
| `event_type` | enum | ✅ | `ITEM_IN` / `ITEM_OUT` / `ITEM_MOVED` / `AGENT_UPDATE` 四选一 |
| `data` | array | ✅ | 至少 1 项，建议 ≤ 8 项 |

### `data[]` 元素字段

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `local_track_id` | int | ✅ | YOLO 跟踪 ID，跨帧同物体保持一致 |
| `category` | string | ✅ | 端侧识别出的类别名（中文/英文都可） |
| `confidence` | float | ✅ | YOLO 置信度，0.0 ~ 1.0 |
| `bbox` | int[4] | ✅ | `[x, y, w, h]`，单位像素 |
| `crop_image` | string | ⚠️ | 物体裁剪图 base64，**不带** `data:` 前缀。`ITEM_IN` 强烈建议带；其他事件可省略 |

### `event_type` 取值

| 值 | 含义 |
| --- | --- |
| `ITEM_IN` | 放入新物体（入库） |
| `ITEM_OUT` | 取出物体 |
| `ITEM_MOVED` | 物体在格内移动（只更新 bbox） |
| `AGENT_UPDATE` | 端侧主动纠正之前的识别（一般用不上） |

---

## 5. 字段约束总表

| 字段 | 约束 |
| --- | --- |
| `device_id` | 字符串，长度 ≤ 50。**只有一台 LuckFox 时可全部省略**，后端取配置里的 `DEVICE_ID`（默认 `luckfox`）|
| `timestamp` | int，毫秒（`int(time.time() * 1000)`） |
| `bbox` | `[x, y, w, h]` 4 个 int，单位像素 |
| `confidence` | float，0.0 ~ 1.0 |
| `crop_image` / `label_image` | 纯 base64 字符串，不含 `data:image/jpeg;base64,` 前缀，JPEG 格式 |

---

## 6. 端侧调用顺序示例

```
启动:  POST /auth/login              → 拿 token
       POST /events/heartbeat        → event="startup"
循环:  POST /events/heartbeat        → 每 30s
扫码:  POST /events/label_scan       → 用户扫描标签
入库:  POST /events/item             → event_type=ITEM_IN，5 分钟内
出库:  POST /events/item             → event_type=ITEM_OUT
```
