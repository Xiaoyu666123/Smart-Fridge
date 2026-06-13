import adminApi from '../adminHttp'

export interface CategoryThreshold {
    id: string
    category: string
    days_before_expiry: number
    unit_price: number | null
    created_at: string | null
}

export function getThresholds() {
    return adminApi.get<any, CategoryThreshold[]>('/category-thresholds')
}

export function updateThreshold(id: string, data: { days_before_expiry?: number; unit_price?: number | null }) {
    return adminApi.put<any, CategoryThreshold>(`/category-thresholds/${id}`, data)
}
