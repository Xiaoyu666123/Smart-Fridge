<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import { ElMessage } from 'element-plus'
import { getInventoryList, getCategories, type InventoryItem } from '@/api/user/inventory'
import InventoryDetailDrawer from '@/components/InventoryDetailDrawer.vue'
import EmptyHint from '@/components/EmptyHint.vue'
import { useInventoryWS, type InventoryWSEvent } from '@/composables/useInventoryWS'
import { uploadUrl } from '@/config/env'

const loading = ref(false)
const items = ref<InventoryItem[]>([])
const categories = ref<string[]>([])
const filterStatus = ref('')
const filterCategory = ref('')
const filterQ = ref('')
const filterExpiring = ref<number | null>(null)
const previewVisible = ref(false)
const previewUrl = ref('')

const detailVisible = ref(false)
const detailItem = ref<InventoryItem | null>(null)
function openDetail(row: InventoryItem) {
  detailItem.value = row
  detailVisible.value = true
}

async function fetchCategories() {
  try {
    categories.value = await getCategories()
  } catch (e) {
    console.error(e)
  }
}

async function fetchInventory() {
  loading.value = true
  try {
    const params: Record<string, string | number> = {}
    if (filterStatus.value) params.status = filterStatus.value
    if (filterCategory.value) params.category = filterCategory.value
    if (filterQ.value.trim()) params.q = filterQ.value.trim()
    if (filterExpiring.value !== null) params.expiring_in_days = filterExpiring.value
    items.value = await getInventoryList(params)
  } catch (e) {
    console.error(e)
  } finally {
    loading.value = false
  }
}

function getRemainDays(item: InventoryItem): number {
  const metadata = item.agent_metadata
  if (!metadata?.expire_at) return -1
  const expire = new Date(metadata.expire_at)
  const now = new Date()
  return Math.max(0, Math.ceil((expire.getTime() - now.getTime()) / (1000 * 60 * 60 * 24)))
}

function getStatusType(item: InventoryItem): string {
  const days = getRemainDays(item)
  if (days < 0) return 'info'
  if (days <= 1) return 'danger'
  if (days <= 3) return 'warning'
  return 'success'
}

function formatDate(dateStr: string | null): string {
  if (!dateStr) return '-'
  return new Date(dateStr).toLocaleString('zh-CN')
}

function getSnapshotUrl(path: string | null | undefined): string {
  return uploadUrl(path)
}

function openPreview(row: InventoryItem) {
  previewUrl.value = getSnapshotUrl(row.snapshot_path)
  previewVisible.value = true
}

const stats = computed(() => {
  const total = items.value.length
  const inStock = items.value.filter(i => i.status === 'IN_STOCK').length
  const expiringSoon = items.value.filter(i => getStatusType(i) === 'warning' || getStatusType(i) === 'danger').length
  return { total, inStock, expiringSoon }
})

onMounted(() => {
  fetchCategories()
  fetchInventory()
})

// ---- WebSocket 实时同步 ----
const newRowIds = ref<Set<string>>(new Set())
const updatedRowIds = ref<Set<string>>(new Set())

function rowClassName({ row }: { row: InventoryItem }): string {
  if (newRowIds.value.has(row.id)) return 'row-new'
  if (updatedRowIds.value.has(row.id)) return 'row-updated'
  return ''
}

function passesFilter(it: InventoryWSEvent | InventoryItem): boolean {
  if (filterStatus.value && it.status !== filterStatus.value) return false
  if (filterCategory.value && it.category !== filterCategory.value) return false
  return true
}

useInventoryWS({
  scope: 'user',
  onCreated: (it, source) => {
    if (!passesFilter(it)) return
    if (items.value.some(x => x.id === it.id)) return
    items.value = [it as InventoryItem, ...items.value]
    newRowIds.value.add(it.id)
    setTimeout(() => {
      newRowIds.value.delete(it.id)
      newRowIds.value = new Set(newRowIds.value)
    }, 2400)
    ElMessage({
      message: source === 'agent' ? `📦 自动入库：${it.category}` : `🍱 新增食材：${it.category}`,
      type: 'success',
      duration: 2500,
      grouping: true,
    })
    if (categories.value.indexOf(it.category) === -1) categories.value.push(it.category)
  },
  onUpdated: (it) => {
    const idx = items.value.findIndex(x => x.id === it.id)
    if (idx === -1) {
      if (passesFilter(it)) items.value = [it as InventoryItem, ...items.value]
      return
    }
    if (!passesFilter(it)) {
      items.value.splice(idx, 1)
      return
    }
    items.value.splice(idx, 1, it as InventoryItem)
    updatedRowIds.value.add(it.id)
    setTimeout(() => {
      updatedRowIds.value.delete(it.id)
      updatedRowIds.value = new Set(updatedRowIds.value)
    }, 1600)
  },
  onDeleted: (id) => {
    const idx = items.value.findIndex(x => x.id === id)
    if (idx !== -1) items.value.splice(idx, 1)
  },
})
</script>

