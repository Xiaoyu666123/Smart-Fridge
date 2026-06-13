<script setup lang="ts">
import { ref, computed } from 'vue'
import { ElMessage } from 'element-plus'
import { detectFoods, type DetectedItem } from '@/api/admin/agent'
import { uploadInventoryImage, bulkCreateInventory } from '@/api/admin/inventory'
import { compressImage } from '@/utils/imageCompress'

const imageFile = ref<File | null>(null)
const imageDataUrl = ref('')
const imageNaturalSize = ref({ w: 0, h: 0 })

const detectLoading = ref(false)
const submitLoading = ref(false)

interface EditableItem {
  id: number
  category: string
  confidence: number
  bbox: number[]   // 相对坐标
  selected: boolean
}

const items = ref<EditableItem[]>([])
const deviceId = ref('luckfox')
const uploadedSnapshotPath = ref<string>('')

function handleUpload(file: any) {
  const f = file?.raw || file
  if (!f) return
  if (f.size > 10 * 1024 * 1024) {
    ElMessage.warning('图片大小不能超过 10MB')
    return
  }
  // 整柜识别图通常更大，给 1600 长边
  compressImage(f, { maxSide: 1600, quality: 0.85 }).then((compressed) => {
    imageFile.value = compressed
    items.value = []
    uploadedSnapshotPath.value = ''
    const reader = new FileReader()
    reader.onload = (e) => {
      imageDataUrl.value = e.target?.result as string
      const img = new Image()
      img.onload = () => {
        imageNaturalSize.value = { w: img.naturalWidth, h: img.naturalHeight }
      }
      img.src = imageDataUrl.value
    }
    reader.readAsDataURL(compressed)
  }).catch(() => {
    ElMessage.error('图片压缩失败，请换一张')
  })
}

async function runDetect() {
  if (!imageFile.value || !imageDataUrl.value) {
    ElMessage.warning('请先选择图片')
    return
  }
  detectLoading.value = true
  try {
    // 1) 上传图片到服务器（顺手保存 snapshot_path 后续入库可用）
    const upRes = await uploadInventoryImage(imageFile.value)
    uploadedSnapshotPath.value = upRes.snapshot_path

    // 2) 取 base64 主体（去掉 data:image/...;base64, 前缀）
    const b64 = imageDataUrl.value.split(',')[1]
    const res = await detectFoods(b64)

    if (!res.items || res.items.length === 0) {
      ElMessage.info('未识别到食材，可换一张更清晰的图片再试')
      items.value = []
      return
    }
    items.value = res.items.map((it: DetectedItem, i: number) => ({
      id: i,
      category: it.category,
      confidence: it.confidence,
      bbox: it.bbox,
      selected: true,
    }))
    ElMessage.success(`识别到 ${items.value.length} 个食材`)
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail || '识别失败')
  } finally {
    detectLoading.value = false
  }
}

async function submitAll() {
  const selected = items.value.filter(i => i.selected && i.category.trim())
  if (selected.length === 0) {
    ElMessage.warning('请至少选择并填写一项')
    return
  }
  if (!deviceId.value.trim()) {
    ElMessage.warning('请填写设备ID')
    return
  }
  submitLoading.value = true
  try {
    // bbox 用相对坐标 -> 像素坐标，便于和现有 FridgeMap 兼容
    const { w, h } = imageNaturalSize.value
    const payload = selected.map(it => ({
      category: it.category.trim(),
      confidence: it.confidence,
      bbox: w && h
        ? [
            Math.round(it.bbox[0] * w),
            Math.round(it.bbox[1] * h),
            Math.round(it.bbox[2] * w),
            Math.round(it.bbox[3] * h),
          ]
        : it.bbox,
      snapshot_path: uploadedSnapshotPath.value || undefined,
    }))
    const res = await bulkCreateInventory(deviceId.value.trim(), payload)
    ElMessage.success(`成功入库 ${res.created_count} 项`)
    // 入库后清空当前项
    items.value = []
    imageFile.value = null
    imageDataUrl.value = ''
    uploadedSnapshotPath.value = ''
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail || '批量入库失败')
  } finally {
    submitLoading.value = false
  }
}

function removeItem(id: number) {
  items.value = items.value.filter(i => i.id !== id)
}

function toggleAll(checked: boolean) {
  items.value.forEach(i => i.selected = checked)
}

const selectedCount = computed(() => items.value.filter(i => i.selected).length)

function bboxStyle(bbox: number[]) {
  return {
    left: (bbox[0] * 100) + '%',
    top: (bbox[1] * 100) + '%',
    width: (bbox[2] * 100) + '%',
    height: (bbox[3] * 100) + '%',
  }
}
</script>

