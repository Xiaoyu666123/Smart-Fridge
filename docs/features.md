# 功能清单

按模块完整盘点项目实现的所有功能。每一项都附路径，方便自查 / 答辩 / 论文引用。

## 目录

- [认证与权限](#认证与权限)
- [库存管理](#库存管理)
- [端侧事件接入](#端侧事件接入)
- [Agent 工具链](#agent-工具链)
- [AI 对话与食谱](#ai-对话与食谱)
- [营养与饮食偏好](#营养与饮食偏好)
- [购物清单与成就](#购物清单与成就)
- [设备管理](#设备管理)
- [数据可视化](#数据可视化)
- [审计与日志](#审计与日志)
- [实时同步（WebSocket）](#实时同步websocket)
- [前端体验](#前端体验)
- [其他工程化](#其他工程化)

---

## 认证与权限

| 功能 | 后端 | 前端 |
|---|---|---|
| 双 JWT 密钥（admin / user 隔离） | `services/auth.py` | `stores/adminAuth.ts` `userAuth.ts` |
| 独立登录页（同一界面切 tab） | `/admin/auth/login` `/user/auth/login` | `views/user/Login.vue` |
| 普通用户注册 | `/user/auth/register` | Login.vue |
| 改密 | `/admin/auth/change-password` | UserManagement.vue |
| 路由守卫（按 user_type 分流） | — | `router/index.ts` beforeEach |
| 401 自动跳登录页 | axios 拦截 | adminHttp.ts / userHttp.ts |

## 库存管理

| 功能 | 路径 |
|---|---|
| 库存 CRUD（含图片上传） | `/admin/inventory` |
| 多条件过滤 + 分页 | q / status / category / start_date / end_date / expiring_in_days |
| 整柜批量入库 | `/admin/inventory/bulk` |
| 双层去重（hash + vector） | `services/dedup.py` |
| 撤销删除（6s 内可恢复） | `composables/useUndoToast.ts` |
| 实时滑入动画 | `views/admin/Inventory.vue` rowClassName |
| 详情抽屉（图 + 标签 + 事件流 + AI 决策路径） | `components/InventoryDetailDrawer.vue` |
| 用户端只读 + 分类筛选 | `views/user/Inventory.vue` |
| 导出 CSV（带 UTF-8 BOM） | `/admin/export/inventory` |

## 端侧事件接入

| 功能 | 路径 |
|---|---|
| ITEM_IN / ITEM_OUT / ITEM_MOVED 事件 | `/admin/events/item` |
| 标签扫描缓冲 | `/admin/events/label_scan` → `pending_labels` 表 |
| 心跳上报 + 自动注册设备 | `/admin/events/heartbeat` |
| 单设备收敛（device_id 缺省自动填 luckfox） | `config.py::DEVICE_ID` + schema `field_validator` |
| 端侧上报协议文档（4 接口完整 JSON） | `docs/device-protocol.md` |
| 端侧模拟器 | `client/demo/luckfox_simulator.py` |
| 模拟器持续模式 | `loop --interval 30 --probability 0.3` |

## Agent 工具链

| Agent | 工具步骤 | 路径 |
|---|---|---|
| `handle_item_in` | save_image → vector_dedup → vision_assist_decide → vision_recognize（按需）→ llm_freshness → label_associate → db_write_inventory | `agents/fridge_agent.py` |
| `handle_item_out` | save_image → db_query_inventory → db_write_event_log（含状态变更广播） | 同上 |
| `chat_stream` | preference_extract → db_save_preferences → db_query_inventory → weather_query → llm_recipe_stream → save_conversation | 同上 |
| Trace 全程留痕 | `agent_traces` 表 + `_trace_tool` 助手 | crud |
| AI 解释决策 | `/admin/traces/{id}/explain` | `services/llm.py::explain_trace` |
| 工作流可视化（神经管线 Canvas 2D） | `/admin/workflow` | `components/TraceCanvas2D.vue` |
| 工作流时间线视图（备选） | tab 切换 | `components/TraceTimeline.vue` |
| 库存详情 → AI 决策路径 | InventoryDetailDrawer 折叠区 | — |

## AI 对话与食谱

| 功能 | 路径 |
|---|---|
| 流式对话（SSE） | `/user/agent/chat/stream` |
| 结构化食谱卡片（前端按 `===RECIPE===` 解析） | `services/llm.py::recommend_structured_stream` |
| 自然语言库存查询（"我有什么 3 天内过期的肉？"） | `/user/agent/inventory-query` → `answer_inventory_query` |
| Chat 双模式切换（食谱推荐 / 问库存） | `views/user/Chat.vue` askMode |
| 临期食材优先 | prompt 自动注入"⚠️ 临期食材"段 |
| 快捷指令（清临期 / 今日推荐 / 清淡 / 15 分钟） | `views/user/Chat.vue` quickPrompts |
| 偏好自动学习 | preference_extract |
| 语音输入（Web Speech 识别） | `composables/useSpeechRecognition.ts` |
| 历史对话按轮次分组 + 点击还原（含食谱卡片） | Chat.vue historyTurns / loadHistoryTurn |
| AI 每日一句话（天气+临期+偏好+健康+消耗） | `/user/agent/daily-tip` → `daily_tip` |
| 食材替换助手 | `/user/agent/substitute` → `suggest_substitute` |
| 收藏食谱 | `/user/recipes` |
| 评分（1-5）+ 笔记 | `/user/recipes/{id}` PUT |
| 打卡 + 库存联动扣减 | `/user/recipes/{id}/cook` |
| 烹饪日历（GitHub 风热图 + 连续打卡 + Top5） | `/user/stats/cooking` |
| 全屏烹饪模式（分步 + 倒计时 + TTS 朗读） | `components/CookingMode.vue` |

## 营养与饮食偏好

| 功能 | 路径 |
|---|---|
| 偏好 CRUD（口味/过敏/不吃/饮食方式） | `/user/agent/preferences` |
| 偏好分组卡片（4 色） + AI 来源徽标 | `views/user/Preferences.vue` |
| 健康饮食评分（0-100） | `services/nutrition.py::assess_health` |
| 食材类别映射（蔬菜/肉/水果/...） | `services/nutrition.py::classify` |
| 评分环形进度 + 改进建议 | `views/user/Nutrition.vue` |
| AI 营养教练（本周饮食安排） | `/user/agent/coach` → `services/llm.py::coach_advice` |
| 撤销删除偏好 | useUndoToast |

## 购物清单与成就

| 功能 | 路径 |
|---|---|
| 购物清单 CRUD | `/user/shopping` GET/POST/PUT/DELETE |
| 智能补货建议（近期常消耗但库存不足） | `/user/shopping/suggest` → `generate_shopping_suggestions` |
| 待买/已买分组 + 数量步进 + 勾选 | `views/user/Shopping.vue` |
| 一键清除已购 + 复制 / 导出 TXT | Shopping.vue |
| 撤销删除清单项 | useUndoToast |
| 我的成就（16 枚徽章 + Lv1-5 等级） | `/user/stats/achievements` → `get_user_achievements` |
| 个人档案 + 30 天消耗趋势折线 | `views/user/Achievements.vue` |
| 烹饪日历（连续打卡 streak + Top5 最爱做） | `/user/stats/cooking` → `get_cooking_calendar` |
| 首次登录 4 步新手引导（可重看） | `components/OnboardingTour.vue` |

## 设备管理

| 功能 | 路径 |
|---|---|
| 设备网格（live_status 按 last_seen_at 推算） | `/admin/devices` |
| 设备详情 + 24h 心跳柱状图 | `getDeviceHeartbeats` |
| 编辑名称 / 位置 / 备注 | PUT `/admin/devices/{id}` |
| 撤销删除（重新注册） | `/admin/devices/restore` |
| 后台 sweeper：超时设备置 offline + 整点清流水 | `main.py::_start_device_sweeper` |
| 顶栏在线/总数小药丸 | AdminLayout 设备 pill |

## 数据可视化

| 模块 | 内容 |
|---|---|
| Dashboard | 5 KPI（总库存/在库/过期/今天/3天内）+ API 用量 4 KPI + 4 图表 + WS 实时刷新 |
| FridgeMap | bbox 平面图，新物品有滑入脉冲动画，按到期天数染色 |
| 大屏 `/admin/screen` | 黑色全屏，5 大字 KPI + 14 天趋势 + 饼图 + 实时事件流 + Top 8 |
| 浪费分析 `/admin/waste` | 5 KPI + 3 cost 卡 + 3 图表 + 智能购物清单 + 365 天日历热图 |
| 食材生命周期 `/admin/lifecycle` | Sankey：来源 → 品类（Top N + 其他）→ 终态 |
| 性能监控 `/admin/perf` | 4 KPI + 趋势线 + 工具明细表 + 周-小时调用热图 |
| Token 用量 `/admin/usage` | 趋势 + 服务分布 + Top 10 入口 + 详情表 |
| 工作流 `/admin/workflow` | trace 列表 + 神经管线 Canvas 2D 流程图（极光/光点流动/入场动画）+ 时间线视图 + AI 解释 |
| 营养 `/user/nutrition` | 评分环 + 类别饼图 + 关键比例条 + 食材标签 |
| 成就 `/user/achievements` | 等级 Hero + 徽章墙 + 30 天消耗折线 + 个人档案卡 |

## 审计与日志

| 功能 | 路径 |
|---|---|
| 系统日志（事件 + trace 合并时间线） | `/admin/logs` |
| 操作审计专页（按 source=admin） | `/admin/audit` |
| 关键操作自动审计（视觉辅助配置 / 品类配置） | `save_log("admin", ...)` |
| 客户端 CSV 导出 | exportAudit |

## 实时同步（WebSocket）

| 功能 | 路径 |
|---|---|
| 全局连接管理器（per-user + broadcast_all） | `services/ws_manager.py` |
| 库存事件广播 | `services/ws_events.py` |
| admin WS 端点 | `/admin/ws/inventory` |
| user 通知 WS 端点 | `/user/ws/notifications` |
| 前端 useInventoryWS hook（心跳 + 重连 + 回调） | `composables/useInventoryWS.ts` |
| 临期通知按日期去重 | `(user_id, related_item_id, notice_date)` 唯一 |
| 大屏实时事件流 + 滑入动画 | Screen.vue |

## 前端体验

| 功能 | 路径 |
|---|---|
| 天青蓝主题（Ocean Fresh） | `style.css` `--brand-primary: #0ea5e9` |
| 暗色主题 + 跟随系统 | `stores/theme.ts` |
| 首次登录新手引导（4 步，可重看） | `components/OnboardingTour.vue` |
| 命令面板 Ctrl+K | `components/CommandPalette.vue` |
| 快捷键帮助 Ctrl+/ | 同上 |
| 快速识别 FAB（admin 全局浮动） | `components/QuickRecognizeFAB.vue` |
| 路由切换进度条 | `components/RouteProgressBar.vue` |
| 撤销 toast | `composables/useUndoToast.ts` |
| 通用空数据引导 | `components/EmptyHint.vue` |
| 数字跳变动画 | `components/AnimatedNumber.vue` |
| ECharts 主题随暗色切换 | `composables/useChartTheme.ts` |
| HTTP 错误统一 toast（5 秒去重） | `utils/httpErrorToast.ts` |
| CSV 通用下载 | `utils/downloadCsv.ts` |
| 图片压缩（长边 1280 + JPEG q=0.85） | `utils/imageCompress.ts` |

## 其他工程化

| 功能 | 路径 |
|---|---|
| LLM token 用量自动记账 | `services/usage.py::track_usage` |
| 用量 / 费用估算 | `cost_usd` 按模型单价计算 |
| 标签缓冲懒清理 | `cleanup_expired_pending_labels` |
| 心跳流水定期裁剪（48 小时） | `cleanup_old_heartbeats` |
| pgvector HNSW 索引 | `tables.sql` `idx_inventory_vector` |
| SQL 表注释（COMMENT） | tables.sql |
| 启动 seed（默认 admin / 类别阈值 / vision_assist 默认值） | `main.py` 多个 _seed_* |
