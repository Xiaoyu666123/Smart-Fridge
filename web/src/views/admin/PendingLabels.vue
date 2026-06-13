<script setup lang="ts">
import { ref, computed, onMounted, onBeforeUnmount } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { listPendingLabels, deletePendingLabel, scanLabel, type PendingLabelItem } from '@/api/admin/pendingLabel'
import { compressImage } from '@/utils/imageCompress'
import { uploadUrl } from '@/config/env'

const loading = ref(false)
const labels = ref<PendingLabelItem[]>([])
const filterStatus = ref('')

// 手动扫描标签（演示/调试用）
const showScanDialog = ref(false)
const scanLoading = ref(false)
const scanForm = ref({ ttl_seconds: 300 })
const scanFile = ref<File | null>(null)
const scanPreview = ref('')
const lastScanResult = ref<any>(null)

let timer: ReturnType<typeof setInterval> | null = null

async function fetchData() {
  loading.value = true
  try {
    const params: Record<string, any> = { limit: 100 }
    if (filterStatus.value) params.status = filterStatus.value
    labels.value = await listPendingLabels(params)
  } catch (e) {
    console.error(e)
  } finally {
    loading.value = false
  }
}

function statusType(s: string): string {
  if (s === 'pending') return 'warning'
  if (s === 'consumed') return 'success'
  return 'info'
}

function statusLabel(s: string): string {
  if (s === 'pending') return '待关联'
  if (s === 'consumed') return '已关联'
  return '已过期'
}

function getSnapshotUrl(path: string | null | undefined): string {
  return uploadUrl(path)
}

function formatDate(s: string | null): string {
  if (!s) return '-'
  return new Date(s).toLocaleString('zh-CN')
}

function expireCountdown(s: string | null): string {
  if (!s) return '-'
  const ms = new Date(s).getTime() - Date.now()
  if (ms <= 0) return '已过期'
  const sec = Math.floor(ms / 1000)
  if (sec < 60) return `${sec}s 后`
  const min = Math.floor(sec / 60)
  return `${min}m ${sec % 60}s 后`
}

const stats = computed(() => ({
  total: labels.value.length,
  pending: labels.value.filter(l => l.status === 'pending').length,
  consumed: labels.value.filter(l => l.status === 'consumed').length,
  expired: labels.value.filter(l => l.status === 'expired').length,
}))

async function handleDelete(item: PendingLabelItem) {
  try {
    await ElMessageBox.confirm(`确定删除该标签缓冲？`, '删除确认', {
      confirmButtonText: '删除', cancelButtonText: '取消', type: 'warning',
    })
    await deletePendingLabel(item.id)
    ElMessage.success('已删除')
    fetchData()
  } catch (e) {
    if (e === 'cancel') return
    ElMessage.error('删除失败')
  }
}

function handleFileChange(file: any) {
  const f = file?.raw || file
  if (!f) return
  compressImage(f).then((compressed) => {
    scanFile.value = compressed
    const reader = new FileReader()
    reader.onload = (e) => {
      scanPreview.value = (e.target?.result as string) || ''
    }
    reader.readAsDataURL(compressed)
  }).catch(() => {
    ElMessage.error('图片处理失败')
  })
}

async function handleScan() {
  if (!scanFile.value) {
    ElMessage.warning('请先选择标签图')
    return
  }
  scanLoading.value = true
  try {
    const b64 = scanPreview.value.split(',')[1]
    const res = await scanLabel({
      label_image: b64,
      ttl_seconds: scanForm.value.ttl_seconds,
    } as any)
    lastScanResult.value = res
    ElMessage.success('已扫描入缓冲，' + (res.label_data?.brand || '未识别到品牌'))
    fetchData()
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail || '扫描失败')
  } finally {
    scanLoading.value = false
  }
}

onMounted(() => {
  fetchData()
  // 每 10 秒自动刷新一次倒计时
  timer = setInterval(() => {
    // 触发 reactivity（status 由后端计算，倒计时由前端实时算）
    labels.value = [...labels.value]
  }, 1000)
})

onBeforeUnmount(() => {
  if (timer) clearInterval(timer)
})
</script>

