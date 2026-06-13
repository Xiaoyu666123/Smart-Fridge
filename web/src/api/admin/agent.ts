import adminApi from '../adminHttp'

export interface AgentConfig {
    vision: AgentModelConfig
    llm: AgentModelConfig
    vision_model: string
    vision_status: string
    llm_model: string
    llm_status: string
}

export interface AgentModelConfig {
    provider: string
    model: string
    api_url: string
    api_key_masked: string | null
    status: string
    has_api_key: boolean
}

export interface AgentConfigUpdate {
    vision: {
        provider: string
        model: string
        api_url: string
        api_key?: string | null
    }
    llm: {
        provider: string
        model: string
        api_url: string
        api_key?: string | null
    }
}

export function getAgentConfig() {
    return adminApi.get<any, AgentConfig>('/agent/config')
}

export function updateAgentConfig(data: AgentConfigUpdate) {
    return adminApi.put<any, AgentConfig>('/agent/config', data)
}


// ---- 整柜批量识别 ----
export interface DetectedItem {
    category: string
    confidence: number
    bbox: number[]   // 相对坐标 [x, y, w, h]，范围 0~1
}

export function detectFoods(image: string) {
    return adminApi.post<any, { items: DetectedItem[] }>('/agent/detect', { image })
}


// ---- 视觉辅助识别策略 ----
export interface VisionAssistConfig {
    id: string
    lower: number
    upper: number
    updated_at: string | null
    updated_by_admin_id: string | null
    is_default: boolean
}

export function getVisionAssistConfig() {
    return adminApi.get<any, VisionAssistConfig>('/agent/vision-assist-config')
}

export function updateVisionAssistConfig(lower: number, upper: number) {
    return adminApi.put<any, VisionAssistConfig>('/agent/vision-assist-config', { lower, upper })
}
