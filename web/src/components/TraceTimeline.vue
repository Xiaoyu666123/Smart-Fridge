<script setup lang="ts">
/**
 * 工具链时间线视图（从上往下顺序阅读，最直观）。
 *
 * 每一步：
 *  - 左侧序号圆点 + 竖线连接（清晰的先后顺序）
 *  - 工具图标 + 中文名 + 分类标签 + 状态
 *  - 一句"人话说明"讲清这步干啥
 *  - 耗时条形（相对最慢一步按比例，一眼看出瓶颈）
 *  - 关键输出字段做成 chip；完整 JSON 折叠（点"详情"展开）
 */
import { ref, computed } from 'vue'
import type { TraceStep } from '@/api/admin/trace'
import {
  toolNameLabels, toolIcons, toolDescriptions, getToolCategory,
} from '@/utils/toolConfig'

const props = defineProps<{ steps: TraceStep[] }>()

const expanded = ref<Set<number>>(new Set())

function toggle(id: number) {
  const s = new Set(expanded.value)
  if (s.has(id)) s.delete(id)
  else s.add(id)
  expanded.value = s
}

const maxDuration = computed(() => {
  let m = 1
  props.steps.forEach(s => { if ((s.duration_ms || 0) > m) m = s.duration_ms || 0 })
  return m
})

const totalDuration = computed(() =>
  props.steps.reduce((sum, s) => sum + (s.duration_ms || 0), 0)
)

function durationPct(ms: number | null): number {
  if (!ms) return 2
  return Math.max(2, Math.round((ms / maxDuration.value) * 100))
}

function isSlowest(step: TraceStep): boolean {
  return (step.duration_ms || 0) === maxDuration.value && maxDuration.value > 1
}

function fmt(ms: number | null): string {
  if (ms === null || ms === undefined) return '-'
  if (ms < 1000) return `${ms}ms`
  return `${(ms / 1000).toFixed(1)}s`
}

function info(step: TraceStep) {
  const cat = getToolCategory(step.tool_name)
  return {
    label: toolNameLabels[step.tool_name] || step.tool_name,
    icon: toolIcons[step.tool_name] || 'Cpu',
    desc: toolDescriptions[step.tool_name] || '',
    catLabel: cat.label,
    color: cat.color,
  }
}

function statusMeta(status: string) {
  if (status === 'SUCCESS') return { text: '成功', bg: '#e8f7e8', fg: '#00b42a' }
  if (status === 'FAILED') return { text: '失败', bg: '#ffece8', fg: '#f53f3f' }
  return { text: status || '跳过', bg: '#f2f3f5', fg: '#86909c' }
}

/**
 * 从 tool_output 里挑几个"有意义的标量字段"做成 chip。
 * 跳过 null / 空 / 对象 / 数组，最多 4 个。
 */
function outputChips(step: TraceStep): { k: string; v: string }[] {
  const out = step.tool_output
  if (!out || typeof out !== 'object') return []
  const chips: { k: string; v: string }[] = []
  for (const [k, v] of Object.entries(out)) {
    if (v === null || v === undefined || v === '') continue
    if (typeof v === 'object') continue
    let val = String(v)
    if (val.length > 40) val = val.slice(0, 40) + '…'
    chips.push({ k: keyLabel(k), v: val })
    if (chips.length >= 4) break
  }
  return chips
}

const keyLabels: Record<string, string> = {
  category: '识别为',
  confidence: '置信度',
  decision: '决策',
  reason: '原因',
  item_count: '库存数',
  preferences_count: '偏好数',
  reply_length: '回复字数',
  shelf_life_days: '保鲜天数',
  similarity: '相似度',
  is_duplicate: '是否重复',
  inventory_id: '库存ID',
  temperature: '温度',
  weather_desc: '天气',
  saved: '已保存',
  triggered: '是否触发',
  matched_category: '匹配到',
}
function keyLabel(k: string): string {
  return keyLabels[k] || k
}

function hasDetail(step: TraceStep): boolean {
  return !!(step.tool_input || step.tool_output)
}
</script>

