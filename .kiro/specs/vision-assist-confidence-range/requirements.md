# Requirements Document

## Introduction

智能冰箱端侧（luckfox + YOLOv5n）通过 `POST /api/v1/admin/events/item` 上报 ITEM_IN 事件，事件载荷包含端侧识别给出的 `category` 与 `confidence`。后端 `agents/fridge_agent.py::handle_item_in` 当前以**硬编码**的单一阈值 `0.5` 作为是否调用云端视觉模型（qwen-vl-flash，`services/vision.py::recognize_food`）做辅助识别的判定条件；管理员手动入库 `POST /api/v1/admin/inventory` 中也存在硬编码 `0.6` 的同类逻辑。

本特性引入一个可在管理员后台运行时调整的"置信度区间触发策略"：仅当端侧上报的 `confidence` 落入区间 `[lower, upper]` 时才上报到云端做辅助识别。区间下界以下视为端侧已严重错检（云端也无法救回），区间上界以上视为端侧已足够可信（无需消耗云端 token）。区间存于数据库，管理员可在已有的"Agent 配置"页面修改后即时生效，不需重启服务、不改 .env、不改端侧上报协议。

本特性不引入新模型、不做"自动学习最优区间"、也不分类目维护多套区间（v1 范围内仅一个全局区间）。

## Glossary

- **VisionAssistConfig**：云端视觉辅助识别的策略配置实体，含 `lower`（区间下界）、`upper`（区间上界）、`updated_at`、`updated_by_admin_id`。全局唯一。
- **ConfidenceRange**：由 `lower` 与 `upper` 组成的闭区间 `[lower, upper]`，要求 `0 ≤ lower < upper ≤ 1`。
- **EdgeConfidence**：端侧 YOLOv5n 在 ITEM_IN 事件中上报的 `item.confidence` 浮点值，取值范围 `[0, 1]`。
- **VisionAssistService**：后端在 ITEM_IN 事件到达后判断是否调用 CloudVisionAssist 的决策组件，对应 `agents/fridge_agent.py::handle_item_in` 中的"低置信度时调云端视觉"逻辑。
- **CloudVisionAssist**：调用 `services/vision.py::recognize_food` 通过 qwen-vl-flash 对裁剪图做辅助分类，返回 `{category, confidence}`。
- **AdminAPI**：FastAPI 路由前缀 `/api/v1/admin`，受 `get_current_admin` 鉴权。
- **AdminUI**：Vue 前端的"管理员后台"中"Agent 配置"页面（既有页面）。
- **Trace**：现有 `agent_traces` 表中的工具链追踪记录。
- **AuditLog**：现有 `event_logs` / 统一日志通道（`save_log`）中针对配置变更写入的可审计记录。

## Requirements

### Requirement 1：可配置的置信度区间持久化

**User Story:** 作为管理员，我希望视觉辅助识别的"触发区间"以一行配置存在数据库里，这样我能在不改代码、不改环境变量、不重启服务的前提下随时调整它。

#### Acceptance Criteria

1. THE VisionAssistConfig SHALL be persisted as a single row in the database with fields `id`, `lower`, `upper`, `updated_at`, `updated_by_admin_id`.
2. THE VisionAssistConfig SHALL constrain `lower` and `upper` to be floating-point values in the closed interval `[0, 1]`.
3. THE VisionAssistConfig SHALL constrain `lower` to be strictly less than `upper`.
4. WHEN the VisionAssistConfig table is queried and contains zero rows, THE VisionAssistService SHALL initialize a row with `lower=0.3` and `upper=0.7` before continuing.
5. THE VisionAssistService SHALL load the active VisionAssistConfig from the database for each ITEM_IN event rather than caching it across process restarts.

### Requirement 2：管理员查询当前区间

**User Story:** 作为管理员，我希望在"Agent 配置"页面上看到当前生效的区间值、最近修改人、最近修改时间，这样我对策略现状有明确感知。

#### Acceptance Criteria

1. WHEN an authenticated admin sends `GET /api/v1/admin/agent/vision-assist-config`, THE AdminAPI SHALL return a JSON body containing `lower`, `upper`, `updated_at`, `updated_by_admin_id`, and `is_default` (true if values equal the system defaults `0.3` / `0.7`).
2. IF the requester is not an authenticated admin, THEN THE AdminAPI SHALL respond with HTTP 401.
3. WHEN the AdminUI loads the AgentConfig page, THE AdminUI SHALL display the current `lower` and `upper` with two-decimal precision.

### Requirement 3：管理员更新区间

**User Story:** 作为管理员，我希望提交新的 `lower` 和 `upper` 后立刻生效，并能看到结果与变更记录，这样我能快速调整策略并回溯改动。

