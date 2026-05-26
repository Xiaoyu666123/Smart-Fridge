import api from './index'

export interface TraceStep {
  id: number
  step_order: number
  tool_name: string
  tool_input: Record<string, any> | null
  tool_output: Record<string, any> | null
  status: string
  duration_ms: number | null
}

export interface TraceSummary {
  trace_id: string
  agent_type: string
  device_id: string | null
  step_count: number
  total_duration_ms: number | null
  created_at: string | null
}

export interface TraceDetail {
  trace_id: string
  agent_type: string
  device_id: string | null
  steps: TraceStep[]
}

export function getTraceList(params?: { agent_type?: string; device_id?: string; limit?: number; offset?: number }) {
  return api.get<any, TraceSummary[]>('/traces', { params })
}

export function getTraceDetail(traceId: string) {
  return api.get<any, TraceDetail>(`/traces/${traceId}`)
}
