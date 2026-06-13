<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import { ElMessage } from 'element-plus'
import { getPreferences, addPreference, deletePreference, type PreferenceItem } from '@/api/user/agent'
import { useUserAuthStore } from '@/stores/userAuth'
import { showUndoToast } from '@/composables/useUndoToast'

const authStore = useUserAuthStore()
const loading = ref(false)
const items = ref<PreferenceItem[]>([])
const showSetupDialog = ref(false)
const setupLoading = ref(false)

interface PrefGroup {
  label: string
  key: string
  color: string
  bgSoft: string
  emoji: string
  icon: string
  desc: string
  options: string[]
}

const prefOptions: PrefGroup[] = [
  {
    label: '口味偏好',
    key: 'taste',
    color: '#f97316',
    bgSoft: 'rgba(249, 115, 22, 0.08)',
    emoji: '味',
    icon: 'MagicStick',
    desc: '常吃、常点的味型',
    options: ['偏辣', '偏甜', '偏咸', '偏酸', '清淡', '重口味'],
  },
  {
    label: '过敏忌口',
    key: 'allergy',
    color: '#ef4444',
    bgSoft: 'rgba(239, 68, 68, 0.08)',
    emoji: '忌',
    icon: 'Warning',
    desc: '严格禁止出现的食材',
    options: ['花生过敏', '海鲜过敏', '牛奶过敏', '鸡蛋过敏', '麸质过敏', '大豆过敏'],
  },
  {
    label: '不吃',
    key: 'dislike',
    color: '#a855f7',
    bgSoft: 'rgba(168, 85, 247, 0.08)',
    emoji: '避',
    icon: 'CloseBold',
    desc: '不爱吃但不致敏的',
    options: ['不吃葱', '不吃蒜', '不吃香菜', '不吃内脏', '不吃辣', '不吃生食'],
  },
  {
    label: '饮食方式',
    key: 'prefer',
    color: '#10b981',
    bgSoft: 'rgba(14, 165, 233, 0.08)',
    emoji: '餐',
    icon: 'CircleCheck',
    desc: '正在执行的饮食习惯',
    options: ['素食', '低碳水', '低脂', '高蛋白', '生酮', '无糖'],
  },
]

const pendingSelections = ref<Record<string, string[]>>({})
prefOptions.forEach(g => { pendingSelections.value[g.key] = [] })

const customInput = ref<Record<string, string>>({})
prefOptions.forEach(g => { customInput.value[g.key] = '' })

function isPendingChecked(key: string, value: string): boolean {
  return pendingSelections.value[key]?.includes(value) || false
}

function togglePending(key: string, value: string) {
  const list = pendingSelections.value[key]
  const idx = list.indexOf(value)
  if (idx >= 0) {
    list.splice(idx, 1)
  } else {
    list.push(value)
  }
}

function addPendingCustom(key: string) {
  const value = customInput.value[key]?.trim()
  if (!value) return
  if (pendingSelections.value[key].includes(value)) {
    ElMessage.info('已添加该选项')
    return
  }
  pendingSelections.value[key].push(value)
  customInput.value[key] = ''
}

function removePendingCustom(key: string, value: string) {
  const list = pendingSelections.value[key]
  const idx = list.indexOf(value)
  if (idx >= 0) list.splice(idx, 1)
}

async function fetchPreferences() {
  loading.value = true
  try {
    items.value = await getPreferences()
  } catch (e) {
    console.error(e)
  } finally {
    loading.value = false
  }
}

function openSetupDialog() {
  prefOptions.forEach(g => {
    pendingSelections.value[g.key] = items.value
      .filter(i => i.preference_key === g.key)
      .map(i => i.preference_value)
  })
  customInput.value = {}
  prefOptions.forEach(g => { customInput.value[g.key] = '' })
  showSetupDialog.value = true
}

async function savePreferences() {
  setupLoading.value = true
  try {
    for (const group of prefOptions) {
      const key = group.key
      const current = items.value.filter(i => i.preference_key === key).map(i => i.preference_value)
      const pending = pendingSelections.value[key] || []

      const toAdd = pending.filter(v => !current.includes(v))
      for (const value of toAdd) {
        const saved = await addPreference({ preference_key: key, preference_value: value })
        items.value.push(saved)
      }

      const toRemove = items.value.filter(i => i.preference_key === key && !pending.includes(i.preference_value))
      for (const item of toRemove) {
        await deletePreference(item.id)
        items.value = items.value.filter(i => i.id !== item.id)
      }
    }
    showSetupDialog.value = false
    ElMessage.success('偏好设置已保存')
  } catch (e) {
    ElMessage.error('保存失败，请重试')
  } finally {
    setupLoading.value = false
  }
}

