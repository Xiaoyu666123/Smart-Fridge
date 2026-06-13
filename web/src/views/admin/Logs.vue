<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { getLogs, type LogEntry } from '@/api/admin/logs'

const loading = ref(false)
const logs = ref<LogEntry[]>([])
const filterSource = ref('')
const filterType = ref('')
const filterStatus = ref('')
const page = ref(1)
const pageSize = 10

async function fetchLogs() {
  loading.value = true
  try {
    const params: Record<string, string | number> = { limit: 100 }
    if (filterSource.value) params.source = filterSource.value
    if (filterType.value) params.event_type = filterType.value
    if (filterStatus.value) params.status = filterStatus.value
    logs.value = await getLogs(params)
    page.value = 1
  } catch (e) {
    console.error(e)
  } finally {
    loading.value = false
  }
}

const expandedIds = ref<Set<string>>(new Set())

function toggleExpand(id: string) {
  if (expandedIds.value.has(id)) {
    expandedIds.value.delete(id)
  } else {
    expandedIds.value.add(id)
  }
}

function isExpanded(id: string): boolean {
  return expandedIds.value.has(id)
}

const sourceOptions = [
  { label: '事件日志', value: 'event' },
  { label: 'Agent 追踪', value: 'trace' },
]

const typeOptions = computed(() => {
  const types = new Set<string>()
  logs.value.forEach(l => types.add(l.event_type))
  return Array.from(types).map(t => ({ label: t, value: t }))
})

const statusOptions = [
  { label: '成功', value: 'SUCCESS' },
  { label: '失败', value: 'FAILED' },
]

const stats = computed(() => {
  const total = logs.value.length
  const success = logs.value.filter(l => l.status === 'SUCCESS').length
  const failed = logs.value.filter(l => l.status === 'FAILED').length
  const events = logs.value.filter(l => l.source === 'event').length
  const traces = logs.value.filter(l => l.source === 'trace').length
  return { total, success, failed, events, traces }
})

const pagedLogs = computed(() => {
  const start = (page.value - 1) * pageSize
  return logs.value.slice(start, start + pageSize)
})

function getSourceLabel(source: string): string {
  return source === 'event' ? '事件' : 'Agent'
}

function getSourceColor(source: string): string {
  return source === 'event' ? '#165dff' : '#722ed1'
}

function getStatusType(status: string): string {
  return status === 'SUCCESS' ? 'success' : 'danger'
}

function getStatusLabel(status: string): string {
  return status === 'SUCCESS' ? '成功' : '失败'
}

function getEventTypeLabel(type: string): string {
  const map: Record<string, string> = {
    'ITEM_IN': '入库', 'ITEM_OUT': '出库', 'ITEM_MOVED': '移动', 'AGENT_UPDATE': 'Agent更新',
    'CHAT': '对话',
  }
  return map[type] || type
}

function formatTime(dateStr: string | null): string {
  if (!dateStr) return '-'
  return new Date(dateStr).toLocaleString('zh-CN')
}

function formatDetail(detail: Record<string, any> | null): string {
  if (!detail) return ''
  return JSON.stringify(detail, null, 2)
}

onMounted(fetchLogs)
</script>

