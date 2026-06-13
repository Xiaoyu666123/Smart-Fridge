<script setup lang="ts">
import { ref, nextTick, onMounted, computed } from 'vue'
import { ElMessage } from 'element-plus'
import { useChatStore, type Message, type RecipeCardData } from '@/stores/chat'
import { useUserAuthStore } from '@/stores/userAuth'
import {
  getConversations, streamChat, saveRecipe, listSavedRecipes,
  queryInventory,
  type ConversationItem,
} from '@/api/user/agent'
import ChatMessage from '@/components/ChatMessage.vue'
import RecipeCard from '@/components/RecipeCard.vue'

const chatStore = useChatStore()
const authStore = useUserAuthStore()
const inputMessage = ref('')
const chatBody = ref<HTMLElement>()
const city = ref('')
const sidebarOpen = ref(true)
const historyLoading = ref(false)
const historyItems = ref<ConversationItem[]>([])
const sessionBreaks = ref<ChatSessionBreak[]>([])

// 是否使用结构化卡片模式
const structuredMode = ref(true)

// 对话模式：recipe（食谱推荐）/ inventory（问库存）
const askMode = ref<'recipe' | 'inventory'>('recipe')

// 已收藏食谱名称集合（避免重复保存）
const savedRecipeNames = ref<Set<string>>(new Set())
const savedRecipeIdMap = ref<Map<string, string>>(new Map())

async function loadHistory() {
  historyLoading.value = true
  try {
    historyItems.value = await getConversations()
    pruneSessionBreaks()
  } catch (e) {
    console.error(e)
  } finally {
    historyLoading.value = false
  }
}

interface ChatSessionBreak {
  afterId: number
  createdAt: string
}

// 后端当前返回的是扁平消息流；前端用“新对话”按钮记录分隔点，
// 这样旧消息会先合成一条完整历史，新消息在分隔点之后形成新会话。
interface HistorySession {
  key: string
  title: string
  lastTime: string | null
  messages: ConversationItem[]
}

function sessionStorageKey() {
  return `smart-fridge:chat-session-breaks:${authStore.user?.id || 'guest'}`
}

function loadSessionBreaks() {
  try {
    const raw = localStorage.getItem(sessionStorageKey())
    const parsed = raw ? JSON.parse(raw) : []
    sessionBreaks.value = Array.isArray(parsed)
      ? parsed
          .map((item) => ({
            afterId: Number(item?.afterId),
            createdAt: String(item?.createdAt || new Date().toISOString()),
          }))
          .filter((item) => Number.isFinite(item.afterId) && item.afterId > 0)
          .sort((a, b) => a.afterId - b.afterId)
          .filter((item, index, list) => index === 0 || item.afterId !== list[index - 1].afterId)
      : []
  } catch {
    sessionBreaks.value = []
  }
}

function saveSessionBreaks() {
  localStorage.setItem(sessionStorageKey(), JSON.stringify(sessionBreaks.value))
}

function latestHistoryId() {
  return historyItems.value.reduce((max, item) => Math.max(max, item.id), 0)
}

function pruneSessionBreaks() {
  const latestId = latestHistoryId()
  if (!latestId || sessionBreaks.value.length === 0) return
  const pruned = sessionBreaks.value.filter((item) => item.afterId <= latestId)
  if (pruned.length !== sessionBreaks.value.length) {
    sessionBreaks.value = pruned
    saveSessionBreaks()
  }
}

function addSessionBreak(afterId: number) {
  if (afterId <= 0) return
  const lastBreak = sessionBreaks.value[sessionBreaks.value.length - 1]
  if (lastBreak?.afterId === afterId) return
  sessionBreaks.value = [
    ...sessionBreaks.value.filter((item) => item.afterId < afterId),
    { afterId, createdAt: new Date().toISOString() },
  ]
  saveSessionBreaks()
}

function getSessionTitle(messages: ConversationItem[]) {
  return messages.find((item) => item.role === 'user')?.content || '完整对话历史'
}

function makeSession(messages: ConversationItem[]): HistorySession {
  const first = messages[0]
  const last = messages[messages.length - 1]
  return {
    key: `session-${first.id}-${last.id}`,
    title: getSessionTitle(messages),
    lastTime: last.created_at,
    messages,
  }
}

