<script setup lang="ts">
/**
 * 路由切换时顶部出现的细进度条（不依赖 nprogress）。
 * 消除"切页面白屏 1-2 秒不知道在加载"的体感。
 */
import { ref, onMounted, onBeforeUnmount } from 'vue'
import { useRouter } from 'vue-router'

const router = useRouter()
const visible = ref(false)
const progress = ref(0)
let timer: ReturnType<typeof setInterval> | null = null
let hideTimer: ReturnType<typeof setTimeout> | null = null
let unbeforeEach: (() => void) | null = null
let unafterEach: (() => void) | null = null

function start() {
  if (hideTimer) { clearTimeout(hideTimer); hideTimer = null }
  visible.value = true
  progress.value = 12
  if (timer) clearInterval(timer)
  // 模拟加载：渐进式增长，永远停在 90% 直到 finish 推到 100
  timer = setInterval(() => {
    if (progress.value < 90) {
      const step = (90 - progress.value) * 0.08 + 0.4
      progress.value = Math.min(90, progress.value + step)
    }
  }, 120)
}

function finish() {
  if (timer) { clearInterval(timer); timer = null }
  progress.value = 100
  hideTimer = setTimeout(() => {
    visible.value = false
    progress.value = 0
  }, 240)
}

onMounted(() => {
  unbeforeEach = router.beforeEach((to, from, next) => {
    if (to.path !== from.path) start()
    next()
  })
  unafterEach = router.afterEach(() => {
    finish()
  })
  router.onError(() => finish())
})

onBeforeUnmount(() => {
  if (timer) clearInterval(timer)
  if (hideTimer) clearTimeout(hideTimer)
  unbeforeEach?.()
  unafterEach?.()
})
</script>

<template>
  <transition name="prog-fade">
    <div v-if="visible" class="route-progress">
      <div class="route-progress-fill" :style="{ width: progress + '%' }"></div>
    </div>
  </transition>
</template>

<style scoped>
.route-progress {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  height: 2.5px;
  background: transparent;
  z-index: 10000;
  pointer-events: none;
}

.route-progress-fill {
  height: 100%;
  background: linear-gradient(90deg, var(--brand-primary), var(--brand-primary-hover));
  box-shadow: 0 0 8px rgba(14, 165, 233, 0.6);
  transition: width 0.18s ease-out;
}

.prog-fade-leave-active {
  transition: opacity 0.25s ease;
}
.prog-fade-leave-to {
  opacity: 0;
}
</style>
