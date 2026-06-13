<script setup lang="ts">
/**
 * 全屏烹饪模式：大字步骤 + 倒计时 + 朗读 + 上下步切换。
 * 用 Web Speech TTS（浏览器原生）朗读步骤，不耗 token。
 */
import { ref, computed, watch, onBeforeUnmount } from 'vue'

interface Recipe {
  name: string
  prep_time?: number | null
  ingredients?: Array<{ name: string; amount?: string | null }> | null
  steps?: string[] | null
}

const props = defineProps<{
  visible: boolean
  recipe: Recipe | null
}>()

const emit = defineEmits<{
  (e: 'update:visible', v: boolean): void
  (e: 'cooked', r: Recipe): void
}>()

const stepIndex = ref(0)
const remainSec = ref(0)
let timerId: ReturnType<typeof setInterval> | null = null
const speaking = ref(false)
const ttsEnabled = ref(true)

const totalSteps = computed(() => props.recipe?.steps?.length || 0)
const currentStep = computed(() => props.recipe?.steps?.[stepIndex.value] || '')

const totalSec = computed(() => (props.recipe?.prep_time || 10) * 60)
const elapsedSec = computed(() => Math.max(0, totalSec.value - remainSec.value))
const progressPct = computed(() => totalSec.value
  ? Math.min(100, Math.round(elapsedSec.value / totalSec.value * 100))
  : 0)

function fmt(sec: number) {
  const m = Math.floor(sec / 60)
  const s = sec % 60
  return `${m.toString().padStart(2, '0')}:${s.toString().padStart(2, '0')}`
}

function startTimer() {
  if (timerId) clearInterval(timerId)
  remainSec.value = totalSec.value
  timerId = setInterval(() => {
    if (remainSec.value > 0) {
      remainSec.value--
    } else {
      stopTimer()
      // 计时结束提示
      try {
        speak('烹饪时间到啦！')
      } catch {}
    }
  }, 1000)
}

function stopTimer() {
  if (timerId) { clearInterval(timerId); timerId = null }
}

function pauseOrResume() {
  if (timerId) {
    stopTimer()
  } else if (remainSec.value > 0) {
    timerId = setInterval(() => {
      if (remainSec.value > 0) remainSec.value--
      else stopTimer()
    }, 1000)
  } else {
    startTimer()
  }
}

function speak(text: string) {
  if (!ttsEnabled.value) return
  if (!('speechSynthesis' in window)) return
  // 取消上一段
  window.speechSynthesis.cancel()
  const utt = new SpeechSynthesisUtterance(text)
  utt.lang = 'zh-CN'
  utt.rate = 1.0
  utt.pitch = 1.0
  utt.onstart = () => { speaking.value = true }
  utt.onend = () => { speaking.value = false }
  utt.onerror = () => { speaking.value = false }
  window.speechSynthesis.speak(utt)
}

function speakCurrentStep() {
  if (currentStep.value) {
    speak(`第 ${stepIndex.value + 1} 步。${currentStep.value}`)
  }
}

function nextStep() {
  if (stepIndex.value < totalSteps.value - 1) {
    stepIndex.value++
    if (ttsEnabled.value) speakCurrentStep()
  }
}

function prevStep() {
  if (stepIndex.value > 0) {
    stepIndex.value--
    if (ttsEnabled.value) speakCurrentStep()
  }
}

function close() {
  emit('update:visible', false)
}

function finishAndCook() {
  if (props.recipe) emit('cooked', props.recipe)
  close()
}

function onKeydown(e: KeyboardEvent) {
  if (!props.visible) return
  if (e.key === 'ArrowRight' || e.key === ' ') { e.preventDefault(); nextStep() }
  else if (e.key === 'ArrowLeft') { e.preventDefault(); prevStep() }
  else if (e.key === 'Escape') close()
}

watch(() => props.visible, (v) => {
  if (v) {
    stepIndex.value = 0
    startTimer()
    if (ttsEnabled.value) {
      // 0.4 秒后朗读，避免动画进入时被打断
      setTimeout(() => speakCurrentStep(), 400)
    }
    window.addEventListener('keydown', onKeydown)
  } else {
    stopTimer()
    if ('speechSynthesis' in window) window.speechSynthesis.cancel()
    speaking.value = false
    window.removeEventListener('keydown', onKeydown)
  }
})

