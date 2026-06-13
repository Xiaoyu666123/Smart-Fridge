<script setup lang="ts">
import { ref, computed, onMounted, onBeforeUnmount } from 'vue'
import { use } from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import { PieChart, BarChart, LineChart } from 'echarts/charts'
import {
  TitleComponent,
  TooltipComponent,
  LegendComponent,
  GridComponent,
  DatasetComponent,
} from 'echarts/components'
import VChart from 'vue-echarts'
import { getInventoryList, type InventoryItem } from '@/api/admin/inventory'
import { getEventLogs, type EventLog } from '@/api/admin/event'
import { getUsageSummary, type UsageSummary } from '@/api/admin/usage'
import { useInventoryWS } from '@/composables/useInventoryWS'
import { useChartTheme } from '@/composables/useChartTheme'
import AnimatedNumber from '@/components/AnimatedNumber.vue'

use([
  CanvasRenderer,
  PieChart,
  BarChart,
  LineChart,
  TitleComponent,
  TooltipComponent,
  LegendComponent,
  GridComponent,
  DatasetComponent,
])

const chartTheme = useChartTheme()

const loading = ref(false)
const items = ref<InventoryItem[]>([])
const events = ref<EventLog[]>([])
const usageSummary = ref<UsageSummary | null>(null)

const PALETTE = ['#165dff', '#00b42a', '#ff7d00', '#f53f3f', '#722ed1', '#0fc6c2', '#3491fa', '#86909c', '#eb2f96', '#13c2c2']

async function fetchAll() {
  loading.value = true
  try {
    const [invRes, evtRes, usageRes] = await Promise.all([
      getInventoryList(),
      getEventLogs(),
      getUsageSummary(7).catch(() => null),
    ])
    items.value = invRes
    events.value = evtRes
    usageSummary.value = usageRes
  } catch (e) {
    console.error(e)
  } finally {
    loading.value = false
  }
}

// ---- 顶部统计 ----

function getRemainDays(item: InventoryItem): number {
  const expireAt = item.agent_metadata?.expire_at
  if (!expireAt) return Number.POSITIVE_INFINITY
  return Math.ceil((new Date(expireAt).getTime() - Date.now()) / 86400000)
}

const stats = computed(() => {
  const inStock = items.value.filter(i => i.status === 'IN_STOCK')
  const expired = inStock.filter(i => getRemainDays(i) < 0).length
  const today = inStock.filter(i => {
    const d = getRemainDays(i)
    return d >= 0 && d <= 0
  }).length
  const within3 = inStock.filter(i => {
    const d = getRemainDays(i)
    return d > 0 && d <= 3
  }).length
  return {
    total: items.value.length,
    inStock: inStock.length,
    expired,
    today,
    within3,
  }
})

// ---- 分类占比饼图 ----

const categoryPieOption = computed(() => {
  const map = new Map<string, number>()
  items.value
    .filter(i => i.status === 'IN_STOCK')
    .forEach(i => map.set(i.category, (map.get(i.category) || 0) + 1))

  const data = Array.from(map.entries())
    .map(([name, value]) => ({ name, value }))
    .sort((a, b) => b.value - a.value)

  return {
    color: PALETTE,
    tooltip: { trigger: 'item', formatter: '{b}: {c} ({d}%)' },
    legend: { type: 'scroll', orient: 'vertical', right: 10, top: 'center', itemGap: 8, textStyle: { fontSize: 12 } },
    series: [{
      type: 'pie',
      radius: ['52%', '78%'],
      center: ['38%', '50%'],
      avoidLabelOverlap: true,
      itemStyle: { borderRadius: 6, borderColor: '#fff', borderWidth: 2 },
      label: { show: false },
      labelLine: { show: false },
      emphasis: { label: { show: true, fontSize: 14, fontWeight: 600 } },
      data,
    }],
  }
})

// ---- 临期分布柱图 ----

