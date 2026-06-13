<script setup lang="ts">
import { ref, computed, onMounted, shallowRef } from 'vue'
import { use } from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import { LineChart, BarChart, PieChart } from 'echarts/charts'
import {
  TitleComponent, TooltipComponent, LegendComponent, GridComponent, DatasetComponent,
} from 'echarts/components'
import VChart from 'vue-echarts'
import { ElMessage } from 'element-plus'
import { useChartTheme } from '@/composables/useChartTheme'
import { exportUsage } from '@/utils/downloadCsv'

const chartTheme = useChartTheme()
import {
  getUsageSummary, getUsageRecords,
  type UsageSummary, type UsageRecord,
} from '@/api/admin/usage'

use([
  CanvasRenderer, LineChart, BarChart, PieChart,
  TitleComponent, TooltipComponent, LegendComponent, GridComponent, DatasetComponent,
])

const summary = shallowRef<UsageSummary | null>(null)
const records = ref<UsageRecord[]>([])
const summaryLoading = ref(false)
const recordsLoading = ref(false)
const days = ref(30)

const filterProvider = ref('')
const filterStatus = ref('')
const recordPage = ref(1)
const recordPageSize = 10

async function fetchSummary() {
  summaryLoading.value = true
  try {
    summary.value = await getUsageSummary(days.value)
  } catch {
    ElMessage.error('查询用量统计失败')
  } finally {
    summaryLoading.value = false
  }
}

async function fetchRecords() {
  recordsLoading.value = true
  try {
    const params: Record<string, any> = { limit: 100 }
    if (filterProvider.value) params.provider = filterProvider.value
    if (filterStatus.value) params.status = filterStatus.value
    records.value = await getUsageRecords(params)
    recordPage.value = 1
  } catch {
    ElMessage.error('查询用量明细失败')
  } finally {
    recordsLoading.value = false
  }
}

const fmtCost = (v: number) => '$' + (v || 0).toFixed(4)
const fmtTokens = (v: number) => (v || 0).toLocaleString()

const dailyOption = computed(() => {
  const d = summary.value?.daily || []
  return {
    color: ['#10b981', '#f59e0b'],
    tooltip: { trigger: 'axis' },
    legend: { data: ['Tokens', '调用次数'], top: 0, right: 10 },
    grid: { left: 50, right: 60, top: 30, bottom: 30 },
    xAxis: {
      type: 'category',
      data: d.map(x => x.date),
      axisLabel: { color: '#94a3b8', fontSize: 11 },
      axisLine: { lineStyle: { color: '#e3eee8' } },
    },
    yAxis: [
      {
        type: 'value', name: 'Tokens', position: 'left',
        axisLabel: { color: '#94a3b8' },
        splitLine: { lineStyle: { color: '#eef7f2' } },
      },
      {
        type: 'value', name: '次数', position: 'right',
        axisLabel: { color: '#94a3b8' },
        splitLine: { show: false },
      },
    ],
    series: [
      {
        name: 'Tokens', type: 'line', smooth: true,
        showSymbol: false,
        data: d.map(x => x.tokens),
        areaStyle: {
          color: { type: 'linear', x: 0, y: 0, x2: 0, y2: 1, colorStops: [
            { offset: 0, color: 'rgba(14, 165, 233,0.3)' },
            { offset: 1, color: 'rgba(14, 165, 233,0)' }
          ]}
        },
      },
      {
        name: '调用次数', type: 'bar', yAxisIndex: 1,
        barMaxWidth: 16,
        data: d.map(x => x.calls),
        itemStyle: { color: '#f59e0b', borderRadius: [4, 4, 0, 0] },
      },
    ],
  }
})

const providerPieOption = computed(() => {
  const list = summary.value?.by_provider || []
  return {
    tooltip: { trigger: 'item', formatter: '{b}: {c} ({d}%)' },
    legend: { orient: 'vertical', right: 10, top: 'center' },
    series: [{
      type: 'pie',
      radius: ['52%', '78%'],
      center: ['38%', '50%'],
      itemStyle: { borderRadius: 6, borderColor: '#fff', borderWidth: 2 },
      label: { show: false },
      data: list.map(x => ({ name: x.provider, value: x.tokens })),
    }],
  }
})

