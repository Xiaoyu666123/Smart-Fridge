<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { use } from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import { HeatmapChart } from 'echarts/charts'
import {
  TooltipComponent, VisualMapComponent, CalendarComponent,
} from 'echarts/components'
import VChart from 'vue-echarts'
import {
  listSavedRecipes, deleteSavedRecipe, cookRecipe, saveRecipe, updateRecipeMeta,
  type SavedRecipe,
} from '@/api/user/agent'
import { getCookingCalendar, type CookingCalendar } from '@/api/user/nutrition'
import { getInventoryList, type InventoryItem } from '@/api/user/inventory'
import RecipeCard from '@/components/RecipeCard.vue'
import { showUndoToast } from '@/composables/useUndoToast'
import { useChartTheme } from '@/composables/useChartTheme'

use([CanvasRenderer, HeatmapChart, TooltipComponent, VisualMapComponent, CalendarComponent])

const chartTheme = useChartTheme()

const loading = ref(false)
const recipes = ref<SavedRecipe[]>([])
const filterTag = ref('')

// ---- Tab + 烹饪日历 ----
const activeTab = ref<'list' | 'calendar'>('list')
const calendar = ref<CookingCalendar | null>(null)
const calendarLoading = ref(false)
const calendarRange = ref(365)
const selectedDay = ref<{ date: string; count: number; names: string[] } | null>(null)

async function fetchCalendar() {
  calendarLoading.value = true
  try {
    calendar.value = await getCookingCalendar(calendarRange.value)
  } catch {
    ElMessage.error('加载烹饪日历失败')
  } finally {
    calendarLoading.value = false
  }
}

function handleTabChange(name: string | number) {
  if (name === 'calendar' && !calendar.value) {
    fetchCalendar()
  }
}

