CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "vector";

--库存状态表(inventory)
create table inventory(
    id uuid primary key default uuid_generate_v4(),
    device_id varchar(50) not null,
    category varchar(50) not null,
    status VARCHAR(20) NOT NULL DEFAULT 'IN_STOCK' CHECK (status IN ('IN_STOCK', 'OUT_PENDING', 'CONSUMED', 'EXPIRED')),-- 状态: IN_STOCK, OUT_PENDING, CONSUMED, EXPIRED
    remain_ratio decimal(5, 2) default 1.00,       -- 剩余比例，1.00代表满额，用于部分取出场景
    bbox jsonb,                                    -- 存放坐标: [x, y, w, h]
    feature_vector vector(1024),                    -- 存放由多模态模型提取的1024维视觉特征向量
    agent_metadata jsonb,                          -- 存放agents提取的结构化标签（如品牌，特征时间）
    snapshot_path varchar(255),                    -- 存放物品图片路径
    image_hash varchar(64),                        -- 图片字节级 SHA256，用于秒拦完全相同的图片
    label_text text,                                -- 标签 OCR 出的原始文字
    label_data jsonb,                               -- 解析后的结构化字段（brand/expire_date/...）
    label_snapshot_path varchar(255),               -- 标签裁剪图保存路径
    created_at timestamp default current_timestamp,
    update_at timestamp default current_timestamp
);

COMMENT ON TABLE inventory IS '冰箱实时库存与数字孪生记忆库';
COMMENT ON COLUMN inventory.status IS 'IN_STOCK(在库), OUT_PENDING(离库暂存等待确认), CONSUMED(完全消耗)';
COMMENT ON COLUMN inventory.feature_vector IS '用于跨帧 Re-ID 身份重识别的视觉特征';

-- 事件流水表
create table event_logs(
    id bigserial primary key,
    inventory_id uuid not null,
    event_type varchar(20) not null,
    confidence float,
    snapshot_path varchar(255),
    create_at timestamp default current_timestamp,

    --设置外键
    constraint fk_inventory
                       foreign key (inventory_id)
                       references inventory(id)
                       on delete cascade
);

COMMENT ON TABLE event_logs IS '物品出入库与状态变化的时序行为流水日志';

-- 创建自动更新update_at的触发器
-- 创建一个通用的函数，每次触发时更新时间
create or replace function update_modified_column()
returns trigger as $$
begin
    new.update_at = now();
    return new;
end;
$$ language 'plpgsql';

-- 将触发器绑定到inventory表
create trigger update_inventory_modtime
    before update on inventory
    for each row
    execute function update_modified_column();

-- 针对设备号和状态创建复合索引，加速“找某个冰箱里暂存的物品”的查询
CREATE INDEX idx_inventory_device_status ON inventory(device_id, status);

-- 针对分类创建索引，加速筛选
CREATE INDEX idx_inventory_category ON inventory(category);

-- HNSW 索引能在几十万级数据量下保持极低的毫秒级查询延迟
CREATE INDEX idx_inventory_vector
    ON inventory USING hnsw (feature_vector vector_cosine_ops);

ALTER TABLE inventory ADD COLUMN IF NOT EXISTS stored_at TIMESTAMP DEFAULT current_timestamp;
  -- 用户偏好表
  CREATE TABLE IF NOT EXISTS user_preferences (
      id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
      user_id VARCHAR(50) NOT NULL,
      preference_key VARCHAR(100) NOT NULL,
      preference_value TEXT NOT NULL,
      source VARCHAR(20) DEFAULT 'chat',
      created_at TIMESTAMP DEFAULT current_timestamp,
      updated_at TIMESTAMP DEFAULT current_timestamp
  );
  -- 对话历史表
  CREATE TABLE IF NOT EXISTS conversations (
      id BIGSERIAL PRIMARY KEY,
      user_id VARCHAR(50) NOT NULL,
      role VARCHAR(20) NOT NULL,
      content TEXT NOT NULL,
      created_at TIMESTAMP DEFAULT current_timestamp
  );

-- Agent 工具链追踪表
CREATE TABLE IF NOT EXISTS agent_traces (
    id BIGSERIAL PRIMARY KEY,
    trace_id UUID NOT NULL,
    agent_type VARCHAR(30) NOT NULL,
    step_order INTEGER NOT NULL,
    tool_name VARCHAR(50) NOT NULL,
    tool_input JSONB,
    tool_output JSONB,
    status VARCHAR(10) NOT NULL DEFAULT 'SUCCESS',
    duration_ms INTEGER,
    device_id VARCHAR(50),
    created_at TIMESTAMP DEFAULT current_timestamp
);

