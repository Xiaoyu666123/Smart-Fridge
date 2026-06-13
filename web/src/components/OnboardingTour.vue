<script setup lang="ts">
/**
 * 普通用户首次登录的 4 步引导。
 *
 * 触发：
 *   - localStorage `onboarding_done_user_<uid>` 不存在时自动弹出（onMounted）
 *   - 用户菜单 / 命令面板手动调用 `startTour()` 任意时刻可重新启动
 *
 * 设计：
 *   - 自带遮罩
 *   - 4 步：欢迎 → AI 推荐 → 偏好 → 成就
 *   - 每步配 emoji 大图 + 标题 + 描述 + 可选体验按钮
 *   - 可"跳过"、"上一步 / 下一步"，体验按钮不会阻断引导流程
 */
import { ref, computed, onMounted, watch } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { useUserAuthStore } from '@/stores/userAuth'

const router = useRouter()
const route = useRoute()
const auth = useUserAuthStore()

interface Step {
  emoji: string
  title: string
  desc: string
  cta?: { label: string; path: string }
}

const steps: Step[] = [
  {
    emoji: '👋',
    title: '欢迎来到智能冰箱',
    desc: '我会帮你管理冰箱里的食材、避免浪费、推荐合心意的菜。先花 30 秒了解一下吧～',
  },
  {
    emoji: '🤖',
    title: 'AI对话',
    desc: '告诉 AI 你想吃什么，它会根据你冰箱里的现货 + 偏好 + 当前天气，实时推荐 1-3 道菜。',
    cta: { label: '试试 AI 推荐', path: '/user/chat' },
  },
  {
    emoji: '🍽️',
    title: '设置饮食偏好',
    desc: '告诉我你喜欢什么口味、有什么忌口，AI 会避开过敏食材并优先推荐你爱吃的。',
    cta: { label: '去设置', path: '/user/preferences' },
  },
  {
    emoji: '🏆',
    title: '解锁成就和徽章',
    desc: '收藏食谱、打卡做菜、维护偏好都会解锁成就。等级越高，徽章越多～',
    cta: { label: '看我的成就', path: '/user/achievements' },
  },
]

const visible = ref(false)
const idx = ref(0)
const current = computed(() => steps[idx.value])
const isLast = computed(() => idx.value === steps.length - 1)

function storageKey(): string {
  const uid = auth.user?.id || 'guest'
  return `onboarding_done_user_${uid}`
}

function shouldAutoOpen(): boolean {
  // 已登录普通用户、未完成过、不在登录页
  if (!auth.user) return false
  if (route.meta.userType !== 'user') return false
  return !localStorage.getItem(storageKey())
}

function open() {
  idx.value = 0
  visible.value = true
}

function close() {
  visible.value = false
}

function finishAndClose() {
  localStorage.setItem(storageKey(), '1')
  visible.value = false
}

function nextStep() {
  if (isLast.value) {
    finishAndClose()
  } else {
    idx.value++
  }
}

function prevStep() {
  if (idx.value > 0) idx.value--
}

function jumpTo(i: number) {
  idx.value = i
}

function gotoCta() {
  const cta = current.value.cta
  if (cta) {
    finishAndClose()
    router.push(cta.path)
  } else {
    nextStep()
  }
}

// 在 user layout 渲染挂载后自动检查一次
onMounted(() => {
  // 给 stores 一点时间从 localStorage 恢复
  setTimeout(() => {
    if (shouldAutoOpen()) open()
  }, 400)
})

// 监听用户切换 / 登录状态变化
watch(() => auth.user?.id, (newId, oldId) => {
  if (newId && newId !== oldId && shouldAutoOpen()) {
    open()
  }
})

// 暴露给父级 / 命令面板调用
defineExpose({ startTour: open })
</script>

<template>
  <Transition name="onb-fade">
    <div v-if="visible" class="onb-mask" @click.self="close">
      <div class="onb-card">
        <button class="onb-skip" type="button" @click="finishAndClose" title="跳过引导">跳过 ×</button>

        <div class="onb-emoji-wrap">
          <div class="onb-emoji-glow"></div>
          <div class="onb-emoji">{{ current.emoji }}</div>
        </div>

        <div class="onb-step">第 {{ idx + 1 }} / {{ steps.length }} 步</div>
        <h2 class="onb-title">{{ current.title }}</h2>
        <p class="onb-desc">{{ current.desc }}</p>

        <!-- 进度点 -->
        <div class="onb-dots">
          <button
            v-for="(_, i) in steps"
            :key="i"
            type="button"
            class="onb-dot"
            :class="{ active: i === idx, done: i < idx }"
            @click="jumpTo(i)"
          ></button>
        </div>

        <!-- 操作按钮 -->
        <div class="onb-actions">
          <el-button v-if="idx > 0" plain @click="prevStep">
            <el-icon><ArrowLeft /></el-icon>
            上一步
          </el-button>

          <el-button v-if="current.cta" plain class="onb-secondary" @click="gotoCta">
            {{ current.cta.label }}
            <el-icon style="margin-left: 4px"><ArrowRight /></el-icon>
          </el-button>
          <el-button type="primary" class="onb-cta" @click="nextStep">
            {{ isLast ? '开始体验' : '下一步' }}
            <el-icon v-if="!isLast" style="margin-left: 4px"><ArrowRight /></el-icon>
          </el-button>
        </div>

        <div class="onb-foot">
          <span class="onb-foot-tip">💡 之后可在「命令面板（Ctrl+K）→ 重新查看引导」里再次打开</span>
        </div>
      </div>
    </div>
  </Transition>
