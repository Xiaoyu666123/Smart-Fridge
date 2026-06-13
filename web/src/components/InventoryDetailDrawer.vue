<script setup lang="ts">
/**
 * 库存详情右滑抽屉（admin / user 共用）
 *
 * - 接收一个 inventoryItem，展示物品图、保鲜状态、标签信息、事件流水等
 * - 用 v-model:visible 控制显隐
 * - admin 模式下额外允许看完整 metadata；user 模式下隐藏调试字段
 */
import { ref, watch, computed } from 'vue'
import { ElMessage } from 'element-plus'
import { toolNameLabels, toolIcons } from '@/utils/toolConfig'
import { uploadUrl } from '@/config/env'

interface InventoryLike {
  id: string
  device_id: string
  category: string
  status: string
  remain_ratio: number
  bbox: number[] | null
  agent_metadata: Record<string, any> | null
  snapshot_path: string | null
  label_text: string | null
  label_data: Record<string, any> | null
  label_snapshot_path: string | null
  has_label?: boolean
  expire_source?: string | null
  expire_at?: string | null
  brand?: string | null
  created_at: string | null
}

const props = defineProps<{
  visible: boolean
  item: InventoryLike | null
  mode?: 'admin' | 'user'
  // 可选：传入获取事件流水的函数（不同模块用不同 API）
  fetchEvents?: ((inventoryId: string) => Promise<any[]>) | null
}>()

const emit = defineEmits<{ (e: 'update:visible', v: boolean): void }>()

const events = ref<any[]>([])
const eventsLoading = ref(false)

const aiTrace = ref<any | null>(null)
const aiTraceLoading = ref(false)
const aiTraceLoaded = ref(false)
const aiTraceVisible = ref(false)

const drawerOpen = computed({
  get: () => props.visible,
  set: (v: boolean) => emit('update:visible', v),
})

const isAdmin = computed(() => props.mode === 'admin')

const item = computed(() => props.item)

// 图片预览
const previewUrl = ref('')
const previewVisible = ref(false)

function openPreview(path: string | null | undefined) {
  if (!path) return
  previewUrl.value = getSnapshotUrl(path)
  previewVisible.value = true
}

function getSnapshotUrl(path: string | null | undefined): string {
  return uploadUrl(path)
}

function getRemainDays(it: InventoryLike): number {
  const expireAt = it?.agent_metadata?.expire_at || it?.expire_at
  if (!expireAt) return Number.POSITIVE_INFINITY
  return Math.ceil((new Date(expireAt).getTime() - Date.now()) / 86400000)
}

function getRemainTag(it: InventoryLike) {
  const d = getRemainDays(it)
  if (!Number.isFinite(d)) return { text: '未计算', type: 'info' }
  if (d < 0) return { text: `已过期 ${-d} 天`, type: 'danger' }
  if (d === 0) return { text: '今天到期', type: 'danger' }
  if (d <= 3) return { text: `还有 ${d} 天`, type: 'warning' }
  return { text: `还有 ${d} 天`, type: 'success' }
}

function statusLabel(s: string): string {
  return ({
    IN_STOCK: '在库',
    OUT_PENDING: '待确认',
    CONSUMED: '已消耗',
  } as Record<string, string>)[s] || s
}

function formatDate(s: string | null | undefined): string {
  if (!s) return '-'
  return new Date(s).toLocaleString('zh-CN')
}

function copyJson(obj: any) {
  try {
    navigator.clipboard.writeText(JSON.stringify(obj, null, 2))
    ElMessage.success('已复制 JSON')
  } catch {
    ElMessage.warning('复制失败，请手动选择')
  }
}

watch(
  () => [props.visible, props.item?.id] as const,
  async ([vis, id]) => {
    aiTrace.value = null
    aiTraceLoaded.value = false
    aiTraceVisible.value = false
    if (!vis || !id || !props.fetchEvents) {
      events.value = []
      return
    }
    eventsLoading.value = true
    try {
      events.value = await props.fetchEvents(id)
    } catch {
      events.value = []
    } finally {
      eventsLoading.value = false
    }
  },
  { immediate: true }
)

