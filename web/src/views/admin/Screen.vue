<script setup lang="ts">
/**
 * 数据可视化大屏（admin/screen）。
 * 全屏黑色背景 + 大字 + ECharts + 实时 WS 滚动。
 * 适合演示 / 答辩 / 现场展示。
 */
import { ref, computed, onMounted, onBeforeUnmount } from 'vue'
import { use } from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import { LineChart, BarChart, PieChart } from 'echarts/charts'
import { TooltipComponent, GridComponent, LegendComponent } from 'echarts/components'
import VChart from 'vue-echarts'
import { getInventoryList, type InventoryItem } from '@/api/admin/inventory'
import { getEventLogs, type EventLog } from '@/api/admin/event'
import { getWasteAnalytics, type WasteAnalytics } from '@/api/admin/stats'
import { listDevices, type DeviceItem } from '@/api/admin/device'
import { useInventoryWS } from '@/composables/useInventoryWS'
import AnimatedNumber from '@/components/AnimatedNumber.vue'

use([CanvasRenderer, LineChart, BarChart, PieChart, TooltipComponent, GridComponent, LegendComponent])

const items = ref<InventoryItem[]>([])
const events = ref<EventLog[]>([])
const waste = ref<WasteAnalytics | null>(null)
const devices = ref<DeviceItem[]>([])
const realtimeFeed = ref<{ id: string; ts: string; type: string; text: string; tone: string }[]>([])
let pollTimer: ReturnType<typeof setInterval> | null = null
let clockTimer: ReturnType<typeof setInterval> | null = null
const now = ref(new Date())

async function fetchAll() {
  try {
    const [invRes, evtRes, wasteRes, devRes] = await Promise.all([
      getInventoryList(),
      getEventLogs(),
      getWasteAnalytics(30).catch(() => null),
      listDevices().catch(() => []),
    ])
    items.value = invRes
    events.value = evtRes
    waste.value = wasteRes
    devices.value = devRes
  } catch (e) {
    console.error(e)
  }
}

// ---- KPI ----
const stats = computed(() => {
  const inStock = items.value.filter(i => i.status === 'IN_STOCK')
  const expired = inStock.filter(i => {
    const e = i.agent_metadata?.expire_at
    return e && new Date(e).getTime() < Date.now()
  }).length
  const soon = inStock.filter(i => {
    const e = i.agent_metadata?.expire_at
    if (!e) return false
    const d = (new Date(e).getTime() - Date.now()) / 86400000
    return d >= 0 && d <= 3
  }).length
  return {
    total: items.value.length,
    inStock: inStock.length,
    expired,
    soon,
    online: devices.value.filter(d => d.live_status === 'online').length,
    deviceTotal: devices.value.length,
    wasteRate: Math.round(((waste.value?.waste_rate || 0) * 100)),
    wastedValue: waste.value?.wasted_value || 0,
  }
})

// ---- 趋势线 ----
const trendOption = computed(() => {
  const days: string[] = []
  const inSeries: number[] = []
  const outSeries: number[] = []
  const today = new Date()
  today.setHours(0, 0, 0, 0)
  for (let i = 13; i >= 0; i--) {
    const d = new Date(today.getTime() - i * 86400000)
    days.push(`${d.getMonth() + 1}/${d.getDate()}`)
    inSeries.push(0)
    outSeries.push(0)
  }
  events.value.forEach(e => {
    if (!e.create_at) return
    const d = new Date(e.create_at)
    d.setHours(0, 0, 0, 0)
    const idx = Math.floor((d.getTime() - (today.getTime() - 13 * 86400000)) / 86400000)
    if (idx < 0 || idx > 13) return
    if (e.event_type === 'ITEM_IN') inSeries[idx]++
    else if (e.event_type === 'ITEM_OUT') outSeries[idx]++
  })
  return {
    backgroundColor: 'transparent',
    color: ['#0ea5e9', '#fa8c16'],
    tooltip: { trigger: 'axis', backgroundColor: 'rgba(0,0,0,0.8)', borderColor: '#0ea5e9', textStyle: { color: '#fff' } },
    legend: { data: ['入库', '出库'], top: 8, right: 16, textStyle: { color: '#94a3b8', fontSize: 12 } },
    grid: { left: 50, right: 24, top: 40, bottom: 36 },
    xAxis: {
      type: 'category', boundaryGap: false, data: days,
      axisLabel: { color: '#64748b', fontSize: 11 },
      axisLine: { lineStyle: { color: '#1e293b' } },
    },
    yAxis: {
      type: 'value',
      splitLine: { lineStyle: { color: '#1e293b' } },
      axisLabel: { color: '#64748b' },
    },
    series: [
      {
        name: '入库', type: 'line', smooth: true, data: inSeries, showSymbol: false,
        lineStyle: { width: 2.5 },
        areaStyle: { color: { type: 'linear', x: 0, y: 0, x2: 0, y2: 1, colorStops: [
          { offset: 0, color: 'rgba(14, 165, 233,0.45)' },
          { offset: 1, color: 'rgba(14, 165, 233,0)' },
        ]}},
      },
      {
        name: '出库', type: 'line', smooth: true, data: outSeries, showSymbol: false,
        lineStyle: { width: 2.5 },
        areaStyle: { color: { type: 'linear', x: 0, y: 0, x2: 0, y2: 1, colorStops: [
          { offset: 0, color: 'rgba(250,140,22,0.45)' },
          { offset: 1, color: 'rgba(250,140,22,0)' },
        ]}},
      },
    ],
  }
})

