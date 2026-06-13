import { defineStore } from 'pinia'
import { ref } from 'vue'

export interface UserInfo {
    id: string
    username: string
    user_type: 'user'
}

export const useUserAuthStore = defineStore('userAuth', () => {
    const token = ref(localStorage.getItem('user_token') || '')
    const user = ref<UserInfo | null>(null)

    function setAuth(newToken: string, info: UserInfo) {
        token.value = newToken
        user.value = info
        localStorage.setItem('user_token', newToken)
        localStorage.setItem('user_info', JSON.stringify(info))
    }

    function loadFromStorage() {
        const saved = localStorage.getItem('user_info')
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
        localStorage.removeItem('user_token')
        localStorage.removeItem('user_info')
    }

    return { token, user, setAuth, loadFromStorage, logout }
})
