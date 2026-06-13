<script setup lang="ts">
import { ref, onMounted, computed, watch } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import type { UploadFile } from 'element-plus'
import { getInventoryList, getInventoryListPaged, getCategories, createInventory, updateInventory, deleteInventory, uploadInventoryImage, type InventoryItem } from '@/api/admin/inventory'
import { listPendingLabels, type PendingLabelItem } from '@/api/admin/pendingLabel'
import { getEventLogs } from '@/api/admin/event'
import { useAdminAuthStore } from '@/stores/adminAuth'
import { compressImage } from '@/utils/imageCompress'
import InventoryDetailDrawer from '@/components/InventoryDetailDrawer.vue'
import EmptyHint from '@/components/EmptyHint.vue'
import { useInventoryWS, type InventoryWSEvent } from '@/composables/useInventoryWS'
import { exportInventory } from '@/utils/downloadCsv'
import { showUndoToast } from '@/composables/useUndoToast'
import { uploadUrl } from '@/config/env'

const authStore = useAdminAuthStore()
// admin 模块下默认所有 CRUD 都开放
const isAdmin = computed(() => true)
void authStore

const loading = ref(false)
const items = ref<InventoryItem[]>([])
const categories = ref<string[]>([])
const filterStatus = ref('')
const filterCategory = ref('')
const filterQ = ref('')
const filterDateRange = ref<[string, string] | null>(null)
const filterExpiring = ref<number | null>(null)

// 分页
const pageSize = ref(20)
const pageNum = ref(1)
const total = ref(0)

// CRUD dialog
const showFormDialog = ref(false)
const formLoading = ref(false)
const isEdit = ref(false)
const editId = ref('')
const form = ref({
  device_id: 'luckfox',
  category: '',
  status: 'IN_STOCK',
  remain_ratio: 1.0,
  snapshot_path: '',
  confidence: 0.9,
  bbox: '0,0,0,0',
})
const imageFile = ref<File | null>(null)
const imagePreview = ref('')
const imageUploading = ref(false)
const previewVisible = ref(false)
const previewUrl = ref('')
let refreshTimer: ReturnType<typeof setTimeout> | null = null

// 详情抽屉
const detailVisible = ref(false)
const detailItem = ref<InventoryItem | null>(null)
async function fetchEventsForDrawer(invId: string) {
  return await getEventLogs({ inventory_id: invId })
}
function openDetail(row: InventoryItem) {
  detailItem.value = row
  detailVisible.value = true
}

// 标签缓冲探针：表单打开时实时查同 device_id 的 pending_label
const pendingLabel = ref<PendingLabelItem | null>(null)
const pendingLabelLoading = ref(false)

async function loadPendingLabel() {
  if (!form.value.device_id?.trim()) {
    pendingLabel.value = null
    return
  }
  pendingLabelLoading.value = true
  try {
    const list = await listPendingLabels({
      device_id: form.value.device_id.trim(),
      status: 'pending',
      limit: 1,
    })
    pendingLabel.value = list?.[0] || null
  } catch {
    pendingLabel.value = null
  } finally {
    pendingLabelLoading.value = false
  }
}

watch(() => form.value.device_id, () => {
  if (showFormDialog.value && !isEdit.value) loadPendingLabel()
})

function hasComputingItems(): boolean {
  return items.value.some(i => !i.agent_metadata?.expire_at)
}

function startRefreshPoll() {
  if (refreshTimer) return
  if (!hasComputingItems()) return
  refreshTimer = setTimeout(async () => {
    refreshTimer = null
    await fetchInventory()
    if (hasComputingItems()) startRefreshPoll()
  }, 3000)
}

function stopRefreshPoll() {
  if (refreshTimer) {
    clearTimeout(refreshTimer)
    refreshTimer = null
  }
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
    const params: Record<string, string | number> = {
      limit: pageSize.value,
      offset: (pageNum.value - 1) * pageSize.value,
    }
    if (filterStatus.value) params.status = filterStatus.value
    if (filterCategory.value) params.category = filterCategory.value
    if (filterQ.value.trim()) params.q = filterQ.value.trim()
    if (filterDateRange.value && filterDateRange.value[0]) params.start_date = filterDateRange.value[0]
    if (filterDateRange.value && filterDateRange.value[1]) params.end_date = filterDateRange.value[1]
    if (filterExpiring.value !== null) params.expiring_in_days = filterExpiring.value
    const res = await getInventoryListPaged(params as any)
    items.value = res.items
    total.value = res.total
  } catch (e) {
    console.error(e)
  } finally {
    loading.value = false
  }
}

