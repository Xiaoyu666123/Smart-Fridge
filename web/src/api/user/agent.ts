import userApi from '../userHttp'
import { apiUrl } from '@/config/env'

export interface RecognizeResponse {
    category: string
    confidence: number
    shelf_life_days: number
    storage_advice: string
}

export interface PreferenceItem {
    id: string
    user_id: string
    preference_key: string
    preference_value: string
    source: string | null
    created_at: string | null
}

export interface ConversationItem {
    id: number
    role: 'user' | 'assistant'
    content: string
    created_at: string | null
}

export function getConversations(limit = 100) {
    return userApi.get<any, ConversationItem[]>('/agent/conversations', { params: { limit } })
}

export function recognize(data: { image: string }) {
    return userApi.post<any, RecognizeResponse>('/agent/recognize', data)
}

export function getPreferences() {
    return userApi.get<any, PreferenceItem[]>('/agent/preferences')
}

export function addPreference(data: { preference_key: string; preference_value: string }) {
    return userApi.post<any, PreferenceItem>('/agent/preferences', data)
}

export function deletePreference(preferenceId: string) {
    return userApi.delete<any, { detail: string }>(`/agent/preferences/${preferenceId}`)
}

// ---- 流式 chat ----
//
// 使用 fetch stream 传 Authorization，避免把 token 放进 URL。
// 调用方提供 onDelta（每段文本）/ onDone（结束帧，含偏好）/ onError 回调。

export interface StreamChatHandlers {
    onDelta: (piece: string) => void
    onDone?: (info: { detected_preferences: Array<{ key: string; value: string }>; trace_id: string }) => void
    onError?: (msg: string) => void
}

export function streamChat(
    message: string,
    city: string | undefined,
    handlers: StreamChatHandlers,
    opts: { structured?: boolean } = {}
): () => void {
    const token = localStorage.getItem('user_token') || ''
    const params = new URLSearchParams({ message })
    if (city) params.set('city', city)
    if (opts.structured) params.set('structured', 'true')
    const url = apiUrl(`/user/agent/chat/stream?${params.toString()}`)
    const controller = new AbortController()

    fetch(url, {
        method: 'GET',
        headers: token ? { Authorization: `Bearer ${token}` } : {},
        signal: controller.signal,
    }).then(async (res) => {
        if (!res.ok || !res.body) {
            handlers.onError?.('连接失败')
            return
        }
        const reader = res.body.getReader()
        const decoder = new TextDecoder()
        let buffer = ''

        while (true) {
            const { done, value } = await reader.read()
            if (done) break
            buffer += decoder.decode(value, { stream: true })

            const frames = buffer.split('\n\n')
            buffer = frames.pop() || ''

            for (const frame of frames) {
                const line = frame.split('\n').find((x) => x.startsWith('data: '))
                if (!line) continue
                try {
                    const data = JSON.parse(line.slice(6))
                    if (data.type === 'delta') {
                        handlers.onDelta(data.content || '')
                    } else if (data.type === 'done') {
                        handlers.onDone?.({ detected_preferences: data.detected_preferences || [], trace_id: data.trace_id })
                        controller.abort()
                        return
                    } else if (data.type === 'error') {
                        handlers.onError?.(data.message || '请求失败')
                        controller.abort()
                        return
                    }
                } catch (e) {
                    console.error('[stream] parse error', e, line)
                }
            }
        }
    }).catch((err) => {
        if (!controller.signal.aborted) {
            console.error('[stream] request error', err)
            handlers.onError?.('连接中断')
        }
    })

    return () => controller.abort()
}


// ---- 食谱收藏 ----
export interface RecipeIngredient {
    name: string
    amount?: string | null
}

export interface SavedRecipe {
    id: string
    user_id: string
    name: string
    summary: string | null
    prep_time: number | null
    difficulty: string | null
    ingredients: RecipeIngredient[] | null
    steps: string[] | null
    tags: string[] | null
    source: string | null
    cooked_count: number
    last_cooked_at: string | null
    rating: number | null
    notes: string | null
    created_at: string | null
}

export function saveRecipe(payload: Partial<SavedRecipe>) {
    return userApi.post<any, SavedRecipe>('/recipes', payload)
}

export function listSavedRecipes(limit = 50) {
    return userApi.get<any, SavedRecipe[]>('/recipes', { params: { limit } })
}

export function deleteSavedRecipe(id: string) {
    return userApi.delete<any, { detail: string }>(`/recipes/${id}`)
}

export interface CookRecipeResult {
    recipe: SavedRecipe
    consumed_count: number
    consumed_inventory_ids: string[]
    skipped_inventory_ids: string[]
}

export function cookRecipe(id: string, consumed_inventory_ids: string[] = []) {
    return userApi.post<any, CookRecipeResult>(`/recipes/${id}/cook`, { consumed_inventory_ids })
}

export function updateRecipeMeta(id: string, data: { rating?: number; notes?: string }) {
    return userApi.put<any, SavedRecipe>(`/recipes/${id}`, data)
}

// ---- 食材替换助手 ----

export interface SubstituteOption {
    name: string
    reason: string
    in_stock: boolean
}

export interface SubstituteResult {
    ingredient: string
    recipe_name: string
    available_count: number
    summary: string
    options: SubstituteOption[]
}

export function getSubstitute(ingredient: string, recipe_name = '') {
    return userApi.post<any, SubstituteResult>('/agent/substitute',
        { ingredient, recipe_name },
        { timeout: 60_000 })
}

// ---- 每日 AI 小贴士 ----

export interface DailyTip {
    date: string
    tip: string
    cached: boolean
}

export function getDailyTip(refresh = false) {
    return userApi.get<any, DailyTip>('/agent/daily-tip',
        { params: refresh ? { refresh: true } : {}, timeout: 90_000 })
}


// ---- 自然语言库存查询 ----

export interface InventoryQueryResult {
    question: string
    in_stock_count: number
    answer: string
    matched: string[]
}

export function queryInventory(question: string) {
    return userApi.post<any, InventoryQueryResult>(
        '/agent/inventory-query',
        { question },
        { timeout: 60_000 },
    )
}
