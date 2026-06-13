# 临期食物消息提醒功能设计

## 概述

为智能冰箱食材管理系统新增消息通知功能，当库存中的食物即将到期时，系统自动为每个用户生成临期提醒消息，用户可通过导航栏铃铛图标查看未读消息。

## 数据模型

### notifications 表

| 字段 | 类型 | 说明 |
|---|---|---|
| `id` | UUID | 主键 |
| `user_id` | UUID | FK -> users，消息所属用户 |
| `type` | VARCHAR(50) | 消息类型，如 `expiry_warning` |
| `title` | VARCHAR(200) | 消息标题，如"蔬菜即将过期" |
| `content` | TEXT | 消息内容，如"西红柿还有2天过期" |
| `related_item_id` | UUID | FK -> inventory，关联的食材 |
| `is_read` | BOOLEAN | 默认 false，用户已读/未读状态 |
| `created_at` | TIMESTAMP | 创建时间 |

- 每条记录关联一个用户，每个用户对同一食材有独立的消息记录和已读状态
- 同一食材对同一用户不重复生成（通过 `user_id` + `related_item_id` 唯一约束）

### category_thresholds 表

| 字段 | 类型 | 说明 |
|---|---|---|
| `id` | UUID | 主键 |
| `category` | VARCHAR(50) | 食物类别（vegetables, meat, dairy, fruit, grains, seafood, other） |
| `days_before_expiry` | INTEGER | 临期提醒天数 |
| `created_at` | TIMESTAMP | 创建时间 |

预设数据：

| 类别 | 临期天数 |
|---|---|
| vegetables | 3 |
| fruit | 3 |
| meat | 2 |
| seafood | 2 |
| dairy | 3 |
| grains | 7 |
| other | 5 |

## 后端 API

### 消息接口

| 方法 | 路径 | 说明 |
|---|---|---|
| `GET` | `/api/v1/notifications` | 获取当前用户的临期消息列表（触发实时生成） |
| `GET` | `/api/v1/notifications/count` | 获取未读消息数量（用于铃铛红点） |
| `PUT` | `/api/v1/notifications/{id}/read` | 标记单条消息为已读 |
| `PUT` | `/api/v1/notifications/read-all` | 全部标记已读 |

### 阈值接口

| 方法 | 路径 | 说明 |
|---|---|---|
| `GET` | `/api/v1/category-thresholds` | 获取所有类别的临期阈值 |
| `PUT` | `/api/v1/category-thresholds/{id}` | 更新某个类别的阈值 |

### 消息生成逻辑

1. 用户请求 `GET /api/v1/notifications` 时触发
2. 后端查询共享库存中所有 `status = IN_STOCK` 且 `expire_at` 不为空的食材
3. 根据食材类别查找对应的 `days_before_expiry` 阈值，无匹配类别时使用 `other` 的阈值
4. 筛选出 `expire_at - now <= days_before_expiry` 的食材（包含已过期的，即剩余天数 <= 0）
5. 为当前用户生成通知记录（如已存在则跳过）
6. 返回该用户的所有通知列表，按剩余天数升序排列（已过期的排在最前面）

## 前端 UI

### 导航栏改动

在顶部导航栏右侧（用户头像旁边）新增铃铛图标：
- 使用 Element Plus 的 `el-badge` 组件显示未读数量
- 未读数为 0 时隐藏红点
- 使用 `el-icon` 的 Bell 图标

### 铃铛弹窗

点击铃铛弹出 `el-popover`：
- 顶部：未读数量统计 + "全部已读"按钮
- 消息列表：每条消息显示食物名称、剩余天数、过期日期
- 点击消息可跳转到库存页面对应食材
- 消息按剩余天数升序排列（最紧急的在最上面）
- 已读消息样式变淡

### 触发时机

- 页面加载时调用 `GET /notifications/count` 获取未读数
- 点击铃铛时调用 `GET /notifications` 获取完整列表
- 标记已读后刷新计数

## 错误处理

- 消息生成失败不影响库存查询（降级为空列表）
- 标记已读失败时提示用户重试
- 未登录用户不显示铃铛图标
