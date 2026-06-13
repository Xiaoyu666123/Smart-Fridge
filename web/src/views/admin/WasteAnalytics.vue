<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { use } from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import { PieChart as EPieChart, BarChart, HeatmapChart } from 'echarts/charts'
import {
  TitleComponent, TooltipComponent, LegendComponent, GridComponent,
  VisualMapComponent, CalendarComponent,
} from 'echarts/components'
import VChart from 'vue-echarts'
import { ElMessage } from 'element-plus'
import { getWasteAnalytics, getWasteCalendar, type WasteAnalytics, type WasteCalendar } from '@/api/admin/stats'
import { useChartTheme } from '@/composables/useChartTheme'
import AnimatedNumber from '@/components/AnimatedNumber.vue'

use([CanvasRenderer, EPieChart, BarChart, HeatmapChart, TitleComponent, TooltipComponent, LegendComponent, GridComponent, VisualMapComponent, CalendarComponent])

const chartTheme = useChartTheme()

const loading = ref(false)
const data = ref<WasteAnalytics | null>(null)
const days = ref(30)
const calendar = ref<WasteCalendar | null>(null)
const calendarYear = ref(365)

async function fetchData() {
  loading.value = true
  try {
    data.value = await getWasteAnalytics(days.value)
  } catch {
    ElMessage.error('获取分析数据失败')
  } finally {
    loading.value = false
  }
}

async function fetchCalendar() {
  try {
    calendar.value = await getWasteCalendar(calendarYear.value)
  } catch {
    // 静默
  }
}

const calendarOption = computed(() => {
  const c = calendar.value
  if (!c) return {}
  return {
    tooltip: {
      formatter: (params: any) => {
        const [d, v, n] = params.data
        if (!v) return `${d}<br/>无浪费`
        return `${d}<br/>浪费 <b>¥${v.toFixed(2)}</b>（${n} 件）`
      },
    },
    visualMap: {
      min: 0,
      max: Math.max(c.max_value || 1, 5),
      calculable: false,
      orient: 'horizontal',
      left: 'center',
      bottom: 0,
      itemWidth: 14,
      itemHeight: 12,
      textStyle: { fontSize: 11, color: '#86909c' },
      inRange: {
        color: ['#ebedf0', '#9be9a8', '#40c463', '#30a14e', '#216e39'].reverse().concat(['#ffece8', '#ffbfb3', '#fa8c16', '#f53f3f']).slice(5),
      },
    },
    calendar: {
      top: 30,
      left: 50,
      right: 30,
      bottom: 36,
      cellSize: ['auto', 16],
      range: [c.start, c.end],
      itemStyle: {
        borderColor: 'var(--bg-card)',
        borderWidth: 2,
        color: '#f2f3f5',
      },
      yearLabel: { show: false },
      monthLabel: { color: '#86909c', fontSize: 11 },
      dayLabel: { color: '#86909c', fontSize: 10, firstDay: 1 },
      splitLine: { show: false },
    },
    series: [{
      type: 'heatmap',
      coordinateSystem: 'calendar',
      data: c.series,
    }],
  }
})

const wastePct = computed(() => Math.round((data.value?.waste_rate || 0) * 100))

const estimatedTotalCost = computed(() => {
  return (data.value?.restock_suggestions || [])
    .reduce((sum, s) => sum + (s.estimated_cost || 0), 0)
})

function buildShoppingListText(): string {
  const lines: string[] = []
  lines.push(`【智能购物清单】${new Date().toLocaleDateString('zh-CN')}`)
  lines.push('')
  ;(data.value?.restock_suggestions || []).forEach(s => {
    const qty = s.suggested_qty ? ` × ${s.suggested_qty}` : ''
    const cost = s.estimated_cost !== null && s.estimated_cost !== undefined
      ? ` （约 ¥${s.estimated_cost.toFixed(2)}）` : ''
    lines.push(`☐ ${s.category}${qty}${cost}`)
  })
  if (estimatedTotalCost.value > 0) {
    lines.push('')
    lines.push(`预估总价：¥${estimatedTotalCost.value.toFixed(2)}`)
  }
  return lines.join('\n')
}

async function copyShoppingList() {
  const text = buildShoppingListText()
  try {
    await navigator.clipboard.writeText(text)
    ElMessage.success('购物清单已复制到剪贴板')
  } catch {
    ElMessage.warning('复制失败，请手动选择')
  }
}

