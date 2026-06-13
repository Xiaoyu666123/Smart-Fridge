<script setup lang="ts">
/**
 * 全局命令面板（Ctrl+K / Cmd+K 唤起）。
 *
 * 默认列出当前用户类型可用的页面 + 一些快捷动作（切换主题、退出登录等）。
 * 输入框做模糊匹配（拼音也好用，因为我们直接 lower-case 字符串匹配）。
 *
 * Esc 关闭，Enter 跳转选中项，↑↓ 切换选中。
 */
import { ref, computed, watch, onMounted, onBeforeUnmount, nextTick } from 'vue'
import { useRouter } from 'vue-router'
import { useThemeStore } from '@/stores/theme'
import { useAdminAuthStore } from '@/stores/adminAuth'
import { useUserAuthStore } from '@/stores/userAuth'

interface CommandItem {
  id: string
  title: string
  icon?: string
  hint?: string
  group: string
  action: () => void
  keywords?: string
}

const router = useRouter()
const theme = useThemeStore()
const adminAuth = useAdminAuthStore()
const userAuth = useUserAuthStore()

const visible = ref(false)
const query = ref('')
const activeIndex = ref(0)
const inputRef = ref<HTMLInputElement>()

const helpVisible = ref(false)

function isAdmin(): boolean {
  return !!localStorage.getItem('admin_token')
}

function isUser(): boolean {
  return !!localStorage.getItem('user_token')
}

const adminPages: { path: string; title: string; icon: string }[] = [
  { path: '/admin/dashboard', title: '数据大盘', icon: 'DataAnalysis' },
  { path: '/admin/inventory', title: '库存管理', icon: 'Box' },
  { path: '/admin/fridge-map', title: '冰箱视图', icon: 'Grid' },
  { path: '/admin/batch-recognize', title: '整柜识别', icon: 'Camera' },
  { path: '/admin/pending-labels', title: '标签缓冲', icon: 'CollectionTag' },
  { path: '/admin/devices', title: '设备管理', icon: 'Monitor' },
  { path: '/admin/users', title: '用户管理', icon: 'User' },
  { path: '/admin/agent', title: 'Agent 配置', icon: 'Cpu' },
  { path: '/admin/vision-assist', title: '视觉辅助策略', icon: 'MagicStick' },
  { path: '/admin/categories', title: '品类配置', icon: 'Collection' },
  { path: '/admin/workflow', title: '工作流', icon: 'Connection' },
  { path: '/admin/logs', title: '系统日志', icon: 'Document' },
  { path: '/admin/audit', title: '操作审计', icon: 'View' },
  { path: '/admin/usage', title: 'Token 用量', icon: 'Money' },
  { path: '/admin/perf', title: '性能监控', icon: 'Histogram' },
  { path: '/admin/waste', title: '浪费分析', icon: 'PieChart' },
  { path: '/admin/lifecycle', title: '食材生命周期', icon: 'Connection' },
  { path: '/admin/screen', title: '可视化大屏', icon: 'FullScreen' },
]

const userPages: { path: string; title: string; icon: string }[] = [
  { path: '/user/home', title: '首页', icon: 'House' },
  { path: '/user/inventory', title: '库存查看', icon: 'Box' },
  { path: '/user/expiring', title: '临期处理', icon: 'AlarmClock' },
  { path: '/user/fridge-map', title: '冰箱视图', icon: 'Grid' },
  { path: '/user/chat', title: 'AI对话', icon: 'ChatDotRound' },
  { path: '/user/recipes', title: '我的食谱', icon: 'Star' },
  { path: '/user/shopping', title: '购物清单', icon: 'ShoppingCart' },
  { path: '/user/nutrition', title: '健康饮食', icon: 'Apple' },
  { path: '/user/recognize', title: '食材识别', icon: 'Camera' },
  { path: '/user/preferences', title: '偏好设置', icon: 'Setting' },
  { path: '/user/achievements', title: '我的成就', icon: 'Medal' },
  { path: '/user/environment', title: '查看天气', icon: 'Sunny' },
]

