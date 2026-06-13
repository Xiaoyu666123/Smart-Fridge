import { defineStore } from 'pinia'
import { ref } from 'vue'

export interface RecipeCardData {
  name: string
  summary?: string | null
  prep_time?: number | null
  difficulty?: string | null
  ingredients?: Array<{ name: string; amount?: string | null }> | null
  steps?: string[] | null
  tags?: string[] | null
}

export interface Message {
  role: 'user' | 'assistant'
  content: string
  preferences?: Array<{ key: string; value: string }>
  recipes?: RecipeCardData[]      // 结构化食谱卡片
  structured?: boolean             // 是否结构化模式（用于决定渲染方式）
  parseBuffer?: string             // 流式解析的 raw 缓冲（解析过的字段会从 content 移除）
  savedRecipeIds?: Record<string, string>  // recipe.name -> 后端 saved_recipe.id（成功收藏后填）
  invMatched?: string[]            // 库存问答命中的食材品类（用于渲染标签）
  kind?: 'recipe' | 'inventory'    // 消息类型：食谱推荐 / 库存问答
}

export const useChatStore = defineStore('chat', () => {
  const messages = ref<Message[]>([])
  const loading = ref(false)
  // 跨页面投递消息：首页 / 临期页等地方点"问 AI"，
  // 在跳转前把要发送的文本塞进来，Chat.vue onMounted 时自动发送
  const queuedMessage = ref<string>('')

  function addMessage(msg: Message) {
    messages.value.push(msg)
  }

  function clearMessages() {
    messages.value = []
  }

  return { messages, loading, queuedMessage, addMessage, clearMessages }
})