<template>
  <div class="batch-page">
    <!-- 顶部说明 -->
    <el-alert type="info" :closable="false" show-icon style="margin-bottom: 16px">
      <template #title>
        整柜批量识别：上传一张冰箱整体照片，AI 一次性识别所有食材，确认后批量入库。
      </template>
    </el-alert>

    <div class="content-grid">
      <!-- 左：图片预览 -->
      <el-card shadow="never" class="image-card">
        <template #header>
          <div class="card-head">
            <span class="card-title">图片预览</span>
            <el-upload
              :auto-upload="false"
              :show-file-list="false"
              accept="image/*"
              :on-change="handleUpload"
            >
              <el-button size="small" type="primary">{{ imageDataUrl ? '换一张' : '选择图片' }}</el-button>
            </el-upload>
          </div>
        </template>

        <div v-if="imageDataUrl" class="image-wrap">
          <img :src="imageDataUrl" class="preview-img" />
          <!-- bbox 叠加 -->
          <div
            v-for="it in items"
            :key="it.id"
            class="bbox-overlay"
            :class="{ 'is-deselected': !it.selected }"
            :style="bboxStyle(it.bbox)"
          >
            <div class="bbox-label">{{ it.category }}</div>
          </div>
        </div>
        <div v-else class="image-empty">
          <el-icon :size="48" color="var(--text-placeholder)"><Picture /></el-icon>
          <p>请选择一张冰箱整体照片</p>
        </div>

        <div v-if="imageDataUrl" style="margin-top: 12px">
          <el-button type="primary" :loading="detectLoading" @click="runDetect" style="width: 100%">
            <el-icon><Search /></el-icon>
            {{ items.length > 0 ? '重新识别' : '开始识别' }}
          </el-button>
        </div>
      </el-card>

      <!-- 右：识别结果列表 -->
      <el-card shadow="never" class="list-card">
        <template #header>
          <div class="card-head">
            <span class="card-title">识别结果</span>
            <el-tag v-if="items.length > 0" round>已选 {{ selectedCount }} / {{ items.length }}</el-tag>
          </div>
        </template>

        <div v-if="items.length > 0">
          <div class="list-actions">
            <el-button size="small" @click="toggleAll(true)">全选</el-button>
            <el-button size="small" @click="toggleAll(false)">取消全选</el-button>
          </div>

          <div class="item-list">
            <div v-for="it in items" :key="it.id" class="item-row" :class="{ 'is-deselected': !it.selected }">
              <el-checkbox v-model="it.selected" />
              <el-input v-model="it.category" size="small" style="flex: 1" placeholder="食材名称" />
              <div class="conf-tag">{{ Math.round(it.confidence * 100) }}%</div>
              <el-button size="small" type="danger" link @click="removeItem(it.id)">
                <el-icon><Close /></el-icon>
              </el-button>
            </div>
          </div>

          <div class="submit-area">
            <el-form :inline="true" style="margin-bottom: 8px">
              <el-form-item label="设备ID">
                <el-input v-model="deviceId" size="small" placeholder="设备ID" style="width: 160px" />
              </el-form-item>
            </el-form>
            <el-button type="success" :loading="submitLoading" @click="submitAll" style="width: 100%">
              <el-icon><Check /></el-icon> 批量入库（{{ selectedCount }} 项）
            </el-button>
          </div>
        </div>

        <div v-else class="list-empty">
          <el-icon :size="36" color="var(--text-placeholder)"><Search /></el-icon>
          <p>尚未识别，请先上传图片并点击识别</p>
        </div>
      </el-card>
    </div>
  </div>
</template>

<style scoped>
.batch-page {
  display: flex;
  flex-direction: column;
}

.content-grid {
  display: grid;
  grid-template-columns: 1.4fr 1fr;
  gap: 16px;
}

.card-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.card-title {
  font-size: 15px;
  font-weight: 600;
}

.image-wrap {
  position: relative;
  width: 100%;
  border-radius: 12px;
  overflow: hidden;
  background: #000;
  display: flex;
  justify-content: center;
}

.preview-img {
  width: 100%;
  height: auto;
  max-height: 70vh;
  object-fit: contain;
  display: block;
}

.bbox-overlay {
  position: absolute;
  border: 2px solid #00b42a;
  background: rgba(0, 180, 42, 0.14);
  border-radius: 4px;
  pointer-events: none;
  transition: all 0.2s;
}

.bbox-overlay.is-deselected {
  border-color: #c9cdd4;
  background: rgba(201, 205, 212, 0.18);
  border-style: dashed;
  opacity: 0.6;
}

.bbox-label {
  position: absolute;
  top: -22px;
  left: 0;
  background: #00b42a;
  color: #fff;
  font-size: 11px;
  font-weight: 600;
  padding: 2px 6px;
  border-radius: 4px 4px 4px 0;
  white-space: nowrap;
}

.bbox-overlay.is-deselected .bbox-label {
  background: #c9cdd4;
}

.image-empty {
  text-align: center;
  padding: 60px 0;
  color: var(--text-placeholder);
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 12px;
}

.list-actions {
  display: flex;
  gap: 8px;
  margin-bottom: 12px;
}

.item-list {
  display: flex;
  flex-direction: column;
  gap: 6px;
  max-height: 50vh;
  overflow-y: auto;
}

.item-row {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 6px 8px;
  border-radius: var(--radius-sm);
  background: var(--bg-color);
}

.item-row.is-deselected {
  opacity: 0.5;
}

.conf-tag {
  font-size: 11px;
  color: var(--text-secondary);
  background: var(--bg-card);
  padding: 2px 8px;
  border-radius: 10px;
  min-width: 44px;
  text-align: center;
  font-variant-numeric: tabular-nums;
}

.submit-area {
  margin-top: 16px;
  border-top: 1px solid var(--border-color);
  padding-top: 16px;
}

.list-empty {
  text-align: center;
  padding: 60px 0;
  color: var(--text-placeholder);
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 12px;
  font-size: 13px;
}

@media (max-width: 1100px) {
  .content-grid {
    grid-template-columns: 1fr;
  }
}
</style>
