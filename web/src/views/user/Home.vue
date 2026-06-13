<script setup lang="ts">
/**
 * 用户首页 Dashboard：登录后第一眼看到的页面。
 *
 * 设计目标：
 * - 一眼看到"今天该做什么"
 * - 临期提醒直达处理
 * - 快捷入口 + 最近食谱
 */
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { useUserAuthStore } from '@/stores/userAuth'
import { useChatStore } from '@/stores/chat'
import { getInventoryList, type InventoryItem } from '@/api/user/inventory'
import { listSavedRecipes, getDailyTip, type SavedRecipe, type DailyTip } from '@/api/user/agent'
import { getNotificationCount } from '@/api/user/notification'
import { getEnvironment, type EnvironmentInfo } from '@/api/user/environment'
import { getNutritionReport, type NutritionReport } from '@/api/user/nutrition'
import AnimatedNumber from '@/components/AnimatedNumber.vue'

const router = useRouter()
const authStore = useUserAuthStore()
const chatStore = useChatStore()

const loading = ref(false)
const items = ref<InventoryItem[]>([])
const recipes = ref<SavedRecipe[]>([])
const env = ref<EnvironmentInfo | null>(null)
const nutrition = ref<NutritionReport | null>(null)
const unreadCount = ref(0)

async function fetchAll() {
  loading.value = true
  try {
    const [invRes, recRes, envRes, nutriRes, notiRes] = await Promise.all([
      getInventoryList({ status: 'IN_STOCK' }).catch(() => []),
      listSavedRecipes(8).catch(() => []),
      getEnvironment().catch(() => null),
      getNutritionReport(7).catch(() => null),
      getNotificationCount().catch(() => ({ unread_count: 0 })),
    ])
    items.value = invRes as any
    recipes.value = recRes as any
    env.value = envRes as any
    nutrition.value = nutriRes as any
    unreadCount.value = notiRes?.unread_count ?? 0
  } finally {
    loading.value = false
  }
  // 异步加载每日小贴士（不阻塞首屏）
  loadDailyTip()
}

// ---- 每日提醒 ----
const dailyTip = ref<DailyTip | null>(null)
const tipLoading = ref(false)

async function loadDailyTip(refresh = false) {
  tipLoading.value = true
  try {
    dailyTip.value = await getDailyTip(refresh)
  } catch {
    // 静默
  } finally {
    tipLoading.value = false
  }
}

// ---- 时段问候 ----
const greeting = computed(() => {
  const h = new Date().getHours()
  if (h < 6) return '夜深了'
  if (h < 11) return '早上好'
  if (h < 14) return '中午好'
  if (h < 18) return '下午好'
  return '晚上好'
})

// ---- 临期食材分组 ----
function getRemainDays(item: InventoryItem): number {
  const expireAt = item.agent_metadata?.expire_at
  if (!expireAt) return Number.POSITIVE_INFINITY
  return Math.ceil((new Date(expireAt).getTime() - Date.now()) / 86400000)
}

const expiringGroups = computed(() => {
  const expired: InventoryItem[] = []
  const today: InventoryItem[] = []
  const soon: InventoryItem[] = []
  items.value.forEach(it => {
    const d = getRemainDays(it)
    if (d < 0) expired.push(it)
    else if (d <= 1) today.push(it)
    else if (d <= 3) soon.push(it)
  })
  return { expired, today, soon }
})

const totalExpiring = computed(() =>
  expiringGroups.value.expired.length +
  expiringGroups.value.today.length +
  expiringGroups.value.soon.length
)

