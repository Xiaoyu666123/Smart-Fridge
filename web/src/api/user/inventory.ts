import userApi from '../userHttp'

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

export function getInventoryList(params?: {
    device_id?: string
    status?: string
    category?: string
    q?: string
    start_date?: string
    end_date?: string
    expiring_in_days?: number
}) {
    return userApi.get<any, InventoryItem[]>('/inventory', { params })
}

export function getCategories() {
    return userApi.get<any, string[]>('/inventory/categories')
}