const expiryDistOption = computed(() => {
  const buckets: { name: string; value: number; color: string }[] = [
    { name: '已过期', value: 0, color: '#f53f3f' },
    { name: '今/明天', value: 0, color: '#fa8c16' },
    { name: '3 天内', value: 0, color: '#fadb14' },
    { name: '7 天内', value: 0, color: '#0ea5e9' },
    { name: '充足', value: 0, color: '#06b6d4' },
  ]
  items.value.filter(i => i.status === 'IN_STOCK').forEach(i => {
    const e = i.agent_metadata?.expire_at
    if (!e) { buckets[4].value++; return }
    const d = (new Date(e).getTime() - Date.now()) / 86400000
    if (d < 0) buckets[0].value++
    else if (d <= 1) buckets[1].value++
    else if (d <= 3) buckets[2].value++
    else if (d <= 7) buckets[3].value++
    else buckets[4].value++
  })
  return {
    backgroundColor: 'transparent',
    tooltip: { trigger: 'item', backgroundColor: 'rgba(0,0,0,0.8)', textStyle: { color: '#fff' } },
    series: [{
      type: 'pie',
      radius: ['55%', '80%'],
      center: ['50%', '50%'],
      avoidLabelOverlap: true,
      itemStyle: { borderRadius: 6, borderColor: '#0a1014', borderWidth: 2 },
      label: { show: true, color: '#cbd5e1', fontSize: 11, formatter: '{b}\n{c}' },
      labelLine: { lineStyle: { color: '#475569' } },
      data: buckets.map(b => ({ name: b.name, value: b.value, itemStyle: { color: b.color } })),
    }],
  }
})

const topCategoryOption = computed(() => {
  const map = new Map<string, number>()
  items.value.filter(i => i.status === 'IN_STOCK').forEach(i =>
    map.set(i.category, (map.get(i.category) || 0) + 1)
  )
  const entries = Array.from(map.entries()).sort((a, b) => b[1] - a[1]).slice(0, 8)
  return {
    backgroundColor: 'transparent',
    color: ['#0ea5e9'],
    grid: { left: 90, right: 24, top: 16, bottom: 16 },
    tooltip: { trigger: 'axis', backgroundColor: 'rgba(0,0,0,0.8)', textStyle: { color: '#fff' } },
    xAxis: { type: 'value', splitLine: { lineStyle: { color: '#1e293b' } }, axisLabel: { color: '#64748b' } },
    yAxis: {
      type: 'category',
      data: entries.map(e => e[0]).reverse(),
      axisLabel: { color: '#cbd5e1' },
      axisLine: { lineStyle: { color: '#1e293b' } },
    },
    series: [{
      type: 'bar',
      barMaxWidth: 16,
      data: entries.map(e => e[1]).reverse(),
      itemStyle: {
        color: { type: 'linear', x: 0, y: 0, x2: 1, y2: 0, colorStops: [
          { offset: 0, color: '#06b6d4' }, { offset: 1, color: '#0ea5e9' },
        ]},
        borderRadius: [0, 6, 6, 0],
      },
      label: { show: true, position: 'right', color: '#fff', fontWeight: 600 },
    }],
  }
})

