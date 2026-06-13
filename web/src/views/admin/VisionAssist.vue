<script setup lang="ts">
/**
 * 视觉辅助识别策略：控制端侧识别置信度落在哪个区间时触发云端复核。
 */
import { ref, computed, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import {
  getVisionAssistConfig,
  updateVisionAssistConfig,
  type VisionAssistConfig,
} from '@/api/admin/agent'

const loading = ref(false)
const saving = ref(false)
const config = ref<VisionAssistConfig | null>(null)
const range = ref<[number, number]>([0.30, 0.70])

const rangeError = computed(() => {
  const [lower, upper] = range.value
  if (lower < 0 || lower > 1) return 'lower 必须在 [0, 1]'
  if (upper < 0 || upper > 1) return 'upper 必须在 [0, 1]'
  if (lower >= upper) return 'lower 必须严格小于 upper'
  return ''
})

const dirty = computed(() => {
  if (!config.value) return false
  return Math.abs(config.value.lower - range.value[0]) > 1e-9 ||
         Math.abs(config.value.upper - range.value[1]) > 1e-9
})

async function fetchConfig() {
  loading.value = true
  try {
    config.value = await getVisionAssistConfig()
    range.value = [config.value.lower, config.value.upper]
  } catch (e) {
    console.error('获取视觉辅助配置失败', e)
    ElMessage.error('获取视觉辅助配置失败')
  } finally {
    loading.value = false
  }
}

async function saveConfig() {
  if (rangeError.value) {
    ElMessage.warning(rangeError.value)
    return
  }
  saving.value = true
  try {
    const [lower, upper] = range.value
    config.value = await updateVisionAssistConfig(
      Number(lower.toFixed(2)),
      Number(upper.toFixed(2)),
    )
    range.value = [config.value.lower, config.value.upper]
    ElMessage.success('视觉辅助识别策略已更新，下一次端侧上报立即生效')
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail || '保存失败')
  } finally {
    saving.value = false
  }
}

function resetDefault() {
  range.value = [0.30, 0.70]
}

function formatPercent(v: number): string {
  return Math.round(v * 100) + '%'
}

function formatDate(s: string | null): string {
  if (!s) return '-'
  return new Date(s).toLocaleString('zh-CN')
}

onMounted(fetchConfig)
</script>

<template>
  <div class="vision-assist-page">
    <el-card shadow="never" class="feature-card">
      <div class="feature-icon">
        <el-icon :size="24"><MagicStick /></el-icon>
      </div>
      <div class="feature-copy">
        <div class="feature-title">视觉辅助识别策略</div>
        <div class="feature-sub">配置端侧识别置信度触发云端 vision 复核的区间，控制准确率与 token 成本的平衡。</div>
      </div>
      <el-tag v-if="config" :type="config.is_default ? 'info' : 'success'" size="small" round>
        {{ config.is_default ? '系统默认' : '已自定义' }}
      </el-tag>
    </el-card>

    <el-card shadow="never" class="strategy-card" v-loading="loading">
      <template #header>
        <div class="strategy-head">
          <span class="card-title">触发区间</span>
          <span v-if="config" class="updated-at">
            最近修改：{{ formatDate(config.updated_at) }}
            <span v-if="config.updated_by_admin_id"> · {{ config.updated_by_admin_id.slice(0, 8) }}</span>
          </span>
        </div>
      </template>

      <div class="rule-grid">
        <div class="rule-item">
          <span class="rule-key">低于 lower</span>
          <span class="rule-text">端侧识别太差，云端也救不回，直接采用端侧结果。</span>
        </div>
        <div class="rule-item active">
          <span class="rule-key">区间内</span>
          <span class="rule-text">可疑档位，触发云端复核，云端置信度更高时覆盖。</span>
        </div>
        <div class="rule-item">
          <span class="rule-key">高于 upper</span>
          <span class="rule-text">端侧已经很准，没必要再消耗 token。</span>
        </div>
      </div>

      <div class="slider-row">
        <span class="slider-label">触发区间</span>
        <el-slider
          v-model="range"
          range
          :min="0"
          :max="1"
          :step="0.05"
          :marks="{ 0: '0', 0.3: { style: { color: 'var(--brand-secondary)' }, label: '默认 0.3' }, 0.5: '0.5', 0.7: { style: { color: 'var(--brand-secondary)' }, label: '默认 0.7' }, 1: '1' }"
          :format-tooltip="formatPercent"
          style="flex: 1"
        />
      </div>

      <div class="num-row">
        <div class="num-cell">
          <span class="num-label">lower</span>
          <el-input-number
            v-model="range[0]"
            :min="0"
            :max="range[1] - 0.05"
            :step="0.05"
            :precision="2"
            controls-position="right"
            size="small"
          />
        </div>
        <div class="num-cell">
          <span class="num-label">upper</span>
          <el-input-number
            v-model="range[1]"
            :min="range[0] + 0.05"
            :max="1"
            :step="0.05"
            :precision="2"
            controls-position="right"
            size="small"
          />
        </div>
      </div>

      <div class="range-visual">
        <div class="rv-bar">
          <div class="rv-zone rv-skip-low" :style="{ width: (range[0] * 100) + '%' }">
            <span v-if="range[0] >= 0.10">跳过</span>
          </div>
          <div class="rv-zone rv-trigger" :style="{ width: ((range[1] - range[0]) * 100) + '%' }">
            <span v-if="(range[1] - range[0]) >= 0.15">触发云端 vision</span>
          </div>
          <div class="rv-zone rv-skip-high" :style="{ width: ((1 - range[1]) * 100) + '%' }">
            <span v-if="(1 - range[1]) >= 0.10">跳过</span>
          </div>
        </div>
        <div class="rv-axis">
          <span>0</span>
          <span>{{ range[0].toFixed(2) }}</span>
          <span>{{ range[1].toFixed(2) }}</span>
          <span>1</span>
        </div>
      </div>

      <div v-if="rangeError" class="error-tip">
        <el-icon :size="12"><Warning /></el-icon> {{ rangeError }}
      </div>

      <div class="strategy-actions">
        <el-button @click="resetDefault" :disabled="saving">恢复默认 0.30 / 0.70</el-button>
        <el-button @click="fetchConfig" :disabled="saving">放弃修改</el-button>
        <el-button
          type="primary"
          :loading="saving"
          :disabled="!!rangeError || !dirty"
          @click="saveConfig"
        >
          保存并立即生效
        </el-button>
      </div>
    </el-card>
  </div>