// ---- 首页状态文案 ----
const heroTip = computed(() => {
  const e = expiringGroups.value
  if (e.expired.length > 0) {
    const names = e.expired.slice(0, 2).map(i => i.category).join('、')
    return {
      title: `有 ${e.expired.length} 件食材已过期`,
      desc: `${names} 等已经过期了，建议今天先处理掉，别继续占着冰箱空间。`,
      tone: 'danger' as const,
    }
  }
  if (e.today.length > 0) {
    const names = e.today.slice(0, 2).map(i => i.category).join('、')
    return {
      title: `今天有 ${e.today.length} 件食材需要优先用掉`,
      desc: `${names} 等快到保鲜期了，可以先安排到今天或明天的菜单里。`,
      tone: 'warn' as const,
    }
  }
  if (e.soon.length > 0) {
    const names = e.soon.slice(0, 2).map(i => i.category).join('、')
    return {
      title: `${e.soon.length} 件食材将在 3 天内过期`,
      desc: `${names} 等需要安排消耗，可以先做个简单计划。`,
      tone: 'caution' as const,
    }
  }
  if (items.value.length > 0) {
    return {
      title: `冰箱里有 ${items.value.length} 件食材`,
      desc: '目前没有明显的临期压力，可以按平时节奏安排本周饮食。',
      tone: 'good' as const,
    }
  }
  return {
    title: '冰箱暂时是空的',
    desc: '添加食材后，这里会显示保鲜、临期和本周饮食情况。',
    tone: 'empty' as const,
  }
})

// ---- 行动 ----
function goAskAboutExpiring() {
  // 凑一段消息，跳到 chat 自动发送
  const e = expiringGroups.value
  const all = [...e.expired, ...e.today, ...e.soon].slice(0, 5)
  if (all.length === 0) {
    router.push('/user/chat')
    return
  }
  const names = all.map(i => i.category).join('、')
  chatStore.queuedMessage = `请用我冰箱里这些临期的食材给我推荐 1-2 道菜：${names}`
  router.push('/user/chat')
}

function quickGoChat(text?: string) {
  if (text) chatStore.queuedMessage = text
  router.push('/user/chat')
}

// ---- 饮食评分 ----
const healthScore = computed(() => nutrition.value?.health_overall.score ?? null)
const healthLevel = computed(() => nutrition.value?.health_overall.level ?? null)
const healthColor = computed(() => {
  if (!healthLevel.value) return '#86909c'
  if (healthLevel.value === 'good') return '#00b42a'
  if (healthLevel.value === 'fair') return '#fa8c16'
  return '#f53f3f'
})

// ---- 最近食谱 ----
const recentRecipes = computed(() => recipes.value.slice(0, 6))

onMounted(fetchAll)
</script>