const expiryBarOption = computed(() => {
  const buckets = [
    { label: '已过期', match: (d: number) => d < 0, color: '#f53f3f' },
    { label: '今天', match: (d: number) => d === 0, color: '#ff7d00' },
    { label: '1-3天', match: (d: number) => d >= 1 && d <= 3, color: '#fadb14' },
    { label: '4-7天', match: (d: number) => d >= 4 && d <= 7, color: '#52c41a' },
    { label: '7天以上', match: (d: number) => d > 7, color: '#165dff' },
    { label: '未知', match: (d: number) => !Number.isFinite(d), color: '#86909c' },
  ]
  const counts = buckets.map(b => 0)
  items.value
    .filter(i => i.status === 'IN_STOCK')
    .forEach(i => {
      const d = getRemainDays(i)
      const idx = buckets.findIndex(b => b.match(d))
      if (idx >= 0) counts[idx]++
    })

  return {
    tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' } },
    grid: { left: 40, right: 16, top: 16, bottom: 28 },
    xAxis: {
      type: 'category',
      data: buckets.map(b => b.label),
      axisLine: { lineStyle: { color: '#e5e6eb' } },
      axisLabel: { color: '#86909c', fontSize: 12 },
      axisTick: { show: false },
    },
    yAxis: {
      type: 'value',
      splitLine: { lineStyle: { color: '#f2f3f5' } },
      axisLabel: { color: '#86909c', fontSize: 12 },
    },
    series: [{
      type: 'bar',
      data: counts.map((v, i) => ({ value: v, itemStyle: { color: buckets[i].color, borderRadius: [6, 6, 0, 0] } })),
      barMaxWidth: 40,
      label: { show: true, position: 'top', color: '#1d2129', fontWeight: 600 },
    }],
  }
})

// ---- 近 30 天入库/出库趋势 ----

const trendLineOption = computed(() => {
  const days: string[] = []
  const now = new Date()
  now.setHours(0, 0, 0, 0)
  for (let i = 29; i >= 0; i--) {
    const d = new Date(now.getTime() - i * 86400000)
    days.push(`${d.getMonth() + 1}/${d.getDate()}`)
  }
  const dayKey = (date: Date) => `${date.getMonth() + 1}/${date.getDate()}`
  const inSeries = new Array(30).fill(0)
  const outSeries = new Array(30).fill(0)
  events.value.forEach(e => {
    if (!e.create_at) return
    const d = new Date(e.create_at)
    d.setHours(0, 0, 0, 0)
    const idx = days.indexOf(dayKey(d))
    if (idx < 0) return
    if (e.event_type === 'ITEM_IN') inSeries[idx]++
    else if (e.event_type === 'ITEM_OUT') outSeries[idx]++
  })

  return {
    color: ['#00b42a', '#ff7d00'],
    tooltip: { trigger: 'axis' },
    legend: { data: ['入库', '出库'], top: 0, right: 10, textStyle: { fontSize: 12 } },
    grid: { left: 40, right: 16, top: 36, bottom: 30 },
    xAxis: {
      type: 'category',
      boundaryGap: false,
      data: days,
      axisLabel: { color: '#86909c', fontSize: 11, interval: 3 },
      axisLine: { lineStyle: { color: '#e5e6eb' } },
    },
    yAxis: {
      type: 'value',
      splitLine: { lineStyle: { color: '#f2f3f5' } },
      axisLabel: { color: '#86909c', fontSize: 12 },
    },
    series: [
      {
        name: '入库', type: 'line', smooth: true, data: inSeries,
        showSymbol: false,
        areaStyle: { color: { type: 'linear', x: 0, y: 0, x2: 0, y2: 1, colorStops: [
          { offset: 0, color: 'rgba(0,180,42,0.3)' }, { offset: 1, color: 'rgba(0,180,42,0)' }
        ]}},
      },
      {
        name: '出库', type: 'line', smooth: true, data: outSeries,
        showSymbol: false,
        areaStyle: { color: { type: 'linear', x: 0, y: 0, x2: 0, y2: 1, colorStops: [
          { offset: 0, color: 'rgba(255,125,0,0.3)' }, { offset: 1, color: 'rgba(255,125,0,0)' }
        ]}},
      },
    ],
  }
})

