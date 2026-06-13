/**
 * 撤销操作 toast：用 ElNotification 显示一条带"撤销"按钮的通知，
 * N 秒倒计时；用户点击撤销就回调 onUndo；超时不点就执行 onCommit。
 *
 * 用法：
 *   showUndoToast({
 *     message: '已删除 番茄',
 *     onUndo: async () => { ... 重新创建 ... },
 *     onCommit: () => { ... 真正确认/同步服务端 ... }
 *   })
 */
import { h } from 'vue'
import { ElNotification } from 'element-plus'

interface UndoOptions {
    message: string
    /** 倒计时秒数，默认 5 秒 */
    duration?: number
    /** 用户点击撤销时调用 */
    onUndo: () => void | Promise<void>
    /** 倒计时结束未撤销时调用，可选 */
    onCommit?: () => void | Promise<void>
}

export function showUndoToast(opts: UndoOptions) {
    const dur = (opts.duration ?? 5) * 1000
    let undoClicked = false
    let timerId: ReturnType<typeof setTimeout> | null = null
    let notif: { close: () => void } | null = null

    const handleUndo = async () => {
        if (undoClicked) return
        undoClicked = true
        if (timerId) clearTimeout(timerId)
        try {
            await opts.onUndo()
        } catch (e) {
            console.warn('[UndoToast] undo failed', e)
        }
        notif?.close()
    }

    notif = ElNotification({
        title: '操作已完成',
        duration: dur,
        position: 'bottom-right',
        customClass: 'undo-toast',
        message: h('div', { style: 'display:flex;align-items:center;gap:12px;' }, [
            h('span', { style: 'flex:1;color:var(--text-primary)' }, opts.message),
            h('button', {
                style: `
          padding: 3px 12px;
          border-radius: 999px;
          border: 1px solid var(--brand-primary);
          background: var(--brand-primary-soft);
          color: var(--brand-primary-dark);
          font-size: 12px;
          font-weight: 600;
          cursor: pointer;
        `,
                onClick: handleUndo,
            }, '撤销'),
        ]),
    })

    timerId = setTimeout(async () => {
        if (undoClicked) return
        try {
            await opts.onCommit?.()
        } catch (e) {
            console.warn('[UndoToast] commit failed', e)
        }
    }, dur)
}
