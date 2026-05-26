# 角色与任务目标
你是一个资深的 Python 后端架构师。请帮我从零搭建一个“智能冰箱食材管理系统”的后端服务。
该后端主要负责接收端侧设备发来的 AI 识别事件 JSON 数据，更新数据库状态，并为前端展示大屏提供 API 接口。

# 核心技术栈
* **框架：** FastAPI
* **数据库：** PostgreSQL (需支持 pgvector 插件)
* **ORM：** SQLAlchemy 2.0 (推荐使用异步，或标准的同步方式)
* **数据校验：** Pydantic V2
* **服务器：** Uvicorn

# 🛑 强制性开发规范 (CRITICAL)
1. **绝对禁止修改变量名：** 请严格按照我下文提供的数据库字段和 JSON 结构进行命名。在后续的修改和迭代中，**不得擅自更改我的变量名以保持与我原始实现的一致性**。
2. **模块化结构：** 请采用标准的 FastAPI 项目结构，分离功能模块（例如拆分出 `models`, `schemas`, `crud`, `api`, `database` 等），切勿将所有代码堆砌在单个文件中。
3. **异常处理：** 在 API 路由层做好 Try-Catch 处理，并返回规范的 HTTP 状态码和友好的 JSON 错误信息。

---

# 1. 数据库结构定义 (SQLAlchemy Models)
请基于以下要求生成 SQLAlchemy 的模型代码：

### 表1: `inventory` (库存状态表)
* `id`: UUID, 主键
* `device_id`: String(50), 设备号
* `category`: String(50), 分类
* `status`: String(20), 必须使用 CHECK 约束 ('IN_STOCK', 'OUT_PENDING', 'CONSUMED')，默认值为 'IN_STOCK'
* `remain_ratio`: Float, 默认值为 1.0
* `bbox`: JSONB, 坐标数组 [x, y, w, h]
* `feature_vector`: VECTOR(512), 视觉特征向量 (务必导入 pgvector 扩展)
* `agent_metadata`: JSONB, 拓展标签信息
* `created_at`: DateTime
* `updated_at`: DateTime

### 表2: `event_logs` (事件流水表)
* `id`: Integer (自增), 主键
* `inventory_id`: UUID, 外键，关联 inventory.id
* `event_type`: String(20), 事件类型 ('ITEM_IN', 'ITEM_OUT', 'ITEM_MOVED', 'AGENT_UPDATE')
* `confidence`: Float, 识别置信度
* `snapshot_path`: String(255), 截图存储路径
* `created_at`: DateTime

---

# 2. 接口及请求体要求 (Pydantic Schemas)
端侧会发送 JSON 数据到接口，请基于以下结构定义请求体验证：

### 事件A：物品变动 (ITEM_EVENT)
```json
{
  "device_id": "fridge_rv1106_01",
  "timestamp": 1716466178000,
  "event_type": "ITEM_IN", 
  "data": [
    {
      "local_track_id": 1002,
      "category": "fruit",
      "confidence": 0.89,
      "bbox": [120, 45, 60, 60],
      "crop_image": "base64_string..." 
    }
  ]
}