CREATE INDEX idx_traces_trace_id ON agent_traces(trace_id);
CREATE INDEX idx_traces_agent_type ON agent_traces(agent_type);
CREATE INDEX idx_traces_device_id ON agent_traces(device_id);
CREATE INDEX idx_traces_created_at ON agent_traces(created_at DESC);

-- 用户表（普通用户）
CREATE TABLE IF NOT EXISTS users (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    username VARCHAR(50) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    created_at TIMESTAMP DEFAULT current_timestamp
);

CREATE INDEX idx_users_username ON users(username);

-- 管理员表（与普通用户表完全分离，独立 JWT 密钥）
CREATE TABLE IF NOT EXISTS admins (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    username VARCHAR(50) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    real_name VARCHAR(50),
    created_at TIMESTAMP DEFAULT current_timestamp
);

CREATE INDEX idx_admins_username ON admins(username);

-- 通知表
CREATE TABLE IF NOT EXISTS notifications (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    type VARCHAR(50) NOT NULL DEFAULT 'expiry_warning',
    title VARCHAR(200) NOT NULL,
    content TEXT NOT NULL,
    related_item_id UUID REFERENCES inventory(id) ON DELETE CASCADE,
    notice_date DATE,
    is_read BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT current_timestamp,
    CONSTRAINT uq_notification_user_item_date UNIQUE (user_id, related_item_id, notice_date)
);

CREATE INDEX idx_notifications_user ON notifications(user_id);
CREATE INDEX idx_notifications_read ON notifications(user_id, is_read);

-- 类别临期阈值表
CREATE TABLE IF NOT EXISTS category_thresholds (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    category VARCHAR(50) UNIQUE NOT NULL,
    days_before_expiry INTEGER NOT NULL DEFAULT 5,
    unit_price NUMERIC(10, 2),                    -- 单件参考价（CNY），用于浪费金额估算
    created_at TIMESTAMP DEFAULT current_timestamp
);

-- 标签缓冲表：端侧先扫标签 -> 后端 OCR 解析 -> 暂存 -> 等物品入库时关联
-- 设计：device_id + 5min TTL，consumed_at 标记是否已挂到 inventory，过期未消费的会被懒清理
CREATE TABLE IF NOT EXISTS pending_labels (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    device_id VARCHAR(50) NOT NULL,
    label_image_path VARCHAR(255),
    label_text TEXT,
    label_data JSONB,
    created_at TIMESTAMP DEFAULT current_timestamp,
    expires_at TIMESTAMP NOT NULL,
    consumed_at TIMESTAMP,
    consumed_by_inventory_id UUID REFERENCES inventory(id) ON DELETE SET NULL
);

-- 加速"找该设备最近未消费的标签"
CREATE INDEX IF NOT EXISTS idx_pending_labels_active
    ON pending_labels (device_id, expires_at)
    WHERE consumed_at IS NULL;

CREATE INDEX IF NOT EXISTS idx_pending_labels_created
    ON pending_labels (created_at DESC);

COMMENT ON TABLE pending_labels IS '端侧扫描标签后的临时缓冲，等物品入库事件到达时与 inventory 关联';
COMMENT ON COLUMN pending_labels.consumed_at IS 'NULL 表示待消费；非 NULL 表示已挂到 inventory';
COMMENT ON COLUMN pending_labels.expires_at IS '过期时间，默认 created_at + 5 分钟';


-- ========================================================
-- 已有数据库的迁移（仅当从旧版本升级时手工执行一次）
-- ========================================================
-- 1) 把现有 admin 账户从 users 搬到 admins
-- INSERT INTO admins (username, password_hash, created_at)
-- SELECT username, password_hash, created_at FROM users WHERE role = 'admin'
-- ON CONFLICT (username) DO NOTHING;
--
-- 2) 删掉 users 表里的管理员行
-- DELETE FROM users WHERE role = 'admin';
--
-- 3) 删 role 列与对应约束
-- ALTER TABLE users DROP CONSTRAINT IF EXISTS ck_user_role;
-- ALTER TABLE users DROP COLUMN IF EXISTS role;


-- 迁移：给 inventory 表加 image_hash 列（旧库执行一次）
-- ALTER TABLE inventory ADD COLUMN IF NOT EXISTS image_hash VARCHAR(64);
-- CREATE INDEX IF NOT EXISTS idx_inventory_image_hash ON inventory(image_hash);


-- 迁移：notifications 加 notice_date 列 + 改唯一约束（旧库执行一次）
-- ALTER TABLE notifications ADD COLUMN IF NOT EXISTS notice_date DATE;
-- UPDATE notifications SET notice_date = created_at::date WHERE notice_date IS NULL;
-- ALTER TABLE notifications DROP CONSTRAINT IF EXISTS uq_notification_user_item;
-- ALTER TABLE notifications ADD CONSTRAINT uq_notification_user_item_date
--   UNIQUE (user_id, related_item_id, notice_date);


