import adminApi from '../adminHttp'

export interface EventLog {
    id: number
    inventory_id: string
    event_type: string
    confidence: number | null
    snapshot_path: string | null
    create_at: string | null
}

export function getEventLogs(params?: { inventory_id?: string }) {
    return adminApi.get<any, EventLog[]>('/events', { params })
}
