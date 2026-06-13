/**
 * 通用的 CSV 下载工具：用 fetch 拉到二进制，从 Content-Disposition 拿文件名，
 * 然后通过临时 a 标签触发浏览器下载。
 */
import { ElMessage } from 'element-plus'
import { apiUrl } from '@/config/env'

export async function downloadCsv(url: string, fallbackName: string) {
    const token = localStorage.getItem('admin_token') || ''
    try {
        const res = await fetch(url, {
            headers: token ? { Authorization: `Bearer ${token}` } : {},
        })
        if (!res.ok) {
            const text = await res.text().catch(() => '')
            throw new Error(text || `HTTP ${res.status}`)
        }
        const blob = await res.blob()
        let filename = fallbackName
        const cd = res.headers.get('Content-Disposition') || ''
        const m = cd.match(/filename="?([^";]+)"?/i) || cd.match(/filename\*=UTF-8''([^;]+)/i)
        if (m) filename = decodeURIComponent(m[1])

        const blobUrl = URL.createObjectURL(blob)
        const a = document.createElement('a')
        a.href = blobUrl
        a.download = filename
        document.body.appendChild(a)
        a.click()
        document.body.removeChild(a)
        URL.revokeObjectURL(blobUrl)
        ElMessage.success(`已开始下载：${filename}`)
    } catch (e: any) {
        ElMessage.error(`下载失败：${e?.message || '未知错误'}`)
    }
}

export function exportInventory() {
    return downloadCsv(apiUrl('/admin/export/inventory'), 'inventory.csv')
}

export function exportUsage() {
    return downloadCsv(apiUrl('/admin/export/usage'), 'usage.csv')
}
