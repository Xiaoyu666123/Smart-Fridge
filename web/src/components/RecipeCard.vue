<script setup lang="ts">
/**
 * 食谱卡片：从 LLM 流式输出 ===RECIPE=== 块解析后的结构化数据渲染。
 *
 * Props:
 *  - recipe: { name, summary, prep_time, difficulty, ingredients, steps, tags }
 *  - saved: 是否已收藏（控制按钮文案/状态）
 *
 * Emits:
 *  - save: 用户点收藏 → 父组件调 saveRecipe API
 *  - unsave: 已收藏状态下取消
 *  - cook: 打卡"做过了"
 */
import { computed, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { getSubstitute, type SubstituteResult } from '@/api/user/agent'
import CookingMode from './CookingMode.vue'

interface Ingredient {
  name: string
  amount?: string | null
}

interface Recipe {
  name: string
  summary?: string | null
  prep_time?: number | null
  difficulty?: string | null
  ingredients?: Ingredient[] | null
  steps?: string[] | null
  tags?: string[] | null
}

const props = defineProps<{
  recipe: Recipe
  saved?: boolean
  showCook?: boolean
}>()

const emit = defineEmits<{
  (e: 'save', r: Recipe): void
  (e: 'unsave', r: Recipe): void
  (e: 'cook', r: Recipe): void
}>()

const difficultyColor = computed(() => {
  const d = props.recipe.difficulty
  if (d === '简单') return '#10b981'
  if (d === '中等') return '#f59e0b'
  if (d === '困难') return '#ef4444'
  return '#94a3b8'
})

function handleSave() {
  if (props.saved) emit('unsave', props.recipe)
  else emit('save', props.recipe)
}

// ---- 食材替换助手 ----
const subDialog = ref({
  visible: false,
  loading: false,
  ingredient: '',
  result: null as SubstituteResult | null,
})

async function askSubstitute(ing: string) {
  subDialog.value.ingredient = ing
  subDialog.value.visible = true
  subDialog.value.loading = true
  subDialog.value.result = null
  try {
    subDialog.value.result = await getSubstitute(ing, props.recipe.name)
  } catch {
    ElMessage.error('AI 替换助手暂时不可用')
  } finally {
    subDialog.value.loading = false
  }
}

// ---- 烹饪模式 ----
const cookingVisible = ref(false)

function startCooking() {
  if (!props.recipe.steps || props.recipe.steps.length === 0) {
    ElMessage.warning('该食谱没有步骤数据')
    return
  }
  cookingVisible.value = true
}

function onCooked() {
  emit('cook', props.recipe)
}
</script>

<template>
  <div class="recipe-card">
    <div class="rc-head">
      <div class="rc-title-row">
        <h3 class="rc-name">{{ recipe.name }}</h3>
        <div class="rc-meta">
          <span v-if="recipe.prep_time" class="meta-pill">
            <el-icon :size="12"><Clock /></el-icon>
            {{ recipe.prep_time }} 分钟
          </span>
          <span v-if="recipe.difficulty" class="meta-pill" :style="{ color: difficultyColor, background: difficultyColor + '15' }">
            {{ recipe.difficulty }}
          </span>
        </div>
      </div>
      <p v-if="recipe.summary" class="rc-summary">{{ recipe.summary }}</p>
      <div v-if="recipe.tags && recipe.tags.length" class="rc-tags">
        <span v-for="t in recipe.tags" :key="t" class="rc-tag">#{{ t }}</span>
      </div>
    </div>

    <div v-if="recipe.ingredients && recipe.ingredients.length" class="rc-section">
      <div class="section-title">📋 食材</div>
      <div class="ingredients-grid">
        <div v-for="(ing, i) in recipe.ingredients" :key="i" class="ing-row">
          <span class="ing-dot"></span>
          <span class="ing-name">{{ ing.name }}</span>
          <span v-if="ing.amount" class="ing-amount">{{ ing.amount }}</span>
          <button class="ing-sub-btn" @click="askSubstitute(ing.name)" title="问 AI 用什么替代">
            🔄
          </button>
        </div>
      </div>
    </div>

    <div v-if="recipe.steps && recipe.steps.length" class="rc-section">
      <div class="section-title">🍳 步骤</div>
      <div class="steps-list">
        <div v-for="(s, i) in recipe.steps" :key="i" class="step-row">
          <div class="step-no">{{ i + 1 }}</div>
          <div class="step-text">{{ s }}</div>
        </div>
      </div>
    </div>

    <div class="rc-actions">
      <el-button
        v-if="recipe.steps && recipe.steps.length > 0"
        size="small"
        type="primary"
        @click="startCooking"
      >
        <el-icon><VideoPlay /></el-icon>
        开始烹饪
      </el-button>
      <el-button
        size="small"
        class="save-recipe-btn"
        :class="{ saved }"
        @click="handleSave"
      >
        <el-icon><Star v-if="!saved" /><StarFilled v-else /></el-icon>
        {{ saved ? '已收藏' : '收藏' }}
      </el-button>
      <el-button v-if="showCook" size="small" class="cook-check-btn" @click="emit('cook', recipe)">
        <el-icon><Check /></el-icon>
        做过了
      </el-button>
    </div>
  </div>

  <!-- 食材替换助手弹窗 -->
  <el-dialog
    v-model="subDialog.visible"
    :title="`AI 替换助手：${subDialog.ingredient}`"
    width="460px"
    append-to-body
  >
    <div v-loading="subDialog.loading" class="sub-body">
      <div v-if="subDialog.result" class="sub-content">
        <div v-if="subDialog.result.summary" class="sub-summary">
          <span class="sub-quote">"</span>
          {{ subDialog.result.summary }}
        </div>
        <div v-if="subDialog.result.options.length === 0" class="sub-empty">
          AI 没找到合适的替代方案
        </div>
        <div v-else class="sub-options">
          <div
            v-for="(opt, i) in subDialog.result.options"
            :key="i"
            class="sub-option"
            :class="{ 'in-stock': opt.in_stock }"
          >
            <div class="sub-rank">{{ i + 1 }}</div>
            <div class="sub-info">
              <div class="sub-name">
                {{ opt.name }}
                <span v-if="opt.in_stock" class="sub-tag in-stock-tag">✓ 冰箱里有</span>
                <span v-else class="sub-tag missing-tag">需采购</span>
              </div>
              <div class="sub-reason">{{ opt.reason }}</div>
            </div>
          </div>
        </div>
      </div>
      <div v-else-if="!subDialog.loading" class="sub-empty">
        请稍候…
      </div>
    </div>
  </el-dialog>

  <!-- 全屏烹饪模式 -->
  <CookingMode
    v-model:visible="cookingVisible"
    :recipe="recipe"
    @cooked="onCooked"
  />
</template>

<style scoped>
.recipe-card {
  background: linear-gradient(135deg, var(--bg-card) 0%, var(--brand-primary-soft) 100%);
  border: 1px solid var(--brand-primary-light);
  border-radius: var(--radius-lg);
  padding: 18px 20px;
  margin: 8px 0;
  box-shadow: var(--shadow-sm);
  transition: box-shadow 0.2s, transform 0.2s;
}

.recipe-card:hover {
  box-shadow: var(--shadow-md);
  transform: translateY(-1px);
}

[data-theme="dark"] .recipe-card {
  background: linear-gradient(135deg, var(--bg-card) 0%, #1d4536 100%);
}

.rc-title-row {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 10px;
  margin-bottom: 4px;
}

.rc-name {
  font-size: 17px;
  font-weight: 700;
  color: var(--text-primary);
  margin: 0;
}

.rc-meta {
  display: flex;
  gap: 6px;
  flex-shrink: 0;
}

.meta-pill {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  font-size: 11px;
  padding: 2px 8px;
  border-radius: 999px;
  background: var(--bg-soft);
  color: var(--text-secondary);
  font-weight: 500;
}

.rc-summary {
  font-size: 13px;
  color: var(--text-secondary);
  margin: 4px 0;
  line-height: 1.5;
}

.rc-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
  margin-top: 6px;
}

.rc-tag {
  font-size: 11px;
  color: var(--brand-primary-dark);
  background: var(--brand-primary-light);
  padding: 1px 8px;
  border-radius: 4px;
}

.rc-section {
  margin-top: 12px;
  padding-top: 12px;
  border-top: 1px dashed var(--brand-primary-light);
}

.section-title {
  font-size: 12px;
  font-weight: 600;
  color: var(--text-secondary);
  margin-bottom: 8px;
}

.ingredients-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 4px 12px;
}

