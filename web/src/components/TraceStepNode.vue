<script setup lang="ts">
import { computed } from 'vue'
import { Handle, Position } from '@vue-flow/core'
import type { TraceNodeData } from '@/utils/traceLayout'

const props = defineProps<{ data: TraceNodeData }>()

const statusTagType = computed(() => {
  if (props.data.step.status === 'SUCCESS') return 'success'
  if (props.data.step.status === 'FAILED') return 'danger'
  return 'info'
})

function formatDuration(ms: number | null): string {
  if (ms === null || ms === undefined) return '-'
  if (ms < 1000) return `${ms}ms`
  return `${(ms / 1000).toFixed(1)}s`
}
</script>

<template>
  <Handle type="target" :position="Position.Top" />
  <div class="trace-step-node" :style="{ borderLeftColor: data.borderColor }">
    <div class="node-header">
      <div class="node-left">
        <div class="step-icon" :style="{ background: data.bgColor, color: data.borderColor }">
          <el-icon :size="16"><component :is="data.icon" /></el-icon>
        </div>
        <span class="step-order">Step {{ data.step.step_order }}</span>
        <span class="step-name">{{ data.label }}</span>
      </div>
      <div class="node-right">
        <el-tag :type="statusTagType" size="small" round>{{ data.step.status }}</el-tag>
        <span class="step-duration">{{ formatDuration(data.step.duration_ms) }}</span>
      </div>
    </div>
  </div>
  <Handle type="source" :position="Position.Bottom" />
</template>

<style scoped>
.trace-step-node {
  min-width: 280px;
  padding: 14px 18px;
  border-radius: 12px;
  background: var(--bg-card);
  border: 1px solid var(--border-color);
  border-left: 4px solid #00b42a;
  box-shadow: 0 1px 2px rgba(0, 0, 0, 0.04);
  cursor: grab;
  transition: box-shadow 0.2s;
}

.trace-step-node:hover {
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.1);
}

.node-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.node-left {
  display: flex;
  align-items: center;
  gap: 8px;
}

.node-right {
  display: flex;
  align-items: center;
  gap: 8px;
}

.step-icon {
  width: 28px;
  height: 28px;
  border-radius: 8px;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.step-order {
  font-size: 11px;
  font-weight: 600;
  color: var(--brand-primary);
  background: var(--brand-primary-light);
  padding: 2px 8px;
  border-radius: 4px;
}

.step-name {
  font-weight: 600;
  font-size: 14px;
  color: var(--text-primary);
}

.step-duration {
  font-size: 13px;
  color: var(--text-secondary);
  font-variant-numeric: tabular-nums;
}
</style>
