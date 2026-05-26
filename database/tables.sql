CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "vector";

--库存状态表(inventory)
create table inventory(
    id uuid primary key default uuid_generate_v4(),
    device_id varchar(50) not null,
    category varchar(50) not null,
    status VARCHAR(20) NOT NULL DEFAULT 'IN_STOCK' CHECK (status IN ('IN_STOCK', 'OUT_PENDING', 'CONSUMED')),-- 状态: IN_STOCK, OUT_PENDING, CONSUMED
    remain_ratio decimal(5, 2) default 1.00,       -- 剩余比例，1.00代表满额，用于部分取出场景
    bbox jsonb,                                    -- 存放坐标: [x, y, w, h]
    feature_vector vector(1024),                    -- 存放由多模态模型提取的1024维视觉特征向量
    agent_metadata jsonb,                          -- 存放agents提取的结构化标签（如品牌，特征时间）
    snapshot_path varchar(255),                    -- 存放物品图片路径
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

-- 用户表
CREATE TABLE IF NOT EXISTS users (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    username VARCHAR(50) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    role VARCHAR(20) NOT NULL DEFAULT 'user' CHECK (role IN ('user', 'admin')),
    created_at TIMESTAMP DEFAULT current_timestamp
);

CREATE INDEX idx_users_username ON users(username);