<template>
  <div>
    <!-- 统计卡片 -->
    <div style="display: grid; grid-template-columns: repeat(5, 1fr); gap: 12px; margin-bottom: 20px">
      <div class="stat-card">
        <div class="stat-value">{{ stats.total }}</div>
        <div class="stat-label">总日志</div>
      </div>
      <div class="stat-card">
        <div class="stat-value" style="color: #00b42a">{{ stats.success }}</div>
        <div class="stat-label">成功</div>
      </div>
      <div class="stat-card">
        <div class="stat-value" style="color: #f53f3f">{{ stats.failed }}</div>
        <div class="stat-label">失败</div>
      </div>
      <div class="stat-card">
        <div class="stat-value" style="color: #165dff">{{ stats.events }}</div>
        <div class="stat-label">事件日志</div>
      </div>
      <div class="stat-card">
        <div class="stat-value" style="color: #722ed1">{{ stats.traces }}</div>
        <div class="stat-label">Agent 追踪</div>
      </div>
    </div>

    <!-- 筛选栏 -->
    <el-card shadow="never" style="margin-bottom: 16px">
      <el-form :inline="true">
        <el-form-item label="来源">
          <el-select v-model="filterSource" placeholder="全部来源" clearable style="width: 140px">
            <el-option v-for="o in sourceOptions" :key="o.value" :label="o.label" :value="o.value" />
          </el-select>
        </el-form-item>
        <el-form-item label="类型">
          <el-select v-model="filterType" placeholder="全部类型" clearable style="width: 140px">
            <el-option v-for="o in typeOptions" :key="o.value" :label="o.label" :value="o.value" />
          </el-select>
        </el-form-item>
        <el-form-item label="状态">
          <el-select v-model="filterStatus" placeholder="全部状态" clearable style="width: 120px">
            <el-option v-for="o in statusOptions" :key="o.value" :label="o.label" :value="o.value" />
          </el-select>
        </el-form-item>
        <el-form-item>
          <el-button type="primary" @click="fetchLogs">查询</el-button>
        </el-form-item>
      </el-form>
    </el-card>

    <!-- 日志列表 -->
    <el-card shadow="never">
      <div v-loading="loading" class="log-list">
        <div
          v-for="log in pagedLogs"
          :key="log.id"
          :class="['log-item', { 'log-item--failed': log.status === 'FAILED' }]"
        >
          <!-- 主行 -->
          <div class="log-main" @click="log.detail && toggleExpand(log.id)">
            <span :class="['log-dot', log.status === 'FAILED' ? 'dot-failed' : 'dot-ok']"></span>
            <span class="log-time">{{ formatTime(log.created_at) }}</span>
            <el-tag
              :color="getSourceColor(log.source)"
              effect="dark"
              size="small"
              round
              style="border: none; min-width: 52px; text-align: center"
            >
              {{ getSourceLabel(log.source) }}
            </el-tag>
            <el-tag size="small" round style="min-width: 56px; text-align: center">
              {{ getEventTypeLabel(log.event_type) }}
            </el-tag>
            <el-tag :type="getStatusType(log.status)" size="small" round style="min-width: 48px; text-align: center">
              {{ getStatusLabel(log.status) }}
            </el-tag>
            <span class="log-summary">
              <template v-if="log.source === 'trace' && log.detail">
                {{ log.detail.tool_name }}
                <span v-if="log.detail.duration_ms" class="log-duration">{{ log.detail.duration_ms }}ms</span>
              </template>
              <template v-else-if="log.source === 'event' && log.detail">
                {{ log.detail.inventory_id?.slice(0, 8) }}...
                <span v-if="log.detail.confidence" class="log-confidence">{{ (log.detail.confidence * 100).toFixed(0) }}%</span>
              </template>
            </span>
            <el-icon v-if="log.detail" class="log-expand-icon" :class="{ rotated: isExpanded(log.id) }">
              <ArrowDown />
            </el-icon>
          </div>

          <!-- 展开详情 -->
          <div v-if="log.detail && isExpanded(log.id)" class="log-detail">
            <div v-if="log.source === 'trace'" class="detail-grid">
              <div class="detail-field" v-if="log.detail.trace_id">
                <span class="detail-key">Trace ID</span>
                <span class="detail-val mono">{{ log.detail.trace_id }}</span>
              </div>
              <div class="detail-field" v-if="log.detail.step_order !== undefined">
                <span class="detail-key">步骤</span>
                <span class="detail-val">{{ log.detail.step_order }}</span>
              </div>
              <div class="detail-field" v-if="log.detail.tool_name">
                <span class="detail-key">工具</span>
                <span class="detail-val">{{ log.detail.tool_name }}</span>
              </div>
              <div class="detail-field" v-if="log.detail.duration_ms !== undefined">
                <span class="detail-key">耗时</span>
                <span class="detail-val">{{ log.detail.duration_ms }}ms</span>
              </div>
              <div class="detail-field" v-if="log.detail.device_id">
                <span class="detail-key">设备</span>
                <span class="detail-val mono">{{ log.detail.device_id }}</span>
              </div>
            </div>
            <div v-if="log.detail.tool_input" class="detail-json">
              <span class="detail-json-label">Input</span>
              <pre class="detail-json-code">{{ formatDetail(log.detail.tool_input) }}</pre>
            </div>
            <div v-if="log.detail.tool_output" class="detail-json">
              <span class="detail-json-label">Output</span>
              <pre class="detail-json-code">{{ formatDetail(log.detail.tool_output) }}</pre>
            </div>
            <div v-if="log.source === 'event'" class="detail-grid">
              <div class="detail-field" v-if="log.detail.inventory_id">
                <span class="detail-key">库存ID</span>
                <span class="detail-val mono">{{ log.detail.inventory_id }}</span>
              </div>
              <div class="detail-field" v-if="log.detail.confidence !== undefined">
                <span class="detail-key">置信度</span>
                <span class="detail-val">{{ (log.detail.confidence * 100).toFixed(1) }}%</span>
              </div>
              <div class="detail-field" v-if="log.detail.snapshot_path">
                <span class="detail-key">快照</span>
                <span class="detail-val mono">{{ log.detail.snapshot_path }}</span>
              </div>
            </div>
          </div>
        </div>

        <el-empty v-if="logs.length === 0 && !loading" description="暂无日志记录" />
      </div>

      <div v-if="logs.length > pageSize" class="pagination-wrap">
        <el-pagination
          v-model:current-page="page"
          :page-size="pageSize"
          :total="logs.length"
          layout="total, prev, pager, next"
          background
        />
      </div>
    </el-card>
  </div>
