# Agent 工具链可视化设计

## 概述

在现有智能冰箱系统中新增 Agent 工具链追踪与可视化功能。每次 Agent 执行时记录各工具调用步骤（工具名、输入输出、耗时、状态），前端以流程图形式展示完整的工具调用链。

## 后端设计

### 新增表：agent_traces

| 字段 | 类型 | 说明 |
|------|------|------|
| id | BIGSERIAL PK | 自增主键 |
| trace_id | UUID | 同一次 agent 调用共享一个 trace_id |
| agent_type | VARCHAR(30) | 触发类型：ITEM_IN / ITEM_OUT / CHAT |
| step_order | INTEGER | 同一 trace 内的步骤序号（从1开始） |
| tool_name | VARCHAR(50) | 工具名 |
| tool_input | JSONB | 输入摘要 |
| tool_output | JSONB | 输出摘要 |
| status | VARCHAR(10) | SUCCESS / FAILED / SKIPPED |
| duration_ms | INTEGER | 耗时毫秒 |
| device_id | VARCHAR(50) | 设备号（对话场景可为空） |
| created_at | TIMESTAMP DEFAULT now() | 调用时间 |

索引：
- `idx_traces_trace_id` ON agent_traces(trace_id)
- `idx_traces_agent_type` ON agent_traces(agent_type)
- `idx_traces_device_id` ON agent_traces(device_id)
- `idx_traces_created_at` ON agent_traces(created_at DESC)

### 工具名称定义

| agent_type | 工具链顺序 |
|------------|-----------|
| ITEM_IN | vision_recognize → llm_freshness → db_write_inventory → db_write_event_log |
| ITEM_OUT | db_query_inventory → db_write_event_log |
| CHAT | preference_extract → db_save_preferences → db_query_inventory → llm_recipe → db_save_conversation |

### FridgeAgent 埋点

在 `fridge_agent.py` 的三个方法中，使用辅助函数 `_trace_tool(trace_id, step_order, tool_name, input, output, status, duration_ms, device_id)` 记录每个工具调用：

1. 方法入口生成 `trace_id = uuid4()`
2. 每个工具调用前后计时，记录 trace 行
3. 工具调用失败时记录 status=FAILED 和错误信息
4. 跳过的工具（如视觉 API 未配置）记录 status=SKIPPED

### 新增 API

- `GET /api/v1/traces` — 查询 trace 列表
  - 参数：agent_type(可选), device_id(可选), limit(默认20), offset(默认0)
  - 返回：按 created_at 倒序的 trace 摘要列表（trace_id, agent_type, device_id, 步骤数, 总耗时, created_at）

- `GET /api/v1/traces/{trace_id}` — 获取某次 trace 的完整工具链
  - 返回：trace_id 对应的所有步骤，按 step_order 排序

## 前端设计

### Workflow.vue 重写

替换现有 mock 页面，使用 Element Plus 原生组件。

**页面布局：**
- 顶部筛选栏：agent 类型下拉、设备 ID 输入、查询按钮
- 左侧面板（30%宽度）：trace 列表，每行显示触发类型、设备、时间、总耗时
- 右侧面板（70%宽度）：选中 trace 后展示工具链流程图

**流程图样式：**
- 纵向排列的节点卡片，CSS 箭头连接
- 每个节点：el-card 显示工具名、状态色标、耗时、可折叠的输入/输出摘要
- 成功=绿色边框，失败=红色边框，跳过=灰色边框
- 节点间用 CSS 伪元素画竖线+箭头

### 新增 API 层

`web/src/api/trace.ts`：
- `getTraceList(params)` → GET /traces
- `getTraceDetail(traceId)` → GET /traces/{traceId}

### 数据流

```
设备事件/用户对话 → FridgeAgent → 逐步调用工具 → 每步写 agent_traces
                                          ↓
前端 Workflow.vue → GET /traces → 左侧列表
                  → GET /traces/{id} → 右侧流程图
```

## Pydantic Schema

### TraceStepResponse
- id: int
- step_order: int
- tool_name: str
- tool_input: dict | None
- tool_output: dict | None
- status: str
- duration_ms: int | None

### TraceSummaryResponse
- trace_id: str
- agent_type: str
- device_id: str | None
- step_count: int
- total_duration_ms: int | None
- created_at: str | None

### TraceDetailResponse
- trace_id: str
- agent_type: str
- device_id: str | None
- steps: list[TraceStepResponse]
