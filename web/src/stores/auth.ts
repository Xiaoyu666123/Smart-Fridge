import { defineStore } from 'pinia'
import { ref, computed } from 'vue'

export interface AuthUser {
  id: string
  username: string
  role: string
}

export const useAuthStore = defineStore('auth', () => {
  const token = ref(localStorage.getItem('token') || '')
  const user = ref<AuthUser | null>(null)

  const isLoggedIn = computed(() => !!token.value)
  const isAdmin = computed(() => user.value?.role === 'admin')

  function setAuth(newToken: string, userInfo: AuthUser) {
    token.value = newToken
    user.value = userInfo
    localStorage.setItem('token', newToken)
    localStorage.setItem('userInfo', JSON.stringify(userInfo))
  }

  function loadFromStorage() {
    const saved = localStorage.getItem('userInfo')
    if (token.value && saved) {
      try {
        user.value = JSON.parse(saved)
      } catch {
        logout()
      }
    }
  }

  function logout() {
    token.value = ''
    user.value = null
    localStorage.removeItem('token')
    localStorage.removeItem('userInfo')
  }

  return { token, user, isLoggedIn, isAdmin, setAuth, loadFromStorage, logout }
})
