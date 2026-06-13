# 开发历程

按倒序整理项目迭代过程。每个里程碑标注核心变更与产出文件，便于答辩讲"如何持续打磨"，也方便论文"开发流程"章节直接引用。

> 时间顺序：从下往上看是从 0 到完整，从上往下看是从完整到第 1 行。

---

## 🧹 第十阶段：单设备收敛 · 体验闭环 · 工程治理

### v0.27 死代码清理 + 类型零告警
- **删除** 4 个无引用 re-export 垫片（`api/api.py` `crud/crud.py` `schemas/schemas.py` `models/models.py`）
- **删除** 后端死函数 `usage_timer` / `create_admin` / `get_admin_by_id`，清掉无用 import
- **删除** 前端死代码：`getAdminMe` / `getUserMe` / `chat()` / `toolCategoryColors` / `exportEvents` / store 里未用的 `userId` / `isLoggedIn`
- **修复** `WasteAnalytics.vue` 中 ECharts `PieChart` 与 Element Plus 图标重名（重命名 `EPieChart`）
- **结果** `vue-tsc --noEmit` 零错误 + 全功能测试 71/71 通过

### v0.26 后端健壮性加固（稳定性测试驱动）
- **新增** `client/demo/test_stability.py`：并发压测 / 异常输入 / 鉴权边界 / 端侧事件 / 去重压力 / WS 抖动 / 持续负载 7 大类 34 项
- **修复** 3 处会返回 500 的入口缺陷 → 统一转 422：
  - `category` 超长（DB String(50) 截断）→ schema 加 `max_length=50`
  - 负数 / 超大 `limit`（SQL 报错）→ 路由用 `Query(ge=1, le=1000)`
  - `confidence` / `remain_ratio` 越界 → schema 加 `ge/le` 范围 + `status` 枚举 pattern

### v0.25 单设备收敛（端侧只有一台 LuckFox）
- **新增** `config.py` `DEVICE_ID = "luckfox"`，所有上报接口 `device_id` 缺省自动兜底
- **修改** schema 用 `field_validator` + `default_factory` 填充默认设备号
- **移除** 前端 admin / user 的设备 ID 筛选、表单项、表格列、FridgeMap 设备下拉、Workflow 设备搜索
- **新增** `docs/device-protocol.md`：端侧只需 4 个接口的完整 JSON 契约（登录 / 心跳 / 标签扫描 / 物品事件）
- **新增** `start-demo.bat` / `stop-demo.bat` 一键启动/停止演示（后端 + 前端 + 模拟器）

### v0.24 配色焕新：薄荷绿 → 天青蓝（Ocean Fresh）
- **修改** `style.css` 主色 `#10b981` → `#0ea5e9`，整套 hover/dark/light/soft + 背景冷调 + 阴影同步
- **批量** 25 个组件里写死的旧绿 RGB 替换为天青蓝；渐变第二色青色 → 靛蓝 `#6366f1`
- **保留** 管理员珊瑚橙辅助色 + success/warning/danger 语义色

### v0.23 工具链可视化重做：神经管线（Canvas 2D）
- **重写** `TraceCanvas2D.vue` 取代旧 DOM+SVG 版（已删 `TraceCanvasFlow.vue`）
- **新增** 深空渐变底 + 缓动极光带 + 氛围粒子 + 微光点阵网格
- **新增** 横向错落管线布局 + 双色渐变贝塞尔连线 + 多光点持续奔流（数据流动感）
- **新增** 节点入场动画（依次浮现 + easeOutBack）+ 呼吸辉光 + 鼠标视差 + 悬停路径高亮
- **新增** 「时间线」备选视图 `TraceTimeline.vue`（按序阅读 + 耗时条 + 人话说明），tab 切换

---

## 🍳 第九阶段：用户端体验闭环

### v0.22 用户购物清单
- **数据库** 新增 `shopping_items` 表（auto 系统建议 / manual 手动）
- **新增** 6 个 CRUD 路由 + `generate_shopping_suggestions`（近期常消耗但库存不足 → 自动补货建议）
- **新增** `views/user/Shopping.vue`：待买/已买分组 + 数量步进 + 勾选 + 智能建议 + 复制/导出 + 撤销删除

