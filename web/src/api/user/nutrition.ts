import userApi from '../userHttp'

export interface NutritionDistItem {
    tag: string
    label: string
    emoji: string
    color: string
    count: number
    healthy: boolean
}

export interface NutritionByCategory {
    category: string
    tag: string
    label: string
    emoji: string
    color: string
    count: number
    healthy: boolean
}

export interface HealthAssessment {
    score: number
    level: 'good' | 'fair' | 'poor'
    tips: string[]
    veg_fruit_ratio: number
    meat_ratio: number
    snack_ratio: number
}

export interface NutritionReport {
    window_days: number
    total: number
    consumed_total: number
    distribution: NutritionDistItem[]
    consumed_distribution: NutritionDistItem[]
    by_category: NutritionByCategory[]
    health_overall: HealthAssessment
    health_consumed: HealthAssessment | null
}

export function getNutritionReport(days = 30) {
    return userApi.get<any, NutritionReport>('/stats/nutrition', { params: { days } })
}

// ---- 烹饪日历 ----

export interface CookingTopRecipe {
    name: string
    cooked_count: number
    last_cooked_at: string | null
}

export interface CookingCalendar {
    window_days: number
    start: string
    end: string
    total_recipes: number
    total_cooks: number
    days_with_cook: number
    current_streak: number
    max_per_day: number
    top_recipes: CookingTopRecipe[]
    series: [string, number, string[]][]
}

export function getCookingCalendar(days = 365) {
    return userApi.get<any, CookingCalendar>('/stats/cooking', { params: { days } })
}

export interface CoachAdvice {
    summary: string
    week_plan: string[]
    action_items: string[]
    avoid: string[]
}

export interface CoachResponse {
    window_days: number
    health: any
    expiring: { category: string; days: number }[]
    recent_consumed: { category: string; count: number }[]
    advice: CoachAdvice
}

export function getCoachAdvice(days = 30) {
    return userApi.get<any, CoachResponse>('/agent/coach', { params: { days }, timeout: 90_000 })
}


// ---- 成就墙 / 个人档案 ----

export interface AchievementBadge {
    id: string
    name: string
    desc: string
    emoji: string
    unlocked: boolean
    progress: number
    total: number
}

export interface AchievementProfile {
    username: string
    register_at: string | null
    register_days: number
    saved_count: number
    total_cooks: number
    distinct_cooked_days: number
    rated_count: number
    note_count: number
    pref_count: number
    inv_total: number
    inv_consumed: number
    inv_wasted: number
    inv_categories: number
    notif_count: number
    level_name: string
    level_idx: number
    level_score: number
    level_next_score: number
    consume_30d: number
    unlocked_count: number
    total_count: number
}

export interface AchievementResponse {
    profile: AchievementProfile
    achievements: AchievementBadge[]
    consume_trend: [string, number][]
}

export function getAchievements() {
    return userApi.get<any, AchievementResponse>('/stats/achievements')
}