<template>
  <div v-loading="loading" class="home-page">
    <!-- 顶部问候 + 天气 -->
    <div class="hero-card" :class="'tone-' + heroTip.tone">
      <div class="hero-bg"></div>
      <div class="hero-row">
        <div class="hero-left">
          <div class="greet">
            <span>{{ greeting }}，<strong>{{ authStore.user?.username || '主人' }}</strong></span>
            <el-tag
              v-if="unreadCount > 0"
              type="danger"
              round
              size="small"
              style="margin-left: 8px; cursor: pointer"
              @click="$router.push('/user/inventory')"
            >
              {{ unreadCount }} 条未读
            </el-tag>
          </div>
          <div class="hero-title">
            {{ heroTip.title }}
          </div>
          <div class="hero-desc">{{ heroTip.desc }}</div>
          <div class="hero-actions">
            <el-button
              v-if="totalExpiring > 0"
              type="primary"
              size="large"
              @click="goAskAboutExpiring"
              class="hero-btn"
            >
              <el-icon><KnifeFork /></el-icon>
              看看怎么搭配
            </el-button>
            <el-button v-else size="large" @click="quickGoChat()" class="hero-btn">
              <el-icon><ChatDotRound /></el-icon>
              看看今天吃什么
            </el-button>
          </div>
        </div>

        <div class="hero-right">
          <div v-if="env" class="weather-mini">
            <div class="w-icon">
              <el-icon><MostlyCloudy /></el-icon>
            </div>
            <div class="w-info">
              <div class="w-temp">{{ env.temperature }}°</div>
              <div class="w-desc">{{ env.weather_desc }} · {{ env.city }}</div>
            </div>
          </div>
          <div v-if="healthScore !== null" class="health-mini" @click="$router.push('/user/nutrition')">
            <div class="hm-ring">
              <svg viewBox="0 0 80 80" class="hm-svg">
                <circle cx="40" cy="40" r="34" stroke="var(--bg-soft)" stroke-width="6" fill="none" />
                <circle
                  cx="40" cy="40" r="34"
                  :stroke="healthColor"
                  stroke-width="6"
                  fill="none"
                  stroke-linecap="round"
                  :stroke-dasharray="`${(healthScore / 100) * 213.6} 213.6`"
                  transform="rotate(-90 40 40)"
                />
              </svg>
              <div class="hm-num" :style="{ color: healthColor }">{{ healthScore }}</div>
            </div>
            <div class="hm-label">本周饮食评分</div>
          </div>
        </div>
      </div>
    </div>

    <!-- 每日提醒 -->
    <div class="tip-card" v-loading="tipLoading">
      <div class="tip-icon">
        <el-icon :size="24"><Notebook /></el-icon>
      </div>
      <div class="tip-body">
        <div class="tip-label">今日提醒</div>
        <div class="tip-text">
          <template v-if="dailyTip">{{ dailyTip.tip }}</template>
          <template v-else-if="tipLoading">正在整理今天的建议…</template>
          <template v-else>暂无提醒，可以稍后再看。</template>
        </div>
      </div>
      <button class="tip-refresh" :disabled="tipLoading" @click="loadDailyTip(true)" title="重新生成">
        <el-icon :size="16"><Refresh /></el-icon>
      </button>
    </div>

    <!-- 临期警告区 -->
    <div v-if="totalExpiring > 0" class="expiring-section">
      <div class="section-head">
        <h3 class="section-title">
          临期食材
          <span class="section-count">{{ totalExpiring }}</span>
        </h3>
        <el-button link type="primary" @click="$router.push('/user/expiring')">
          全部处理 →
        </el-button>
      </div>
      <div class="expiring-rows">
        <div
          v-for="item in [...expiringGroups.expired, ...expiringGroups.today, ...expiringGroups.soon].slice(0, 8)"
          :key="item.id"
          class="expiring-row"
          :class="{
            danger: getRemainDays(item) < 0,
            warn: getRemainDays(item) >= 0 && getRemainDays(item) <= 1,
            soon: getRemainDays(item) > 1 && getRemainDays(item) <= 3,
          }"
        >
          <div class="exp-status">{{ getRemainDays(item) < 0 ? '过期' : getRemainDays(item) <= 1 ? '今天' : '临期' }}</div>
          <div class="exp-body">
            <div class="exp-name">
              {{ item.category }}
              <span v-if="item.label_data?.brand" class="exp-brand">{{ item.label_data.brand }}</span>
            </div>
            <div class="exp-days">
              <template v-if="getRemainDays(item) < 0">
                已过期 <strong>{{ -getRemainDays(item) }}</strong> 天
              </template>
              <template v-else-if="getRemainDays(item) === 0">
                <strong>今天</strong>到期
              </template>
              <template v-else>
                还剩 <strong>{{ getRemainDays(item) }}</strong> 天
              </template>
            </div>
          </div>
          <el-button
            link
            type="primary"
            size="small"
            @click="quickGoChat(`用 ${item.category} 给我推荐一道菜`)"
          >
            看做法
          </el-button>
        </div>
      </div>
    </div>

    <!-- 快捷入口 -->
    <div class="quick-section">
      <h3 class="section-title">常用功能</h3>
      <div class="quick-grid">
        <div class="quick-card" @click="$router.push('/user/chat')">
          <div class="qc-icon"><el-icon><ChatDotRound /></el-icon></div>
          <div class="qc-title">吃什么</div>
          <div class="qc-desc">根据现有食材找灵感</div>
        </div>
        <div class="quick-card" @click="$router.push('/user/recipes')">
          <div class="qc-icon"><el-icon><Star /></el-icon></div>
          <div class="qc-title">我的食谱</div>
          <div class="qc-desc">收藏和评分</div>
        </div>
        <div class="quick-card" @click="$router.push('/user/nutrition')">
          <div class="qc-icon"><el-icon><Food /></el-icon></div>
          <div class="qc-title">健康饮食</div>
          <div class="qc-desc">查看本周营养情况</div>
        </div>
        <div class="quick-card" @click="$router.push('/user/expiring')">
          <div class="qc-icon"><el-icon><Bell /></el-icon></div>
          <div class="qc-title">临期处理</div>
          <div class="qc-desc">{{ totalExpiring }} 件待处理</div>
        </div>
        <div class="quick-card" @click="$router.push('/user/inventory')">
          <div class="qc-icon"><el-icon><Box /></el-icon></div>
          <div class="qc-title">库存查看</div>
          <div class="qc-desc">{{ items.length }} 件在库</div>
        </div>
        <div class="quick-card" @click="$router.push('/user/preferences')">
          <div class="qc-icon"><el-icon><Setting /></el-icon></div>
          <div class="qc-title">偏好设置</div>
          <div class="qc-desc">口味和忌口</div>
        </div>
        <div class="quick-card" @click="$router.push('/user/achievements')">
          <div class="qc-icon"><el-icon><Trophy /></el-icon></div>
          <div class="qc-title">我的成就</div>
          <div class="qc-desc">徽章和等级</div>
        </div>
        <div class="quick-card" @click="$router.push('/user/shopping')">
          <div class="qc-icon"><el-icon><ShoppingCart /></el-icon></div>
          <div class="qc-title">购物清单</div>
          <div class="qc-desc">缺什么补什么</div>
        </div>
      </div>
    </div>

    <!-- 最近食谱 -->
    <div v-if="recentRecipes.length > 0" class="recent-section">
      <div class="section-head">
        <h3 class="section-title">最近收藏的食谱</h3>
        <el-button link type="primary" @click="$router.push('/user/recipes')">
          查看全部 →
        </el-button>
      </div>
      <div class="recent-row">
        <div
          v-for="r in recentRecipes"
          :key="r.id"
          class="recent-card"
          @click="$router.push('/user/recipes')"
        >
          <div class="rc-name">{{ r.name }}</div>
          <div class="rc-meta">
            <span v-if="r.cooked_count > 0">做过 {{ r.cooked_count }} 次</span>
            <span v-if="r.rating">评分 {{ r.rating }}</span>
          </div>
        </div>
      </div>
    </div>

    <!-- 库存统计 -->
    <div class="stats-section">
      <div class="stat-block">
        <div class="sb-num">
          <AnimatedNumber :value="items.length" />
        </div>
        <div class="sb-label">在库食材</div>
      </div>
      <div class="stat-block">
        <div class="sb-num" :style="{ color: totalExpiring > 0 ? '#fa8c16' : 'var(--text-primary)' }">
          <AnimatedNumber :value="totalExpiring" />
        </div>
        <div class="sb-label">临期待处理</div>
      </div>
      <div class="stat-block">
        <div class="sb-num">
          <AnimatedNumber :value="recipes.length" />
        </div>
        <div class="sb-label">收藏食谱</div>
      </div>
      <div class="stat-block">
        <div class="sb-num">
          <AnimatedNumber :value="recipes.reduce((s, r) => s + (r.cooked_count || 0), 0)" />
        </div>
        <div class="sb-label">累计打卡</div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.home-page {
  display: flex;
  flex-direction: column;
  gap: 18px;
  color: var(--text-primary);
}

