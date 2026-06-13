<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  getShoppingList, addShoppingItem, updateShoppingItem,
  deleteShoppingItem, clearCheckedShopping, suggestShopping,
  type ShoppingItem,
} from '@/api/user/shopping'
import { showUndoToast } from '@/composables/useUndoToast'

const loading = ref(false)
const items = ref<ShoppingItem[]>([])
const newName = ref('')
const newQty = ref(1)
const adding = ref(false)
const suggesting = ref(false)

async function fetchList() {
  loading.value = true
  try {
    const res = await getShoppingList()
    items.value = res.items
  } catch {
    ElMessage.error('加载购物清单失败')
  } finally {
    loading.value = false
  }
}

const pending = computed(() => items.value.filter(i => !i.checked))
const done = computed(() => items.value.filter(i => i.checked))
const stats = computed(() => ({
  total: items.value.length,
  pending: pending.value.length,
  done: done.value.length,
}))

async function handleAdd() {
  const name = newName.value.trim()
  if (!name) {
    ElMessage.warning('请输入要买的东西')
    return
  }
  adding.value = true
  try {
    const it = await addShoppingItem(name, newQty.value)
    const idx = items.value.findIndex(x => x.id === it.id)
    if (idx >= 0) items.value[idx] = it
    else items.value.unshift(it)
    newName.value = ''
    newQty.value = 1
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail || '添加失败')
  } finally {
    adding.value = false
  }
}

async function toggleCheck(item: ShoppingItem) {
  const target = !item.checked
  try {
    const updated = await updateShoppingItem(item.id, { checked: target })
    const idx = items.value.findIndex(x => x.id === item.id)
    if (idx >= 0) items.value[idx] = updated
  } catch {
    ElMessage.error('操作失败')
  }
}

async function changeQty(item: ShoppingItem, delta: number) {
  const q = Math.max(1, (item.qty || 1) + delta)
  if (q === item.qty) return
  try {
    const updated = await updateShoppingItem(item.id, { qty: q })
    const idx = items.value.findIndex(x => x.id === item.id)
    if (idx >= 0) items.value[idx] = updated
  } catch {
    ElMessage.error('操作失败')
  }
}

async function handleDelete(item: ShoppingItem) {
  try {
    await deleteShoppingItem(item.id)
    items.value = items.value.filter(x => x.id !== item.id)
    showUndoToast({
      message: `已删除「${item.name}」`,
      duration: 5,
      onUndo: async () => {
        try {
          const restored = await addShoppingItem(item.name, item.qty)
          items.value.unshift(restored)
          ElMessage.success('已恢复')
        } catch {
          ElMessage.error('恢复失败')
        }
      },
    })
  } catch {
    ElMessage.error('删除失败')
  }
}

async function handleSuggest() {
  suggesting.value = true
  try {
    const res = await suggestShopping()
    if (res.added_count > 0) {
      await fetchList()
      ElMessage.success(`已根据消耗习惯补充 ${res.added_count} 项建议`)
    } else {
      ElMessage.info('暂无新的补货建议')
    }
  } catch {
    ElMessage.error('生成建议失败')
  } finally {
    suggesting.value = false
  }
}

async function handleClearChecked() {
  if (done.value.length === 0) return
  try {
    await ElMessageBox.confirm(`确定清除 ${done.value.length} 项已购买的？`, '清除已购', {
      confirmButtonText: '清除', cancelButtonText: '取消', type: 'warning',
    })
    const res = await clearCheckedShopping()
    items.value = items.value.filter(i => !i.checked)
    ElMessage.success(`已清除 ${res.removed} 项`)
  } catch (e) {
    if (e === 'cancel') return
  }
}

function buildText(): string {
  const lines: string[] = []
  lines.push(`🛒 购物清单 ${new Date().toLocaleDateString('zh-CN')}`)
  lines.push('')
  pending.value.forEach(i => lines.push(`☐ ${i.name}${i.qty > 1 ? ' ×' + i.qty : ''}`))
  if (done.value.length) {
    lines.push('')
    lines.push('已买：')
    done.value.forEach(i => lines.push(`☑ ${i.name}${i.qty > 1 ? ' ×' + i.qty : ''}`))
  }
  return lines.join('\n')
}

async function copyList() {
  if (items.value.length === 0) {
    ElMessage.info('清单是空的')
    return
  }
  try {
    await navigator.clipboard.writeText(buildText())
    ElMessage.success('清单已复制到剪贴板')
  } catch {
    ElMessage.warning('复制失败，请手动选择')
  }
}

