import adminApi from '../adminHttp'

export interface DeviceItem {
    id: string
    device_id: string
    name: string
    location: string | null
    description: string | null
    status: string
    live_status: 'online' | 'idle' | 'offline'
    last_seen_at: string | null
    last_event_type: string | null
    heartbeat_count: number
    registered_at: string | null
    seconds_since_last_seen: number | null
}

export interface HeartbeatBucket {
    label: string
    ts: string
    count: number
}

export interface HeartbeatSeries {
    device_id: string
    hours: number
    bucket_minutes: number
    series: HeartbeatBucket[]
}

export function listDevices() {
    return adminApi.get<any, DeviceItem[]>('/devices')
}

export function updateDevice(deviceId: string, data: { name?: string; location?: string; description?: string }) {
    return adminApi.put<any, DeviceItem>(`/devices/${deviceId}`, data)
}

export function deleteDevice(deviceId: string) {
    return adminApi.delete<any, { detail: string }>(`/devices/${deviceId}`)
}

export function restoreDevice(data: { device_id: string; name?: string | null; location?: string | null; description?: string | null }) {
    return adminApi.post<any, DeviceItem>('/devices/restore', data)
}

export function getDeviceHeartbeats(deviceId: string, hours = 24, bucket = 30) {
    return adminApi.get<any, HeartbeatSeries>(`/devices/${deviceId}/heartbeats`, {
        params: { hours, bucket },
    })
}