const endpointBarOption = computed(() => {
  const list = (summary.value?.by_endpoint || []).slice().reverse()
  return {
    tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' } },
    grid: { left: 110, right: 30, top: 16, bottom: 28 },
    xAxis: { type: 'value', axisLabel: { color: '#94a3b8' } },
    yAxis: {
      type: 'category',
      data: list.map(x => x.endpoint),
      axisLabel: { color: '#475569', fontSize: 12 },
    },
    series: [{
      type: 'bar',
      data: list.map(x => x.tokens),
      barMaxWidth: 16,
      itemStyle: {
        color: { type: 'linear', x: 0, y: 0, x2: 1, y2: 0, colorStops: [
          { offset: 0, color: '#10b981' }, { offset: 1, color: '#34d399' }
        ]},
        borderRadius: [0, 4, 4, 0],
      },
      label: { show: true, position: 'right', color: '#475569', fontSize: 11,
               formatter: (p: any) => (p.value || 0).toLocaleString() },
    }],
  }
})

const failureRate = computed(() => {
  const s = summary.value
  if (!s || s.total_calls === 0) return 0
  return Math.round((s.failed_calls / s.total_calls) * 1000) / 10
})

const pagedRecords = computed(() => {
  const start = (recordPage.value - 1) * recordPageSize
  return records.value.slice(start, start + recordPageSize)
})

function statusType(s: string) {
  return s === 'SUCCESS' ? 'success' : 'danger'
}

function providerColor(p: string) {
  if (p === 'llm') return '#10b981'
  if (p === 'vision') return '#f59e0b'
  if (p === 'embedding') return '#06b6d4'
  return '#64748b'
}

function fmtDate(s: string | null) {
  if (!s) return '-'
  return new Date(s).toLocaleString('zh-CN')
}

function fmtDuration(ms: number | null) {
  if (ms === null || ms === undefined) return '-'
  if (ms < 1000) return `${ms}ms`
  return `${(ms / 1000).toFixed(1)}s`
}

onMounted(async () => {
  await fetchSummary()
  await fetchRecords()
})
</script>