.ing-row {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 13px;
  padding: 2px 0;
}

.ing-dot {
  width: 5px;
  height: 5px;
  border-radius: 50%;
  background: var(--brand-primary);
  flex-shrink: 0;
}

.ing-name {
  color: var(--text-primary);
  flex: 1;
}

.ing-amount {
  color: var(--text-secondary);
  font-size: 12px;
}

.ing-sub-btn {
  background: transparent;
  border: none;
  cursor: pointer;
  font-size: 12px;
  opacity: 0;
  transition: opacity 0.18s, transform 0.18s;
  padding: 2px 6px;
  border-radius: 6px;
}

.ing-row:hover .ing-sub-btn {
  opacity: 1;
}

.ing-sub-btn:hover {
  background: var(--brand-primary-light);
  transform: scale(1.15);
}

/* 替换助手弹窗 */
.sub-body {
  min-height: 80px;
}

.sub-summary {
  font-size: 14px;
  color: var(--text-primary);
  line-height: 1.6;
  background: var(--brand-primary-soft);
  border: 1px dashed var(--brand-primary);
  border-radius: 10px;
  padding: 10px 14px;
  margin-bottom: 14px;
}

.sub-quote {
  font-size: 20px;
  color: var(--brand-primary);
  font-family: Georgia, serif;
  vertical-align: -2px;
  margin-right: 4px;
  opacity: 0.5;
}

