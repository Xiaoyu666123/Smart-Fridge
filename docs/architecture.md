# 系统架构详解

本文档把项目的"端 - 云 - 后 - 前"四层架构、关键数据流、关键设计决策一次说清。

## 总览

```mermaid
flowchart TB
    subgraph 端侧["🛰️ 端侧 LuckFox Pico Pro Max（嵌入式 Linux）"]
        Cam["📷 OV5640<br/>1920×1080"]
        Det["YOLOv5n RKNN<br/>本地检测<br/>≈40ms / 帧"]
        Sim["luckfox_simulator.py<br/>开发期模拟器"]
        Cam --> Det
    end

    subgraph 网络["🌐 HTTP / WS"]
        REST[REST API]
        WSS[WebSocket]
    end

    subgraph 后端["🔧 FastAPI 后端（Python 3.9 + uvicorn）"]
        direction TB
        Routes["api/<br/>admin / user 双路由 + 双 JWT"]
        Agents["agents/<br/>FridgeAgent"]
        Services["services/<br/>vision / llm / dedup / ws_*"]
        CRUD["crud/"]
        WSManager["WS Manager<br/>per-user + broadcast_all"]
        Routes --> Agents
        Routes --> Services
        Agents --> Services
        Services --> CRUD
        Routes --> WSManager
        Agents --> WSManager
    end

    subgraph 存储["🗄️ PostgreSQL 15 + pgvector"]
        T1["inventory<br/>+ feature_vector(1024)"]
        T2[event_logs]
        T3[agent_traces]
        T4[pending_labels]
        T5[notifications]
        T6[saved_recipes]
        T7[devices + heartbeats]
        T8[users / admins]
        T9[llm_usage]
        T10[vision_assist_config]
        T11[shopping_items]
    end

    subgraph 云端["☁️ DashScope + DeepSeek"]
        VS[Vision 多模态识别]
        EM[Embedding 1024d]
        LLM[Chat / Stream]
    end

    subgraph 前端["🌐 Vue 3 前端（admin + user + 大屏）"]
        ALayout[AdminLayout]
        ULayout[UserLayout]
        Screen[Screen 大屏]
        FAB[QuickRecognizeFAB]
        CMD[CommandPalette]
    end

    Det -.JSON.-> REST
    Sim -.JSON.-> REST
    REST <--> 后端
    WSS <-->|实时推送| WSManager
    CRUD <--> 存储
    Services <-->|HTTPS| 云端
    ALayout <-.->|HTTP+WS| 后端
    ULayout <-.->|HTTP+WS| 后端
    Screen <-.->|HTTP+WS| 后端
```

## 模块划分

### 后端 `client/`

| 目录 | 职责 |
|---|---|
| `api/admin.py` | 管理员路由（CRUD / 设备 / 配置 / 统计 / 审计） |
| `api/user.py` | 普通用户路由（库存只读 / 对话 / 偏好 / 食谱 / 营养） |
| `api/api.py` | 路由聚合，挂在 `/api/v1` |
| `agents/fridge_agent.py` | ITEM_IN / ITEM_OUT / CHAT 三类 Agent |
| `services/vision.py` | DashScope 多模态识别 |
| `services/embedding.py` | 向量提取 + 阈值定义 |
| `services/dedup.py` | 双层去重统一入口 |
| `services/llm.py` | DeepSeek/Qwen 同步 + 流式 + 教练 + 解释 |
| `services/label_parser.py` | 标签 OCR + 结构化 |
| `services/vision_assist.py` | 共享区间策略决策 |
| `services/ws_manager.py` | 全局 WS 连接池 |
| `services/ws_events.py` | 库存事件广播辅助 |
| `services/auth.py` | 双 JWT + 密码 hash + 鉴权依赖 |
| `services/usage.py` | LLM token 用量记账 |
| `crud/__init__.py` | 数据库读写聚合 |

### 前端 `web/src/`

| 目录 | 职责 |
|---|---|
| `views/admin/*` | 管理员页面（13 个） |
| `views/user/*` | 用户页面（7 个） |
| `components/*` | 跨页面通用组件（CommandPalette / FAB / NotificationBell / EmptyHint / RouteProgressBar / TraceCanvasFlow / RecipeCard / InventoryDetailDrawer / AnimatedNumber） |
| `composables/*` | useInventoryWS / useChartTheme / useUndoToast / useSpeechRecognition |
| `api/admin/*` `api/user/*` | axios 封装，自动带 token |
| `stores/*` | Pinia: adminAuth / userAuth / theme / chat |

## 关键数据流

### 流 1：端侧 ITEM_IN 入库

