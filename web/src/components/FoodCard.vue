<script setup lang="ts">
defineProps<{
  category: string
  confidence: number
  shelfLifeDays: number
  storageAdvice: string
}>()
</script>

<template>
  <el-card shadow="never" class="food-card">
    <div class="food-header">
      <div class="food-icon">
        <el-icon :size="22" color="var(--brand-primary)"><Food /></el-icon>
      </div>
      <span class="food-name">{{ category }}</span>
    </div>
    <el-descriptions :column="1" border>
      <el-descriptions-item label="置信度">
        <el-progress :percentage="Math.round(confidence * 100)" :stroke-width="6" :color="confidence > 0.8 ? '#00b42a' : '#ff7d00'" />
      </el-descriptions-item>
      <el-descriptions-item label="保鲜天数">
        <el-tag :type="shelfLifeDays > 3 ? 'success' : shelfLifeDays > 1 ? 'warning' : 'danger'" round>
          {{ shelfLifeDays }} 天
        </el-tag>
      </el-descriptions-item>
      <el-descriptions-item label="存储建议">
        {{ storageAdvice }}
      </el-descriptions-item>
    </el-descriptions>
  </el-card>
</template>

<style scoped>
.food-card {
  border-radius: var(--radius-md) !important;
}

.food-header {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 16px;
}

.food-icon {
  width: 40px;
  height: 40px;
  border-radius: 10px;
  background: var(--brand-primary-light);
  display: flex;
  align-items: center;
  justify-content: center;
}

.food-name {
  font-size: 18px;
  font-weight: 600;
  color: var(--text-primary);
}
</style>