/* === Hero === */
.hero-card {
  position: relative;
  border-radius: 8px;
  border: 1px solid var(--border-color);
  background:
    linear-gradient(135deg, rgba(255, 255, 255, 0.96), rgba(250, 252, 253, 0.98)),
    var(--bg-card);
  overflow: hidden;
  box-shadow: 0 8px 20px rgba(15, 23, 42, 0.04);
}

.hero-bg {
  position: absolute;
  inset: 0;
  pointer-events: none;
  background:
    linear-gradient(90deg, rgba(14, 165, 233, 0.05), transparent 44%),
    linear-gradient(180deg, rgba(15, 23, 42, 0.03), transparent 55%);
}

.hero-card.tone-danger .hero-bg {
  background:
    linear-gradient(90deg, rgba(245, 63, 63, 0.08), transparent 46%),
    linear-gradient(180deg, rgba(15, 23, 42, 0.03), transparent 55%);
}

.hero-card.tone-warn .hero-bg {
  background:
    linear-gradient(90deg, rgba(250, 140, 22, 0.09), transparent 46%),
    linear-gradient(180deg, rgba(15, 23, 42, 0.03), transparent 55%);
}

.hero-row {
  position: relative;
  display: flex;
  justify-content: space-between;
  align-items: stretch;
  gap: 24px;
  padding: 26px 30px;
  flex-wrap: wrap;
}

