<script setup lang="ts">
/**
 * 临期食材专属处理页：把"被动通知"变成"主动管理"。
 * 按"今天到期 / 明天 / 3 天内 / 7 天内 / 已过期"分组，每条食材右侧三个动作。
 */
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { getInventoryList, type InventoryItem } from '@/api/user/inventory'
import { useChatStore } from '@/stores/chat'
import { useInventoryWS, type InventoryWSEvent } from '@/composables/useInventoryWS'

const router = useRouter()
const chatStore = useChatStore()

const loading = ref(false)
const items = ref<InventoryItem[]>([])

async function fetchData() {
  loading.value = true
  try {
    items.value = await getInventoryList({ status: 'IN_STOCK' })
  } catch {
    ElMessage.error('加载失败')
  } finally {
    loading.value = false
  }
}

function getRemainDays(item: InventoryItem): number {
  const expireAt = item.agent_metadata?.expire_at
  if (!expireAt) return Number.POSITIVE_INFINITY
  return Math.ceil((new Date(expireAt).getTime() - Date.now()) / 86400000)
}

const groups = computed(() => {
  const expired: InventoryItem[] = []
  const today: InventoryItem[] = []
  const tomorrow: InventoryItem[] = []
  const within3: InventoryItem[] = []
  const within7: InventoryItem[] = []

  items.value.forEach(it => {
    const d = getRemainDays(it)
    if (!Number.isFinite(d)) return
    if (d < 0) expired.push(it)
    else if (d === 0) today.push(it)
    else if (d === 1) tomorrow.push(it)
    else if (d <= 3) within3.push(it)
    else if (d <= 7) within7.push(it)
  })
  return { expired, today, tomorrow, within3, within7 }
})

const totalToHandle = computed(() =>
  groups.value.expired.length +
  groups.value.today.length +
  groups.value.tomorrow.length +
  groups.value.within3.length
)

const totalAll = computed(() =>
  totalToHandle.value + groups.value.within7.length
)

// ---- 行动 ----
function askAi(item: InventoryItem) {
  chatStore.queuedMessage = `请用 ${item.category}${item.label_data?.brand ? '（' + item.label_data.brand + '）' : ''} 给我推荐 1 道菜，要简单快手，因为它快过期了`
  router.push('/user/chat')
}

function askAiBatch(itemsList: InventoryItem[]) {
  if (itemsList.length === 0) return
  const names = itemsList.slice(0, 8).map(i => i.category).join('、')
  chatStore.queuedMessage = `我冰箱里这些食材都快过期了：${names}。请用其中 2-3 样给我推荐 1-2 道菜。`
  router.push('/user/chat')
}

async function markUsed(item: InventoryItem) {
  // user 端没有改 inventory 的 API，让用户去找管理员或在 admin 端改
  // 这里只能提示；如果将来用户端也有写权限再补
  await ElMessageBox.confirm(
    `标记「${item.category}」已用掉？\n\n注：当前用户端为只读，标记功能需要管理员操作。下次我们让 AI 自动判断更准。`,
    '提示',
    { type: 'info', confirmButtonText: '我知道了', cancelButtonText: '取消' }
  ).catch(() => {})
}

// ---- WS 实时同步 ----
useInventoryWS({
  scope: 'user',
  onCreated: (it: InventoryWSEvent) => {
    if (it.status === 'IN_STOCK' && !items.value.some(i => i.id === it.id)) {
      items.value = [it as any, ...items.value]
    }
  },
  onUpdated: (it: InventoryWSEvent) => {
    const idx = items.value.findIndex(i => i.id === it.id)
    if (idx === -1) {
      if (it.status === 'IN_STOCK') items.value = [it as any, ...items.value]
    } else {
      if (it.status !== 'IN_STOCK') items.value.splice(idx, 1)
      else items.value.splice(idx, 1, it as any)
    }
  },
  onDeleted: (id: string) => {
    const idx = items.value.findIndex(i => i.id === id)
    if (idx !== -1) items.value.splice(idx, 1)
  },
})

onMounted(fetchData)
</script>