### v0.21 自然语言库存查询
- **新增** `services/llm.py::answer_inventory_query`：读全量在库（含保质期/品牌）让 LLM 据实回答
- **新增** `/user/agent/inventory-query` 路由
- **新增** Chat 页「🍳 食谱推荐 / 🔍 问库存」模式切换 + 命中食材标签

### v0.20 我的成就 + 烹饪日历 + AI 每日一句话
- **新增** `/user/stats/achievements`：16 枚徽章 + Lv1-5 等级 + 个人档案 + 30 天消耗趋势
- **新增** `views/user/Achievements.vue` 徽章墙（金箔贴纸 + 进度条 + 等级 Hero）
- **新增** `/user/stats/cooking` 烹饪日历（GitHub 风热图 + 连续打卡 streak + Top5 最爱做）
- **新增** Recipes 页加「食谱列表 / 烹饪日历」tab
- **新增** `/user/agent/daily-tip`（综合天气+临期+偏好+健康+消耗，60 字内）+ Home 页每日小贴士卡

### v0.19 新手引导 + 烹饪模式 + 历史对话可点击
- **新增** `OnboardingTour.vue` 首次登录 4 步引导（localStorage 记忆，命令面板可重看）
- **新增** `CookingMode.vue` 全屏分步烹饪（大字步骤 + 倒计时 + Web Speech TTS 朗读 + 键盘控制）
- **新增** Chat 历史对话按"轮次"分组 + 点击还原对话（含食谱卡片解析）+ 新对话按钮
- **美化** Preferences 偏好页（emoji 分组卡 + AI 学习脉冲标签）+ Chat 空状态居中卡片

---

## 🛠️ 第八阶段：稳定化与文档化

### v0.18 项目文档化（README + docs 体系）
- **新增** `README.md` 项目主页（badge / 总览架构图 / 快速启动 / 测试账号 / 4 个关键特性）
- **新增** `docs/architecture.md`（详细架构 + 4 个数据流时序图 + ER 图 + 部署拓扑）
- **新增** `docs/features.md`（12 大模块功能清单）
- **新增** `docs/highlights.md`（10 段论文素材库，每段 200-300 字）
- **新增** `docs/demo-script.md`（8 分钟 + 3 分钟双版演示脚本 + 录制小贴士 + 答辩 Q&A）
- **新增** `docs/changelog.md`（本文）

### v0.17 第一轮稳定化打磨
- **修复** 8 处硬编码颜色（Logs / Workflow / Recognize / FridgeMap / Dashboard / AdminLayout / BatchRecognize / Login）改为 CSS 变量
- **新增** 全局暗色规则：`stat-icon / kpi-icon / metric-icon` 在暗色下 `filter: brightness(0.55) saturate(1.1)`
- **新增** `EmptyHint.vue` 通用空状态组件（emoji + 渐变光晕 + 引导按钮）
- **新增** admin / user Inventory 空数据引导
- **新增** `utils/httpErrorToast.ts` 全局错误兜底（5xx / 网络断 / 超时统一弹 toast，5 秒去重）
- **新增** `RouteProgressBar.vue` 路由切换顶部进度条
- **接入** adminHttp / userHttp axios 拦截器调用全局 toast

---

## 🌟 第七阶段：高级亮点功能

### v0.16 性能监控周-小时热图
- **新增** 后端 `weekday_hour_heatmap` 字段（7×24 = 168 格）
- **新增** Perf 页周-小时热图（GitHub 风格调色 ebedf0 → 216e39）
- **修改** `crud.get_tool_perf_stats`

### v0.15 浪费金额日历热图
- **新增** `/admin/stats/waste-calendar` 路由
- **新增** WasteAnalytics 页底部加 365 天日历热图（ECharts calendar）
- **新增** 4 张统计：累计 / 件数 / 浪费天数 / 单日最高
- **修改** `crud.get_waste_calendar`

### v0.14 食材生命周期 Sankey 图
- **新增** 独立路由 `/admin/lifecycle`
- **新增** 三段式 Sankey：来源（带标签 / 端侧 / 手动）→ 品类（Top N + 其他）→ 终态（充足 / 临期 / 取出 / 消耗 / 浪费）
- **新增** `crud.get_lifecycle_sankey` + `Lifecycle.vue`
- **新增** ECharts SankeyChart 注册