const historySessions = computed<HistorySession[]>(() => {
  const sessions: HistorySession[] = []
  let curMessages: ConversationItem[] = []
  let breakIndex = 0
  const breaks = sessionBreaks.value
  for (const item of historyItems.value) {
    while (breakIndex < breaks.length && item.id > breaks[breakIndex].afterId) {
      if (curMessages.length > 0) {
        sessions.push(makeSession(curMessages))
        curMessages = []
      }
      breakIndex += 1
    }
    curMessages.push(item)
  }
  if (curMessages.length > 0) {
    sessions.push(makeSession(curMessages))
  }
  return sessions.reverse()
})

const activeSessionKey = ref<string>('')

function addConversationItemToChat(m: ConversationItem) {
  if (m.role === 'user') {
    chatStore.addMessage({ role: 'user', content: m.content })
    return
  }
  const msg: Message = {
    role: 'assistant',
    content: m.content,
    structured: m.content.includes('===RECIPE==='),
    parseBuffer: m.content,
    recipes: [],
  }
  if (msg.structured) {
    parseRecipeBuffer(msg)
  }
  chatStore.addMessage(msg)
}

// 点击左侧某个会话 → 把完整历史加载回主聊天区
function loadHistorySession(session: HistorySession) {
  activeSessionKey.value = session.key
  chatStore.clearMessages()
  for (const m of session.messages) {
    addConversationItemToChat(m)
  }
  scrollToBottom()
}

function startNewChat() {
  addSessionBreak(latestHistoryId())
  activeSessionKey.value = ''
  chatStore.clearMessages()
}

async function loadSavedRecipes() {
  try {
    const list = await listSavedRecipes(100)
    savedRecipeNames.value = new Set(list.map(r => r.name))
    savedRecipeIdMap.value = new Map(list.map(r => [r.name, r.id]))
  } catch {
    // 静默
  }
}

function scrollToBottom() {
  nextTick(() => {
    if (chatBody.value) {
      chatBody.value.scrollTop = chatBody.value.scrollHeight
    }
  })
}

/**
 * 流式解析：每收到一段 piece，追加到 buffer，扫描 ===RECIPE===...===RECIPE=== 完整块。
 * 完整块里的 JSON 解析后入 message.recipes，并从 buffer 里删除（保持 content 干净）。
 */
function parseRecipeBuffer(msg: Message) {
  if (!msg.parseBuffer) return
  let buf = msg.parseBuffer
  const MARKER = '===RECIPE==='
  while (true) {
    const start = buf.indexOf(MARKER)
    if (start < 0) break
    const end = buf.indexOf(MARKER, start + MARKER.length)
    if (end < 0) break  // 后半截还没到
    const inner = buf.slice(start + MARKER.length, end).trim()
    // 尝试解析 JSON
    try {
      const obj = JSON.parse(inner) as RecipeCardData
      if (obj && obj.name) {
        if (!msg.recipes) msg.recipes = []
        msg.recipes.push(obj)
      }
    } catch (e) {
      console.warn('[recipe] JSON parse failed', inner.slice(0, 200))
    }
    // 把这段从 buffer 里干掉
    buf = buf.slice(0, start) + buf.slice(end + MARKER.length)
  }
  msg.parseBuffer = buf
  // content 显示用 buffer（已剔除完整 RECIPE 块），还残留半截 ===RECIPE=== 时也展示中
  msg.content = buf
}

async function sendMessage() {
  const msg = inputMessage.value.trim()
  if (!msg) return

  // 问库存模式：走库存问答接口，不流式
  if (askMode.value === 'inventory') {
    await sendInventoryQuery(msg)
    return
  }

  chatStore.addMessage({ role: 'user', content: msg })
  // 占位 assistant 消息
  const placeholder: Message = {
    role: 'assistant', content: '',
    structured: structuredMode.value,
    parseBuffer: '',
    recipes: [],
  }
  chatStore.addMessage(placeholder)
  inputMessage.value = ''
  chatStore.loading = true
  scrollToBottom()

  const idx = chatStore.messages.length - 1

  streamChat(msg, city.value || undefined, {
    onDelta(piece) {
      const cur = chatStore.messages[idx]
      if (cur.structured) {
        cur.parseBuffer = (cur.parseBuffer || '') + piece
        parseRecipeBuffer(cur)
      } else {
        cur.content += piece
      }
      scrollToBottom()
    },
    onDone(info) {
      const cur = chatStore.messages[idx]
      // 收尾再扫一次 buffer 确保最后一段处理完
      if (cur.structured) parseRecipeBuffer(cur)

      if (info.detected_preferences && info.detected_preferences.length > 0) {
        cur.preferences = info.detected_preferences
        const prefs = info.detected_preferences.map(p => p.value).join('、')
        ElMessage.success(`已记住您的偏好：${prefs}`)
      }
      chatStore.loading = false
      loadHistory()
    },
    onError(msgText) {
      const cur = chatStore.messages[idx]
      if (!cur.content && (!cur.recipes || cur.recipes.length === 0)) {
        cur.content = '抱歉，推荐服务暂时不可用，请稍后再试。'
      }
      chatStore.loading = false
      console.error('[chat stream]', msgText)
    },
  }, { structured: structuredMode.value })
}

