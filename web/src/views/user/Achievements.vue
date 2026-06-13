<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { use } from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import { LineChart } from 'echarts/charts'
import { GridComponent, TooltipComponent } from 'echarts/components'
import VChart from 'vue-echarts'
import { ElMessage } from 'element-plus'
import { getAchievements, type AchievementResponse } from '@/api/user/nutrition'
import { useChartTheme } from '@/composables/useChartTheme'
import AnimatedNumber from '@/components/AnimatedNumber.vue'

use([CanvasRenderer, LineChart, GridComponent, TooltipComponent])

const chartTheme = useChartTheme()

const loading = ref(false)
const data = ref<AchievementResponse | null>(null)

async function fetchData() {
  loading.value = true
  try {
    data.value = await getAchievements()
  } catch {
    ElMessage.error('加载成就失败')
  } finally {
    loading.value = false
  }
}

const profile = computed(() => data.value?.profile)
const badges = computed(() => data.value?.achievements || [])
const unlocked = computed(() => badges.value.filter(b => b.unlocked))
const locked = computed(() => badges.value.filter(b => !b.unlocked))

// 等级进度（当前 score → 下一档）
const levelPct = computed(() => {
  const p = profile.value
  if (!p) return 0
  if (p.level_idx >= 5) return 100
  const prev = [0, 10, 30, 80, 200][p.level_idx - 1] || 0
  const span = p.level_next_score - prev
  if (span <= 0) return 0
  return Math.min(100, Math.round(((p.level_score - prev) / span) * 100))
})

const trendOption = computed(() => {
  const trend = data.value?.consume_trend || []
  return {
    grid: { left: 36, right: 16, top: 24, bottom: 28 },
    tooltip: {
      trigger: 'axis',
      formatter: (params: any) => {
        const p = params[0]
        return `${p.axisValue}<br/>消耗 <b>${p.data}</b> 件`
      },
    },
    xAxis: {
      type: 'category',
      data: trend.map(t => t[0].slice(5)),
      axisLine: { lineStyle: { color: '#e5e6eb' } },
      axisLabel: { color: '#86909c', fontSize: 10, interval: 4 },
    },
    yAxis: {
      type: 'value',
      minInterval: 1,
      splitLine: { lineStyle: { type: 'dashed', color: '#f2f3f5' } },
      axisLabel: { color: '#86909c', fontSize: 11 },
    },
    series: [{
      type: 'line',
      smooth: true,
      symbol: 'circle',
      symbolSize: 6,
      data: trend.map(t => t[1]),
      itemStyle: { color: '#0ea5e9' },
      lineStyle: { width: 2.5, color: '#0ea5e9' },
      areaStyle: {
        color: {
          type: 'linear',
          x: 0, y: 0, x2: 0, y2: 1,
          colorStops: [
            { offset: 0, color: 'rgba(14, 165, 233, 0.42)' },
            { offset: 1, color: 'rgba(14, 165, 233, 0.04)' },
          ],
        },
      },
    }],
  }
})

function fmtDate(s: string | null) {
  if (!s) return '—'
  return new Date(s).toLocaleDateString('zh-CN')
}

onMounted(fetchData)
</script>

