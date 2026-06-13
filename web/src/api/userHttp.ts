import axios from 'axios'
import { maybeToastNetworkError } from '@/utils/httpErrorToast'
import { apiUrl } from '@/config/env'

const userApi = axios.create({
    baseURL: apiUrl('/user'),
    timeout: 60000,
})

userApi.interceptors.request.use((config) => {
    const token = localStorage.getItem('user_token')
    if (token) {
        config.headers.Authorization = `Bearer ${token}`
    }
    return config
})

userApi.interceptors.response.use(
    (response) => response.data,
    (error) => {
        if (error.response?.status === 401) {
            localStorage.removeItem('user_token')
            localStorage.removeItem('user_info')
            if (location.pathname.startsWith('/user')) {
                location.href = '/login'
            }
        }
        const msg = error.response?.data?.detail || error.message || '请求失败'
        console.error('[User API]', msg)
        maybeToastNetworkError(error)
        return Promise.reject(error)
    }
)

export default userApi
