# 创新点详解（论文素材库）

每一节都是一段独立可用的 200-300 字论文段落，可直接复制到论文 / 答辩稿。

## 1. 端云协同的"标签缓冲"识别架构

> **关键词**：端侧资源受限 / 异步配对 / TTL 缓冲表 / 时间窗关联

LuckFox Pico Pro Max 仅能运行 YOLOv5n 这类轻量模型，对食材本体的检测准确，但摄像头分辨率有限、本地无 OCR 能力，无法读清商品包装上的小字（生产日期、品牌、保质期等）。本项目设计了 **"端侧扫描 → 云端 OCR → 缓冲表 → 物品入库时自动配对"** 的异步架构：用户先把商品标签朝向摄像头，端侧通过 `POST /events/label_scan` 把标签照片上传，后端调用云端多模态识别完成 OCR + 结构化解析（品牌、产品名、保质期），将结果写入 `pending_labels` 缓冲表（TTL 5 分钟）。当用户随后把商品放进冰箱时，端侧 YOLO 触发 ITEM_IN 事件，后端按时间窗自动找到最近一条未消费的标签，将真实保质期注入 `inventory.label_data`，并把 LLM 估算的保鲜期覆盖为标签真实日期。这样既不增加端侧算力负担，又能拿到结构化的真实数据。该设计将"端侧检测"和"云端识别"解耦，实现了**异步事件驱动**的端云分工。

**实现位置**：`client/services/label_parser.py` · `client/agents/fridge_agent.py::handle_item_in` 的 `label_associate` 步骤 · `pending_labels` 表结构。

---

## 2. 共享置信度区间的视觉辅助识别策略

> **关键词**：成本可控 AI / 双闸门策略 / 区间触发 / 配置可审计

为兼顾识别准确度与云端 API 调用成本，本项目提出 **"区间触发"** 的视觉辅助识别策略。端侧 YOLO 给出的置信度仅在 `[lower, upper]` 区间内才触发云端复核：低于下界视为端侧"瞎猜"，调云端浪费 token；高于上界视为端侧已可信，无需复核。区间值由管理员通过双滑块在前端 `/admin/agent` 页面动态调整，存储在 `vision_assist_config` 单行表中。**两条入库路径（端侧 ITEM_IN agent 和管理员手动 POST /admin/inventory）共享同一区间策略**，保证策略的全局一致。每一次区间修改都通过 `save_log("admin", "VISION_ASSIST_CONFIG_UPDATE", ...)` 写入审计日志通道，可在 `/admin/audit` 页面以时间线形式回溯。该设计在保证准确度的前提下，把云端识别调用次数压缩到约 30%（取决于区间宽度），显著降低运营成本。

**实现位置**：`client/services/vision_assist.py::decide` · `client/api/admin.py::update_vision_assist_config` · `.kiro/specs/vision-assist-confidence-range/requirements.md`（10 条 EARS 格式需求文档）。

---

## 3. 双层去重的入库 ID 机制

> **关键词**：哈希秒拦 / 向量相似度 / pgvector HNSW / O(1) + O(log N)

为防止同一物品因多次拍照、不同角度被重复录入，本项目采用 **"字节哈希 + 向量相似度"** 的双层去重机制。第一层用 SHA-256 计算图片字节哈希，对完全相同的图片（最常见的复制粘贴 / 多次上传场景）做 O(1) 等值匹配秒拦；第二层调用 DashScope 多模态嵌入将图片转为 1024 维特征向量，存入 pgvector 列并建 HNSW 索引，新图入库时通过余弦相似度（`<=> ` 算子）做全表近邻检索，超过预设阈值则判定为同一物品。两层去重统一封装在 `services/dedup.py::check_duplicate` 中，**手动入库 / Agent ITEM_IN / 整柜批量入库** 三条路径共用一份逻辑，保证一致性。第一层秒拦让大部分重复请求开销极低，第二层兜底覆盖角度变化、轻微剪裁的"语义相同"场景。配合 HNSW 索引，百万级数据量下查询仍在毫秒级。

**实现位置**：`client/services/dedup.py` · `client/services/image_hash.py` · `client/services/embedding.py` · `database/tables.sql` 中 `idx_inventory_vector` HNSW 索引定义。

---

## 4. 全程可追踪、可解释的多 Agent 工具链

> **关键词**：Agent trace / step_order / AI 解释 / 可信 AI

