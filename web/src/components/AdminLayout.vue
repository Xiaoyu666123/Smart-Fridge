<script setup lang="ts">
import { ref, computed, onMounted, onBeforeUnmount } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { useAdminAuthStore } from '@/stores/adminAuth'
import { useThemeStore } from '@/stores/theme'
import { listDevices, type DeviceItem } from '@/api/admin/device'

const router = useRouter()
const route = useRoute()
const authStore = useAdminAuthStore()
const themeStore = useThemeStore()
authStore.loadFromStorage()

const isCollapse = ref(false)

const devices = ref<DeviceItem[]>([])
let deviceTimer: ReturnType<typeof setInterval> | null = null

async function refreshDevices() {
  try {
    devices.value = await listDevices()
  } catch {
    // 静默
  }
}

const deviceStats = computed(() => {
  const total = devices.value.length
  const online = devices.value.filter(d => d.live_status === 'online').length
  const offline = devices.value.filter(d => d.live_status === 'offline').length
  return { total, online, offline }
})

const deviceTone = computed(() => {
  if (deviceStats.value.total === 0) return 'gray'
  if (deviceStats.value.offline === 0) return 'green'
  if (deviceStats.value.online > 0) return 'orange'
  return 'red'
})

onMounted(() => {
  refreshDevices()
  deviceTimer = setInterval(refreshDevices, 30_000)
})

onBeforeUnmount(() => {
  if (deviceTimer) clearInterval(deviceTimer)
})

const menuItems = [
  { path: '/admin/dashboard', icon: 'DataAnalysis', title: '数据大盘' },
  { path: '/admin/inventory', icon: 'Box', title: '库存管理' },
  { path: '/admin/fridge-map', icon: 'Grid', title: '冰箱视图' },
  { path: '/admin/batch-recognize', icon: 'Camera', title: '整柜识别' },
  { path: '/admin/pending-labels', icon: 'CollectionTag', title: '标签缓冲' },
  { path: '/admin/devices', icon: 'Monitor', title: '设备管理' },
  { path: '/admin/device-ingest', icon: 'DataLine', title: '端侧联调' },
  { path: '/admin/users', icon: 'User', title: '用户管理' },
  { path: '/admin/agent', icon: 'Cpu', title: 'Agent 配置' },
  { path: '/admin/vision-assist', icon: 'MagicStick', title: '视觉辅助' },
  { path: '/admin/categories', icon: 'Collection', title: '品类配置' },
  { path: '/admin/workflow', icon: 'Connection', title: '工作流' },
  { path: '/admin/logs', icon: 'Document', title: '系统日志' },
  { path: '/admin/audit', icon: 'View', title: '操作审计' },
  { path: '/admin/usage', icon: 'Money', title: 'Token 用量' },
  { path: '/admin/perf', icon: 'Histogram', title: '性能监控' },
  { path: '/admin/waste', icon: 'PieChart', title: '浪费分析' },
  { path: '/admin/lifecycle', icon: 'Connection', title: '生命周期' },
]

const pageTitle = computed(() => route.meta.title || '管理员后台')

