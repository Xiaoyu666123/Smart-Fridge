import api from './index'

export interface EventLog {
  id: number
  inventory_id: string
  event_type: string
  confidence: number | null
  snapshot_path: string | null
  create_at: string | null
}

export function getEventLogs(params?: { inventory_id?: string }) {
  return api.get<any, EventLog[]>('/events', { params })
}