// ---- WS 实时滚动 ----
function pushFeed(type: string, text: string, tone: string) {
  const ts = new Date()
  const pad = (n: number) => n.toString().padStart(2, '0')
  realtimeFeed.value.unshift({
    id: ts.getTime() + Math.random().toString(36).slice(2, 8),
    ts: `${pad(ts.getHours())}:${pad(ts.getMinutes())}:${pad(ts.getSeconds())}`,
    type,
    text,
    tone,
  })
  if (realtimeFeed.value.length > 20) realtimeFeed.value.pop()
}

useInventoryWS({
  scope: 'admin',
  onCreated: (it, source) => {
    if (!items.value.some(x => x.id === it.id)) {
      items.value = [it as any, ...items.value]
    }
    pushFeed(
      source === 'agent' ? '端侧入库' : source === 'bulk' ? '批量入库' : '手动入库',
      `${it.category}${(it as any).label_data?.brand ? ' (' + (it as any).label_data.brand + ')' : ''}`,
      'green',
    )
  },
  onUpdated: (it, source, prev) => {
    const idx = items.value.findIndex(x => x.id === it.id)
    if (idx !== -1) items.value.splice(idx, 1, it as any)
    if (prev === 'IN_STOCK' && it.status === 'OUT_PENDING') {
      pushFeed(source === 'agent' ? '端侧出库' : '出库', it.category, 'orange')
    }
  },
  onDeleted: (id) => {
    const idx = items.value.findIndex(x => x.id === id)
    if (idx !== -1) {
      const removed = items.value[idx]
      items.value.splice(idx, 1)
      pushFeed('删除', removed.category, 'red')
    }
  },
})

// 时钟
function tick() { now.value = new Date() }

const clockText = computed(() => {
  const d = now.value
  const pad = (n: number) => n.toString().padStart(2, '0')
  return `${pad(d.getHours())}:${pad(d.getMinutes())}:${pad(d.getSeconds())}`
})

const dateText = computed(() => {
  const d = now.value
  return `${d.getFullYear()}-${(d.getMonth() + 1).toString().padStart(2, '0')}-${d.getDate().toString().padStart(2, '0')} 周${'日一二三四五六'[d.getDay()]}`
})

const greeting = computed(() => {
  const h = now.value.getHours()
  if (h < 6) return '凌晨好'
  if (h < 12) return '早上好'
  if (h < 14) return '中午好'
  if (h < 18) return '下午好'
  return '晚上好'
})

// 全屏
function toggleFullscreen() {
  if (document.fullscreenElement) {
    document.exitFullscreen?.()
  } else {
    document.documentElement.requestFullscreen?.()
  }
}

onMounted(() => {
  fetchAll()
  pollTimer = setInterval(fetchAll, 30_000)  // 30s 拉一次
  clockTimer = setInterval(tick, 1000)
})

onBeforeUnmount(() => {
  if (pollTimer) clearInterval(pollTimer)
  if (clockTimer) clearInterval(clockTimer)
})
</script>

