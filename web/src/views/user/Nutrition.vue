<script setup lang="ts">
/**
 * 健康饮食报告：把库存按营养类别（蔬菜/肉/水果/...）展示分布 + 评分 + 建议。
 */
import { ref, computed, onMounted } from 'vue'
import { use } from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import { PieChart, BarChart } from 'echarts/charts'
import { TooltipComponent, LegendComponent, GridComponent } from 'echarts/components'
import VChart from 'vue-echarts'
import { ElMessage } from 'element-plus'
import { getNutritionReport, getCoachAdvice, type NutritionReport, type CoachResponse } from '@/api/user/nutrition'
import { useChartTheme } from '@/composables/useChartTheme'
import AnimatedNumber from '@/components/AnimatedNumber.vue'

use([CanvasRenderer, PieChart, BarChart, TooltipComponent, LegendComponent, GridComponent])

const chartTheme = useChartTheme()
const loading = ref(false)
const data = ref<NutritionReport | null>(null)
const days = ref(30)

async function fetchData() {
  loading.value = true
  try {
    data.value = await getNutritionReport(days.value)
  } catch {
    ElMessage.error('加载营养报告失败')
  } finally {
    loading.value = false
  }
}

// ---- AI 教练 ----
const coach = ref<CoachResponse | null>(null)
const coachLoading = ref(false)
const coachError = ref<string>('')

async function loadCoach() {
  coachLoading.value = true
  coachError.value = ''
  try {
    coach.value = await getCoachAdvice(days.value)
  } catch (e: any) {
    coachError.value = e?.response?.data?.detail || e?.message || '请稍后再试'
    ElMessage.error('AI 教练调用失败')
  } finally {
    coachLoading.value = false
  }
}

const score = computed(() => data.value?.health_overall.score ?? 0)
const level = computed(() => data.value?.health_overall.level ?? 'fair')

const levelStyle = computed(() => {
  if (level.value === 'good') return { label: '👍 健康', color: '#00b42a', bg: '#e8f7e8' }
  if (level.value === 'fair') return { label: '🙂 还行', color: '#fa8c16', bg: '#fff7e6' }
  return { label: '⚠️ 需改善', color: '#f53f3f', bg: '#ffece8' }
})

const distOption = computed(() => {
  const d = data.value?.distribution || []
  if (d.length === 0) return {}
  return {
    color: d.map(x => x.color),
    tooltip: { trigger: 'item', formatter: '{b}: {c} ({d}%)' },
    legend: { bottom: 0, textStyle: { fontSize: 12 } },
    series: [{
      type: 'pie',
      radius: ['52%', '78%'],
      avoidLabelOverlap: true,
      itemStyle: { borderRadius: 6, borderColor: '#fff', borderWidth: 2 },
      label: { show: false },
      labelLine: { show: false },
      data: d.map(x => ({ name: `${x.emoji} ${x.label}`, value: x.count })),
    }],
  }
})

const ratioOption = computed(() => {
  const h = data.value?.health_overall
  if (!h) return {}
  const items = [
    { name: '蔬果占比', value: Math.round(h.veg_fruit_ratio * 100), tone: '#00b42a' },
    { name: '蛋白质占比', value: Math.round(h.meat_ratio * 100), tone: '#fa8c16' },
    { name: '零食占比', value: Math.round(h.snack_ratio * 100), tone: '#f53f3f' },
  ]
  return {
    tooltip: { trigger: 'axis', formatter: '{b}: {c}%' },
    grid: { left: 80, right: 30, top: 10, bottom: 20 },
    xAxis: { type: 'value', max: 100, axisLabel: { formatter: '{value}%' } },
    yAxis: { type: 'category', data: items.map(i => i.name) },
    series: [{
      type: 'bar',
      barMaxWidth: 18,
      data: items.map(i => ({ value: i.value, itemStyle: { color: i.tone, borderRadius: [0, 6, 6, 0] } })),
      label: { show: true, position: 'right', formatter: '{c}%' },
    }],
  }
})

onMounted(fetchData)
</script>