// ---- 消耗 Top ----

const topConsumed = computed(() => {
  const map = new Map<string, number>()
  events.value
    .filter(e => e.event_type === 'ITEM_OUT')
    .forEach(e => {
      // event 关联 inventory，找回 category
      const inv = items.value.find(i => i.id === e.inventory_id)
      const key = inv?.category || '未知'
      map.set(key, (map.get(key) || 0) + 1)
    })
  return Array.from(map.entries())
    .map(([category, count]) => ({ category, count }))
    .sort((a, b) => b.count - a.count)
    .slice(0, 8)
})

const topMax = computed(() => Math.max(1, ...topConsumed.value.map(t => t.count)))

// ---- 实时同步 ----

let refreshTimer: ReturnType<typeof setInterval> | null = null

const wsConnection = useInventoryWS({
  scope: 'admin',
  onCreated: (it) => {
    if (items.value.some(i => i.id === it.id)) return
    items.value = [it as any, ...items.value]
  },
  onUpdated: (it) => {
    const idx = items.value.findIndex(i => i.id === it.id)
    if (idx === -1) {
      items.value = [it as any, ...items.value]
    } else {
      items.value.splice(idx, 1, it as any)
    }
  },
  onDeleted: (id) => {
    const idx = items.value.findIndex(i => i.id === id)
    if (idx !== -1) items.value.splice(idx, 1)
  },
})

const wsConnected = wsConnection.connected

async function refreshEvents() {
  // 仅刷新事件流，库存有 WS 推送不需要全量拉
  try {
    events.value = await getEventLogs()
  } catch {
    // silent
  }
}

onMounted(() => {
  fetchAll()
  // 60s 拉一次事件，保持趋势图新鲜
  refreshTimer = setInterval(refreshEvents, 60_000)
})

onBeforeUnmount(() => {
  if (refreshTimer) clearInterval(refreshTimer)
})
</script>