### v0.13 AI 决策一键解释
- **新增** `services/llm.py::explain_trace`：把工具链 trace 翻译成自然语言段落
- **新增** `/admin/traces/{id}/explain` 路由
- **新增** Workflow 页右侧顶部 "AI 解释决策" 按钮 + 渐变面板（薄荷绿光晕 + 引号装饰 + 重新生成）

---

## 🎙️ 第六阶段：交互升级

### v0.12 语音输入
- **新增** `composables/useSpeechRecognition.ts` 封装 Web Speech API
- **新增** Chat 输入区左侧麦克风按钮（红色脉冲 + interim 实时显示）
- **特性**：浏览器原生、零依赖、零 token 成本

### v0.11 数据可视化大屏
- **新增** 独立路由 `/admin/screen`（脱离 AdminLayout）
- **新增** 黑色全屏 + 渐变标题 + 大字数字时钟 + 5 KPI（彩色左色条）
- **新增** 三栏：14 天趋势 / 饼图 + 实时事件流 / Top 8 柱图
- **新增** AdminLayout 顶栏 "大屏" 渐变胶囊（新窗口打开）

### v0.10 快速识别浮动面板（FAB）
- **新增** `QuickRecognizeFAB.vue` 全局右下角圆形按钮
- **特性**：渐变 + 呼吸光晕 + 复用 detect / bulk / upload-image
- **新增** 移动端 `<input capture="environment">` 自动调摄像头
- **挂载** App.vue（仅 admin 路径下显示）

### v0.9 AI 营养教练
- **新增** `services/llm.py::coach_advice` 把健康评分 + 偏好 + 临期 + 消耗组成 prompt
- **新增** `/user/agent/coach` 路由
- **新增** Nutrition 页"让 AI 给我建议"按钮 + 三栏建议面板
- **特性**：返回结构化 JSON（summary / week_plan / action_items / avoid）

---

## 📊 第五阶段：管理 & 分析

### v0.8 操作审计 + 健康饮食
- **新增** `/admin/audit` 操作审计独立页（按天分组时间线 + 客户端 CSV 导出）
- **修复** `get_unified_logs` 支持 source='admin' 过滤
- **新增** `services/nutrition.py` 9 大类营养标签映射 + 0-100 分健康评分
- **新增** `/user/nutrition` 健康饮食页（评分环 + 改进 tip + 饼图 + 比例条）
- **新增** `/user/stats/nutrition` 路由

### v0.7 单价配置 + 浪费金额 + 智能购物清单
- **数据库** `category_thresholds` 加 `unit_price NUMERIC(10,2)` 列
- **新增** `/admin/categories` 品类配置页（点击单元格内联编辑）
- **修改** `get_waste_analytics` 加 `wasted_value / consumed_value / priced_categories`
- **新增** WasteAnalytics 加 3 张金额卡 + 购物清单"复制 / 导出 TXT"按钮
- **新增** 补货建议加 `suggested_qty` + `estimated_cost`

### v0.6 设备管理 + 心跳 + Web 模拟器持续模式
- **新增** `devices` + `device_heartbeats` 表
- **新增** `crud.upsert_device_seen` 自动注册 + 心跳记录
- **新增** `/admin/events/heartbeat` + `/admin/devices` 路由
- **新增** Devices.vue 设备网格 + 24h 心跳柱图 + 编辑弹窗 + 撤销删除
- **新增** main.py 后台 sweeper（60s 巡检 offline + 整点清理流水）
- **新增** AdminLayout 顶栏设备状态 pill
- **修改** simulator 加 `loop` / `heartbeat` 子命令

### v0.5 性能监控 + AI 可解释性下钻
- **新增** `crud.get_tool_perf_stats` 按 tool_name 聚合 P50/P95/成功率
- **新增** `/admin/stats/perf` + `/admin/perf` 页（4 KPI + 趋势 + 工具明细表）
- **新增** `/admin/inventory/{id}/last-trace` 路由
- **新增** InventoryDetailDrawer 加"🧠 AI 是怎么决定的"折叠区
- **新增** 5 类 step 的人话翻译（vector_dedup / vision_assist / vision_recognize / llm_freshness / label_associate）

