<script setup lang="ts">
import { ref, computed } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { useUserAuthStore } from '@/stores/userAuth'
import { useThemeStore } from '@/stores/theme'
import NotificationBell from './NotificationBell.vue'
import OnboardingTour from './OnboardingTour.vue'

const router = useRouter()
const route = useRoute()
const authStore = useUserAuthStore()
const themeStore = useThemeStore()
authStore.loadFromStorage()

const isCollapse = ref(false)
const tourRef = ref<InstanceType<typeof OnboardingTour> | null>(null)

// 暴露给全局命令面板：window.__startOnboarding()
if (typeof window !== 'undefined') {
  ;(window as any).__startOnboarding = () => tourRef.value?.startTour()
}

const menuItems = [
  { path: '/user/home', icon: 'House', title: '首页' },
  { path: '/user/inventory', icon: 'Box', title: '库存查看' },
  { path: '/user/expiring', icon: 'AlarmClock', title: '临期处理' },
  { path: '/user/fridge-map', icon: 'Grid', title: '冰箱视图' },
  { path: '/user/chat', icon: 'ChatDotRound', title: 'AI对话' },
  { path: '/user/recipes', icon: 'Star', title: '我的食谱' },
  { path: '/user/shopping', icon: 'ShoppingCart', title: '购物清单' },
  { path: '/user/nutrition', icon: 'Apple', title: '健康饮食' },
  { path: '/user/recognize', icon: 'Camera', title: '食材识别' },
  { path: '/user/preferences', icon: 'Setting', title: '偏好设置' },
  { path: '/user/achievements', icon: 'Medal', title: '我的成就' },
  { path: '/user/environment', icon: 'Sunny', title: '查看天气' },
]

const pageTitle = computed(() => route.meta.title || 'SMART-FRIDGE')

const userInitial = computed(() => {
  const name = authStore.user?.username || ''
  return name.charAt(0).toUpperCase() || '?'
})

function handleMenuSelect(path: string) {
  router.push(path)
}

function handleLogout() {
  authStore.logout()
  router.push('/login')
}

function handleUserCommand(command: string) {
  if (command === 'logout') handleLogout()
  if (command === 'theme') themeStore.toggle()
  if (command === 'tour') tourRef.value?.startTour()
}

function triggerCmd() {
  const ev = new KeyboardEvent('keydown', { key: 'k', ctrlKey: true })
  window.dispatchEvent(ev)
}
</script>

<template>
  <el-container style="height: 100vh">
    <el-aside :width="isCollapse ? '64px' : '220px'" class="sidebar">
      <div class="sidebar-logo" :class="{ 'is-collapse': isCollapse }">
        <img src="/logo.jpg" alt="logo" class="logo-img" />
        <div v-if="!isCollapse" class="logo-copy">
          <span class="logo-text">SMART-FRIDGE</span>
          <span class="logo-badge">
            <el-icon :size="10"><UserFilled /></el-icon>
            用户端
          </span>
        </div>
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
        <div style="display: flex; align-items: center; gap: 16px">
          <div class="cmd-hint" @click="triggerCmd">
            <span>命令面板</span>
            <kbd>Ctrl</kbd><kbd>K</kbd>
          </div>
          <NotificationBell />
          <el-dropdown trigger="click" @command="handleUserCommand">
            <div class="user-chip">
              <div class="user-avatar">{{ userInitial }}</div>
              <div class="user-meta">
                <div class="user-meta-name">{{ authStore.user?.username || '--' }}</div>
                <div class="user-meta-role">用户</div>
              </div>
              <el-icon class="user-chip-arrow"><ArrowDown /></el-icon>
            </div>
            <template #dropdown>
              <el-dropdown-menu>
                <el-dropdown-item disabled>
                  <div style="display: flex; flex-direction: column; line-height: 1.4">
                    <span style="font-weight: 600; color: var(--text-primary)">{{ authStore.user?.username || '--' }}</span>
                    <span style="font-size: 12px; color: var(--text-placeholder)">普通用户</span>
                  </div>
                </el-dropdown-item>
                <el-dropdown-item command="theme">
                  <el-icon>
                    <Moon v-if="!themeStore.isDark" />
                    <Sunny v-else />
                  </el-icon>
                  {{ themeStore.isDark ? '切换到浅色' : '切换到暗色' }}
                </el-dropdown-item>
                <el-dropdown-item command="tour">
                  <el-icon><GuideFilled /></el-icon>
                  重新查看新手引导
                </el-dropdown-item>
                <el-dropdown-item divided command="logout">
                  <el-icon><SwitchButton /></el-icon>
                  退出登录
                </el-dropdown-item>
              </el-dropdown-menu>
            </template>
          </el-dropdown>
        </div>
      </el-header>

      <el-main style="padding: 20px; background: var(--bg-color)">
        <router-view />
      </el-main>
    </el-container>

    <!-- 首次登录引导（也可被命令面板手动触发） -->
    <OnboardingTour ref="tourRef" />
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
  height: 64px;
  display: flex;
  align-items: center;
  justify-content: flex-start;
  gap: 10px;
  padding: 0 18px;
  border-bottom: 1px solid var(--border-color);
  overflow: hidden;
  flex-shrink: 0;
}