onBeforeUnmount(() => {
  stopTimer()
  if ('speechSynthesis' in window) window.speechSynthesis.cancel()
  window.removeEventListener('keydown', onKeydown)
})
</script>

<template>
  <transition name="cm-fade">
    <div v-if="visible" class="cooking-mode">
      <!-- 顶部 -->
      <div class="cm-top">
        <div class="cm-name">{{ recipe?.name || '烹饪中' }}</div>
        <div class="cm-progress">
          <span>第 {{ stepIndex + 1 }} / {{ totalSteps }} 步</span>
          <div class="cm-step-bar">
            <div class="cm-step-fill" :style="{ width: ((stepIndex + 1) / totalSteps * 100) + '%' }"></div>
          </div>
        </div>
        <button class="cm-btn-icon" @click="close" title="退出（Esc）">
          <el-icon :size="20"><Close /></el-icon>
        </button>
      </div>

      <!-- 主体：当前步骤 -->
      <div class="cm-main">
        <div class="cm-step-no">第 {{ stepIndex + 1 }} 步</div>
        <div class="cm-step-text">{{ currentStep }}</div>
        <div v-if="speaking" class="cm-speaking">
          <span class="cm-wave"></span>
          <span class="cm-wave"></span>
          <span class="cm-wave"></span>
          <span style="margin-left: 8px">朗读中…</span>
        </div>
      </div>

      <!-- 底部计时 + 操作 -->
      <div class="cm-bottom">
        <div class="cm-timer">
          <div class="cm-timer-display">{{ fmt(remainSec) }}</div>
          <div class="cm-timer-track">
            <div class="cm-timer-fill" :style="{ width: progressPct + '%' }"></div>
          </div>
          <div class="cm-timer-label">
            {{ remainSec > 0 ? '剩余时间' : '时间到 ⏰' }}
            · 总时长 {{ recipe?.prep_time || 10 }} 分钟
          </div>
        </div>

        <div class="cm-controls">
          <button class="cm-btn" :disabled="stepIndex === 0" @click="prevStep">
            <el-icon :size="18"><ArrowLeft /></el-icon>
            上一步
          </button>
          <button class="cm-btn cm-btn-tts" @click="speakCurrentStep" :class="{ active: speaking }">
            <el-icon :size="18"><Microphone /></el-icon>
            朗读
          </button>
          <button class="cm-btn cm-btn-pause" @click="pauseOrResume">
            <el-icon :size="18">
              <VideoPause v-if="timerId" />
              <VideoPlay v-else />
            </el-icon>
            {{ timerId ? '暂停' : '继续' }}
          </button>
          <button v-if="stepIndex < totalSteps - 1" class="cm-btn cm-btn-primary" @click="nextStep">
            下一步
            <el-icon :size="18"><ArrowRight /></el-icon>
          </button>
          <button v-else class="cm-btn cm-btn-success" @click="finishAndCook">
            <el-icon :size="18"><CircleCheck /></el-icon>
            完成 + 打卡
          </button>
        </div>

        <div class="cm-help">
          <span>↑ ← 上一步</span>
          <span>↓ → / 空格 下一步</span>
          <span>Esc 退出</span>
          <label class="cm-tts-toggle">
            <input type="checkbox" v-model="ttsEnabled" />
            自动朗读
          </label>
        </div>
      </div>
    </div>
  </transition>
</template>

<style scoped>
.cooking-mode {
  position: fixed;
  inset: 0;
  z-index: 9000;
  background:
    radial-gradient(ellipse at top, rgba(14, 165, 233, 0.15), transparent 50%),
    radial-gradient(ellipse at bottom, rgba(6, 182, 212, 0.10), transparent 50%),
    #0f1a16;
  color: #fff;
  display: flex;
  flex-direction: column;
  user-select: none;
}

/* 顶部 */
.cm-top {
  display: flex;
  align-items: center;
  gap: 16px;
  padding: 18px 28px;
  border-bottom: 1px solid rgba(255, 255, 255, 0.08);
}

.cm-name {
  font-size: 18px;
  font-weight: 700;
  color: var(--brand-primary-hover);
  flex-shrink: 0;
}

.cm-progress {
  flex: 1;
  display: flex;
  align-items: center;
  gap: 12px;
  font-size: 12px;
  color: rgba(255, 255, 255, 0.6);
}

.cm-step-bar {
  flex: 1;
  height: 4px;
  border-radius: 2px;
  background: rgba(255, 255, 255, 0.10);
  overflow: hidden;
  max-width: 480px;
}