const allCommands = computed<CommandItem[]>(() => {
  const list: CommandItem[] = []
  const pages = isAdmin() ? adminPages : isUser() ? userPages : []
  pages.forEach(p => {
    list.push({
      id: 'page:' + p.path,
      title: p.title,
      icon: p.icon,
      hint: p.path,
      group: '页面',
      action: () => router.push(p.path),
      keywords: p.title + ' ' + p.path,
    })
  })

  // 通用动作
  list.push({
    id: 'action:theme',
    title: theme.isDark ? '切换到浅色模式' : '切换到暗色模式',
    icon: theme.isDark ? 'Sunny' : 'Moon',
    group: '动作',
    action: () => theme.toggle(),
  })
  list.push({
    id: 'action:help',
    title: '查看快捷键帮助',
    icon: 'QuestionFilled',
    group: '动作',
    hint: 'Ctrl + /',
    action: () => { helpVisible.value = true },
  })
  if (isAdmin()) {
    list.push({
      id: 'action:logout-admin',
      title: '退出管理员登录',
      icon: 'SwitchButton',
      group: '动作',
      action: () => { adminAuth.logout(); router.push('/login') },
    })
  }
  if (isUser()) {
    list.push({
      id: 'action:tour',
      title: '重新查看新手引导',
      icon: 'GuideFilled',
      group: '动作',
      action: () => {
        const fn = (window as any).__startOnboarding
        if (typeof fn === 'function') fn()
      },
    })
    list.push({
      id: 'action:logout-user',
      title: '退出当前账号',
      icon: 'SwitchButton',
      group: '动作',
      action: () => { userAuth.logout(); router.push('/login') },
    })
  }
  return list
})

const filtered = computed(() => {
  const q = query.value.trim().toLowerCase()
  if (!q) return allCommands.value
  return allCommands.value.filter(c =>
    (c.title + ' ' + (c.hint || '') + ' ' + (c.keywords || '')).toLowerCase().includes(q)
  )
})

const grouped = computed(() => {
  const groups = new Map<string, CommandItem[]>()
  filtered.value.forEach(c => {
    if (!groups.has(c.group)) groups.set(c.group, [])
    groups.get(c.group)!.push(c)
  })
  return Array.from(groups.entries())
})

watch(filtered, () => { activeIndex.value = 0 })

function open() {
  visible.value = true
  query.value = ''
  activeIndex.value = 0
  nextTick(() => inputRef.value?.focus())
}

function close() {
  visible.value = false
}

function execute(cmd: CommandItem) {
  close()
  cmd.action()
}

function flatList(): CommandItem[] {
  return filtered.value
}

function moveActive(delta: number) {
  const list = flatList()
  if (list.length === 0) return
  activeIndex.value = (activeIndex.value + delta + list.length) % list.length
}

function onEnter() {
  const list = flatList()
  if (list.length === 0) return
  execute(list[activeIndex.value])
}

function isActive(cmd: CommandItem): boolean {
  return flatList()[activeIndex.value]?.id === cmd.id
}

function onGlobalKeydown(e: KeyboardEvent) {
  // Ctrl+K / Cmd+K：打开
  if ((e.ctrlKey || e.metaKey) && (e.key === 'k' || e.key === 'K')) {
    e.preventDefault()
    if (visible.value) close()
    else open()
    return
  }
  // Ctrl+/ ：帮助
  if ((e.ctrlKey || e.metaKey) && e.key === '/') {
    e.preventDefault()
    helpVisible.value = true
    return
  }
}

onMounted(() => {
  window.addEventListener('keydown', onGlobalKeydown)
})

onBeforeUnmount(() => {
  window.removeEventListener('keydown', onGlobalKeydown)
})

defineExpose({ open, close })
</script>