async function loadAITrace() {
  const id = props.item?.id
  if (!id || !isAdmin.value) return
  aiTraceVisible.value = !aiTraceVisible.value
  if (!aiTraceVisible.value) return
  if (aiTraceLoaded.value) return
  aiTraceLoading.value = true
  try {
    const { getInventoryLastTrace } = await import('@/api/admin/perf')
    aiTrace.value = await getInventoryLastTrace(id)
    aiTraceLoaded.value = true
  } catch {
    aiTrace.value = { trace_id: null, steps: [] }
    aiTraceLoaded.value = true
  } finally {
    aiTraceLoading.value = false
  }
}

function getStepLabel(name: string) {
  return toolNameLabels[name] || name
}
function getStepIcon(name: string) {
  return toolIcons[name] || 'Cpu'
}

function explainStep(step: any): string {
  const name = step.tool_name
  const out = step.tool_output || {}
  const inp = step.tool_input || {}
  if (name === 'vector_dedup') {
    if (out.is_duplicate) {
      return `命中重复：${out.reason === 'hash' ? '字节完全相同' : `向量相似度 ${(out.similarity || 0).toFixed(3)}`}`
    }
    return '通过去重检查，未找到相似已有库存'
  }
  if (name === 'vision_assist_decide') {
    const dec = out.decision || ''
    if (dec === 'TRIGGERED') return `置信度 ${out.edge_confidence} 落入触发区间 [${out.lower}, ${out.upper}]，调用云端视觉复核`
    if (dec === 'SKIPPED_BELOW_LOWER') return `置信度 ${out.edge_confidence} 低于下界 ${out.lower}，跳过复核`
    if (dec === 'SKIPPED_ABOVE_UPPER') return `置信度 ${out.edge_confidence} 高于上界 ${out.upper}，端侧已足够可信`
    if (dec === 'SKIPPED_NO_CROP_IMAGE') return '没有裁剪图，跳过云端复核'
    return `决策：${dec}`
  }
  if (name === 'vision_recognize') {
    const c = out.category
    const conf = out.confidence
    if (c) return `云端识别为 ${c}（置信度 ${(conf || 0).toFixed(2)}）`
    return '云端识别失败'
  }
  if (name === 'llm_freshness') {
    const days = out.shelf_life_days
    if (days != null) return `LLM 推算保鲜期 ${days} 天`
    return 'LLM 推算保鲜期失败'
  }
  if (name === 'label_associate') {
    if (out.pending_label_id) {
      return `挂载到标签缓冲（品牌：${out.brand || '未知'}），过期时间来源 ${out.expire_source}`
    }
    return '该设备无待关联标签'
  }
  if (name === 'preference_extract') {
    return `从消息中识别出 ${out.preferences_count || 0} 条偏好`
  }
  if (name === 'embedding_extract') {
    return '提取 1024 维视觉特征向量'
  }
  if (name === 'db_write_inventory') {
    return '已写入数据库'
  }
  if (name === 'db_write_event_log') {
    return '已写入事件流水'
  }
  if (name === 'db_query_inventory') {
    return out.found ? '匹配到一条库存记录' : '没有匹配到库存'
  }
  return JSON.stringify(out).slice(0, 80)
}

// 标签字段格式化展示
const labelFields = computed(() => {
  const d = item.value?.label_data || {}
  const fields = [
    { key: 'brand', label: '品牌' },
    { key: 'product_name', label: '产品名' },
    { key: 'manufacture_date', label: '生产日期' },
    { key: 'expire_date', label: '保质期截止' },
    { key: 'shelf_life_days', label: '保质期(天)' },
    { key: 'net_weight', label: '净含量' },
    { key: 'storage', label: '储存条件' },
  ]
  return fields
    .map(f => ({ ...f, value: d[f.key] }))
    .filter(f => f.value !== '' && f.value !== null && f.value !== undefined && f.value !== 0)
})
</script>

