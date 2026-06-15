<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import {
  listDeviceRawEvents,
  reprocessDeviceRawEvent,
  type DeviceRawEvent,
  type DeviceRawEventStatus,
} from '@/api/admin/deviceIngest'

const loading = ref(false)
const reprocessingId = ref('')
const rows = ref<DeviceRawEvent[]>([])
const selected = ref<DeviceRawEvent | null>(null)
const detailVisible = ref(false)

const filterDevice = ref('')
const filterEventType = ref('')
const filterStatus = ref('')

const eventOptions = [
  { label: '入库', value: 'ITEM_IN' },
  { label: '出库', value: 'ITEM_OUT' },
  { label: '整理', value: 'ITEM_MOVED' },
  { label: 'Agent 更新', value: 'AGENT_UPDATE' },
]

const statusOptions = [
  { label: '成功', value: 'success' },
  { label: '失败', value: 'failed' },
  { label: '处理中', value: 'processing' },
  { label: '已接收', value: 'received' },
  { label: '已忽略', value: 'ignored' },
]

async function fetchRows() {
  loading.value = true
  try {
    rows.value = await listDeviceRawEvents({
      device_id: filterDevice.value || undefined,
      event_type: filterEventType.value || undefined,
      status: filterStatus.value || undefined,
      limit: 100,
    })
  } finally {
    loading.value = false
  }
}

function openDetail(row: DeviceRawEvent) {
  selected.value = row
  detailVisible.value = true
}

async function handleReprocess(row: DeviceRawEvent) {
  reprocessingId.value = row.id
  try {
    const updated = await reprocessDeviceRawEvent(row.id)
    const idx = rows.value.findIndex(x => x.id === row.id)
    if (idx !== -1) rows.value[idx] = updated
    if (selected.value?.id === row.id) selected.value = updated
    ElMessage.success(updated.status === 'success' ? '重处理成功' : '重处理完成')
  } catch (e: any) {
    ElMessage.error(e.response?.data?.detail || '重处理失败')
  } finally {
    reprocessingId.value = ''
  }
}

function getEventLabel(type?: string | null): string {
  const map: Record<string, string> = {
    ITEM_IN: '入库',
    ITEM_OUT: '出库',
    ITEM_MOVED: '整理',
    AGENT_UPDATE: 'Agent 更新',
  }
  return type ? map[type] || type : '-'
}

function getStatusLabel(status: DeviceRawEventStatus): string {
  const map: Record<string, string> = {
    received: '已接收',
    processing: '处理中',
    success: '成功',
    failed: '失败',
    ignored: '已忽略',
  }
  return map[status] || status
}

function getStatusType(status: DeviceRawEventStatus): string {
  if (status === 'success') return 'success'
  if (status === 'failed') return 'danger'
  if (status === 'processing') return 'warning'
  if (status === 'ignored') return 'info'
  return ''
}

function formatTime(value?: string | null): string {
  if (!value) return '-'
  return new Date(value).toLocaleString('zh-CN')
}

function formatJson(value: unknown): string {
  if (!value) return ''
  return JSON.stringify(value, null, 2)
}

function shortId(id?: string | null): string {
  return id ? id.slice(0, 8) : '-'
}

const stats = computed(() => {
  const total = rows.value.length
  const success = rows.value.filter(x => x.status === 'success').length
  const failed = rows.value.filter(x => x.status === 'failed').length
  const pending = rows.value.filter(x => x.status === 'received' || x.status === 'processing').length
  return { total, success, failed, pending }
})

onMounted(fetchRows)
</script>

