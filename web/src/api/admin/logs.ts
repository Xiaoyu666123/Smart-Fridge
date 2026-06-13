import adminApi from '../adminHttp'

export interface LogEntry {
    id: string
    source: string
    event_type: string
    status: string
    detail: Record<string, any> | null
    created_at: string | null
}

export function getLogs(params?: { source?: string; event_type?: string; status?: string; limit?: number; offset?: number }) {
    return adminApi.get<any, LogEntry[]>('/logs', { params })
}