const calendarOption = computed(() => {
  const c = calendar.value
  if (!c) return {}
  return {
    tooltip: {
      formatter: (params: any) => {
        const [d, v, names] = params.data
        if (!v) return `${d}<br/>没有打卡`
        const list = (names as string[]).slice(0, 3).join('、')
        const more = (names as string[]).length > 3 ? ` 等 ${(names as string[]).length} 道` : ''
        return `${d}<br/>打卡 <b>${v}</b> 道菜<br/>${list}${more}`
      },
    },
    visualMap: {
      min: 0,
      max: Math.max(c.max_per_day || 1, 4),
      calculable: false,
      orient: 'horizontal',
      left: 'center',
      bottom: 0,
      itemWidth: 14,
      itemHeight: 12,
      textStyle: { fontSize: 11, color: '#86909c' },
      inRange: {
        color: ['#ebedf0', '#9be9a8', '#40c463', '#30a14e', '#216e39'],
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

function handleCalendarClick(params: any) {
  if (!params || !params.data) return
  const [date, count, names] = params.data
  if (!count) {
    selectedDay.value = null
    return
  }
  selectedDay.value = { date, count, names: names || [] }
}

// ---- 打卡弹窗 ----
const cookDialog = ref({
  visible: false,
  recipe: null as SavedRecipe | null,
  inStockItems: [] as InventoryItem[],
  selectedIds: [] as string[],
  loading: false,
})

async function fetchRecipes() {
  loading.value = true
  try {
    recipes.value = await listSavedRecipes(100)
  } catch {
    ElMessage.error('加载收藏失败')
  } finally {
    loading.value = false
  }
}

const allTags = computed(() => {
  const set = new Set<string>()
  recipes.value.forEach(r => (r.tags || []).forEach(t => set.add(t)))
  return Array.from(set)
})

const filteredRecipes = computed(() => {
  if (!filterTag.value) return recipes.value
  return recipes.value.filter(r => (r.tags || []).includes(filterTag.value))
})

const stats = computed(() => {
  const total = recipes.value.length
  const totalCooks = recipes.value.reduce((s, r) => s + (r.cooked_count || 0), 0)
  const cookedCount = recipes.value.filter(r => (r.cooked_count || 0) > 0).length
  return { total, totalCooks, cookedCount }
})

function similar(a: string, b: string): boolean {
  if (!a || !b) return false
  const al = a.toLowerCase()
  const bl = b.toLowerCase()
  return al.includes(bl) || bl.includes(al)
}

async function openCookDialog(r: SavedRecipe) {
  cookDialog.value.recipe = r
  cookDialog.value.selectedIds = []
  cookDialog.value.visible = true
  cookDialog.value.loading = true
  try {
    const all = await getInventoryList({ status: 'IN_STOCK' })
    cookDialog.value.inStockItems = all
    // 自动勾选：库存 category 与食谱 ingredient.name 模糊匹配
    const ingNames = (r.ingredients || []).map(i => i.name || '').filter(Boolean)
    const auto: string[] = []
    for (const item of all) {
      if (ingNames.some(n => similar(item.category, n))) {
        auto.push(item.id)
      }
    }
    cookDialog.value.selectedIds = auto
  } catch {
    cookDialog.value.inStockItems = []
  } finally {
    cookDialog.value.loading = false
  }
}

async function handleCookConfirm() {
  const r = cookDialog.value.recipe
  if (!r) return
  try {
    const result = await cookRecipe(r.id, cookDialog.value.selectedIds)
    const idx = recipes.value.findIndex(x => x.id === r.id)
    if (idx >= 0) recipes.value[idx] = result.recipe
    cookDialog.value.visible = false
    if (result.consumed_count > 0) {
      ElMessage.success(`✓ 已打卡，消耗了 ${result.consumed_count} 项库存`)
    } else {
      ElMessage.success(`✓ 已打卡 ${result.recipe.cooked_count} 次`)
    }
  } catch {
    ElMessage.error('打卡失败')
  }
}

function getRemainDays(item: InventoryItem): number {
  const expireAt = item.agent_metadata?.expire_at
  if (!expireAt) return Number.POSITIVE_INFINITY
  return Math.ceil((new Date(expireAt).getTime() - Date.now()) / 86400000)
}

function ingredientList(): string {
  const ings = cookDialog.value.recipe?.ingredients || []
  return ings.map(i => `${i.name}${i.amount ? ' · ' + i.amount : ''}`).join('、')
}

async function handleDelete(r: SavedRecipe) {
  try {
    await ElMessageBox.confirm(`确定移除「${r.name}」？`, '取消收藏', {
      confirmButtonText: '取消收藏', cancelButtonText: '保留', type: 'warning',
    })
    // 缓存数据用于撤销
    const payload = {
      name: r.name, summary: r.summary || '',
      prep_time: r.prep_time, difficulty: r.difficulty,
      ingredients: r.ingredients || undefined,
      steps: r.steps || undefined,
      tags: r.tags || undefined,
    }
    await deleteSavedRecipe(r.id)
    recipes.value = recipes.value.filter(x => x.id !== r.id)

    showUndoToast({
      message: `已取消收藏「${r.name}」`,
      duration: 6,
      onUndo: async () => {
        try {
          const restored = await saveRecipe(payload as any)
          recipes.value = [restored, ...recipes.value]
          ElMessage.success('已恢复收藏')
        } catch {
          ElMessage.error('恢复失败')
        }
      },
    })
  } catch (e) {
    if (e === 'cancel') return
    ElMessage.error('操作失败')
  }
}

function formatDate(s: string | null) {
  if (!s) return '从未'
  return new Date(s).toLocaleDateString('zh-CN')
}

// ---- 评分 / 笔记 ----
const noteDialog = ref({
  visible: false,
  recipe: null as SavedRecipe | null,
  notes: '',
  saving: false,
})

async function handleRating(r: SavedRecipe, rating: number) {
  // 同一个值再点一次 = 取消评分
  const target = r.rating === rating ? null : rating
  try {
    if (target === null) {
      // 后端不支持把 rating 清回 null（schema 里是 ge=1），所以仅前端把 rating 0 视作"无评分"
      // 简单做法：发 1 起步，或干脆不允许取消。这里改成"必须 1-5"，重复点同值也保持。
      r.rating = rating
      await updateRecipeMeta(r.id, { rating })
    } else {
      const updated = await updateRecipeMeta(r.id, { rating: target })
      const idx = recipes.value.findIndex(x => x.id === r.id)
      if (idx !== -1) recipes.value[idx] = updated
      ElMessage.success(`已评分 ${target} 星`)
    }
  } catch {
    ElMessage.error('评分失败')
  }
}

function openNoteDialog(r: SavedRecipe) {
  noteDialog.value.recipe = r
  noteDialog.value.notes = r.notes || ''
  noteDialog.value.visible = true
}

async function saveNote() {
  const r = noteDialog.value.recipe
  if (!r) return
  noteDialog.value.saving = true
  try {
    const updated = await updateRecipeMeta(r.id, { notes: noteDialog.value.notes })
    const idx = recipes.value.findIndex(x => x.id === r.id)
    if (idx !== -1) recipes.value[idx] = updated
    ElMessage.success('笔记已保存')
    noteDialog.value.visible = false
  } catch {
    ElMessage.error('保存失败')
  } finally {
    noteDialog.value.saving = false
  }
}

onMounted(fetchRecipes)
</script>

<template>
  <div>
    <!-- 顶部统计 -->
    <div class="stat-row">
      <div class="stat-card">
        <div class="stat-icon" style="background: var(--brand-primary-light); color: var(--brand-primary-dark)">
          <el-icon :size="22"><StarFilled /></el-icon>
        </div>
        <div>
          <div class="stat-value">{{ stats.total }}</div>
          <div class="stat-label">收藏食谱</div>
        </div>
      </div>
      <div class="stat-card">
        <div class="stat-icon" style="background: #eef2ff; color: #6366f1">
          <el-icon :size="22"><Bowl /></el-icon>
        </div>
        <div>
          <div class="stat-value">{{ stats.totalCooks }}</div>
          <div class="stat-label">累计打卡次数</div>
        </div>
      </div>
      <div class="stat-card">
        <div class="stat-icon" style="background: #fff7ed; color: #f59e0b">
          <el-icon :size="22"><Trophy /></el-icon>
        </div>
        <div>
          <div class="stat-value">{{ stats.cookedCount }}</div>
          <div class="stat-label">做过的菜数</div>
        </div>
      </div>
    </div>

    <!-- Tab 切换：食谱列表 / 烹饪日历 -->
    <el-tabs v-model="activeTab" class="recipes-tabs" @tab-change="handleTabChange">
      <el-tab-pane label="食谱列表" name="list">
        <!-- 标签筛选 -->
        <el-card v-if="allTags.length > 0" shadow="never" style="margin-bottom: 16px">
          <div class="tag-filter">
            <span class="tf-label">标签筛选：</span>
            <el-tag
              :type="filterTag === '' ? 'primary' : 'info'"
              :effect="filterTag === '' ? 'dark' : 'plain'"
              round
              style="cursor: pointer"
              @click="filterTag = ''"
            >全部</el-tag>
            <el-tag
              v-for="t in allTags" :key="t"
              :type="filterTag === t ? 'primary' : 'info'"
              :effect="filterTag === t ? 'dark' : 'plain'"
              round
              style="cursor: pointer"
              @click="filterTag = filterTag === t ? '' : t"
            >{{ t }}</el-tag>
          </div>
        </el-card>

        <!-- 食谱列表 -->
        <div v-loading="loading">
          <div v-if="filteredRecipes.length > 0" class="recipes-grid">
            <div v-for="r in filteredRecipes" :key="r.id" class="recipe-wrap">
              <RecipeCard
                :recipe="r"
                :saved="true"
                :show-cook="true"
                @unsave="handleDelete(r)"
                @cook="openCookDialog(r)"
              />
              <div class="recipe-meta">
                <div class="recipe-meta-row">
                  <div class="rating-stars">
                    <el-icon
                      v-for="n in 5"
                      :key="n"
                      :size="16"
                      :color="(r.rating || 0) >= n ? '#fa8c16' : 'var(--text-placeholder)'"
                      class="rating-star"
                      @click.stop="handleRating(r, n)"
                    >
                      <StarFilled v-if="(r.rating || 0) >= n" />
                      <Star v-else />
                    </el-icon>
                    <span v-if="r.rating" class="rating-num">{{ r.rating }}/5</span>
                  </div>
                  <div class="meta-actions">
                    <el-button size="small" link @click.stop="openNoteDialog(r)">
                      <el-icon><EditPen /></el-icon>
                      {{ r.notes ? '查看/编辑笔记' : '添加笔记' }}
                    </el-button>
                  </div>
                </div>
                <div v-if="r.notes" class="recipe-notes">{{ r.notes }}</div>
                <div class="recipe-meta-bottom">
                  做过 <strong>{{ r.cooked_count }}</strong> 次 · 上次：{{ formatDate(r.last_cooked_at) }}
                </div>
              </div>
            </div>
          </div>
          <el-empty v-else-if="!loading" description="还没收藏食谱，去 AI 推荐里点收藏吧" />
        </div>
      </el-tab-pane>

      <el-tab-pane label="烹饪日历" name="calendar">
        <div v-loading="calendarLoading">
          <!-- 4 个 KPI -->
          <div v-if="calendar" class="cal-kpi-row">
            <div class="cal-kpi">
              <div class="cal-kpi-icon" style="background: var(--brand-primary-light); color: var(--brand-primary-dark)">📚</div>
              <div>
                <div class="cal-kpi-value">{{ calendar.total_recipes }}</div>
                <div class="cal-kpi-label">已收藏食谱</div>
              </div>
            </div>
            <div class="cal-kpi">
              <div class="cal-kpi-icon" style="background: #eef2ff; color: #6366f1">🍳</div>
              <div>
                <div class="cal-kpi-value">{{ calendar.total_cooks }}</div>
                <div class="cal-kpi-label">累计打卡</div>
              </div>
            </div>
            <div class="cal-kpi">
              <div class="cal-kpi-icon" style="background: #fff7ed; color: #f59e0b">📅</div>
              <div>
                <div class="cal-kpi-value">{{ calendar.days_with_cook }}</div>
                <div class="cal-kpi-label">打卡天数</div>
              </div>
            </div>
            <div class="cal-kpi cal-kpi-streak">
              <div class="cal-kpi-icon" style="background: #fff1f0; color: #f53f3f">🔥</div>
              <div>
                <div class="cal-kpi-value">{{ calendar.current_streak }}</div>
                <div class="cal-kpi-label">连续打卡天</div>
              </div>
            </div>
          </div>

          <!-- 日历热图 -->
          <el-card v-if="calendar" shadow="never" class="cal-card">
            <template #header>
              <div class="cal-card-head">
                <span class="cal-card-title">
                  <el-icon :size="14" color="var(--brand-primary)"><Calendar /></el-icon>
                  做菜日历（点击格子查看当天打卡）
                </span>
                <el-radio-group v-model="calendarRange" size="small" @change="fetchCalendar">
                  <el-radio-button :value="180">半年</el-radio-button>
                  <el-radio-button :value="365">一年</el-radio-button>
                </el-radio-group>
              </div>
            </template>
            <v-chart
              v-if="calendar.series.length > 0"
              :theme="chartTheme"
              :option="calendarOption"
              autoresize
              class="cal-chart"
              @click="handleCalendarClick"
            />
            <el-empty v-else description="还没有打卡记录" />

            <!-- 选中日期详情 -->
            <div v-if="selectedDay" class="cal-day-detail">
              <div class="cal-day-head">
                <span>📌 {{ selectedDay.date }}</span>
                <span class="cal-day-cnt">{{ selectedDay.count }} 道菜</span>
                <el-button size="small" link @click="selectedDay = null">关闭</el-button>
              </div>
              <ul class="cal-day-list">
                <li v-for="(name, i) in selectedDay.names" :key="i">🍽️ {{ name }}</li>
              </ul>
            </div>
          </el-card>

          <!-- Top 5 最爱做的菜 -->
          <el-card v-if="calendar && calendar.top_recipes.length > 0" shadow="never" class="top-card">
            <template #header>
              <span class="cal-card-title">
                <el-icon :size="14" color="#f59e0b"><Trophy /></el-icon>
                最爱做的菜 Top {{ calendar.top_recipes.length }}
              </span>
            </template>
            <div class="top-list">
              <div
                v-for="(t, idx) in calendar.top_recipes"
                :key="t.name"
                class="top-item"
              >
                <div class="top-rank" :class="{ gold: idx === 0, silver: idx === 1, bronze: idx === 2 }">
                  {{ idx + 1 }}
                </div>
                <div class="top-body">
                  <div class="top-name">{{ t.name }}</div>
                  <div class="top-meta">
                    做过 <strong>{{ t.cooked_count }}</strong> 次
                    <span v-if="t.last_cooked_at"> · 上次 {{ formatDate(t.last_cooked_at) }}</span>
                  </div>
                </div>
              </div>
            </div>
          </el-card>

          <el-empty
            v-if="calendar && calendar.total_cooks === 0 && !calendarLoading"
            description="还没有任何打卡，去食谱列表打卡一道菜吧"
          />
        </div>
      </el-tab-pane>
    </el-tabs>

    <!-- 打卡对话框 -->
    <el-dialog
      v-model="cookDialog.visible"
      :title="`做菜打卡：${cookDialog.recipe?.name || ''}`"
      width="540px"
    >
      <div v-loading="cookDialog.loading">
        <div v-if="ingredientList()" class="cook-ingredients">
          <div class="cook-ingredients-label">食谱所需食材：</div>
          <div class="cook-ingredients-text">{{ ingredientList() }}</div>
        </div>

        <div class="cook-section-title">勾选你实际用到的库存项（这些将被消耗）：</div>
        <div v-if="cookDialog.inStockItems.length === 0" class="cook-empty">
          冰箱当前没有在库的物品，可以直接打卡（不消耗任何库存）。
        </div>
        <el-checkbox-group v-else v-model="cookDialog.selectedIds" class="cook-checkbox-list">
          <el-checkbox
            v-for="item in cookDialog.inStockItems"
            :key="item.id"
            :label="item.id"
            class="cook-check-item"
          >
            <span class="cook-check-name">{{ item.category }}</span>
            <span v-if="item.label_data?.brand" class="cook-check-brand">{{ item.label_data.brand }}</span>
            <span class="cook-check-days" :class="{
              danger: getRemainDays(item) < 0,
              warn: getRemainDays(item) >= 0 && getRemainDays(item) <= 3,
            }">
              {{ Number.isFinite(getRemainDays(item))
                ? (getRemainDays(item) < 0 ? `已过期 ${-getRemainDays(item)}天` : `剩 ${getRemainDays(item)}天`)
                : '保鲜未计算' }}
            </span>
          </el-checkbox>
        </el-checkbox-group>

        <div class="cook-tip">
          <el-icon :size="13"><InfoFilled /></el-icon>
          已为你按食材名自动勾选，可手动调整。被勾选的库存会变为「待确认」状态。
        </div>
      </div>
      <template #footer>
        <el-button @click="cookDialog.visible = false">取消</el-button>
        <el-button type="primary" @click="handleCookConfirm">
          打卡（消耗 {{ cookDialog.selectedIds.length }} 项）
        </el-button>
      </template>
    </el-dialog>

    <!-- 笔记编辑弹窗 -->
    <el-dialog
      v-model="noteDialog.visible"
      :title="`笔记：${noteDialog.recipe?.name || ''}`"
      width="480px"
    >
      <el-input
        v-model="noteDialog.notes"
        type="textarea"
        :rows="6"
        placeholder="记录这道菜的心得：火候、调味、改良方向…"
      />
      <template #footer>
        <el-button @click="noteDialog.visible = false">取消</el-button>
        <el-button type="primary" :loading="noteDialog.saving" @click="saveNote">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped>
.stat-row {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 16px;
  margin-bottom: 16px;
}

.stat-card {
  display: flex;
  align-items: center;
  gap: 14px;
  padding: 18px 20px;
  background: var(--bg-card);
  border-radius: var(--radius-md);
  box-shadow: var(--shadow-sm);
}

.stat-icon {
  width: 44px;
  height: 44px;
  border-radius: 12px;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.stat-value {
  font-size: 22px;
  font-weight: 700;
  color: var(--text-primary);
  line-height: 1.2;
}

.stat-label {
  font-size: 12px;
  color: var(--text-secondary);
  margin-top: 2px;
}

.tag-filter {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 8px;
}

.tf-label {
  font-size: 13px;
  color: var(--text-secondary);
  margin-right: 4px;
}

.recipes-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(380px, 1fr));
  align-items: stretch;
  gap: 16px;
}

.recipe-wrap {
  display: flex;
  flex-direction: column;
  min-width: 0;
  height: 100%;
}

.recipe-wrap :deep(.recipe-card) {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-height: 390px;
  margin: 0;
}

.recipe-wrap :deep(.rc-actions) {
  margin-top: auto;
}

.recipe-meta {
  margin-top: 4px;
  padding: 8px 4px 4px 4px;
  font-size: 12px;
  color: var(--text-placeholder);
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.recipe-meta-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
}

.rating-stars {
  display: inline-flex;
  align-items: center;
  gap: 2px;
}

.rating-star {
  cursor: pointer;
  transition: transform 0.15s;
}

.rating-star:hover {
  transform: scale(1.2);
}

.rating-num {
  font-size: 11px;
  color: var(--text-secondary);
  margin-left: 6px;
  font-weight: 600;
}

.meta-actions {
  margin-left: auto;
}

.recipe-notes {
  margin-top: 4px;
  padding: 8px 10px;
  background: var(--bg-soft);
  border-radius: 8px;
  font-size: 12px;
  color: var(--text-primary);
  line-height: 1.5;
  white-space: pre-wrap;
}

.recipe-meta-bottom {
  text-align: right;
  font-size: 12px;
  color: var(--text-placeholder);
}

/* 打卡对话框 */
.cook-ingredients {
  background: var(--brand-primary-light);
  border: 1px dashed var(--brand-primary);
  border-radius: 10px;
  padding: 10px 14px;
  margin-bottom: 14px;
}

.cook-ingredients-label {
  font-size: 12px;
  color: var(--brand-primary-dark);
  font-weight: 600;
  margin-bottom: 4px;
}

.cook-ingredients-text {
  font-size: 13px;
  color: var(--text-primary);
  line-height: 1.6;
}

.cook-section-title {
  font-size: 13px;
  font-weight: 600;
  color: var(--text-primary);
  margin-bottom: 8px;
}

.cook-empty {
  padding: 18px 0;
  font-size: 13px;
  color: var(--text-placeholder);
  text-align: center;
}

.cook-checkbox-list {
  display: flex !important;
  flex-direction: column;
  gap: 4px;
  max-height: 280px;
  overflow-y: auto;
  border: 1px solid var(--border-color);
  border-radius: 10px;
  padding: 6px 12px;
  margin-bottom: 12px;
}

.cook-check-item {
  width: 100%;
  margin-right: 0 !important;
}

.cook-check-item :deep(.el-checkbox__label) {
  display: flex;
  align-items: center;
  gap: 8px;
  width: 100%;
}

.cook-check-name {
  font-weight: 500;
  color: var(--text-primary);
}

.cook-check-brand {
  font-size: 12px;
  padding: 1px 6px;
  border-radius: 6px;
  background: var(--brand-primary-light);
  color: var(--brand-primary-dark);
}

.cook-check-days {
  margin-left: auto;
  font-size: 12px;
  color: var(--text-secondary);
}

.cook-check-days.danger { color: #f53f3f; font-weight: 600; }
.cook-check-days.warn   { color: #ff7d00; font-weight: 600; }

.cook-tip {
  display: flex;
  align-items: center;
  gap: 4px;
  font-size: 12px;
  color: var(--text-placeholder);
}

/* ---- Tab + 烹饪日历 ---- */
.recipes-tabs :deep(.el-tabs__header) {
  margin-bottom: 16px;
}

.recipes-tabs :deep(.el-tabs__item) {
  font-size: 14px;
  font-weight: 500;
}

.cal-kpi-row {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 16px;
  margin-bottom: 16px;
}

.cal-kpi {
  display: flex;
  align-items: center;
  gap: 14px;
  padding: 18px 20px;
  background: var(--bg-card);
  border-radius: var(--radius-md);
  box-shadow: var(--shadow-sm);
}

.cal-kpi-streak {
  background: linear-gradient(135deg, #fff1f0 0%, var(--bg-card) 100%);
  border-left: 3px solid #f53f3f;
}

.cal-kpi-icon {
  width: 44px;
  height: 44px;
  border-radius: 12px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 22px;
  flex-shrink: 0;
}

.cal-kpi-value {
  font-size: 22px;
  font-weight: 700;
  color: var(--text-primary);
  line-height: 1.2;
  font-variant-numeric: tabular-nums;
}

.cal-kpi-label {
  font-size: 12px;
  color: var(--text-secondary);
  margin-top: 2px;
}

.cal-card {
  margin-bottom: 16px;
}

.cal-card-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
}

.cal-card-title {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  font-size: 15px;
  font-weight: 600;
}

.cal-chart {
  width: 100%;
  height: 220px;
}

.cal-day-detail {
  margin-top: 12px;
  padding: 12px 14px;
  background: var(--bg-soft);
  border-left: 3px solid var(--brand-primary);
  border-radius: 8px;
}

.cal-day-head {
  display: flex;
  align-items: center;
  gap: 10px;
  font-size: 13px;
  color: var(--text-primary);
  font-weight: 600;
}

.cal-day-cnt {
  padding: 1px 8px;
  background: var(--brand-primary-light);
  color: var(--brand-primary-dark);
  border-radius: 10px;
  font-size: 12px;
  font-weight: 600;
}

.cal-day-list {
  margin: 8px 0 0 0;
  padding-left: 4px;
  list-style: none;
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.cal-day-list li {
  font-size: 13px;
  color: var(--text-primary);
}

.top-card {
  /* spacing only */
}

.top-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.top-item {
  display: flex;
  align-items: center;
  gap: 14px;
  padding: 10px 14px;
  background: var(--bg-soft);
  border-radius: 10px;
  transition: all 0.18s;
}

.top-item:hover {
  background: var(--brand-primary-light);
  transform: translateX(2px);
}

.top-rank {
  width: 28px;
  height: 28px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-weight: 700;
  font-size: 14px;
  background: var(--bg-card);
  color: var(--text-secondary);
  flex-shrink: 0;
}

.top-rank.gold   { background: linear-gradient(135deg, #ffd700, #ffae00); color: #fff; }
.top-rank.silver { background: linear-gradient(135deg, #c0c0c0, #9e9e9e); color: #fff; }
.top-rank.bronze { background: linear-gradient(135deg, #cd7f32, #a0522d); color: #fff; }

.top-body {
  flex: 1;
  min-width: 0;
}

.top-name {
  font-size: 14px;
  font-weight: 600;
  color: var(--text-primary);
}

.top-meta {
  font-size: 12px;
  color: var(--text-secondary);
  margin-top: 2px;
}

.top-meta strong {
  color: var(--brand-primary-dark);
  font-weight: 700;
}

@media (max-width: 1100px) {
  .cal-kpi-row { grid-template-columns: repeat(2, 1fr); }
}
</style>