<template>
  <el-drawer
    v-model="drawerOpen"
    direction="rtl"
    :size="480"
    :with-header="false"
    :show-close="false"
  >
    <div v-if="item" class="drawer-body">
      <!-- 头部 -->
      <div class="dh-header">
        <div class="dh-left">
          <div class="dh-name">
            {{ item.category }}
            <el-tag v-if="item.has_label" size="small" round
              style="background: var(--brand-primary-light); color: var(--brand-primary-dark); border: none">
              📦 带标签
            </el-tag>
          </div>
          <div class="dh-sub">{{ item.device_id }} · {{ statusLabel(item.status) }}</div>
        </div>
        <el-icon class="dh-close" :size="20" @click="drawerOpen = false"><Close /></el-icon>
      </div>

      <!-- 物品图 -->
      <div v-if="item.snapshot_path" class="image-block">
        <img :src="getSnapshotUrl(item.snapshot_path)" class="hero-img" @click="openPreview(item.snapshot_path)" />
      </div>

      <!-- 关键状态 -->
      <div class="kv-grid">
        <div class="kv">
          <div class="kv-label">保鲜状态</div>
          <div class="kv-value">
            <el-tag :type="getRemainTag(item).type as any" round size="small">
              {{ getRemainTag(item).text }}
            </el-tag>
          </div>
        </div>
        <div class="kv">
          <div class="kv-label">过期来源</div>
          <div class="kv-value">
            <span v-if="item.agent_metadata?.expire_source === 'label'">📦 包装标签</span>
            <span v-else-if="item.agent_metadata?.expire_source === 'manual'">✍️ 手动填写</span>
            <span v-else>🤖 AI 估算</span>
          </div>
        </div>
        <div class="kv">
          <div class="kv-label">剩余比例</div>
          <div class="kv-value" style="display: flex; align-items: center; gap: 8px">
            <el-progress :percentage="Math.round(item.remain_ratio * 100)" :stroke-width="5" :show-text="false" style="flex:1" />
            <span style="font-size: 12px; color: var(--text-secondary)">{{ Math.round(item.remain_ratio * 100) }}%</span>
          </div>
        </div>
        <div class="kv">
          <div class="kv-label">入库时间</div>
          <div class="kv-value">{{ formatDate(item.created_at) }}</div>
        </div>
        <div class="kv">
          <div class="kv-label">过期时间</div>
          <div class="kv-value">{{ formatDate(item.agent_metadata?.expire_at || item.expire_at) }}</div>
        </div>
        <div class="kv">
          <div class="kv-label">bbox</div>
          <div class="kv-value">
            <code v-if="item.bbox" class="mono">[{{ item.bbox.join(', ') }}]</code>
            <span v-else style="color: var(--text-placeholder)">无</span>
          </div>
        </div>
      </div>

      <!-- 标签卡片 -->
      <div v-if="item.has_label || item.label_data" class="section">
        <div class="section-title">📦 商品标签</div>
        <div class="label-card">
          <div v-if="item.label_snapshot_path" class="label-snapshot">
            <img :src="getSnapshotUrl(item.label_snapshot_path)" @click="openPreview(item.label_snapshot_path)" />
          </div>
          <div v-if="labelFields.length" class="label-fields">
            <div v-for="f in labelFields" :key="f.key" class="lf-row">
              <span class="lf-key">{{ f.label }}</span>
              <span class="lf-val">{{ f.value }}</span>
            </div>
          </div>
          <div v-if="item.label_data?.ingredients" class="label-ingredients">
            <div class="lf-key" style="margin-bottom: 4px">配料</div>
            <div class="ingredients-text">{{ item.label_data.ingredients }}</div>
          </div>
          <details v-if="item.label_text" class="raw-text">
            <summary>查看 OCR 原始文字</summary>
            <pre>{{ item.label_text }}</pre>
          </details>
        </div>
      </div>

      <!-- 存储建议 -->
      <div v-if="item.agent_metadata?.storage_advice" class="section">
        <div class="section-title">💡 存储建议</div>
        <div class="advice">{{ item.agent_metadata.storage_advice }}</div>
      </div>

      <!-- AI 决策路径（仅 admin） -->
      <div v-if="isAdmin" class="section">
        <div class="section-title ai-title">
          🧠 AI 是怎么决定的
          <el-button text size="small" @click="loadAITrace">
            {{ aiTraceVisible ? '收起' : '展开' }}
          </el-button>
        </div>
        <div v-if="aiTraceVisible" v-loading="aiTraceLoading" class="ai-trace">
          <div v-if="aiTraceLoaded && (!aiTrace || !aiTrace.trace_id)" class="ai-empty">
            未找到关联 trace（可能是手动入库或时间窗口外）
          </div>
          <div v-else-if="aiTrace?.steps?.length" class="ai-steps">
            <div v-for="(step, i) in aiTrace.steps" :key="step.id" class="ai-step">
              <div class="ai-step-marker" :class="step.status === 'FAILED' ? 'fail' : 'ok'">
                <el-icon :size="12"><component :is="getStepIcon(step.tool_name)" /></el-icon>
              </div>
              <div class="ai-step-body">
                <div class="ai-step-head">
                  <span class="ai-step-no">#{{ i + 1 }}</span>
                  <span class="ai-step-name">{{ getStepLabel(step.tool_name) }}</span>
                  <span v-if="step.duration_ms !== null" class="ai-step-dur">{{ step.duration_ms }}ms</span>
                </div>
                <div class="ai-step-text">{{ explainStep(step) }}</div>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- 事件流水 -->
      <div v-if="events.length > 0 || eventsLoading" class="section">
        <div class="section-title">🕓 事件流水</div>
        <div v-loading="eventsLoading" class="events">
          <div v-for="ev in events" :key="ev.id" class="event-row">
            <el-tag size="small" round
              :type="ev.event_type === 'ITEM_IN' ? 'success' : ev.event_type === 'ITEM_OUT' ? 'warning' : 'info'">
              {{ ev.event_type }}
            </el-tag>
            <span class="ev-time">{{ formatDate(ev.create_at) }}</span>
            <span v-if="ev.confidence" class="ev-conf">{{ (ev.confidence * 100).toFixed(0) }}%</span>
          </div>
        </div>
      </div>

      <!-- 调试 raw（仅 admin） -->
      <div v-if="isAdmin" class="section">
        <div class="section-title raw-title">
          🛠 调试 Raw Metadata
          <el-button text size="small" @click="copyJson(item)">复制全量</el-button>
        </div>
        <details>
          <summary>agent_metadata</summary>
          <pre class="raw-json">{{ JSON.stringify(item.agent_metadata || {}, null, 2) }}</pre>
        </details>
        <details v-if="item.label_data">
          <summary>label_data</summary>
          <pre class="raw-json">{{ JSON.stringify(item.label_data, null, 2) }}</pre>
        </details>
      </div>
    </div>

    <!-- 图片预览 -->
    <el-dialog v-model="previewVisible" width="auto" :show-close="true" append-to-body>
      <img :src="previewUrl" style="max-width: 80vw; max-height: 80vh; display: block; margin: 0 auto; border-radius: 8px" />
    </el-dialog>
  </el-drawer>