.sub-options {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.sub-option {
  display: flex;
  gap: 10px;
  padding: 10px 14px;
  border-radius: 10px;
  border: 1px solid var(--border-color);
  background: var(--bg-card);
}

.sub-option.in-stock {
  border-color: var(--brand-primary);
  background: var(--brand-primary-soft);
}

.sub-rank {
  width: 24px;
  height: 24px;
  border-radius: 50%;
  background: var(--bg-soft);
  color: var(--text-secondary);
  font-size: 12px;
  font-weight: 700;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.sub-option.in-stock .sub-rank {
  background: var(--brand-primary);
  color: #fff;
}

.sub-info {
  flex: 1;
  min-width: 0;
}

.sub-name {
  font-size: 14px;
  font-weight: 700;
  color: var(--text-primary);
  display: flex;
  align-items: center;
  gap: 8px;
}

.sub-tag {
  font-size: 11px;
  font-weight: 600;
  padding: 1px 8px;
  border-radius: 999px;
}

.sub-tag.in-stock-tag {
  background: var(--brand-primary);
  color: #fff;
}

.sub-tag.missing-tag {
  background: var(--bg-soft);
  color: var(--text-secondary);
}

.sub-reason {
  font-size: 12px;
  color: var(--text-secondary);
  margin-top: 4px;
  line-height: 1.5;
}

.sub-empty {
  text-align: center;
  padding: 20px;
  color: var(--text-placeholder);
  font-size: 13px;
}

.steps-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.step-row {
  display: flex;
  gap: 10px;
  align-items: flex-start;
}

.step-no {
  width: 22px;
  height: 22px;
  border-radius: 50%;
  background: var(--brand-primary);
  color: #fff;
  font-size: 12px;
  font-weight: 700;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  margin-top: 1px;
}

.step-text {
  font-size: 13px;
  color: var(--text-primary);
  line-height: 1.6;
  flex: 1;
}

.rc-actions {
  display: flex;
  gap: 8px;
  margin-top: 14px;
  padding-top: 12px;
  border-top: 1px solid var(--brand-primary-light);
  justify-content: flex-end;
}

.save-recipe-btn.el-button {
  background: #f6fbfd !important;
  border-color: #cfe7f4 !important;
  color: #0369a1 !important;
  box-shadow: none !important;
}

.save-recipe-btn.el-button:hover {
  background: #eaf6fc !important;
  border-color: #8fcdec !important;
  color: #075985 !important;
}

.save-recipe-btn.el-button.saved {
  background: #f0fdf4 !important;
  border-color: #bbf7d0 !important;
  color: #15803d !important;
}

.save-recipe-btn.el-button.saved:hover {
  background: #dcfce7 !important;
  border-color: #86efac !important;
  color: #166534 !important;
}

.cook-check-btn.el-button {
  background: var(--bg-card) !important;
  border-color: #9fd4f2 !important;
  color: #0369a1 !important;
  font-weight: 600;
}

.cook-check-btn.el-button:hover,
.cook-check-btn.el-button:focus {
  background: var(--brand-primary-soft) !important;
  border-color: var(--brand-primary-dark) !important;
  color: var(--brand-primary-dark) !important;
}

.cook-check-btn.el-button:active {
  background: var(--brand-primary-light) !important;
  color: var(--brand-primary-dark) !important;
}

[data-theme="dark"] .cook-check-btn.el-button {
  background: #102536 !important;
  border-color: #2f7596 !important;
  color: #7dd3fc !important;
}

[data-theme="dark"] .cook-check-btn.el-button:hover,
[data-theme="dark"] .cook-check-btn.el-button:focus {
  background: #143a52 !important;
  border-color: #38bdf8 !important;
  color: #bae6fd !important;
}

@media (max-width: 600px) {
  .ingredients-grid {
    grid-template-columns: 1fr;
  }
}
</style>
