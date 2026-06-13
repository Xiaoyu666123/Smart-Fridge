import adminApi from '../adminHttp'

export interface ToolPerf {
    tool_name: string
    count: number
    success_count: number
    fail_count: number
    success_rate: number
    avg_ms: number
    p50_ms: number
    p95_ms: number
    max_ms: number
}

export interface PerfTrendPoint {
    label: string
    count: number
}

export interface PerfStats {
    window_hours: number
    total_steps: number
    tools: ToolPerf[]
    trend: PerfTrendPoint[]
    weekday_hour_heatmap: [number, number, number][]   // [hour, weekday, count]
}

export function getPerfStats(hours = 24) {
    return adminApi.get<any, PerfStats>('/stats/perf', { params: { hours } })
}

export interface InventoryTraceStep {
    id: number
    step_order: number
    tool_name: string
    tool_input: any
    tool_output: any
    status: string
    duration_ms: number | null
}

export interface InventoryTrace {
    trace_id: string | null
    agent_type?: string
    device_id?: string | null
    steps: InventoryTraceStep[]
}

export function getInventoryLastTrace(inventoryId: string) {
    return adminApi.get<any, InventoryTrace>(`/inventory/${inventoryId}/last-trace`)
}
