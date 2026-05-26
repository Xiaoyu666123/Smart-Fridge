import { defineStore } from 'pinia'
import { ref } from 'vue'

export interface Message {
  role: 'user' | 'assistant'
  content: string
  preferences?: Array<{ key: string; value: string }>
}

export const useChatStore = defineStore('chat', () => {
  const userId = ref('user_001')
  const messages = ref<Message[]>([])
  const loading = ref(false)

  function addMessage(msg: Message) {
    messages.value.push(msg)
  }

  function clearMessages() {
    messages.value = []
  }

  return { userId, messages, loading, addMessage, clearMessages }
})
