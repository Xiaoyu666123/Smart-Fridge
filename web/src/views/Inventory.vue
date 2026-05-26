<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import type { UploadFile } from 'element-plus'
import { getInventoryList, getCategories, createInventory, updateInventory, deleteInventory, uploadInventoryImage, type InventoryItem } from '@/api/inventory'
import { useAuthStore } from '@/stores/auth'

const authStore = useAuthStore()
const isAdmin = computed(() => authStore.isAdmin)

const loading = ref(false)
const items = ref<InventoryItem[]>([])
const categories = ref<string[]>([])
const filterDeviceId = ref('')
const filterStatus = ref('')
const filterCategory = ref('')

// CRUD dialog
const showFormDialog = ref(false)
const formLoading = ref(false)
const isEdit = ref(false)
const editId = ref('')
const form = ref({
  device_id: '',
  category: '',
  status: 'IN_STOCK',
  remain_ratio: 1.0,
  snapshot_path: '',
})
const imageFile = ref<File | null>(null)
const imagePreview = ref('')
const imageUploading = ref(false)
const previewVisible = ref(false)
const previewUrl = ref('')
let refreshTimer: ReturnType<typeof setTimeout> | null = null

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
    const params: Record<string, string> = {}
    if (filterDeviceId.value) params.device_id = filterDeviceId.value
    if (filterStatus.value) params.status = filterStatus.value
    if (filterCategory.value) params.category = filterCategory.value
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
  form.value = { device_id: '', category: '', status: 'IN_STOCK', remain_ratio: 1.0, snapshot_path: '' }
  imageFile.value = null
  imagePreview.value = ''
  showFormDialog.value = true
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
  }
  imageFile.value = null
  imagePreview.value = row.snapshot_path ? getSnapshotUrl(row.snapshot_path) : ''
  showFormDialog.value = true
}

function handleImageChange(uploadFile: UploadFile) {
  if (!uploadFile.raw) return
  imageFile.value = uploadFile.raw
  const reader = new FileReader()
  reader.onload = (e) => { imagePreview.value = e.target?.result as string }
  reader.readAsDataURL(uploadFile.raw)
}

function openPreview(row: InventoryItem) {
  previewUrl.value = getSnapshotUrl(row.snapshot_path)
  previewVisible.value = true
}

function getSnapshotUrl(path: string | null | undefined): string {
  if (!path) return ''
  if (path.startsWith('http')) return path
  const filename = path.replace(/\\/g, '/').split('/').pop() || ''
  return `/uploads/${filename}`
}

async function handleFormSubmit() {
  if (!form.value.category.trim() || !form.value.device_id.trim()) {
    ElMessage.warning('请填写食材名称和设备ID')
    return
  }
  formLoading.value = true
  try {
    let snapshotPath = form.value.snapshot_path
    if (imageFile.value) {
      imageUploading.value = true
      const uploadResult = await uploadInventoryImage(imageFile.value)
      snapshotPath = uploadResult.snapshot_path
      imageUploading.value = false
    }
    if (isEdit.value) {
      await updateInventory(editId.value, {
        category: form.value.category,
        status: form.value.status,
        remain_ratio: form.value.remain_ratio,
        snapshot_path: snapshotPath || undefined,
      })
      ElMessage.success('修改成功')
    } else {
      await createInventory({
        device_id: form.value.device_id,
        category: form.value.category,
        status: form.value.status,
        remain_ratio: form.value.remain_ratio,
        snapshot_path: snapshotPath || undefined,
      })
      ElMessage.success('添加成功')
    }
    showFormDialog.value = false
    fetchCategories()
    await fetchInventory()
    if (!isEdit.value && hasComputingItems()) startRefreshPoll()
  } catch (e: any) {
    const detail = e?.response?.data?.detail
    if (detail) {
      ElMessage.warning(detail)
    } else {
      ElMessage.error(isEdit.value ? '修改失败' : '添加失败')
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
    await deleteInventory(row.id)
    ElMessage.success('删除成功')
    fetchInventory()
  } catch (e) {
    if (e !== 'cancel') {
      ElMessage.error('删除失败')
    }
  }
}

onMounted(() => {
  fetchCategories()
  fetchInventory().then(() => {
    if (hasComputingItems()) startRefreshPoll()
  })
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
        <el-form-item label="设备ID">
          <el-input v-model="filterDeviceId" placeholder="输入设备ID" clearable style="width: 200px" />
        </el-form-item>
        <el-form-item label="状态">
          <el-select v-model="filterStatus" placeholder="选择状态" clearable style="width: 160px">
            <el-option label="在库" value="IN_STOCK" />
            <el-option label="待确认" value="OUT_PENDING" />
            <el-option label="已消耗" value="CONSUMED" />
          </el-select>
        </el-form-item>
        <el-form-item label="食材种类">
          <el-select v-model="filterCategory" placeholder="选择种类" clearable filterable style="width: 160px">
            <el-option v-for="cat in categories" :key="cat" :label="cat" :value="cat" />
          </el-select>
        </el-form-item>
        <el-form-item>
          <el-button type="primary" @click="fetchInventory">查询</el-button>
        </el-form-item>
        <el-form-item v-if="isAdmin">
          <el-button type="success" @click="handleAdd">
            <el-icon><Plus /></el-icon> 添加食材
          </el-button>
        </el-form-item>
      </el-form>
    </el-card>

    <!-- 表格 -->
    <el-card shadow="never">
      <el-table :data="items" v-loading="loading" stripe>
        <el-table-column label="图片" width="80">
          <template #default="{ row }">
            <img
              v-if="row.snapshot_path"
              :src="getSnapshotUrl(row.snapshot_path)"
              @click="openPreview(row)"
              style="width: 50px; height: 50px; border-radius: 6px; object-fit: cover; cursor: pointer"
            />
            <span v-else style="color: var(--text-secondary); font-size: 12px">无图</span>
          </template>
        </el-table-column>
        <el-table-column prop="category" label="食材名称" width="120" />
        <el-table-column prop="device_id" label="设备ID" width="180" />
        <el-table-column prop="status" label="状态" width="100">
          <template #default="{ row }">
            <el-tag :type="row.status === 'IN_STOCK' ? 'success' : row.status === 'OUT_PENDING' ? 'warning' : 'info'" round>
              {{ row.status === 'IN_STOCK' ? '在库' : row.status === 'OUT_PENDING' ? '待确认' : '已消耗' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="保鲜状态" width="120">
          <template #default="{ row }">
            <el-tag v-if="!row.agent_metadata?.expire_at" type="info" round>
              计算中...
            </el-tag>
            <el-tag v-else :type="getStatusType(row)" round>
              {{ getRemainDays(row) >= 0 ? `${getRemainDays(row)} 天` : '未知' }}
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
        <el-table-column v-if="isAdmin" label="操作" width="150" fixed="right">
          <template #default="{ row }">
            <el-button size="small" type="primary" link @click="handleEdit(row)">编辑</el-button>
            <el-button size="small" type="danger" link @click="handleDelete(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <!-- 添加/编辑弹窗 -->
    <el-dialog v-model="showFormDialog" :title="isEdit ? '编辑食材' : '添加食材'" width="500px" :close-on-click-modal="false">
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
        <el-form-item label="设备ID">
          <el-input v-model="form.device_id" placeholder="输入设备ID" :disabled="isEdit" />
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
  </div>
</template>

<style scoped>
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
</style>