-- 迁移：inventory 加 label_text / label_data / label_snapshot_path 三列（旧库执行一次）
-- ALTER TABLE inventory ADD COLUMN IF NOT EXISTS label_text TEXT;
-- ALTER TABLE inventory ADD COLUMN IF NOT EXISTS label_data JSONB;
-- ALTER TABLE inventory ADD COLUMN IF NOT EXISTS label_snapshot_path VARCHAR(255);
--
-- 迁移：新建 pending_labels 表（旧库执行一次，新库由 Base.metadata.create_all 自动建）
-- 直接执行上面的 CREATE TABLE IF NOT EXISTS pending_labels (...) 语句即可。


-- LLM/视觉/向量 API 调用计量表（追踪 token 消耗与费用）
CREATE TABLE IF NOT EXISTS llm_usage (
    id BIGSERIAL PRIMARY KEY,
    provider VARCHAR(20) NOT NULL,        -- llm / vision / embedding
    model VARCHAR(100) NOT NULL,
    endpoint VARCHAR(50),                  -- recipe / freshness / preference_extract / vision_recognize / detect / label_parse / embedding ...
    user_id VARCHAR(50),                   -- 触发本次调用的用户（可空，端侧/后台触发的没有）
    prompt_tokens INTEGER DEFAULT 0,
    completion_tokens INTEGER DEFAULT 0,
    total_tokens INTEGER DEFAULT 0,
    cost_usd NUMERIC(10, 6) DEFAULT 0,    -- 估算费用（按本地表查 model 单价）
    duration_ms INTEGER,
    status VARCHAR(10) DEFAULT 'SUCCESS', -- SUCCESS / FAILED
    created_at TIMESTAMP DEFAULT current_timestamp
);