<template>
  <div v-loading="loading" class="dashboard">
    <!-- 实时状态条 -->
    <div class="realtime-bar">
      <span class="ws-dot" :class="{ ok: wsConnected, off: !wsConnected }"></span>
      <span class="ws-text">{{ wsConnected ? '实时同步中' : '实时连接断开，将自动重试' }}</span>
      <span class="realtime-spacer"></span>
      <span class="realtime-hint">事件趋势 60s 自动刷新</span>
    </div>

    <!-- 顶部统计卡 -->
    <div class="stat-row">
      <div class="stat-card">
        <div class="stat-icon" style="background: var(--brand-primary-light); color: var(--brand-primary)">
          <el-icon :size="22"><Box /></el-icon>
        </div>
        <div class="stat-info">
          <div class="stat-value"><AnimatedNumber :value="stats.total" /></div>
          <div class="stat-label">总记录</div>
        </div>
      </div>
      <div class="stat-card">
        <div class="stat-icon" style="background: #e8f7e8; color: #00b42a">
          <el-icon :size="22"><CircleCheck /></el-icon>
        </div>
        <div class="stat-info">
          <div class="stat-value"><AnimatedNumber :value="stats.inStock" /></div>
          <div class="stat-label">在库</div>
        </div>
      </div>
      <div class="stat-card">
        <div class="stat-icon" style="background: #ffece8; color: #f53f3f">
          <el-icon :size="22"><Warning /></el-icon>
        </div>
        <div class="stat-info">
          <div class="stat-value"><AnimatedNumber :value="stats.expired" /></div>
          <div class="stat-label">已过期</div>
        </div>
      </div>
      <div class="stat-card">
        <div class="stat-icon" style="background: #fff3e8; color: #ff7d00">
          <el-icon :size="22"><AlarmClock /></el-icon>
        </div>
        <div class="stat-info">
          <div class="stat-value"><AnimatedNumber :value="stats.today" /></div>
          <div class="stat-label">今天到期</div>
        </div>
      </div>
      <div class="stat-card">
        <div class="stat-icon" style="background: #fff7e6; color: #fa8c16">
          <el-icon :size="22"><Clock /></el-icon>
        </div>
        <div class="stat-info">
          <div class="stat-value"><AnimatedNumber :value="stats.within3" /></div>
          <div class="stat-label">3天内到期</div>
        </div>
      </div>
    </div>

    <!-- 第二行：API 用量（仅有数据时显示） -->
    <div v-if="usageSummary && usageSummary.total_calls > 0" class="stat-row" style="grid-template-columns: repeat(4, 1fr); margin-bottom: 16px">
      <div class="stat-card">
        <div class="stat-icon" style="background: var(--brand-primary-light); color: var(--brand-primary-dark)">
          <el-icon :size="22"><Money /></el-icon>
        </div>
        <div class="stat-info">
          <div class="stat-value"><AnimatedNumber :value="usageSummary.total_cost_usd || 0" :decimals="4" prefix="$" /></div>
          <div class="stat-label">近 7 天费用</div>
        </div>
      </div>
      <div class="stat-card">
        <div class="stat-icon" style="background: #ecfeff; color: #06b6d4">
          <el-icon :size="22"><Histogram /></el-icon>
        </div>
        <div class="stat-info">
          <div class="stat-value"><AnimatedNumber :value="usageSummary.total_tokens || 0" format="compact" /></div>
          <div class="stat-label">近 7 天 Tokens</div>
        </div>
      </div>
      <div class="stat-card">
        <div class="stat-icon" style="background: #fff7ed; color: #f59e0b">
          <el-icon :size="22"><DataAnalysis /></el-icon>
        </div>
        <div class="stat-info">
          <div class="stat-value"><AnimatedNumber :value="usageSummary.total_calls" /></div>
          <div class="stat-label">API 调用次数</div>
        </div>
      </div>
      <div class="stat-card">
        <div class="stat-icon" :style="{ background: '#fef2f2', color: '#ef4444' }">
          <el-icon :size="22"><Warning /></el-icon>
        </div>
        <div class="stat-info">
          <div class="stat-value"><AnimatedNumber :value="usageSummary.failed_calls" /></div>
          <div class="stat-label">调用失败</div>
        </div>
      </div>
    </div>

    <!-- 图表行1: 分类占比 + 临期分布 -->
    <div class="chart-row">
      <el-card shadow="never" class="chart-card">
        <template #header>
          <span class="card-title">分类占比</span>
        </template>
        <v-chart v-if="items.length" :theme="chartTheme" :option="categoryPieOption" autoresize class="chart" />
        <el-empty v-else description="暂无数据" />
      </el-card>
      <el-card shadow="never" class="chart-card">
        <template #header>
          <span class="card-title">临期分布</span>
        </template>
        <v-chart v-if="items.length" :theme="chartTheme" :option="expiryBarOption" autoresize class="chart" />
        <el-empty v-else description="暂无数据" />
      </el-card>
    </div>

    <!-- 图表行2: 趋势 + Top -->
    <div class="chart-row">
      <el-card shadow="never" class="chart-card chart-card-wide">
        <template #header>
          <span class="card-title">近 30 天入库 / 出库趋势</span>
        </template>
        <v-chart v-if="events.length" :theme="chartTheme" :option="trendLineOption" autoresize class="chart" />
        <el-empty v-else description="暂无事件记录" />
      </el-card>
      <el-card shadow="never" class="chart-card">
        <template #header>
          <span class="card-title">消耗 Top</span>
        </template>
        <div v-if="topConsumed.length" class="top-list">
          <div v-for="(item, i) in topConsumed" :key="item.category" class="top-item">
            <div class="top-rank" :class="{ 'is-top3': i < 3 }">{{ i + 1 }}</div>
            <div class="top-content">
              <div class="top-row">
                <span class="top-name">{{ item.category }}</span>
                <span class="top-count">{{ item.count }} 次</span>
              </div>
              <div class="top-bar">
                <div class="top-bar-fill" :style="{ width: (item.count / topMax * 100) + '%' }"></div>
              </div>
            </div>
          </div>
        </div>
        <el-empty v-else description="暂无消耗记录" />
      </el-card>
    </div>
  </div>