</template>

<style scoped>
.drawer-body {
  padding: 18px 20px 32px;
}

.dh-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 12px;
  margin-bottom: 16px;
}

.dh-name {
  font-size: 20px;
  font-weight: 700;
  color: var(--text-primary);
  display: flex;
  align-items: center;
  gap: 8px;
}

.dh-sub {
  font-size: 12px;
  color: var(--text-secondary);
  margin-top: 4px;
}

.dh-close {
  cursor: pointer;
  color: var(--text-placeholder);
  transition: color 0.2s;
}

.dh-close:hover {
  color: var(--text-primary);
}

.image-block {
  margin-bottom: 16px;
}

.hero-img {
  width: 100%;
  max-height: 220px;
  object-fit: cover;
  border-radius: 12px;
  cursor: zoom-in;
  background: var(--bg-soft);
}

.kv-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 8px 20px;
  padding: 14px 16px;
  background: var(--bg-soft);
  border-radius: 12px;
  margin-bottom: 16px;
}

.kv-grid .kv:last-child {
  grid-column: 1 / span 2;
}

.kv-label {
  font-size: 11px;
  color: var(--text-placeholder);
  margin-bottom: 4px;
}

.kv-value {
  font-size: 13px;
  color: var(--text-primary);
}

.section {
  margin-bottom: 18px;
}

