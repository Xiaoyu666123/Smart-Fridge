<script setup lang="ts">
import { ref, computed, onMounted, onBeforeUnmount } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { use } from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import { BarChart } from 'echarts/charts'
import { GridComponent, TooltipComponent } from 'echarts/components'
import VChart from 'vue-echarts'
import {
  listDevices, updateDevice, deleteDevice, restoreDevice, getDeviceHeartbeats,
  type DeviceItem,
} from '@/api/admin/device'
import { useChartTheme } from '@/composables/useChartTheme'
import { showUndoToast } from '@/composables/useUndoToast'

use([CanvasRenderer, BarChart, GridComponent, TooltipComponent])

const chartTheme = useChartTheme()

const loading = ref(false)
const devices = ref<DeviceItem[]>([])
let pollTimer: ReturnType<typeof setInterval> | null = null

const editDialog = ref({
  visible: false,
  saving: false,
  device: null as DeviceItem | null,
  form: { name: '', location: '', description: '' },
})

const detailDialog = ref({
  visible: false,
  device: null as DeviceItem | null,
  series: [] as { label: string; count: number }[],
  loading: false,
})

async function fetchDevices() {
  loading.value = true
  try {
    devices.value = await listDevices()
  } catch {
    ElMessage.error('设备列表加载失败')
  } finally {
    loading.value = false
  }
}

const stats = computed(() => {
  const total = devices.value.length
  const online = devices.value.filter(d => d.live_status === 'online').length
  const idle = devices.value.filter(d => d.live_status === 'idle').length
  const offline = devices.value.filter(d => d.live_status === 'offline').length
  return { total, online, idle, offline }
})

function liveStatusInfo(s: string) {
  if (s === 'online') return { label: '在线', color: '#00b42a', bg: '#e8f7e8' }
  if (s === 'idle') return { label: '空闲', color: '#fa8c16', bg: '#fff7e6' }
  return { label: '离线', color: '#f53f3f', bg: '#ffece8' }
}

function relativeTime(ts: string | null, age: number | null): string {
  if (age == null) return '从未'
  if (age < 60) return `${age} 秒前`
  if (age < 3600) return `${Math.floor(age / 60)} 分钟前`
  if (age < 86400) return `${Math.floor(age / 3600)} 小时前`
  return `${Math.floor(age / 86400)} 天前`
}

function openEdit(d: DeviceItem) {
  editDialog.value.device = d
  editDialog.value.form = {
    name: d.name || '',
    location: d.location || '',
    description: d.description || '',
  }
  editDialog.value.visible = true
}

async function saveEdit() {
  const d = editDialog.value.device
  if (!d) return
  editDialog.value.saving = true
  try {
    const updated = await updateDevice(d.device_id, editDialog.value.form)
    const idx = devices.value.findIndex(x => x.device_id === d.device_id)
    if (idx !== -1) devices.value[idx] = updated
    ElMessage.success('已保存')
    editDialog.value.visible = false
  } catch {
    ElMessage.error('保存失败')
  } finally {
    editDialog.value.saving = false
  }
}

async function handleDelete(d: DeviceItem) {
  try {
    await ElMessageBox.confirm(
      `确定移除设备「${d.name}」？该设备的库存与心跳记录不会被删除，但设备本身会从列表移除。`,
      '删除设备',
      { type: 'warning', confirmButtonText: '删除', cancelButtonText: '取消' }
    )
    const snapshot = {
      device_id: d.device_id,
      name: d.name,
      location: d.location,
      description: d.description,
    }
    await deleteDevice(d.device_id)
    devices.value = devices.value.filter(x => x.device_id !== d.device_id)

    showUndoToast({
      message: `已删除设备「${d.name}」`,
      duration: 6,
      onUndo: async () => {
        try {
          const restored = await restoreDevice(snapshot)
          devices.value = [restored, ...devices.value]
          ElMessage.success('已恢复设备')
        } catch {
          ElMessage.error('恢复失败')
        }
      },
    })
  } catch (e) {
    if (e !== 'cancel' && e !== 'close') {
      ElMessage.error('删除失败')
    }
  }
}