</template>

<style scoped>
.dashboard {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.realtime-bar {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 14px;
  background: var(--bg-card);
  border: 1px solid var(--border-color);
  border-radius: 999px;
  font-size: 12px;
  color: var(--text-secondary);
  align-self: flex-start;
}

.realtime-bar .ws-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  flex-shrink: 0;
}

.realtime-bar .ws-dot.ok {
  background: #00b42a;
  box-shadow: 0 0 0 4px rgba(0, 180, 42, 0.18);
  animation: ws-pulse 1.6s ease-in-out infinite;
}

.realtime-bar .ws-dot.off {
  background: #f53f3f;
  box-shadow: 0 0 0 4px rgba(245, 63, 63, 0.18);
}

@keyframes ws-pulse {
  0%, 100% { box-shadow: 0 0 0 4px rgba(0, 180, 42, 0.18); }
  50%      { box-shadow: 0 0 0 8px rgba(0, 180, 42, 0.06); }
}

.realtime-bar .ws-text {
  font-weight: 500;
  color: var(--text-primary);
}

.realtime-spacer {
  width: 12px;
  border-left: 1px solid var(--border-color);
  height: 14px;
}

.realtime-hint {
  color: var(--text-placeholder);
}

.stat-row {
  display: grid;
  grid-template-columns: repeat(5, 1fr);
  gap: 16px;
}

.stat-card {
  display: flex;
  align-items: center;
  gap: 14px;
  padding: 18px 20px;
  background: var(--bg-card);
  border-radius: var(--radius-md);
  box-shadow: var(--shadow-sm);
  transition: box-shadow 0.2s;
}

.stat-card:hover {
  box-shadow: var(--shadow-md);
}

.stat-icon {
  width: 44px;
  height: 44px;
  border-radius: 12px;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.stat-value {
  font-size: 22px;
  font-weight: 700;
  color: var(--text-primary);
  line-height: 1.2;
}

.stat-label {
  font-size: 12px;
  color: var(--text-secondary);
  margin-top: 2px;
}

.chart-row {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 16px;
}

.chart-row:last-child {
  grid-template-columns: 2fr 1fr;
}

.chart-card {
  min-height: 360px;
  display: flex;
  flex-direction: column;
}

.chart-card :deep(.el-card__body) {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-height: 0;
}

.card-title {
  font-size: 15px;
  font-weight: 600;
}

.chart {
  flex: 1;
  width: 100%;
  min-height: 280px;
}

.top-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.top-item {
  display: flex;
  align-items: center;
  gap: 12px;
}

.top-rank {
  width: 24px;
  height: 24px;
  border-radius: 6px;
  background: var(--bg-soft);
  color: var(--text-secondary);
  font-size: 12px;
  font-weight: 600;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.top-rank.is-top3 {
  background: var(--brand-primary);
  color: #fff;
}

.top-content {
  flex: 1;
  min-width: 0;
}

.top-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 4px;
}

.top-name {
  font-size: 13px;
  font-weight: 500;
  color: var(--text-primary);
}

.top-count {
  font-size: 12px;
  color: var(--text-secondary);
}

.top-bar {
  height: 6px;
  background: var(--bg-color);
  border-radius: 3px;
  overflow: hidden;
}

.top-bar-fill {
  height: 100%;
  background: linear-gradient(90deg, var(--brand-primary), #4080ff);
  border-radius: 3px;
  transition: width 0.5s ease;
}

@media (max-width: 1200px) {
  .stat-row {
    grid-template-columns: repeat(3, 1fr);
  }
  .chart-row,
  .chart-row:last-child {
    grid-template-columns: 1fr;
  }
}
</style>
