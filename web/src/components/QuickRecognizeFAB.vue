<script setup lang="ts">
/**
 * 全局浮动快速识别面板（admin 端）。
 * 点右下角圆形按钮 → 弹出抽屉：上传图片 → 调云端 detect → 显示识别结果 → 一键入库。
 */
import { ref, computed } from 'vue'
import { ElMessage } from 'element-plus'
import { useRoute } from 'vue-router'
import { detectFoods, type DetectedItem } from '@/api/admin/agent'
import { bulkCreateInventory, uploadInventoryImage } from '@/api/admin/inventory'
import { compressImage } from '@/utils/imageCompress'

const route = useRoute()

// 仅 admin 端显示
const visible = computed(() => {
  return !!localStorage.getItem('admin_token') && route.path.startsWith('/admin')
})

const drawerOpen = ref(false)
const imageFile = ref<File | null>(null)
const imagePreview = ref<string>('')
const detecting = ref(false)
const submitting = ref(false)
const detected = ref<DetectedItem[]>([])
const selected = ref<Set<number>>(new Set())
const deviceId = ref('luckfox')

function openDrawer() {
  drawerOpen.value = true
  reset()
}

function reset() {
  imageFile.value = null
  imagePreview.value = ''
  detected.value = []
  selected.value = new Set()
}

function fileToDataURL(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader()
    reader.onload = () => resolve(reader.result as string)
    reader.onerror = () => reject(new Error('读取文件失败'))
    reader.readAsDataURL(file)
  })
}

async function handleFile(e: Event) {
  const input = e.target as HTMLInputElement
  const f = input.files?.[0]
  if (!f) return
  try {
    const compressed = await compressImage(f)
    imageFile.value = compressed
    imagePreview.value = await fileToDataURL(compressed)
    detected.value = []
    selected.value = new Set()
  } catch {
    imageFile.value = f
    imagePreview.value = await fileToDataURL(f)
  }
}

async function runDetect() {
  if (!imageFile.value) {
    ElMessage.warning('请先选一张图片')
    return
  }
  detecting.value = true
  try {
    const dataUrl = await fileToDataURL(imageFile.value)
    const b64 = dataUrl.split(',')[1] || ''
    const res = await detectFoods(b64)
    detected.value = res.items || []
    // 默认全选
    selected.value = new Set(detected.value.map((_, i) => i))
    if (detected.value.length === 0) {
      ElMessage.info('未识别到食材，可以换一张图')
    } else {
      ElMessage.success(`识别到 ${detected.value.length} 个食材`)
    }
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail || '识别失败')
  } finally {
    detecting.value = false
  }
}

function toggleSelect(idx: number) {
  if (selected.value.has(idx)) {
    selected.value.delete(idx)
  } else {
    selected.value.add(idx)
  }
  selected.value = new Set(selected.value)
}

async function submitAll() {
  const picks = detected.value.filter((_, i) => selected.value.has(i))
  if (picks.length === 0) {
    ElMessage.warning('请至少勾选一项')
    return
  }
  if (!imageFile.value) return
  submitting.value = true
  try {
    // 上传一次图，所有项共用 snapshot_path
    const uploaded = await uploadInventoryImage(imageFile.value)
    const items = picks.map(it => ({
      category: it.category,
      confidence: it.confidence,
      bbox: it.bbox?.length === 4 ? it.bbox.map(Math.round) : [0, 0, 0, 0],
      snapshot_path: (uploaded.snapshot_path || '').replace(/\\/g, '/'),
    }))
    const res = await bulkCreateInventory(deviceId.value, items)
    ElMessage.success(`✓ 入库成功 ${res.created_count} 项`)
    drawerOpen.value = false
    reset()
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail || '入库失败')
  } finally {
    submitting.value = false
  }
}
</script>

