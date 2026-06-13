/**
 * 统一的后端地址配置中心。
 *
 * - 本地开发（dev）：VITE_API_BASE 留空，走相对路径 '/api/v1'，由 Vite proxy 转发到 localhost:8000。
 * - 打包成 App / 部署到云：在 .env.production 里配 VITE_API_BASE=https://你的域名
 *   则所有 REST / SSE / WebSocket 都指向该绝对地址。
 *
 * 用法：
 *   import { API_BASE, apiUrl, wsUrl } from '@/config/env'
 *   axios.create({ baseURL: apiUrl('/admin') })          // -> /api/v1/admin 或 https://x/api/v1/admin
 *   new WebSocket(wsUrl('/admin/ws/inventory?token=...')) // 自动转 ws/wss
 */

// 去掉结尾斜杠，统一形态。空字符串表示"用相对路径 + vite proxy"。
const RAW_BASE = (import.meta.env.VITE_API_BASE || '').replace(/\/+$/, '')

/** 后端根地址（不含 /api/v1）。本地为空字符串。 */
export const API_BASE = RAW_BASE

/** /api/v1 前缀（REST 用）。本地 -> '/api/v1'，云端 -> 'https://x/api/v1' */
export const API_PREFIX = `${API_BASE}/api/v1`

/**
 * 拼 REST 路径。
 * apiUrl('/admin') -> '/api/v1/admin'（本地） 或 'https://x/api/v1/admin'（云端）
 */
export function apiUrl(path = ''): string {
    const p = path.startsWith('/') ? path : `/${path}`
    return `${API_PREFIX}${p}`
}

/**
 * 拼 WebSocket 完整地址（自动选 ws/wss）。
 * wsUrl('/admin/ws/inventory?token=x')
 *  - 本地：ws://当前host/api/v1/admin/ws/inventory?token=x
 *  - 云端：wss://你的域名/api/v1/admin/ws/inventory?token=x
 */
export function wsUrl(path = ''): string {
    const p = path.startsWith('/') ? path : `/${path}`
    if (API_BASE) {
        // 云端：把 http(s) 协议换成 ws(s)
        const wsBase = API_BASE.replace(/^http/i, 'ws')
        return `${wsBase}/api/v1${p}`
    }
    // 本地：沿用当前页面 host，由 vite proxy 升级 ws
    const proto = location.protocol === 'https:' ? 'wss:' : 'ws:'
    return `${proto}//${location.host}/api/v1${p}`
}

/**
 * 拼后端静态资源（上传图片）地址。
 * uploadUrl('inv_xxx.jpg') -> '/uploads/inv_xxx.jpg'（本地）或 'https://x/uploads/inv_xxx.jpg'（云端）
 * 传入已是 http(s) 完整地址时原样返回。
 */
export function uploadUrl(pathOrName: string | null | undefined): string {
    if (!pathOrName) return ''
    if (/^https?:\/\//i.test(pathOrName)) return pathOrName
    const filename = pathOrName.replace(/\\/g, '/').split('/').pop() || ''
    return `${API_BASE}/uploads/${filename}`
}
