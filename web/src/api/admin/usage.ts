import adminApi from '../adminHttp'

export interface UsageProviderRow {
    provider: string
    calls: number
    tokens: number
    cost_usd: number
}

export interface UsageEndpointRow {
    endpoint: string
    calls: number
    tokens: number
    cost_usd: number
}

export interface UsageDailyRow {
    date: string | null
    calls: number
    tokens: number
    cost_usd: number
}

export interface UsageSummary {
    since: string
    total_calls: number
    failed_calls: number
    total_tokens: number
    total_cost_usd: number
    by_provider: UsageProviderRow[]
    by_endpoint: UsageEndpointRow[]
    daily: UsageDailyRow[]
}

export interface UsageRecord {
    id: number
    provider: string
    model: string
    endpoint: string | null
    user_id: string | null
    prompt_tokens: number
    completion_tokens: number
    total_tokens: number
    cost_usd: number
    duration_ms: number | null
    status: string
    created_at: string | null
}

export function getUsageSummary(days = 30) {
    return adminApi.get<any, UsageSummary>('/usage/summary', { params: { days } })
}

export function getUsageRecords(params?: { limit?: number; offset?: number; provider?: string; endpoint?: string; status?: string }) {
    return adminApi.get<any, UsageRecord[]>('/usage/records', { params })
}