---

## 🔄 第四阶段：实时 + 互动

### v0.4 库存分页 + 食谱评分笔记 + 撤销扩展
- **数据库** `saved_recipes` 加 `rating INT(1-5) + notes TEXT`
- **新增** `getInventoryListPaged` 用 fetch 拿 X-Total-Count
- **新增** admin Inventory 加 el-pagination
- **新增** `PUT /user/recipes/{id}` 评分 / 笔记
- **新增** Recipes 页 5 颗星 hover + 笔记弹窗
- **新增** Devices / Preferences 删除接入撤销 toast

### v0.3 暗色主题完善 + CSV 导出 + 撤销 toast
- **修改** `theme.ts` 加跟随系统模式 + 监听 prefers-color-scheme
- **新增** `style.css` 暗色覆盖大量 Element Plus 组件（select / popover / dialog / table / pagination）
- **新增** `useChartTheme` composable（4 个 echarts 页面接入）
- **新增** `services/export_csv.py` + 3 个导出端点（inventory / events / usage）
- **新增** `utils/downloadCsv.ts`
- **新增** `useUndoToast.ts` 通用撤销 6 秒可点
- **接入** admin Inventory 删除 + user Recipes 取消收藏

### v0.2 库存搜索 + 命令面板 + 快捷键帮助
- **修改** `_apply_inventory_filters` 共用过滤器
- **新增** 4 个新参数：q（模糊）/ start_date / end_date / expiring_in_days
- **新增** admin / user Inventory 搜索框 + 日期范围 + 临期下拉
- **新增** `CommandPalette.vue` 全局 Ctrl+K 命令面板
- **新增** Ctrl+/ 快捷键帮助
- **新增** AdminLayout / UserLayout 顶栏 "命令面板" 胶囊

### v0.1 Dashboard 实时 + 临期食谱 + FridgeMap 实时 bbox + 食谱→库存联动 + 浪费分析
- **新增** `AnimatedNumber.vue` 数字跳变动画
- **接入** Dashboard / FridgeMap useInventoryWS（实时刷新）
- **新增** Chat 4 张快捷卡片（清临期 / 今日推荐 / 清淡 / 15 分钟）
- **新增** LLM prompt 加"⚠️ 临期食材 - 优先使用"段
- **新增** `/user/recipes/{id}/cook` 接受 `consumed_inventory_ids`，扣库存 + WS 广播
- **新增** Recipes 打卡弹窗（自动按食材名匹配勾选 + 临期颜色）
- **新增** `crud.get_waste_analytics` + `/admin/waste` 浪费分析页

---

## 🔗 第三阶段：实时同步基础

### v0.0.9 库存 WebSocket 实时推送
- **新增** `services/ws_manager.py` 加 `broadcast_all_sync`
- **新增** `services/ws_events.py` 三个广播函数（created / updated / deleted）
- **接入** agent ITEM_IN/OUT + admin manual create/update/delete + bulk
- **新增** `/admin/ws/inventory` 端点
- **新增** `composables/useInventoryWS.ts`
- **接入** admin / user Inventory + admin FridgeMap（滑入动画 + 高亮）

### v0.0.8 可调置信度区间触发视觉辅助
- **新增** spec `vision-assist-confidence-range/requirements.md`（10 条 EARS）
- **数据库** `vision_assist_config` 表 + 3 个 CHECK 约束
- **新增** `services/vision_assist.py` 决策服务 + 5 种枚举状态
- **新增** Schemas + `/admin/agent/vision-assist-config` GET/PUT
- **接入** ITEM_IN agent + 手动入库 共用同一区间
- **新增** main.py `_seed_vision_assist_config`
- **新增** AgentConfig.vue 视觉辅助识别策略卡片（双滑块 + 三段式可视化）

### v0.0.7 端侧模拟器 + 标签缓冲设计
- **新增** `client/demo/luckfox_simulator.py`（demo / label / item 三种模式）
- **新增** `client/demo/README.md`
- **设计** 端侧 JSON 协议（label_scan + ITEM_IN）
- **新增** `pending_labels` 表 + 5 分钟 TTL + 自动配对