<template>
  <div class="screen">
    <!-- 顶栏 -->
    <header class="screen-header">
      <div class="screen-title-zone">
        <h1 class="screen-title">智能冰箱食材管理 <span>· 实时监控大屏</span></h1>
        <div class="screen-greet">{{ greeting }}，管理员</div>
      </div>
      <div class="screen-clock">
        <div class="clock-time">{{ clockText }}</div>
        <div class="clock-date">{{ dateText }}</div>
      </div>
      <button class="screen-fs" @click="toggleFullscreen" title="全屏">
        <el-icon :size="20"><FullScreen /></el-icon>
      </button>
    </header>

    <!-- KPI 行 -->
    <div class="kpi-row">
      <div class="kpi kpi-primary">
        <div class="kpi-label">总库存</div>
        <div class="kpi-value"><AnimatedNumber :value="stats.total" /></div>
        <div class="kpi-foot">在库 <strong>{{ stats.inStock }}</strong></div>
      </div>
      <div class="kpi kpi-warn">
        <div class="kpi-label">即将到期</div>
        <div class="kpi-value"><AnimatedNumber :value="stats.soon" /></div>
        <div class="kpi-foot">3 天内</div>
      </div>
      <div class="kpi kpi-danger">
        <div class="kpi-label">已过期</div>
        <div class="kpi-value"><AnimatedNumber :value="stats.expired" /></div>
        <div class="kpi-foot">需处理</div>
      </div>
      <div class="kpi kpi-info">
        <div class="kpi-label">在线设备</div>
        <div class="kpi-value">
          <AnimatedNumber :value="stats.online" />
          <span class="kpi-of"> / {{ stats.deviceTotal }}</span>
        </div>
        <div class="kpi-foot">实时心跳</div>
      </div>
      <div class="kpi kpi-success">
        <div class="kpi-label">浪费率（30 天）</div>
        <div class="kpi-value"><AnimatedNumber :value="stats.wasteRate" suffix="%" /></div>
        <div class="kpi-foot">¥<AnimatedNumber :value="stats.wastedValue" :decimals="2" /></div>
      </div>
    </div>

    <!-- 主体三栏 -->
    <div class="screen-body">
      <!-- 左：趋势线 -->
      <div class="panel panel-large">
        <div class="panel-title">14 天入库 / 出库趋势</div>
        <v-chart :option="trendOption" autoresize class="chart" />
      </div>

      <!-- 中：饼图 + 实时事件 -->
      <div class="screen-mid">
        <div class="panel">
          <div class="panel-title">保鲜状态分布</div>
          <v-chart :option="expiryDistOption" autoresize class="chart" />
        </div>
        <div class="panel panel-feed">
          <div class="panel-title">
            <span class="dot-pulse"></span>
            实时事件
          </div>
          <div class="feed">
            <div v-if="realtimeFeed.length === 0" class="feed-empty">
              等待端侧上报…
            </div>
            <transition-group name="feed-anim" tag="div">
              <div
                v-for="row in realtimeFeed"
                :key="row.id"
                class="feed-row"
                :class="`tone-${row.tone}`"
              >
                <span class="feed-ts">{{ row.ts }}</span>
                <span class="feed-type">{{ row.type }}</span>
                <span class="feed-text">{{ row.text }}</span>
              </div>
            </transition-group>
          </div>
        </div>
      </div>

      <!-- 右：Top 类别 -->
      <div class="panel">
        <div class="panel-title">在库 Top 8 品类</div>
        <v-chart :option="topCategoryOption" autoresize class="chart" />
      </div>
    </div>
  </div>
</template>

<style scoped>
.screen {
  position: fixed;
  inset: 0;
  background:
    radial-gradient(ellipse at top left, rgba(14, 165, 233, 0.12), transparent 50%),
    radial-gradient(ellipse at bottom right, rgba(6, 182, 212, 0.10), transparent 50%),
    #0a1014;
  color: #e2e8f0;
  display: flex;
  flex-direction: column;
  padding: 18px 22px 22px;
  gap: 14px;
  overflow: hidden;
  z-index: 1000;
}

/* 顶栏 */
.screen-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  padding-bottom: 8px;
  border-bottom: 1px solid #1e293b;
}