参考 LangChain 的工具链思路，本项目实现了三类业务 Agent：`handle_item_in` / `handle_item_out` / `chat_stream`，每个 Agent 内部分解为 5-7 个原子工具步骤（如 `vector_dedup` / `vision_assist_decide` / `vision_recognize` / `llm_freshness` / `label_associate` / `db_write_inventory` 等）。**每一步都通过 `_trace_tool` 助手记录到 `agent_traces` 表**，包含工具名称、输入、输出、状态、耗时（ms）、设备 ID、所属 trace_id。前端 `/admin/workflow` 用 SVG + 拖拽节点把工具链拓扑可视化，每个节点可展开看完整 JSON 输入输出。在此基础上，进一步实现了 **"AI 解释决策"** 功能：点击按钮后调用 LLM 把整条 trace 翻译成 200-300 字的自然语言段落，例如把 5 步的 ITEM_IN trace 解释为"由于端侧置信度 0.42 落入触发区间，调用云端识别为 apple，找到 2 分钟前的标签缓冲并用真实保质期覆盖估算..."。该机制把"黑盒 AI"升级为"可解释 AI"，是论文中"可信 AI / 可解释机器学习"章节的直接落地。

**实现位置**：`client/agents/fridge_agent.py` · `client/services/llm.py::explain_trace` · `client/api/admin.py::explain_trace_api` · `web/src/components/TraceCanvasFlow.vue`。

---

## 5. WebSocket 全局广播的多 tab 实时同步

> **关键词**：fan-out / per-user 通知 / broadcast_all / 跨 tab 一致性

本项目对实时数据采用 **"按用户私推 + 全局广播"** 双通道设计。私推通道（`send_to_user(user_id, ...)`）用于"临期食品通知"等私人事件；全局广播通道（`broadcast_all`）用于"库存增删改"等所有连接都关心的共享事件。后端 `services/ws_manager.py` 实现进程内的 fan-out：所有连接以 `user_id` 为 key 存入字典，单条事件 broadcast 时遍历所有 socket 发送 JSON。前端通过 `composables/useInventoryWS.ts` 提供 `onCreated / onUpdated / onDeleted` 三种回调，admin Inventory、FridgeMap、可视化大屏、user Inventory 等多个页面共用一份连接管理逻辑（含 30s 心跳、5s 自动重连）。同一时刻打开三个 tab 时，任意一端删除一条食材，三个 tab 会同时执行"行滑出"动画并保持 total 数字一致。该设计杜绝了"刷新才更新"的传统体验，实现了**跨页面、跨用户、跨设备**的强实时一致性。

**实现位置**：`client/services/ws_manager.py` · `client/services/ws_events.py` · `web/src/composables/useInventoryWS.ts` · `client/api/admin.py::ws_admin_inventory`。

---

## 6. 共享区间策略 + 智能购物清单：从浪费分析到行动闭环

> **关键词**：单价配置 / 浪费金额估算 / 补货建议 / 一键购物清单

传统"浪费率"指标停留在数字层面，对用户的行为指导有限。本项目把"分析"升级为"行动"：每个品类可在 `/admin/categories` 页面配置参考单价（CNY），后端浪费分析接口将"浪费数量"按单价折算为"浪费金额"。同时，根据近期消耗节奏与当前在库数量推断"该补货什么"（消耗 ≥ 2 次但当前在库 ≤ 1 件的品类），生成结构化的购物建议（含建议数量、单价、预估总价）。前端 `/admin/waste` 页提供 **"复制清单"** 和 **"导出 TXT"** 按钮，把"近期消耗多但库存少 → 列出 SKU + 数量 + 预估总价"输出成可直接发到购物 App 或微信群的纯文本。365 天浪费金额日历热图把全年浪费分布一眼可视化，配合 GitHub-style 颜色深浅，让用户对"哪天浪费最多 / 一周浪费规律"形成直观感受。这把"数据分析"和"实际决策"打通成完整闭环。

**实现位置**：`client/crud/__init__.py::get_waste_analytics` `get_waste_calendar` · `web/src/views/admin/WasteAnalytics.vue` · 单价表 `category_thresholds.unit_price`。

---

## 7. AI 营养教练：从评分到周计划

> **关键词**：营养类别映射 / 健康评分 / 个性化建议 / 临期优先

本项目把现有数据组合成一个 AI 营养教练。`services/nutrition.py` 通过中文关键词匹配把食材品类映射到 9 种营养类别（蔬菜 / 水果 / 肉 / 海鲜 / 蛋奶 / 主食 / 零食 / 调料 / 饮料），结合"蔬果占比 / 蛋白质占比 / 零食占比"三维计算 0-100 分健康评分。用户点击 `/user/nutrition` 页的 **"让 AI 给我建议"** 按钮，后端 `coach_advice` 函数将"健康评分 + 偏好（含过敏忌口）+ 临期食材列表 + 近期消耗品类"打包成结构化 prompt 喂给 LLM，要求严格输出 JSON 格式，包含：1) 一句简短点评 2) 3-5 天具体的早午晚餐安排（必须用临期食材、避开过敏） 3) 3-5 条可执行的行动建议 4) 1-3 项本周该少吃的食物。前端按结构化展示，每条建议都对应可视化卡片。实测中 LLM 真正使用了"剩 1 天的香蕉"作为周二早餐的食材，并避开了用户偏好里登记的"不吃辣"，证明 prompt 工程到位。这是论文中"个性化推荐 / 数据驱动健康干预"章节的直接落地案例。

