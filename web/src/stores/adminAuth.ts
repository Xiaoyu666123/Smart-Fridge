import { defineStore } from 'pinia'
import { ref } from 'vue'

export interface AdminInfo {
    id: string
    username: string
    user_type: 'admin'
    real_name?: string | null
}

export const useAdminAuthStore = defineStore('adminAuth', () => {
    const token = ref(localStorage.getItem('admin_token') || '')
    const admin = ref<AdminInfo | null>(null)

    function setAuth(newToken: string, info: AdminInfo) {
        token.value = newToken
        admin.value = info
        localStorage.setItem('admin_token', newToken)
        localStorage.setItem('admin_info', JSON.stringify(info))
    }

    function loadFromStorage() {
        const saved = localStorage.getItem('admin_info')
        if (token.value && saved) {
            try {
                admin.value = JSON.parse(saved)
            } catch {
                logout()
            }
        }
    }

    function logout() {
        token.value = ''
        admin.value = null
        localStorage.removeItem('admin_token')
        localStorage.removeItem('admin_info')
    }

    return { token, admin, setAuth, loadFromStorage, logout }
})