</template>

<style scoped>
.stat-card {
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 16px 20px;
  background: var(--bg-card);
  border-radius: var(--radius-md);
  box-shadow: var(--shadow-sm);
}

.stat-value {
  font-size: 28px;
  font-weight: 700;
  color: var(--text-primary);
  line-height: 1.2;
}

.stat-label {
  font-size: 12px;
  color: var(--text-secondary);
  margin-top: 4px;
}

.log-list {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.pagination-wrap {
  display: flex;
  justify-content: flex-end;
  padding-top: 16px;
}

.log-item {
  border-radius: var(--radius-sm);
  overflow: hidden;
  transition: box-shadow 0.2s;
}

.log-item:hover {
  box-shadow: var(--shadow-sm);
}

.log-item--failed {
  background: rgba(245, 63, 63, 0.08);
}

.log-main {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 14px;
  cursor: pointer;
  font-size: 13px;
}

.log-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  flex-shrink: 0;
}

.dot-ok {
  background: #00b42a;
  box-shadow: 0 0 4px #00b42a60;
}

.dot-failed {
  background: #f53f3f;
  box-shadow: 0 0 4px #f53f3f60;
}

.log-time {
  color: var(--text-secondary);
  font-size: 12px;
  min-width: 160px;
  flex-shrink: 0;
}

.log-summary {
  color: var(--text-primary);
  font-size: 13px;
  flex: 1;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.log-duration {
  font-size: 11px;
  color: var(--text-placeholder);
  background: var(--bg-soft);
  padding: 1px 6px;
  border-radius: 4px;
  margin-left: 6px;
}

.log-confidence {
  font-size: 11px;
  color: var(--brand-primary);
  background: var(--brand-primary-light);
  padding: 1px 6px;
  border-radius: 4px;
  margin-left: 6px;
}

.log-expand-icon {
  color: var(--text-placeholder);
  transition: transform 0.2s;
  flex-shrink: 0;
}

.log-expand-icon.rotated {
  transform: rotate(180deg);
}

.log-detail {
  padding: 0 14px 14px 30px;
  animation: slideDown 0.2s ease;
}

@keyframes slideDown {
  from { opacity: 0; max-height: 0; }
  to { opacity: 1; max-height: 500px; }
}

.detail-grid {
  display: flex;
  flex-wrap: wrap;
  gap: 12px 24px;
  margin-bottom: 10px;
}

.detail-field {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.detail-key {
  font-size: 11px;
  color: var(--text-placeholder);
}

.detail-val {
  font-size: 13px;
  color: var(--text-primary);
}

.detail-val.mono {
  font-family: 'SFMono-Regular', Consolas, monospace;
  font-size: 12px;
}

.detail-json {
  margin-top: 8px;
}

.detail-json-label {
  font-size: 11px;
  color: var(--text-placeholder);
  display: block;
  margin-bottom: 4px;
}

.detail-json-code {
  background: var(--bg-soft);
  border: 1px solid var(--border-color);
  border-radius: 6px;
  padding: 10px 12px;
  font-family: 'SFMono-Regular', Consolas, monospace;
  font-size: 12px;
  color: var(--text-primary);
  overflow-x: auto;
  margin: 0;
  white-space: pre-wrap;
  word-break: break-all;
  max-height: 200px;
  overflow-y: auto;
}
</style>