.hero-left {
  flex: 1;
  min-width: 280px;
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.greet {
  display: inline-flex;
  align-items: center;
  font-size: 14px;
  color: var(--text-secondary);
  gap: 4px;
}

.greet strong {
  color: var(--text-primary);
  font-weight: 700;
}

.hero-title {
  font-size: 26px;
  font-weight: 750;
  color: var(--text-primary);
  letter-spacing: 0;
  line-height: 1.3;
  display: flex;
  align-items: center;
}

.hero-desc {
  font-size: 14px;
  color: var(--text-secondary);
  line-height: 1.7;
  max-width: 540px;
}

.hero-actions {
  margin-top: 8px;
}

.hero-btn {
  background: #f6fbfd !important;
  border-color: #d9ecf5 !important;
  color: var(--brand-primary-dark) !important;
  font-weight: 600;
  box-shadow: none;
}

.hero-btn:hover {
  background: var(--brand-primary-light) !important;
  border-color: var(--brand-primary) !important;
  color: var(--brand-primary-dark) !important;
  transform: translateY(-1px);
  box-shadow: 0 8px 18px rgba(14, 165, 233, 0.10);
}

.hero-right {
  display: flex;
  align-items: center;
  gap: 18px;
  flex-shrink: 0;
}

.weather-mini {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 12px 16px;
  background: #f7fafc;
  border: 1px solid var(--border-color);
  border-radius: 8px;
}

.w-icon {
  width: 36px;
  height: 36px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 8px;
  background: #eef6fb;
  color: var(--brand-primary);
  font-size: 22px;
  line-height: 1;
}

.w-temp {
  font-size: 22px;
  font-weight: 800;
  color: var(--text-primary);
  line-height: 1;
}

.w-desc {
  font-size: 11px;
  color: var(--text-secondary);
  margin-top: 4px;
}

.health-mini {
  position: relative;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 4px;
  padding: 10px 14px;
  background: #f7fafc;
  border: 1px solid var(--border-color);
  border-radius: 8px;
  cursor: pointer;
  transition: all 0.18s;
}

.health-mini:hover {
  transform: translateY(-2px);
  box-shadow: 0 6px 16px rgba(0, 0, 0, 0.06);
}

.hm-ring {
  position: relative;
  width: 60px;
  height: 60px;
}

.hm-svg {
  width: 100%;
  height: 100%;
}

.hm-num {
  position: absolute;
  inset: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  font-weight: 800;
  font-size: 18px;
  font-variant-numeric: tabular-nums;
}

.hm-label {
  font-size: 11px;
  color: var(--text-secondary);
}

/* === 今日提醒 === */
.tip-card {
  display: flex;
  align-items: center;
  gap: 16px;
  padding: 18px 22px;
  border-radius: 8px;
  background: var(--bg-card);
  border: 1px solid var(--border-color);
  box-shadow: 0 6px 16px rgba(15, 23, 42, 0.035);
  position: relative;
  overflow: hidden;
}

.tip-card::before {
  display: none;
}

.tip-icon {
  width: 44px;
  height: 44px;
  border-radius: 8px;
  background: #f7fafc;
  color: var(--brand-primary);
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  position: relative;
  border: 1px solid var(--border-color);
}

.tip-body {
  flex: 1;
  min-width: 0;
  position: relative;
}

.tip-label {
  font-size: 12px;
  font-weight: 700;
  color: var(--text-secondary);
  letter-spacing: 0;
  margin-bottom: 4px;
}

.tip-text {
  font-size: 15px;
  font-weight: 500;
  color: var(--text-primary);
  line-height: 1.6;
}

.tip-refresh {
  background: var(--bg-card);
  border: 1px solid var(--border-color);
  width: 36px;
  height: 36px;
  border-radius: 8px;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  transition: all 0.18s;
  color: var(--text-secondary);
  flex-shrink: 0;
}

.tip-refresh:hover:not(:disabled) {
  background: #f6fbfd;
  color: var(--brand-primary-dark);
  border-color: var(--brand-primary);
}

.tip-refresh:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

/* === 各 section === */
.section-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
}

.section-title {
  margin: 0;
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 16px;
  font-weight: 700;
  color: var(--text-primary);
}

.section-count {
  font-size: 12px;
  font-weight: 700;
  color: #fff;
  background: #f53f3f;
  border-radius: 999px;
  padding: 2px 10px;
  margin-left: 4px;
}

/* 临期 */
.expiring-rows {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
  gap: 10px;
}