CREATE INDEX IF NOT EXISTS idx_llm_usage_created ON llm_usage(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_llm_usage_provider ON llm_usage(provider);
CREATE INDEX IF NOT EXISTS idx_llm_usage_user ON llm_usage(user_id);
CREATE INDEX IF NOT EXISTS idx_llm_usage_model ON llm_usage(model);

COMMENT ON TABLE llm_usage IS '云端 API 调用 token 消耗与费用追踪';

-- 迁移：新建 llm_usage 表（旧库执行一次，新库由 Base.metadata.create_all 自动建）
-- 直接执行上面的 CREATE TABLE IF NOT EXISTS llm_usage 语句即可。


-- 用户收藏的食谱
CREATE TABLE IF NOT EXISTS saved_recipes (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id VARCHAR(50) NOT NULL,
    name VARCHAR(100) NOT NULL,                 -- 食谱名（"番茄炒蛋"）
    summary TEXT,                                -- 简介（一两句）
    prep_time INTEGER,                           -- 预计耗时（分钟）
    difficulty VARCHAR(20),                      -- 难度（简单/中等/困难）
    ingredients JSONB,                           -- 原材料 list[{"name":"番茄","amount":"2个"}]
    steps JSONB,                                 -- 步骤 list[str]
    tags JSONB,                                  -- 标签 list[str]（清淡/快手/下饭...）
    source VARCHAR(20) DEFAULT 'chat',           -- chat / manual
    cooked_count INTEGER DEFAULT 0,              -- 用户标记"做过"的次数
    last_cooked_at TIMESTAMP,                    -- 最近一次做的时间
    rating INTEGER,                              -- 1-5 星评分，未评分时 NULL
    notes TEXT,                                  -- 自由笔记
    created_at TIMESTAMP DEFAULT current_timestamp
);

CREATE INDEX IF NOT EXISTS idx_saved_recipes_user ON saved_recipes(user_id, created_at DESC);

COMMENT ON TABLE saved_recipes IS '用户收藏的食谱（结构化），支持打卡"做过了"';

-- 迁移：新建 saved_recipes 表（旧库执行一次，新库由 Base.metadata.create_all 自动建）
-- 直接执行上面的 CREATE TABLE IF NOT EXISTS saved_recipes 语句即可。

-- 迁移：给 saved_recipes 加 rating + notes 列（旧库执行一次）
-- ALTER TABLE saved_recipes ADD COLUMN IF NOT EXISTS rating INTEGER;
-- ALTER TABLE saved_recipes ADD COLUMN IF NOT EXISTS notes TEXT;


-- 视觉辅助识别策略：单行配置
-- 端侧上报置信度落入 [lower, upper] 时才触发云端 vision 辅助识别
CREATE TABLE IF NOT EXISTS vision_assist_config (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    "lower" NUMERIC(3, 2) NOT NULL DEFAULT 0.30 CHECK ("lower" >= 0 AND "lower" <= 1),
    "upper" NUMERIC(3, 2) NOT NULL DEFAULT 0.70 CHECK ("upper" >= 0 AND "upper" <= 1),
    updated_at TIMESTAMP DEFAULT current_timestamp,
    updated_by_admin_id UUID REFERENCES admins(id) ON DELETE SET NULL,
    CONSTRAINT ck_vac_lower_lt_upper CHECK ("lower" < "upper")
);

COMMENT ON TABLE vision_assist_config IS '云端视觉辅助识别触发区间策略（全局单行）';

-- 迁移：新建 vision_assist_config 表（旧库执行一次，新库由 Base.metadata.create_all 自动建）
-- 直接执行上面的 CREATE TABLE IF NOT EXISTS vision_assist_config 语句即可。


-- ========================================================
-- 设备表 + 设备心跳流水
-- ========================================================
CREATE TABLE IF NOT EXISTS devices (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    device_id VARCHAR(50) UNIQUE NOT NULL,
    name VARCHAR(100),
    location VARCHAR(100),
    description TEXT,
    status VARCHAR(20) DEFAULT 'online',          -- online / idle / offline
    last_seen_at TIMESTAMP,
    last_event_type VARCHAR(30),
    heartbeat_count INTEGER DEFAULT 0,
    registered_at TIMESTAMP DEFAULT current_timestamp
);

CREATE INDEX IF NOT EXISTS idx_devices_device_id ON devices(device_id);
CREATE INDEX IF NOT EXISTS idx_devices_status ON devices(status);

COMMENT ON TABLE devices IS '端侧设备登记表，第一次上报自动注册';

CREATE TABLE IF NOT EXISTS device_heartbeats (
    id BIGSERIAL PRIMARY KEY,
    device_id VARCHAR(50) NOT NULL,
    event VARCHAR(30) DEFAULT 'heartbeat',         -- heartbeat / startup / item_in / item_out / label_scan
    payload JSONB,
    created_at TIMESTAMP DEFAULT current_timestamp
);

CREATE INDEX IF NOT EXISTS idx_dev_heartbeats_device_time
    ON device_heartbeats(device_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_dev_heartbeats_created
    ON device_heartbeats(created_at DESC);

COMMENT ON TABLE device_heartbeats IS '设备心跳流水（保留近 24-48 小时，可定期裁剪）';

-- 迁移：新建 devices / device_heartbeats（旧库执行一次，新库由 Base.metadata.create_all 自动建）
-- 直接执行上面的 CREATE TABLE IF NOT EXISTS devices / device_heartbeats 即可。


-- 端侧联调收件箱：保存端侧上报摘要、规范化结构、处理状态和错误信息
CREATE TABLE IF NOT EXISTS device_raw_events (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    device_id VARCHAR(50),
    event_type VARCHAR(30),
    raw_payload JSONB,
    normalized_payload JSONB,
    status VARCHAR(20) NOT NULL DEFAULT 'received'
        CHECK (status IN ('received', 'processing', 'success', 'failed', 'ignored')),
    error_message TEXT,
    related_inventory_ids JSONB,
    trace_id UUID,
    created_at TIMESTAMP DEFAULT current_timestamp,
    processed_at TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_device_raw_events_created
    ON device_raw_events(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_device_raw_events_device
    ON device_raw_events(device_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_device_raw_events_status
    ON device_raw_events(status, created_at DESC);

COMMENT ON TABLE device_raw_events IS '端侧联调原始事件收件箱，用于排查 JSON、图片和处理失败问题';

-- 迁移：新建 device_raw_events（旧库执行一次，新库由 Base.metadata.create_all 自动建）
-- 直接执行上面的 CREATE TABLE IF NOT EXISTS device_raw_events 即可。


-- 用户购物清单（shopping_items）
CREATE TABLE IF NOT EXISTS shopping_items (
    id uuid PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id VARCHAR(50) NOT NULL,
    name VARCHAR(50) NOT NULL,
    qty INTEGER DEFAULT 1,
    checked BOOLEAN DEFAULT FALSE,
    source VARCHAR(20) DEFAULT 'manual',           -- auto(系统建议) / manual(手动添加)
    created_at TIMESTAMP DEFAULT current_timestamp,
    CONSTRAINT uq_shopping_user_name UNIQUE (user_id, name)
);

CREATE INDEX IF NOT EXISTS idx_shopping_user ON shopping_items(user_id, created_at DESC);

COMMENT ON TABLE shopping_items IS '用户购物清单：auto 为系统根据消耗/库存自动建议，manual 为手动添加';

-- 迁移：新建 shopping_items（旧库执行一次，新库由 Base.metadata.create_all 自动建）
-- 直接执行上面的 CREATE TABLE IF NOT EXISTS shopping_items 即可。
