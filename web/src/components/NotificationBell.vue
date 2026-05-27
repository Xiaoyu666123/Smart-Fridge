<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import {
  getNotifications,
  getNotificationCount,
  markAsRead,
  markAllAsRead,
  type NotificationItem,
} from '@/api/notification'

const router = useRouter()
const unreadCount = ref(0)
const notifications = ref<NotificationItem[]>([])
const loading = ref(false)
const popoverVisible = ref(false)

async function fetchCount() {
  try {
    const res = await getNotificationCount()
    unreadCount.value = res.unread_count
  } catch {
    // silent
  }
}

async function fetchNotifications() {
  loading.value = true
  try {
    notifications.value = await getNotifications()
  } catch {
    ElMessage.error('获取通知失败')
  } finally {
    loading.value = false
  }
}

async function handleMarkRead(item: NotificationItem) {
  try {
    await markAsRead(item.id)
    item.is_read = true
    unreadCount.value = Math.max(0, unreadCount.value - 1)
  } catch {
    ElMessage.error('标记已读失败')
  }
}

async function handleMarkAllRead() {
  try {
    await markAllAsRead()
    notifications.value.forEach((n) => (n.is_read = true))
    unreadCount.value = 0
    ElMessage.success('已全部标记已读')
  } catch {
    ElMessage.error('操作失败')
  }
}

function handleItemClick(item: NotificationItem) {
  if (!item.is_read) {
    handleMarkRead(item)
  }
  if (item.related_item_id) {
    popoverVisible.value = false
    router.push('/')
  }
}

function handlePopoverShow() {
  fetchNotifications()
}

onMounted(() => {
  fetchCount()
})

defineExpose({ fetchCount })
</script>

<template>
  <el-popover
    v-model:visible="popoverVisible"
    placement="bottom-end"
    :width="360"
    trigger="click"
    @show="handlePopoverShow"
  >
    <template #reference>
      <el-badge :value="unreadCount" :hidden="unreadCount === 0" :max="99">
        <el-icon style="font-size: 20px; cursor: pointer; color: var(--text-secondary)">
          <Bell />
        </el-icon>
      </el-badge>
    </template>

    <div class="notification-panel">
      <div class="notification-header">
        <span class="notification-title">消息通知</span>
        <el-button
          v-if="unreadCount > 0"
          type="primary"
          link
          size="small"
          @click="handleMarkAllRead"
        >
          全部已读
        </el-button>
      </div>

      <div v-loading="loading" class="notification-list">
        <div v-if="notifications.length === 0" class="notification-empty">
          暂无通知
        </div>
        <div
          v-for="item in notifications"
          :key="item.id"
          class="notification-item"
          :class="{ 'is-read': item.is_read }"
          @click="handleItemClick(item)"
        >
          <div class="notification-item-header">
            <el-tag v-if="!item.is_read" type="danger" size="small" round>未读</el-tag>
            <span class="notification-item-title">{{ item.title }}</span>
          </div>
          <div class="notification-item-content">{{ item.content }}</div>
          <div class="notification-item-time">
            {{ item.created_at ? new Date(item.created_at).toLocaleString('zh-CN') : '' }}
          </div>
        </div>
      </div>
    </div>
  </el-popover>
</template>

<style scoped>
.notification-panel {
  margin: -12px;
}

.notification-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 12px 16px;
  border-bottom: 1px solid var(--border-color);
}

.notification-title {
  font-size: 15px;
  font-weight: 600;
  color: var(--text-primary);
}

.notification-list {
  max-height: 400px;
  overflow-y: auto;
}

.notification-empty {
  padding: 40px 0;
  text-align: center;
  color: var(--text-placeholder);
  font-size: 14px;
}

.notification-item {
  padding: 12px 16px;
  cursor: pointer;
  transition: background 0.2s;
  border-bottom: 1px solid var(--border-color);
}

.notification-item:hover {
  background: var(--bg-color);
}

.notification-item.is-read {
  opacity: 0.5;
}

.notification-item-header {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 4px;
}

.notification-item-title {
  font-size: 14px;
  font-weight: 500;
  color: var(--text-primary);
}

.notification-item-content {
  font-size: 13px;
  color: var(--text-secondary);
  margin-bottom: 4px;
}

.notification-item-time {
  font-size: 12px;
  color: var(--text-placeholder);
}
</style>