---

## 🎨 第二阶段：核心模块迭代

### v0.0.6 WebSocket 通知实时推送
- **新增** `services/ws_manager.py` 连接管理器
- **新增** `/api/v1/user/ws/notifications` 端点
- **接入** `generate_expiry_notifications` 推送
- **新增** NotificationBell.vue 接 ws + 心跳 + 自动重连 + ElNotification toast

### v0.0.5 AI 食谱结构化卡片 + 收藏
- **新增** `recommend_structured_stream`：LLM 流式输出 `===RECIPE===` JSON 块
- **新增** `RecipeCard.vue` 边收边解析渲染卡片
- **数据库** `saved_recipes` 表
- **新增** `Recipes.vue` 我的食谱页
- **修改** `chat_stream` 加 `structured` 参数

### v0.0.4 双层去重防止相同图片入库
- **数据库** `inventory` 加 `image_hash VARCHAR(64)` 列
- **新增** `services/image_hash.py` SHA256 字节哈希
- **新增** `services/dedup.py::check_duplicate` 统一入口
- **修改** 向量比对扩到全表（不限 category）

### v0.0.3 临期通知按日期去重
- **数据库** `notifications` 加 `notice_date DATE` 列
- **修改** 唯一约束 → `(user_id, related_item_id, notice_date)`
- **效果**：每天每个临期食材生成一条新通知

### v0.0.2 工作流追踪页换 Canvas 动画
- **新增** `TraceCanvasFlow.vue` 矩形节点 + SVG 折线
- **新增** 拖拽节点 + 平移画布 + 滚轮缩放
- **新增** AI 解释装饰光晕

---

## 🌱 第一阶段：基础架构

### v0.0.1 双 JWT 完全分离的认证体系
- **设计** admin / user 独立用户表 + 独立 JWT 密钥
- **新增** `services/auth.py` `decode_admin_token` / `decode_user_token`
- **新增** `users` / `admins` 两张独立表
- **新增** 路由分流 `/api/v1/admin/*` `/api/v1/user/*`
- **新增** 前端独立 axios 实例 + 路由守卫

### v0.0.0 项目骨架
- FastAPI 后端骨架（api / agents / crud / models / schemas / services）
- Vue 3 + Vite + Element Plus + Pinia + TypeScript
- PostgreSQL + pgvector + uuid-ossp 扩展
- 端侧 LuckFox Pico Pro Max + YOLOv5n + OV5640
- 主体表：inventory（含 1024 维 feature_vector）+ event_logs + agent_traces

---

## 📈 量化数据

| 指标 | 数值 |
|---|---|
| 后端 Python 文件 | ~25 个 |
| 前端 Vue 组件 | ~45 个 |
| 后端总代码量 | ~6000 行 |
| 前端总代码量 | ~9000 行 |
| 数据库表 | 15 张（新增 shopping_items；含 vector / jsonb / uuid 类型） |
| REST 端点 | ~80 个 |
| WebSocket 端点 | 2 个 |
| Agent 工具步骤 | ~14 种 |
| 集成的云服务 | 3 个（DashScope Vision / Embedding + DeepSeek/Qwen） |
| 浏览器原生 API | Web Speech（识别 + TTS）/ WebSocket / Fetch Stream / Fullscreen / Canvas 2D |
| 主要可视化组件 | ECharts 7 种 + 自研 Canvas 2D 神经管线 |
| 自动化测试 | 全功能 71 项 + 稳定性 34 项 |

## 🎯 关键迭代驱动力

1. **从功能完整到亮点突出**：第七阶段加 Sankey / AI 解释 / 大屏 / 营养教练，把项目从"工程作业"推向"答辩亮点"
2. **从单机到实时**：WebSocket broadcast_all 是项目从"网页应用"升级到"实时系统"的转折
3. **从黑盒到可解释**：Agent trace + AI 解释让"AI 决策不再是猜"
4. **从数据到行动**：浪费分析 → 购物清单、AI 教练 → 周饮食计划，闭环价值
5. **从统一识别到端云分工**：标签缓冲机制利用了端侧 / 云端各自的优势
6. **从一刀切到可调阈值**：vision-assist-confidence-range 让管理员可控可审计