async function openDetail(d: DeviceItem) {
  detailDialog.value.device = d
  detailDialog.value.visible = true
  detailDialog.value.loading = true
  detailDialog.value.series = []
  try {
    const data = await getDeviceHeartbeats(d.device_id, 24, 30)
    detailDialog.value.series = data.series.map(s => ({ label: s.label, count: s.count }))
  } catch {
    ElMessage.error('心跳曲线加载失败')
  } finally {
    detailDialog.value.loading = false
  }
}

const heartbeatChartOption = computed(() => {
  const s = detailDialog.value.series
  return {
    color: ['#0ea5e9'],
    tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' } },
    grid: { left: 40, right: 16, top: 16, bottom: 30 },
    xAxis: {
      type: 'category',
      data: s.map(x => x.label),
      axisLabel: { color: '#86909c', fontSize: 11, interval: Math.max(1, Math.floor(s.length / 12)) },
      axisLine: { lineStyle: { color: '#e5e6eb' } },
    },
    yAxis: {
      type: 'value',
      splitLine: { lineStyle: { color: '#f2f3f5' } },
      axisLabel: { color: '#86909c', fontSize: 12 },
    },
    series: [{
      type: 'bar',
      data: s.map(x => x.count),
      barMaxWidth: 14,
      itemStyle: { color: '#0ea5e9', borderRadius: [4, 4, 0, 0] },
    }],
  }
})

onMounted(() => {
  fetchDevices()
  // 30s 轮询一次（live_status 推算需要后端 sweeper 配合）
  pollTimer = setInterval(fetchDevices, 30_000)
})

onBeforeUnmount(() => {
  if (pollTimer) clearInterval(pollTimer)
})
</script>

