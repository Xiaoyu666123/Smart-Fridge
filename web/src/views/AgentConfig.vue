<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { getAgentConfig, type AgentConfig } from '../api/agent'

const loading = ref(true)
const config = ref<AgentConfig>({
  vision_model: '',
  vision_status: '未连接',
  llm_model: '',
  llm_status: '未连接',
})

async function fetchConfig() {
  loading.value = true
  try {
    config.value = await getAgentConfig()
  } catch (e) {
    console.error('获取配置失败', e)
  } finally {
    loading.value = false
  }
}

onMounted(fetchConfig)
</script>

<template>
  <div v-loading="loading">
    <el-row :gutter="16">
      <el-col :span="12">
        <el-card shadow="never" class="model-card">
          <div class="model-header">
            <div class="model-icon" style="background: var(--brand-primary-light); color: var(--brand-primary)">
              <el-icon :size="24"><Camera /></el-icon>
            </div>
            <span class="model-title">视觉模型</span>
          </div>
          <el-descriptions :column="1" border>
            <el-descriptions-item label="模型名称">{{ config.vision_model || '-' }}</el-descriptions-item>
            <el-descriptions-item label="连接状态">
              <div class="status-dot-wrap">
                <span :class="['status-dot', config.vision_status === '已连接' ? 'online' : 'offline']"></span>
                <el-tag :type="config.vision_status === '已连接' ? 'success' : 'danger'" size="small" round>
                  {{ config.vision_status }}
                </el-tag>
              </div>
            </el-descriptions-item>
          </el-descriptions>
        </el-card>
      </el-col>
      <el-col :span="12">
        <el-card shadow="never" class="model-card">
          <div class="model-header">
            <div class="model-icon" style="background: #e8f7e8; color: #00b42a">
              <el-icon :size="24"><ChatDotRound /></el-icon>
            </div>
            <span class="model-title">语言模型</span>
          </div>
          <el-descriptions :column="1" border>
            <el-descriptions-item label="模型名称">{{ config.llm_model || '-' }}</el-descriptions-item>
            <el-descriptions-item label="连接状态">
              <div class="status-dot-wrap">
                <span :class="['status-dot', config.llm_status === '已连接' ? 'online' : 'offline']"></span>
                <el-tag :type="config.llm_status === '已连接' ? 'success' : 'danger'" size="small" round>
                  {{ config.llm_status }}
                </el-tag>
              </div>
            </el-descriptions-item>
          </el-descriptions>
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<style scoped>
.model-card {
  height: 100%;
}

.model-header {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 16px;
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
  font-size: 16px;
  font-weight: 600;
}

.status-dot-wrap {
  display: flex;
  align-items: center;
  gap: 8px;
}

.status-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
}

.status-dot.online {
  background: #00b42a;
  box-shadow: 0 0 6px #00b42a80;
}

.status-dot.offline {
  background: #f53f3f;
  box-shadow: 0 0 6px #f53f3f80;
}
</style>
