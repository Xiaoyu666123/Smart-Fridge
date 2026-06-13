import axios from 'axios'
import { maybeToastNetworkError } from '@/utils/httpErrorToast'
import { apiUrl } from '@/config/env'

const adminApi = axios.create({
    baseURL: apiUrl('/admin'),
    timeout: 120000, // 部分管理操作要调云端视觉 + 向量，最长给 2 分钟
})

adminApi.interceptors.request.use((config) => {
    const token = localStorage.getItem('admin_token')
    if (token) {
        config.headers.Authorization = `Bearer ${token}`
    }
    return config
})

adminApi.interceptors.response.use(
    (response) => response.data,
    (error) => {
        if (error.response?.status === 401) {
            localStorage.removeItem('admin_token')
            localStorage.removeItem('admin_info')
            if (location.pathname.startsWith('/admin')) {
                location.href = '/login'
            }
        }
        const msg = error.response?.data?.detail || error.message || '请求失败'
        console.error('[Admin API]', msg)
        // 基础设施类错误统一兜底 toast（业务 4xx 让组件自己处理）
        maybeToastNetworkError(error)
        return Promise.reject(error)
    }
)

export default adminApi