<template>
  <div class="device-ingest-page">
    <div class="stat-grid">
      <div class="stat-card">
        <div class="stat-value">{{ stats.total }}</div>
        <div class="stat-label">最近上报</div>
      </div>
      <div class="stat-card">
        <div class="stat-value success">{{ stats.success }}</div>
        <div class="stat-label">处理成功</div>
      </div>
      <div class="stat-card">
        <div class="stat-value danger">{{ stats.failed }}</div>
        <div class="stat-label">处理失败</div>
      </div>
      <div class="stat-card">
        <div class="stat-value warning">{{ stats.pending }}</div>
        <div class="stat-label">待处理</div>
      </div>
    </div>

    <el-card shadow="never" class="filter-card">
      <el-form :inline="true">
        <el-form-item label="设备">
          <el-input v-model="filterDevice" placeholder="device_id" clearable style="width: 180px" />
        </el-form-item>
        <el-form-item label="事件">
          <el-select v-model="filterEventType" placeholder="全部事件" clearable style="width: 140px">
            <el-option v-for="o in eventOptions" :key="o.value" :label="o.label" :value="o.value" />
          </el-select>
        </el-form-item>
        <el-form-item label="状态">
          <el-select v-model="filterStatus" placeholder="全部状态" clearable style="width: 140px">
            <el-option v-for="o in statusOptions" :key="o.value" :label="o.label" :value="o.value" />
          </el-select>
        </el-form-item>
        <el-form-item>
          <el-button type="primary" @click="fetchRows">
            <el-icon><Search /></el-icon>
            查询
          </el-button>
          <el-button @click="fetchRows">
            <el-icon><Refresh /></el-icon>
            刷新
          </el-button>
        </el-form-item>
      </el-form>
    </el-card>

    <el-card shadow="never">
      <el-table
        v-loading="loading"
        :data="rows"
        row-key="id"
        style="width: 100%"
        empty-text="暂无端侧上报"
      >
        <el-table-column label="时间" width="180">
          <template #default="{ row }">{{ formatTime(row.created_at) }}</template>
        </el-table-column>
        <el-table-column label="设备" min-width="160">
          <template #default="{ row }">
            <span class="mono">{{ row.device_id || '-' }}</span>
          </template>
        </el-table-column>
        <el-table-column label="事件" width="110">
          <template #default="{ row }">
            <el-tag size="small" round>{{ getEventLabel(row.event_type) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="状态" width="110">
          <template #default="{ row }">
            <el-tag :type="getStatusType(row.status)" size="small" round>
              {{ getStatusLabel(row.status) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="关联库存" min-width="150">
          <template #default="{ row }">
            <template v-if="row.related_inventory_ids?.length">
              <el-tag
                v-for="id in row.related_inventory_ids"
                :key="id"
                size="small"
                effect="plain"
                class="id-tag"
              >
                {{ shortId(id) }}
              </el-tag>
            </template>
            <span v-else class="muted">-</span>
          </template>
        </el-table-column>
        <el-table-column label="错误" min-width="220">
          <template #default="{ row }">
            <span class="error-text">{{ row.error_message || '-' }}</span>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="180" fixed="right">
          <template #default="{ row }">
            <el-button size="small" text type="primary" @click="openDetail(row)">详情</el-button>
            <el-button
              size="small"
              text
              :loading="reprocessingId === row.id"
              :disabled="row.status === 'processing'"
              @click="handleReprocess(row)"
            >
              重处理
            </el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <el-drawer v-model="detailVisible" title="端侧上报详情" size="52%">
      <div v-if="selected" class="detail-wrap">
        <div class="detail-grid">
          <div class="detail-field">
            <span class="detail-key">记录 ID</span>
            <span class="detail-val mono">{{ selected.id }}</span>
          </div>
          <div class="detail-field">
            <span class="detail-key">设备</span>
            <span class="detail-val mono">{{ selected.device_id || '-' }}</span>
          </div>
          <div class="detail-field">
            <span class="detail-key">事件</span>
            <span class="detail-val">{{ getEventLabel(selected.event_type) }}</span>
          </div>
          <div class="detail-field">
            <span class="detail-key">状态</span>
            <span class="detail-val">{{ getStatusLabel(selected.status) }}</span>
          </div>
          <div class="detail-field">
            <span class="detail-key">Trace</span>
            <span class="detail-val mono">{{ selected.trace_id || '-' }}</span>
          </div>
          <div class="detail-field">
            <span class="detail-key">处理时间</span>
            <span class="detail-val">{{ formatTime(selected.processed_at) }}</span>
          </div>
        </div>

        <el-alert
          v-if="selected.error_message"
          :title="selected.error_message"
          type="error"
          show-icon
          :closable="false"
        />

        <div class="json-section">
          <div class="section-title">规范化 JSON</div>
          <pre class="json-code">{{ formatJson(selected.normalized_payload) }}</pre>
        </div>

        <div class="json-section">
          <div class="section-title">原始 JSON 摘要</div>
          <pre class="json-code">{{ formatJson(selected.raw_payload) }}</pre>
        </div>
      </div>
    </el-drawer>
  </div>
</template>

<style scoped>
.device-ingest-page {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.stat-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 12px;
}

.stat-card {
  background: var(--bg-card);
  border: 1px solid var(--border-color);
  border-radius: 8px;
  padding: 16px;
  box-shadow: var(--shadow-sm);
}

.stat-value {
  font-size: 26px;
  font-weight: 700;
  color: var(--text-primary);
  line-height: 1.1;
}

.stat-value.success { color: #00b42a; }
.stat-value.danger { color: #f53f3f; }
.stat-value.warning { color: #fa8c16; }

.stat-label {
  margin-top: 6px;
  font-size: 12px;
  color: var(--text-secondary);
}

.filter-card :deep(.el-card__body) {
  padding-bottom: 0;
}

.mono {
  font-family: 'SFMono-Regular', Consolas, monospace;
  font-size: 12px;
}

.muted {
  color: var(--text-placeholder);
}

.id-tag {
  margin-right: 4px;
}

.error-text {
  display: inline-block;
  max-width: 360px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  color: var(--text-secondary);
}

.detail-wrap {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.detail-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 10px;
}

.detail-field {
  padding: 10px 12px;
  border: 1px solid var(--border-color);
  border-radius: 8px;
  background: var(--bg-soft);
  min-width: 0;
}

.detail-key {
  display: block;
  font-size: 12px;
  color: var(--text-secondary);
  margin-bottom: 6px;
}

.detail-val {
  display: block;
  color: var(--text-primary);
  overflow-wrap: anywhere;
}

.json-section {
  border: 1px solid var(--border-color);
  border-radius: 8px;
  overflow: hidden;
}

.section-title {
  padding: 10px 12px;
  background: var(--bg-soft);
  border-bottom: 1px solid var(--border-color);
  font-weight: 600;
  color: var(--text-primary);
}

.json-code {
  margin: 0;
  padding: 12px;
  max-height: 360px;
  overflow: auto;
  background: var(--bg-card);
  color: var(--text-primary);
  font-family: 'SFMono-Regular', Consolas, monospace;
  font-size: 12px;
  line-height: 1.55;
  white-space: pre-wrap;
  word-break: break-word;
}

@media (max-width: 900px) {
  .stat-grid,
  .detail-grid {
    grid-template-columns: 1fr;
  }
}
</style>
