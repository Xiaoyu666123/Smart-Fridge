<script setup lang="ts">
/**
 * 品类配置：临期阈值（多少天前提醒）+ 参考单价（用于浪费金额估算）。
 */
import { ref, computed, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { getThresholds, updateThreshold, type CategoryThreshold } from '@/api/admin/categoryThreshold'

const loading = ref(false)
const rows = ref<CategoryThreshold[]>([])
const filterQ = ref('')
const editing = ref<Map<string, { days?: number; price?: number | null }>>(new Map())

async function fetchAll() {
  loading.value = true
  try {
    rows.value = await getThresholds()
  } catch {
    ElMessage.error('加载失败')
  } finally {
    loading.value = false
  }
}

const filteredRows = computed(() => {
  const q = filterQ.value.trim().toLowerCase()
  if (!q) return rows.value
  return rows.value.filter(r => r.category.toLowerCase().includes(q))
})

const stats = computed(() => {
  const total = rows.value.length
  const priced = rows.value.filter(r => r.unit_price !== null && r.unit_price !== undefined).length
  const avgDays = total
    ? Math.round(rows.value.reduce((s, r) => s + r.days_before_expiry, 0) / total)
    : 0
  return { total, priced, avgDays, coverage: total ? Math.round(priced / total * 100) : 0 }
})

function startEditDays(row: CategoryThreshold) {
  if (!editing.value.has(row.id)) editing.value.set(row.id, {})
  const e = editing.value.get(row.id)!
  e.days = row.days_before_expiry
  editing.value = new Map(editing.value)
}

function startEditPrice(row: CategoryThreshold) {
  if (!editing.value.has(row.id)) editing.value.set(row.id, {})
  const e = editing.value.get(row.id)!
  e.price = row.unit_price ?? null
  editing.value = new Map(editing.value)
}

async function saveDays(row: CategoryThreshold) {
  const e = editing.value.get(row.id)
  if (!e || e.days === undefined) return
  if (e.days === row.days_before_expiry) {
    cancelDays(row)
    return
  }
  try {
    const updated = await updateThreshold(row.id, { days_before_expiry: e.days })
    Object.assign(row, updated)
    editing.value.delete(row.id)
    editing.value = new Map(editing.value)
    ElMessage.success('阈值已保存')
  } catch {
    ElMessage.error('保存失败')
  }
}

function cancelDays(row: CategoryThreshold) {
  const e = editing.value.get(row.id)
  if (e) {
    e.days = undefined
    if (e.price === undefined) editing.value.delete(row.id)
  }
  editing.value = new Map(editing.value)
}

async function savePrice(row: CategoryThreshold) {
  const e = editing.value.get(row.id)
  if (!e) return
  const newPrice = e.price ?? null
  if (newPrice === row.unit_price) {
    cancelPrice(row)
    return
  }
  try {
    const updated = await updateThreshold(row.id, { unit_price: newPrice ?? 0 })
    Object.assign(row, updated)
    editing.value.delete(row.id)
    editing.value = new Map(editing.value)
    ElMessage.success('单价已保存')
  } catch {
    ElMessage.error('保存失败')
  }
}

function cancelPrice(row: CategoryThreshold) {
  const e = editing.value.get(row.id)
  if (e) {
    e.price = undefined
    if (e.days === undefined) editing.value.delete(row.id)
  }
  editing.value = new Map(editing.value)
}

function isEditingDays(id: string) {
  return editing.value.get(id)?.days !== undefined
}
function isEditingPrice(id: string) {
  return editing.value.get(id)?.price !== undefined
}

onMounted(fetchAll)
</script>

<template>
  <div v-loading="loading">
    <!-- 顶部统计 -->
    <div class="kpi-row">
      <div class="kpi-card">
        <div class="kpi-icon" style="background: var(--brand-primary-light); color: var(--brand-primary-dark)">
          <el-icon :size="22"><Collection /></el-icon>
        </div>
        <div>
          <div class="kpi-value">{{ stats.total }}</div>
          <div class="kpi-label">已登记品类</div>
        </div>
      </div>
      <div class="kpi-card">
        <div class="kpi-icon" style="background: #fff7e6; color: #fa8c16">
          <el-icon :size="22"><AlarmClock /></el-icon>
        </div>
        <div>
          <div class="kpi-value">{{ stats.avgDays }} 天</div>
          <div class="kpi-label">平均临期阈值</div>
        </div>
      </div>
      <div class="kpi-card">
        <div class="kpi-icon" style="background: #e8f7e8; color: #00b42a">
          <el-icon :size="22"><Money /></el-icon>
        </div>
        <div>
          <div class="kpi-value">{{ stats.priced }} <span class="kpi-of">/ {{ stats.total }}</span></div>
          <div class="kpi-label">已配置单价</div>
        </div>
      </div>
      <div class="kpi-card">
        <div class="kpi-icon" :style="{
          background: stats.coverage >= 80 ? '#e8f7e8' : stats.coverage >= 40 ? '#fff7e6' : '#ffece8',
          color: stats.coverage >= 80 ? '#00b42a' : stats.coverage >= 40 ? '#fa8c16' : '#f53f3f',
        }">
          <el-icon :size="22"><DataAnalysis /></el-icon>
        </div>
        <div>
          <div class="kpi-value">{{ stats.coverage }}%</div>
          <div class="kpi-label">单价覆盖率</div>
        </div>
      </div>
    </div>

    <!-- 工具栏 -->
    <div class="page-tool">
      <div class="page-tip">
        <el-icon :size="14" color="var(--text-secondary)"><InfoFilled /></el-icon>
        临期阈值：还有几天到期时开始通知用户。单价：用于浪费金额 / 购物清单估算。
      </div>
      <el-input
        v-model="filterQ"
        placeholder="搜索品类"
        clearable
        size="default"
        style="width: 240px"
      >
        <template #prefix><el-icon><Search /></el-icon></template>
      </el-input>
    </div>

    <!-- 表格 -->
    <el-card shadow="never">
      <el-table :data="filteredRows" stripe>
        <el-table-column label="品类" prop="category" min-width="160">
          <template #default="{ row }">
            <span style="font-weight: 600">{{ row.category }}</span>
          </template>
        </el-table-column>
        <el-table-column label="临期阈值（天）" min-width="200">
          <template #default="{ row }">
            <div v-if="!isEditingDays(row.id)" class="cell-view" @click="startEditDays(row)">
              <strong>{{ row.days_before_expiry }}</strong> 天
              <el-icon class="cell-edit-icon" :size="12"><EditPen /></el-icon>
            </div>
            <div v-else class="cell-edit">
              <el-input-number
                :model-value="editing.get(row.id)?.days"
                @update:model-value="(v: any) => { const e = editing.get(row.id)!; e.days = v; editing = new Map(editing) }"
                :min="1" :max="365" size="small" style="width: 110px"
                @keyup.enter="saveDays(row)"
              />
              <el-button size="small" type="primary" @click="saveDays(row)">保存</el-button>
              <el-button size="small" @click="cancelDays(row)">取消</el-button>
            </div>
          </template>
        </el-table-column>
        <el-table-column label="参考单价（CNY）" min-width="220">
          <template #default="{ row }">
            <div v-if="!isEditingPrice(row.id)" class="cell-view" @click="startEditPrice(row)">
              <span v-if="row.unit_price !== null && row.unit_price !== undefined">
                ¥<strong>{{ Number(row.unit_price).toFixed(2) }}</strong>
              </span>
              <span v-else style="color: var(--text-placeholder)">未配置</span>
              <el-icon class="cell-edit-icon" :size="12"><EditPen /></el-icon>
            </div>
            <div v-else class="cell-edit">
              <el-input-number
                :model-value="editing.get(row.id)?.price ?? 0"
                @update:model-value="(v: any) => { const e = editing.get(row.id)!; e.price = v; editing = new Map(editing) }"
                :min="0" :max="100000" :precision="2" :step="0.5"
                size="small" style="width: 130px"
                @keyup.enter="savePrice(row)"
              />
              <el-button size="small" type="primary" @click="savePrice(row)">保存</el-button>
              <el-button size="small" @click="cancelPrice(row)">取消</el-button>
            </div>
          </template>
        </el-table-column>
        <el-table-column label="登记时间" width="180">
          <template #default="{ row }">
            {{ row.created_at ? new Date(row.created_at).toLocaleDateString('zh-CN') : '-' }}
          </template>
        </el-table-column>
      </el-table>
    </el-card>
  </div>
</template>

<style scoped>
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

.kpi-of {
  font-size: 14px;
  color: var(--text-placeholder);
  font-weight: 500;
}

.kpi-label {
  font-size: 12px;
  color: var(--text-secondary);
  margin-top: 2px;
}

.page-tool {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 12px;
  margin-bottom: 16px;
}

.page-tip {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  font-size: 12px;
  color: var(--text-secondary);
}

.cell-view {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  cursor: pointer;
  padding: 4px 10px;
  border-radius: 6px;
  transition: background 0.15s;
}

.cell-view:hover {
  background: var(--brand-primary-soft);
}

.cell-edit-icon {
  color: var(--text-placeholder);
  opacity: 0;
  transition: opacity 0.15s;
}

.cell-view:hover .cell-edit-icon {
  opacity: 1;
}

.cell-edit {
  display: inline-flex;
  align-items: center;
  gap: 6px;
}

@media (max-width: 1100px) {
  .kpi-row { grid-template-columns: repeat(2, 1fr); }
}
</style>
