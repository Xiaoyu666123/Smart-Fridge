<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import { getTraceList, getTraceDetail, type TraceSummary, type TraceDetail } from '@/api/trace'
import TraceFlowChart from '@/components/TraceFlowChart.vue'

const loading = ref(false)
const detailLoading = ref(false)
const traces = ref<TraceSummary[]>([])
const selectedTrace = ref<TraceDetail | null>(null)

const filterAgentType = ref('')
const filterDeviceId = ref('')

const agentTypeLabels: Record<string, string> = {
  ITEM_IN: '食材入库',
  ITEM_OUT: '食材取出',
  CHAT: 'AI 对话',
}

async function fetchTraces() {
  loading.value = true
  try {
    const params: Record<string, any> = { limit: 50 }
    if (filterAgentType.value) params.agent_type = filterAgentType.value
    if (filterDeviceId.value) params.device_id = filterDeviceId.value
    traces.value = await getTraceList(params)
    selectedTrace.value = null
  } catch (e) {
    console.error(e)
  } finally {
    loading.value = false
  }
}

async function selectTrace(traceId: string) {
  detailLoading.value = true
  try {
    selectedTrace.value = await getTraceDetail(traceId)
  } catch (e) {
    console.error(e)
  } finally {
    detailLoading.value = false
  }
}

function getAgentTypeLabel(type: string): string {
  return agentTypeLabels[type] || type
}

function getAgentTypeTag(type: string): string {
  if (type === 'ITEM_IN') return 'success'
  if (type === 'ITEM_OUT') return 'warning'
  return 'primary'
}

function formatDuration(ms: number | null): string {
  if (ms === null || ms === undefined) return '-'
  if (ms < 1000) return `${ms}ms`
  return `${(ms / 1000).toFixed(1)}s`
}

function formatTime(dateStr: string | null): string {
  if (!dateStr) return '-'
  return new Date(dateStr).toLocaleString('zh-CN')
}

const totalDuration = computed(() => {
  if (!selectedTrace.value) return '-'
  const ms = selectedTrace.value.steps.reduce((sum, s) => sum + (s.duration_ms || 0), 0)
  return formatDuration(ms)
})

onMounted(fetchTraces)
</script>

<template>
  <div style="display: flex; gap: 16px; height: calc(100vh - 150px)">
    <!-- 左侧 trace 列表 -->
    <el-card shadow="never" style="width: 340px; flex-shrink: 0; display: flex; flex-direction: column">
      <template #header>
        <span class="card-title">工具链追踪</span>
      </template>

      <div style="margin-bottom: 12px; display: flex; gap: 8px; flex-wrap: wrap">
        <el-select v-model="filterAgentType" placeholder="类型" clearable size="small" style="width: 110px">
          <el-option label="食材入库" value="ITEM_IN" />
          <el-option label="食材取出" value="ITEM_OUT" />
          <el-option label="AI对话" value="CHAT" />
        </el-select>
        <el-input v-model="filterDeviceId" placeholder="设备ID" clearable size="small" style="width: 120px" />
        <el-button type="primary" size="small" @click="fetchTraces">查询</el-button>
      </div>

      <div style="flex: 1; overflow-y: auto">
        <div
          v-for="trace in traces"
          :key="trace.trace_id"
          :class="['trace-item', { active: selectedTrace?.trace_id === trace.trace_id }]"
          @click="selectTrace(trace.trace_id)"
        >
          <div style="display: flex; align-items: center; gap: 8px; margin-bottom: 6px">
            <el-tag :type="getAgentTypeTag(trace.agent_type)" size="small" round>
              {{ getAgentTypeLabel(trace.agent_type) }}
            </el-tag>
            <span v-if="trace.device_id" class="trace-device">{{ trace.device_id }}</span>
          </div>
          <div style="display: flex; justify-content: space-between; font-size: 12px; color: var(--text-secondary)">
            <span>{{ trace.step_count }} 步</span>
            <span>{{ formatDuration(trace.total_duration_ms) }}</span>
          </div>
          <div class="trace-time">
            {{ formatTime(trace.created_at) }}
          </div>
        </div>

        <div v-if="traces.length === 0 && !loading" class="empty-state">
          <div class="empty-icon-bg">
            <el-icon :size="28" color="var(--brand-primary)"><Connection /></el-icon>
          </div>
          <p style="margin-top: 10px; color: var(--text-placeholder); font-size: 13px">暂无追踪记录</p>
        </div>
      </div>
    </el-card>

    <!-- 右侧流程图 -->
    <el-card shadow="never" class="flow-card">
      <template #header>
        <div style="display: flex; align-items: center; justify-content: space-between">
          <span class="card-title">
            {{ selectedTrace ? getAgentTypeLabel(selectedTrace.agent_type) + ' 工具链' : '工具链详情' }}
          </span>
          <div v-if="selectedTrace" class="trace-stats">
            <span class="stat-item">
              <el-icon :size="14"><Timer /></el-icon>
              {{ totalDuration }}
            </span>
            <span class="stat-item">
              <el-icon :size="14"><List /></el-icon>
              {{ selectedTrace.steps.length }} 步
            </span>
          </div>
        </div>
      </template>

      <div v-if="!selectedTrace" v-loading="detailLoading" class="empty-detail">
        <div class="empty-icon-bg-lg">
          <el-icon :size="36" color="var(--brand-primary)"><Connection /></el-icon>
        </div>
        <p style="margin-top: 14px; color: var(--text-placeholder)">选择左侧追踪记录查看工具链</p>
      </div>

      <TraceFlowChart v-else :steps="selectedTrace.steps" />
    </el-card>
  </div>
</template>

<style scoped>
.card-title {
  font-size: 16px;
  font-weight: 600;
}

.trace-item {
  padding: 12px;
  border-radius: var(--radius-sm);
  cursor: pointer;
  margin-bottom: 6px;
  border: 1px solid transparent;
  transition: all 0.2s;
}

.trace-item:hover {
  background: var(--bg-color);
  border-color: var(--border-color);
}

.trace-item.active {
  background: var(--brand-primary-light);
  border-color: var(--brand-primary);
}

.trace-device {
  font-size: 12px;
  color: var(--text-secondary);
  background: #f2f3f5;
  padding: 1px 6px;
  border-radius: 4px;
}

.trace-time {
  font-size: 11px;
  color: var(--text-placeholder);
  margin-top: 4px;
}

.empty-state {
  text-align: center;
  padding: 40px 0;
}

.empty-icon-bg {
  width: 56px;
  height: 56px;
  border-radius: 50%;
  background: var(--brand-primary-light);
  display: flex;
  align-items: center;
  justify-content: center;
  margin: 0 auto;
}

.empty-detail {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  color: var(--text-placeholder);
}

.empty-icon-bg-lg {
  width: 72px;
  height: 72px;
  border-radius: 50%;
  background: var(--brand-primary-light);
  display: flex;
  align-items: center;
  justify-content: center;
}

.trace-stats {
  display: flex;
  gap: 16px;
  font-size: 13px;
  color: var(--text-secondary);
}

.stat-item {
  display: flex;
  align-items: center;
  gap: 4px;
}

.flow-card {
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  min-height: 0;
}

.flow-card :deep(.el-card__body) {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-height: 0;
  overflow: hidden;
}
</style>
