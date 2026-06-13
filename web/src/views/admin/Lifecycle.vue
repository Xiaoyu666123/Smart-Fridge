<script setup lang="ts">
/**
 * 食材生命周期 Sankey：来源 → 品类 → 终态。
 */
import { ref, computed, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { use } from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import { SankeyChart } from 'echarts/charts'
import { TooltipComponent, TitleComponent, LegendComponent } from 'echarts/components'
import VChart from 'vue-echarts'
import { getLifecycleSankey, type LifecycleSankey } from '@/api/admin/stats'
import { useChartTheme } from '@/composables/useChartTheme'

use([CanvasRenderer, SankeyChart, TooltipComponent, TitleComponent, LegendComponent])

const chartTheme = useChartTheme()
const loading = ref(false)
const data = ref<LifecycleSankey | null>(null)
const days = ref(30)
const topN = ref(8)

async function fetchData() {
  loading.value = true
  try {
    data.value = await getLifecycleSankey(days.value, topN.value)
  } catch {
    ElMessage.error('加载生命周期数据失败')
  } finally {
    loading.value = false
  }
}

// 颜色调色板：来源 / 品类 / 终态各一套
const sourceColors: Record<string, string> = {
  '📦 带标签入库': '#06b6d4',
  '🤖 端侧识别': '#0ea5e9',
  '✍️ 手动录入': '#a855f7',
}

const stateColors: Record<string, string> = {
  '🟢 充足在库': '#00b42a',
  '⚠️ 临期在库': '#fa8c16',
  '🔄 取出中': '#06b6d4',
  '✅ 已消耗': '#0ea5e9',
  '❌ 已浪费': '#f53f3f',
}

const categoryFallback = ['#3b82f6', '#8b5cf6', '#ec4899', '#f43f5e', '#ef4444', '#f97316', '#eab308', '#84cc16']

function colorForNode(name: string, depth: number): string {
  if (depth === 0) return sourceColors[name] || '#94a3b8'
  if (depth === 2) return stateColors[name] || '#94a3b8'
  // depth === 1：品类，按顺序取
  const idx = (data.value?.categories.categories || []).indexOf(name)
  return idx >= 0 ? categoryFallback[idx % categoryFallback.length] : '#94a3b8'
}

const sankeyOption = computed(() => {
  if (!data.value || data.value.nodes.length === 0) return {}
  const nodes = data.value.nodes.map(n => ({
    name: n.name,
    depth: n.depth,
    itemStyle: { color: colorForNode(n.name, n.depth) },
  }))
  return {
    tooltip: {
      trigger: 'item',
      triggerOn: 'mousemove',
      formatter: (params: any) => {
        if (params.dataType === 'edge') {
          return `${params.data.source} → ${params.data.target}<br/>数量：<b>${params.data.value}</b>`
        }
        return `${params.name}`
      },
    },
    series: [{
      type: 'sankey',
      left: 80,
      right: 100,
      top: 24,
      bottom: 24,
      nodeWidth: 18,
      nodeGap: 12,
      nodeAlign: 'justify',
      data: nodes,
      links: data.value.links,
      lineStyle: {
        color: 'gradient',
        curveness: 0.5,
        opacity: 0.5,
      },
      label: {
        fontSize: 12,
        fontWeight: 600,
      },
      emphasis: {
        focus: 'adjacency',
        lineStyle: { opacity: 0.8 },
      },
      levels: [
        { depth: 0, itemStyle: { borderColor: '#06b6d4' }, lineStyle: { opacity: 0.4 } },
        { depth: 1, lineStyle: { opacity: 0.4 } },
        { depth: 2, lineStyle: { opacity: 0.55 } },
      ],
    }],
  }
})

const stats = computed(() => {
  if (!data.value) return { total: 0, sources: 0, categories: 0, states: 0 }
  return {
    total: data.value.total,
    sources: data.value.categories.sources.length,
    categories: data.value.categories.categories.length,
    states: data.value.categories.states.length,
  }
})

onMounted(fetchData)
</script>

<template>
  <div v-loading="loading" class="lifecycle-page">
    <!-- 顶栏 -->
    <div class="page-header">
      <div class="page-title">
        <el-icon :size="22" color="var(--brand-primary)"><Connection /></el-icon>
        <span>食材生命周期</span>
      </div>
      <div class="page-controls">
        <el-radio-group v-model="days" @change="fetchData" size="small">
          <el-radio-button :value="7">最近 7 天</el-radio-button>
          <el-radio-button :value="30">30 天</el-radio-button>
          <el-radio-button :value="90">90 天</el-radio-button>
        </el-radio-group>
        <el-select v-model="topN" @change="fetchData" size="small" style="width: 140px">
          <el-option :value="5" label="Top 5 品类" />
          <el-option :value="8" label="Top 8 品类" />
          <el-option :value="12" label="Top 12 品类" />
        </el-select>
        <el-button size="small" @click="fetchData"><el-icon><Refresh /></el-icon></el-button>
      </div>
    </div>

    <!-- 说明 -->
    <div class="explain-bar">
      <div class="explain-item explain-from">
        <span class="explain-dot" style="background: #06b6d4"></span>
        <span>第一列：<strong>来源</strong>（端侧 / 手动 / 带标签）</span>
      </div>
      <el-icon :size="14" color="var(--text-placeholder)"><Right /></el-icon>
      <div class="explain-item explain-mid">
        <span class="explain-dot" style="background: #8b5cf6"></span>
        <span>第二列：<strong>品类</strong>（Top {{ topN }} + 其他）</span>
      </div>
      <el-icon :size="14" color="var(--text-placeholder)"><Right /></el-icon>
      <div class="explain-item explain-to">
        <span class="explain-dot" style="background: #00b42a"></span>
        <span>第三列：<strong>终态</strong>（在库 / 临期 / 消耗 / 浪费）</span>
      </div>
    </div>

    <!-- KPI -->
    <div class="kpi-row">
      <div class="kpi-card">
        <div class="kpi-emoji">📦</div>
        <div>
          <div class="kpi-num">{{ stats.total }}</div>
          <div class="kpi-lbl">{{ days }} 天入库总数</div>
        </div>
      </div>
      <div class="kpi-card">
        <div class="kpi-emoji">🌊</div>
        <div>
          <div class="kpi-num">{{ stats.sources }}</div>
          <div class="kpi-lbl">入库来源</div>
        </div>
      </div>
      <div class="kpi-card">
        <div class="kpi-emoji">🏷️</div>
        <div>
          <div class="kpi-num">{{ stats.categories }}</div>
          <div class="kpi-lbl">不同品类</div>
        </div>
      </div>
      <div class="kpi-card">
        <div class="kpi-emoji">🎯</div>
        <div>
          <div class="kpi-num">{{ stats.states }}</div>
          <div class="kpi-lbl">终态分类</div>
        </div>
      </div>
    </div>

    <!-- Sankey -->
    <el-card shadow="never" class="sankey-card">
      <template #header>
        <span class="card-title">
          <el-icon :size="14" color="var(--brand-primary)"><DataLine /></el-icon>
          流量图：每条线粗细代表数量，鼠标悬浮可高亮全链路
        </span>
      </template>
      <div v-if="!data || data.total === 0" class="empty-tip">
        <el-icon :size="40" color="var(--text-placeholder)"><Connection /></el-icon>
        <p>窗口内暂无入库记录，跑下端侧 simulator 或手动入几条试试</p>
      </div>
      <v-chart v-else :theme="chartTheme" :option="sankeyOption" autoresize class="sankey-chart" />
    </el-card>
  </div>
</template>

<style scoped>
.lifecycle-page {
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
  font-weight: 700;
  color: var(--text-primary);
}

.page-controls {
  display: flex;
  align-items: center;
  gap: 10px;
}

.explain-bar {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 12px;
  padding: 10px 18px;
  background: var(--bg-card);
  border-radius: 999px;
  border: 1px solid var(--border-color);
  font-size: 12px;
  color: var(--text-secondary);
  align-self: flex-start;
}

.explain-item {
  display: inline-flex;
  align-items: center;
  gap: 6px;
}

.explain-item strong {
  color: var(--text-primary);
}

.explain-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
}

.kpi-row {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 12px;
}

.kpi-card {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 14px 18px;
  background: var(--bg-card);
  border-radius: var(--radius-md);
  box-shadow: var(--shadow-sm);
  border: 1px solid var(--border-color);
}

.kpi-emoji {
  font-size: 26px;
  line-height: 1;
}

.kpi-num {
  font-size: 22px;
  font-weight: 800;
  color: var(--text-primary);
  font-variant-numeric: tabular-nums;
  line-height: 1.1;
}

.kpi-lbl {
  font-size: 12px;
  color: var(--text-secondary);
  margin-top: 2px;
}

.sankey-card {
  flex: 1;
  display: flex;
  flex-direction: column;
}

.sankey-card :deep(.el-card__body) {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-height: 0;
}

.card-title {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  font-size: 14px;
  color: var(--text-secondary);
}

.sankey-chart {
  width: 100%;
  height: 540px;
}

.empty-tip {
  text-align: center;
  padding: 60px 0;
  display: flex;
  flex-direction: column;
  gap: 10px;
  align-items: center;
  color: var(--text-placeholder);
  font-size: 13px;
}

@media (max-width: 1100px) {
  .kpi-row { grid-template-columns: repeat(2, 1fr); }
}
</style>
