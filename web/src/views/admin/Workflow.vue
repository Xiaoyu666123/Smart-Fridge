<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import { ElMessage } from 'element-plus'
import {
  getTraceList, getTraceDetail, explainTrace,
  type TraceSummary, type TraceDetail,
} from '@/api/admin/trace'
import TraceCanvas2D from '@/components/TraceCanvas2D.vue'
import TraceTimeline from '@/components/TraceTimeline.vue'

const loading = ref(false)
const detailLoading = ref(false)
const traces = ref<TraceSummary[]>([])
const selectedTrace = ref<TraceDetail | null>(null)

// 视图模式：canvas（画布图谱，默认，交互+播放动画）/ timeline（时间线，按序阅读）
const viewMode = ref<'canvas' | 'timeline'>('canvas')

const filterAgentType = ref('')

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
  explanation.value = ''   // 切换 trace 时清掉旧解释
  explainOpen.value = false
  try {
    selectedTrace.value = await getTraceDetail(traceId)
  } catch (e) {
    console.error(e)
  } finally {
    detailLoading.value = false
  }
}

// ---- AI 解释 ----
const explanation = ref<string>('')
const explainLoading = ref(false)
const explainOpen = ref(false)

async function loadExplain() {
  if (!selectedTrace.value) return
  explainOpen.value = true
  if (explanation.value) return  // 已有就不重新拉
  explainLoading.value = true
  try {
    const res = await explainTrace(selectedTrace.value.trace_id)
    explanation.value = res.explanation || '暂无解释'
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail || 'AI 解释失败')
    explanation.value = '暂时无法生成解释，请稍后再试。'
  } finally {
    explainLoading.value = false
  }
}

async function regenerateExplain() {
  explanation.value = ''
  await loadExplain()
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
            <el-radio-group v-model="viewMode" size="small">
              <el-radio-button value="canvas">图谱</el-radio-button>
              <el-radio-button value="timeline">时间线</el-radio-button>
            </el-radio-group>
            <span class="stat-item">
              <el-icon :size="14"><Timer /></el-icon>
              {{ totalDuration }}
            </span>
            <span class="stat-item">
              <el-icon :size="14"><List /></el-icon>
              {{ selectedTrace.steps.length }} 步
            </span>
            <el-button
              type="primary"
              size="small"
              :loading="explainLoading"
              @click="loadExplain"
              class="explain-btn"
            >
              <el-icon v-if="!explainLoading"><MagicStick /></el-icon>
              {{ explanation && explainOpen ? '收起 AI 解释' : 'AI 解释决策' }}
            </el-button>
          </div>
        </div>
      </template>

      <div v-if="!selectedTrace" v-loading="detailLoading" class="empty-detail">
        <div class="empty-icon-bg-lg">
          <el-icon :size="36" color="var(--brand-primary)"><Connection /></el-icon>
        </div>
        <p style="margin-top: 14px; color: var(--text-placeholder)">选择左侧追踪记录查看工具链</p>
      </div>

      <template v-else>
        <!-- AI 解释面板 -->
        <transition name="explain">
          <div v-if="explainOpen" class="explain-panel" v-loading="explainLoading">
            <div class="explain-header">
              <div class="explain-title">
                <span class="explain-icon">🧠</span>
                <span>AI 用一段话解释这次决策</span>
              </div>
              <div class="explain-actions">
                <el-button link size="small" :loading="explainLoading" @click="regenerateExplain">
                  <el-icon><Refresh /></el-icon> 重新生成
                </el-button>
                <el-icon class="explain-close" @click="explainOpen = false"><Close /></el-icon>
              </div>
            </div>
            <div v-if="explanation" class="explain-body">
              <span class="explain-quote">"</span>
              {{ explanation }}
              <span class="explain-quote">"</span>
            </div>
            <div v-else class="explain-loading-tip">
              正在让 AI 分析这条 {{ selectedTrace.steps.length }} 步的工具链…
            </div>
          </div>
        </transition>

        <div class="view-host">
          <TraceTimeline v-if="viewMode === 'timeline'" :steps="selectedTrace.steps" />
          <TraceCanvas2D v-else :steps="selectedTrace.steps" />
        </div>
      </template>
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
  background: var(--bg-soft);
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
  align-items: center;
  gap: 14px;
  font-size: 13px;
  color: var(--text-secondary);
  flex-wrap: wrap;
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

.view-host {
  flex: 1;
  min-height: 0;
  overflow: hidden;
  display: flex;
  flex-direction: column;
}

.explain-btn {
  background: linear-gradient(135deg, var(--brand-primary), var(--brand-primary-dark)) !important;
  border-color: transparent !important;
  font-weight: 600;
  box-shadow: 0 4px 10px rgba(14, 165, 233, 0.30);
}

.explain-btn:hover {
  transform: translateY(-1px);
  box-shadow: 0 6px 14px rgba(14, 165, 233, 0.40);
}

.explain-panel {
  position: relative;
  margin: 0 0 14px 0;
  padding: 16px 20px;
  border-radius: 12px;
  background: linear-gradient(135deg, rgba(14, 165, 233, 0.10), rgba(6, 182, 212, 0.06)), var(--bg-card);
  border: 1px solid rgba(14, 165, 233, 0.4);
  box-shadow: 0 6px 18px rgba(14, 165, 233, 0.10);
  flex-shrink: 0;
  overflow: hidden;
}

.explain-panel::before {
  content: '';
  position: absolute;
  top: -30px;
  right: -30px;
  width: 140px;
  height: 140px;
  background: radial-gradient(circle, rgba(14, 165, 233, 0.20) 0%, transparent 60%);
  pointer-events: none;
}

.explain-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 10px;
  position: relative;
}

.explain-title {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 14px;
  font-weight: 700;
  color: var(--text-primary);
}

.explain-icon {
  font-size: 18px;
  line-height: 1;
}

.explain-actions {
  display: flex;
  align-items: center;
  gap: 6px;
}

.explain-close {
  cursor: pointer;
  color: var(--text-placeholder);
  font-size: 16px;
  padding: 4px;
  transition: color 0.18s;
}

.explain-close:hover {
  color: var(--text-primary);
}

.explain-body {
  position: relative;
  font-size: 14px;
  line-height: 1.75;
  color: var(--text-primary);
  padding: 4px 0;
}

.explain-quote {
  font-size: 24px;
  color: var(--brand-primary);
  font-family: 'Georgia', serif;
  vertical-align: -4px;
  margin: 0 4px;
  opacity: 0.5;
}

.explain-loading-tip {
  font-size: 13px;
  color: var(--text-secondary);
  text-align: center;
  padding: 18px 0;
}

.explain-enter-active,
.explain-leave-active {
  transition: all 0.32s cubic-bezier(0.4, 0, 0.2, 1);
}

.explain-enter-from,
.explain-leave-to {
  opacity: 0;
  transform: translateY(-8px);
  max-height: 0;
}

.explain-enter-to,
.explain-leave-from {
  max-height: 400px;
}
</style>
