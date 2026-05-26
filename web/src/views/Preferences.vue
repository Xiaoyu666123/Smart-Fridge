<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { getPreferences, addPreference, deletePreference, type PreferenceItem } from '@/api/agent'
import { useAuthStore } from '@/stores/auth'

const authStore = useAuthStore()
const loading = ref(false)
const items = ref<PreferenceItem[]>([])
const showAddDialog = ref(false)
const addLoading = ref(false)
const newPref = ref({ key: 'taste', value: '' })

const prefTypes = [
  { label: '口味', value: 'taste', color: '#165dff' },
  { label: '过敏', value: 'allergy', color: '#f53f3f' },
  { label: '忌口', value: 'dislike', color: '#ff7d00' },
  { label: '饮食方式', value: 'prefer', color: '#00b42a' },
]

async function fetchPreferences() {
  loading.value = true
  try {
    items.value = await getPreferences()
  } catch (e) {
    console.error(e)
  } finally {
    loading.value = false
  }
}

async function handleAdd() {
  if (!newPref.value.value.trim()) {
    ElMessage.warning('请输入偏好值')
    return
  }
  addLoading.value = true
  try {
    const saved = await addPreference({
      preference_key: newPref.value.key,
      preference_value: newPref.value.value,
    })
    items.value.push(saved)
    showAddDialog.value = false
    newPref.value = { key: 'taste', value: '' }
    ElMessage.success('添加成功')
  } catch (e) {
    ElMessage.error('添加失败，请重试')
  } finally {
    addLoading.value = false
  }
}

async function handleDelete(index: number) {
  const item = items.value[index]
  try {
    await deletePreference(item.id)
    items.value.splice(index, 1)
    ElMessage.success('删除成功')
  } catch (e) {
    ElMessage.error('删除失败，请重试')
  }
}

function getPrefTypeLabel(key: string): string {
  return prefTypes.find(t => t.value === key)?.label || key
}

function getPrefTypeColor(key: string): string {
  return prefTypes.find(t => t.value === key)?.color || '#165dff'
}

onMounted(fetchPreferences)
</script>

<template>
  <el-card shadow="never">
    <template #header>
      <div style="display: flex; align-items: center; justify-content: space-between">
        <div style="display: flex; align-items: center; gap: 12px">
          <span class="card-title">偏好设置</span>
          <el-tag size="small" round>{{ authStore.user?.username || '--' }}</el-tag>
        </div>
        <el-button type="primary" @click="showAddDialog = true">
          <el-icon><Plus /></el-icon> 添加偏好
        </el-button>
      </div>
    </template>

    <div v-if="items.length > 0" style="display: flex; flex-wrap: wrap; gap: 12px">
      <div
        v-for="(item, index) in items"
        :key="item.id"
        class="pref-chip"
      >
        <el-tag :color="getPrefTypeColor(item.preference_key)" effect="dark" size="small" round style="border: none">
          {{ getPrefTypeLabel(item.preference_key) }}
        </el-tag>
        <span class="pref-value">{{ item.preference_value }}</span>
        <span class="pref-source">{{ item.source === 'chat' ? '对话学习' : '手动' }}</span>
        <el-icon class="pref-delete" @click="handleDelete(index)"><Close /></el-icon>
      </div>
    </div>

    <el-empty v-if="items.length === 0 && !loading" description="暂无偏好设置" />

    <el-dialog v-model="showAddDialog" title="添加偏好" width="400px" :close-on-click-modal="false">
      <el-form label-width="80px">
        <el-form-item label="偏好类型">
          <el-select v-model="newPref.key" style="width: 100%">
            <el-option v-for="t in prefTypes" :key="t.value" :label="t.label" :value="t.value" />
          </el-select>
        </el-form-item>
        <el-form-item label="偏好值">
          <el-input v-model="newPref.value" placeholder="如：不吃辣、花生过敏" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showAddDialog = false">取消</el-button>
        <el-button type="primary" :loading="addLoading" @click="handleAdd">确定</el-button>
      </template>
    </el-dialog>
  </el-card>
</template>

<style scoped>
.card-title {
  font-size: 16px;
  font-weight: 600;
}

.pref-chip {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 14px;
  background: var(--bg-card);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-sm);
  transition: box-shadow 0.2s;
}

.pref-chip:hover {
  box-shadow: var(--shadow-md);
}

.pref-value {
  font-size: 14px;
  color: var(--text-primary);
}

.pref-source {
  font-size: 11px;
  color: var(--text-placeholder);
  background: #f2f3f5;
  padding: 1px 6px;
  border-radius: 4px;
}

.pref-delete {
  cursor: pointer;
  color: var(--text-placeholder);
  transition: color 0.2s;
  margin-left: 4px;
}

.pref-delete:hover {
  color: #f53f3f;
}
</style>