<template>
  <div v-loading="loading" class="expiring-page">
    <!-- 顶部 Hero -->
    <div class="hero">
      <div class="hero-left">
        <h1 class="hero-title">⏰ 临期食材</h1>
        <p class="hero-sub">本页只显示需要尽快处理的食材，按时间紧迫度排序</p>
      </div>
      <div class="hero-stats">
        <div class="hero-stat danger">
          <div class="hs-num">{{ groups.expired.length }}</div>
          <div class="hs-label">已过期</div>
        </div>
        <div class="hero-stat warn">
          <div class="hs-num">{{ groups.today.length + groups.tomorrow.length }}</div>
          <div class="hs-label">2 天内</div>
        </div>
        <div class="hero-stat caution">
          <div class="hs-num">{{ groups.within3.length }}</div>
          <div class="hs-label">3 天内</div>
        </div>
        <div class="hero-stat ok">
          <div class="hs-num">{{ groups.within7.length }}</div>
          <div class="hs-label">7 天内</div>
        </div>
      </div>
    </div>

    <!-- 进度条 -->
    <div v-if="totalAll > 0" class="progress-bar">
      <div class="progress-info">
        <strong>本周需要处理 {{ totalToHandle }} 件</strong>
        <span>· 共 {{ totalAll }} 件食材在临期窗口</span>
      </div>
      <div class="progress-track">
        <div
          class="progress-fill danger"
          :style="{ width: (groups.expired.length / totalAll * 100) + '%' }"
        ></div>
        <div
          class="progress-fill warn"
          :style="{ width: ((groups.today.length + groups.tomorrow.length) / totalAll * 100) + '%' }"
        ></div>
        <div
          class="progress-fill caution"
          :style="{ width: (groups.within3.length / totalAll * 100) + '%' }"
        ></div>
        <div
          class="progress-fill ok"
          :style="{ width: (groups.within7.length / totalAll * 100) + '%' }"
        ></div>
      </div>
    </div>

    <!-- 已过期 -->
    <div v-if="groups.expired.length > 0" class="bucket bucket-danger">
      <div class="bucket-head">
        <h3>❌ 已过期 <span class="bucket-count">{{ groups.expired.length }}</span></h3>
        <p>建议立刻清理或丢弃，避免占用冰箱空间</p>
      </div>
      <div class="bucket-grid">
        <div v-for="item in groups.expired" :key="item.id" class="item-card danger">
          <div class="ic-emoji">❌</div>
          <div class="ic-body">
            <div class="ic-name">{{ item.category }}</div>
            <div class="ic-meta">
              <span v-if="item.label_data?.brand">{{ item.label_data.brand }}</span>
              <span class="ic-days">已过期 <strong>{{ -getRemainDays(item) }}</strong> 天</span>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- 今天 -->
    <div v-if="groups.today.length > 0" class="bucket bucket-warn">
      <div class="bucket-head">
        <h3>🔥 今天到期 <span class="bucket-count">{{ groups.today.length }}</span></h3>
        <p>必须今晚做掉，再不吃就浪费了</p>
        <el-button v-if="groups.today.length > 1" link type="primary" size="small"
                   @click="askAiBatch(groups.today)">
          🤖 一次性问 AI 怎么用掉
        </el-button>
      </div>
      <div class="bucket-grid">
        <div v-for="item in groups.today" :key="item.id" class="item-card warn">
          <div class="ic-emoji">🔥</div>
          <div class="ic-body">
            <div class="ic-name">{{ item.category }}</div>
            <div class="ic-meta">
              <span v-if="item.label_data?.brand">{{ item.label_data.brand }}</span>
              <span class="ic-days"><strong>今天</strong>到期</span>
            </div>
          </div>
          <el-button type="primary" size="small" @click="askAi(item)">
            🤖 推荐做法
          </el-button>
        </div>
      </div>
    </div>

    <!-- 明天 -->
    <div v-if="groups.tomorrow.length > 0" class="bucket bucket-warn">
      <div class="bucket-head">
        <h3>⚡ 明天到期 <span class="bucket-count">{{ groups.tomorrow.length }}</span></h3>
        <p>提前规划好明天午晚餐</p>
        <el-button v-if="groups.tomorrow.length > 1" link type="primary" size="small"
                   @click="askAiBatch(groups.tomorrow)">
          🤖 一次性问 AI 怎么搭配
        </el-button>
      </div>
      <div class="bucket-grid">
        <div v-for="item in groups.tomorrow" :key="item.id" class="item-card warn">
          <div class="ic-emoji">⚡</div>
          <div class="ic-body">
            <div class="ic-name">{{ item.category }}</div>
            <div class="ic-meta">
              <span v-if="item.label_data?.brand">{{ item.label_data.brand }}</span>
              <span class="ic-days"><strong>明天</strong>到期</span>
            </div>
          </div>
          <el-button type="primary" size="small" @click="askAi(item)">
            🤖 推荐做法
          </el-button>
        </div>
      </div>
    </div>

    <!-- 3 天内 -->
    <div v-if="groups.within3.length > 0" class="bucket bucket-caution">
      <div class="bucket-head">
        <h3>⏰ 3 天内 <span class="bucket-count">{{ groups.within3.length }}</span></h3>
        <p>本周末前安排消耗，避免周一补货时还在冰箱</p>
        <el-button v-if="groups.within3.length > 1" link type="primary" size="small"
                   @click="askAiBatch(groups.within3)">
          🤖 让 AI 给本周饮食安排
        </el-button>
      </div>
      <div class="bucket-grid">
        <div v-for="item in groups.within3" :key="item.id" class="item-card caution">
          <div class="ic-emoji">⏰</div>
          <div class="ic-body">
            <div class="ic-name">{{ item.category }}</div>
            <div class="ic-meta">
              <span v-if="item.label_data?.brand">{{ item.label_data.brand }}</span>
              <span class="ic-days">还剩 <strong>{{ getRemainDays(item) }}</strong> 天</span>
            </div>
          </div>
          <el-button link type="primary" size="small" @click="askAi(item)">
            🤖 问 AI
          </el-button>
        </div>
      </div>
    </div>

    <!-- 7 天内 -->
    <div v-if="groups.within7.length > 0" class="bucket bucket-ok">
      <div class="bucket-head">
        <h3>📅 7 天内 <span class="bucket-count">{{ groups.within7.length }}</span></h3>
        <p>下周需要消耗的食材，可以提前规划</p>
      </div>
      <div class="bucket-grid">
        <div v-for="item in groups.within7" :key="item.id" class="item-card ok">
          <div class="ic-emoji">📅</div>
          <div class="ic-body">
            <div class="ic-name">{{ item.category }}</div>
            <div class="ic-meta">
              <span v-if="item.label_data?.brand">{{ item.label_data.brand }}</span>
              <span class="ic-days">还剩 <strong>{{ getRemainDays(item) }}</strong> 天</span>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- 全空 -->
    <div v-if="totalAll === 0 && !loading" class="empty-state">
      <div class="empty-emoji">🌱</div>
      <div class="empty-title">没有临期食材</div>
      <div class="empty-desc">冰箱里的食材都很新鲜，可以放心规划本周饮食</div>
      <el-button type="primary" size="large" @click="$router.push('/user/chat')">
        和 AI 聊聊吃什么
      </el-button>
    </div>
  </div>