async function handleDelete(item: PreferenceItem) {
  try {
    await deletePreference(item.id)
    items.value = items.value.filter(i => i.id !== item.id)
    showUndoToast({
      message: `已删除偏好「${item.preference_value}」`,
      duration: 6,
      onUndo: async () => {
        try {
          const restored = await addPreference({
            preference_key: item.preference_key,
            preference_value: item.preference_value,
          })
          items.value = [restored, ...items.value]
          ElMessage.success('已恢复')
        } catch {
          ElMessage.error('恢复失败')
        }
      },
    })
  } catch (e) {
    ElMessage.error('删除失败')
  }
}

// 统计
const aiLearnedCount = computed(() => items.value.filter(i => i.source === 'chat').length)
const manualCount = computed(() => items.value.length - aiLearnedCount.value)
const filledGroups = computed(() =>
  prefOptions.filter(g => items.value.some(i => i.preference_key === g.key)).length
)

// 对话学习类（不在预设分组内的）
const chatLearnedItems = computed(() =>
  items.value.filter(i => i.source === 'chat' && !prefOptions.some(g => g.key === i.preference_key))
)

function groupItems(key: string) {
  return items.value.filter(i => i.preference_key === key)
}

onMounted(fetchPreferences)
</script>

<template>
  <div class="pref-page">
    <!-- 顶部概览 -->
    <div class="hero-card">
      <div class="hero-inner">
        <div class="hero-left">
          <div class="hero-icon">
            <span>偏</span>
          </div>
          <div>
            <div class="hero-title">饮食偏好</div>
            <div class="hero-sub">
              <strong>{{ authStore.user?.username || '--' }}</strong>
              <span>共 {{ items.length }} 项</span>
              <span v-if="aiLearnedCount > 0" class="hero-badge ai">
                来自对话 {{ aiLearnedCount }} 项
              </span>
            </div>
          </div>
        </div>
        <el-button
          type="primary"
          size="large"
          @click="openSetupDialog"
          class="hero-btn"
        >
          <el-icon><Edit /></el-icon>
          {{ items.length > 0 ? '编辑' : '开始设置' }}
        </el-button>
      </div>
    </div>

    <!-- 数据统计行 -->
    <div v-if="items.length > 0" class="kpi-row">
      <div class="kpi-card">
        <div>
          <div class="kpi-num">{{ items.length }}</div>
          <div class="kpi-lbl">偏好项</div>
        </div>
      </div>
      <div class="kpi-card">
        <div>
          <div class="kpi-num">{{ filledGroups }} <span class="kpi-of">/ 4</span></div>
          <div class="kpi-lbl">已填分类</div>
        </div>
      </div>
      <div class="kpi-card">
        <div>
          <div class="kpi-num">{{ manualCount }}</div>
          <div class="kpi-lbl">手动添加</div>
        </div>
      </div>
      <div class="kpi-card">
        <div>
          <div class="kpi-num">{{ aiLearnedCount }}</div>
          <div class="kpi-lbl">来自对话</div>
        </div>
      </div>
    </div>

    <!-- 偏好分组卡片 -->
    <div v-loading="loading">
      <div v-if="items.length > 0" class="pref-grid">
        <div
          v-for="group in prefOptions"
          :key="group.key"
          class="pref-card"
          :class="{ 'is-empty-group': groupItems(group.key).length === 0 }"
          :style="{ '--group-color': group.color, '--group-soft': group.bgSoft } as any"
        >
          <div class="pref-card-stripe"></div>
          <div class="pref-card-header">
            <div class="pref-card-icon">
              <span>{{ group.emoji }}</span>
            </div>
            <div class="pref-card-meta">
              <div class="pref-card-title">{{ group.label }}</div>
              <div class="pref-card-desc">{{ group.desc }}</div>
            </div>
            <span class="pref-card-count">{{ groupItems(group.key).length }}</span>
          </div>

          <div v-if="groupItems(group.key).length === 0" class="pref-empty-group">
            <span style="opacity: 0.5">暂无</span>
            <el-button link size="small" @click="openSetupDialog">+ 添加</el-button>
          </div>
          <div v-else class="pref-tags">
            <div
              v-for="item in groupItems(group.key)"
              :key="item.id"
              class="pref-tag"
            >
              <span>{{ item.preference_value }}</span>
              <span v-if="item.source === 'chat'" class="pref-tag-ai" title="来自对话记录">对话</span>
              <el-icon class="pref-tag-del" @click="handleDelete(item)"><Close /></el-icon>
            </div>
          </div>
        </div>

        <!-- 对话补充的、不在预设分组内的偏好 -->
        <div
          v-if="chatLearnedItems.length > 0"
          class="pref-card chat-card"
          :style="{ '--group-color': '#64748b', '--group-soft': 'rgba(100,116,139,0.08)' } as any"
        >
          <div class="pref-card-stripe"></div>
          <div class="pref-card-header">
            <div class="pref-card-icon">
              <span>记</span>
            </div>
            <div class="pref-card-meta">
              <div class="pref-card-title">对话补充</div>
              <div class="pref-card-desc">从日常提问里整理出的额外偏好</div>
            </div>
            <span class="pref-card-count">{{ chatLearnedItems.length }}</span>
          </div>
          <div class="pref-tags">
            <div v-for="item in chatLearnedItems" :key="item.id" class="pref-tag">
              <span>{{ item.preference_value }}</span>
              <span class="pref-tag-ai">对话</span>
              <el-icon class="pref-tag-del" @click="handleDelete(item)"><Close /></el-icon>
            </div>
          </div>
        </div>
      </div>

      <!-- 空状态 -->
      <div v-else-if="!loading" class="empty-pref">
        <p class="empty-title">还没有设置饮食偏好</p>
        <p class="empty-desc">先记录口味、忌口和饮食方式，后面推荐食谱时会更合你的胃口。</p>
        <div class="empty-features">
          <div class="empty-feature">
            <span>口味偏好</span>
          </div>
          <div class="empty-feature">
            <span>过敏忌口</span>
          </div>
          <div class="empty-feature">
            <span>不爱吃的</span>
          </div>
          <div class="empty-feature">
            <span>饮食方式</span>
          </div>
        </div>
        <el-button type="primary" size="large" @click="openSetupDialog" class="empty-cta">
          <el-icon><Plus /></el-icon> 立即设置
        </el-button>
      </div>
    </div>

    <!-- 设置偏好弹窗 -->
    <el-dialog
      v-model="showSetupDialog"
      title="设置饮食偏好"
      width="600px"
      :close-on-click-modal="false"
      class="setup-dialog"
    >
      <div class="setup-dialog-body">
        <p class="setup-tip">
          <el-icon :size="13"><InfoFilled /></el-icon>
          勾选符合你的偏好。也可以输入自定义内容（按 Enter 添加）。
        </p>
        <div
          v-for="group in prefOptions"
          :key="group.key"
          class="setup-group"
          :style="{ '--group-color': group.color, '--group-soft': group.bgSoft } as any"
        >
          <div class="setup-group-header">
            <div class="setup-group-icon">
              <span>{{ group.emoji }}</span>
            </div>
            <div>
              <div class="setup-group-label">{{ group.label }}</div>
              <div class="setup-group-desc">{{ group.desc }}</div>
            </div>
            <span class="setup-group-count">
              已选 {{ pendingSelections[group.key]?.length || 0 }}
            </span>
          </div>
          <div class="option-grid">
            <div
              v-for="opt in group.options"
              :key="opt"
              :class="['option-chip', { checked: isPendingChecked(group.key, opt) }]"
              @click="togglePending(group.key, opt)"
            >
              <el-icon v-if="isPendingChecked(group.key, opt)" :size="13" style="margin-right: 4px"><Check /></el-icon>
              {{ opt }}
            </div>
          </div>
          <div class="custom-row">
            <el-input
              v-model="customInput[group.key]"
              placeholder="自定义偏好…"
              size="small"
              style="width: 200px"
              @keyup.enter="addPendingCustom(group.key)"
            >
              <template #append>
                <el-button size="small" @click="addPendingCustom(group.key)">
                  <el-icon><Plus /></el-icon>
                </el-button>
              </template>
            </el-input>
          </div>
          <div v-if="pendingSelections[group.key]?.filter(v => !group.options.includes(v)).length" class="custom-tags">
            <div
              v-for="val in pendingSelections[group.key].filter(v => !group.options.includes(v))"
              :key="val"
              class="custom-tag"
            >
              {{ val }}
              <el-icon :size="12" style="cursor: pointer; margin-left: 2px" @click="removePendingCustom(group.key, val)"><Close /></el-icon>
            </div>
          </div>
        </div>
      </div>
      <template #footer>
        <el-button @click="showSetupDialog = false">取消</el-button>
        <el-button type="primary" :loading="setupLoading" @click="savePreferences">保存偏好</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped>
