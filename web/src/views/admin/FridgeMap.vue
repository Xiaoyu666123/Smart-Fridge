<script setup lang="ts">
import { ref, computed, onMounted, watch, nextTick } from 'vue'
import { ElMessage } from 'element-plus'
import { getInventoryList, type InventoryItem } from '@/api/admin/inventory'
import { useInventoryWS } from '@/composables/useInventoryWS'
import { uploadUrl } from '@/config/env'

const loading = ref(false)
const items = ref<InventoryItem[]>([])
const filterStatus = ref('IN_STOCK')
const selectedItem = ref<InventoryItem | null>(null)

const canvasRef = ref<HTMLDivElement>()
const canvasSize = ref({ w: 800, h: 600 })

async function fetchData() {
  loading.value = true
  try {
    items.value = await getInventoryList()
  } catch {
    ElMessage.error('获取库存失败')
  } finally {
    loading.value = false
  }
}

// 当前状态过滤下，所有有 bbox 的物品
const visibleItems = computed(() =>
  items.value.filter(i =>
    (!filterStatus.value || i.status === filterStatus.value) &&
    Array.isArray(i.bbox) && i.bbox.length === 4 &&
    (i.bbox[2] > 0 || i.bbox[3] > 0)
  )
)

// 计算所有 bbox 的边界，用来归一化
const bounds = computed(() => {
  if (visibleItems.value.length === 0) return { minX: 0, minY: 0, maxX: 1, maxY: 1 }
  let minX = Infinity, minY = Infinity, maxX = -Infinity, maxY = -Infinity
  visibleItems.value.forEach(i => {
    const [x, y, w, h] = i.bbox as number[]
    minX = Math.min(minX, x)
    minY = Math.min(minY, y)
    maxX = Math.max(maxX, x + w)
    maxY = Math.max(maxY, y + h)
  })
  // 留 5% padding
  const padX = (maxX - minX) * 0.05 || 10
  const padY = (maxY - minY) * 0.05 || 10
  return { minX: minX - padX, minY: minY - padY, maxX: maxX + padX, maxY: maxY + padY }
})

function getRemainDays(item: InventoryItem): number {
  const expireAt = item.agent_metadata?.expire_at
  if (!expireAt) return Number.POSITIVE_INFINITY
  return Math.ceil((new Date(expireAt).getTime() - Date.now()) / 86400000)
}

function getItemColor(item: InventoryItem): { bg: string; border: string } {
  const days = getRemainDays(item)
  if (days < 0) return { bg: 'rgba(245,63,63,0.2)', border: '#f53f3f' }
  if (days <= 1) return { bg: 'rgba(255,125,0,0.2)', border: '#ff7d00' }
  if (days <= 3) return { bg: 'rgba(250,219,20,0.25)', border: '#fadb14' }
  if (Number.isFinite(days)) return { bg: 'rgba(0,180,42,0.18)', border: '#00b42a' }
  return { bg: 'rgba(134,144,156,0.18)', border: '#86909c' }
}

// 把 bbox 映射到画布坐标
function transform(bbox: number[]) {
  const b = bounds.value
  const rangeX = b.maxX - b.minX || 1
  const rangeY = b.maxY - b.minY || 1
  const [x, y, w, h] = bbox
  return {
    left: ((x - b.minX) / rangeX) * 100 + '%',
    top: ((y - b.minY) / rangeY) * 100 + '%',
    width: (w / rangeX) * 100 + '%',
    height: (h / rangeY) * 100 + '%',
  }
}

function handleSelect(item: InventoryItem) {
  selectedItem.value = item
}

function getSnapshotUrl(path: string | null | undefined): string {
  return uploadUrl(path)
}

function statusLabel(item: InventoryItem): string {
  const map: Record<string, string> = {
    IN_STOCK: '在库',
    OUT_PENDING: '待确认',
    CONSUMED: '已消耗',
  }
  return map[item.status] || item.status
}

