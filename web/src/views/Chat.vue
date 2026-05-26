<script setup lang="ts">
import { ref, nextTick, onMounted, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { useChatStore } from '@/stores/chat'
import { useAuthStore } from '@/stores/auth'
import { chat, getConversations, type ConversationItem } from '@/api/agent'
import ChatMessage from '@/components/ChatMessage.vue'

const chatStore = useChatStore()
const authStore = useAuthStore()
const inputMessage = ref('')
const chatBody = ref<HTMLElement>()
const city = ref('')
const sidebarOpen = ref(true)
const historyLoading = ref(false)
const historyItems = ref<ConversationItem[]>([])

async function loadHistory() {
  historyLoading.value = true
  try {
    historyItems.value = await getConversations()
  } catch (e) {
    console.error(e)
  } finally {
    historyLoading.value = false
  }
}

function scrollToBottom() {
  nextTick(() => {
    if (chatBody.value) {
      chatBody.value.scrollTop = chatBody.value.scrollHeight
    }
  })
}

async function sendMessage() {
  const msg = inputMessage.value.trim()
  if (!msg) return

  chatStore.addMessage({ role: 'user', content: msg })
  inputMessage.value = ''
  chatStore.loading = true
  scrollToBottom()

  try {
    const res = await chat({
      message: msg,
      city: city.value || undefined,
    })
    chatStore.addMessage({
      role: 'assistant',
      content: res.reply,
      preferences: res.detected_preferences,
    })

    if (res.detected_preferences.length > 0) {
      const prefs = res.detected_preferences.map(p => p.value).join('、')
      ElMessage.success(`已记住您的偏好：${prefs}`)
    }

    loadHistory()
  } catch (e) {
    chatStore.addMessage({ role: 'assistant', content: '抱歉，推荐服务暂时不可用，请稍后再试。' })
  } finally {
    chatStore.loading = false
    scrollToBottom()
  }
}

function handleKeydown(e: KeyboardEvent) {
  if (e.key === 'Enter' && !e.shiftKey) {
    e.preventDefault()
    sendMessage()
  }
}

onMounted(loadHistory)
</script>

<template>
  <div class="chat-layout">
    <!-- 侧边栏：对话历史 -->
    <div :class="['chat-sidebar', { 'sidebar-collapsed': !sidebarOpen }]">
      <div class="sidebar-header">
        <span v-if="sidebarOpen" class="sidebar-title">对话记录</span>
        <el-icon class="sidebar-toggle" @click="sidebarOpen = !sidebarOpen">
          <Fold v-if="sidebarOpen" />
          <Expand v-else />
        </el-icon>
      </div>

      <div v-if="sidebarOpen" class="sidebar-body" v-loading="historyLoading">
        <div v-if="historyItems.length === 0" class="sidebar-empty">
          暂无历史对话
        </div>
        <div v-for="(item, i) in historyItems" :key="item.id" :class="['history-item', `history-${item.role}`]">
          <div class="history-icon">
            <el-icon v-if="item.role === 'user'" :size="14"><User /></el-icon>
            <el-icon v-else :size="14"><Cpu /></el-icon>
          </div>
          <div class="history-content">
            <div class="history-text">{{ item.content }}</div>
            <div class="history-time" v-if="item.created_at">{{ new Date(item.created_at).toLocaleString('zh-CN', { month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' }) }}</div>
          </div>
        </div>
      </div>
    </div>

    <!-- 主聊天区 -->
    <el-card shadow="never" class="chat-main">
      <template #header>
        <div class="chat-header">
          <div class="chat-title">
            <el-icon :size="20" color="var(--brand-primary)"><ChatDotRound /></el-icon>
            <span>AI 食谱推荐</span>
          </div>
          <div style="display: flex; gap: 10px; align-items: center">
            <el-input v-model="city" placeholder="城市（可选）" style="width: 120px" size="small" clearable />
            <el-button size="small" @click="chatStore.clearMessages()">清空</el-button>
          </div>
        </div>
      </template>

      <div ref="chatBody" class="chat-body">
        <div v-if="chatStore.messages.length === 0" class="chat-empty">
          <div class="empty-icon">
            <el-icon :size="36" color="var(--brand-primary)"><ChatDotRound /></el-icon>
          </div>
          <p class="empty-greeting">你好，{{ authStore.user?.username || '用户' }}</p>
          <p class="empty-hint">告诉我你想吃什么，我来推荐食谱</p>
        </div>
        <ChatMessage v-for="(msg, i) in chatStore.messages" :key="i" :role="msg.role" :content="msg.content" />
        <div v-if="chatStore.loading" class="typing-indicator">
          <div class="typing-avatar">
            <el-icon :size="18"><Cpu /></el-icon>
          </div>
          <div class="typing-bubble">
            <span class="dot"></span>
            <span class="dot"></span>
            <span class="dot"></span>
          </div>
        </div>
      </div>

      <div class="chat-input-area">
        <el-input
          v-model="inputMessage"
          type="textarea"
          :rows="2"
          placeholder="输入消息，按 Enter 发送..."
          @keydown="handleKeydown"
          style="flex: 1"
        />
        <el-button type="primary" :loading="chatStore.loading" @click="sendMessage" class="send-btn">
          发送
        </el-button>
      </div>
    </el-card>
  </div>
</template>

<style scoped>
.chat-layout {
  display: flex;
  gap: 0;
  height: calc(100vh - 150px);
}

/* ---- 侧边栏 ---- */

.chat-sidebar {
  width: 280px;
  background: var(--bg-card);
  border-right: 1px solid var(--border-color);
  display: flex;
  flex-direction: column;
  flex-shrink: 0;
  transition: width 0.3s;
  overflow: hidden;
  border-radius: var(--radius-md) 0 0 var(--radius-md);
}

.chat-sidebar.sidebar-collapsed {
  width: 44px;
}

.sidebar-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 12px;
  border-bottom: 1px solid var(--border-color);
  flex-shrink: 0;
}

.sidebar-title {
  font-size: 14px;
  font-weight: 600;
  color: var(--text-primary);
}

.sidebar-toggle {
  cursor: pointer;
  color: var(--text-secondary);
  font-size: 16px;
  transition: color 0.2s;
}

.sidebar-toggle:hover {
  color: var(--brand-primary);
}

.sidebar-body {
  flex: 1;
  overflow-y: auto;
  padding: 8px;
}

.sidebar-empty {
  text-align: center;
  color: var(--text-placeholder);
  font-size: 13px;
  padding: 40px 12px;
}

.history-item {
  display: flex;
  gap: 8px;
  padding: 8px 10px;
  border-radius: var(--radius-sm);
  margin-bottom: 4px;
  transition: background 0.15s;
}

.history-item:hover {
  background: var(--bg-color);
}

.history-icon {
  width: 26px;
  height: 26px;
  border-radius: 8px;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  margin-top: 2px;
}

.history-user .history-icon {
  background: var(--brand-primary-light);
  color: var(--brand-primary);
}

.history-assistant .history-icon {
  background: #e8f7e8;
  color: #00b42a;
}

.history-content {
  min-width: 0;
  flex: 1;
}

.history-text {
  font-size: 13px;
  color: var(--text-primary);
  line-height: 1.4;
  display: -webkit-box;
  -webkit-line-clamp: 3;
  -webkit-box-orient: vertical;
  overflow: hidden;
  word-break: break-all;
}

.history-assistant .history-text {
  color: var(--text-secondary);
}

.history-time {
  font-size: 11px;
  color: var(--text-placeholder);
  margin-top: 4px;
}

/* ---- 主聊天区 ---- */

.chat-main {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-width: 0;
  border-radius: 0 var(--radius-md) var(--radius-md) 0;
}

.chat-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.chat-title {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 16px;
  font-weight: 600;
}

.chat-body {
  flex: 1;
  overflow-y: auto;
  padding: 16px;
  background: var(--bg-color);
  border-radius: var(--radius-sm);
}

.chat-empty {
  text-align: center;
  padding-top: 80px;
}

.empty-greeting {
  margin-top: 16px;
  font-size: 22px;
  font-weight: 700;
  color: var(--text-primary);
}

.empty-hint {
  margin-top: 8px;
  color: var(--text-secondary);
  font-size: 15px;
}

.empty-icon {
  width: 64px;
  height: 64px;
  border-radius: 50%;
  background: var(--brand-primary-light);
  display: flex;
  align-items: center;
  justify-content: center;
  margin: 0 auto;
}

.typing-indicator {
  display: flex;
  gap: 10px;
  margin-bottom: 14px;
}

.typing-avatar {
  width: 32px;
  height: 32px;
  border-radius: 10px;
  background: #e8f7e8;
  color: #00b42a;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.typing-bubble {
  padding: 12px 16px;
  background: var(--bg-card);
  border-radius: 12px;
  border: 1px solid var(--border-color);
  display: flex;
  gap: 4px;
  align-items: center;
}

.dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: var(--text-placeholder);
  animation: bounce 1.4s infinite ease-in-out both;
}

.dot:nth-child(1) { animation-delay: -0.32s; }
.dot:nth-child(2) { animation-delay: -0.16s; }

@keyframes bounce {
  0%, 80%, 100% { transform: scale(0); }
  40% { transform: scale(1); }
}

.chat-input-area {
  margin-top: 16px;
  display: flex;
  gap: 12px;
  align-items: flex-end;
}

.send-btn {
  height: 56px;
  border-radius: var(--radius-sm);
}
</style>