.pref-page {
  display: flex;
  flex-direction: column;
  gap: 14px;
}

/* === 顶部概览 === */
.hero-card {
  position: relative;
  border-radius: 8px;
  overflow: hidden;
  background: var(--bg-card);
  border: 1px solid var(--border-color);
}

.hero-bg {
  display: none;
}

.hero-inner {
  position: relative;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  padding: 20px 24px;
  flex-wrap: wrap;
}

.hero-left {
  display: flex;
  align-items: center;
  gap: 14px;
}

.hero-icon {
  width: 46px;
  height: 46px;
  border-radius: 8px;
  background: var(--bg-soft);
  border: 1px solid var(--border-color);
  color: var(--text-secondary);
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 15px;
  font-weight: 700;
}

.hero-title {
  font-size: 22px;
  font-weight: 800;
  color: var(--text-primary);
  letter-spacing: 0;
  line-height: 1.2;
}

.hero-sub {
  font-size: 13px;
  color: var(--text-secondary);
  margin-top: 4px;
  display: inline-flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 6px;
}

.hero-sub strong {
  color: var(--text-primary);
  font-weight: 700;
}

.hero-badge {
  display: inline-flex;
  align-items: center;
  padding: 2px 8px;
  border-radius: 999px;
  font-size: 11px;
  font-weight: 600;
}

