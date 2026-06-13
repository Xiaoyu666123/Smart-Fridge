<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import {
  getAgentConfig,
  updateAgentConfig,
  type AgentConfig,
  type AgentConfigUpdate,
} from '@/api/admin/agent'

const loading = ref(true)
const saving = ref(false)
const editing = ref(false)
const config = ref<AgentConfig>({
  vision: {
    provider: '',
    model: '',
    api_url: '',
    api_key_masked: null,
    status: '未连接',
    has_api_key: false,
  },
  llm: {
    provider: '',
    model: '',
    api_url: '',
    api_key_masked: null,
    status: '未连接',
    has_api_key: false,
  },
  vision_model: '',
  vision_status: '未连接',
  llm_model: '',
  llm_status: '未连接',
})

const form = ref<AgentConfigUpdate>({
  vision: { provider: 'dashscope', model: '', api_url: '', api_key: '' },
  llm: { provider: 'deepseek', model: '', api_url: '', api_key: '' },
})

const providerOptions = [
  { label: '阿里云 DashScope', value: 'dashscope' },
  { label: 'DeepSeek', value: 'deepseek' },
  { label: 'OpenAI', value: 'openai' },
  { label: '自定义', value: 'custom' },
]

function providerLabel(value: string) {
  return providerOptions.find((item) => item.value === value)?.label || value || '-'
}

function normalizeConfig(next: AgentConfig): AgentConfig {
  return {
    ...next,
    vision: next.vision || {
      provider: 'dashscope',
      model: next.vision_model || '',
      api_url: '',
      api_key_masked: null,
      status: next.vision_status || '未配置',
      has_api_key: false,
    },
    llm: next.llm || {
      provider: 'deepseek',
      model: next.llm_model || '',
      api_url: '',
      api_key_masked: null,
      status: next.llm_status || '未配置',
      has_api_key: false,
    },
  }
}

function applyConfig(next: AgentConfig) {
  const normalized = normalizeConfig(next)
  config.value = normalized
  form.value = {
    vision: {
      provider: normalized.vision.provider || 'dashscope',
      model: normalized.vision.model || normalized.vision_model || '',
      api_url: normalized.vision.api_url || '',
      api_key: '',
    },
    llm: {
      provider: normalized.llm.provider || 'deepseek',
      model: normalized.llm.model || normalized.llm_model || '',
      api_url: normalized.llm.api_url || '',
      api_key: '',
    },
  }
}

async function fetchConfig() {
  loading.value = true
  try {
    applyConfig(await getAgentConfig())
  } catch (e) {
    console.error('获取配置失败', e)
    ElMessage.error('获取 Agent 配置失败')
  } finally {
    loading.value = false
  }
}

function normalizePayload(): AgentConfigUpdate {
  return {
    vision: {
      provider: form.value.vision.provider,
      model: form.value.vision.model.trim(),
      api_url: form.value.vision.api_url.trim(),
      api_key: form.value.vision.api_key?.trim() || null,
    },
    llm: {
      provider: form.value.llm.provider,
      model: form.value.llm.model.trim(),
      api_url: form.value.llm.api_url.trim(),
      api_key: form.value.llm.api_key?.trim() || null,
    },
  }
}

function startEdit() {
  applyConfig(config.value)
  editing.value = true
}

function cancelEdit() {
  applyConfig(config.value)
  editing.value = false
}

async function saveConfig() {
  const payload = normalizePayload()
  if (!payload.vision.provider || !payload.vision.model || !payload.vision.api_url) {
    ElMessage.warning('请完整填写视觉模型的厂商、模型名称和 API 地址')
    return
  }
  if (!payload.llm.provider || !payload.llm.model || !payload.llm.api_url) {
    ElMessage.warning('请完整填写语言模型的厂商、模型名称和 API 地址')
    return
  }
  saving.value = true
  try {
    applyConfig(await updateAgentConfig(payload))
    editing.value = false
    ElMessage.success('Agent 模型配置已保存，新的调用将立即使用最新配置')
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail || '保存失败')
  } finally {
    saving.value = false
  }
}

onMounted(() => {
  fetchConfig()
})
</script>