function legendDays(item: InventoryItem): string {
  const d = getRemainDays(item)
  if (!Number.isFinite(d)) return '未计算'
  if (d < 0) return `已过期 ${-d} 天`
  if (d === 0) return '今天到期'
  return `剩 ${d} 天`
}

const stats = computed(() => {
  const all = visibleItems.value
  return {
    total: all.length,
    expired: all.filter(i => getRemainDays(i) < 0).length,
    soon: all.filter(i => {
      const d = getRemainDays(i)
      return d >= 0 && d <= 3
    }).length,
    fresh: all.filter(i => getRemainDays(i) > 3).length,
  }
})

function updateCanvasSize() {
  nextTick(() => {
    if (canvasRef.value) {
      const rect = canvasRef.value.getBoundingClientRect()
      canvasSize.value = { w: rect.width, h: rect.height }
    }
  })
}

watch(filterStatus, () => { selectedItem.value = null })

// ---- WebSocket 实时同步 ----
const newItemIds = ref<Set<string>>(new Set())

const { connected: wsConnected } = useInventoryWS({
  scope: 'admin',
  onCreated: (it) => {
    if (items.value.some(x => x.id === it.id)) return
    items.value = [it as any, ...items.value]
    newItemIds.value.add(it.id)
    setTimeout(() => {
      newItemIds.value.delete(it.id)
      newItemIds.value = new Set(newItemIds.value)
    }, 1600)
    ElMessage({
      message: `📦 检测到新物品：${it.category}`,
      type: 'success',
      duration: 2000,
      grouping: true,
    })
  },
  onUpdated: (it) => {
    const idx = items.value.findIndex(x => x.id === it.id)
    if (idx === -1) {
      items.value = [it as any, ...items.value]
    } else {
      items.value.splice(idx, 1, it as any)
    }
  },
  onDeleted: (id) => {
    const idx = items.value.findIndex(x => x.id === id)
    if (idx !== -1) {
      items.value.splice(idx, 1)
      if (selectedItem.value?.id === id) selectedItem.value = null
    }
  },
})

onMounted(async () => {
  await fetchData()
  updateCanvasSize()
  window.addEventListener('resize', updateCanvasSize)
})
</script>