<template>
  <div class="usage-page">
    <!-- 时间范围 -->
    <el-card shadow="never" style="margin-bottom: 16px">
      <el-form :inline="true">
        <el-form-item label="统计范围">
          <el-select v-model="days" @change="fetchSummary" style="width: 130px">
            <el-option label="近 7 天" :value="7" />
            <el-option label="近 30 天" :value="30" />
            <el-option label="近 90 天" :value="90" />
          </el-select>
        </el-form-item>
        <el-form-item>
          <el-button type="primary" @click="fetchSummary">刷新统计</el-button>
        </el-form-item>
        <el-form-item>
          <el-button @click="exportUsage">
            <el-icon><Download /></el-icon> 导出 CSV
          </el-button>
        </el-form-item>
      </el-form>
    </el-card>

    <!-- 顶部 KPI -->
    <div v-loading="summaryLoading" class="kpi-row">
      <div class="kpi-card">
        <div class="kpi-icon" style="background: var(--brand-primary-light); color: var(--brand-primary-dark)">
          <el-icon :size="22"><Money /></el-icon>
        </div>
        <div>
          <div class="kpi-value">{{ fmtCost(summary?.total_cost_usd ?? 0) }}</div>
          <div class="kpi-label">总费用（USD）</div>
        </div>
      </div>
      <div class="kpi-card">
        <div class="kpi-icon" style="background: #ecfeff; color: #06b6d4">
          <el-icon :size="22"><Histogram /></el-icon>
        </div>
        <div>
          <div class="kpi-value">{{ fmtTokens(summary?.total_tokens ?? 0) }}</div>
          <div class="kpi-label">总 Tokens</div>
        </div>
      </div>
      <div class="kpi-card">
        <div class="kpi-icon" style="background: #fff7ed; color: #f59e0b">
          <el-icon :size="22"><DataAnalysis /></el-icon>
        </div>
        <div>
          <div class="kpi-value">{{ summary?.total_calls ?? 0 }}</div>
          <div class="kpi-label">调用次数</div>
        </div>
      </div>
      <div class="kpi-card">
        <div class="kpi-icon" :style="{ background: '#fef2f2', color: '#ef4444' }">
          <el-icon :size="22"><Warning /></el-icon>
        </div>
        <div>
          <div class="kpi-value">{{ failureRate }}%</div>
          <div class="kpi-label">失败率（{{ summary?.failed_calls ?? 0 }} 次）</div>
        </div>
      </div>
    </div>

    <!-- 图表行 -->
    <div class="chart-row">
      <el-card shadow="never" class="chart-card chart-card-wide">
        <template #header>
          <span class="card-title">每日 Token 消耗趋势</span>
        </template>
        <v-chart v-if="summary?.daily?.length" :theme="chartTheme" :option="dailyOption" autoresize class="chart" />
        <el-empty v-else description="暂无数据" />
      </el-card>
      <el-card shadow="never" class="chart-card">
        <template #header>
          <span class="card-title">按服务分布</span>
        </template>
        <v-chart v-if="summary?.by_provider?.length" :theme="chartTheme" :option="providerPieOption" autoresize class="chart" />
        <el-empty v-else description="暂无数据" />
      </el-card>
    </div>

    <el-card shadow="never" style="margin-bottom: 16px">
      <template #header>
        <span class="card-title">Top 10 调用入口</span>
      </template>
      <v-chart v-if="summary?.by_endpoint?.length" :theme="chartTheme" :option="endpointBarOption" autoresize style="height: 360px" />
      <el-empty v-else description="暂无数据" />
    </el-card>

    <!-- 明细 -->
    <el-card shadow="never">
      <template #header>
        <div style="display: flex; justify-content: space-between; align-items: center">
          <span class="card-title">调用明细</span>
          <div style="display: flex; gap: 8px">
            <el-select v-model="filterProvider" placeholder="服务" clearable size="small" style="width: 130px">
              <el-option label="LLM" value="llm" />
              <el-option label="Vision" value="vision" />
              <el-option label="Embedding" value="embedding" />
            </el-select>
            <el-select v-model="filterStatus" placeholder="状态" clearable size="small" style="width: 110px">
              <el-option label="SUCCESS" value="SUCCESS" />
              <el-option label="FAILED" value="FAILED" />
            </el-select>
            <el-button type="primary" size="small" @click="fetchRecords">查询</el-button>
          </div>
        </div>
      </template>

      <el-table :data="pagedRecords" v-loading="recordsLoading" stripe>
        <el-table-column label="时间" width="170">
          <template #default="{ row }">{{ fmtDate(row.created_at) }}</template>
        </el-table-column>
        <el-table-column label="服务" width="100">
          <template #default="{ row }">
            <el-tag size="small" round
              :style="{ background: providerColor(row.provider) + '22', color: providerColor(row.provider), border: 'none' }">
              {{ row.provider }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="模型" prop="model" min-width="160" />
        <el-table-column label="入口" prop="endpoint" width="140">
          <template #default="{ row }">
            <span v-if="row.endpoint">{{ row.endpoint }}</span>
            <span v-else style="color: var(--text-placeholder)">-</span>
          </template>
        </el-table-column>
        <el-table-column label="prompt" width="100" align="right">
          <template #default="{ row }">{{ fmtTokens(row.prompt_tokens) }}</template>
        </el-table-column>
        <el-table-column label="completion" width="110" align="right">
          <template #default="{ row }">{{ fmtTokens(row.completion_tokens) }}</template>
        </el-table-column>
        <el-table-column label="费用" width="100" align="right">
          <template #default="{ row }">
            <strong style="color: var(--brand-primary-dark)">{{ fmtCost(row.cost_usd) }}</strong>
          </template>
        </el-table-column>
        <el-table-column label="耗时" width="80" align="right">
          <template #default="{ row }">{{ fmtDuration(row.duration_ms) }}</template>
        </el-table-column>
        <el-table-column label="状态" width="90">
          <template #default="{ row }">
            <el-tag :type="statusType(row.status) as any" size="small" round>{{ row.status }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="用户" width="120">
          <template #default="{ row }">
            <code v-if="row.user_id" style="font-size: 11px">{{ row.user_id.slice(0, 8) }}</code>
            <span v-else style="color: var(--text-placeholder)">-</span>
          </template>
        </el-table-column>
      </el-table>

      <div class="records-pagination">
        <span class="records-total">共 {{ records.length }} 条，每页 10 条</span>
        <el-pagination
          v-model:current-page="recordPage"
          background
          layout="prev, pager, next"
          :page-size="recordPageSize"
          :total="records.length"
          :hide-on-single-page="records.length <= recordPageSize"
        />
      </div>
    </el-card>
  </div>
</template>

<style scoped>
.usage-page {
  display: flex;
  flex-direction: column;
}

.kpi-row {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 16px;
  margin-bottom: 16px;
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

.chart-row {
  display: grid;
  grid-template-columns: 2fr 1fr;
  gap: 16px;
  margin-bottom: 16px;
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

.records-pagination {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: 16px;
  padding-top: 14px;
}

.records-total {
  color: var(--text-secondary);
  font-size: 13px;
}

@media (max-width: 1100px) {
  .kpi-row {
    grid-template-columns: repeat(2, 1fr);
  }
  .chart-row {
    grid-template-columns: 1fr;
  }
}
</style>
