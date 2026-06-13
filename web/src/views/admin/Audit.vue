<script setup lang="ts">
/**
 * 操作审计日志：管理员关键操作的时间线视图。
 * 数据源同 /admin/logs，过滤 source='admin'。
 */
import { ref, computed, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { getLogs, type LogEntry } from '@/api/admin/logs'
import { downloadCsv } from '@/utils/downloadCsv'

const loading = ref(false)
const logs = ref<LogEntry[]>([])
const filterType = ref('')
const filterStatus = ref('')
const page = ref(1)
const pageSize = 10

const eventLabels: Record<string, { icon: string; label: string; color: string }> = {
  VISION_ASSIST_CONFIG_UPDATE: { icon: 'View', label: '视觉辅助策略调整', color: '#722ed1' },
  CATEGORY_CONFIG_UPDATE: { icon: 'Collection', label: '品类配置变更', color: '#0fc6c2' },
  VISION_ASSIST: { icon: 'Camera', label: '视觉辅助识别', color: '#165dff' },
}

async function fetchAuditLogs() {
  loading.value = true
  try {
    const params: Record<string, string | number> = {
      source: 'admin',
      limit: 200,
    }
    if (filterType.value) params.event_type = filterType.value
    if (filterStatus.value) params.status = filterStatus.value
    logs.value = await getLogs(params)
    page.value = 1
  } catch {
    ElMessage.error('加载失败')
  } finally {
    loading.value = false
  }
}

const stats = computed(() => {
  const total = logs.value.length
  const success = logs.value.filter(l => l.status === 'SUCCESS').length
  const failed = logs.value.filter(l => l.status === 'FAILED').length
  const today = new Date()
  today.setHours(0, 0, 0, 0)
  const todayCount = logs.value.filter(l => {
    const t = l.created_at ? new Date(l.created_at) : null
    return t && t >= today
  }).length
  return { total, success, failed, today: todayCount }
})

const pagedLogs = computed(() => {
  const start = (page.value - 1) * pageSize
  return logs.value.slice(start, start + pageSize)
})

// 同一天的日志聚到一起
const grouped = computed(() => {
  const m = new Map<string, LogEntry[]>()
  pagedLogs.value.forEach(l => {
    const d = l.created_at ? new Date(l.created_at) : null
    const key = d ? d.toLocaleDateString('zh-CN') : '未知日期'
    if (!m.has(key)) m.set(key, [])
    m.get(key)!.push(l)
  })
  return Array.from(m.entries())
})

const typeOptions = computed(() => {
  const types = new Set<string>()
  logs.value.forEach(l => types.add(l.event_type))
  return Array.from(types).map(t => ({ label: eventLabels[t]?.label || t, value: t }))
})

function getEventInfo(type: string) {
  return eventLabels[type] || { icon: 'Document', label: type, color: '#86909c' }
}

function getActorName(detail: any): string {
  return detail?.admin_username || detail?.admin_id?.slice(0, 8) || '系统'
}

function describeChange(log: LogEntry): string {
  const d = log.detail || {}
  if (log.event_type === 'VISION_ASSIST_CONFIG_UPDATE') {
    return `区间从 [${d.old_lower}, ${d.old_upper}] 调整为 [${d.new_lower}, ${d.new_upper}]`
  }
  if (log.event_type === 'CATEGORY_CONFIG_UPDATE') {
    const parts: string[] = []
    if (d.old_days !== d.new_days) {
      parts.push(`阈值 ${d.old_days} → ${d.new_days} 天`)
    }
    if (d.old_unit_price !== d.new_unit_price) {
      const oldP = d.old_unit_price ?? '未配置'
      const newP = d.new_unit_price ?? '清空'
      parts.push(`单价 ${oldP === '未配置' ? oldP : '¥' + oldP} → ${newP === '清空' ? newP : '¥' + newP}`)
    }
    return `${d.category}：${parts.join('，')}`
  }
  if (log.event_type === 'VISION_ASSIST') {
    return `原始 ${d.original_category}(${d.original_confidence}) → 云端 ${d.vision_category}(${d.vision_confidence?.toFixed?.(2)})`
  }
  return JSON.stringify(d).slice(0, 100)
}

function formatTime(ts: string | null): string {
  if (!ts) return '-'
  const d = new Date(ts)
  return d.toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit', second: '2-digit' })
}

function exportAudit() {
  // 直接调通用下载工具，但 /admin/export/audit 不存在；
  // 简单做：前端把 logs 转成 CSV 客户端导出
  const lines = [
    'time,event_type,status,actor,description',
    ...logs.value.map(l => {
      const t = l.created_at ? new Date(l.created_at).toISOString() : ''
      const desc = describeChange(l).replace(/"/g, '""')
      const actor = getActorName(l.detail)
      return `${t},${l.event_type},${l.status},${actor},"${desc}"`
    })
  ]
  const blob = new Blob([new TextEncoder().encode('\ufeff' + lines.join('\n'))],
                        { type: 'text/csv;charset=utf-8' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = `audit_${new Date().toISOString().slice(0,10)}.csv`
  document.body.appendChild(a)
  a.click()
  document.body.removeChild(a)
  URL.revokeObjectURL(url)
  ElMessage.success('已下载审计日志')
}

void downloadCsv

onMounted(fetchAuditLogs)
</script>

<template>
  <div v-loading="loading" class="audit-page">
    <!-- KPI -->
    <div class="kpi-row">
      <div class="kpi-card">
        <div class="kpi-icon" style="background: var(--brand-primary-light); color: var(--brand-primary-dark)">
          <el-icon :size="22"><Document /></el-icon>
        </div>
        <div>
          <div class="kpi-value">{{ stats.total }}</div>
          <div class="kpi-label">审计记录</div>
        </div>
      </div>
      <div class="kpi-card">
        <div class="kpi-icon" style="background: #ecfeff; color: #06b6d4">
          <el-icon :size="22"><Calendar /></el-icon>
        </div>
        <div>
          <div class="kpi-value">{{ stats.today }}</div>
          <div class="kpi-label">今日操作</div>
        </div>
      </div>
      <div class="kpi-card">
        <div class="kpi-icon" style="background: #e8f7e8; color: #00b42a">
          <el-icon :size="22"><CircleCheck /></el-icon>
        </div>
        <div>
          <div class="kpi-value">{{ stats.success }}</div>
          <div class="kpi-label">成功</div>
        </div>
      </div>
      <div class="kpi-card">
        <div class="kpi-icon" style="background: #ffece8; color: #f53f3f">
          <el-icon :size="22"><Warning /></el-icon>
        </div>
        <div>
          <div class="kpi-value">{{ stats.failed }}</div>
          <div class="kpi-label">失败</div>
        </div>
      </div>
    </div>

    <!-- 工具栏 -->
    <el-card shadow="never" class="filter-card">
      <el-form :inline="true">
        <el-form-item label="事件类型">
          <el-select v-model="filterType" clearable placeholder="全部" style="width: 240px">
            <el-option v-for="o in typeOptions" :key="o.value" :label="o.label" :value="o.value" />
          </el-select>
        </el-form-item>
        <el-form-item label="状态">
          <el-select v-model="filterStatus" clearable placeholder="全部" style="width: 120px">
            <el-option label="成功" value="SUCCESS" />
            <el-option label="失败" value="FAILED" />
          </el-select>
        </el-form-item>
        <el-form-item>
          <el-button type="primary" @click="fetchAuditLogs">查询</el-button>
        </el-form-item>
        <el-form-item>
          <el-button @click="exportAudit">
            <el-icon><Download /></el-icon> 导出 CSV
          </el-button>
        </el-form-item>
      </el-form>
    </el-card>

    <!-- 时间线 -->
    <el-card shadow="never">
      <div v-if="logs.length === 0 && !loading" class="empty">
        <el-icon :size="48" color="var(--text-placeholder)"><Document /></el-icon>
        <p>暂无审计记录</p>
        <p class="empty-tip">视觉辅助配置 / 品类配置 / 用户管理等关键操作会自动记录</p>
      </div>
      <div v-else class="timeline">
        <div v-for="[day, items] in grouped" :key="day" class="day-group">
          <div class="day-header">{{ day }}</div>
          <div
            v-for="log in items"
            :key="log.id"
            class="timeline-item"
            :class="{ failed: log.status === 'FAILED' }"
          >
            <div class="timeline-dot" :style="{ background: getEventInfo(log.event_type).color }">
              <el-icon :size="14"><component :is="getEventInfo(log.event_type).icon" /></el-icon>
            </div>
            <div class="timeline-body">
              <div class="timeline-head">
                <span class="event-name">{{ getEventInfo(log.event_type).label }}</span>
                <el-tag size="small" round
                  :type="log.status === 'SUCCESS' ? 'success' : 'danger'"
                >{{ log.status === 'SUCCESS' ? '成功' : '失败' }}</el-tag>
                <span class="event-time">{{ formatTime(log.created_at) }}</span>
              </div>
              <div class="timeline-desc">{{ describeChange(log) }}</div>
              <div class="timeline-actor">
                <el-icon :size="12"><User /></el-icon>
                {{ getActorName(log.detail) }}
              </div>
            </div>
          </div>
        </div>
      </div>

      <div v-if="logs.length > pageSize" class="audit-pagination">
        <span class="audit-total">共 {{ logs.length }} 条，每页 10 条</span>
        <el-pagination
          v-model:current-page="page"
          background
          layout="prev, pager, next"
          :page-size="pageSize"
          :total="logs.length"
        />
      </div>
    </el-card>
  </div>
</template>

<style scoped>
.audit-page {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.kpi-row {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 16px;
}

.kpi-card {
  display: flex;
  align-items: center;
  gap: 14px;
  padding: 18px 20px;
  background: var(--bg-card);
  border-radius: var(--radius-md);
  box-shadow: var(--shadow-sm);
}

.kpi-icon {
  width: 44px;
  height: 44px;
  border-radius: 12px;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.kpi-value {
  font-size: 22px;
  font-weight: 700;
  color: var(--text-primary);
  line-height: 1.2;
}

.kpi-label {
  font-size: 12px;
  color: var(--text-secondary);
  margin-top: 2px;
}

.filter-card :deep(.el-form-item) {
  margin-bottom: 0;
}

.empty {
  text-align: center;
  padding: 60px 0;
  color: var(--text-placeholder);
  display: flex;
  flex-direction: column;
  gap: 8px;
  align-items: center;
}

.empty-tip {
  font-size: 12px;
  color: var(--text-placeholder);
}

.timeline {
  position: relative;
  padding-left: 0;
}

.day-group {
  margin-bottom: 24px;
}

.day-group:last-child {
  margin-bottom: 0;
}

.day-header {
  font-size: 13px;
  font-weight: 700;
  color: var(--text-secondary);
  padding: 8px 0;
  margin-bottom: 8px;
  border-bottom: 1px dashed var(--border-color);
}

.timeline-item {
  display: flex;
  gap: 14px;
  padding: 14px 12px;
  border-left: 2px solid var(--border-color);
  margin-left: 14px;
  position: relative;
  transition: background 0.18s;
}

.timeline-item:hover {
  background: var(--bg-soft);
}

.timeline-item.failed {
  border-left-color: #f53f3f;
  background: rgba(245, 63, 63, 0.04);
}

.timeline-dot {
  position: absolute;
  left: -16px;
  top: 16px;
  width: 30px;
  height: 30px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #fff;
  box-shadow: 0 2px 6px rgba(0, 0, 0, 0.12);
}

.timeline-body {
  flex: 1;
  min-width: 0;
  margin-left: 24px;
}

.timeline-head {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 4px;
  flex-wrap: wrap;
}

.event-name {
  font-size: 14px;
  font-weight: 600;
  color: var(--text-primary);
}

.event-time {
  margin-left: auto;
  font-size: 12px;
  color: var(--text-placeholder);
  font-variant-numeric: tabular-nums;
}

.timeline-desc {
  font-size: 13px;
  color: var(--text-secondary);
  line-height: 1.5;
  margin-top: 2px;
}

.timeline-actor {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  font-size: 11px;
  color: var(--text-placeholder);
  margin-top: 4px;
}

.audit-pagination {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: 16px;
  padding-top: 16px;
  border-top: 1px solid var(--border-color);
}

.audit-total {
  color: var(--text-secondary);
  font-size: 13px;
}

@media (max-width: 1100px) {
  .kpi-row { grid-template-columns: repeat(2, 1fr); }
}
</style>
