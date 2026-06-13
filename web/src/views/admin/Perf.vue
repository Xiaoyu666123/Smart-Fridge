<script setup lang="ts">
import { ref, computed, onMounted, onBeforeUnmount } from 'vue'
import { ElMessage } from 'element-plus'
import { use } from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import { BarChart, LineChart, HeatmapChart } from 'echarts/charts'
import { GridComponent, TooltipComponent, LegendComponent, VisualMapComponent } from 'echarts/components'
import VChart from 'vue-echarts'
import { getPerfStats, type PerfStats } from '@/api/admin/perf'
import { useChartTheme } from '@/composables/useChartTheme'
import { toolNameLabels } from '@/utils/toolConfig'

use([CanvasRenderer, BarChart, LineChart, HeatmapChart, GridComponent, TooltipComponent, LegendComponent, VisualMapComponent])

const chartTheme = useChartTheme()

const loading = ref(false)
const data = ref<PerfStats | null>(null)
const hours = ref(24)
let pollTimer: ReturnType<typeof setInterval> | null = null

async function fetchData() {
  loading.value = true
  try {
    data.value = await getPerfStats(hours.value)
  } catch {
    ElMessage.error('加载性能数据失败')
  } finally {
    loading.value = false
  }
}

const trendOption = computed(() => {
  const t = data.value?.trend || []
  return {
    color: ['#0ea5e9'],
    tooltip: { trigger: 'axis', axisPointer: { type: 'line' } },
    grid: { left: 40, right: 16, top: 16, bottom: 30 },
    xAxis: {
      type: 'category',
      boundaryGap: false,
      data: t.map(x => x.label),
      axisLabel: { color: '#86909c', fontSize: 11, interval: Math.max(1, Math.floor(t.length / 12)) },
      axisLine: { lineStyle: { color: '#e5e6eb' } },
    },
    yAxis: {
      type: 'value',
      splitLine: { lineStyle: { color: '#f2f3f5' } },
      axisLabel: { color: '#86909c', fontSize: 12 },
    },
    series: [{
      type: 'line',
      smooth: true,
      data: t.map(x => x.count),
      showSymbol: false,
      areaStyle: {
        color: { type: 'linear', x: 0, y: 0, x2: 0, y2: 1, colorStops: [
          { offset: 0, color: 'rgba(14, 165, 233, 0.3)' },
          { offset: 1, color: 'rgba(14, 165, 233, 0)' },
        ]},
      },
    }],
  }
})

const weekdayLabels = ['周一', '周二', '周三', '周四', '周五', '周六', '周日']
const hourLabels = Array.from({ length: 24 }, (_, i) => `${i.toString().padStart(2, '0')}:00`)

const heatmapOption = computed(() => {
  const arr = data.value?.weekday_hour_heatmap || []
  if (arr.length === 0) return {}
  const max = arr.reduce((m, [, , v]) => Math.max(m, v), 0)
  return {
    tooltip: {
      formatter: (p: any) => {
        const [h, w, v] = p.data
        return `${weekdayLabels[w]} ${hourLabels[h]}<br/>调用 <b>${v}</b> 次`
      },
    },
    grid: { left: 60, right: 24, top: 14, bottom: 36 },
    xAxis: {
      type: 'category',
      data: hourLabels,
      splitArea: { show: true },
      axisLabel: { color: '#86909c', fontSize: 10, interval: 1 },
      axisLine: { lineStyle: { color: '#e5e6eb' } },
      axisTick: { show: false },
    },
    yAxis: {
      type: 'category',
      data: weekdayLabels,
      splitArea: { show: true },
      axisLabel: { color: '#86909c', fontSize: 12 },
      axisLine: { lineStyle: { color: '#e5e6eb' } },
      axisTick: { show: false },
    },
    visualMap: {
      min: 0,
      max: Math.max(max, 1),
      calculable: false,
      orient: 'horizontal',
      left: 'center',
      bottom: 0,
      itemWidth: 14,
      itemHeight: 12,
      textStyle: { fontSize: 11, color: '#86909c' },
      inRange: { color: ['#ebedf0', '#9be9a8', '#40c463', '#30a14e', '#216e39'] },
    },
    series: [{
      type: 'heatmap',
      data: arr,
      label: { show: false },
      itemStyle: { borderRadius: 2 },
    }],
  }
})

function getToolLabel(name: string) {
  return toolNameLabels[name] || name
}

function tagType(rate: number): 'success' | 'warning' | 'danger' {
  if (rate >= 0.99) return 'success'
  if (rate >= 0.9) return 'warning'
  return 'danger'
}

function durationTone(ms: number): string {
  if (ms <= 100) return '#00b42a'
  if (ms <= 500) return '#fa8c16'
  return '#f53f3f'
}

onMounted(() => {
  fetchData()
  pollTimer = setInterval(fetchData, 60_000)
})

onBeforeUnmount(() => {
  if (pollTimer) clearInterval(pollTimer)
})
</script>

