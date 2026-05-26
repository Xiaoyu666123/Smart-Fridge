<script setup lang="ts">
import { ref, watch, onMounted, nextTick } from 'vue'
import { VueFlow, useVueFlow } from '@vue-flow/core'
import { Background } from '@vue-flow/background'
import { Controls } from '@vue-flow/controls'
import '@vue-flow/core/dist/style.css'
import '@vue-flow/core/dist/theme-default.css'
import '@vue-flow/controls/dist/style.css'
import TraceStepNode from './TraceStepNode.vue'
import { buildTraceFlow } from '@/utils/traceLayout'
import { toolNameLabels } from '@/utils/toolConfig'
import type { TraceStep } from '@/api/trace'

const props = defineProps<{ steps: TraceStep[] }>()

const { fitView } = useVueFlow()

const nodes = ref([])
const edges = ref([])

const selectedStep = ref<TraceStep | null>(null)

watch(() => props.steps, (steps) => {
  if (steps.length) {
    const flow = buildTraceFlow(steps)
    nodes.value = flow.nodes
    edges.value = flow.edges
    nextTick(() => {
      setTimeout(() => fitView({ padding: 0.2 }), 200)
    })
  } else {
    nodes.value = []
    edges.value = []
  }
  selectedStep.value = null
}, { immediate: true })

function onNodeClick(event: any) {
  const node = event.node
  if (node?.data?.step) {
    selectedStep.value = node.data.step
  }
}

function getToolLabel(name: string): string {
  return toolNameLabels[name] || name
}
</script>

<template>
  <div class="flow-chart-wrapper">
    <VueFlow
      v-model:nodes="nodes"
      v-model:edges="edges"
      :node-types="{ traceStep: TraceStepNode }"
      :default-viewport="{ zoom: 1, x: 0, y: 0 }"
      :min-zoom="0.3"
      :max-zoom="2"
      fit-view-on-init
      @node-click="onNodeClick"
    >
      <Background :gap="20" :size="1" pattern-color="#e5e6eb" />
      <Controls position="bottom-right" />
    </VueFlow>

    <transition name="slide">
      <div v-if="selectedStep" class="detail-panel">
        <div class="detail-panel-header">
          <span class="detail-panel-title">{{ getToolLabel(selectedStep.tool_name) }}</span>
          <el-icon :size="18" style="cursor: pointer; color: var(--text-secondary)" @click="selectedStep = null"><Close /></el-icon>
        </div>
        <div class="detail-panel-body">
          <div class="detail-section">
            <div class="detail-label">
              <el-icon :size="14"><ArrowRight /></el-icon>
              输入
            </div>
            <pre v-if="selectedStep.tool_input" class="detail-json">{{ JSON.stringify(selectedStep.tool_input, null, 2) }}</pre>
            <span v-else class="detail-empty">无输入数据</span>
          </div>
          <div class="detail-section">
            <div class="detail-label">
              <el-icon :size="14"><ArrowRight /></el-icon>
              输出
            </div>
            <pre v-if="selectedStep.tool_output" class="detail-json">{{ JSON.stringify(selectedStep.tool_output, null, 2) }}</pre>
            <span v-else class="detail-empty">无输出数据</span>
          </div>
        </div>
      </div>
    </transition>
  </div>
</template>

<style scoped>
.flow-chart-wrapper {
  width: 100%;
  height: 100%;
  position: relative;
  overflow: hidden;
}

.detail-panel {
  position: absolute;
  top: 0;
  right: 0;
  width: 340px;
  height: 100%;
  background: var(--bg-card);
  border-left: 1px solid var(--border-color);
  box-shadow: -4px 0 12px rgba(0, 0, 0, 0.06);
  display: flex;
  flex-direction: column;
  z-index: 10;
}

.detail-panel-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 16px 18px;
  border-bottom: 1px solid var(--border-color);
}

.detail-panel-title {
  font-weight: 600;
  font-size: 15px;
  color: var(--text-primary);
}

.detail-panel-body {
  flex: 1;
  overflow-y: auto;
  padding: 16px 18px;
}

.detail-section {
  margin-bottom: 16px;
}

.detail-label {
  display: flex;
  align-items: center;
  gap: 4px;
  font-size: 13px;
  font-weight: 500;
  color: var(--text-secondary);
  margin-bottom: 8px;
}

.detail-json {
  margin: 0;
  padding: 12px 14px;
  border-radius: 8px;
  background: var(--bg-color);
  font-size: 12px;
  line-height: 1.6;
  overflow-x: auto;
  max-height: 260px;
  overflow-y: auto;
  white-space: pre-wrap;
  word-break: break-all;
  color: var(--text-primary);
}

.detail-empty {
  font-size: 12px;
  color: var(--text-placeholder);
}

.slide-enter-active,
.slide-leave-active {
  transition: transform 0.25s ease;
}

.slide-enter-from,
.slide-leave-to {
  transform: translateX(100%);
}
</style>
