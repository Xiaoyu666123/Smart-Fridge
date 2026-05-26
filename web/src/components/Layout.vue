<script setup lang="ts">
import { ref, computed } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { useAuthStore } from '@/stores/auth'

const router = useRouter()
const route = useRoute()
const authStore = useAuthStore()
authStore.loadFromStorage()

const isCollapse = ref(false)

const allMenuItems = [
  { path: '/', icon: 'Box', title: '库存概览', admin: false },
  { path: '/chat', icon: 'ChatDotRound', title: 'AI 食谱推荐', admin: false },
  { path: '/recognize', icon: 'Camera', title: '食材识别', admin: false },
  { path: '/preferences', icon: 'Setting', title: '偏好设置', admin: false },
  { path: '/environment', icon: 'Sunny', title: '环境信息', admin: false },
  { path: '/agent', icon: 'Cpu', title: 'Agent 管理', admin: true },
  { path: '/workflow', icon: 'Connection', title: '工作流管理', admin: true },
  { path: '/logs', icon: 'Document', title: '系统日志', admin: true },
]

const menuItems = computed(() => {
  if (authStore.isAdmin) return allMenuItems
  return allMenuItems.filter(item => !item.admin)
})

const pageTitle = computed(() => route.meta.title || 'SMART-FRIDGE')

function handleMenuSelect(path: string) {
  router.push(path)
}

function handleLogout() {
  authStore.logout()
  router.push('/login')
}
</script>

<template>
  <el-container style="height: 100vh">
    <el-aside :width="isCollapse ? '64px' : '220px'" class="sidebar">
      <div class="sidebar-logo">
        <img src="/logo.jpg" alt="logo" class="logo-img" />
        <span v-if="!isCollapse" class="logo-text">SMART-FRIDGE</span>
      </div>
      <el-menu
        :default-active="route.path"
        :collapse="isCollapse"
        background-color="transparent"
        text-color="var(--sidebar-text)"
        active-text-color="var(--sidebar-active)"
        @select="handleMenuSelect"
      >
        <el-menu-item v-for="item in menuItems" :key="item.path" :index="item.path">
          <el-icon><component :is="item.icon" /></el-icon>
          <template #title>{{ item.title }}</template>
        </el-menu-item>
      </el-menu>

      <div class="sidebar-footer">
        <div v-if="!isCollapse" class="user-info" @click="handleLogout">
          <el-icon><User /></el-icon>
          <span class="user-name">{{ authStore.user?.username || '--' }}</span>
          <el-tag v-if="authStore.isAdmin" type="danger" size="small" round>管理员</el-tag>
          <el-icon class="logout-icon"><SwitchButton /></el-icon>
        </div>
        <div v-else class="user-info-collapsed" @click="handleLogout">
          <el-icon><SwitchButton /></el-icon>
        </div>
      </div>
    </el-aside>

    <el-container>
      <el-header class="top-header">
        <div style="display: flex; align-items: center; gap: 12px">
          <el-icon style="cursor: pointer; font-size: 20px; color: var(--text-secondary)" @click="isCollapse = !isCollapse">
            <Fold v-if="!isCollapse" />
            <Expand v-else />
          </el-icon>
          <span class="page-title">{{ pageTitle }}</span>
        </div>
      </el-header>

      <el-main style="padding: 20px; background: var(--bg-color)">
        <router-view />
      </el-main>
    </el-container>
  </el-container>
</template>

<style scoped>
.sidebar {
  transition: width 0.3s;
  background: var(--sidebar-bg);
  border-right: 1px solid var(--border-color);
  display: flex;
  flex-direction: column;
}

.sidebar-logo {
  height: 60px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-bottom: 1px solid var(--border-color);
  overflow: hidden;
}

.logo-img {
  width: 32px;
  height: 32px;
  border-radius: 8px;
  object-fit: cover;
  flex-shrink: 0;
}

.logo-text {
  font-size: 18px;
  font-weight: 700;
  color: var(--brand-primary);
  letter-spacing: 1px;
  margin-left: 8px;
}

.sidebar-footer {
  margin-top: auto;
  border-top: 1px solid var(--border-color);
  padding: 12px;
}

.user-info {
  display: flex;
  align-items: center;
  gap: 8px;
  cursor: pointer;
  padding: 8px 10px;
  border-radius: var(--radius-sm);
  transition: background 0.2s;
  color: var(--text-secondary);
  font-size: 13px;
}

.user-info:hover {
  background: var(--bg-color);
}

.user-name {
  flex: 1;
  color: var(--text-primary);
  font-weight: 500;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.logout-icon {
  color: var(--text-placeholder);
  transition: color 0.2s;
}

.user-info:hover .logout-icon {
  color: #f53f3f;
}

.user-info-collapsed {
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  padding: 8px;
  border-radius: var(--radius-sm);
  color: var(--text-placeholder);
  transition: color 0.2s;
}

.user-info-collapsed:hover {
  color: #f53f3f;
}

.top-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  border-bottom: 1px solid var(--border-color);
  background: var(--bg-card);
  box-shadow: var(--shadow-sm);
}

.page-title {
  font-size: 16px;
  font-weight: 600;
  color: var(--text-primary);
}

.el-menu {
  border-right: none;
  padding: 8px;
}
</style>