<template>
  <div v-if="visible">
    <!-- FAB -->
    <button class="fab" @click="openDrawer" title="快速识别 (Alt+Q)">
      <el-icon :size="22" color="#fff"><Camera /></el-icon>
      <span class="fab-pulse"></span>
    </button>

    <!-- 抽屉 -->
    <el-drawer
      v-model="drawerOpen"
      direction="rtl"
      :size="420"
      :with-header="false"
    >
      <div class="qr-panel">
        <div class="qr-header">
          <div class="qr-title">
            <el-icon :size="20" color="var(--brand-primary)"><Camera /></el-icon>
            <span>快速识别入库</span>
          </div>
          <el-icon class="qr-close" :size="18" @click="drawerOpen = false"><Close /></el-icon>
        </div>

        <!-- 设备 -->
        <el-form-item label="设备 ID" class="qr-device">
          <el-input v-model="deviceId" size="small" placeholder="luckfox" />
        </el-form-item>

        <!-- 图片选择区 -->
        <div class="qr-upload">
          <label class="qr-upload-label">
            <input
              type="file"
              accept="image/*"
              capture="environment"
              style="display: none"
              @change="handleFile"
            />
            <div v-if="!imagePreview" class="qr-upload-empty">
              <el-icon :size="36" color="var(--text-placeholder)"><UploadFilled /></el-icon>
              <span>点击拍照或选择图片</span>
              <span class="qr-upload-tip">手机端会自动调用摄像头</span>
            </div>
            <img v-else :src="imagePreview" class="qr-upload-img" />
          </label>
        </div>

        <!-- 操作按钮 -->
        <div class="qr-actions">
          <el-button
            type="primary"
            :loading="detecting"
            :disabled="!imagePreview"
            @click="runDetect"
            class="qr-btn-detect"
          >
            <el-icon v-if="!detecting"><Search /></el-icon>
            {{ detecting ? '识别中…' : '识别食材' }}
          </el-button>
        </div>

        <!-- 识别结果 -->
        <div v-if="detected.length > 0" class="qr-results">
          <div class="qr-results-head">
            识别到 <strong>{{ detected.length }}</strong> 个食材，已勾选 <strong>{{ selected.size }}</strong> 个
          </div>
          <div class="qr-list">
            <div
              v-for="(it, i) in detected"
              :key="i"
              class="qr-item"
              :class="{ active: selected.has(i) }"
              @click="toggleSelect(i)"
            >
              <div class="qr-item-check">
                <el-icon v-if="selected.has(i)" :size="14" color="#fff"><Check /></el-icon>
              </div>
              <div class="qr-item-body">
                <div class="qr-item-name">{{ it.category }}</div>
                <div class="qr-item-meta">
                  置信度 {{ (it.confidence * 100).toFixed(0) }}%
                </div>
              </div>
              <el-tag
                size="small"
                :type="it.confidence >= 0.8 ? 'success' : it.confidence >= 0.5 ? 'warning' : 'danger'"
                round
              >
                {{ it.confidence >= 0.8 ? '高' : it.confidence >= 0.5 ? '中' : '低' }}
              </el-tag>
            </div>
          </div>
          <el-button
            type="success"
            :loading="submitting"
            :disabled="selected.size === 0"
            @click="submitAll"
            class="qr-btn-submit"
          >
            <el-icon v-if="!submitting"><Plus /></el-icon>
            一键入库（{{ selected.size }} 项）
          </el-button>
        </div>

        <!-- 提示 -->
        <div class="qr-tip">
          <el-icon :size="13"><InfoFilled /></el-icon>
          已自动调用云端整柜识别。多个食材一次性入库，会自动去重。
        </div>
      </div>
    </el-drawer>
  </div>
</template>

<style scoped>
.fab {
  position: fixed;
  right: 24px;
  bottom: 24px;
  z-index: 999;
  width: 56px;
  height: 56px;
  border-radius: 50%;
  border: none;
  cursor: pointer;
  background: linear-gradient(135deg, var(--brand-primary), var(--brand-primary-dark));
  box-shadow: 0 8px 24px rgba(14, 165, 233, 0.45);
  display: flex;
  align-items: center;
  justify-content: center;
  transition: transform 0.2s ease, box-shadow 0.2s ease;
}