<template>
  <div v-loading="loading">
    <!-- 顶部筛选 -->
    <el-card shadow="never" style="margin-bottom: 16px">
      <el-form :inline="true">
        <el-form-item label="状态">
          <el-select v-model="filterStatus" clearable placeholder="全部" style="width: 140px">
            <el-option label="在库" value="IN_STOCK" />
            <el-option label="待确认" value="OUT_PENDING" />
            <el-option label="已消耗" value="CONSUMED" />
          </el-select>
        </el-form-item>
        <el-form-item>
          <el-button type="primary" @click="fetchData">刷新</el-button>
        </el-form-item>
      </el-form>
    </el-card>

    <!-- 统计 + 图例 -->
    <div class="map-stats">
      <div class="stats-left">
        <div class="stat-chip">总计 <strong>{{ stats.total }}</strong></div>
        <div class="stat-chip stat-fresh">充足 <strong>{{ stats.fresh }}</strong></div>
        <div class="stat-chip stat-soon">临期 <strong>{{ stats.soon }}</strong></div>
        <div class="stat-chip stat-expired">过期 <strong>{{ stats.expired }}</strong></div>
      </div>
      <div class="stats-right">
        <span class="ws-pill" :class="{ ok: wsConnected, off: !wsConnected }">
          <span class="ws-dot"></span>
          <span>{{ wsConnected ? '实时' : '离线' }}</span>
        </span>
        <span class="legend-dot" style="background: #00b42a"></span><span class="legend-label">充足 &gt; 3天</span>
        <span class="legend-dot" style="background: #fadb14"></span><span class="legend-label">1-3天</span>
        <span class="legend-dot" style="background: #ff7d00"></span><span class="legend-label">今天/明天</span>
        <span class="legend-dot" style="background: #f53f3f"></span><span class="legend-label">已过期</span>
      </div>
    </div>

    <!-- 主体：左侧画布 + 右侧详情 -->
    <div class="map-layout">
      <el-card shadow="never" class="canvas-card">
        <div ref="canvasRef" class="fridge-canvas">
          <!-- 网格背景 -->
          <div class="grid-bg"></div>

          <!-- 物品矩形 -->
          <div
            v-for="item in visibleItems"
            :key="item.id"
            class="item-rect"
            :class="{ active: selectedItem?.id === item.id, 'is-new': newItemIds.has(item.id) }"
            :style="{
              ...transform(item.bbox as number[]),
              background: getItemColor(item).bg,
              borderColor: getItemColor(item).border,
            }"
            @click="handleSelect(item)"
          >
            <div class="item-rect-label" :style="{ color: getItemColor(item).border }">
              {{ item.category }}
            </div>
            <div class="item-rect-sub">{{ legendDays(item) }}</div>
          </div>

          <!-- 空态 -->
          <div v-if="visibleItems.length === 0 && !loading" class="canvas-empty">
            <el-icon :size="48" color="var(--text-placeholder)"><Box /></el-icon>
            <p>当前筛选条件下没有带 bbox 的物品</p>
          </div>
        </div>
      </el-card>

      <!-- 右侧详情面板 -->
      <el-card shadow="never" class="detail-card">
        <template #header>
          <span class="card-title">物品详情</span>
        </template>
        <div v-if="selectedItem" class="detail-body">
          <div v-if="selectedItem.snapshot_path" class="detail-image">
            <el-image :src="getSnapshotUrl(selectedItem.snapshot_path)" fit="cover" style="width: 100%; height: 180px; border-radius: 8px" />
          </div>
          <div class="detail-name">{{ selectedItem.category }}</div>
          <el-descriptions :column="1" size="small" border>
            <el-descriptions-item label="状态">
              <el-tag size="small" round>{{ statusLabel(selectedItem) }}</el-tag>
            </el-descriptions-item>
            <el-descriptions-item label="保鲜">
              <span :style="{ color: getItemColor(selectedItem).border, fontWeight: 600 }">
                {{ legendDays(selectedItem) }}
              </span>
            </el-descriptions-item>
            <el-descriptions-item label="剩余比例">
              <el-progress :percentage="Math.round(selectedItem.remain_ratio * 100)" :stroke-width="6" />
            </el-descriptions-item>
            <el-descriptions-item label="bbox">
              <code class="mono">[{{ (selectedItem.bbox as number[]).join(', ') }}]</code>
            </el-descriptions-item>
            <el-descriptions-item v-if="selectedItem.agent_metadata?.storage_advice" label="存储建议">
              {{ selectedItem.agent_metadata.storage_advice }}
            </el-descriptions-item>
          </el-descriptions>
        </div>
        <div v-else class="detail-empty">
          <el-icon :size="36" color="var(--text-placeholder)"><Pointer /></el-icon>
          <p>点击左侧物品查看详情</p>
        </div>
      </el-card>
    </div>
  </div>
</template>

<style scoped>
.map-stats {
  display: flex;
  align-items: center;
  justify-content: space-between;
  flex-wrap: wrap;
  gap: 12px;
  margin-bottom: 16px;
}

.stats-left {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}

.stat-chip {
  padding: 6px 14px;
  background: var(--bg-card);
  border-radius: 999px;
  font-size: 13px;
  color: var(--text-secondary);
  box-shadow: var(--shadow-sm);
}

.stat-chip strong {
  color: var(--text-primary);
  font-weight: 700;
  margin-left: 4px;
}

