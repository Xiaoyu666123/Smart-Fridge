/**
 * Inventory 实时事件订阅 composable。
 *
 * 用法（admin 端）：
 *   const { connected } = useInventoryWS({
 *     scope: 'admin',
 *     onCreated: (it, source) => items.value.unshift(it),
 *     onUpdated: (it) => { ... },
 *     onDeleted: (id) => { ... },
 *   })
 *
 * scope 可以是 'admin' 或 'user'，分别用 admin_token / user_token 鉴权，
 * 连不同的 ws 端点。后端 broadcast_all 会把库存事件广播到所有连接，
 * 因此 user scope 用现有的通知端点也能收到。
 */

import { onBeforeUnmount, onMounted, ref } from 'vue'
import { wsUrl } from '@/config/env'

export type InventorySource = 'agent' | 'manual' | 'bulk'

export interface InventoryWSEvent {
    id: string
    device_id: string
    category: string
    status: string
    remain_ratio: number
    bbox: number[] | null
    agent_metadata: Record<string, any> | null
    snapshot_path: string | null
    label_text: string | null
    label_data: Record<string, any> | null
    label_snapshot_path: string | null
    has_label: boolean
    label_status: 'label' | 'no_label'
    expire_source: 'label' | 'llm_estimate' | 'manual' | null
    expire_at: string | null
    brand: string | null
    created_at: string | null
    update_at: string | null
    stored_at: string | null
}

export interface UseInventoryWSOptions {
    scope?: 'admin' | 'user'
    onCreated?: (item: InventoryWSEvent, source: InventorySource) => void
    onUpdated?: (item: InventoryWSEvent, source: InventorySource, prevStatus: string | null) => void
    onDeleted?: (id: string, source: InventorySource) => void
    /** 是否在 onMounted 时自动连接，默认 true */
    autoConnect?: boolean
}

export function useInventoryWS(opts: UseInventoryWSOptions) {
    const scope = opts.scope || 'admin'
    const connected = ref(false)
    let ws: WebSocket | null = null
    let pingTimer: ReturnType<typeof setInterval> | null = null
    let reconnectTimer: ReturnType<typeof setTimeout> | null = null
    let manualClosed = false

    function buildUrl(): string | null {
        if (scope === 'admin') {
            const token = localStorage.getItem('admin_token') || ''
            if (!token) return null
            return wsUrl(`/admin/ws/inventory?token=${encodeURIComponent(token)}`)
        } else {
            // 普通用户复用现有的 notifications 端点（broadcast_all 已经推到所有连接）
            const token = localStorage.getItem('user_token') || ''
            if (!token) return null
            return wsUrl(`/user/ws/notifications?token=${encodeURIComponent(token)}`)
        }
    }

    function connect() {
        if (manualClosed) return
        const url = buildUrl()
        if (!url) return
        try {
            ws = new WebSocket(url)
        } catch (e) {
            console.warn('[inventoryWS] create failed', e)
            scheduleReconnect()
            return
        }
        ws.onopen = () => {
            connected.value = true
            if (pingTimer) clearInterval(pingTimer)
            pingTimer = setInterval(() => {
                try { ws?.send('ping') } catch { }
            }, 30000)
        }
        ws.onmessage = (evt) => {
            if (evt.data === 'pong') return
            let ev: any
            try { ev = JSON.parse(evt.data) } catch { return }
            if (!ev || !ev.type) return
            switch (ev.type) {
                case 'inventory.created':
                    if (ev.data && opts.onCreated) opts.onCreated(ev.data, ev.source || 'agent')
                    break
                case 'inventory.updated':
                    if (ev.data && opts.onUpdated) opts.onUpdated(ev.data, ev.source || 'manual', ev.prev_status || null)
                    break
                case 'inventory.deleted':
                    if (ev.id && opts.onDeleted) opts.onDeleted(ev.id, ev.source || 'manual')
                    break
            }
        }
        ws.onerror = (e) => {
            console.warn('[inventoryWS] error', e)
        }
        ws.onclose = () => {
            connected.value = false
            if (pingTimer) { clearInterval(pingTimer); pingTimer = null }
            scheduleReconnect()
        }
    }

    function scheduleReconnect() {
        if (manualClosed) return
        if (reconnectTimer) return
        reconnectTimer = setTimeout(() => {
            reconnectTimer = null
            connect()
        }, 5000)
    }

    function close() {
        manualClosed = true
        if (pingTimer) { clearInterval(pingTimer); pingTimer = null }
        if (reconnectTimer) { clearTimeout(reconnectTimer); reconnectTimer = null }
        try { ws?.close() } catch { }
        ws = null
    }

    if (opts.autoConnect !== false) {
        onMounted(() => connect())
    }
    onBeforeUnmount(() => close())

    return { connected, connect, close }
}