.fab:hover {
  transform: translateY(-2px) scale(1.05);
  box-shadow: 0 12px 30px rgba(14, 165, 233, 0.55);
}

.fab:active {
  transform: scale(0.96);
}

.fab-pulse {
  position: absolute;
  inset: 0;
  border-radius: 50%;
  border: 2px solid var(--brand-primary);
  opacity: 0;
  animation: fab-ring 2.4s ease-out infinite;
}

@keyframes fab-ring {
  0%   { transform: scale(1); opacity: 0.6; }
  100% { transform: scale(1.4); opacity: 0; }
}

/* 抽屉 */
.qr-panel {
  padding: 18px 20px 28px;
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.qr-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.qr-title {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 16px;
  font-weight: 700;
  color: var(--text-primary);
}

.qr-close {
  cursor: pointer;
  color: var(--text-placeholder);
  transition: color 0.18s;
}

.qr-close:hover {
  color: var(--text-primary);
}

.qr-device {
  margin-bottom: 0 !important;
}

.qr-device :deep(.el-form-item__label) {
  font-size: 12px;
}

.qr-upload {
  width: 100%;
}

.qr-upload-label {
  display: block;
  cursor: pointer;
}

.qr-upload-empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 6px;
  padding: 40px 12px;
  border: 2px dashed var(--border-color);
  border-radius: 12px;
  background: var(--bg-soft);
  color: var(--text-secondary);
  font-size: 14px;
  transition: border-color 0.2s;
}

.qr-upload-empty:hover {
  border-color: var(--brand-primary);
  color: var(--brand-primary-dark);
}

.qr-upload-tip {
  font-size: 11px;
  color: var(--text-placeholder);
}

.qr-upload-img {
  width: 100%;
  max-height: 220px;
  object-fit: cover;
  border-radius: 12px;
  border: 1px solid var(--border-color);
}

.qr-actions {
  display: flex;
  gap: 8px;
}

.qr-btn-detect {
  width: 100%;
  background: linear-gradient(135deg, var(--brand-primary), var(--brand-primary-dark)) !important;
  border-color: transparent !important;
  font-weight: 600;
}

.qr-results {
  display: flex;
  flex-direction: column;
  gap: 10px;
  padding: 12px 14px;
  background: var(--bg-card);
  border: 1px solid var(--border-color);
  border-radius: 12px;
}

.qr-results-head {
  font-size: 12px;
  color: var(--text-secondary);
}

.qr-results-head strong {
  color: var(--brand-primary-dark);
  font-weight: 700;
}

.qr-list {
  display: flex;
  flex-direction: column;
  gap: 6px;
  max-height: 280px;
  overflow-y: auto;
}

.qr-item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 12px;
  border-radius: 10px;
  border: 1px solid var(--border-color);
  background: var(--bg-card);
  cursor: pointer;
  transition: all 0.15s;
}

.qr-item:hover {
  border-color: var(--brand-primary);
}

.qr-item.active {
  background: var(--brand-primary-soft);
  border-color: var(--brand-primary);
}

.qr-item-check {
  width: 20px;
  height: 20px;
  border-radius: 50%;
  border: 1.5px solid var(--border-color);
  background: var(--bg-card);
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  transition: all 0.15s;
}

.qr-item.active .qr-item-check {
  background: var(--brand-primary);
  border-color: var(--brand-primary);
}

.qr-item-body {
  flex: 1;
  min-width: 0;
}

.qr-item-name {
  font-size: 14px;
  font-weight: 600;
  color: var(--text-primary);
}

.qr-item-meta {
  font-size: 11px;
  color: var(--text-placeholder);
  margin-top: 2px;
}

.qr-btn-submit {
  width: 100%;
}

.qr-tip {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  font-size: 11px;
  color: var(--text-placeholder);
  padding: 8px 0;
}
</style>