.expiring-row {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 12px 14px;
  background: var(--bg-card);
  border: 1px solid var(--border-color);
  border-left-width: 3px;
  border-radius: 8px;
  transition: transform 0.15s, box-shadow 0.15s;
}

.expiring-row:hover {
  transform: translateX(2px);
  box-shadow: 0 6px 14px rgba(0, 0, 0, 0.06);
}

.expiring-row.danger { border-left-color: #f53f3f; }
.expiring-row.warn   { border-left-color: #fa8c16; }
.expiring-row.soon   { border-left-color: #fadb14; }

.exp-status {
  min-width: 42px;
  padding: 4px 8px;
  border-radius: 999px;
  background: #f7fafc;
  color: var(--text-secondary);
  font-size: 12px;
  font-weight: 700;
  text-align: center;
  flex-shrink: 0;
}

.exp-body {
  flex: 1;
  min-width: 0;
}

.exp-name {
  font-size: 14px;
  font-weight: 600;
  color: var(--text-primary);
  display: flex;
  align-items: center;
  gap: 6px;
}

.exp-brand {
  font-size: 11px;
  background: var(--brand-primary-light);
  color: var(--brand-primary-dark);
  padding: 1px 6px;
  border-radius: 6px;
}

.exp-days {
  font-size: 12px;
  color: var(--text-secondary);
  margin-top: 2px;
}

.exp-days strong {
  color: var(--text-primary);
}

.expiring-row.danger .exp-days strong { color: #f53f3f; }
.expiring-row.warn .exp-days strong { color: #fa8c16; }

/* 快捷入口 */
.quick-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(160px, 1fr));
  gap: 12px;
}

.quick-card {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 6px;
  padding: 16px 18px;
  background: var(--bg-card);
  border: 1px solid var(--border-color);
  border-radius: 8px;
  cursor: pointer;
  transition: all 0.2s;
  position: relative;
  overflow: hidden;
}

.quick-card::before {
  display: none;
}

.quick-card:hover {
  transform: translateY(-2px);
  box-shadow: 0 10px 22px rgba(15, 23, 42, 0.06);
  border-color: #bfd9e8;
}

.quick-card:hover::before {
  opacity: 0.5;
}

.qc-icon {
  width: 34px;
  height: 34px;
  display: flex;
  align-items: center;
  justify-content: center;
  margin-bottom: 4px;
  border-radius: 8px;
  background: #f7fafc;
  color: var(--brand-primary);
  font-size: 18px;
  position: relative;
}

.qc-title {
  font-size: 14px;
  font-weight: 700;
  color: var(--text-primary);
  position: relative;
}

.qc-desc {
  font-size: 11px;
  color: var(--text-secondary);
  position: relative;
}

/* 最近食谱 */
.recent-row {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(150px, 1fr));
  gap: 10px;
}

.recent-card {
  padding: 14px;
  background: var(--bg-card);
  border: 1px solid var(--border-color);
  border-radius: 8px;
  cursor: pointer;
  transition: all 0.18s;
}

.recent-card:hover {
  transform: translateY(-2px);
  border-color: #bfd9e8;
  box-shadow: 0 8px 18px rgba(15, 23, 42, 0.06);
}

.rc-name {
  font-size: 13px;
  font-weight: 600;
  color: var(--text-primary);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.rc-meta {
  display: flex;
  gap: 8px;
  margin-top: 4px;
  font-size: 11px;
  color: var(--text-placeholder);
}

/* 统计区 */
.stats-section {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 12px;
}

.stat-block {
  padding: 16px 20px;
  background: var(--bg-card);
  border: 1px solid var(--border-color);
  border-radius: 8px;
  text-align: center;
}

.sb-num {
  font-size: 28px;
  font-weight: 800;
  color: var(--text-primary);
  font-variant-numeric: tabular-nums;
  line-height: 1;
}

.sb-label {
  margin-top: 6px;
  font-size: 12px;
  color: var(--text-secondary);
}

@media (max-width: 1100px) {
  .hero-row { padding: 20px 22px; }
  .hero-title { font-size: 22px; }
  .hero-right { width: 100%; }
  .stats-section { grid-template-columns: repeat(2, 1fr); }
  .expiring-rows { grid-template-columns: 1fr; }
}
</style>