const userInitial = computed(() => {
  const name = authStore.admin?.username || ''
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
}

function triggerCmd() {
  // 通过模拟 Ctrl+K 触发面板（CommandPalette 会监听）
  const ev = new KeyboardEvent('keydown', { key: 'k', ctrlKey: true })
  window.dispatchEvent(ev)
}
</script>

<template>
  <el-container style="height: 100vh">
    <el-aside :width="isCollapse ? '64px' : '220px'" class="sidebar admin">
      <div class="sidebar-logo" :class="{ 'is-collapse': isCollapse }">
        <img src="/logo.jpg" alt="logo" class="logo-img" />
        <div v-if="!isCollapse" class="logo-copy">
          <span class="logo-text">SMART-FRIDGE</span>
          <span class="logo-badge">
            <el-icon :size="10"><UserFilled /></el-icon>
            管理端
          </span>
        </div>
      </div>
      <el-menu
        :default-active="route.path"
        :collapse="isCollapse"
        background-color="transparent"
        text-color="var(--sidebar-text)"
        active-text-color="var(--brand-secondary)"
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
          <el-tag type="warning" size="small" round style="margin-left: 4px">管理员</el-tag>
        </div>
        <div style="display: flex; align-items: center; gap: 16px">
          <a href="/admin/screen" target="_blank" class="screen-link" title="打开可视化大屏（新窗口）">
            <el-icon :size="14"><FullScreen /></el-icon>
            <span>大屏</span>
          </a>
          <div class="cmd-hint" @click="triggerCmd">
            <span>命令面板</span>
            <kbd>Ctrl</kbd><kbd>K</kbd>
          </div>
          <el-tooltip placement="bottom">
            <template #content>
              <div style="line-height: 1.6">
                <div>设备总数：{{ deviceStats.total }}</div>
                <div>在线：{{ deviceStats.online }}</div>
                <div>离线：{{ deviceStats.offline }}</div>
                <div style="font-size: 11px; opacity: 0.7; margin-top: 4px">点击进入设备管理</div>
              </div>
            </template>
            <div class="device-pill" :class="'tone-' + deviceTone" @click="router.push('/admin/devices')">
              <span class="device-pill-dot"></span>
              <el-icon :size="14"><Monitor /></el-icon>
              <span class="device-pill-num">{{ deviceStats.online }}/{{ deviceStats.total }}</span>
            </div>
          </el-tooltip>
          <el-dropdown trigger="click" @command="handleUserCommand">
            <div class="user-chip">
              <div class="user-avatar is-admin">{{ userInitial }}</div>
              <div class="user-meta">
                <div class="user-meta-name">{{ authStore.admin?.username || '--' }}</div>
                <div class="user-meta-role">管理员</div>
              </div>
              <el-icon class="user-chip-arrow"><ArrowDown /></el-icon>
            </div>
            <template #dropdown>
              <el-dropdown-menu>
                <el-dropdown-item disabled>
                  <div style="display: flex; flex-direction: column; line-height: 1.4">
                    <span style="font-weight: 600; color: var(--text-primary)">{{ authStore.admin?.username || '--' }}</span>
                    <span style="font-size: 12px; color: var(--text-placeholder)">管理员账户</span>
                  </div>
                </el-dropdown-item>
                <el-dropdown-item command="theme">
                  <el-icon>
                    <Moon v-if="!themeStore.isDark" />
                    <Sunny v-else />
                  </el-icon>
                  {{ themeStore.isDark ? '切换到浅色' : '切换到暗色' }}
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
  background: var(--brand-secondary-soft);
  border: 1px solid var(--brand-secondary-light);
  color: var(--brand-secondary);
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
  background: var(--brand-secondary-soft);
  border-color: var(--brand-secondary-soft);
}

.user-avatar {
  width: 32px;
  height: 32px;
  border-radius: 50%;
  background: linear-gradient(135deg, var(--brand-secondary-hover), var(--brand-secondary));
  color: #fff;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 14px;
  font-weight: 600;
  flex-shrink: 0;
  box-shadow: 0 2px 6px rgba(249, 115, 22, 0.30);
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
  color: var(--brand-secondary);
}

.device-pill {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 4px 12px;
  border-radius: 999px;
  cursor: pointer;
  font-size: 12px;
  font-weight: 600;
  border: 1px solid transparent;
  transition: all 0.18s;
}

.device-pill:hover {
  transform: translateY(-1px);
  box-shadow: 0 4px 10px rgba(0, 0, 0, 0.06);
}

.device-pill .device-pill-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  flex-shrink: 0;
  animation: dev-pulse 1.6s ease-in-out infinite;
}

@keyframes dev-pulse {
  0%, 100% { transform: scale(1); opacity: 1; }
  50%      { transform: scale(0.85); opacity: 0.6; }
}

.device-pill.tone-green {
  background: #e8f7e8;
  color: #00b42a;
}
.device-pill.tone-green .device-pill-dot { background: #00b42a; }

.device-pill.tone-orange {
  background: #fff7e6;
  color: #fa8c16;
}
.device-pill.tone-orange .device-pill-dot { background: #fa8c16; }

.device-pill.tone-red {
  background: #ffece8;
  color: #f53f3f;
}
.device-pill.tone-red .device-pill-dot { background: #f53f3f; }

.device-pill.tone-gray {
  background: var(--bg-soft);
  color: var(--text-secondary);
}
.device-pill.tone-gray .device-pill-dot { background: var(--text-placeholder); }

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

.screen-link {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 4px 12px;
  border-radius: 999px;
  font-size: 12px;
  font-weight: 600;
  color: #fff;
  background: linear-gradient(135deg, #0ea5e9, #06b6d4);
  text-decoration: none;
  cursor: pointer;
  transition: all 0.18s;
  box-shadow: 0 4px 10px rgba(14, 165, 233, 0.30);
}

.screen-link:hover {
  transform: translateY(-1px);
  box-shadow: 0 6px 14px rgba(14, 165, 233, 0.45);
}

.el-menu {
  border-right: none;
  padding: 8px;
  flex: 1;
  overflow-y: auto;
  overflow-x: hidden;
}

.el-menu-item.is-active {
  background: var(--brand-secondary-soft) !important;
  color: var(--brand-secondary) !important;
  font-weight: 600;
}
</style>