<template>
  <div v-loading="loading" class="ach-page">
    <!-- 顶部 Hero：等级 + 进度 -->
    <div v-if="profile" class="hero">
      <div class="hero-bg"></div>
      <div class="hero-inner">
        <div class="avatar">{{ (profile.username[0] || '?').toUpperCase() }}</div>
        <div class="hero-body">
          <div class="hero-name">
            {{ profile.username }}
            <span class="level-badge">Lv.{{ profile.level_idx }} · {{ profile.level_name }}</span>
          </div>
          <div class="hero-meta">
            <span>📅 注册 {{ profile.register_days }} 天</span>
            <span>·</span>
            <span>🏅 解锁 {{ profile.unlocked_count }}/{{ profile.total_count }}</span>
            <span>·</span>
            <span>🔥 经验 {{ profile.level_score }}</span>
          </div>
          <div class="level-progress">
            <div class="bar"><div class="bar-fill" :style="{ width: levelPct + '%' }"></div></div>
            <div class="level-pct">
              {{ profile.level_idx >= 5
                ? '已封顶 ✨'
                : `距下一档 ${Math.max(0, profile.level_next_score - profile.level_score)} 经验` }}
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- 个人档案小卡 -->
    <div v-if="profile" class="profile-grid">
      <div class="p-card"><div class="p-emoji">📚</div>
        <div><div class="p-num"><AnimatedNumber :value="profile.saved_count" /></div><div class="p-label">收藏食谱</div></div></div>
      <div class="p-card"><div class="p-emoji">🍳</div>
        <div><div class="p-num"><AnimatedNumber :value="profile.total_cooks" /></div><div class="p-label">累计打卡</div></div></div>
      <div class="p-card"><div class="p-emoji">⭐</div>
        <div><div class="p-num"><AnimatedNumber :value="profile.rated_count" /></div><div class="p-label">已评分</div></div></div>
      <div class="p-card"><div class="p-emoji">📝</div>
        <div><div class="p-num"><AnimatedNumber :value="profile.note_count" /></div><div class="p-label">写过笔记</div></div></div>
      <div class="p-card"><div class="p-emoji">🥬</div>
        <div><div class="p-num"><AnimatedNumber :value="profile.inv_total" /></div><div class="p-label">累计入库</div></div></div>
      <div class="p-card"><div class="p-emoji">✨</div>
        <div><div class="p-num"><AnimatedNumber :value="profile.inv_consumed" /></div><div class="p-label">有效消耗</div></div></div>
      <div class="p-card"><div class="p-emoji">🌈</div>
        <div><div class="p-num"><AnimatedNumber :value="profile.inv_categories" /></div><div class="p-label">品类种类</div></div></div>
      <div class="p-card"><div class="p-emoji">💚</div>
        <div><div class="p-num"><AnimatedNumber :value="profile.pref_count" /></div><div class="p-label">饮食偏好</div></div></div>
    </div>

    <!-- 消耗趋势 -->
    <el-card v-if="profile" shadow="never" class="trend-card">
      <template #header>
        <span class="card-title">📈 近 30 天消耗趋势</span>
        <span class="card-sub">合计 <strong>{{ profile.consume_30d }}</strong> 件</span>
      </template>
      <v-chart
        :theme="chartTheme"
        :option="trendOption"
        autoresize
        class="trend-chart"
      />
    </el-card>

    <!-- 已解锁徽章 -->
    <el-card shadow="never" class="badge-card">
      <template #header>
        <span class="card-title">🏆 已解锁徽章 · {{ unlocked.length }}</span>
      </template>
      <div v-if="unlocked.length > 0" class="badge-grid">
        <div v-for="b in unlocked" :key="b.id" class="badge unlocked">
          <div class="badge-emoji">{{ b.emoji }}</div>
          <div class="badge-name">{{ b.name }}</div>
          <div class="badge-desc">{{ b.desc }}</div>
          <div class="badge-stamp">已获得</div>
        </div>
      </div>
      <el-empty v-else description="还没有解锁徽章，去完成第一个挑战吧" />
    </el-card>

    <!-- 待解锁徽章 -->
    <el-card v-if="locked.length > 0" shadow="never" class="badge-card">
      <template #header>
        <span class="card-title">🎯 进行中 · {{ locked.length }}</span>
      </template>
      <div class="badge-grid">
        <div v-for="b in locked" :key="b.id" class="badge locked">
          <div class="badge-emoji">{{ b.emoji }}</div>
          <div class="badge-name">{{ b.name }}</div>
          <div class="badge-desc">{{ b.desc }}</div>
          <div class="badge-progress">
            <div class="bp-bar">
              <div class="bp-fill" :style="{ width: Math.round((b.progress / b.total) * 100) + '%' }"></div>
            </div>
            <div class="bp-text">{{ b.progress }} / {{ b.total }}</div>
          </div>
        </div>
      </div>
    </el-card>

    <!-- 注册时间小尾巴 -->
    <div v-if="profile" class="footer-tip">
      🌱 自 {{ fmtDate(profile.register_at) }} 起，与智能冰箱一同成长
    </div>
  </div>
</template>