<template>
  <div class="agent-config-page" v-loading="loading">
    <div v-if="!editing" class="page-toolbar">
      <el-button type="primary" @click="startEdit">
        <el-icon><Edit /></el-icon>
        编辑配置
      </el-button>
    </div>

    <el-alert
      v-if="editing"
      type="info"
      :closable="false"
      show-icon
      title="API Key 不会在页面回显；留空表示继续使用当前密钥，填写新值才会覆盖。"
    />

    <el-row :gutter="16">
      <el-col :xs="24" :lg="12">
        <el-card shadow="never" class="model-card">
          <div class="model-header">
            <div class="model-icon" style="background: var(--brand-primary-light); color: var(--brand-primary)">
              <el-icon :size="24"><Camera /></el-icon>
            </div>
            <div class="model-heading">
              <span class="model-title">视觉模型</span>
              <span class="model-sub">用于食材识别、整柜识别和标签视觉解析</span>
            </div>
            <el-tag :type="config.vision.status === '已连接' ? 'success' : 'warning'" size="small" round>
              {{ config.vision.status }}
            </el-tag>
          </div>

          <el-descriptions v-if="!editing" :column="1" border class="model-summary">
            <el-descriptions-item label="模型名称">
              {{ config.vision.model || config.vision_model || '-' }}
            </el-descriptions-item>
            <el-descriptions-item label="厂商">
              {{ providerLabel(config.vision.provider) }}
            </el-descriptions-item>
            <el-descriptions-item label="API 地址">
              <span class="api-url">{{ config.vision.api_url || '-' }}</span>
            </el-descriptions-item>
            <el-descriptions-item label="API Key">
              {{ config.vision.has_api_key ? config.vision.api_key_masked : '未配置' }}
            </el-descriptions-item>
            <el-descriptions-item label="连接状态">
              <span class="status-dot" :class="{ online: config.vision.status === '已连接' }" />
              {{ config.vision.status }}
            </el-descriptions-item>
          </el-descriptions>

          <el-form v-else label-position="top" class="config-form">
            <el-form-item label="厂商">
              <el-select v-model="form.vision.provider" style="width: 100%">
                <el-option v-for="p in providerOptions" :key="p.value" :label="p.label" :value="p.value" />
              </el-select>
            </el-form-item>
            <el-form-item label="模型名称">
              <el-input v-model="form.vision.model" placeholder="例如 qwen3-vl-flash" />
            </el-form-item>
            <el-form-item label="API 地址">
              <el-input v-model="form.vision.api_url" placeholder="https://.../chat/completions" />
            </el-form-item>
            <el-form-item label="API Key">
              <el-input
                v-model="form.vision.api_key"
                type="password"
                show-password
                :placeholder="config.vision.has_api_key ? `当前：${config.vision.api_key_masked}` : '请输入 API Key'"
              />
            </el-form-item>
          </el-form>
        </el-card>
      </el-col>
      <el-col :xs="24" :lg="12">
        <el-card shadow="never" class="model-card">
          <div class="model-header">
            <div class="model-icon" style="background: #e8f7e8; color: #00b42a">
              <el-icon :size="24"><ChatDotRound /></el-icon>
            </div>
            <div class="model-heading">
              <span class="model-title">语言模型</span>
              <span class="model-sub">用于食谱推荐、库存问答、偏好提取和解释生成</span>
            </div>
            <el-tag :type="config.llm.status === '已连接' ? 'success' : 'warning'" size="small" round>
              {{ config.llm.status }}
            </el-tag>
          </div>

          <el-descriptions v-if="!editing" :column="1" border class="model-summary">
            <el-descriptions-item label="模型名称">
              {{ config.llm.model || config.llm_model || '-' }}
            </el-descriptions-item>
            <el-descriptions-item label="厂商">
              {{ providerLabel(config.llm.provider) }}
            </el-descriptions-item>
            <el-descriptions-item label="API 地址">
              <span class="api-url">{{ config.llm.api_url || '-' }}</span>
            </el-descriptions-item>
            <el-descriptions-item label="API Key">
              {{ config.llm.has_api_key ? config.llm.api_key_masked : '未配置' }}
            </el-descriptions-item>
            <el-descriptions-item label="连接状态">
              <span class="status-dot" :class="{ online: config.llm.status === '已连接' }" />
              {{ config.llm.status }}
            </el-descriptions-item>
          </el-descriptions>

          <el-form v-else label-position="top" class="config-form">
            <el-form-item label="厂商">
              <el-select v-model="form.llm.provider" style="width: 100%">
                <el-option v-for="p in providerOptions" :key="p.value" :label="p.label" :value="p.value" />
              </el-select>
            </el-form-item>
            <el-form-item label="模型名称">
              <el-input v-model="form.llm.model" placeholder="例如 deepseek-v4-flash" />
            </el-form-item>
            <el-form-item label="API 地址">
              <el-input v-model="form.llm.api_url" placeholder="https://.../chat/completions" />
            </el-form-item>
            <el-form-item label="API Key">
              <el-input
                v-model="form.llm.api_key"
                type="password"
                show-password
                :placeholder="config.llm.has_api_key ? `当前：${config.llm.api_key_masked}` : '请输入 API Key'"
              />
            </el-form-item>
          </el-form>
        </el-card>
      </el-col>
    </el-row>

    <div v-if="editing" class="action-bar">
      <el-button @click="cancelEdit" :disabled="saving">取消</el-button>
      <el-button type="primary" :loading="saving" @click="saveConfig">保存模型配置</el-button>
    </div>
  </div>
</template>

<style scoped>
.agent-config-page {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.page-toolbar {
  display: flex;
  justify-content: flex-end;
}

.model-card {
  height: 100%;
}

.model-header {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 18px;
}

.model-icon {
  width: 44px;
  height: 44px;
  border-radius: 12px;
  display: flex;
  align-items: center;
  justify-content: center;
}

.model-title {
  display: block;
  font-size: 16px;
  font-weight: 600;
}

.model-heading {
  flex: 1;
  min-width: 0;
}

.model-sub {
  display: block;
  margin-top: 3px;
  color: var(--text-secondary);
  font-size: 12px;
  line-height: 1.4;
}

.config-form :deep(.el-form-item) {
  margin-bottom: 16px;
}

.model-summary :deep(.el-descriptions__table) {
  table-layout: fixed;
}

.model-summary :deep(.el-descriptions__label) {
  width: 112px;
  min-width: 112px;
  white-space: nowrap;
  word-break: keep-all;
  color: var(--text-secondary);
}

.model-summary :deep(.el-descriptions__content) {
  min-width: 0;
}

.api-url {
  display: inline-block;
  width: 100%;
  max-width: 100%;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.status-dot {
  display: inline-block;
  width: 8px;
  height: 8px;
  margin-right: 8px;
  border-radius: 999px;
  background: var(--el-color-warning);
}

.status-dot.online {
  background: #00b42a;
}

.action-bar {
  display: flex;
  justify-content: flex-end;
  gap: 10px;
  padding: 16px 0 0;
}

@media (max-width: 1199px) {
  .model-card {
    margin-bottom: 16px;
  }
}
</style>
