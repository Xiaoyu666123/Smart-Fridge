<script setup lang="ts">
/**
 * 简单的数字跳变动画。
 *
 * 使用 requestAnimationFrame 在 value 变化时插值，从旧值平滑过渡到新值。
 * 用于 Dashboard 顶部统计数字、Inventory 总数等需要"实时跳变"提示的场景。
 */
import { ref, watch, onBeforeUnmount } from 'vue'

const props = withDefaults(defineProps<{
  value: number
  duration?: number     // 动画时长，毫秒
  decimals?: number     // 小数位
  prefix?: string
  suffix?: string
  format?: 'number' | 'compact'   // compact 显示 1.2k / 3.4M
}>(), {
  duration: 600,
  decimals: 0,
  prefix: '',
  suffix: '',
  format: 'number',
})

const display = ref<number>(props.value || 0)
let rafId: number | null = null

function animateTo(target: number) {
  const start = display.value
  const delta = target - start
  if (delta === 0) return
  const startTime = performance.now()
  const dur = props.duration
  if (rafId !== null) cancelAnimationFrame(rafId)

  function tick(now: number) {
    const t = Math.min(1, (now - startTime) / dur)
    // easeOutCubic 缓动
    const eased = 1 - Math.pow(1 - t, 3)
    display.value = start + delta * eased
    if (t < 1) {
      rafId = requestAnimationFrame(tick)
    } else {
      display.value = target
      rafId = null
    }
  }

  rafId = requestAnimationFrame(tick)
}

watch(() => props.value, (v) => animateTo(Number(v) || 0))

onBeforeUnmount(() => {
  if (rafId !== null) cancelAnimationFrame(rafId)
})

function formatNumber(n: number): string {
  if (props.format === 'compact') {
    if (Math.abs(n) >= 1_000_000) return (n / 1_000_000).toFixed(1) + 'M'
    if (Math.abs(n) >= 1_000) return (n / 1_000).toFixed(1) + 'k'
  }
  return n.toFixed(props.decimals)
}
</script>

<template>
  <span>{{ prefix }}{{ formatNumber(display) }}{{ suffix }}</span>
</template>