<template>
  <div class="tl-wrap">
    <!-- 顶部摘要条 -->
    <div class="tl-summary">
      <div class="tl-sum-item">
        <span class="tl-sum-num">{{ steps.length }}</span>
        <span class="tl-sum-label">个步骤</span>
      </div>
      <div class="tl-sum-divider"></div>
      <div class="tl-sum-item">
        <span class="tl-sum-num">{{ fmt(totalDuration) }}</span>
        <span class="tl-sum-label">总耗时</span>
      </div>
      <div class="tl-sum-divider"></div>
      <div class="tl-sum-item">
        <span class="tl-sum-num" :class="{ 'has-fail': steps.some(s => s.status === 'FAILED') }">
          {{ steps.filter(s => s.status === 'SUCCESS').length }}/{{ steps.length }}
        </span>
        <span class="tl-sum-label">成功步骤</span>
      </div>
      <div class="tl-legend">
        <span class="lg ai">AI 推理</span>
        <span class="lg db">数据库</span>
        <span class="lg vector">向量计算</span>
        <span class="lg api">外部 API</span>
      </div>
    </div>

    <!-- 时间线 -->
    <div class="tl-list">
      <div
        v-for="(step, idx) in steps"
        :key="step.id"
        class="tl-row"
        :class="{ 'is-failed': step.status === 'FAILED' }"
      >
        <!-- 左侧序号 + 竖线 -->
        <div class="tl-rail">
          <div class="tl-dot" :style="{ background: info(step).color }">{{ idx + 1 }}</div>
          <div v-if="idx < steps.length - 1" class="tl-line"></div>
        </div>

        <!-- 右侧卡片 -->
        <div class="tl-card" :style="{ '--accent': info(step).color } as any">
          <div class="tl-card-head">
            <div class="tl-icon" :style="{ background: info(step).color + '18', color: info(step).color }">
              <el-icon :size="18"><component :is="info(step).icon" /></el-icon>
            </div>
            <div class="tl-titles">
              <div class="tl-name-row">
                <span class="tl-name">{{ info(step).label }}</span>
                <span class="tl-cat" :style="{ background: info(step).color + '18', color: info(step).color }">
                  {{ info(step).catLabel }}
                </span>
                <span class="tl-status" :style="{ background: statusMeta(step.status).bg, color: statusMeta(step.status).fg }">
                  {{ statusMeta(step.status).text }}
                </span>
              </div>
              <div class="tl-desc">{{ info(step).desc }}</div>
            </div>
            <div class="tl-dur" :class="{ slowest: isSlowest(step) }">
              {{ fmt(step.duration_ms) }}
              <span v-if="isSlowest(step)" class="slow-tag">最慢</span>
            </div>
          </div>

          <!-- 耗时条 -->
          <div class="tl-bar-track">
            <div
              class="tl-bar-fill"
              :class="{ slowest: isSlowest(step) }"
              :style="{ width: durationPct(step.duration_ms) + '%', background: isSlowest(step) ? '#ff7d00' : info(step).color }"
            ></div>
          </div>

          <!-- 输出关键字段 chips -->
          <div v-if="outputChips(step).length" class="tl-chips">
            <span v-for="(c, i) in outputChips(step)" :key="i" class="tl-chip">
              <span class="tl-chip-k">{{ c.k }}</span>
              <span class="tl-chip-v">{{ c.v }}</span>
            </span>
          </div>

          <!-- 详情折叠 -->
          <div v-if="hasDetail(step)" class="tl-detail-toggle" @click="toggle(step.id)">
            <el-icon :size="13"><component :is="expanded.has(step.id) ? 'ArrowUp' : 'ArrowDown'" /></el-icon>
            {{ expanded.has(step.id) ? '收起原始数据' : '查看原始输入/输出' }}
          </div>
          <transition name="tl-expand">
            <div v-if="expanded.has(step.id)" class="tl-detail">
              <div class="tl-detail-block">
                <div class="tl-detail-label">输入</div>
                <pre v-if="step.tool_input" class="tl-json">{{ JSON.stringify(step.tool_input, null, 2) }}</pre>
                <span v-else class="tl-json-empty">无</span>
              </div>
              <div class="tl-detail-block">
                <div class="tl-detail-label">输出</div>
                <pre v-if="step.tool_output" class="tl-json">{{ JSON.stringify(step.tool_output, null, 2) }}</pre>
                <span v-else class="tl-json-empty">无</span>
              </div>
            </div>
          </transition>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.tl-wrap {
  height: 100%;
  overflow-y: auto;
  padding: 4px 4px 20px;
}

/* 摘要条 */
.tl-summary {
  display: flex;
  align-items: center;
  gap: 18px;
  padding: 14px 20px;
  background: var(--bg-soft);
  border-radius: 12px;
  margin-bottom: 18px;
  flex-wrap: wrap;
}

.tl-sum-item {
  display: flex;
  flex-direction: column;
  align-items: center;
}

.tl-sum-num {
  font-size: 20px;
  font-weight: 800;
  color: var(--text-primary);
  font-variant-numeric: tabular-nums;
  line-height: 1.1;
}

.tl-sum-num.has-fail {
  color: #f53f3f;
}

.tl-sum-label {
  font-size: 11px;
  color: var(--text-secondary);
  margin-top: 2px;
}

.tl-sum-divider {
  width: 1px;
  height: 28px;
  background: var(--border-color);
}

.tl-legend {
  margin-left: auto;
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}

.lg {
  font-size: 11px;
  font-weight: 600;
  padding: 2px 10px;
  border-radius: 999px;
  display: inline-flex;
  align-items: center;
  gap: 4px;
}