<template>
  <div v-loading="loading" class="device-page">
    <!-- 顶部 KPI -->
    <div class="kpi-row">
      <div class="kpi-card">
        <div class="kpi-icon" style="background: var(--brand-primary-light); color: var(--brand-primary-dark)">
          <el-icon :size="22"><Monitor /></el-icon>
        </div>
        <div>
          <div class="kpi-value">{{ stats.total }}</div>
          <div class="kpi-label">设备总数</div>
        </div>
      </div>
      <div class="kpi-card">
        <div class="kpi-icon" style="background: #e8f7e8; color: #00b42a">
          <el-icon :size="22"><CircleCheck /></el-icon>
        </div>
        <div>
          <div class="kpi-value">{{ stats.online }}</div>
          <div class="kpi-label">在线</div>
        </div>
      </div>
      <div class="kpi-card">
        <div class="kpi-icon" style="background: #fff7e6; color: #fa8c16">
          <el-icon :size="22"><Clock /></el-icon>
        </div>
        <div>
          <div class="kpi-value">{{ stats.idle }}</div>
          <div class="kpi-label">空闲</div>
        </div>
      </div>
      <div class="kpi-card">
        <div class="kpi-icon" style="background: #ffece8; color: #f53f3f">
          <el-icon :size="22"><Warning /></el-icon>
        </div>
        <div>
          <div class="kpi-value">{{ stats.offline }}</div>
          <div class="kpi-label">离线</div>
        </div>
      </div>
    </div>

    <!-- 工具栏 -->
    <div class="page-tool">
      <div class="page-tip">
        <el-icon :size="14" color="var(--text-secondary)"><InfoFilled /></el-icon>
        端侧第一次上报时自动注册。状态每 30s 自动刷新。
      </div>
      <el-button size="small" @click="fetchDevices"><el-icon><Refresh /></el-icon> 刷新</el-button>
    </div>

    <!-- 设备网格 -->
    <div v-if="devices.length === 0" class="empty-wrap">
      <el-empty description="暂无设备。让端侧调用 /events/heartbeat 即可自动注册。" />
    </div>
    <div v-else class="device-grid">
      <div
        v-for="d in devices"
        :key="d.device_id"
        class="device-card"
        :class="['live-' + d.live_status]"
        @click="openDetail(d)"
      >
        <div class="device-card-header">
          <div class="device-card-title">
            <el-icon :size="18" color="var(--brand-primary-dark)"><Monitor /></el-icon>
            <span>{{ d.name }}</span>
          </div>
          <el-tag
            size="small"
            round
            :style="{
              background: liveStatusInfo(d.live_status).bg,
              color: liveStatusInfo(d.live_status).color,
              border: 'none',
              fontWeight: 600,
            }"
          >
            <span class="live-dot" :style="{ background: liveStatusInfo(d.live_status).color }"></span>
            {{ liveStatusInfo(d.live_status).label }}
          </el-tag>
        </div>
        <div class="device-id">
          <code>{{ d.device_id }}</code>
        </div>
        <div v-if="d.location" class="device-meta">
          <el-icon :size="13"><LocationFilled /></el-icon>
          <span>{{ d.location }}</span>
        </div>
        <div class="device-stats">
          <div class="device-stat">
            <span class="device-stat-label">最近上报</span>
            <span class="device-stat-value">{{ relativeTime(d.last_seen_at, d.seconds_since_last_seen) }}</span>
          </div>
          <div class="device-stat">
            <span class="device-stat-label">心跳次数</span>
            <span class="device-stat-value">{{ d.heartbeat_count }}</span>
          </div>
          <div class="device-stat">
            <span class="device-stat-label">最后事件</span>
            <span class="device-stat-value">{{ d.last_event_type || '-' }}</span>
          </div>
        </div>
        <div class="device-actions" @click.stop>
          <el-button size="small" link type="primary" @click="openEdit(d)">编辑</el-button>
          <el-button size="small" link type="danger" @click="handleDelete(d)">删除</el-button>
        </div>
      </div>
    </div>

    <!-- 编辑弹窗 -->
    <el-dialog v-model="editDialog.visible" title="编辑设备" width="460px">
      <el-form label-width="80px">
        <el-form-item label="设备 ID">
          <code class="mono">{{ editDialog.device?.device_id }}</code>
        </el-form-item>
        <el-form-item label="显示名">
          <el-input v-model="editDialog.form.name" placeholder="如：厨房冰箱" />
        </el-form-item>
        <el-form-item label="位置">
          <el-input v-model="editDialog.form.location" placeholder="如：客厅 / 厨房" />
        </el-form-item>
        <el-form-item label="备注">
          <el-input
            v-model="editDialog.form.description"
            type="textarea"
            :rows="3"
            placeholder="可选备注"
          />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="editDialog.visible = false">取消</el-button>
        <el-button type="primary" :loading="editDialog.saving" @click="saveEdit">保存</el-button>
      </template>
    </el-dialog>

    <!-- 详情弹窗 -->
    <el-dialog
      v-model="detailDialog.visible"
      :title="`设备详情：${detailDialog.device?.name || ''}`"
      width="640px"
    >
      <div v-loading="detailDialog.loading">
        <el-descriptions :column="2" size="small" border>
          <el-descriptions-item label="设备 ID">
            <code class="mono">{{ detailDialog.device?.device_id }}</code>
          </el-descriptions-item>
          <el-descriptions-item label="状态">
            <el-tag size="small" round
              :style="{
                background: liveStatusInfo(detailDialog.device?.live_status || 'offline').bg,
                color: liveStatusInfo(detailDialog.device?.live_status || 'offline').color,
                border: 'none',
              }"
            >{{ liveStatusInfo(detailDialog.device?.live_status || 'offline').label }}</el-tag>
          </el-descriptions-item>
          <el-descriptions-item label="位置">
            {{ detailDialog.device?.location || '-' }}
          </el-descriptions-item>
          <el-descriptions-item label="最后事件">
            {{ detailDialog.device?.last_event_type || '-' }}
          </el-descriptions-item>
          <el-descriptions-item label="注册时间">
            {{ detailDialog.device?.registered_at ? new Date(detailDialog.device.registered_at).toLocaleString('zh-CN') : '-' }}
          </el-descriptions-item>
          <el-descriptions-item label="心跳次数">
            {{ detailDialog.device?.heartbeat_count || 0 }}
          </el-descriptions-item>
        </el-descriptions>

        <div class="chart-title">近 24 小时心跳频率（每 30 分钟桶）</div>
        <v-chart
          v-if="detailDialog.series.length > 0"
          :theme="chartTheme"
          :option="heartbeatChartOption"
          autoresize
          class="hb-chart"
        />
      </div>
    </el-dialog>
  </div>