.stat-fresh strong { color: #00b42a; }
.stat-soon strong { color: #ff7d00; }
.stat-expired strong { color: #f53f3f; }

.stats-right {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
  color: var(--text-secondary);
}

.legend-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  margin-left: 8px;
}

.legend-label {
  margin-right: 4px;
}

.map-layout {
  display: grid;
  grid-template-columns: 1fr 320px;
  gap: 16px;
  height: calc(100vh - 280px);
  min-height: 500px;
}

.canvas-card {
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.canvas-card :deep(.el-card__body) {
  flex: 1;
  padding: 16px !important;
  display: flex;
  min-height: 0;
}

.fridge-canvas {
  flex: 1;
  position: relative;
  border-radius: 12px;
  background: linear-gradient(135deg, var(--bg-soft) 0%, var(--bg-color) 100%);
  border: 2px solid var(--border-color);
  overflow: hidden;
}

.grid-bg {
  position: absolute;
  inset: 0;
  background-image:
    linear-gradient(to right, rgba(22,93,255,0.04) 1px, transparent 1px),
    linear-gradient(to bottom, rgba(22,93,255,0.04) 1px, transparent 1px);
  background-size: 40px 40px;
  pointer-events: none;
}

.item-rect {
  position: absolute;
  border: 2px solid;
  border-radius: 6px;
  cursor: pointer;
  display: flex;
  flex-direction: column;
  justify-content: center;
  align-items: center;
  padding: 4px;
  transition: transform 0.15s, box-shadow 0.15s, z-index 0s;
  overflow: hidden;
  min-width: 40px;
  min-height: 30px;
}

.item-rect.is-new {
  animation: rect-pop 0.45s ease-out, rect-pulse 1.4s ease-out;
  z-index: 8;
}

@keyframes rect-pop {
  from { transform: scale(0.4); opacity: 0; }
  to   { transform: scale(1); opacity: 1; }
}

@keyframes rect-pulse {
  0%   { box-shadow: 0 0 0 0 rgba(14, 165, 233, 0.7); }
  60%  { box-shadow: 0 0 0 12px rgba(14, 165, 233, 0); }
  100% { box-shadow: 0 0 0 0 rgba(14, 165, 233, 0); }
}

.ws-pill {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 2px 10px;
  border-radius: 999px;
  font-size: 11px;
  font-weight: 600;
  margin-right: 8px;
}

.ws-pill.ok {
  background: rgba(0, 180, 42, 0.12);
  color: #00b42a;
}

.ws-pill.off {
  background: rgba(245, 63, 63, 0.12);
  color: #f53f3f;
}

.ws-pill .ws-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: currentColor;
  animation: ws-blink 1.4s ease-in-out infinite;
}

@keyframes ws-blink {
  0%, 100% { opacity: 1; }
  50%      { opacity: 0.4; }
}

.item-rect:hover {
  transform: scale(1.04);
  box-shadow: 0 4px 12px rgba(0,0,0,0.15);
  z-index: 5;
}

.item-rect.active {
  box-shadow: 0 0 0 3px rgba(22,93,255,0.4), 0 6px 16px rgba(0,0,0,0.18);
  z-index: 10;
}

.item-rect-label {
  font-weight: 700;
  font-size: 13px;
  text-align: center;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  max-width: 100%;
}

.item-rect-sub {
  font-size: 11px;
  color: var(--text-secondary);
  margin-top: 2px;
  white-space: nowrap;
}

.canvas-empty {
  position: absolute;
  inset: 0;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 12px;
  color: var(--text-placeholder);
  font-size: 14px;
}

.detail-card :deep(.el-card__body) {
  padding: 16px !important;
}

.card-title {
  font-size: 15px;
  font-weight: 600;
}

.detail-body {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.detail-image {
  border-radius: 8px;
  overflow: hidden;
}

.detail-name {
  font-size: 18px;
  font-weight: 700;
  color: var(--text-primary);
}

.detail-empty {
  text-align: center;
  padding: 60px 0;
  color: var(--text-placeholder);
  display: flex;
  flex-direction: column;
  gap: 12px;
  align-items: center;
  font-size: 13px;
}

.mono {
  font-family: 'SFMono-Regular', Consolas, monospace;
  font-size: 12px;
  color: var(--text-primary);
  background: var(--bg-color);
  padding: 2px 6px;
  border-radius: 4px;
}

@media (max-width: 1100px) {
  .map-layout {
    grid-template-columns: 1fr;
    height: auto;
  }
}
</style>
