import api from './index'

export interface ChatRequest {
  message: string
  city?: string
}

export interface ChatResponse {
  reply: string
  detected_preferences: Array<{ key: string; value: string }>
}

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
  return api.get<any, ConversationItem[]>('/agent/conversations', { params: { limit } })
}

export function chat(data: ChatRequest) {
  return api.post<any, ChatResponse>('/agent/chat', data)
}

export function recognize(data: { image: string }) {
  return api.post<any, RecognizeResponse>('/agent/recognize', data)
}

export function getPreferences() {
  return api.get<any, PreferenceItem[]>('/agent/preferences')
}

export function addPreference(data: { preference_key: string; preference_value: string }) {
  return api.post<any, PreferenceItem>('/agent/preferences', data)
}

export function deletePreference(preferenceId: string) {
  return api.delete<any, { detail: string }>(`/agent/preferences/${preferenceId}`)
}

export interface AgentConfig {
  vision_model: string
  vision_status: string
  llm_model: string
  llm_status: string
}

export function getAgentConfig() {
  return api.get<any, AgentConfig>('/agent/config')
}