function exportShoppingList() {
  const text = buildShoppingListText()
  const blob = new Blob([new TextEncoder().encode('\ufeff' + text)],
                        { type: 'text/plain;charset=utf-8' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = `shopping_list_${new Date().toISOString().slice(0,10)}.txt`
  document.body.appendChild(a)
  a.click()
  document.body.removeChild(a)
  URL.revokeObjectURL(url)
  ElMessage.success('已下载购物清单')
}

const distOption = computed(() => {
  const d = data.value
  if (!d) return {}
  return {
    color: ['#00b42a', '#fa8c16', '#f53f3f'],
    tooltip: { trigger: 'item', formatter: '{b}: {c} ({d}%)' },
    legend: { bottom: 0, textStyle: { fontSize: 12 } },
    series: [{
      type: 'pie',
      radius: ['55%', '78%'],
      avoidLabelOverlap: true,
      itemStyle: { borderRadius: 6, borderColor: '#fff', borderWidth: 2 },
      label: { show: false },
      labelLine: { show: false },
      data: [
        { name: '已消耗', value: d.consumed_in_time },
        { name: '在库', value: d.in_stock },
        { name: '浪费', value: d.wasted },
      ],
    }],
  }
})

const wasteBarOption = computed(() => {
  const d = data.value
  if (!d || d.top_wasted.length === 0) return {}
  return {
    color: ['#f53f3f'],
    tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' } },
    grid: { left: 100, right: 24, top: 16, bottom: 24 },
    xAxis: { type: 'value', axisLabel: { color: '#86909c', fontSize: 12 } },
    yAxis: {
      type: 'category',
      data: d.top_wasted.map(t => t.category).reverse(),
      axisLine: { lineStyle: { color: '#e5e6eb' } },
      axisLabel: { color: '#86909c', fontSize: 12 },
    },
    series: [{
      type: 'bar',
      barMaxWidth: 22,
      data: d.top_wasted.map(t => t.count).reverse(),
      itemStyle: { color: '#f53f3f', borderRadius: [0, 6, 6, 0] },
      label: { show: true, position: 'right', color: '#1d2129' },
    }],
  }
})

const consumedBarOption = computed(() => {
  const d = data.value
  if (!d || d.top_consumed.length === 0) return {}
  return {
    color: ['#00b42a'],
    tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' } },
    grid: { left: 100, right: 24, top: 16, bottom: 24 },
    xAxis: { type: 'value', axisLabel: { color: '#86909c', fontSize: 12 } },
    yAxis: {
      type: 'category',
      data: d.top_consumed.map(t => t.category).reverse(),
      axisLine: { lineStyle: { color: '#e5e6eb' } },
      axisLabel: { color: '#86909c', fontSize: 12 },
    },
    series: [{
      type: 'bar',
      barMaxWidth: 22,
      data: d.top_consumed.map(t => t.count).reverse(),
      itemStyle: { color: '#00b42a', borderRadius: [0, 6, 6, 0] },
      label: { show: true, position: 'right', color: '#1d2129' },
    }],
  }
})

onMounted(() => {
  fetchData()
  fetchCalendar()
})
</script>

<template>
  <div v-loading="loading" class="waste-page">
    <!-- 顶部筛选 -->
    <div class="page-header">
      <div class="page-title">
        <el-icon :size="22" color="var(--brand-primary)"><PieChart /></el-icon>
        <span>浪费分析与购物建议</span>
      </div>
      <div class="page-controls">
        <el-radio-group v-model="days" @change="fetchData" size="small">
          <el-radio-button :value="7">最近 7 天</el-radio-button>
          <el-radio-button :value="30">最近 30 天</el-radio-button>
          <el-radio-button :value="90">最近 90 天</el-radio-button>
        </el-radio-group>
        <el-button size="small" @click="fetchData"><el-icon><Refresh /></el-icon></el-button>
      </div>
    </div>

    <!-- 顶部 KPI -->
    <div v-if="data" class="kpi-row">
      <div class="kpi-card kpi-primary">
        <div class="kpi-icon" style="background: rgba(14, 165, 233, 0.18); color: var(--brand-primary-dark)">
          <el-icon :size="22"><Box /></el-icon>
        </div>
        <div>
          <div class="kpi-value"><AnimatedNumber :value="data.total" /></div>
          <div class="kpi-label">总入库</div>
        </div>
      </div>
      <div class="kpi-card">
        <div class="kpi-icon" style="background: #e8f7e8; color: #00b42a">
          <el-icon :size="22"><CircleCheck /></el-icon>
        </div>
        <div>
          <div class="kpi-value"><AnimatedNumber :value="data.consumed_in_time" /></div>
          <div class="kpi-label">已消耗</div>
        </div>
      </div>
      <div class="kpi-card">
        <div class="kpi-icon" style="background: #fff7e6; color: #fa8c16">
          <el-icon :size="22"><Goods /></el-icon>
        </div>
        <div>
          <div class="kpi-value"><AnimatedNumber :value="data.in_stock" /></div>
          <div class="kpi-label">仍在库</div>
        </div>
      </div>
      <div class="kpi-card kpi-danger">
        <div class="kpi-icon" style="background: #ffece8; color: #f53f3f">
          <el-icon :size="22"><Warning /></el-icon>
        </div>
        <div>
          <div class="kpi-value"><AnimatedNumber :value="data.wasted" /></div>
          <div class="kpi-label">浪费数量</div>
        </div>
      </div>
      <div class="kpi-card kpi-rate">
        <div class="kpi-icon" :class="{ ok: wastePct < 10, warn: wastePct >= 10 && wastePct < 25, bad: wastePct >= 25 }">
          <el-icon :size="22"><TrendCharts /></el-icon>
        </div>
        <div>
          <div class="kpi-value"><AnimatedNumber :value="wastePct" suffix="%" /></div>
          <div class="kpi-label">浪费率</div>
        </div>
      </div>
    </div>

    <!-- 浪费金额估算 -->
    <div v-if="data" class="cost-row">
      <div class="cost-card cost-wasted">
        <div class="cost-card-icon">💸</div>
        <div class="cost-card-body">
          <div class="cost-card-label">{{ data.window_days }} 天浪费金额</div>
          <div class="cost-card-value">¥<AnimatedNumber :value="data.wasted_value" :decimals="2" /></div>
          <div class="cost-card-sub">{{ data.wasted }} 件 · 平均每件 ¥{{ data.wasted ? (data.wasted_value / data.wasted).toFixed(2) : '0.00' }}</div>
        </div>
      </div>
      <div class="cost-card cost-saved">
        <div class="cost-card-icon">✅</div>
        <div class="cost-card-body">
          <div class="cost-card-label">{{ data.window_days }} 天有效消耗金额</div>
          <div class="cost-card-value">¥<AnimatedNumber :value="data.consumed_value" :decimals="2" /></div>
          <div class="cost-card-sub">{{ data.consumed_in_time }} 件 · 按时消耗</div>
        </div>
      </div>
      <div class="cost-card cost-coverage" v-if="data.total_categories_seen > 0">
        <div class="cost-card-icon">📋</div>
        <div class="cost-card-body">
          <div class="cost-card-label">单价配置覆盖率</div>
          <div class="cost-card-value">
            {{ data.priced_categories }} <span class="cost-card-of">/ {{ data.total_categories_seen }}</span>
          </div>
          <div class="cost-card-sub">
            <el-button link type="primary" size="small" @click="$router.push('/admin/agent')">
              去配置 →
            </el-button>
          </div>
        </div>
      </div>
    </div>

    <!-- 图表 -->
    <div v-if="data" class="chart-row">
      <el-card shadow="never" class="chart-card">
        <template #header><span class="card-title">食材去向分布</span></template>
        <v-chart v-if="data.total > 0" :theme="chartTheme" :option="distOption" autoresize class="chart" />
        <el-empty v-else description="窗口内暂无入库" />
      </el-card>

      <el-card shadow="never" class="chart-card">
        <template #header><span class="card-title">最容易浪费的品类</span></template>
        <v-chart v-if="data.top_wasted.length > 0" :theme="chartTheme" :option="wasteBarOption" autoresize class="chart" />
        <div v-else class="empty-good">
          <el-icon :size="36" color="#00b42a"><CircleCheckFilled /></el-icon>
          <p>窗口内未发现浪费 🎉</p>
        </div>
      </el-card>

      <el-card shadow="never" class="chart-card">
        <template #header><span class="card-title">消耗最多的品类</span></template>
        <v-chart v-if="data.top_consumed.length > 0" :theme="chartTheme" :option="consumedBarOption" autoresize class="chart" />
        <el-empty v-else description="窗口内暂无消耗" />
      </el-card>
    </div>

    <!-- 补货建议 -->
    <el-card v-if="data" shadow="never" class="suggest-card">
      <template #header>
        <div class="card-title-row">
          <span class="card-title">
            <el-icon :size="16" color="#fa8c16"><ShoppingCart /></el-icon>
            智能购物建议
          </span>
          <div style="display: flex; align-items: center; gap: 8px">
            <el-tag size="small" round type="warning">{{ data.restock_suggestions.length }} 项</el-tag>
            <el-button
              v-if="data.restock_suggestions.length > 0"
              size="small"
              type="primary"
              @click="copyShoppingList"
            >
              <el-icon><CopyDocument /></el-icon>
              复制清单
            </el-button>
            <el-button
              v-if="data.restock_suggestions.length > 0"
              size="small"
              @click="exportShoppingList"
            >
              <el-icon><Download /></el-icon>
              导出 TXT
            </el-button>
          </div>
        </div>
      </template>
      <div v-if="data.restock_suggestions.length === 0" class="empty-good">
        <el-icon :size="36" color="#00b42a"><CircleCheckFilled /></el-icon>
        <p>当前库存与消耗节奏匹配，暂无补货建议</p>
      </div>
      <div v-else>
        <!-- 估算总价 -->
        <div v-if="estimatedTotalCost > 0" class="shopping-total">
          <span>预估购物总价：</span>
          <strong>¥{{ estimatedTotalCost.toFixed(2) }}</strong>
          <span class="shopping-total-tip">（基于已配置单价的品类）</span>
        </div>
        <div class="suggest-grid">
          <div
            v-for="s in data.restock_suggestions"
            :key="s.category"
            class="suggest-item"
          >
            <div class="suggest-emoji">🛒</div>
            <div class="suggest-body">
              <div class="suggest-name">
                {{ s.category }}
                <span v-if="s.suggested_qty" class="suggest-qty">× {{ s.suggested_qty }}</span>
              </div>
              <div class="suggest-meta">
                近期消耗 <strong>{{ s.consumed_count }}</strong> 次 ·
                当前在库 <strong :class="{ low: s.current_stock === 0 }">{{ s.current_stock }}</strong> 件
              </div>
              <div class="suggest-reason">
                {{ s.reason }}
                <span v-if="s.estimated_cost !== null && s.estimated_cost !== undefined" class="suggest-cost">
                  · 预估 ¥{{ s.estimated_cost.toFixed(2) }}
                </span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </el-card>

    <!-- 浪费日历热图（365 天）-->
    <el-card v-if="calendar" shadow="never" class="calendar-card">
      <template #header>
        <div class="card-title-row">
          <span class="card-title">
            <el-icon :size="14" color="#f53f3f"><Calendar /></el-icon>
            浪费金额年度日历
          </span>
          <div class="cal-legend">
            <span>近 365 天，每格 = 一天</span>
            <el-radio-group v-model="calendarYear" size="small" @change="fetchCalendar">
              <el-radio-button :value="180">半年</el-radio-button>
              <el-radio-button :value="365">一年</el-radio-button>
            </el-radio-group>
          </div>
        </div>
      </template>
      <div class="cal-stats">
        <div class="cal-stat">
          <div class="cal-stat-num">¥{{ calendar.total_value.toFixed(2) }}</div>
          <div class="cal-stat-label">{{ calendar.window_days }} 天累计浪费</div>
        </div>
        <div class="cal-stat">
          <div class="cal-stat-num">{{ calendar.total_count }}</div>
          <div class="cal-stat-label">浪费件数</div>
        </div>
        <div class="cal-stat">
          <div class="cal-stat-num">{{ calendar.days_with_waste }}</div>
          <div class="cal-stat-label">有浪费的天数</div>
        </div>
        <div class="cal-stat">
          <div class="cal-stat-num">¥{{ calendar.max_value.toFixed(2) }}</div>
          <div class="cal-stat-label">单日最高</div>
        </div>
      </div>
      <v-chart
        v-if="calendar.series.length > 0"
        :theme="chartTheme"
        :option="calendarOption"
        autoresize
        class="cal-chart"
      />
      <div v-else class="cal-empty">
        <el-icon :size="36" color="#00b42a"><CircleCheckFilled /></el-icon>
        <p>窗口内未发现浪费 🎉</p>
      </div>
    </el-card>
  </div>
</template>

<style scoped>
.waste-page {
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
  grid-template-columns: repeat(5, 1fr);
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

/* 浪费金额卡片 */
.cost-row {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 16px;
}

.cost-card {
  display: flex;
  align-items: center;
  gap: 14px;
  padding: 18px 22px;
  border-radius: var(--radius-md);
  border: 1px solid var(--border-color);
  background: var(--bg-card);
  box-shadow: var(--shadow-sm);
}

.cost-card.cost-wasted {
  border-left: 4px solid #f53f3f;
  background: linear-gradient(90deg, rgba(245, 63, 63, 0.04), var(--bg-card));
}

.cost-card.cost-saved {
  border-left: 4px solid #00b42a;
  background: linear-gradient(90deg, rgba(0, 180, 42, 0.04), var(--bg-card));
}

.cost-card.cost-coverage {
  border-left: 4px solid var(--brand-primary);
  background: linear-gradient(90deg, rgba(14, 165, 233, 0.04), var(--bg-card));
}

.cost-card-icon {
  font-size: 30px;
  line-height: 1;
}

.cost-card-body {
  flex: 1;
  min-width: 0;
}

.cost-card-label {
  font-size: 12px;
  color: var(--text-secondary);
}

.cost-card-value {
  font-size: 26px;
  font-weight: 700;
  color: var(--text-primary);
  line-height: 1.2;
  margin-top: 2px;
  font-variant-numeric: tabular-nums;
}

.cost-card-of {
  font-size: 14px;
  color: var(--text-placeholder);
  font-weight: 500;
}

.cost-card-sub {
  font-size: 12px;
  color: var(--text-secondary);
  margin-top: 4px;
}

.shopping-total {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 10px 14px;
  background: var(--brand-primary-soft);
  border: 1px dashed var(--brand-primary);
  border-radius: 10px;
  margin-bottom: 14px;
  font-size: 14px;
  color: var(--text-primary);
}

.shopping-total strong {
  color: var(--brand-primary-dark);
  font-size: 16px;
  font-weight: 700;
}

.shopping-total-tip {
  margin-left: auto;
  font-size: 11px;
  color: var(--text-placeholder);
}

.suggest-qty {
  margin-left: 6px;
  font-size: 12px;
  font-weight: 600;
  color: #fa8c16;
}

.suggest-cost {
  font-weight: 600;
  color: var(--brand-primary-dark);
}

/* 日历热图 */
.calendar-card {
}

.cal-legend {
  display: inline-flex;
  align-items: center;
  gap: 12px;
  font-size: 12px;
  color: var(--text-placeholder);
}

.cal-stats {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 12px;
  margin-bottom: 14px;
}

.cal-stat {
  padding: 10px 14px;
  background: var(--bg-soft);
  border-radius: 10px;
  border-left: 3px solid #f53f3f;
}

.cal-stat:nth-child(2) { border-left-color: #fa8c16; }
.cal-stat:nth-child(3) { border-left-color: var(--brand-primary); }
.cal-stat:nth-child(4) { border-left-color: #722ed1; }

.cal-stat-num {
  font-size: 18px;
  font-weight: 700;
  color: var(--text-primary);
  font-variant-numeric: tabular-nums;
  line-height: 1.2;
}

.cal-stat-label {
  font-size: 11px;
  color: var(--text-secondary);
  margin-top: 2px;
}

.cal-chart {
  width: 100%;
  height: 220px;
}

.cal-empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 8px;
  padding: 30px 0;
  font-size: 14px;
  color: var(--text-secondary);
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

.kpi-icon.ok   { background: #e8f7e8; color: #00b42a; }
.kpi-icon.warn { background: #fff7e6; color: #fa8c16; }
.kpi-icon.bad  { background: #ffece8; color: #f53f3f; }

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
  grid-template-columns: 1fr 1fr 1fr;
  gap: 16px;
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

.card-title-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.card-title {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  font-size: 15px;
  font-weight: 600;
}

.chart {
  flex: 1;
  width: 100%;
  min-height: 280px;
}

.empty-good {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 10px;
  height: 100%;
  min-height: 200px;
  color: var(--text-secondary);
  font-size: 14px;
}

.suggest-card {
  /* spacing only */
}

.suggest-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(260px, 1fr));
  gap: 12px;
}

.suggest-item {
  display: flex;
  align-items: flex-start;
  gap: 12px;
  padding: 14px 16px;
  border: 1px solid var(--border-color);
  border-radius: 12px;
  background: var(--bg-card);
  transition: all 0.18s;
}

.suggest-item:hover {
  border-color: #fa8c16;
  box-shadow: 0 6px 16px rgba(250, 140, 22, 0.12);
  transform: translateY(-1px);
}

.suggest-emoji {
  font-size: 24px;
  line-height: 1;
}

.suggest-body {
  flex: 1;
  min-width: 0;
}

.suggest-name {
  font-size: 15px;
  font-weight: 600;
  color: var(--text-primary);
}

.suggest-meta {
  font-size: 12px;
  color: var(--text-secondary);
  margin-top: 4px;
}

.suggest-meta strong {
  color: var(--text-primary);
  font-weight: 700;
}

.suggest-meta strong.low {
  color: #f53f3f;
}

.suggest-reason {
  font-size: 12px;
  color: #fa8c16;
  margin-top: 4px;
}

@media (max-width: 1200px) {
  .kpi-row { grid-template-columns: repeat(3, 1fr); }
  .cost-row { grid-template-columns: 1fr; }
  .chart-row { grid-template-columns: 1fr; }
}
</style>
