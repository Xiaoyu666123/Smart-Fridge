<script setup lang="ts">
/**
 * 通用引导式空状态。
 * 比 el-empty 多一个标题、说明、若干快捷按钮。
 */
defineProps<{
  emoji?: string
  title?: string
  desc?: string
  actions?: { label: string; to?: string; href?: string; click?: () => void }[]
}>()

import { useRouter } from 'vue-router'
const router = useRouter()

function go(a: { to?: string; href?: string; click?: () => void }) {
  if (a.click) a.click()
  else if (a.to) router.push(a.to)
  else if (a.href) window.open(a.href, '_blank')
}
</script>

<template>
  <div class="empty-hint">
    <div class="empty-glow"></div>
    <div class="empty-emoji">{{ emoji || '📭' }}</div>
    <div class="empty-title">{{ title || '暂无数据' }}</div>
    <div v-if="desc" class="empty-desc">{{ desc }}</div>
    <div v-if="actions && actions.length" class="empty-actions">
      <el-button
        v-for="(a, i) in actions"
        :key="i"
        :type="i === 0 ? 'primary' : 'default'"
        @click="go(a)"
      >
        {{ a.label }}
      </el-button>
    </div>
    <slot />
  </div>
</template>

<style scoped>
.empty-hint {
  position: relative;
  text-align: center;
  padding: 56px 20px 40px;
  background: var(--bg-card);
  border-radius: var(--radius-md);
  border: 1px solid var(--border-color);
  overflow: hidden;
}

.empty-glow {
  position: absolute;
  left: 50%;
  top: 50px;
  width: 220px;
  height: 220px;
  transform: translateX(-50%);
  background: radial-gradient(circle, rgba(14, 165, 233, 0.22) 0%, rgba(14, 165, 233, 0) 70%);
  filter: blur(20px);
  pointer-events: none;
  animation: empty-glow-pulse 3.6s ease-in-out infinite;
}

@keyframes empty-glow-pulse {
  0%, 100% { transform: translateX(-50%) scale(1); opacity: 0.7; }
  50%      { transform: translateX(-50%) scale(1.15); opacity: 1; }
}

.empty-emoji {
  position: relative;
  font-size: 56px;
  line-height: 1;
  margin-bottom: 16px;
}

.empty-title {
  position: relative;
  font-size: 18px;
  font-weight: 700;
  color: var(--text-primary);
  margin-bottom: 8px;
}

.empty-desc {
  position: relative;
  font-size: 13px;
  color: var(--text-secondary);
  max-width: 420px;
  margin: 0 auto 22px;
  line-height: 1.7;
}

.empty-actions {
  position: relative;
  display: flex;
  justify-content: center;
  gap: 10px;
  flex-wrap: wrap;
}
</style>
