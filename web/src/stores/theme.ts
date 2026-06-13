import { defineStore } from 'pinia'
import { ref, watch } from 'vue'

export const useThemeStore = defineStore('theme', () => {
  // 优先读用户偏好；没设置过的话跟随系统
  const saved = localStorage.getItem('theme') as 'light' | 'dark' | null
  const systemDark = window.matchMedia?.('(prefers-color-scheme: dark)').matches || false
  const isDark = ref<boolean>(saved ? saved === 'dark' : systemDark)
  const followSystem = ref<boolean>(saved === null)

  function applyTheme(dark: boolean) {
    document.documentElement.dataset.theme = dark ? 'dark' : 'light'
    if (!followSystem.value) {
      localStorage.setItem('theme', dark ? 'dark' : 'light')
    }
  }

  function toggle() {
    followSystem.value = false  // 一旦用户主动切换就不再跟随系统
    isDark.value = !isDark.value
  }

  function setDark(dark: boolean) {
    followSystem.value = false
    isDark.value = dark
  }

  function resetToSystem() {
    followSystem.value = true
    localStorage.removeItem('theme')
    isDark.value = window.matchMedia?.('(prefers-color-scheme: dark)').matches || false
  }

  // 跟随系统：监听系统主题切换
  if (window.matchMedia) {
    window.matchMedia('(prefers-color-scheme: dark)').addEventListener('change', (e) => {
      if (followSystem.value) {
        isDark.value = e.matches
      }
    })
  }

  watch(isDark, applyTheme, { immediate: true })

  return { isDark, followSystem, toggle, setDark, resetToSystem }
})