.lg::before {
  content: '';
  width: 7px;
  height: 7px;
  border-radius: 50%;
  background: currentColor;
}

.lg.ai { background: rgba(114,46,209,0.10); color: #722ed1; }
.lg.db { background: rgba(14,165,233,0.12); color: #0ea5e9; }
.lg.vector { background: rgba(15,198,194,0.12); color: #0fc6c2; }
.lg.api { background: rgba(255,125,0,0.12); color: #ff7d00; }

/* 时间线 */
.tl-list {
  display: flex;
  flex-direction: column;
}

.tl-row {
  display: flex;
  gap: 16px;
}

.tl-rail {
  display: flex;
  flex-direction: column;
  align-items: center;
  flex-shrink: 0;
  width: 32px;
}

.tl-dot {
  width: 32px;
  height: 32px;
  border-radius: 50%;
  color: #fff;
  font-size: 14px;
  font-weight: 700;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  box-shadow: 0 2px 6px rgba(0,0,0,0.12);
  z-index: 1;
}

.tl-line {
  flex: 1;
  width: 2px;
  background: var(--border-color);
  margin: 2px 0;
  min-height: 18px;
}

.tl-card {
  flex: 1;
  min-width: 0;
  margin-bottom: 16px;
  padding: 14px 16px;
  background: var(--bg-card);
  border: 1px solid var(--border-color);
  border-left: 3px solid var(--accent);
  border-radius: 12px;
  box-shadow: var(--shadow-sm);
  transition: box-shadow 0.18s;
}

.tl-card:hover {
  box-shadow: var(--shadow-md);
}

.tl-row.is-failed .tl-card {
  border-color: rgba(245,63,63,0.35);
  border-left-color: #f53f3f;
}

.tl-card-head {
  display: flex;
  align-items: flex-start;
  gap: 12px;
}

.tl-icon {
  width: 36px;
  height: 36px;
  border-radius: 10px;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.tl-titles {
  flex: 1;
  min-width: 0;
}

.tl-name-row {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}

.tl-name {
  font-size: 15px;
  font-weight: 700;
  color: var(--text-primary);
}

.tl-cat, .tl-status {
  font-size: 10px;
  font-weight: 700;
  padding: 1px 8px;
  border-radius: 999px;
}

.tl-desc {
  font-size: 12.5px;
  color: var(--text-secondary);
  line-height: 1.5;
  margin-top: 4px;
}

.tl-dur {
  font-size: 13px;
  font-weight: 700;
  color: var(--text-secondary);
  font-variant-numeric: tabular-nums;
  flex-shrink: 0;
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  gap: 2px;
}

.tl-dur.slowest {
  color: #ff7d00;
}

.slow-tag {
  font-size: 9px;
  font-weight: 700;
  padding: 1px 6px;
  border-radius: 6px;
  background: rgba(255,125,0,0.14);
  color: #ff7d00;
}

/* 耗时条 */
.tl-bar-track {
  height: 5px;
  border-radius: 3px;
  background: var(--bg-soft);
  margin-top: 12px;
  overflow: hidden;
}

.tl-bar-fill {
  height: 100%;
  border-radius: 3px;
  transition: width 0.5s ease;
}

/* chips */
.tl-chips {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin-top: 12px;
}

.tl-chip {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 3px 10px;
  border-radius: 8px;
  background: var(--bg-soft);
  font-size: 12px;
}

.tl-chip-k {
  color: var(--text-secondary);
}

.tl-chip-v {
  color: var(--text-primary);
  font-weight: 600;
  font-variant-numeric: tabular-nums;
}

/* 详情折叠 */
.tl-detail-toggle {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  margin-top: 12px;
  font-size: 12px;
  color: var(--brand-primary-dark);
  cursor: pointer;
  user-select: none;
}

.tl-detail-toggle:hover {
  text-decoration: underline;
}

.tl-detail {
  margin-top: 10px;
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 10px;
}

.tl-detail-block {
  min-width: 0;
}

.tl-detail-label {
  font-size: 11px;
  font-weight: 600;
  color: var(--text-secondary);
  margin-bottom: 4px;
}

.tl-json {
  margin: 0;
  padding: 10px 12px;
  border-radius: 8px;
  background: var(--bg-soft);
  font-size: 11.5px;
  line-height: 1.55;
  max-height: 220px;
  overflow: auto;
  white-space: pre-wrap;
  word-break: break-all;
  color: var(--text-primary);
}

.tl-json-empty {
  font-size: 12px;
  color: var(--text-placeholder);
}

.tl-expand-enter-active,
.tl-expand-leave-active {
  transition: all 0.25s ease;
}

.tl-expand-enter-from,
.tl-expand-leave-to {
  opacity: 0;
  transform: translateY(-6px);
}

@media (max-width: 900px) {
  .tl-detail { grid-template-columns: 1fr; }
}
</style>