<template>
  <div>
    <!-- 顶部说明 -->
    <el-alert type="info" :closable="false" show-icon style="margin-bottom: 16px">
      <template #title>
        端侧扫到食品标签后会先 POST 到 <code>/events/label_scan</code>，后端 OCR 解析后写入缓冲表；
        同设备下一次 ITEM_IN 入库时会自动关联最近未消费的一条。
      </template>
    </el-alert>

    <!-- 统计 -->
    <div class="stat-row">
      <div class="stat-card">
        <div class="stat-icon" style="background: var(--brand-primary-light); color: var(--brand-primary-dark)">
          <el-icon :size="20"><CollectionTag /></el-icon>
        </div>
        <div>
          <div class="stat-value">{{ stats.total }}</div>
          <div class="stat-label">总记录</div>
        </div>
      </div>
      <div class="stat-card">
        <div class="stat-icon" style="background: #fff7ed; color: var(--brand-secondary)">
          <el-icon :size="20"><Timer /></el-icon>
        </div>
        <div>
          <div class="stat-value">{{ stats.pending }}</div>
          <div class="stat-label">待关联</div>
        </div>
      </div>
      <div class="stat-card">
        <div class="stat-icon" style="background: var(--brand-primary-light); color: var(--brand-primary-dark)">
          <el-icon :size="20"><CircleCheck /></el-icon>
        </div>
        <div>
          <div class="stat-value">{{ stats.consumed }}</div>
          <div class="stat-label">已关联</div>
        </div>
      </div>
      <div class="stat-card">
        <div class="stat-icon" style="background: #f0f5f3; color: var(--text-secondary)">
          <el-icon :size="20"><Close /></el-icon>
        </div>
        <div>
          <div class="stat-value">{{ stats.expired }}</div>
          <div class="stat-label">已过期</div>
        </div>
      </div>
    </div>

    <!-- 操作 -->
    <el-card shadow="never" style="margin-bottom: 16px">
      <el-form :inline="true">
        <el-form-item label="状态">
          <el-select v-model="filterStatus" placeholder="全部" clearable style="width: 140px">
            <el-option label="待关联" value="pending" />
            <el-option label="已关联" value="consumed" />
            <el-option label="已过期" value="expired" />
          </el-select>
        </el-form-item>
        <el-form-item>
          <el-button type="primary" @click="fetchData">查询</el-button>
        </el-form-item>
        <el-form-item>
          <el-button @click="showScanDialog = true; lastScanResult = null">
            <el-icon><Upload /></el-icon> 模拟扫描标签（调试）
          </el-button>
        </el-form-item>
      </el-form>
    </el-card>

    <!-- 列表 -->
    <el-card shadow="never">
      <el-table :data="labels" v-loading="loading" stripe>
        <el-table-column label="标签图" width="80">
          <template #default="{ row }">
            <img v-if="row.label_image_path" :src="getSnapshotUrl(row.label_image_path)"
                 style="width: 48px; height: 48px; border-radius: 6px; object-fit: cover" />
            <span v-else style="color: var(--text-placeholder); font-size: 12px">无</span>
          </template>
        </el-table-column>
        <el-table-column label="状态" width="100">
          <template #default="{ row }">
            <el-tag :type="statusType(row.status)" round size="small">
              {{ statusLabel(row.status) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="品牌" width="120">
          <template #default="{ row }">
            <span v-if="row.label_data?.brand">{{ row.label_data.brand }}</span>
            <span v-else style="color: var(--text-placeholder)">-</span>
          </template>
        </el-table-column>
        <el-table-column label="产品" min-width="150">
          <template #default="{ row }">
            <span v-if="row.label_data?.product_name">{{ row.label_data.product_name }}</span>
            <span v-else style="color: var(--text-placeholder)">-</span>
          </template>
        </el-table-column>
        <el-table-column label="保质期截止" width="130">
          <template #default="{ row }">
            <span v-if="row.label_data?.expire_date" style="color: var(--brand-primary-dark); font-weight: 600">
              {{ row.label_data.expire_date }}
            </span>
            <span v-else style="color: var(--text-placeholder)">-</span>
          </template>
        </el-table-column>
        <el-table-column label="创建时间" width="170">
          <template #default="{ row }">{{ formatDate(row.created_at) }}</template>
        </el-table-column>
        <el-table-column label="过期" width="120">
          <template #default="{ row }">
            <span v-if="row.status === 'pending'" style="color: var(--brand-secondary); font-weight: 600">
              {{ expireCountdown(row.expires_at) }}
            </span>
            <span v-else-if="row.status === 'consumed'" style="color: var(--brand-primary-dark)">已消费</span>
            <span v-else style="color: var(--text-placeholder)">已过期</span>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="80" fixed="right">
          <template #default="{ row }">
            <el-button type="danger" link size="small" @click="handleDelete(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <!-- 模拟扫描对话框 -->
    <el-dialog v-model="showScanDialog" title="模拟扫描标签" width="520px">
      <el-form label-width="90px">
        <el-form-item label="缓冲时间">
          <el-input-number v-model="scanForm.ttl_seconds" :min="60" :max="3600" :step="60" />
          <span style="margin-left: 8px; color: var(--text-secondary); font-size: 12px">秒</span>
        </el-form-item>
        <el-form-item label="标签图">
          <el-upload :auto-upload="false" :show-file-list="false" accept="image/*" :on-change="handleFileChange">
            <el-button type="primary" size="small">选择图片</el-button>
          </el-upload>
          <div v-if="scanPreview" style="margin-top: 12px">
            <img :src="scanPreview" style="max-width: 100%; max-height: 200px; border-radius: 8px" />
          </div>
        </el-form-item>
      </el-form>

      <div v-if="lastScanResult" class="result-box">
        <div class="result-title">解析结果</div>
        <pre>{{ JSON.stringify(lastScanResult, null, 2) }}</pre>
      </div>

      <template #footer>
        <el-button @click="showScanDialog = false">关闭</el-button>
        <el-button type="primary" :loading="scanLoading" @click="handleScan">扫描入缓冲</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped>
.stat-row {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
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
  width: 40px;
  height: 40px;
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

.result-box {
  margin-top: 16px;
  padding: 12px 14px;
  background: var(--bg-soft);
  border-radius: 10px;
  border: 1px solid var(--border-light);
}

.result-title {
  font-size: 13px;
  font-weight: 600;
  color: var(--text-primary);
  margin-bottom: 8px;
}

.result-box pre {
  margin: 0;
  font-size: 12px;
  font-family: 'SFMono-Regular', Consolas, monospace;
  color: var(--text-primary);
  max-height: 240px;
  overflow: auto;
}
</style>
