import adminApi from '../adminHttp'

export interface PendingLabelItem {
    id: string
    device_id: string
    label_image_path: string | null
    label_text: string | null
    label_data: Record<string, any> | null
    created_at: string | null
    expires_at: string | null
    consumed_at: string | null
    consumed_by_inventory_id: string | null
    status: 'pending' | 'consumed' | 'expired'
}

export interface LabelScanResponse {
    pending_label_id: string
    label_text: string
    label_data: Record<string, any>
    expires_at: string
}

export function listPendingLabels(params?: { device_id?: string; status?: string; limit?: number }) {
    return adminApi.get<any, PendingLabelItem[]>('/pending-labels', { params })
}

export function deletePendingLabel(id: string) {
    return adminApi.delete<any, { detail: string }>(`/pending-labels/${id}`)
}

export function scanLabel(data: { device_id?: string; label_image: string; ttl_seconds?: number }) {
    return adminApi.post<any, LabelScanResponse>('/events/label_scan', data)
}