// ---- 问库存（自然语言库存查询）----
async function sendInventoryQuery(msg: string) {
  chatStore.addMessage({ role: 'user', content: msg })
  const placeholder: Message = {
    role: 'assistant', content: '',
    kind: 'inventory',
    invMatched: [],
  }
  chatStore.addMessage(placeholder)
  inputMessage.value = ''
  chatStore.loading = true
  scrollToBottom()

  const idx = chatStore.messages.length - 1
  try {
    const res = await queryInventory(msg)
    const cur = chatStore.messages[idx]
    cur.content = res.answer
    cur.invMatched = res.matched || []
  } catch (e: any) {
    chatStore.messages[idx].content = e?.response?.data?.detail || '库存查询暂时不可用，请稍后再试。'
  } finally {
    chatStore.loading = false
    scrollToBottom()
  }
}

async function handleSaveRecipe(recipe: RecipeCardData) {
  try {
    const saved = await saveRecipe(recipe)
    savedRecipeNames.value = new Set([...savedRecipeNames.value, saved.name])
    savedRecipeIdMap.value.set(saved.name, saved.id)
    ElMessage.success(`已收藏「${saved.name}」`)
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail || '收藏失败')
  }
}

function isRecipeSaved(name: string) {
  return savedRecipeNames.value.has(name)
}

function handleKeydown(e: KeyboardEvent) {
  if (e.key === 'Enter' && !e.shiftKey) {
    e.preventDefault()
    sendMessage()
  }
}

// ---- 快捷指令 ----
interface QuickPrompt {
  emoji: string
  label: string
  text: string
  tip: string
}

const quickPrompts: QuickPrompt[] = [
  { emoji: '⏰', label: '清临期', text: '请用我冰箱里最快过期的食材，给我推荐 2 道菜，要简单快手。', tip: '优先消耗 3 天内过期的食材' },
  { emoji: '🌟', label: '今日推荐', text: '看看我冰箱里有什么，根据当前天气和季节，推荐一道适合今天的菜。', tip: '基于库存 / 天气 / 季节' },
  { emoji: '🥗', label: '清淡少油', text: '用我冰箱里的食材，推荐 1 道清淡少油的菜。', tip: '健康轻负担' },
  { emoji: '🍳', label: '15分钟搞定', text: '用我冰箱里的食材，推荐 2 道 15 分钟内就能做好的快手菜。', tip: '懒人友好' },
]

function quickAsk(p: QuickPrompt) {
  inputMessage.value = p.text
  // 直接发出
  sendMessage()
}

// ---- 问库存快捷指令 ----
const invPrompts: { emoji: string; label: string; text: string }[] = [
  { emoji: '⏰', label: '快过期的', text: '我有哪些 3 天内要过期的食材？' },
  { emoji: '🥩', label: '还有肉吗', text: '冰箱里还有哪些肉类或蛋白质？' },
  { emoji: '🥬', label: '蔬菜清单', text: '我现在有哪些蔬菜？' },
  { emoji: '🔢', label: '一共多少', text: '我冰箱里现在一共有多少件食材？都有什么？' },
]

function quickAskInv(p: { text: string }) {
  inputMessage.value = p.text
  sendMessage()
}