function clearFilters() {
  filterStatus.value = ''
  filterCategory.value = ''
  filterQ.value = ''
  filterDateRange.value = null
  filterExpiring.value = null
  pageNum.value = 1
  fetchInventory()
}

function handlePageChange(p: number) {
  pageNum.value = p
  fetchInventory()
}

function handleSizeChange(s: number) {
  pageSize.value = s
  pageNum.value = 1
  fetchInventory()
}

function searchAndReset() {
  pageNum.value = 1
  fetchInventory()
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

const stats = computed(() => {
  const total = items.value.length
  const inStock = items.value.filter(i => i.status === 'IN_STOCK').length
  const expiringSoon = items.value.filter(i => getStatusType(i) === 'warning' || getStatusType(i) === 'danger').length
  return { total, inStock, expiringSoon }
})

// CRUD operations
function handleAdd() {
  isEdit.value = false
  editId.value = ''
  form.value = { device_id: 'luckfox', category: '', status: 'IN_STOCK', remain_ratio: 1.0, snapshot_path: '', confidence: 0.9, bbox: '0,0,0,0' }
  imageFile.value = null
  imagePreview.value = ''
  pendingLabel.value = null
  showFormDialog.value = true
  loadPendingLabel()
}

function handleEdit(row: InventoryItem) {
  isEdit.value = true
  editId.value = row.id
  form.value = {
    device_id: row.device_id,
    category: row.category,
    status: row.status,
    remain_ratio: row.remain_ratio,
    snapshot_path: row.snapshot_path || '',
    confidence: 0.9,
    bbox: row.bbox ? row.bbox.join(',') : '0,0,0,0',
  }
  imageFile.value = null
  imagePreview.value = row.snapshot_path ? getSnapshotUrl(row.snapshot_path) : ''
  showFormDialog.value = true
}

function handleImageChange(uploadFile: UploadFile) {
  if (!uploadFile.raw) return
  // 压缩到长边 1280 + JPEG 0.85，避免触发云端 vision/embedding 的尺寸上限
  compressImage(uploadFile.raw).then((compressed) => {
    imageFile.value = compressed
    const reader = new FileReader()
    reader.onload = (e) => { imagePreview.value = e.target?.result as string }
    reader.readAsDataURL(compressed)
  }).catch((err) => {
    console.warn('[Inventory] 图片压缩失败，使用原图:', err)
    imageFile.value = uploadFile.raw!
    const reader = new FileReader()
    reader.onload = (e) => { imagePreview.value = e.target?.result as string }
    reader.readAsDataURL(uploadFile.raw!)
  })
}

function openPreview(row: InventoryItem) {
  previewUrl.value = getSnapshotUrl(row.snapshot_path)
  previewVisible.value = true
}

function getSnapshotUrl(path: string | null | undefined): string {
  return uploadUrl(path)
}

async function handleFormSubmit() {
  if (!form.value.category.trim()) {
    ElMessage.warning('请填写食材名称')
    return
  }
  formLoading.value = true
  try {
    let snapshotPath = form.value.snapshot_path
    if (imageFile.value) {
      imageUploading.value = true
      const uploadResult = await uploadInventoryImage(imageFile.value)
      // 服务器返回可能含反斜杠（windows），归一化为正斜杠
      snapshotPath = (uploadResult.snapshot_path || '').replace(/\\/g, '/')
      imageUploading.value = false
    }
    if (isEdit.value) {
      await updateInventory(editId.value, {
        category: form.value.category,
        status: form.value.status,
        remain_ratio: form.value.remain_ratio,
        snapshot_path: snapshotPath || undefined,
        bbox: form.value.bbox ? form.value.bbox.split(',').map(Number) : undefined,
      })
      ElMessage.success('修改成功')
    } else {
      await createInventory({
        device_id: form.value.device_id,
        category: form.value.category,
        status: form.value.status,
        remain_ratio: form.value.remain_ratio,
        snapshot_path: snapshotPath || undefined,
        bbox: form.value.bbox ? form.value.bbox.split(',').map(Number) : undefined,
        agent_metadata: { confidence: form.value.confidence },
      })
      ElMessage.success('添加成功')
    }
    showFormDialog.value = false
    fetchCategories()
    await fetchInventory()
    if (!isEdit.value && hasComputingItems()) startRefreshPoll()
  } catch (e: any) {
    console.error('[Inventory] submit failed:', e)
    const detail = e?.response?.data?.detail
    if (detail) {
      ElMessage.warning(typeof detail === 'string' ? detail : JSON.stringify(detail))
    } else {
      const status = e?.response?.status
      const statusText = e?.response?.statusText
      const msg = e?.message || '未知错误'
      ElMessage.error(`${isEdit.value ? '修改' : '添加'}失败：${status ? status + ' ' + statusText : msg}`)
    }
  } finally {
    formLoading.value = false
    imageUploading.value = false
  }
}

async function handleDelete(row: InventoryItem) {
  try {
    await ElMessageBox.confirm(`确定删除食材「${row.category}」？`, '删除确认', {
      confirmButtonText: '删除',
      cancelButtonText: '取消',
      type: 'warning',
    })
    // 缓存原始数据用于撤销恢复
    const snapshot = {
      device_id: row.device_id,
      category: row.category,
      status: row.status,
      remain_ratio: row.remain_ratio,
      snapshot_path: row.snapshot_path || undefined,
      bbox: row.bbox || undefined,
      agent_metadata: row.agent_metadata || undefined,
    }
    await deleteInventory(row.id)
    fetchInventory()

    showUndoToast({
      message: `已删除「${row.category}」`,
      duration: 6,
      onUndo: async () => {
        try {
          await createInventory(snapshot)
          ElMessage.success('已恢复删除的食材')
          fetchInventory()
        } catch (e: any) {
          // 重新插入可能撞上去重（hash 一致），那就直接告诉用户
          const detail = e?.response?.data?.detail
          if (detail) {
            ElMessage.warning(typeof detail === 'string' ? detail : JSON.stringify(detail))
          } else {
            ElMessage.error('恢复失败')
          }
        }
      },
    })
  } catch (e) {
    if (e !== 'cancel' && e !== 'close') {
      ElMessage.error('删除失败')
    }
  }
}

async function handleMarkExpired(row: InventoryItem) {
  try {
    await ElMessageBox.confirm(
      `确定将「${row.category}」标记为已过期？`,
      '标记过期',
      { confirmButtonText: '确定', cancelButtonText: '取消', type: 'warning' }
    )
    await updateInventory(row.id, { status: 'EXPIRED' })
    ElMessage.success(`「${row.category}」已标记为过期`)
    fetchInventory()
  } catch (e) {
    if (e !== 'cancel' && e !== 'close') {
      ElMessage.error('操作失败')
    }
  }
}

onMounted(() => {
  fetchCategories()
  fetchInventory().then(() => {
    if (hasComputingItems()) startRefreshPoll()
  })
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
  scope: 'admin',
  onCreated: (it, source) => {
    if (!passesFilter(it)) return
    if (items.value.some(x => x.id === it.id)) return
    items.value = [it as InventoryItem, ...items.value]
    total.value++
    newRowIds.value.add(it.id)
    setTimeout(() => {
      newRowIds.value.delete(it.id)
      // 触发响应式更新
      newRowIds.value = new Set(newRowIds.value)
    }, 2400)
    ElMessage({
      message: source === 'agent'
        ? `📦 端侧自动入库：${it.category}`
        : source === 'bulk'
          ? `🍱 批量入库：${it.category}`
          : `✏️ 新增：${it.category}`,
      type: 'success',
      duration: 2500,
      grouping: true,
    })
    if (categories.value.indexOf(it.category) === -1) categories.value.push(it.category)
  },
  onUpdated: (it) => {
    const idx = items.value.findIndex(x => x.id === it.id)
    if (idx === -1) {
      // 原本因为 filter 不在视图里；如果更新后符合 filter 则插入
      if (passesFilter(it)) items.value = [it as InventoryItem, ...items.value]
      return
    }
    if (!passesFilter(it)) {
      // 更新后不再符合筛选条件，从列表移除
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
    if (idx !== -1) {
      items.value.splice(idx, 1)
      total.value = Math.max(0, total.value - 1)
    }
  },
})
</script>

<template>
  <div>
    <!-- 顶部统计卡片 -->
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

    <!-- 筛选栏 -->
    <el-card shadow="never" style="margin-bottom: 16px">
      <el-form :inline="true">
        <el-form-item label="搜索">
          <el-input
            v-model="filterQ"
            placeholder="食材名 / 品牌 / 设备 / 备注"
            clearable
            style="width: 240px"
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
            <el-option label="已过期" value="EXPIRED" />
          </el-select>
        </el-form-item>
        <el-form-item label="食材种类">
          <el-select v-model="filterCategory" placeholder="选择种类" clearable filterable style="width: 140px">
            <el-option v-for="cat in categories" :key="cat" :label="cat" :value="cat" />
          </el-select>
        </el-form-item>
        <el-form-item label="入库时间">
          <el-date-picker
            v-model="filterDateRange"
            type="daterange"
            value-format="YYYY-MM-DD"
            range-separator="至"
            start-placeholder="开始日期"
            end-placeholder="结束日期"
            style="width: 240px"
          />
        </el-form-item>
        <el-form-item label="临期">
          <el-select v-model="filterExpiring" placeholder="不限" clearable style="width: 130px">
            <el-option :value="0" label="今天到期" />
            <el-option :value="1" label="明天前" />
            <el-option :value="3" label="3 天内" />
            <el-option :value="7" label="7 天内" />
          </el-select>
        </el-form-item>
        <el-form-item>
          <el-button type="primary" @click="searchAndReset"><el-icon><Search /></el-icon> 查询</el-button>
          <el-button @click="clearFilters">重置</el-button>
        </el-form-item>
        <el-form-item v-if="isAdmin">
          <el-button type="success" @click="handleAdd">
            <el-icon><Plus /></el-icon> 添加食材
          </el-button>
        </el-form-item>
        <el-form-item>
          <el-button @click="exportInventory">
            <el-icon><Download /></el-icon> 导出 CSV
          </el-button>
        </el-form-item>
      </el-form>
    </el-card>

    <!-- 表格 -->
    <el-card shadow="never">
      <EmptyHint
        v-if="!loading && items.length === 0 && total === 0"
        emoji="🥬"
        title="冰箱空空如也"
        desc="试试以下几种方式把第一批食材送进来："
        :actions="[
          { label: '➕ 手动添加食材', click: handleAdd },
          { label: '📷 整柜批量识别', to: '/admin/batch-recognize' },
          { label: '⚡ 用快速识别 (右下角)', click: () => {} },
        ]"
      />
      <template v-else>
        <el-table :data="items" v-loading="loading" stripe @row-click="openDetail" class="row-clickable" :row-class-name="rowClassName">
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
              <el-tooltip v-if="row.label_data?.brand" content="带标签：来自包装的真实信息" placement="top">
                <el-tag size="small" round style="background: var(--brand-primary-light); color: var(--brand-primary-dark); border: none; padding: 0 6px">📦</el-tag>
              </el-tooltip>
            </div>
          </template>
        </el-table-column>
        <el-table-column label="品牌" width="120">
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
            <el-tag v-else-if="!row.agent_metadata?.expire_at" type="info" round>
              计算中...
            </el-tag>
            <el-tag v-else-if="getRemainDays(row) === 0" type="danger" round>已过期</el-tag>
            <el-tag v-else :type="getStatusType(row)" round>
              {{ getRemainDays(row) > 0 ? `${getRemainDays(row)} 天` : '未知' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="入库时间" width="180">
          <template #default="{ row }">{{ formatDate(row.created_at) }}</template>
        </el-table-column>
        <el-table-column label="过期时间" width="200">
          <template #default="{ row }">
            <div v-if="row.agent_metadata?.expire_at" style="display: flex; align-items: center; gap: 6px">
              <span>{{ formatDate(row.agent_metadata.expire_at) }}</span>
              <el-tooltip
                v-if="row.agent_metadata?.expire_source === 'label'"
                content="来自包装标签"
                placement="top"
              >
                <el-tag size="small" round
                  :style="{
                    background: 'var(--brand-primary-light)',
                    color: 'var(--brand-primary-dark)',
                    border: 'none',
                    padding: '0 6px',
                  }">
                  📦
                </el-tag>
              </el-tooltip>
            </div>
            <el-tag v-else type="info" size="small" round>计算中...</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="remain_ratio" label="剩余比例" width="140">
          <template #default="{ row }">
            <el-progress :percentage="Math.round(row.remain_ratio * 100)" :stroke-width="6" :show-text="true" />
          </template>
        </el-table-column>
        <el-table-column label="过期处理" width="100" fixed="right">
          <template #default="{ row }">
            <span
              v-if="row.status === 'IN_STOCK' && row.agent_metadata?.expire_at && getRemainDays(row) === 0"
              class="link-expired"
              @click.stop="handleMarkExpired(row)"
            >标记过期</span>
            <span v-else style="color: var(--text-placeholder)">-</span>
          </template>
        </el-table-column>
        <el-table-column v-if="isAdmin" label="操作" width="120" fixed="right">
          <template #default="{ row }">
            <span class="link-action" @click.stop="handleEdit(row)">编辑</span>
            <span class="link-action link-danger" @click.stop="handleDelete(row)">删除</span>
          </template>
        </el-table-column>
      </el-table>

      <!-- 分页 -->
      <div class="pagination-bar">
        <el-pagination
          v-model:current-page="pageNum"
          v-model:page-size="pageSize"
          :total="total"
          :page-sizes="[10, 20, 50, 100]"
          background
          layout="total, sizes, prev, pager, next, jumper"
          @current-change="handlePageChange"
          @size-change="handleSizeChange"
        />
      </div>
      </template>
    </el-card>

    <!-- 添加/编辑弹窗 -->
    <el-dialog v-model="showFormDialog" :title="isEdit ? '编辑食材' : '添加食材'" width="500px" :close-on-click-modal="false">
      <!-- 标签缓冲探针：仅"添加"模式 -->
      <div v-if="!isEdit" class="label-probe" :class="{ 'has-label': pendingLabel }">
        <template v-if="pendingLabelLoading">
          <el-icon class="probe-icon"><Loading /></el-icon>
          <span class="probe-text">检测设备 luckfox 的标签缓冲...</span>
        </template>
        <template v-else-if="pendingLabel">
          <span class="probe-icon">📦</span>
          <div class="probe-body">
            <div class="probe-title">
              <strong>检测到待关联标签</strong>
              <el-tag size="small" round type="success" style="margin-left: 6px">将自动挂载</el-tag>
            </div>
            <div class="probe-detail">
              <span v-if="pendingLabel.label_data?.brand">
                品牌：<b>{{ pendingLabel.label_data.brand }}</b>
              </span>
              <span v-if="pendingLabel.label_data?.product_name" style="margin-left: 12px">
                产品：{{ pendingLabel.label_data.product_name }}
              </span>
              <span v-if="pendingLabel.label_data?.expire_date" style="margin-left: 12px">
                保质期：<b>{{ pendingLabel.label_data.expire_date }}</b>
              </span>
            </div>
          </div>
        </template>
        <template v-else>
          <span class="probe-icon">🤖</span>
          <span class="probe-text">该设备暂无标签缓冲，将走 AI 估算保质期</span>
        </template>
      </div>

      <el-form label-width="80px">
        <el-form-item label="食材图片">
          <div style="display: flex; align-items: center; gap: 12px">
            <el-upload
              :auto-upload="false"
              :show-file-list="false"
              accept="image/jpeg,image/png,image/gif,image/webp"
              :on-change="handleImageChange"
            >
              <el-button size="small" type="primary">选择图片</el-button>
            </el-upload>
            <el-image
              v-if="imagePreview"
              :src="imagePreview"
              fit="cover"
              style="width: 60px; height: 60px; border-radius: 6px; border: 1px solid var(--border-light)"
            />
            <span v-else style="color: var(--text-secondary); font-size: 12px">未选择图片</span>
          </div>
        </el-form-item>
        <el-form-item label="食材名称">
          <el-input v-model="form.category" placeholder="如：西红柿、鸡蛋" :disabled="isEdit" />
        </el-form-item>
        <el-form-item label="置信度">
          <el-slider v-model="form.confidence" :min="0" :max="1" :step="0.05" :format-tooltip="(v: number) => Math.round(v * 100) + '%'" show-input style="width: 100%" />
          <div v-if="form.confidence < 0.6" style="margin-top: 4px; font-size: 12px; color: #ff7d00">
            <el-icon :size="12"><Warning /></el-icon> 低于0.6将自动调用视觉模型辅助识别
          </div>
        </el-form-item>
        <el-form-item label="BBox框">
          <el-input v-model="form.bbox" placeholder="x,y,w,h">
            <template #append>
              <el-button @click="form.bbox = '0,0,0,0'">快捷</el-button>
            </template>
          </el-input>
        </el-form-item>
        <el-form-item label="状态">
          <el-select v-model="form.status" style="width: 100%">
            <el-option label="在库" value="IN_STOCK" />
            <el-option label="待确认" value="OUT_PENDING" />
            <el-option label="已消耗" value="CONSUMED" />
          </el-select>
        </el-form-item>
        <el-form-item label="剩余比例">
          <el-slider v-model="form.remain_ratio" :min="0" :max="1" :step="0.05" :format-tooltip="(v: number) => Math.round(v * 100) + '%'" show-input />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showFormDialog = false">取消</el-button>
        <el-button type="primary" :loading="formLoading || imageUploading" @click="handleFormSubmit">确定</el-button>
      </template>
    </el-dialog>

    <!-- 图片预览 -->
    <el-dialog v-model="previewVisible" width="auto" :show-close="true" class="preview-dialog" @close="previewVisible = false">
      <img :src="previewUrl" style="max-width: 80vw; max-height: 80vh; display: block; margin: 0 auto; border-radius: 8px" />
    </el-dialog>

    <!-- 详情抽屉 -->
    <InventoryDetailDrawer
      v-model:visible="detailVisible"
      :item="detailItem"
      mode="admin"
      :fetch-events="fetchEventsForDrawer"
    />
  </div>
</template>

<style scoped>
.row-clickable :deep(.el-table__row) {
  cursor: pointer;
}

.pagination-bar {
  display: flex;
  justify-content: flex-end;
  margin-top: 16px;
  padding: 4px 0;
}

.label-probe {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 12px 14px;
  background: var(--bg-soft);
  border: 1px solid var(--border-light);
  border-radius: 10px;
  margin-bottom: 18px;
  font-size: 13px;
  color: var(--text-secondary);
  transition: background 0.2s, border-color 0.2s;
}

.label-probe.has-label {
  background: var(--brand-primary-soft);
  border-color: var(--brand-primary-light);
  color: var(--text-primary);
}

.probe-icon {
  font-size: 20px;
  flex-shrink: 0;
  line-height: 1;
}

.probe-body {
  flex: 1;
  min-width: 0;
}

.probe-title {
  font-size: 13px;
  color: var(--brand-primary-dark);
  display: flex;
  align-items: center;
}

.probe-detail {
  margin-top: 4px;
  font-size: 12px;
  color: var(--text-secondary);
}

.probe-detail b {
  color: var(--brand-primary-dark);
  font-weight: 600;
}

.probe-text {
  flex: 1;
  font-size: 13px;
}

.stat-card {
  display: flex;
  align-items: center;
  gap: 16px;
  padding: 20px 24px;
  background: var(--bg-card);
  border-radius: var(--radius-md);
  box-shadow: var(--shadow-sm);
  transition: box-shadow 0.2s;
}

.stat-card:hover {
  box-shadow: var(--shadow-md);
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

.link-action {
  font-size: 13px;
  color: var(--brand-primary);
  cursor: pointer;
  margin-right: 10px;
  transition: opacity 0.15s;
}
.link-action:hover {
  opacity: 0.7;
}
.link-danger {
  color: var(--el-color-danger);
}
.link-expired {
  font-size: 13px;
  color: #ff7d00;
  cursor: pointer;
  font-weight: 500;
  transition: opacity 0.15s;
}
.link-expired:hover {
  opacity: 0.7;
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

/* 库存实时事件高亮（el-table 行级类名） */
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