</template>

<style scoped>
.expiring-page {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

/* Hero */
.hero {
  display: flex;
  align-items: center;
  justify-content: space-between;
  flex-wrap: wrap;
  gap: 16px;
  padding: 22px 26px;
  background: var(--bg-card);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-md);
  box-shadow: var(--shadow-sm);
}

.hero-title {
  margin: 0;
  font-size: 24px;
  font-weight: 800;
  color: var(--text-primary);
}

.hero-sub {
  margin: 4px 0 0 0;
  font-size: 13px;
  color: var(--text-secondary);
}

.hero-stats {
  display: flex;
  gap: 10px;
}

.hero-stat {
  text-align: center;
  padding: 10px 18px;
  border-radius: 12px;
  background: var(--bg-soft);
  min-width: 80px;
}

.hs-num {
  font-size: 24px;
  font-weight: 800;
  font-variant-numeric: tabular-nums;
  line-height: 1;
}

.hs-label {
  font-size: 11px;
  color: var(--text-secondary);
  margin-top: 4px;
}

.hero-stat.danger .hs-num { color: #f53f3f; }
.hero-stat.warn .hs-num   { color: #fa8c16; }
.hero-stat.caution .hs-num { color: #fadb14; }
.hero-stat.ok .hs-num     { color: var(--brand-primary-dark); }

/* Progress */
.progress-bar {
  padding: 14px 18px;
  background: var(--bg-card);
  border: 1px solid var(--border-color);
  border-radius: 12px;
}

.progress-info {
  font-size: 13px;
  color: var(--text-secondary);
  margin-bottom: 8px;
}

.progress-info strong {
  color: var(--text-primary);
  font-weight: 700;
}

.progress-track {
  display: flex;
  height: 8px;
  border-radius: 4px;
  overflow: hidden;
  background: var(--bg-soft);
}

.progress-fill { height: 100%; }
.progress-fill.danger { background: #f53f3f; }
.progress-fill.warn   { background: #fa8c16; }
.progress-fill.caution { background: #fadb14; }
.progress-fill.ok     { background: var(--brand-primary); }

/* Bucket */
.bucket {
  background: var(--bg-card);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-md);
  padding: 18px 22px;
}

.bucket.bucket-danger { border-left: 4px solid #f53f3f; }
.bucket.bucket-warn   { border-left: 4px solid #fa8c16; }
.bucket.bucket-caution { border-left: 4px solid #fadb14; }
.bucket.bucket-ok     { border-left: 4px solid var(--brand-primary); }

.bucket-head {
  margin-bottom: 12px;
}

.bucket-head h3 {
  margin: 0;
  font-size: 16px;
  font-weight: 700;
  color: var(--text-primary);
  display: flex;
  align-items: center;
  gap: 4px;
}

.bucket-count {
  font-size: 12px;
  font-weight: 700;
  color: var(--text-secondary);
  background: var(--bg-soft);
  padding: 2px 10px;
  border-radius: 999px;
  margin-left: 6px;
}

.bucket-head p {
  margin: 4px 0 6px;
  font-size: 12px;
  color: var(--text-secondary);
}

/* Item Card */
.bucket-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
  gap: 10px;
}

.item-card {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 12px 14px;
  background: var(--bg-soft);
  border-radius: 10px;
  transition: all 0.18s;
}

.item-card:hover {
  background: var(--bg-card);
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.06);
  transform: translateY(-1px);
}

.ic-emoji {
  font-size: 20px;
  line-height: 1;
  flex-shrink: 0;
}

.ic-body {
  flex: 1;
  min-width: 0;
}

.ic-name {
  font-size: 14px;
  font-weight: 600;
  color: var(--text-primary);
}

.ic-meta {
  font-size: 12px;
  color: var(--text-secondary);
  margin-top: 2px;
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}

.ic-days strong {
  font-weight: 700;
  color: var(--text-primary);
}

.item-card.danger .ic-days strong { color: #f53f3f; }
.item-card.warn .ic-days strong { color: #fa8c16; }
.item-card.caution .ic-days strong { color: #fa8c16; }

/* 空态 */
.empty-state {
  text-align: center;
  padding: 80px 20px;
  background: var(--bg-card);
  border-radius: var(--radius-md);
  border: 1px solid var(--border-color);
}

.empty-emoji {
  font-size: 64px;
  margin-bottom: 16px;
}

.empty-title {
  font-size: 22px;
  font-weight: 700;
  color: var(--text-primary);
}

.empty-desc {
  font-size: 14px;
  color: var(--text-secondary);
  margin: 8px 0 24px;
}

@media (max-width: 1100px) {
  .hero { flex-direction: column; align-items: flex-start; }
  .hero-stats { width: 100%; }
}
</style>