</template>

<style scoped>
.onb-mask {
  position: fixed;
  inset: 0;
  z-index: 2400;
  background: rgba(15, 23, 42, 0.55);
  backdrop-filter: blur(6px);
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 20px;
  animation: onb-mask-in 0.3s ease;
}

@keyframes onb-mask-in {
  from { opacity: 0; }
  to   { opacity: 1; }
}

.onb-card {
  position: relative;
  width: min(440px, 100%);
  padding: 36px 32px 28px;
  background: var(--bg-card);
  border-radius: 22px;
  box-shadow:
    0 30px 60px rgba(15, 23, 42, 0.45),
    0 12px 32px rgba(14, 165, 233, 0.25);
  text-align: center;
  animation: onb-pop 0.45s cubic-bezier(0.34, 1.56, 0.64, 1);
}

@keyframes onb-pop {
  from { opacity: 0; transform: scale(0.85) translateY(20px); }
  to   { opacity: 1; transform: scale(1) translateY(0); }
}

.onb-skip {
  position: absolute;
  top: 14px;
  right: 16px;
  padding: 4px 12px;
  font-size: 12px;
  color: var(--text-placeholder);
  background: transparent;
  border: 1px solid var(--border-color);
  border-radius: 999px;
  cursor: pointer;
  transition: all 0.18s;
}

.onb-skip:hover {
  color: var(--text-primary);
  border-color: var(--text-secondary);
}

.onb-emoji-wrap {
  position: relative;
  width: 110px;
  height: 110px;
  margin: 0 auto 16px;
  display: flex;
  align-items: center;
  justify-content: center;
}

.onb-emoji-glow {
  position: absolute;
  inset: -24px;
  border-radius: 50%;
  background:
    radial-gradient(circle, rgba(14, 165, 233, 0.45) 0%, rgba(14, 165, 233, 0) 70%);
  filter: blur(14px);
  animation: onb-glow 3s ease-in-out infinite;
  pointer-events: none;
}

@keyframes onb-glow {
  0%, 100% { transform: scale(1); opacity: 0.7; }
  50%      { transform: scale(1.18); opacity: 1; }
}

.onb-emoji {
  position: relative;
  font-size: 70px;
  line-height: 1;
  animation: onb-emoji-bounce 2.4s ease-in-out infinite;
}

@keyframes onb-emoji-bounce {
  0%, 100% { transform: translateY(0) rotate(0deg); }
  50%      { transform: translateY(-6px) rotate(-3deg); }
}

.onb-step {
  display: inline-block;
  padding: 3px 12px;
  background: var(--brand-primary-soft);
  color: var(--brand-primary-dark);
  border-radius: 999px;
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 0.5px;
  margin-bottom: 10px;
}

.onb-title {
  margin: 0;
  font-size: 22px;
  font-weight: 800;
  color: var(--text-primary);
  letter-spacing: -0.4px;
}

.onb-desc {
  margin: 10px 0 22px;
  font-size: 14px;
  color: var(--text-secondary);
  line-height: 1.7;
  padding: 0 6px;
}

.onb-dots {
  display: flex;
  justify-content: center;
  gap: 8px;
  margin-bottom: 22px;
}

.onb-dot {
  width: 26px;
  height: 6px;
  border-radius: 3px;
  background: rgba(0, 0, 0, 0.08);
  border: none;
  padding: 0;
  cursor: pointer;
  transition: all 0.25s;
}

.onb-dot.done {
  background: var(--brand-primary);
  opacity: 0.6;
}

.onb-dot.active {
  background: linear-gradient(90deg, var(--brand-primary), var(--brand-primary-dark));
  width: 36px;
  opacity: 1;
}

.onb-actions {
  display: flex;
  justify-content: center;
  flex-wrap: wrap;
  gap: 10px;
}

.onb-secondary {
  padding: 10px 18px;
  font-weight: 600;
  color: var(--brand-primary-dark) !important;
  border-color: var(--brand-primary-light) !important;
  background: var(--brand-primary-soft) !important;
}

.onb-secondary:hover {
  border-color: var(--brand-primary) !important;
  background: var(--brand-primary-light) !important;
}

.onb-cta {
  background: linear-gradient(135deg, var(--brand-primary), var(--brand-primary-dark)) !important;
  border-color: transparent !important;
  font-weight: 600;
  padding: 10px 22px;
  box-shadow: 0 6px 16px rgba(14, 165, 233, 0.35);
}

.onb-cta:hover {
  transform: translateY(-1px);
  box-shadow: 0 10px 22px rgba(14, 165, 233, 0.45);
}

.onb-foot {
  margin-top: 22px;
  padding-top: 14px;
  border-top: 1px dashed var(--border-color);
}

.onb-foot-tip {
  font-size: 11px;
  color: var(--text-placeholder);
}

/* 过渡 */
.onb-fade-enter-active,
.onb-fade-leave-active {
  transition: opacity 0.25s ease;
}

.onb-fade-enter-from,
.onb-fade-leave-to {
  opacity: 0;
}
</style>