.section-title {
  font-size: 13px;
  font-weight: 600;
  color: var(--text-secondary);
  margin-bottom: 10px;
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.label-card {
  background: var(--brand-primary-soft);
  border: 1px solid var(--brand-primary-light);
  border-radius: 12px;
  padding: 14px;
}

.label-snapshot {
  margin-bottom: 12px;
}

.label-snapshot img {
  width: 100%;
  max-height: 160px;
  object-fit: cover;
  border-radius: 8px;
  cursor: zoom-in;
}

.lf-row {
  display: flex;
  justify-content: space-between;
  font-size: 13px;
  padding: 4px 0;
  border-bottom: 1px dashed var(--brand-primary-light);
}

.lf-row:last-child {
  border-bottom: none;
}

.lf-key {
  color: var(--text-secondary);
  font-size: 12px;
}

.lf-val {
  color: var(--brand-primary-dark);
  font-weight: 500;
}

.label-ingredients {
  margin-top: 10px;
  padding-top: 10px;
  border-top: 1px solid var(--brand-primary-light);
}

.ingredients-text {
  font-size: 12px;
  color: var(--text-primary);
  line-height: 1.5;
}

.raw-text {
  margin-top: 10px;
}

.raw-text summary {
  font-size: 12px;
  color: var(--text-secondary);
  cursor: pointer;
  user-select: none;
}

.raw-text pre {
  margin-top: 6px;
  font-size: 11px;
  color: var(--text-secondary);
  background: #fff;
  padding: 8px 10px;
  border-radius: 6px;
  white-space: pre-wrap;
  word-break: break-all;
  max-height: 180px;
  overflow-y: auto;
}

.advice {
  padding: 10px 12px;
  background: var(--bg-soft);
  border-radius: 8px;
  font-size: 13px;
  color: var(--text-primary);
  line-height: 1.5;
}

.events {
  display: flex;
  flex-direction: column;
  gap: 6px;
}.event-row {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 10px;
  background: var(--bg-soft);
  border-radius: 8px;
  font-size: 12px;
}

.ev-time {
  color: var(--text-secondary);
}

.ev-conf {
  margin-left: auto;
  color: var(--brand-primary-dark);
  font-weight: 600;
}

.raw-title {
  color: var(--text-placeholder);
}

details summary {
  font-size: 12px;
  color: var(--text-secondary);
  cursor: pointer;
  user-select: none;
  padding: 4px 0;
}

.raw-json {
  margin-top: 6px;
  padding: 10px 12px;
  background: var(--bg-soft);
  border-radius: 8px;
  font-family: 'SFMono-Regular', Consolas, monospace;
  font-size: 11px;
  line-height: 1.4;
  color: var(--text-primary);
  white-space: pre-wrap;
  word-break: break-all;
  max-height: 220px;
  overflow-y: auto;
}

.mono {
  font-family: 'SFMono-Regular', Consolas, monospace;
  font-size: 12px;
  background: var(--bg-soft);
  padding: 1px 6px;
  border-radius: 4px;
}

/* AI 决策路径 */
.ai-title {
  color: var(--brand-primary-dark);
}

.ai-trace {
  background: var(--bg-soft);
  border: 1px solid var(--border-light);
  border-radius: 12px;
  padding: 12px 14px;
}

.ai-empty {
  font-size: 12px;
  color: var(--text-placeholder);
  text-align: center;
  padding: 8px 0;
}

.ai-steps {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.ai-step {
  display: flex;
  gap: 10px;
  position: relative;
}

.ai-step:not(:last-child)::after {
  content: '';
  position: absolute;
  left: 11px;
  top: 26px;
  bottom: -10px;
  width: 1px;
  background: var(--border-color);
}

.ai-step-marker {
  width: 24px;
  height: 24px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  position: relative;
  z-index: 1;
}

.ai-step-marker.ok {
  background: var(--brand-primary-light);
  color: var(--brand-primary-dark);
}

.ai-step-marker.fail {
  background: #ffece8;
  color: #f53f3f;
}

.ai-step-body {
  flex: 1;
  min-width: 0;
}

.ai-step-head {
  display: flex;
  align-items: center;
  gap: 8px;
}

.ai-step-no {
  font-size: 10px;
  font-weight: 700;
  color: var(--text-placeholder);
  font-variant-numeric: tabular-nums;
}

.ai-step-name {
  font-size: 13px;
  font-weight: 600;
  color: var(--text-primary);
}

.ai-step-dur {
  margin-left: auto;
  font-size: 11px;
  color: var(--text-placeholder);
  font-variant-numeric: tabular-nums;
}

.ai-step-text {
  font-size: 12px;
  color: var(--text-secondary);
  margin-top: 2px;
  line-height: 1.5;
}
</style>