#### Acceptance Criteria

1. WHEN an authenticated admin sends `PUT /api/v1/admin/agent/vision-assist-config` with body `{lower: float, upper: float}`, THE AdminAPI SHALL persist the new values atomically and return the updated VisionAssistConfig in the response body.
2. WHEN VisionAssistConfig is updated successfully, THE AdminAPI SHALL set `updated_at` to the server time of the update and `updated_by_admin_id` to the current admin's id.
3. WHEN VisionAssistConfig is updated successfully, THE AdminAPI SHALL write one AuditLog entry containing `event_type=VISION_ASSIST_CONFIG_UPDATE`, `actor=updated_by_admin_id`, `old={lower, upper}`, `new={lower, upper}`, and `timestamp`.
4. WHEN VisionAssistConfig is updated successfully, THE next ITEM_IN event arriving at VisionAssistService SHALL use the new range without server restart.
5. IF `lower` is missing, non-numeric, NaN, or outside `[0, 1]`, THEN THE AdminAPI SHALL respond with HTTP 400 and an error message identifying the invalid field.
6. IF `upper` is missing, non-numeric, NaN, or outside `[0, 1]`, THEN THE AdminAPI SHALL respond with HTTP 400 and an error message identifying the invalid field.
7. IF `lower >= upper`, THEN THE AdminAPI SHALL respond with HTTP 400 with the error message "lower must be strictly less than upper".
8. IF the requester is not an authenticated admin, THEN THE AdminAPI SHALL respond with HTTP 401 and SHALL NOT modify VisionAssistConfig.

### Requirement 4：ITEM_IN 事件中的区间触发判定

**User Story:** 作为系统，我希望端侧上报的物品在置信度落入区间内时才发起云端辅助识别，避免对低质量数据浪费 token，也避免对高置信度数据多此一举。

#### Acceptance Criteria

1. WHEN VisionAssistService processes an ITEM_IN event whose EdgeConfidence is within the closed interval `[lower, upper]` AND the event's `crop_image` is non-empty, THE VisionAssistService SHALL call CloudVisionAssist with the crop image.
2. WHEN VisionAssistService processes an ITEM_IN event whose EdgeConfidence is strictly less than `lower`, THE VisionAssistService SHALL skip CloudVisionAssist and use the edge-reported `category` for inventory creation.
3. WHEN VisionAssistService processes an ITEM_IN event whose EdgeConfidence is strictly greater than `upper`, THE VisionAssistService SHALL skip CloudVisionAssist and use the edge-reported `category` for inventory creation.
4. WHEN VisionAssistService processes an ITEM_IN event whose EdgeConfidence is within the closed interval `[lower, upper]` AND the event's `crop_image` is empty or missing, THE VisionAssistService SHALL skip CloudVisionAssist and use the edge-reported `category` for inventory creation.
5. WHEN CloudVisionAssist returns a result whose confidence is greater than EdgeConfidence, THE VisionAssistService SHALL replace the inventory record's `category` with the CloudVisionAssist result.
6. WHEN CloudVisionAssist returns a result whose confidence is less than or equal to EdgeConfidence, THE VisionAssistService SHALL keep the edge-reported `category` for the inventory record.
7. IF CloudVisionAssist raises an exception or returns `category=="unknown"`, THEN THE VisionAssistService SHALL keep the edge-reported `category` and continue inventory creation.

### Requirement 5：决策可观测性

**User Story:** 作为管理员，我希望每次"是否触发云端辅助识别"的决策都能在 trace 与日志里看到，这样我能调试某个具体物品为什么被或没被云端复核。

#### Acceptance Criteria

1. WHEN VisionAssistService completes its decision for an ITEM_IN event, THE VisionAssistService SHALL write one trace step to `agent_traces` with `tool_name="vision_assist_decide"` and `tool_input` containing `edge_confidence`, `lower`, `upper`, `has_crop_image`.
2. THE same trace step SHALL include `tool_output` containing `decision` (one of `TRIGGERED`, `SKIPPED_BELOW_LOWER`, `SKIPPED_ABOVE_UPPER`, `SKIPPED_NO_CROP_IMAGE`).
3. WHEN VisionAssistService writes the decision trace, THE VisionAssistService SHALL set `device_id` on the trace step to the device id from the originating event.
4. WHEN the decision is `TRIGGERED` and CloudVisionAssist returns a result, THE VisionAssistService SHALL also write the existing `vision_recognize` trace step recording the cloud result.

### Requirement 6：管理员后台 UI 入口

**User Story:** 作为管理员，我希望在已有的"Agent 配置"页面里就能调整区间，不需要去新页面或翻菜单。