```mermaid
sequenceDiagram
    participant E as 端侧
    participant B as 后端 /events/item
    participant Ag as FridgeAgent
    participant DB as Postgres
    participant W as WS
    participant FE as 前端

    E->>B: POST {event_type:'ITEM_IN', items:[{category, conf, bbox, crop_image}]}
    B->>Ag: handle_item_in
    Ag->>DB: 写设备心跳
    Ag->>Ag: dedup（hash + 向量）
    alt 命中重复
        Ag-->>B: return None
    else 通过
        Ag->>Ag: vision_assist_decide
        opt 决策 = TRIGGERED
            Ag->>云端: vision_recognize
        end
        Ag->>云端: estimate_freshness (LLM)
        Ag->>DB: find_active_pending_label
        Ag->>DB: INSERT inventory + label_*
        Ag->>W: broadcast_inventory_created
        W->>FE: ws.send {type:'inventory.created'}
    end
```

### 流 2：标签缓冲配对

```mermaid
sequenceDiagram
    participant E as 端侧
    participant B as 后端
    participant DB as pending_labels
    participant Inv as inventory

    Note over E: 用户拿出新物品<br/>把标签朝向摄像头
    E->>B: POST /events/label_scan {label_image}
    B->>云端: OCR + 结构化
    B->>DB: INSERT pending_label (TTL 5min)
    Note over E: 用户把物品放进冰箱
    E->>B: POST /events/item ITEM_IN
    B->>DB: SELECT pending_label<br/>WHERE consumed_at IS NULL<br/>ORDER BY created_at DESC LIMIT 1
    B->>Inv: INSERT 含 label_text/label_data
    B->>DB: UPDATE pending_label SET consumed_at=now
```

### 流 3：CHAT 推荐（流式）

```mermaid
sequenceDiagram
    participant U as 用户浏览器
    participant B as 后端 /agent/chat/stream
    participant Ag as FridgeAgent
    participant LLM as DeepSeek

    U->>B: GET /chat/stream?message=...&structured=true + Authorization Bearer (fetch stream)
    B->>Ag: chat_stream
    Ag->>Ag: extract_preferences + save
    Ag->>DB: 查库存 + 偏好 + 历史
    Ag->>云端: get_current_weather
    Ag->>LLM: stream chat (含临期食材 + 偏好 prompt)
    LLM-->>Ag: chunk by chunk
    Ag-->>U: text/event-stream data: {"type":"delta", "content":"..."}
    Note over U: 前端按 ===RECIPE=== 块解析卡片
    Ag->>DB: save assistant message
    Ag-->>U: SSE data: {"type":"done", "detected_preferences":[...]}
```

### 流 4：WebSocket 全局广播

```mermaid
sequenceDiagram
    participant FE1 as 前端 admin tab
    participant FE2 as 前端 user tab
    participant FE3 as 前端大屏
    participant W as WSManager
    participant B as 后端

    FE1->>W: connect /admin/ws/inventory?token
    FE2->>W: connect /user/ws/notifications?token
    FE3->>W: connect /admin/ws/inventory?token

    Note over B: 任意人删了一条 inventory
    B->>W: broadcast_all_sync({type:'inventory.deleted', id:...})
    W-->>FE1: ws.send
    W-->>FE2: ws.send
    W-->>FE3: ws.send
    Note over FE1,FE3: 三端动画同步消失
```

## 关键设计决策

### 为什么用双 JWT 密钥（admin / user 完全分离）？

`services/auth.py` 用 `ADMIN_JWT_SECRET` / `USER_JWT_SECRET` 两套独立密钥签发 token，token 载荷里嵌入 `user_type='admin'|'user'`，解码时双重校验。

生产环境启动时会拒绝默认 JWT 密钥，并要求配置 `CORS_ORIGINS`；管理员初始化密码通过 `ADMIN_INITIAL_PASSWORD` 显式提供。浏览器端的流式聊天使用 `fetch` stream 携带 `Authorization`，避免把 token 放进 URL。WebSocket 目前仍因浏览器 API 限制使用查询参数传 token，正式部署可进一步升级为一次性短期 WS ticket。

**好处**：
- 即使 user token 泄露也无法访问 admin 路由（密钥不同 + 类型校验）
- 用户名同名（如同样叫 `admin`）也不会混淆
- 数据库表也分 `users` / `admins`，杜绝 SQL 越权

### 为什么去重做两层？

| 层 | 算法 | 复杂度 | 命中场景 |
|---|---|---|---|
| 1 | SHA256 字节哈希 | O(1) | 同一张图重复上传（最常见） |
| 2 | pgvector 余弦相似度 | O(N)（HNSW 索引下近 O(log N)） | 不同角度 / 轻微剪裁的同一物品 |