<template>
  <div v-loading="loading" class="nutrition-page">
    <!-- 顶部 -->
    <div class="page-header">
      <div class="page-title">
        <el-icon :size="22" color="var(--brand-primary)"><Apple /></el-icon>
        <span>健康饮食报告</span>
      </div>
      <el-radio-group v-model="days" @change="fetchData" size="small">
        <el-radio-button :value="7">最近 7 天</el-radio-button>
        <el-radio-button :value="30">30 天</el-radio-button>
        <el-radio-button :value="90">90 天</el-radio-button>
      </el-radio-group>
    </div>

    <!-- 评分卡 -->
    <div v-if="data" class="score-row">
      <div class="score-card">
        <div class="score-ring">
          <svg viewBox="0 0 100 100" class="score-svg">
            <circle cx="50" cy="50" r="44" stroke="var(--bg-soft)" stroke-width="8" fill="none" />
            <circle
              cx="50" cy="50" r="44"
              :stroke="levelStyle.color"
              stroke-width="8"
              fill="none"
              stroke-linecap="round"
              :stroke-dasharray="`${(score / 100) * 276.46} 276.46`"
              transform="rotate(-90 50 50)"
              style="transition: stroke-dasharray 0.6s ease"
            />
          </svg>
          <div class="score-text">
            <div class="score-num">
              <AnimatedNumber :value="score" />
            </div>
            <div class="score-label">满分 100</div>
          </div>
        </div>
        <div class="score-info">
          <div class="score-tag" :style="{ background: levelStyle.bg, color: levelStyle.color }">
            {{ levelStyle.label }}
          </div>
          <div class="score-meta">
            最近 <strong>{{ data.window_days }}</strong> 天 ·
            共入库 <strong>{{ data.total }}</strong> 件食材
          </div>
          <div class="score-tips">
            <div v-for="tip in data.health_overall.tips" :key="tip" class="score-tip">
              💡 {{ tip }}
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- AI 营养教练 -->
    <div v-if="data" class="coach-card">
      <div class="coach-header">
        <div class="coach-icon">
          <span style="font-size: 22px">🥗</span>
        </div>
        <div style="flex: 1; min-width: 0">
          <div class="coach-title">AI 营养教练</div>
          <div class="coach-sub">基于你的健康评分、临期食材、消耗节奏和偏好，给出本周建议</div>
        </div>
        <el-button
          v-if="!coach"
          type="primary"
          :loading="coachLoading"
          @click="loadCoach"
          class="coach-btn"
        >
          <el-icon v-if="!coachLoading"><MagicStick /></el-icon>
          {{ coachLoading ? '正在分析…' : '让 AI 给我建议' }}
        </el-button>
        <el-button
          v-else
          link
          :loading="coachLoading"
          @click="loadCoach"
        >
          <el-icon><Refresh /></el-icon>
          重新生成
        </el-button>
      </div>

      <div v-if="coachError && !coach" class="coach-error">
        <el-icon><Warning /></el-icon>
        AI 教练暂不可用：{{ coachError }}
      </div>

      <div v-if="coach && coach.advice" class="coach-body">
        <div v-if="coach.advice.summary" class="coach-summary">
          <span class="coach-quote">"</span>
          {{ coach.advice.summary }}
          <span class="coach-quote">"</span>
        </div>

        <div class="coach-grid">
          <div v-if="coach.advice.week_plan?.length" class="coach-section coach-plan">
            <div class="coach-section-title">📅 本周饮食安排</div>
            <ol class="coach-list">
              <li v-for="(line, i) in coach.advice.week_plan" :key="i">{{ line }}</li>
            </ol>
          </div>

          <div v-if="coach.advice.action_items?.length" class="coach-section coach-action">
            <div class="coach-section-title">✅ 行动建议</div>
            <ul class="coach-list">
              <li v-for="(line, i) in coach.advice.action_items" :key="i">{{ line }}</li>
            </ul>
          </div>

          <div v-if="coach.advice.avoid?.length" class="coach-section coach-avoid">
            <div class="coach-section-title">⛔ 本周尽量少吃</div>
            <ul class="coach-list">
              <li v-for="(line, i) in coach.advice.avoid" :key="i">{{ line }}</li>
            </ul>
          </div>
        </div>

        <div v-if="coach.expiring?.length" class="coach-expiring">
          <span class="coach-expiring-label">⏰ 需要本周用掉的临期食材：</span>
          <span
            v-for="e in coach.expiring"
            :key="e.category"
            class="coach-expiring-tag"
            :class="{ urgent: e.days <= 1 }"
          >
            {{ e.category }} <small>剩 {{ e.days }} 天</small>
          </span>
        </div>
      </div>
    </div>

    <!-- 图表 -->
    <div v-if="data" class="chart-row">
      <el-card shadow="never">
        <template #header><span class="card-title">食材类别分布</span></template>
        <v-chart v-if="data.distribution.length > 0" :theme="chartTheme" :option="distOption" autoresize class="chart" />
        <el-empty v-else description="暂无数据" />
      </el-card>
      <el-card shadow="never">
        <template #header><span class="card-title">关键比例</span></template>
        <v-chart v-if="data.distribution.length > 0" :theme="chartTheme" :option="ratioOption" autoresize class="chart" />
        <el-empty v-else description="暂无数据" />
      </el-card>
    </div>

    <!-- 食材标签明细 -->
    <el-card v-if="data && data.by_category.length > 0" shadow="never">
      <template #header><span class="card-title">已入库食材的健康标签</span></template>
      <div class="tag-grid">
        <div
          v-for="item in data.by_category"
          :key="item.category"
          class="tag-item"
          :style="{ borderLeftColor: item.color }"
        >
          <div class="tag-emoji">{{ item.emoji }}</div>
          <div class="tag-body">
            <div class="tag-name">{{ item.category }}</div>
            <div class="tag-cat">{{ item.label }} · {{ item.count }} 件</div>
          </div>
          <div v-if="!item.healthy" class="tag-warn" title="可能需控制摄入">
            <el-icon :size="12" color="#fa8c16"><Warning /></el-icon>
          </div>
        </div>
      </div>
    </el-card>
  </div>