</template>

<style scoped>
.vision-assist-page {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.feature-card :deep(.el-card__body) {
  display: flex;
  align-items: center;
  gap: 14px;
}

.feature-icon {
  width: 48px;
  height: 48px;
  border-radius: 12px;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  background: #fff7ed;
  color: var(--brand-secondary);
}

.feature-copy {
  flex: 1;
  min-width: 0;
}

.feature-title {
  font-size: 18px;
  font-weight: 700;
  color: var(--text-primary);
  line-height: 1.3;
}

.feature-sub {
  margin-top: 4px;
  color: var(--text-secondary);
  font-size: 13px;
  line-height: 1.6;
}

.strategy-card :deep(.el-card__header) {
  padding: 14px 20px !important;
}

.strategy-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
}

.card-title {
  font-size: 15px;
  font-weight: 600;
}

.updated-at {
  color: var(--text-placeholder);
  font-size: 12px;
}

.rule-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 10px;
  margin-bottom: 18px;
}

.rule-item {
  min-height: 88px;
  padding: 14px;
  border: 1px solid var(--border-color);
  border-radius: 8px;
  background: var(--bg-soft);
}

.rule-item.active {
  border-color: var(--brand-secondary-light);
  background: var(--brand-secondary-soft);
}

.rule-key {
  display: block;
  color: var(--text-primary);
  font-size: 14px;
  font-weight: 700;
  margin-bottom: 6px;
}

.rule-text {
  color: var(--text-secondary);
  font-size: 13px;
  line-height: 1.6;
}

.slider-row {
  display: flex;
  align-items: center;
  gap: 16px;
  padding: 18px 12px 30px;
}

.slider-label {
  font-size: 13px;
  font-weight: 600;
  color: var(--text-secondary);
  min-width: 70px;
}

.num-row {
  display: flex;
  align-items: flex-end;
  gap: 16px;
  margin-bottom: 18px;
}

.num-cell {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.num-label {
  font-size: 11px;
  color: var(--text-placeholder);
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

.range-visual {
  margin: 8px 0 16px;
}

.rv-bar {
  display: flex;
  height: 28px;
  border-radius: 999px;
  overflow: hidden;
  background: var(--bg-soft);
  font-size: 11px;
  font-weight: 600;
  color: #fff;
}

.rv-zone {
  display: flex;
  align-items: center;
  justify-content: center;
  transition: width 0.3s ease;
  white-space: nowrap;
  overflow: hidden;
}

.rv-skip-low {
  background: linear-gradient(90deg, #94a3b8, #cbd5e1);
}

.rv-trigger {
  background: linear-gradient(90deg, var(--brand-secondary), var(--brand-secondary-hover));
  box-shadow: inset 0 0 0 2px rgba(255, 255, 255, 0.3);
}

.rv-skip-high {
  background: linear-gradient(90deg, var(--brand-primary), var(--brand-primary-hover));
}

.rv-axis {
  display: flex;
  justify-content: space-between;
  margin-top: 4px;
  font-size: 11px;
  color: var(--text-secondary);
  font-variant-numeric: tabular-nums;
  padding: 0 2px;
}

.error-tip {
  display: flex;
  align-items: center;
  gap: 4px;
  margin-bottom: 12px;
  font-size: 12px;
  color: #ef4444;
}

.strategy-actions {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
  border-top: 1px solid var(--border-light);
  padding-top: 16px;
}

@media (max-width: 900px) {
  .rule-grid {
    grid-template-columns: 1fr;
  }

  .slider-row {
    align-items: stretch;
    flex-direction: column;
  }
}
</style>