#### Acceptance Criteria

1. THE AdminUI SHALL render a "视觉辅助识别策略" section on the AgentConfig page containing two numeric inputs labelled `lower` and `upper`, each accepting two-decimal floats in `[0, 1]`.
2. WHEN the admin enters `lower >= upper` or values outside `[0, 1]` and clicks save, THE AdminUI SHALL display an inline validation error and SHALL NOT issue the save request.
3. WHEN the save request returns HTTP 400 from the AdminAPI, THE AdminUI SHALL display the API's error message verbatim.
4. WHEN the save request succeeds, THE AdminUI SHALL show a confirmation toast and re-render the section with the returned `updated_at` and `updated_by_admin_id`.
5. THE AdminUI SHALL display the current values within 2 seconds of the AgentConfig page being loaded, assuming the AdminAPI responds normally.

### Requirement 7：管理员手动入库的复核策略复用

**User Story:** 作为管理员，我希望手动入库 `POST /api/v1/admin/inventory` 在 `agent_metadata.confidence` 出现时，也走和端侧 ITEM_IN 一致的区间判定逻辑，这样不存在两套阈值打架。

#### Acceptance Criteria

1. WHEN the AdminAPI processes `POST /api/v1/admin/inventory` AND the request body's `agent_metadata.confidence` is present AND `snapshot_path` is non-empty, THE AdminAPI SHALL apply the active VisionAssistConfig range to decide whether to call CloudVisionAssist.
2. WHEN the AdminAPI processes `POST /api/v1/admin/inventory` AND `agent_metadata.confidence` is absent, THE AdminAPI SHALL skip CloudVisionAssist regardless of the active VisionAssistConfig range.
3. THE AdminAPI SHALL remove the hardcoded `CONFIDENCE_THRESHOLD = 0.6` literal from `client/api/admin.py::create_inventory`, replacing it with a call that consults VisionAssistConfig.
4. THE handle_item_in path SHALL remove the hardcoded `CONFIDENCE_THRESHOLD = 0.5` literal from `client/agents/fridge_agent.py`, replacing it with a call that consults VisionAssistConfig.
5. WHERE QA confirms that manual inventory creation should use a different range than ITEM_IN (open question), THE design phase SHALL extend VisionAssistConfig with a per-source range; until that decision, both sources use the same range.

### Requirement 8：配置变更审计

**User Story:** 作为管理员，我希望配置历史是可追溯的，这样事后能解释"为什么那段时间区间是 0.4-0.6"。

#### Acceptance Criteria

1. WHEN VisionAssistConfig is created or updated, THE AdminAPI SHALL append one row to the unified log channel (`save_log`) with `source="admin"`, `event_type="VISION_ASSIST_CONFIG_UPDATE"`, `status="SUCCESS"`, and a JSON detail containing `old_lower`, `old_upper`, `new_lower`, `new_upper`, `admin_id`, `admin_username`.
2. THE AdminAPI SHALL preserve at least the last 90 days of VISION_ASSIST_CONFIG_UPDATE log entries (subject to existing log retention policy).
3. WHEN an admin views existing system logs filtered by `event_type=VISION_ASSIST_CONFIG_UPDATE`, THE AdminAPI SHALL return matching entries via the existing `GET /api/v1/admin/logs` endpoint.

### Requirement 9：默认值与首次引导

**User Story:** 作为系统部署者，我希望第一次启动时也有一组合理默认值在跑，无需先去手动配置。

#### Acceptance Criteria

1. WHEN the application starts and the VisionAssistConfig table is empty, THE VisionAssistService SHALL insert one row with `lower=0.3`, `upper=0.7`, `updated_by_admin_id=NULL`.
2. WHEN VisionAssistConfig has been initialized with default values and never modified, THE AdminAPI SHALL return `is_default=true` in the GET response.
3. WHEN VisionAssistConfig has been modified at least once, THE AdminAPI SHALL return `is_default=false` in the GET response.

### Requirement 10：范围与不做事项

**User Story:** 作为产品负责人，我希望本期需求边界清晰，避免 v1 实现走偏。

#### Acceptance Criteria

1. THE VisionAssistConfig SHALL store exactly one global range; per-category ranges are out of scope for v1.
2. THE VisionAssistService SHALL NOT learn or auto-tune the range based on historical decisions.
3. THE VisionAssistService SHALL NOT introduce a new vision model; CloudVisionAssist continues to use the existing `services/vision.py::recognize_food` and the model from `settings.VISION_MODEL`.
4. THE edge device upload protocol (`ItemEventRequest` schema and `/api/v1/admin/events/item` endpoint contract) SHALL remain unchanged by this feature.