.cm-step-fill {
  height: 100%;
  background: linear-gradient(90deg, var(--brand-primary), var(--brand-primary-hover));
  transition: width 0.3s;
}

.cm-btn-icon {
  background: transparent;
  border: 1px solid rgba(255, 255, 255, 0.15);
  color: #fff;
  width: 36px;
  height: 36px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  transition: all 0.18s;
}

.cm-btn-icon:hover {
  background: rgba(255, 255, 255, 0.1);
}

/* 主体 */
.cm-main {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 40px 60px;
  text-align: center;
}

.cm-step-no {
  font-size: 28px;
  color: var(--brand-primary-hover);
  font-weight: 700;
  letter-spacing: 1px;
  margin-bottom: 24px;
}

.cm-step-text {
  font-size: 48px;
  font-weight: 700;
  line-height: 1.4;
  color: #fff;
  max-width: 1100px;
  letter-spacing: 0.5px;
}

.cm-speaking {
  display: inline-flex;
  align-items: center;
  margin-top: 24px;
  font-size: 14px;
  color: rgba(255, 255, 255, 0.7);
  gap: 4px;
}

.cm-wave {
  display: inline-block;
  width: 4px;
  height: 14px;
  background: var(--brand-primary);
  border-radius: 2px;
  animation: cm-wave 0.9s ease-in-out infinite;
}

.cm-wave:nth-child(2) { animation-delay: 0.15s; }
.cm-wave:nth-child(3) { animation-delay: 0.30s; }

@keyframes cm-wave {
  0%, 100% { transform: scaleY(0.4); }
  50%      { transform: scaleY(1); }
}

/* 底部 */
.cm-bottom {
  padding: 24px 40px 32px;
  border-top: 1px solid rgba(255, 255, 255, 0.08);
  background: rgba(0, 0, 0, 0.2);
  display: flex;
  flex-direction: column;
  gap: 16px;
  align-items: center;
}

.cm-timer {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 8px;
  width: 100%;
  max-width: 600px;
}

.cm-timer-display {
  font-size: 56px;
  font-weight: 800;
  font-variant-numeric: tabular-nums;
  color: var(--brand-primary-hover);
  letter-spacing: 4px;
  line-height: 1;
}

.cm-timer-track {
  width: 100%;
  height: 6px;
  border-radius: 3px;
  background: rgba(255, 255, 255, 0.08);
  overflow: hidden;
}

.cm-timer-fill {
  height: 100%;
  background: linear-gradient(90deg, var(--brand-primary), var(--brand-primary-hover));
  transition: width 1s linear;
}

.cm-timer-label {
  font-size: 12px;
  color: rgba(255, 255, 255, 0.5);
}

/* 控制按钮 */
.cm-controls {
  display: flex;
  gap: 10px;
  flex-wrap: wrap;
  justify-content: center;
}

.cm-btn {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 10px 20px;
  background: rgba(255, 255, 255, 0.08);
  border: 1px solid rgba(255, 255, 255, 0.12);
  border-radius: 12px;
  color: #fff;
  font-size: 14px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.18s;
}

.cm-btn:hover:not(:disabled) {
  background: rgba(255, 255, 255, 0.15);
  transform: translateY(-1px);
}

.cm-btn:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}

.cm-btn-primary {
  background: linear-gradient(135deg, var(--brand-primary), var(--brand-primary-dark));
  border-color: transparent;
}

.cm-btn-success {
  background: linear-gradient(135deg, #00b42a, #009920);
  border-color: transparent;
}

.cm-btn-tts.active {
  background: var(--brand-primary);
  border-color: var(--brand-primary);
}

.cm-help {
  display: flex;
  align-items: center;
  gap: 16px;
  font-size: 11px;
  color: rgba(255, 255, 255, 0.4);
  flex-wrap: wrap;
  justify-content: center;
}

.cm-tts-toggle {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  cursor: pointer;
}

.cm-tts-toggle input {
  cursor: pointer;
}

/* 进入动画 */
.cm-fade-enter-active,
.cm-fade-leave-active {
  transition: opacity 0.3s ease;
}
.cm-fade-enter-from,
.cm-fade-leave-to {
  opacity: 0;
}

@media (max-width: 800px) {
  .cm-step-text { font-size: 32px; }
  .cm-timer-display { font-size: 40px; }
  .cm-main { padding: 20px; }
}
</style>