<template>
  <!-- 命令面板 -->
  <el-dialog
    v-model="visible"
    width="560px"
    :show-close="false"
    :close-on-click-modal="true"
    custom-class="cmd-palette-dialog"
    align-center
  >
    <div class="cmd-palette" @keydown.esc.stop.prevent="close" @keydown.down.prevent="moveActive(1)" @keydown.up.prevent="moveActive(-1)" @keydown.enter.prevent="onEnter">
      <div class="cmd-input-wrap">
        <el-icon :size="18" color="var(--text-placeholder)"><Search /></el-icon>
        <input
          ref="inputRef"
          v-model="query"
          class="cmd-input"
          type="text"
          placeholder="搜索页面、功能、动作…"
          autocomplete="off"
        />
        <span class="cmd-shortcut">Esc 关闭</span>
      </div>

      <div class="cmd-list">
        <div v-if="flatList().length === 0" class="cmd-empty">未找到匹配项</div>
        <template v-for="[groupName, items] in grouped" :key="groupName">
          <div class="cmd-group-label">{{ groupName }}</div>
          <div
            v-for="cmd in items"
            :key="cmd.id"
            class="cmd-item"
            :class="{ active: isActive(cmd) }"
            @mouseenter="activeIndex = flatList().findIndex(c => c.id === cmd.id)"
            @click="execute(cmd)"
          >
            <el-icon v-if="cmd.icon" :size="16" class="cmd-item-icon"><component :is="cmd.icon" /></el-icon>
            <span class="cmd-item-title">{{ cmd.title }}</span>
            <span v-if="cmd.hint" class="cmd-item-hint">{{ cmd.hint }}</span>
          </div>
        </template>
      </div>

      <div class="cmd-footer">
        <span class="kbd-hint"><kbd>↑</kbd> <kbd>↓</kbd> 切换</span>
        <span class="kbd-hint"><kbd>Enter</kbd> 选择</span>
        <span class="kbd-hint"><kbd>Esc</kbd> 关闭</span>
      </div>
    </div>
  </el-dialog>

  <!-- 快捷键帮助 -->
  <el-dialog v-model="helpVisible" title="快捷键" width="420px">
    <ul class="kbd-list">
      <li><kbd>Ctrl</kbd> + <kbd>K</kbd><span class="kbd-desc">打开命令面板（搜索页面 / 动作）</span></li>
      <li><kbd>Ctrl</kbd> + <kbd>/</kbd><span class="kbd-desc">显示快捷键帮助</span></li>
      <li><kbd>↑</kbd> <kbd>↓</kbd><span class="kbd-desc">在命令面板里切换选项</span></li>
      <li><kbd>Enter</kbd><span class="kbd-desc">执行选中的命令</span></li>
      <li><kbd>Esc</kbd><span class="kbd-desc">关闭弹窗</span></li>
    </ul>
    <p style="margin-top: 12px; font-size: 12px; color: var(--text-placeholder)">
      💡 Mac 用户可用 <kbd>Cmd</kbd> 替换 <kbd>Ctrl</kbd>
    </p>
  </el-dialog>
</template>

<style scoped>
.cmd-palette {
  display: flex;
  flex-direction: column;
  margin: -20px;
}

.cmd-input-wrap {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 14px 18px;
  border-bottom: 1px solid var(--border-color);
}

.cmd-input {
  flex: 1;
  border: none;
  outline: none;
  background: transparent;
  font-size: 15px;
  color: var(--text-primary);
}

.cmd-shortcut {
  font-size: 11px;
  color: var(--text-placeholder);
  padding: 2px 6px;
  border-radius: 4px;
  background: var(--bg-soft);
}

.cmd-list {
  max-height: 360px;
  overflow-y: auto;
  padding: 6px 0;
}

.cmd-empty {
  padding: 32px;
  text-align: center;
  color: var(--text-placeholder);
  font-size: 13px;
}

.cmd-group-label {
  padding: 8px 18px 4px;
  font-size: 11px;
  color: var(--text-placeholder);
  font-weight: 600;
  letter-spacing: 0.5px;
  text-transform: uppercase;
}

.cmd-item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 8px 18px;
  cursor: pointer;
  transition: background 0.12s;
}

.cmd-item:hover,
.cmd-item.active {
  background: var(--brand-primary-soft);
}

.cmd-item.active {
  background: var(--brand-primary-light);
}

.cmd-item-icon {
  color: var(--text-secondary);
  flex-shrink: 0;
}

.cmd-item.active .cmd-item-icon {
  color: var(--brand-primary-dark);
}

.cmd-item-title {
  flex: 1;
  font-size: 14px;
  color: var(--text-primary);
}

.cmd-item-hint {
  font-size: 11px;
  color: var(--text-placeholder);
  font-family: 'SFMono-Regular', Consolas, monospace;
}

.cmd-footer {
  display: flex;
  gap: 12px;
  padding: 10px 18px;
  border-top: 1px solid var(--border-color);
  background: var(--bg-soft);
}

.kbd-hint {
  font-size: 11px;
  color: var(--text-placeholder);
  display: flex;
  align-items: center;
  gap: 4px;
}

.kbd-hint kbd,
.kbd-list kbd {
  font-family: 'SFMono-Regular', Consolas, monospace;
  background: var(--bg-card);
  border: 1px solid var(--border-color);
  border-bottom-width: 2px;
  border-radius: 4px;
  padding: 1px 6px;
  font-size: 11px;
  color: var(--text-secondary);
}

.kbd-list {
  list-style: none;
  margin: 0;
  padding: 0;
}

.kbd-list li {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 0;
  border-bottom: 1px dashed var(--border-color);
  font-size: 13px;
  color: var(--text-primary);
}

.kbd-list li:last-child {
  border-bottom: none;
}

.kbd-desc {
  margin-left: auto;
  color: var(--text-secondary);
  font-size: 12px;
}
</style>

<style>
/* 全局：让命令面板的 dialog 没有头部留白 */
.cmd-palette-dialog .el-dialog__header {
  display: none;
}
.cmd-palette-dialog .el-dialog__body {
  padding: 0 !important;
}
</style>