<template>
  <div>
    <div style="display: grid; grid-template-columns: repeat(3, 1fr); gap: 16px; margin-bottom: 20px">
      <div class="stat-card">
        <div class="stat-icon" style="background: var(--brand-primary-light); color: var(--brand-primary)">
          <el-icon :size="24"><Box /></el-icon>
        </div>
        <div class="stat-info">
          <div class="stat-value">{{ stats.total }}</div>
          <div class="stat-label">总库存</div>
        </div>
      </div>
      <div class="stat-card">
        <div class="stat-icon" style="background: #e8f7e8; color: #00b42a">
          <el-icon :size="24"><CircleCheck /></el-icon>
        </div>
        <div class="stat-info">
          <div class="stat-value">{{ stats.inStock }}</div>
          <div class="stat-label">在库</div>
        </div>
      </div>
      <div class="stat-card">
        <div class="stat-icon" style="background: #fff3e8; color: #ff7d00">
          <el-icon :size="24"><Warning /></el-icon>
        </div>
        <div class="stat-info">
          <div class="stat-value">{{ stats.expiringSoon }}</div>
          <div class="stat-label">即将过期</div>
        </div>
      </div>
    </div>

    <el-card shadow="never" style="margin-bottom: 16px">
      <el-form :inline="true">
        <el-form-item label="搜索">
          <el-input
            v-model="filterQ"
            placeholder="食材名 / 品牌"
            clearable
            style="width: 200px"
            @keyup.enter="fetchInventory"
            @clear="fetchInventory"
          >
            <template #prefix><el-icon><Search /></el-icon></template>
          </el-input>
        </el-form-item>
        <el-form-item label="状态">
          <el-select v-model="filterStatus" placeholder="选择状态" clearable style="width: 130px">
            <el-option label="在库" value="IN_STOCK" />
            <el-option label="待确认" value="OUT_PENDING" />
            <el-option label="已消耗" value="CONSUMED" />
          </el-select>
        </el-form-item>
        <el-form-item label="食材种类">
          <el-select v-model="filterCategory" placeholder="选择种类" clearable filterable style="width: 140px">
            <el-option v-for="cat in categories" :key="cat" :label="cat" :value="cat" />
          </el-select>
        </el-form-item>
        <el-form-item label="临期">
          <el-select v-model="filterExpiring" placeholder="不限" clearable style="width: 120px">
            <el-option :value="0" label="今天到期" />
            <el-option :value="3" label="3 天内" />
            <el-option :value="7" label="7 天内" />
          </el-select>
        </el-form-item>
        <el-form-item>
          <el-button type="primary" @click="fetchInventory"><el-icon><Search /></el-icon> 查询</el-button>
        </el-form-item>
      </el-form>
    </el-card>

    <el-card shadow="never">
      <EmptyHint
        v-if="!loading && items.length === 0"
        emoji="🥬"
        title="冰箱里还没有食材"
        desc="等管理员或端侧设备录入第一批食材后，这里就会显示"
        :actions="[
          { label: 'AI对话', to: '/user/chat' },
          { label: '⚙️ 设置我的偏好', to: '/user/preferences' },
        ]"
      />
      <el-table v-else :data="items" v-loading="loading" stripe @row-click="openDetail" class="row-clickable" :row-class-name="rowClassName">
        <el-table-column label="图片" width="80">
          <template #default="{ row }">
            <img
              v-if="row.snapshot_path"
              :src="getSnapshotUrl(row.snapshot_path)"
              @click.stop="openPreview(row)"
              style="width: 50px; height: 50px; border-radius: 6px; object-fit: cover; cursor: pointer"
            />
            <span v-else style="color: var(--text-secondary); font-size: 12px">无图</span>
          </template>
        </el-table-column>
        <el-table-column prop="category" label="食材名称" width="120">
          <template #default="{ row }">
            <div style="display: flex; align-items: center; gap: 6px">
              <span>{{ row.category }}</span>
              <el-tag v-if="row.label_data?.brand" size="small" round style="background: var(--brand-primary-light); color: var(--brand-primary-dark); border: none; padding: 0 6px">📦</el-tag>
            </div>
          </template>
        </el-table-column>
        <el-table-column label="品牌" width="110">
          <template #default="{ row }">
            <span v-if="row.label_data?.brand">{{ row.label_data.brand }}</span>
            <span v-else style="color: var(--text-placeholder)">-</span>
          </template>
        </el-table-column>
        <el-table-column prop="status" label="状态" width="100">
          <template #default="{ row }">
            <el-tag :type="row.status === 'IN_STOCK' ? 'success' : row.status === 'OUT_PENDING' ? 'warning' : 'info'" round>
              {{ row.status === 'IN_STOCK' ? '在库' : row.status === 'OUT_PENDING' ? '待确认' : '已消耗' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="保鲜状态" width="120">
          <template #default="{ row }">
            <el-tag v-if="row.status === 'EXPIRED'" type="danger" round>已过期</el-tag>
            <el-tag v-else-if="!row.agent_metadata?.expire_at" type="info" round>计算中...</el-tag>
            <el-tag v-else-if="getRemainDays(row) === 0" type="danger" round>已过期</el-tag>
            <el-tag v-else :type="getStatusType(row)" round>
              {{ getRemainDays(row) > 0 ? `${getRemainDays(row)} 天` : '未知' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="入库时间" width="180">
          <template #default="{ row }">{{ formatDate(row.created_at) }}</template>
        </el-table-column>
        <el-table-column label="过期时间" width="180">
          <template #default="{ row }">
            <span v-if="row.agent_metadata?.expire_at">{{ formatDate(row.agent_metadata.expire_at) }}</span>
            <el-tag v-else type="info" size="small" round>计算中...</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="remain_ratio" label="剩余比例" width="140">
          <template #default="{ row }">
            <el-progress :percentage="Math.round(row.remain_ratio * 100)" :stroke-width="6" :show-text="true" />
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <el-dialog v-model="previewVisible" width="auto" :show-close="true" class="preview-dialog" @close="previewVisible = false">
      <img :src="previewUrl" style="max-width: 80vw; max-height: 80vh; display: block; margin: 0 auto; border-radius: 8px" />
    </el-dialog>

    <InventoryDetailDrawer
      v-model:visible="detailVisible"
      :item="detailItem"
      mode="user"
      :fetch-events="null"
    />
  </div>
</template>

<style scoped>
.row-clickable :deep(.el-table__row) {
  cursor: pointer;
}

.stat-card {
  display: flex;
  align-items: center;
  gap: 16px;
  padding: 20px 24px;
  background: var(--bg-card);
  border-radius: var(--radius-md);
  box-shadow: var(--shadow-sm);
}

.stat-icon {
  width: 48px;
  height: 48px;
  border-radius: 12px;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.stat-value {
  font-size: 24px;
  font-weight: 700;
  color: var(--text-primary);
  line-height: 1.2;
}

.stat-label {
  font-size: 13px;
  color: var(--text-secondary);
  margin-top: 2px;
}
</style>

<style>
.preview-dialog .el-dialog__body {
  padding: 0;
  background: #000;
}
.preview-dialog .el-dialog__header {
  background: #000;
  padding: 10px 16px;
}
.preview-dialog .el-dialog__headerbtn .el-dialog__close {
  color: #fff;
  font-size: 20px;
}

/* 库存实时事件高亮 */
.el-table .el-table__row.row-new {
  animation: row-slide-in 0.45s ease-out, row-flash 2.2s ease-out;
}
.el-table .el-table__row.row-updated {
  animation: row-flash-soft 1.4s ease-out;
}
@keyframes row-slide-in {
  from { transform: translateY(-12px); opacity: 0; }
  to   { transform: translateY(0); opacity: 1; }
}
@keyframes row-flash {
  0%   { background-color: rgba(14, 165, 233, 0.30); }
  60%  { background-color: rgba(14, 165, 233, 0.18); }
  100% { background-color: transparent; }
}
@keyframes row-flash-soft {
  0%   { background-color: rgba(255, 187, 86, 0.22); }
  100% { background-color: transparent; }
}
</style>