<template>
  <div v-loading="loading" class="perf-page">
    <div class="page-header">
      <div class="page-title">
        <el-icon :size="20" color="var(--brand-primary)"><Histogram /></el-icon>
        <span>工具链性能监控</span>
      </div>
      <div class="page-controls">
        <el-radio-group v-model="hours" @change="fetchData" size="small">
          <el-radio-button :value="1">最近 1 小时</el-radio-button>
          <el-radio-button :value="6">6 小时</el-radio-button>
          <el-radio-button :value="24">24 小时</el-radio-button>
          <el-radio-button :value="72">3 天</el-radio-button>
        </el-radio-group>
        <el-button size="small" @click="fetchData"><el-icon><Refresh /></el-icon></el-button>
      </div>
    </div>

    <!-- KPI -->
    <div v-if="data" class="kpi-row">
      <div class="kpi-card">
        <div class="kpi-icon" style="background: var(--brand-primary-light); color: var(--brand-primary-dark)">
          <el-icon :size="22"><DataLine /></el-icon>
        </div>
        <div>
          <div class="kpi-value">{{ data.total_steps }}</div>
          <div class="kpi-label">工具调用次数</div>
        </div>
      </div>
      <div class="kpi-card">
        <div class="kpi-icon" style="background: #ecfeff; color: #06b6d4">
          <el-icon :size="22"><Connection /></el-icon>
        </div>
        <div>
          <div class="kpi-value">{{ data.tools.length }}</div>
          <div class="kpi-label">参与工具数</div>
        </div>
      </div>
      <div class="kpi-card">
        <div class="kpi-icon" style="background: #e8f7e8; color: #00b42a">
          <el-icon :size="22"><CircleCheck /></el-icon>
        </div>
        <div>
          <div class="kpi-value">
            {{ data.tools.length > 0
              ? Math.round(data.tools.reduce((s, t) => s + t.success_count, 0) / data.total_steps * 100)
              : 0 }}%
          </div>
          <div class="kpi-label">整体成功率</div>
        </div>
      </div>
      <div class="kpi-card">
        <div class="kpi-icon" style="background: #fff7e6; color: #fa8c16">
          <el-icon :size="22"><Stopwatch /></el-icon>
        </div>
        <div>
          <div class="kpi-value">
            {{ data.tools.length > 0
              ? Math.round(data.tools.reduce((s, t) => s + t.avg_ms * t.count, 0) / Math.max(1, data.total_steps))
              : 0 }} ms
          </div>
          <div class="kpi-label">平均耗时</div>
        </div>
      </div>
    </div>

    <!-- 趋势 -->
    <el-card v-if="data" shadow="never" class="trend-card">
      <template #header>
        <span class="card-title">每小时调用量趋势</span>
      </template>
      <v-chart :theme="chartTheme" :option="trendOption" autoresize class="trend-chart" />
    </el-card>

    <!-- 周-小时热图 -->
    <el-card v-if="data" shadow="never">
      <template #header>
        <span class="card-title">周-小时调用热图（{{ data.window_hours >= 168 ? '近一周' : '近 ' + data.window_hours + ' 小时' }}）</span>
      </template>
      <v-chart :theme="chartTheme" :option="heatmapOption" autoresize class="heatmap-chart" />
    </el-card>

    <!-- 工具明细表 -->
    <el-card v-if="data" shadow="never">
      <template #header>
        <span class="card-title">工具性能明细（按调用量降序）</span>
      </template>
      <el-table :data="data.tools" stripe>
        <el-table-column label="工具" min-width="180">
          <template #default="{ row }">
            <div style="display: flex; align-items: center; gap: 8px">
              <span style="font-weight: 600">{{ getToolLabel(row.tool_name) }}</span>
              <code class="mono">{{ row.tool_name }}</code>
            </div>
          </template>
        </el-table-column>
        <el-table-column label="调用次数" prop="count" width="110" align="right" />
        <el-table-column label="成功率" width="160">
          <template #default="{ row }">
            <el-tag size="small" round :type="tagType(row.success_rate)" effect="light">
              {{ (row.success_rate * 100).toFixed(1) }}%
            </el-tag>
            <span v-if="row.fail_count > 0" style="margin-left: 8px; color: #f53f3f; font-size: 12px">
              失败 {{ row.fail_count }}
            </span>
          </template>
        </el-table-column>
        <el-table-column label="平均耗时" width="120" align="right">
          <template #default="{ row }">
            <span :style="{ color: durationTone(row.avg_ms), fontWeight: 600 }">{{ row.avg_ms }} ms</span>
          </template>
        </el-table-column>
        <el-table-column label="P50" prop="p50_ms" width="100" align="right">
          <template #default="{ row }">{{ row.p50_ms }} ms</template>
        </el-table-column>
        <el-table-column label="P95" prop="p95_ms" width="100" align="right">
          <template #default="{ row }">
            <span :style="{ color: durationTone(row.p95_ms), fontWeight: 600 }">{{ row.p95_ms }} ms</span>
          </template>
        </el-table-column>
        <el-table-column label="最大" prop="max_ms" width="100" align="right">
          <template #default="{ row }">{{ row.max_ms }} ms</template>
        </el-table-column>
      </el-table>
    </el-card>
  </div>
</template>

<style scoped>
.perf-page {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  flex-wrap: wrap;
  gap: 12px;
}

.page-title {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 18px;
  font-weight: 600;
  color: var(--text-primary);
}

.page-controls {
  display: flex;
  align-items: center;
  gap: 10px;
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

.card-title {
  font-size: 15px;
  font-weight: 600;
}

.trend-chart {
  width: 100%;
  height: 220px;
}

.heatmap-chart {
  width: 100%;
  height: 240px;
}

.mono {
  font-family: 'SFMono-Regular', Consolas, monospace;
  font-size: 11px;
  color: var(--text-placeholder);
  background: var(--bg-color);
  padding: 1px 6px;
  border-radius: 4px;
}

@media (max-width: 1100px) {
  .kpi-row { grid-template-columns: repeat(2, 1fr); }
}
</style>