**实现位置**：`client/services/nutrition.py` · `client/services/llm.py::coach_advice` · `client/api/user.py::user_agent_coach` · `web/src/views/user/Nutrition.vue`。

---

## 8. 食材生命周期可视化（Sankey 流图）

> **关键词**：流量图 / 来源-品类-终态三段式 / 数据叙事

不同于传统的柱图饼图，本项目用 **Sankey 流图** 对食材生命周期做"流量化"表达：横向三列分别是"来源（端侧识别 / 手动录入 / 带标签入库）→ 品类（Top N + 其他）→ 终态（充足在库 / 临期在库 / 取出中 / 已消耗 / 已浪费）"，每条线的粗细对应该路径上的食材数量。鼠标悬浮时高亮 adjacency（同一条流的全部上下游），让评估者一眼看出"哪种来源最容易导致浪费"、"哪类食材最容易被按时消耗"。后端 `crud::get_lifecycle_sankey` 在一次 SQL 全表扫描中完成 source 推断、品类聚合、终态判定，前端用 ECharts sankey 渲染，节点按来源/品类/终态各用一套配色，深色主题下自动切换 echarts 内置 dark 主题。这是项目可视化层的"答辩亮点"——传统毕设很少做 Sankey。

**实现位置**：`client/crud/__init__.py::get_lifecycle_sankey` · `web/src/views/admin/Lifecycle.vue`。

---

## 9. 可视化大屏：B 端展示场景的颜值担当

> **关键词**：黑色全屏 / 实时事件流 / 双时钟 / 投影场景

`/admin/screen` 路由是脱离 AdminLayout 的独立全屏路由，黑色科幻配色（`#0a1014` 主背景 + 双 radial 渐变 + 薄荷绿 / 青色渐变标题），适合答辩投影 / 智能家居展厅 / 监控中心场景。布局：顶栏渐变标题 + 大字数字时钟（实时秒级更新）+ 全屏按钮；五张彩色 KPI 卡（彩色左色条），分别是总库存 / 即将到期 / 已过期 / 在线设备 / 浪费率。主体三栏：14 天入库出库趋势线图（带渐变面积）、保鲜状态饼图、实时事件流（红点呼吸 + 滑入动画）、Top 8 品类柱图（横向渐变）。所有 ECharts 使用深色配色覆盖。事件流复用同一份 `useInventoryWS` hook，新事件按"绿/橙/红"边色滑入，最多保留 20 条。打开后 F11 全屏，跑端侧 simulator loop，整个大屏会"活起来"，是答辩演示视频的开场首选。

**实现位置**：`web/src/views/admin/Screen.vue` · 全屏覆盖式定位 + transform 适配。

---

## 10. 双 JWT 完全分离的认证架构

> **关键词**：双密钥 / user_type 嵌入 / 分库分表 / 越权防护

参考 RuoYi-Vue3-FastAPI 的设计，本项目让 admin 与普通用户的认证体系**完全分离**。后端使用两套独立 JWT 密钥（`ADMIN_JWT_SECRET` / `USER_JWT_SECRET`）签发 token，token 载荷里嵌入 `user_type='admin'|'user'`。`decode_admin_token` / `decode_user_token` 在校验签名的同时严格校验类型字段，任一不匹配都视为非法 token。数据库层 `admins` 与 `users` 是两张独立表，CRUD 访问也分别走 `services/auth.py::get_current_admin` 和 `get_current_user` 两个 FastAPI 依赖。生产环境启动时拒绝默认 JWT 密钥，并要求显式配置 `CORS_ORIGINS` 和管理员初始化密码。即使 user token 泄露，攻击者也无法通过 admin 路由访问受保护资源（密钥不同 + 类型校验 + 数据库层完全隔离）。前端两套 axios 实例（`adminHttp` / `userHttp`）从各自登录态取 `admin_token` / `user_token`，路由守卫按 `meta.userType` 分流；流式聊天已改为 `fetch` stream 携带 Authorization，避免 token 出现在 URL。这是论文"安全设计"章节的标准案例。

**实现位置**：`client/services/auth.py` · `client/api/admin.py` `user.py` · `web/src/api/adminHttp.ts` `userHttp.ts` · `web/src/router/index.ts`。

---

## 用法建议

写论文时挑 **5-6 个** 创新点重点展开（每个 1.5-2 页）：
- 必选：1（标签缓冲）+ 4（可解释 Agent trace）+ 5（WS 实时同步）
- 二选一：2（共享区间）或 7（AI 教练）
- 二选一：3（双层去重）或 8（Sankey 可视化）
- 加分：6（购物清单闭环）

录视频时按这个顺序：**9（大屏开场）→ 4（工作流 + AI 解释）→ 1（标签缓冲）→ 5（多 tab 实时同步演示）→ 7（AI 教练）→ 8（Sankey）→ 6（购物清单导出）**，5-8 分钟完整覆盖所有亮点。
