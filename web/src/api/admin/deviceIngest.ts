import adminApi from '../adminHttp'

export type DeviceRawEventStatus = 'received' | 'processing' | 'success' | 'failed' | 'ignored'

export interface DeviceRawEvent {
    id: string
    device_id: string | null
    event_type: string | null
    raw_payload: Record<string, any> | null
    normalized_payload: Record<string, any> | null
    status: DeviceRawEventStatus
    error_message: string | null
    related_inventory_ids: string[] | null
    trace_id: string | null
    created_at: string | null
    processed_at: string | null
}

export interface DeviceRawEventQuery {
    device_id?: string
    event_type?: string
    status?: string
    limit?: number
    offset?: number
}

export function ingestDevicePayload(payload: Record<string, any>) {
    return adminApi.post<any, DeviceRawEvent>('/device-ingest', payload)
}

export function listDeviceRawEvents(params?: DeviceRawEventQuery) {
    return adminApi.get<any, DeviceRawEvent[]>('/device-raw-events', { params })
}

export function getDeviceRawEvent(id: string) {
    return adminApi.get<any, DeviceRawEvent>(`/device-raw-events/${id}`)
}

export function reprocessDeviceRawEvent(id: string) {
    return adminApi.post<any, DeviceRawEvent>(`/device-raw-events/${id}/reprocess`)
}