.hero-badge.ai {
  background: var(--bg-soft);
  color: var(--text-secondary);
}

.hero-btn {
  font-weight: 600;
  border-radius: 8px;
}

.hero-btn:hover {
  transform: none;
}

/* === KPI === */
.kpi-row {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 10px;
}

.kpi-card {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 14px 16px;
  background: var(--bg-card);
  border-radius: 8px;
  border: 1px solid var(--border-color);
}

.kpi-num {
  font-size: 21px;
  font-weight: 800;
  color: var(--text-primary);
  line-height: 1.1;
  font-variant-numeric: tabular-nums;
}

.kpi-of {
  font-size: 14px;
  color: var(--text-placeholder);
  font-weight: 500;
}

.kpi-lbl {
  font-size: 12px;
  color: var(--text-secondary);
  margin-top: 2px;
}

/* === 偏好分组卡片 === */
.pref-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 12px;
}

.pref-card {
  position: relative;
  padding: 16px 18px;
  border-radius: 8px;
  background: var(--bg-card);
  border: 1px solid var(--border-color);
  transition: border-color 0.18s, box-shadow 0.18s;
  overflow: hidden;
}

.pref-card:hover {
  box-shadow: 0 8px 18px rgba(15, 23, 42, 0.05);
  border-color: var(--border-color);
}

.pref-card.is-empty-group {
  opacity: 0.85;
}

.pref-card-stripe {
  position: absolute;
  top: 0;
  left: 0;
  bottom: 0;
  width: 3px;
  background: var(--group-color);
  opacity: 0.75;
}

.pref-card-header {
  display: flex;
  align-items: center;
  gap: 12px;
  padding-left: 6px;
  margin-bottom: 14px;
}

.pref-card-icon {
  width: 38px;
  height: 38px;
  border-radius: 8px;
  background: var(--group-soft);
  color: var(--group-color);
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  font-size: 14px;
  font-weight: 800;
}

.pref-card-meta {
  flex: 1;
  min-width: 0;
}

.pref-card-title {
  font-size: 16px;
  font-weight: 700;
  color: var(--text-primary);
  line-height: 1.2;
}

.pref-card-desc {
  font-size: 11px;
  color: var(--text-placeholder);
  margin-top: 2px;
}

.pref-card-count {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-width: 24px;
  height: 24px;
  padding: 0 8px;
  border-radius: 999px;
  background: var(--bg-soft);
  color: var(--text-secondary);
  font-size: 12px;
  font-weight: 700;
}

.pref-empty-group {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 12px 6px;
  font-size: 13px;
  color: var(--text-placeholder);
}

.pref-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  padding-left: 6px;
}

.pref-tag {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 6px 10px;
  border-radius: 8px;
  background: var(--bg-soft);
  color: var(--text-primary);
  font-size: 13px;
  font-weight: 600;
  border: 1px solid var(--border-color);
  transition: border-color 0.18s, background 0.18s;
}

