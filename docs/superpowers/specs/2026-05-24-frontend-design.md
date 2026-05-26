# 智能冰箱前端系统设计文档

## 概述

为智能冰箱食材管理系统构建 Vue 3 前端，包含库存概览、AI 食谱推荐对话、食材识别、偏好设置等功能页面，支持浅色/深色主题切换。

## 技术栈

| 组件 | 选型 |
|------|------|
| 框架 | Vue 3 + TypeScript + Composition API |
| UI 组件库 | Element Plus |
| 路由 | Vue Router |
| 状态管理 | Pinia |
| HTTP | Axios |
| 构建工具 | Vite |

## 目录结构

```
web/
├── src/
│   ├── api/                  # API 请求封装
│   │   ├── index.ts          # axios 实例（baseURL、拦截器）
│   │   ├── inventory.ts      # 库存接口
│   │   ├── agent.ts          # Agent 接口
│   │   └── event.ts          # 事件接口
│   ├── views/                # 页面组件
│   │   ├── Inventory.vue     # 库存概览
│   │   ├── Chat.vue          # AI 食谱推荐
│   │   ├── Recognize.vue     # 食材识别
│   │   ├── Preferences.vue   # 偏好设置
│   │   ├── AgentConfig.vue   # Agent 管理（占位）
│   │   ├── Workflow.vue      # 工作流管理（占位）
│   │   └── Logs.vue          # 系统日志（占位）
│   ├── components/           # 公共组件
│   │   ├── Layout.vue        # 侧边栏 + 顶栏布局
│   │   ├── ChatMessage.vue   # 聊天气泡组件
│   │   └── FoodCard.vue      # 食材卡片组件
│   ├── stores/               # Pinia 状态管理
│   │   ├── theme.ts          # 主题切换（浅色/深色）
│   │   └── chat.ts           # 对话状态
│   ├── router/
│   │   └── index.ts          # 路由配置
│   ├── App.vue
│   ├── main.ts
│   └── style.css             # 全局样式 + CSS 变量
├── index.html
├── package.json
├── vite.config.ts
└── tsconfig.json
```

## 布局

左侧固定侧边栏导航 + 右侧内容区 + 顶部主题切换。

```
┌──────────┬──────────────────────────────────┐
│          │  顶部栏（标题 + 主题切换按钮）    │
│  侧边栏  ├──────────────────────────────────┤
│  导航菜单 │                                  │
│          │        内容区域                   │
│  - 库存   │                                  │
│  - AI对话 │                                  │
│  - 识别   │                                  │
│  - 偏好   │                                  │
│  - Agent  │                                  │
│  - 工作流 │                                  │
│  - 日志   │                                  │
└──────────┴──────────────────────────────────┘
```

## 页面设计

### 1. 库存概览 (Inventory.vue)

- Element Plus 表格展示食材列表
- 列：食材名称、设备ID、状态、剩余保鲜天数、入库时间、过期时间
- 保鲜状态颜色标记：绿色（充足）、黄色（即将过期）、红色（已过期）
- 筛选：按设备ID、按状态
- 调用：`GET /api/v1/inventory`

### 2. AI 食谱推荐 (Chat.vue)

- 左侧：对话历史列表（按 user_id 分组）
- 右侧：聊天窗口
  - 消息气泡：用户消息靠右灰色，AI 回复靠左蓝色
  - 底部输入框 + 发送按钮
  - 支持 Enter 发送
- 自动提取用户偏好并提示
- 调用：`POST /api/v1/agent/chat`

### 3. 食材识别 (Recognize.vue)

- 图片上传区域（拖拽或点击上传）
- 上传后显示识别结果卡片：
  - 食材类别
  - 置信度（进度条）
  - 保鲜天数
  - 存储建议
- 调用：`POST /api/v1/agent/recognize`

### 4. 偏好设置 (Preferences.vue)

- 表格展示用户偏好列表
- 列：偏好类型、偏好值、来源、创建时间
- 支持手动添加偏好（弹窗表单）
- 支持删除偏好
- 调用：`GET /api/v1/agent/preferences`

### 5. Agent 管理 (AgentConfig.vue) — 占位

- 展示 Agent 配置信息卡片：
  - 视觉模型连接状态
  - 语言模型连接状态
  - 默认城市
  - 当前季节
- 暂用静态数据，后续对接后端接口

### 6. 工作流管理 (Workflow.vue) — 占位

- 表格展示 Agent 处理事件的流水记录
- 列：时间、事件类型、食材、处理结果
- 暂用静态数据，后续对接后端接口

### 7. 系统日志 (Logs.vue) — 占位

- 表格展示系统日志
- 列：时间、级别、来源、消息
- 暂用静态数据，后续对接后端接口

## 主题切换

- 浅色/深色两套配色
- 使用 CSS 变量 + Element Plus 暗色模式
- 状态存 localStorage 持久化
- 切换按钮在顶部栏右侧

## Vite 代理配置

```ts
server: {
  port: 3000,
  proxy: {
    '/api': {
      target: 'http://localhost:8000',
      changeOrigin: true,
    }
  }
}
```

## API 对接

| 前端调用 | 后端接口 | 说明 |
|---------|---------|------|
| `inventoryApi.list()` | `GET /api/v1/inventory` | 获取库存列表 |
| `agentApi.chat()` | `POST /api/v1/agent/chat` | 对话推荐 |
| `agentApi.recognize()` | `POST /api/v1/agent/recognize` | 图片识别 |
| `agentApi.getPreferences()` | `GET /api/v1/agent/preferences` | 获取偏好 |
| `eventApi.list()` | `GET /api/v1/events` | 获取事件日志 |

## 路由配置

| 路径 | 页面 | 说明 |
|------|------|------|
| `/` | Inventory.vue | 默认首页 |
| `/chat` | Chat.vue | AI 食谱推荐 |
| `/recognize` | Recognize.vue | 食材识别 |
| `/preferences` | Preferences.vue | 偏好设置 |
| `/agent` | AgentConfig.vue | Agent 管理 |
| `/workflow` | Workflow.vue | 工作流管理 |
| `/logs` | Logs.vue | 系统日志 |