.logo-img {
  width: 32px;
  height: 32px;
  border-radius: 8px;
  object-fit: cover;
  flex-shrink: 0;
}

.logo-text {
  font-size: 16px;
  font-weight: 700;
  color: var(--brand-primary-dark);
  letter-spacing: 0;
  line-height: 1.1;
}

.sidebar-logo.is-collapse {
  justify-content: center;
  padding: 0;
}

.logo-copy {
  display: flex;
  flex-direction: column;
  gap: 4px;
  min-width: 0;
}

.logo-badge {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  align-self: flex-start;
  padding: 1px 6px;
  border-radius: 999px;
  background: var(--brand-primary-soft);
  border: 1px solid var(--brand-primary-light);
  color: var(--brand-primary-dark);
  font-size: 10px;
  font-weight: 600;
  line-height: 1.3;
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

.user-chip {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 4px 12px 4px 4px;
  border-radius: 999px;
  background: var(--bg-color);
  border: 1px solid transparent;
  cursor: pointer;
  transition: background 0.2s, border-color 0.2s;
  outline: none;
}

.user-chip:hover {
  background: var(--brand-primary-light);
  border-color: var(--brand-primary-light);
}

.user-avatar {
  width: 32px;
  height: 32px;
  border-radius: 50%;
  background: linear-gradient(135deg, var(--brand-primary-hover), var(--brand-primary-dark));
  color: #fff;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 14px;
  font-weight: 600;
  flex-shrink: 0;
  box-shadow: 0 2px 6px rgba(14, 165, 233, 0.30);
}

.user-meta {
  display: flex;
  flex-direction: column;
  line-height: 1.2;
  min-width: 0;
}

.user-meta-name {
  font-size: 13px;
  font-weight: 600;
  color: var(--text-primary);
  max-width: 120px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.user-meta-role {
  font-size: 11px;
  color: var(--text-placeholder);
  margin-top: 1px;
}

.user-chip-arrow {
  color: var(--text-placeholder);
  font-size: 12px;
  transition: transform 0.2s;
}

.user-chip:hover .user-chip-arrow {
  color: var(--brand-primary);
}

.cmd-hint {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 4px 10px;
  border-radius: 999px;
  background: var(--bg-color);
  border: 1px solid var(--border-color);
  font-size: 12px;
  color: var(--text-secondary);
  cursor: pointer;
  transition: all 0.18s;
}

.cmd-hint:hover {
  border-color: var(--brand-primary);
  color: var(--brand-primary-dark);
  background: var(--brand-primary-soft);
}

.cmd-hint kbd {
  font-family: 'SFMono-Regular', Consolas, monospace;
  background: var(--bg-card);
  border: 1px solid var(--border-color);
  border-bottom-width: 2px;
  border-radius: 3px;
  padding: 0 4px;
  font-size: 10px;
  color: var(--text-secondary);
}

.el-menu {
  border-right: none;
  padding: 8px;
  flex: 1;
  overflow-y: auto;
  overflow-x: hidden;
}
</style>