.screen-title-zone {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.screen-title {
  margin: 0;
  font-size: 26px;
  font-weight: 800;
  background: linear-gradient(90deg, #0ea5e9, #06b6d4);
  -webkit-background-clip: text;
  background-clip: text;
  color: transparent;
  letter-spacing: 1px;
}

.screen-title span {
  color: #64748b;
  font-weight: 500;
  font-size: 16px;
  letter-spacing: 0.5px;
  -webkit-text-fill-color: #64748b;
}

.screen-greet {
  font-size: 12px;
  color: #94a3b8;
}

.screen-clock {
  text-align: right;
}

.clock-time {
  font-size: 38px;
  font-weight: 900;
  font-variant-numeric: tabular-nums;
  color: #0ea5e9;
  letter-spacing: 2px;
  line-height: 1;
}

.clock-date {
  font-size: 12px;
  color: #94a3b8;
  margin-top: 6px;
}

.screen-fs {
  width: 40px;
  height: 40px;
  border-radius: 10px;
  background: rgba(14, 165, 233, 0.12);
  border: 1px solid rgba(14, 165, 233, 0.30);
  color: #0ea5e9;
  cursor: pointer;
  transition: all 0.18s;
  display: flex;
  align-items: center;
  justify-content: center;
}

.screen-fs:hover {
  background: rgba(14, 165, 233, 0.22);
  transform: translateY(-1px);
}

/* KPI */
.kpi-row {
  display: grid;
  grid-template-columns: repeat(5, 1fr);
  gap: 12px;
}

.kpi {
  position: relative;
  padding: 16px 20px;
  border-radius: 12px;
  background: linear-gradient(135deg, rgba(14, 165, 233, 0.06), rgba(0, 0, 0, 0.2));
  border: 1px solid #1e293b;
  overflow: hidden;
}

.kpi::before {
  content: '';
  position: absolute;
  left: 0; top: 0; bottom: 0;
  width: 4px;
}

.kpi-primary::before { background: #0ea5e9; }
.kpi-warn::before    { background: #fa8c16; }
.kpi-danger::before  { background: #f53f3f; }
.kpi-info::before    { background: #06b6d4; }
.kpi-success::before { background: #a855f7; }

.kpi-label {
  font-size: 12px;
  color: #94a3b8;
  margin-bottom: 6px;
}

.kpi-value {
  font-size: 32px;
  font-weight: 800;
  font-variant-numeric: tabular-nums;
  color: #fff;
  letter-spacing: 1px;
}

.kpi-of {
  font-size: 16px;
  color: #475569;
}

.kpi-foot {
  font-size: 11px;
  color: #64748b;
  margin-top: 4px;
}

.kpi-foot strong {
  color: #cbd5e1;
}

/* 主体 */
.screen-body {
  flex: 1;
  display: grid;
  grid-template-columns: 1.2fr 1fr 1fr;
  gap: 14px;
  min-height: 0;
}

.screen-mid {
  display: flex;
  flex-direction: column;
  gap: 14px;
  min-height: 0;
}

.panel {
  display: flex;
  flex-direction: column;
  padding: 14px 16px;
  border-radius: 12px;
  background: linear-gradient(180deg, rgba(15, 23, 42, 0.6), rgba(10, 16, 20, 0.8));
  border: 1px solid #1e293b;
  min-height: 0;
}

.panel-title {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 13px;
  font-weight: 600;
  color: #cbd5e1;
  margin-bottom: 8px;
  padding-left: 8px;
  border-left: 3px solid #0ea5e9;
}

.dot-pulse {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: #f53f3f;
  margin-right: 4px;
  box-shadow: 0 0 0 0 rgba(245, 63, 63, 0.7);
  animation: dot-pulse 1.4s ease-out infinite;
}

@keyframes dot-pulse {
  0%   { box-shadow: 0 0 0 0 rgba(245, 63, 63, 0.7); }
  70%  { box-shadow: 0 0 0 8px rgba(245, 63, 63, 0); }
  100% { box-shadow: 0 0 0 0 rgba(245, 63, 63, 0); }
}

.chart {
  flex: 1;
  width: 100%;
  min-height: 0;
}

.panel-feed {
  flex: 1;
  min-height: 0;
}

.feed {
  flex: 1;
  overflow-y: auto;
  padding-right: 4px;
  font-family: 'SFMono-Regular', Consolas, monospace;
}

.feed-empty {
  text-align: center;
  padding: 30px 0;
  color: #475569;
  font-size: 12px;
}

.feed-row {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 6px 8px;
  border-radius: 6px;
  font-size: 12px;
  margin-bottom: 4px;
  background: rgba(15, 23, 42, 0.6);
  border-left: 2px solid;
}

.feed-row.tone-green   { border-left-color: #0ea5e9; color: #d4f4dd; }
.feed-row.tone-orange  { border-left-color: #fa8c16; color: #ffe7c2; }
.feed-row.tone-red     { border-left-color: #f53f3f; color: #ffcfc7; }

.feed-ts {
  color: #64748b;
  flex-shrink: 0;
}

.feed-type {
  font-weight: 700;
  flex-shrink: 0;
  min-width: 64px;
}

.feed-text {
  flex: 1;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

/* 滚动入场 */
.feed-anim-enter-active {
  transition: all 0.4s ease;
}
.feed-anim-leave-active {
  transition: all 0.3s ease;
}
.feed-anim-enter-from {
  opacity: 0;
  transform: translateX(-20px);
  background: rgba(14, 165, 233, 0.20);
}
.feed-anim-leave-to {
  opacity: 0;
  transform: translateX(20px);
}

@media (max-width: 1300px) {
  .kpi-row { grid-template-columns: repeat(3, 1fr); }
  .screen-body { grid-template-columns: 1fr; }
  .panel-large { min-height: 280px; }
}
</style>