<style scoped>
.ach-page {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

/* Hero */
.hero {
  position: relative;
  border-radius: var(--radius-md);
  overflow: hidden;
  background: var(--bg-card);
  box-shadow: var(--shadow-sm);
}

.hero-bg {
  position: absolute;
  inset: 0;
  background:
    radial-gradient(circle at 12% 20%, rgba(14, 165, 233, 0.35), transparent 45%),
    radial-gradient(circle at 90% 80%, rgba(249, 115, 22, 0.18), transparent 50%),
    linear-gradient(135deg, #eef7fe 0%, #eef7fe 100%);
}

.hero-inner {
  position: relative;
  display: flex;
  align-items: center;
  gap: 22px;
  padding: 26px 30px;
}

.avatar {
  width: 78px;
  height: 78px;
  border-radius: 50%;
  background: linear-gradient(135deg, #0ea5e9, #6366f1);
  color: #fff;
  font-size: 36px;
  font-weight: 700;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  box-shadow: 0 8px 22px rgba(14, 165, 233, 0.4);
}

.hero-body {
  flex: 1;
  min-width: 0;
}

.hero-name {
  font-size: 22px;
  font-weight: 700;
  color: var(--text-primary);
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
}

.level-badge {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 3px 10px;
  background: linear-gradient(135deg, #f97316, #f59e0b);
  color: #fff;
  border-radius: 999px;
  font-size: 12px;
  font-weight: 600;
  box-shadow: 0 4px 10px rgba(249, 115, 22, 0.35);
}

.hero-meta {
  display: flex;
  gap: 8px;
  margin-top: 6px;
  font-size: 13px;
  color: var(--text-secondary);
  flex-wrap: wrap;
}

.level-progress {
  margin-top: 12px;
}

.bar {
  height: 10px;
  border-radius: 5px;
  background: rgba(0, 0, 0, 0.06);
  overflow: hidden;
}

.bar-fill {
  height: 100%;
  background: linear-gradient(90deg, #0ea5e9, #6366f1);
  border-radius: 5px;
  transition: width 0.6s ease;
}

.level-pct {
  margin-top: 6px;
  font-size: 12px;
  color: var(--text-secondary);
}

/* 档案小卡 */
.profile-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 12px;
}

.p-card {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 14px 16px;
  background: var(--bg-card);
  border-radius: var(--radius-md);
  box-shadow: var(--shadow-sm);
  transition: all 0.18s;
}

.p-card:hover {
  transform: translateY(-2px);
  box-shadow: 0 8px 18px rgba(0, 0, 0, 0.06);
}

.p-emoji {
  font-size: 26px;
  line-height: 1;
}

.p-num {
  font-size: 20px;
  font-weight: 700;
  color: var(--text-primary);
  font-variant-numeric: tabular-nums;
  line-height: 1.2;
}

.p-label {
  font-size: 11px;
  color: var(--text-secondary);
  margin-top: 2px;
}

/* 趋势 */
.trend-card :deep(.el-card__header) {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.card-title {
  font-size: 15px;
  font-weight: 600;
  color: var(--text-primary);
}

.card-sub {
  font-size: 12px;
  color: var(--text-secondary);
  float: right;
}

.card-sub strong {
  color: var(--brand-primary-dark);
  font-weight: 700;
}

.trend-chart {
  width: 100%;
  height: 200px;
}

/* 徽章 */
.badge-card {
  /* spacing */
}

.badge-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(170px, 1fr));
  gap: 14px;
}

.badge {
  position: relative;
  padding: 18px 14px 14px;
  border-radius: 14px;
  border: 1px solid var(--border-color);
  text-align: center;
  background: var(--bg-card);
  transition: all 0.22s;
}

.badge.unlocked {
  background: linear-gradient(160deg, #fff8e6 0%, var(--bg-card) 100%);
  border-color: rgba(249, 115, 22, 0.3);
}

.badge.unlocked:hover {
  transform: translateY(-3px) rotate(-1deg);
  box-shadow: 0 12px 22px rgba(249, 115, 22, 0.2);
}

.badge.locked {
  filter: grayscale(0.3);
  opacity: 0.85;
}

.badge.locked .badge-emoji {
  filter: grayscale(0.6);
  opacity: 0.55;
}

.badge.locked:hover {
  filter: grayscale(0);
  opacity: 1;
  transform: translateY(-2px);
}

.badge-emoji {
  font-size: 38px;
  line-height: 1;
  margin-bottom: 8px;
}

.badge-name {
  font-size: 14px;
  font-weight: 700;
  color: var(--text-primary);
}

.badge-desc {
  font-size: 11px;
  color: var(--text-secondary);
  margin-top: 4px;
  min-height: 32px;
}

.badge-stamp {
  display: inline-block;
  margin-top: 8px;
  padding: 2px 10px;
  border-radius: 999px;
  font-size: 11px;
  font-weight: 600;
  background: linear-gradient(135deg, #f59e0b, #f97316);
  color: #fff;
  box-shadow: 0 2px 6px rgba(249, 115, 22, 0.3);
}

.badge-progress {
  margin-top: 10px;
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.bp-bar {
  height: 6px;
  border-radius: 3px;
  background: rgba(0, 0, 0, 0.06);
  overflow: hidden;
}

.bp-fill {
  height: 100%;
  background: linear-gradient(90deg, #0ea5e9, #6366f1);
  border-radius: 3px;
  transition: width 0.5s ease;
}

.bp-text {
  font-size: 11px;
  color: var(--text-secondary);
  font-variant-numeric: tabular-nums;
}

.footer-tip {
  text-align: center;
  font-size: 12px;
  color: var(--text-placeholder);
  padding: 8px 0 4px;
}

@media (max-width: 900px) {
  .profile-grid { grid-template-columns: repeat(2, 1fr); }
  .hero-inner { flex-direction: column; text-align: center; }
}
</style>
