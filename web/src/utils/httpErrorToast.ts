/**
 * 全局 HTTP 错误兜底 toast。
 *
 * 仅对"基础设施类"错误自动弹（网络中断 / 超时 / 5xx），
 * 让业务页面用自己的 catch 处理 4xx 和具体业务文案。
 *
 * 同一类错误 5 秒内只弹一次，避免刷屏。
 */
import { ElMessage } from 'element-plus'

let lastKey = ''
let lastTime = 0

export function maybeToastNetworkError(error: any) {
    // 401 已经在拦截器里跳登录，不弹
    if (error?.response?.status === 401) return

    // 业务错误（4xx 含 detail）不弹，让组件处理
    const status = error?.response?.status
    if (status && status >= 400 && status < 500 && error?.response?.data?.detail) {
        return
    }

    let key = ''
    let msg = ''

    if (!error?.response) {
        // 没有 response：网络中断 / 超时
        if (error?.code === 'ECONNABORTED' || /timeout/i.test(error?.message || '')) {
            key = 'timeout'
            msg = '⏱️ 请求超时，请稍后重试'
        } else if (/Network Error/i.test(error?.message || '')) {
            key = 'network'
            msg = '🔌 网络连接异常，请检查后端是否在线'
        } else {
            key = 'unknown'
            msg = `请求失败：${error?.message || '未知错误'}`
        }
    } else if (status >= 500) {
        key = 'server-' + status
        msg = `🔥 服务端错误（${status}），请稍后重试`
    } else {
        return  // 其它情况不弹
    }

    const now = Date.now()
    if (key === lastKey && now - lastTime < 5000) return  // 5 秒去重
    lastKey = key
    lastTime = now
    ElMessage.error(msg)
}
