import adminApi from '../adminHttp'

export interface WasteCategoryItem {
    category: string
    count: number
    unit_price?: number | null
    estimated_value?: number | null
}

export interface RestockSuggestion {
    category: string
    consumed_count: number
    current_stock: number
    suggested_qty?: number
    unit_price?: number | null
    estimated_cost?: number | null
    reason: string
}

export interface WasteAnalytics {
    window_days: number
    total: number
    wasted: number
    consumed_in_time: number
    in_stock: number
    waste_rate: number
    wasted_value: number
    consumed_value: number
    priced_categories: number
    total_categories_seen: number
    top_wasted: WasteCategoryItem[]
    top_consumed: WasteCategoryItem[]
    restock_suggestions: RestockSuggestion[]
}

export function getWasteAnalytics(days = 30) {
    return adminApi.get<any, WasteAnalytics>('/stats/waste', { params: { days } })
}

// ---- 食材生命周期（Sankey）----

export interface SankeyNode {
    name: string
    depth: number
}

export interface SankeyLink {
    source: string
    target: string
    value: number
}

export interface LifecycleSankey {
    window_days: number
    total: number
    nodes: SankeyNode[]
    links: SankeyLink[]
    categories: {
        sources: string[]
        categories: string[]
        states: string[]
    }
}

export function getLifecycleSankey(days = 30, topN = 8) {
    return adminApi.get<any, LifecycleSankey>('/stats/lifecycle', { params: { days, top_n: topN } })
}

// ---- 浪费金额日历热力图 ----

export interface WasteCalendar {
    window_days: number
    start: string
    end: string
    max_value: number
    total_value: number
    total_count: number
    days_with_waste: number
    series: [string, number, number][]   // [date, value, count]
}

export function getWasteCalendar(days = 365) {
    return adminApi.get<any, WasteCalendar>('/stats/waste-calendar', { params: { days } })
}