</template>

<style scoped>
.nutrition-page {
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

.score-row {
  display: grid;
  grid-template-columns: 1fr;
  gap: 16px;
}

.score-card {
  display: flex;
  align-items: center;
  gap: 24px;
  padding: 24px;
  background: var(--bg-card);
  border-radius: var(--radius-md);
  box-shadow: var(--shadow-sm);
}

.score-ring {
  position: relative;
  width: 120px;
  height: 120px;
  flex-shrink: 0;
}

.score-svg {
  width: 100%;
  height: 100%;
}

.score-text {
  position: absolute;
  inset: 0;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
}

.score-num {
  font-size: 32px;
  font-weight: 800;
  color: var(--text-primary);
  line-height: 1;
  font-variant-numeric: tabular-nums;
}

.score-label {
  font-size: 11px;
  color: var(--text-placeholder);
  margin-top: 4px;
}

.score-info {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.score-tag {
  display: inline-block;
  width: fit-content;
  padding: 4px 14px;
  border-radius: 999px;
  font-size: 13px;
  font-weight: 600;
}

.score-meta {
  font-size: 13px;
  color: var(--text-secondary);
}

.score-tips {
  display: flex;
  flex-direction: column;
  gap: 4px;
  margin-top: 4px;
}

.score-tip {
  font-size: 12px;
  color: var(--text-primary);
  background: var(--bg-soft);
  padding: 6px 10px;
  border-radius: 8px;
}

.chart-row {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 16px;
}

/* AI 教练卡 */
.coach-card {
  position: relative;
  padding: 22px 26px;
  border-radius: var(--radius-md);
  background: linear-gradient(135deg, rgba(14, 165, 233, 0.10), rgba(99, 102, 241, 0.06)), var(--bg-card);
  border: 1px solid rgba(14, 165, 233, 0.4);
  box-shadow: 0 8px 24px rgba(14, 165, 233, 0.10);
  overflow: hidden;
}

.coach-card::before {
  content: '';
  position: absolute;
  top: -40px;
  right: -40px;
  width: 200px;
  height: 200px;
  background: radial-gradient(circle, rgba(14, 165, 233, 0.20) 0%, transparent 60%);
  filter: blur(8px);
  pointer-events: none;
}

.coach-header {
  position: relative;
  display: flex;
  align-items: center;
  gap: 14px;
  margin-bottom: 16px;
}

.coach-icon {
  width: 48px;
  height: 48px;
  border-radius: 14px;
  background: linear-gradient(135deg, var(--brand-primary), var(--brand-primary-dark));
  display: flex;
  align-items: center;
  justify-content: center;
  box-shadow: 0 6px 14px rgba(14, 165, 233, 0.35);
}

.coach-title {
  font-size: 18px;
  font-weight: 700;
  color: var(--text-primary);
}

.coach-sub {
  font-size: 12px;
  color: var(--text-secondary);
  margin-top: 2px;
}

.coach-btn {
  background: linear-gradient(135deg, var(--brand-primary), var(--brand-primary-dark)) !important;
  border-color: transparent !important;
  font-weight: 600;
  box-shadow: 0 4px 10px rgba(14, 165, 233, 0.30);
}

.coach-btn:hover {
  transform: translateY(-1px);
  box-shadow: 0 8px 16px rgba(14, 165, 233, 0.40);
}

.coach-error {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 10px 14px;
  border-radius: 8px;
  background: #ffece8;
  color: #f53f3f;
  font-size: 13px;
}

.coach-body {
  position: relative;
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.coach-summary {
  position: relative;
  font-size: 16px;
  font-weight: 500;
  color: var(--text-primary);
  line-height: 1.6;
  padding: 14px 20px;
  background: var(--bg-card);
  border-radius: 12px;
  border-left: 4px solid var(--brand-primary);
}

.coach-quote {
  font-size: 28px;
  color: var(--brand-primary);
  font-family: 'Georgia', serif;
  vertical-align: -6px;
  margin: 0 4px;
  opacity: 0.5;
}

.coach-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(260px, 1fr));
  gap: 12px;
}

.coach-section {
  padding: 14px 16px;
  border-radius: 12px;
  background: var(--bg-card);
  border: 1px solid var(--border-color);
}

.coach-plan {
  border-left: 3px solid #6366f1;
}

.coach-action {
  border-left: 3px solid #00b42a;
}

.coach-avoid {
  border-left: 3px solid #f53f3f;
}

.coach-section-title {
  font-size: 13px;
  font-weight: 700;
  color: var(--text-primary);
  margin-bottom: 10px;
}

.coach-list {
  margin: 0;
  padding-left: 20px;
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.coach-list li {
  font-size: 13px;
  color: var(--text-secondary);
  line-height: 1.6;
}

.coach-expiring {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 8px;
  padding: 12px 14px;
  background: rgba(250, 140, 22, 0.08);
  border: 1px dashed #fa8c16;
  border-radius: 10px;
}

.coach-expiring-label {
  font-size: 13px;
  font-weight: 600;
  color: #fa8c16;
}

.coach-expiring-tag {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 4px 10px;
  border-radius: 999px;
  background: var(--bg-card);
  font-size: 12px;
  font-weight: 600;
  color: var(--text-primary);
  border: 1px solid var(--border-color);
}

.coach-expiring-tag small {
  color: var(--text-secondary);
  font-size: 11px;
  font-weight: 500;
}

.coach-expiring-tag.urgent {
  background: #ffece8;
  color: #f53f3f;
  border-color: #ffbfb3;
}

.coach-expiring-tag.urgent small {
  color: #f53f3f;
}

.card-title {
  font-size: 15px;
  font-weight: 600;
}

.chart {
  width: 100%;
  height: 280px;
}

.tag-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(220px, 1fr));
  gap: 10px;
}

.tag-item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 12px;
  background: var(--bg-soft);
  border-radius: 10px;
  border-left: 3px solid;
}

.tag-emoji {
  font-size: 24px;
  line-height: 1;
}

.tag-body {
  flex: 1;
  min-width: 0;
}

.tag-name {
  font-size: 14px;
  font-weight: 600;
  color: var(--text-primary);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.tag-cat {
  font-size: 11px;
  color: var(--text-secondary);
}

.tag-warn {
  flex-shrink: 0;
}

@media (max-width: 1100px) {
  .chart-row { grid-template-columns: 1fr; }
}
</style>