onMounted(() => {
  if (!authStore.user) {
    authStore.loadFromStorage()
  }
  loadSessionBreaks()
  loadHistory()
  loadSavedRecipes()
  // 跨页面投递的消息（首页 / 临期页 "问 AI" 按钮）
  if (chatStore.queuedMessage) {
    inputMessage.value = chatStore.queuedMessage
    chatStore.queuedMessage = ''
    nextTick(() => sendMessage())
  }
})
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
        <div class="sidebar-newchat" @click="startNewChat">
          <el-icon :size="15"><Plus /></el-icon>
          <span>新对话</span>
        </div>
        <div v-if="historySessions.length === 0" class="sidebar-empty">
          暂无历史对话
        </div>
        <div
          v-for="session in historySessions"
          :key="session.key"
          :class="['history-turn', { active: activeSessionKey === session.key }]"
          @click="loadHistorySession(session)"
        >
          <div class="history-turn-icon">
            <el-icon :size="14"><ChatLineRound /></el-icon>
          </div>
          <div class="history-turn-content">
            <div class="history-turn-text">{{ session.title }}</div>
            <div class="history-turn-meta">
              <span v-if="session.lastTime">{{ new Date(session.lastTime).toLocaleString('zh-CN', { month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' }) }}</span>
              <span class="history-turn-count">{{ session.messages.length }} 条</span>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- 主聊天区 -->
    <el-card shadow="never" class="chat-main">
      <template #header>
        <div class="chat-header">
          <div class="chat-title">
            <div class="chat-title-icon">
              <el-icon :size="18" color="#fff"><ChatDotRound /></el-icon>
            </div>
            <div>
              <div class="chat-title-text">AI对话</div>
              <div class="chat-title-sub">按库存、口味和时间给你出主意</div>
            </div>
          </div>
          <div style="display: flex; gap: 10px; align-items: center">
            <el-radio-group v-model="askMode" size="small">
              <el-radio-button value="recipe">食谱</el-radio-button>
              <el-radio-button value="inventory">库存</el-radio-button>
            </el-radio-group>
            <el-tooltip v-if="askMode === 'recipe'" content="结构化卡片：以更直观的卡片形式展示推荐食谱，可一键收藏" placement="bottom">
              <el-switch v-model="structuredMode" size="small" active-text="卡片模式" inline-prompt style="margin-right: 4px" />
            </el-tooltip>
            <el-input v-model="city" placeholder="城市（可选）" style="width: 120px" size="small" clearable />
            <el-button size="small" @click="chatStore.clearMessages()">清空</el-button>
          </div>
        </div>
      </template>

      <div ref="chatBody" class="chat-body">
        <div v-if="chatStore.messages.length === 0" class="chat-empty">
          <div class="empty-panel">
            <div class="empty-kicker">
              {{ askMode === 'inventory' ? '冰箱清单' : '做饭灵感' }}
            </div>
            <p class="empty-greeting">
              你好，<span class="greet-name">{{ authStore.user?.username || '用户' }}</span>
            </p>
            <p class="empty-hint">
              {{ askMode === 'inventory'
                ? '想知道还剩什么、哪些快过期，直接问一句就行。'
                : '说说你想吃的口味、人数或时间，我会尽量从冰箱现有食材里搭配。' }}
            </p>
            <div class="empty-note">
              <span class="empty-note-dot"></span>
              <span>{{ askMode === 'inventory' ? '会优先标出临期和库存不足的食材' : '默认优先用临期食材，少买少浪费' }}</span>
            </div>
          </div>

          <div class="quick-prompts">
            <template v-if="askMode === 'recipe'">
              <button
                v-for="p in quickPrompts"
                :key="p.label"
                class="quick-prompt-card"
                type="button"
                @click="quickAsk(p)"
              >
                <span class="quick-prompt-emoji">{{ p.emoji }}</span>
                <span class="quick-prompt-content">
                  <span class="quick-prompt-label">{{ p.label }}</span>
                  <span class="quick-prompt-tip">{{ p.tip }}</span>
                </span>
              </button>
            </template>
            <template v-else>
              <button
                v-for="p in invPrompts"
                :key="p.label"
                class="quick-prompt-card"
                type="button"
                @click="quickAskInv(p)"
              >
                <span class="quick-prompt-emoji">{{ p.emoji }}</span>
                <span class="quick-prompt-content">
                  <span class="quick-prompt-label">{{ p.label }}</span>
                  <span class="quick-prompt-tip">{{ p.text }}</span>
                </span>
              </button>
            </template>
          </div>

          <div class="empty-foot">
            <span class="empty-foot-tip">
              <el-icon :size="13"><InfoFilled /></el-icon>
              提示：按 <kbd>Enter</kbd> 发送 · <kbd>Shift</kbd>+<kbd>Enter</kbd> 换行
            </span>
          </div>
        </div>
        <template v-for="(msg, i) in chatStore.messages" :key="i">
          <!-- 普通消息（user 或 非结构化 assistant，或结构化的"前缀文字"） -->
          <ChatMessage
            v-if="msg.role === 'user' || msg.content"
            :role="msg.role"
            :content="msg.content"
          />
          <!-- 库存问答命中的食材标签 -->
          <div v-if="msg.kind === 'inventory' && msg.invMatched && msg.invMatched.length" class="inv-matched">
            <span class="inv-matched-label">📦 相关食材：</span>
            <span v-for="c in msg.invMatched" :key="c" class="inv-matched-tag">{{ c }}</span>
          </div>
          <!-- 结构化食谱卡片 -->
          <div v-if="msg.recipes && msg.recipes.length" class="recipes-wrap">
            <RecipeCard
              v-for="(rc, j) in msg.recipes"
              :key="j"
              :recipe="rc"
              :saved="isRecipeSaved(rc.name)"
              @save="handleSaveRecipe"
            />
          </div>
        </template>
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
        <div class="quick-prompts-bar">
          <template v-if="askMode === 'recipe'">
            <span
              v-for="p in quickPrompts"
              :key="p.label"
              class="quick-chip"
              @click="quickAsk(p)"
            >
              <span class="quick-chip-emoji">{{ p.emoji }}</span>
              <span>{{ p.label }}</span>
            </span>
          </template>
          <template v-else>
            <span
              v-for="p in invPrompts"
              :key="p.label"
              class="quick-chip"
              @click="quickAskInv(p)"
            >
              <span class="quick-chip-emoji">{{ p.emoji }}</span>
              <span>{{ p.label }}</span>
            </span>
          </template>
        </div>
        <div class="chat-input-row">
          <el-input
            v-model="inputMessage"
            type="textarea"
            :rows="2"
            :placeholder="askMode === 'inventory'
              ? '问问冰箱里有什么，按 Enter 发送…'
              : '输入消息，按 Enter 发送…'"
            @keydown="handleKeydown"
            style="flex: 1"
          />
          <el-button type="primary" :loading="chatStore.loading" @click="sendMessage" class="send-btn">
            发送
          </el-button>
        </div>
      </div>
    </el-card>
  </div>
</template>

<style scoped>
.recipes-wrap {
  display: flex;
  flex-direction: column;
  gap: 4px;
  margin: 4px 0 14px 42px;  /* 对齐 assistant 消息气泡缩进 */
}

.inv-matched {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 6px;
  margin: -6px 0 14px 42px;
}

.inv-matched-label {
  font-size: 12px;
  color: var(--text-secondary);
}

.inv-matched-tag {
  font-size: 12px;
  font-weight: 600;
  padding: 2px 10px;
  border-radius: 999px;
  background: var(--brand-primary-light);
  color: var(--brand-primary-dark);
}

.chat-layout {
  display: flex;
  gap: 0;
  height: calc(100vh - 112px);
  min-height: 560px;
  overflow: hidden;
}

/* ---- 侧边栏 ---- */

.chat-sidebar {
  width: 280px;
  height: 100%;
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
  min-height: 0;
  overflow-y: auto;
  padding: 8px;
}

.sidebar-empty {
  text-align: center;
  color: var(--text-placeholder);
  font-size: 13px;
  padding: 40px 12px;
}

.sidebar-newchat {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  padding: 9px 12px;
  margin-bottom: 10px;
  border-radius: var(--radius-sm);
  border: 1px dashed var(--brand-primary);
  background: var(--brand-primary-soft);
  color: var(--brand-primary-dark);
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.18s;
}

.sidebar-newchat:hover {
  background: var(--brand-primary-light);
  transform: translateY(-1px);
}

.history-turn {
  display: flex;
  gap: 9px;
  padding: 10px 11px;
  border-radius: var(--radius-sm);
  margin-bottom: 5px;
  border: 1px solid transparent;
  cursor: pointer;
  transition: all 0.15s;
}

.history-turn:hover {
  background: var(--bg-color);
  border-color: var(--border-color);
}

.history-turn.active {
  background: var(--brand-primary-light);
  border-color: var(--brand-primary);
}

.history-turn-icon {
  width: 26px;
  height: 26px;
  border-radius: 8px;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  margin-top: 1px;
  background: var(--brand-primary-light);
  color: var(--brand-primary-dark);
}

.history-turn.active .history-turn-icon {
  background: var(--brand-primary);
  color: #fff;
}

.history-turn-content {
  min-width: 0;
  flex: 1;
}

.history-turn-text {
  font-size: 13px;
  font-weight: 500;
  color: var(--text-primary);
  line-height: 1.45;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
  word-break: break-all;
}

.history-turn-meta {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 11px;
  color: var(--text-placeholder);
  margin-top: 4px;
}

.history-turn-count {
  padding: 0 6px;
  border-radius: 6px;
  background: var(--bg-soft);
  color: var(--text-secondary);
}

/* ---- 主聊天区 ---- */

.chat-main {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-width: 0;
  height: 100%;
  overflow: hidden;
  border-radius: 0 var(--radius-md) var(--radius-md) 0;
}

.chat-main :deep(.el-card__header) {
  flex-shrink: 0;
}

.chat-main :deep(.el-card__body) {
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  padding: 16px 18px 18px;
}

.chat-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.chat-title {
  display: flex;
  align-items: center;
  gap: 12px;
}

.chat-title-icon {
  width: 36px;
  height: 36px;
  border-radius: 10px;
  background: linear-gradient(135deg, var(--brand-primary), var(--brand-primary-dark));
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  box-shadow: 0 4px 10px rgba(14, 165, 233, 0.30);
}

.chat-title-text {
  font-size: 16px;
  font-weight: 700;
  color: var(--text-primary);
  line-height: 1.2;
}

.chat-title-sub {
  font-size: 11px;
  color: var(--text-placeholder);
  margin-top: 2px;
}

.chat-body {
  flex: 1 1 auto;
  min-height: 0;
  overflow-y: auto;
  padding: 20px 20px 28px;
  border-radius: var(--radius-sm);
  background: var(--bg-color);
}

.chat-empty {
  min-height: 100%;
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  justify-content: flex-start;
  text-align: left;
  padding: 52px min(7vw, 72px) 34px;
  animation: empty-fade 0.5s ease-out;
}

@keyframes empty-fade {
  from { opacity: 0; transform: translateY(8px); }
  to   { opacity: 1; transform: translateY(0); }
}

.empty-panel {
  width: min(680px, 100%);
  padding-bottom: 24px;
  border-bottom: 1px solid var(--border-color);
}

.empty-kicker {
  display: inline-flex;
  align-items: center;
  height: 26px;
  padding: 0 10px;
  border-radius: 999px;
  background: rgba(14, 165, 233, 0.08);
  color: var(--brand-primary-dark);
  font-size: 12px;
  font-weight: 700;
}

.empty-greeting {
  margin-top: 16px;
  font-size: 28px;
  font-weight: 700;
  color: var(--text-primary);
  line-height: 1.25;
}

.greet-name {
  color: var(--brand-primary-dark);
}

.empty-hint {
  margin-top: 12px;
  color: var(--text-secondary);
  font-size: 15px;
  max-width: 620px;
  line-height: 1.7;
}

.empty-note {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  margin-top: 18px;
  padding: 9px 12px;
  border-radius: 8px;
  background: var(--bg-card);
  border: 1px solid var(--border-color);
  color: var(--text-secondary);
  font-size: 13px;
}

.empty-note-dot {
  width: 7px;
  height: 7px;
  border-radius: 50%;
  background: #22c55e;
  flex-shrink: 0;
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
  flex-shrink: 0;
  margin-top: 12px;
  display: flex;
  flex-direction: column;
  gap: 10px;
  padding: 14px 14px 14px 14px;
  background: var(--bg-card);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-md);
  box-shadow: 0 4px 14px rgba(0, 0, 0, 0.04);
}

.chat-input-row {
  display: flex;
  gap: 12px;
  align-items: flex-end;
}

.chat-input-row :deep(.el-textarea__inner) {
  border-radius: 12px;
  resize: none;
  font-size: 14px;
  line-height: 1.6;
  padding: 12px 14px;
  border: 1px solid var(--border-color);
  background: var(--bg-color);
  transition: all 0.2s;
}

.chat-input-row :deep(.el-textarea__inner:focus) {
  background: var(--bg-card);
  border-color: var(--brand-primary);
  box-shadow: 0 0 0 3px rgba(14, 165, 233, 0.18);
}

.quick-prompts-bar {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  padding: 0 2px;
}

.quick-chip {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 4px 12px;
  border: 1px solid var(--border-color);
  border-radius: 999px;
  background: var(--bg-card);
  color: var(--text-secondary);
  font-size: 12px;
  cursor: pointer;
  transition: all 0.18s;
  user-select: none;
}

.quick-chip:hover {
  border-color: var(--brand-primary);
  color: var(--brand-primary-dark);
  background: var(--brand-primary-soft, var(--brand-primary-light));
  transform: translateY(-1px);
}

.quick-chip-emoji {
  font-size: 13px;
}

.send-btn {
  height: 64px;
  min-width: 80px;
  border-radius: 12px;
  font-weight: 600;
  font-size: 14px;
  background: linear-gradient(135deg, var(--brand-primary), var(--brand-primary-dark)) !important;
  border-color: transparent !important;
  box-shadow: 0 6px 16px rgba(14, 165, 233, 0.35);
  transition: all 0.18s;
}

.send-btn:hover {
  transform: translateY(-1px);
  box-shadow: 0 10px 22px rgba(14, 165, 233, 0.45);
}

.quick-prompts {
  display: grid;
  grid-template-columns: repeat(2, minmax(220px, 1fr));
  gap: 10px;
  margin-top: 22px;
  width: min(680px, 100%);
}

.quick-prompt-card {
  display: flex;
  align-items: center;
  gap: 12px;
  min-height: 64px;
  padding: 12px 14px;
  border: 1px solid var(--border-color);
  border-radius: 8px;
  background: var(--bg-card);
  cursor: pointer;
  transition: border-color 0.18s, background 0.18s, transform 0.18s, box-shadow 0.18s;
  text-align: left;
}

.quick-prompt-card:hover {
  border-color: var(--brand-primary-light);
  background: var(--brand-primary-soft);
  box-shadow: 0 8px 18px rgba(15, 23, 42, 0.06);
  transform: translateY(-1px);
}

.quick-prompt-emoji {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 34px;
  height: 34px;
  border-radius: 8px;
  background: var(--bg-soft);
  font-size: 17px;
  line-height: 1;
  flex-shrink: 0;
}

.quick-prompt-content {
  display: flex;
  flex-direction: column;
  gap: 3px;
  min-width: 0;
}

.quick-prompt-label {
  font-size: 14px;
  font-weight: 700;
  color: var(--text-primary);
}

.quick-prompt-tip {
  font-size: 12px;
  color: var(--text-secondary);
  line-height: 1.4;
}

.empty-foot {
  margin-top: 28px;
  display: flex;
  justify-content: center;
}

.empty-foot-tip {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
  color: var(--text-placeholder);
}

.empty-foot-tip kbd {
  font-family: 'SFMono-Regular', Consolas, monospace;
  background: var(--bg-card);
  border: 1px solid var(--border-color);
  border-bottom-width: 2px;
  border-radius: 4px;
  padding: 0 6px;
  font-size: 11px;
  color: var(--text-secondary);
}

@media (max-width: 900px) {
  .chat-layout {
    height: calc(100vh - 96px);
    min-height: 560px;
    flex-direction: column;
  }

  .chat-sidebar,
  .chat-sidebar.sidebar-collapsed {
    width: 100%;
    border-right: 0;
    border-bottom: 1px solid var(--border-color);
    border-radius: var(--radius-md) var(--radius-md) 0 0;
  }

  .chat-sidebar.sidebar-collapsed {
    height: 48px;
  }

  .chat-sidebar:not(.sidebar-collapsed) {
    height: 220px;
    flex-shrink: 0;
  }

  .chat-main {
    min-height: 0;
    border-radius: 0 0 var(--radius-md) var(--radius-md);
  }

  .chat-header {
    align-items: flex-start;
    gap: 12px;
    flex-direction: column;
  }

  .chat-header > div:last-child {
    width: 100%;
    flex-wrap: wrap;
  }

  .chat-empty {
    padding: 32px 4px 26px;
  }

  .quick-prompts {
    grid-template-columns: 1fr;
  }

  .chat-input-row {
    flex-direction: column;
    align-items: stretch;
  }

  .send-btn {
    width: 100%;
    height: 44px;
  }
}
</style>