</template>

<style scoped>
.device-page {
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

.page-tool {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 12px;
}

.page-tip {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  font-size: 12px;
  color: var(--text-secondary);
}

.empty-wrap {
  padding: 40px;
}

.device-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
  gap: 16px;
}

.device-card {
  position: relative;
  padding: 18px 18px 14px 18px;
  background: var(--bg-card);
  border: 1.5px solid var(--border-color);
  border-radius: 14px;
  box-shadow: var(--shadow-sm);
  cursor: pointer;
  transition: all 0.2s;
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.device-card:hover {
  transform: translateY(-2px);
  box-shadow: 0 10px 24px rgba(0, 0, 0, 0.08);
  border-color: var(--brand-primary);
}

.device-card.live-online   { border-left: 4px solid #00b42a; }
.device-card.live-idle     { border-left: 4px solid #fa8c16; }
.device-card.live-offline  { border-left: 4px solid #f53f3f; opacity: 0.85; }

.device-card-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
}

.device-card-title {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 15px;
  font-weight: 600;
  color: var(--text-primary);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.live-dot {
  display: inline-block;
  width: 6px;
  height: 6px;
  border-radius: 50%;
  margin-right: 4px;
  vertical-align: middle;
  animation: hb-blink 1.4s ease-in-out infinite;
}

@keyframes hb-blink {
  0%, 100% { opacity: 1; }
  50%      { opacity: 0.4; }
}

.device-id {
  font-size: 11px;
  color: var(--text-placeholder);
}

.device-id code {
  font-family: 'SFMono-Regular', Consolas, monospace;
  background: var(--bg-color);
  padding: 1px 6px;
  border-radius: 4px;
}

.device-meta {
  display: flex;
  align-items: center;
  gap: 4px;
  font-size: 12px;
  color: var(--text-secondary);
}

.device-stats {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 4px;
  padding: 10px 0;
  border-top: 1px dashed var(--border-color);
}

.device-stat {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.device-stat-label {
  font-size: 11px;
  color: var(--text-placeholder);
}

.device-stat-value {
  font-size: 12px;
  font-weight: 600;
  color: var(--text-primary);
}

.device-actions {
  display: flex;
  justify-content: flex-end;
  gap: 4px;
  margin-top: -4px;
}

.device-actions :deep(.el-button.is-link) {
  height: 24px;
  padding: 0 6px;
  background: transparent !important;
  border: none !important;
  box-shadow: none !important;
}

.device-actions :deep(.el-button.is-link.el-button--primary) {
  color: var(--brand-primary-dark) !important;
}

.device-actions :deep(.el-button.is-link.el-button--primary:hover) {
  background: var(--brand-primary-soft) !important;
  color: var(--brand-primary-dark) !important;
}

.device-actions :deep(.el-button.is-link.el-button--danger) {
  color: var(--color-danger) !important;
}

.device-actions :deep(.el-button.is-link.el-button--danger:hover) {
  background: #fef2f2 !important;
  color: #b91c1c !important;
}

.mono {
  font-family: 'SFMono-Regular', Consolas, monospace;
  font-size: 12px;
  color: var(--text-primary);
  background: var(--bg-color);
  padding: 2px 6px;
  border-radius: 4px;
}

.chart-title {
  font-size: 13px;
  font-weight: 600;
  color: var(--text-secondary);
  margin: 16px 0 8px;
}

.hb-chart {
  width: 100%;
  height: 180px;
}

@media (max-width: 1100px) {
  .kpi-row { grid-template-columns: repeat(2, 1fr); }
}
</style>