function exportTxt() {
  if (items.value.length === 0) {
    ElMessage.info('清单是空的')
    return
  }
  const blob = new Blob([new TextEncoder().encode('\ufeff' + buildText())],
                        { type: 'text/plain;charset=utf-8' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = `shopping_${new Date().toISOString().slice(0, 10)}.txt`
  document.body.appendChild(a)
  a.click()
  document.body.removeChild(a)
  URL.revokeObjectURL(url)
}

function onEnter() {
  handleAdd()
}

onMounted(fetchList)
</script>

<template>
  <div class="shop-page">
    <!-- Hero -->
    <div class="hero">
      <div class="hero-bg"></div>
      <div class="hero-inner">
        <div class="hero-left">
          <div class="hero-icon">🛒</div>
          <div>
            <div class="hero-title">购物清单</div>
            <div class="hero-sub">
              共 <strong>{{ stats.total }}</strong> 项 ·
              待买 <strong>{{ stats.pending }}</strong> ·
              已买 <strong>{{ stats.done }}</strong>
            </div>
          </div>
        </div>
        <div class="hero-actions">
          <el-button :loading="suggesting" @click="handleSuggest">
            <el-icon><MagicStick /></el-icon> 智能补货建议
          </el-button>
          <el-button @click="copyList">
            <el-icon><CopyDocument /></el-icon> 复制
          </el-button>
          <el-button @click="exportTxt">
            <el-icon><Download /></el-icon> 导出
          </el-button>
        </div>
      </div>
    </div>

    <!-- 添加输入 -->
    <el-card shadow="never" class="add-card">
      <div class="add-row">
        <el-input
          v-model="newName"
          placeholder="要买什么？输入后按 Enter 添加"
          size="large"
          clearable
          @keyup.enter="onEnter"
        >
          <template #prefix><el-icon><ShoppingCart /></el-icon></template>
        </el-input>
        <div class="qty-stepper">
          <button @click="newQty = Math.max(1, newQty - 1)">−</button>
          <span>{{ newQty }}</span>
          <button @click="newQty++">+</button>
        </div>
        <el-button type="primary" size="large" :loading="adding" @click="handleAdd">
          <el-icon><Plus /></el-icon> 添加
        </el-button>
      </div>
    </el-card>

    <div v-loading="loading">
      <!-- 待买 -->
      <div class="list-section">
        <div class="section-head">
          <h3 class="section-title">📝 待买 <span class="count">{{ pending.length }}</span></h3>
        </div>
        <div v-if="pending.length > 0" class="item-list">
          <div v-for="item in pending" :key="item.id" class="shop-item">
            <button class="check-box" @click="toggleCheck(item)" title="标记已买"></button>
            <div class="item-name">
              {{ item.name }}
              <span v-if="item.source === 'auto'" class="auto-tag" title="系统根据消耗习惯建议">建议</span>
            </div>
            <div class="qty-stepper small">
              <button @click="changeQty(item, -1)">−</button>
              <span>{{ item.qty }}</span>
              <button @click="changeQty(item, 1)">+</button>
            </div>
            <button class="del-btn" @click="handleDelete(item)" title="删除">
              <el-icon><Delete /></el-icon>
            </button>
          </div>
        </div>
        <el-empty v-else-if="!loading" description="待买清单是空的，加点东西或点「智能补货建议」" :image-size="80" />
      </div>

      <!-- 已买 -->
      <div v-if="done.length > 0" class="list-section">
        <div class="section-head">
          <h3 class="section-title done-title">✅ 已买 <span class="count">{{ done.length }}</span></h3>
          <el-button link type="danger" size="small" @click="handleClearChecked">清除已买</el-button>
        </div>
        <div class="item-list">
          <div v-for="item in done" :key="item.id" class="shop-item checked">
            <button class="check-box checked" @click="toggleCheck(item)" title="取消已买">
              <el-icon :size="12"><Check /></el-icon>
            </button>
            <div class="item-name">
              {{ item.name }}
              <span v-if="item.qty > 1" class="qty-badge">×{{ item.qty }}</span>
            </div>
            <button class="del-btn" @click="handleDelete(item)" title="删除">
              <el-icon><Delete /></el-icon>
            </button>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.shop-page {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

/* Hero */
.hero {
  position: relative;
  border-radius: var(--radius-md);
  overflow: hidden;
  background: var(--bg-card);
  box-shadow: var(--shadow-sm);
  border: 1px solid var(--border-color);
}

.hero-bg {
  position: absolute;
  inset: 0;
  background:
    radial-gradient(ellipse at 0% 0%, rgba(14, 165, 233, 0.16), transparent 55%),
    radial-gradient(ellipse at 100% 100%, rgba(99, 102, 241, 0.10), transparent 55%);
  pointer-events: none;
}

.hero-inner {
  position: relative;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  padding: 22px 26px;
  flex-wrap: wrap;
}

.hero-left {
  display: flex;
  align-items: center;
  gap: 16px;
}

.hero-icon {
  width: 56px;
  height: 56px;
  border-radius: 16px;
  background: linear-gradient(135deg, var(--brand-primary-light), var(--brand-primary-soft));
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 28px;
  border: 1px solid rgba(14, 165, 233, 0.3);
}

.hero-title {
  font-size: 22px;
  font-weight: 800;
  color: var(--text-primary);
  letter-spacing: -0.5px;
}

.hero-sub {
  font-size: 13px;
  color: var(--text-secondary);
  margin-top: 4px;
}

.hero-sub strong {
  color: var(--brand-primary-dark);
  font-weight: 700;
}

.hero-actions {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}

/* 添加输入 */
.add-card :deep(.el-card__body) {
  padding: 16px 18px !important;
}

.add-row {
  display: flex;
  align-items: center;
  gap: 12px;
}

.qty-stepper {
  display: inline-flex;
  align-items: center;
  gap: 0;
  border: 1px solid var(--border-color);
  border-radius: 10px;
  overflow: hidden;
  flex-shrink: 0;
}

.qty-stepper button {
  width: 36px;
  height: 38px;
  border: none;
  background: var(--bg-soft);
  color: var(--text-secondary);
  font-size: 18px;
  cursor: pointer;
  transition: all 0.15s;
}

.qty-stepper button:hover {
  background: var(--brand-primary-light);
  color: var(--brand-primary-dark);
}

.qty-stepper span {
  min-width: 36px;
  text-align: center;
  font-weight: 700;
  color: var(--text-primary);
  font-variant-numeric: tabular-nums;
}

.qty-stepper.small button {
  width: 26px;
  height: 26px;
  font-size: 14px;
}

.qty-stepper.small span {
  min-width: 26px;
  font-size: 13px;
}

/* 列表 */
.list-section {
  margin-top: 4px;
}

.section-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 10px;
}

.section-title {
  margin: 0;
  font-size: 16px;
  font-weight: 700;
  color: var(--text-primary);
  display: flex;
  align-items: center;
  gap: 8px;
}

.section-title.done-title {
  color: var(--text-secondary);
}

.count {
  font-size: 12px;
  font-weight: 700;
  color: #fff;
  background: var(--brand-primary);
  border-radius: 999px;
  padding: 1px 9px;
}

.done-title .count {
  background: var(--text-placeholder);
}

.item-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.shop-item {
  display: flex;
  align-items: center;
  gap: 14px;
  padding: 12px 16px;
  background: var(--bg-card);
  border: 1px solid var(--border-color);
  border-radius: 12px;
  transition: all 0.18s;
}

.shop-item:hover {
  border-color: var(--brand-primary);
  box-shadow: 0 4px 12px rgba(14, 165, 233, 0.10);
}

.shop-item.checked {
  opacity: 0.6;
  background: var(--bg-soft);
}

.check-box {
  width: 22px;
  height: 22px;
  border-radius: 50%;
  border: 2px solid var(--border-color);
  background: transparent;
  cursor: pointer;
  flex-shrink: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #fff;
  transition: all 0.18s;
}

.check-box:hover {
  border-color: var(--brand-primary);
}

.check-box.checked {
  background: var(--brand-primary);
  border-color: var(--brand-primary);
}

.item-name {
  flex: 1;
  font-size: 15px;
  font-weight: 500;
  color: var(--text-primary);
  display: flex;
  align-items: center;
  gap: 8px;
  min-width: 0;
}

.shop-item.checked .item-name {
  text-decoration: line-through;
  color: var(--text-placeholder);
}

.auto-tag {
  font-size: 10px;
  font-weight: 700;
  padding: 1px 7px;
  border-radius: 999px;
  background: rgba(99, 102, 241, 0.12);
  color: #6366f1;
}

.qty-badge {
  font-size: 12px;
  color: var(--text-secondary);
}

.del-btn {
  background: transparent;
  border: none;
  cursor: pointer;
  color: var(--text-placeholder);
  padding: 4px;
  border-radius: 6px;
  display: flex;
  align-items: center;
  transition: all 0.18s;
  flex-shrink: 0;
}

.del-btn:hover {
  color: var(--color-danger);
  background: #fef2f2;
}

@media (max-width: 700px) {
  .add-row { flex-wrap: wrap; }
  .hero-actions { width: 100%; }
}
</style>