第一层秒拦，第二层兜底。统一从 `services/dedup.py::check_duplicate` 进入，所有入库路径（手动 / agent / 批量）共用一份逻辑。

### 为什么 Vision 辅助走"区间触发"？

```
端侧 YOLOv5n 置信度
─────────────────────────
< lower (默认 0.3)：太低，端侧大概率瞎猜，跳过云端复核（节省 token）
[lower, upper]：可疑档位，触发云端复核，置信度更高时覆盖
> upper (默认 0.7)：端侧已足够可信，跳过云端
```

由 admin 在前端调，写到 `vision_assist_config` 单行表。所有变更走 `save_log("admin", "VISION_ASSIST_CONFIG_UPDATE", ...)` 留审计。

### 为什么 WebSocket 用 `broadcast_all`？

库存事件本质是"共享 fridge 视图"：admin 删一条食材，所有看 inventory 的 tab 都该立刻更新；user 也该看到。所以不按 user_id 分发，直接 `broadcast_all`，前端自己根据当前页面决定怎么渲染（Inventory 改列表，FridgeMap 改 bbox，大屏滚事件流）。

通知类（临期）才走 `send_to_user(user_id, ...)`，因为通知是私人的。

### 为什么用 pgvector 而不是 Faiss / Pinecone？

- 数据已经在 Postgres，不想再部署一套向量数据库
- 入库 / 查询都在同一事务里，原子性保证
- HNSW 索引性能足够（百万级才会瓶颈）
- pgvector 的 `<=>` 余弦运算符就是 SQL，BI 工具都能直接查

### 为什么 trace 数据写到 `agent_traces` 表而不是 ELK / Jaeger？

- 项目演示场景，运维栈太重
- 数据可直接用 SQL 聚合做性能监控（P50/P95 都是一句 SQL）
- AI 解释直接读这张表喂给 LLM

## 数据库表关系

```mermaid
erDiagram
    users ||--o{ user_preferences : "1:N"
    users ||--o{ conversations : "1:N"
    users ||--o{ notifications : "1:N"
    users ||--o{ saved_recipes : "1:N"
    users ||--o{ shopping_items : "1:N"
    admins ||--o{ vision_assist_config : "updated_by"
    inventory ||--o{ event_logs : "1:N"
    inventory ||--o{ pending_labels : "consumed_by"
    devices ||--o{ device_heartbeats : "1:N"
    agent_traces }o--o{ inventory : "via 时间窗"

    inventory {
        uuid id PK
        varchar device_id "单设备部署，固定为 luckfox"
        varchar category
        varchar status
        vector feature_vector "1024 维"
        jsonb agent_metadata
        jsonb label_data
        varchar image_hash "SHA256"
        timestamp expire_at
    }
    pending_labels {
        uuid id PK
        varchar device_id "单设备部署，固定为 luckfox"
        text label_text
        jsonb label_data
        timestamp expires_at "TTL 5min"
        uuid consumed_by_inventory_id FK
    }
    agent_traces {
        bigint id PK
        uuid trace_id "同 trace 同 ID"
        varchar agent_type "ITEM_IN/OUT/CHAT/admin"
        int step_order
        varchar tool_name
        jsonb tool_input
        jsonb tool_output
        varchar status
        int duration_ms
    }
```

## 性能指标

| 操作 | P50 | P95 | 备注 |
|---|---|---|---|
| ITEM_IN（含云端 vision + LLM 估算） | ~3-5s | ~8s | 主要是 LLM 推理 |
| 库存查询（带过滤分页） | ~10ms | ~30ms | HNSW 索引保护 |
| 双层去重 | ~50ms | ~200ms | embedding 网络往返 |
| WebSocket 单事件广播 | <5ms | <20ms | 内存 fan-out |
| AI 解释 trace | ~3-6s | ~10s | LLM 推理 |
| 前端首屏（大屏） | ~800ms | ~1.5s | lazy chunk + ECharts 分包 |

> 数据来源：`services/usage.py` 实际记录的 `duration_ms`。

## 部署拓扑

```mermaid
flowchart LR
    Internet[公网用户] -->|HTTPS:443| LB[Nginx]
    LuckFox[LuckFox 设备] -->|HTTPS| LB
    LB -->|/api/v1/| Backend[FastAPI x N]
    LB -->|/| Frontend[Vue 静态]
    LB -->|/uploads/| Static[图片存储]
    Backend --> PG[(PostgreSQL<br/>+ pgvector)]
    Backend --> Redis[(Redis<br/>可选 WS 跨进程)]
    Backend -->|出向| Cloud[DashScope / DeepSeek]
```

> 单进程部署也能跑（项目目前如此）。多 worker 时 WS 跨进程广播需要 Redis pub/sub。
