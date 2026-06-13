import adminApi from '../adminHttp'
import { apiUrl } from '@/config/env'

export interface InventoryItem {
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

export interface InventoryCreateData {
    device_id: string
    category: string
    status?: string
    remain_ratio?: number
    bbox?: number[] | null
    agent_metadata?: Record<string, any> | null
    snapshot_path?: string | null
}

export interface InventoryUpdateData {
    category?: string
    status?: string
    remain_ratio?: number
    bbox?: number[] | null
    agent_metadata?: Record<string, any> | null
    snapshot_path?: string | null
}

export function getInventoryList(params?: {
    device_id?: string
    status?: string
    category?: string
    q?: string
    start_date?: string
    end_date?: string
    expiring_in_days?: number
    limit?: number
    offset?: number
}) {
    return adminApi.get<any, InventoryItem[]>('/inventory', { params })
}

export interface InventoryListPage {
    items: InventoryItem[]
    total: number
}

/**
 * 分页拉库存。需要 X-Total-Count，绕开 axios response interceptor（它把 headers 丢了），
 * 直接用 fetch。
 */
export async function getInventoryListPaged(params: {
    device_id?: string
    status?: string
    category?: string
    q?: string
    start_date?: string
    end_date?: string
    expiring_in_days?: number
    limit: number
    offset: number
}): Promise<InventoryListPage> {
    const token = localStorage.getItem('admin_token') || ''
    const search = new URLSearchParams()
    Object.entries(params).forEach(([k, v]) => {
        if (v !== '' && v !== null && v !== undefined) search.set(k, String(v))
    })
    const r = await fetch(apiUrl(`/admin/inventory?${search.toString()}`), {
        headers: token ? { Authorization: `Bearer ${token}` } : {},
    })
    if (!r.ok) {
        let detail = ''
        try { detail = (await r.json())?.detail || '' } catch { /* ignore */ }
        throw new Error(detail || `HTTP ${r.status}`)
    }
    const items: InventoryItem[] = await r.json()
    const totalHeader = r.headers.get('X-Total-Count')
    return { items, total: totalHeader ? Number(totalHeader) : items.length }
}

export function getCategories() {
    return adminApi.get<any, string[]>('/inventory/categories')
}

export function createInventory(data: InventoryCreateData) {
    return adminApi.post<any, InventoryItem>('/inventory', data)
}

export function updateInventory(id: string, data: InventoryUpdateData) {
    return adminApi.put<any, InventoryItem>(`/inventory/${id}`, data)
}

export function deleteInventory(id: string) {
    return adminApi.delete<any, { detail: string }>(`/inventory/${id}`)
}

export function uploadInventoryImage(file: File) {
    const formData = new FormData()
    formData.append('file', file)
    return adminApi.post<any, { snapshot_path: string; url: string }>('/inventory/upload-image', formData, {
        headers: { 'Content-Type': 'multipart/form-data' }
    })
}

export interface BulkInventoryItemPayload {
    category: string
    confidence?: number
    bbox?: number[] | null
    snapshot_path?: string | null
}

export function bulkCreateInventory(device_id: string, items: BulkInventoryItemPayload[]) {
    return adminApi.post<any, { created_count: number; inventory_ids: string[] }>(
        '/inventory/bulk',
        { device_id, items },
    )
}
