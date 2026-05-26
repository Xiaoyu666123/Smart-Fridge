<script setup lang="ts">
defineProps<{
  role: 'user' | 'assistant'
  content: string
}>()
</script>

<template>
  <div :class="['message', role]">
    <div class="avatar">
      <el-icon v-if="role === 'user'" :size="18"><User /></el-icon>
      <el-icon v-else :size="18"><Cpu /></el-icon>
    </div>
    <div class="bubble">
      <div class="content">{{ content }}</div>
    </div>
  </div>
</template>

<style scoped>
.message {
  display: flex;
  gap: 10px;
  margin-bottom: 14px;
}

.message.user {
  flex-direction: row-reverse;
}

.avatar {
  width: 32px;
  height: 32px;
  border-radius: 10px;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.message.user .avatar {
  background: var(--brand-primary);
  color: white;
}

.message.assistant .avatar {
  background: #e8f7e8;
  color: #00b42a;
}

.bubble {
  max-width: 70%;
  padding: 10px 14px;
  border-radius: 12px;
  line-height: 1.6;
  white-space: pre-wrap;
  font-size: 14px;
}

.message.user .bubble {
  background: var(--brand-primary);
  color: white;
  border-top-right-radius: 4px;
}

.message.assistant .bubble {
  background: var(--bg-card);
  color: var(--text-primary);
  border: 1px solid var(--border-color);
  border-top-left-radius: 4px;
}
</style>