.pref-tag:hover {
  border-color: var(--group-color);
  background: var(--group-soft);
}

.pref-tag-ai {
  font-size: 11px;
  padding: 1px 6px;
  border-radius: 4px;
  background: var(--bg-card);
  border: 1px solid var(--border-color);
  color: var(--text-secondary);
  font-weight: 600;
  letter-spacing: 0;
}

.pref-tag-del {
  cursor: pointer;
  color: currentColor;
  opacity: 0.4;
  transition: opacity 0.18s;
  margin-left: -2px;
}

.pref-tag-del:hover {
  opacity: 1;
  color: #ef4444 !important;
}

/* === 空态 === */
.empty-pref {
  position: relative;
  text-align: left;
  padding: 30px;
  background: var(--bg-card);
  border-radius: 8px;
  border: 1px solid var(--border-color);
  overflow: hidden;
}

.empty-title {
  position: relative;
  font-size: 18px;
  font-weight: 700;
  color: var(--text-primary);
  margin-bottom: 8px;
}

.empty-desc {
  position: relative;
  font-size: 14px;
  color: var(--text-secondary);
  max-width: 520px;
  margin: 0 0 20px;
  line-height: 1.6;
}

.empty-features {
  position: relative;
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-bottom: 24px;
}

.empty-feature {
  display: inline-flex;
  align-items: center;
  padding: 6px 12px;
  border-radius: 8px;
  background: var(--bg-soft);
  border: 1px solid var(--border-color);
  font-size: 12px;
  color: var(--text-secondary);
  font-weight: 500;
}

.empty-cta {
  position: relative;
  border-radius: 8px;
  padding: 11px 22px;
  font-weight: 600;
}

.empty-cta:hover {
  transform: none;
}

/* === 弹窗 === */
.setup-dialog-body {
  max-height: 64vh;
  overflow-y: auto;
  padding-right: 8px;
}

.setup-tip {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
  color: var(--text-secondary);
  margin-bottom: 18px;
  padding: 8px 14px;
  background: var(--bg-soft);
  border: 1px solid var(--border-color);
  border-radius: 8px;
  width: 100%;
}

.setup-group {
  position: relative;
  margin-bottom: 14px;
  padding: 16px;
  border-radius: 8px;
  border: 1px solid var(--border-color);
  background: var(--bg-card);
  transition: border-color 0.18s;
}

.setup-group:hover {
  border-color: var(--group-color);
}

.setup-group:last-child {
  margin-bottom: 0;
}

.setup-group-header {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 12px;
}

.setup-group-icon {
  width: 32px;
  height: 32px;
  border-radius: 8px;
  background: var(--group-soft);
  color: var(--group-color);
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 13px;
  font-weight: 800;
}

.setup-group-label {
  font-size: 14px;
  font-weight: 700;
  color: var(--text-primary);
}

.setup-group-desc {
  font-size: 11px;
  color: var(--text-placeholder);
  margin-top: 1px;
}

.setup-group-count {
  margin-left: auto;
  font-size: 11px;
  font-weight: 600;
  color: var(--text-secondary);
  padding: 2px 10px;
  border-radius: 999px;
  background: var(--bg-soft);
}

.option-grid {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.option-chip {
  display: inline-flex;
  align-items: center;
  padding: 6px 14px;
  border-radius: 8px;
  border: 1px solid var(--border-color);
  background: var(--bg-card);
  font-size: 13px;
  color: var(--text-secondary);
  cursor: pointer;
  transition: all 0.18s;
  user-select: none;
}

.option-chip:hover {
  border-color: var(--group-color);
  color: var(--text-primary);
  background: var(--group-soft);
}

.option-chip.checked {
  border-color: var(--group-color);
  color: var(--text-primary);
  background: var(--group-soft);
  font-weight: 600;
}

.custom-row {
  margin-top: 12px;
}

.custom-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin-top: 10px;
}

.custom-tag {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 4px 12px;
  border-radius: 8px;
  background: var(--bg-soft);
  color: var(--text-primary);
  font-size: 12px;
  font-weight: 600;
  border: 1px solid var(--border-color);
}

@media (max-width: 1100px) {
  .pref-grid { grid-template-columns: 1fr; }
  .kpi-row { grid-template-columns: repeat(2, 1fr); }
  .hero-inner { padding: 18px 20px; }
}
</style>
