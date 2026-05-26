<script setup lang="ts">
import { ref } from 'vue'
import { ElMessage } from 'element-plus'
import { recognize, type RecognizeResponse } from '@/api/agent'
import FoodCard from '@/components/FoodCard.vue'

const loading = ref(false)
const result = ref<RecognizeResponse | null>(null)
const imageUrl = ref('')

function handleUpload(uploadFile: any) {
  const file = uploadFile.raw
  if (!file) return

  if (file.size > 5 * 1024 * 1024) {
    ElMessage.warning('图片大小不能超过 5MB')
    return
  }

  imageUrl.value = URL.createObjectURL(file)

  const reader = new FileReader()
  reader.onload = async (e) => {
    const base64 = (e.target?.result as string).split(',')[1]
    loading.value = true
    try {
      result.value = await recognize({ image: base64 })
    } catch (err) {
      ElMessage.error('识别失败，请重试')
    } finally {
      loading.value = false
    }
  }
  reader.readAsDataURL(file)
}
</script>

<template>
  <div style="display: flex; gap: 20px">
    <el-card shadow="never" style="flex: 1">
      <template #header>
        <span class="card-title">上传图片</span>
      </template>
      <el-upload
        drag
        :auto-upload="false"
        :show-file-list="false"
        accept="image/*"
        @change="handleUpload"
        v-loading="loading"
        class="upload-area"
      >
        <img v-if="imageUrl" :src="imageUrl" style="max-width: 100%; max-height: 300px; object-fit: contain; border-radius: 8px" />
        <div v-else class="upload-placeholder">
          <div class="upload-icon-bg">
            <el-icon :size="28" color="var(--brand-primary)"><UploadFilled /></el-icon>
          </div>
          <div style="margin-top: 12px; color: var(--text-secondary); font-size: 14px">拖拽图片到此处，或点击上传</div>
          <div style="margin-top: 4px; color: var(--text-placeholder); font-size: 12px">支持 JPG/PNG，最大 5MB</div>
        </div>
      </el-upload>
    </el-card>

    <el-card shadow="never" style="flex: 1">
      <template #header>
        <span class="card-title">识别结果</span>
      </template>
      <div v-if="result" style="display: flex; flex-direction: column; gap: 16px">
        <FoodCard
          :category="result.category"
          :confidence="result.confidence"
          :shelf-life-days="result.shelf_life_days"
          :storage-advice="result.storage_advice"
        />
      </div>
      <div v-else class="empty-result">
        <div class="empty-icon-bg">
          <el-icon :size="28" color="var(--text-placeholder)"><Camera /></el-icon>
        </div>
        <p style="margin-top: 12px; color: var(--text-placeholder); font-size: 14px">上传图片后查看识别结果</p>
      </div>
    </el-card>
  </div>
</template>

<style scoped>
.card-title {
  font-size: 16px;
  font-weight: 600;
}

.upload-placeholder {
  padding: 40px 0;
}

.upload-icon-bg {
  width: 56px;
  height: 56px;
  border-radius: 50%;
  background: var(--brand-primary-light);
  display: flex;
  align-items: center;
  justify-content: center;
  margin: 0 auto;
}

.empty-result {
  text-align: center;
  padding: 60px 0;
}

.empty-icon-bg {
  width: 56px;
  height: 56px;
  border-radius: 50%;
  background: #f2f3f5;
  display: flex;
  align-items: center;
  justify-content: center;
  margin: 0 auto;
}
</style>
