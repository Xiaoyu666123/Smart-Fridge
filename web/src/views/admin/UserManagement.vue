<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  listUsers, createUser, resetUserPassword, deleteUser,
  changeAdminPassword,
  type AdminUserItem,
} from '@/api/admin/users'
import { useAdminAuthStore } from '@/stores/adminAuth'

const authStore = useAdminAuthStore()

const loading = ref(false)
const users = ref<AdminUserItem[]>([])
const search = ref('')

// 创建用户
const showCreateDialog = ref(false)
const createLoading = ref(false)
const createForm = ref({ username: '', password: '' })

// 重置密码
const showResetDialog = ref(false)
const resetLoading = ref(false)
const resetForm = ref({ user_id: '', username: '', new_password: '' })

// 改自己密码
const showChangePwdDialog = ref(false)
const changePwdLoading = ref(false)
const changePwdForm = ref({ old_password: '', new_password: '', confirm: '' })

async function fetchUsers() {
  loading.value = true
  try {
    users.value = await listUsers(search.value || undefined)
  } catch {
    ElMessage.error('获取用户列表失败')
  } finally {
    loading.value = false
  }
}

function openCreate() {
  createForm.value = { username: '', password: '' }
  showCreateDialog.value = true
}

async function handleCreate() {
  const f = createForm.value
  if (!f.username.trim() || !f.password.trim()) {
    ElMessage.warning('请填写用户名和密码')
    return
  }
  if (f.username.length < 3) {
    ElMessage.warning('用户名至少3个字符')
    return
  }
  if (f.password.length < 6) {
    ElMessage.warning('密码至少6个字符')
    return
  }
  createLoading.value = true
  try {
    await createUser(f)
    ElMessage.success('用户创建成功')
    showCreateDialog.value = false
    fetchUsers()
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail || '创建失败')
  } finally {
    createLoading.value = false
  }
}

function openReset(user: AdminUserItem) {
  resetForm.value = { user_id: user.id, username: user.username, new_password: '' }
  showResetDialog.value = true
}

async function handleReset() {
  if (resetForm.value.new_password.length < 6) {
    ElMessage.warning('密码至少6个字符')
    return
  }
  resetLoading.value = true
  try {
    await resetUserPassword(resetForm.value.user_id, resetForm.value.new_password)
    ElMessage.success('密码已重置')
    showResetDialog.value = false
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail || '重置失败')
  } finally {
    resetLoading.value = false
  }
}

async function handleDelete(user: AdminUserItem) {
  try {
    await ElMessageBox.confirm(
      `确定删除用户「${user.username}」？该操作会同时删除其偏好和对话记录，且不可恢复。`,
      '删除确认',
      { confirmButtonText: '删除', cancelButtonText: '取消', type: 'warning' },
    )
    await deleteUser(user.id)
    ElMessage.success('删除成功')
    fetchUsers()
  } catch (e: any) {
    if (e === 'cancel') return
    ElMessage.error(e?.response?.data?.detail || '删除失败')
  }
}

function openChangePwd() {
  changePwdForm.value = { old_password: '', new_password: '', confirm: '' }
  showChangePwdDialog.value = true
}

async function handleChangePwd() {
  const f = changePwdForm.value
  if (!f.old_password || !f.new_password) {
    ElMessage.warning('请填写完整')
    return
  }
  if (f.new_password.length < 6) {
    ElMessage.warning('新密码至少6个字符')
    return
  }
  if (f.new_password !== f.confirm) {
    ElMessage.warning('两次新密码不一致')
    return
  }
  changePwdLoading.value = true
  try {
    await changeAdminPassword(f.old_password, f.new_password)
    ElMessage.success('密码修改成功，请重新登录')
    showChangePwdDialog.value = false
    setTimeout(() => {
      authStore.logout()
      window.location.href = '/login'
    }, 800)
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail || '修改失败')
  } finally {
    changePwdLoading.value = false
  }
}

function formatDate(s: string | null) {
  if (!s) return '-'
  return new Date(s).toLocaleString('zh-CN')
}

const stats = computed(() => ({
  total: users.value.length,
  active: users.value.filter(u => u.conversation_count > 0).length,
  withPrefs: users.value.filter(u => u.preference_count > 0).length,
}))

onMounted(fetchUsers)
</script>

<template>
  <div>
    <!-- 顶部统计 -->
    <div class="stat-row">
      <div class="stat-card">
        <div class="stat-icon" style="background: var(--brand-primary-light); color: var(--brand-primary)">
          <el-icon :size="22"><User /></el-icon>
        </div>
        <div>
          <div class="stat-value">{{ stats.total }}</div>
          <div class="stat-label">普通用户总数</div>
        </div>
      </div>
      <div class="stat-card">
        <div class="stat-icon" style="background: #e8f7e8; color: #00b42a">
          <el-icon :size="22"><ChatDotRound /></el-icon>
        </div>
        <div>
          <div class="stat-value">{{ stats.active }}</div>
          <div class="stat-label">使用过 AI 对话</div>
        </div>
      </div>
      <div class="stat-card">
        <div class="stat-icon" style="background: #fff7e6; color: #fa8c16">
          <el-icon :size="22"><MagicStick /></el-icon>
        </div>
        <div>
          <div class="stat-value">{{ stats.withPrefs }}</div>
          <div class="stat-label">设置了偏好</div>
        </div>
      </div>
    </div>

    <!-- 操作栏 -->
    <el-card shadow="never" style="margin-bottom: 16px">
      <el-form :inline="true">
        <el-form-item label="用户名">
          <el-input v-model="search" placeholder="模糊搜索" clearable style="width: 220px" @keyup.enter="fetchUsers" />
        </el-form-item>
        <el-form-item>
          <el-button type="primary" @click="fetchUsers">查询冰箱库存</el-button>
        </el-form-item>
        <el-form-item>
          <el-button type="success" @click="openCreate">
            <el-icon><Plus /></el-icon> 新建用户
          </el-button>
        </el-form-item>
        <el-form-item>
          <el-button @click="openChangePwd">
            <el-icon><Lock /></el-icon> 修改我的密码
          </el-button>
        </el-form-item>
      </el-form>
    </el-card>

    <!-- 表格 -->
    <el-card shadow="never">
      <el-table :data="users" v-loading="loading" stripe>
        <el-table-column label="用户名" prop="username" width="180" />
        <el-table-column label="注册时间" width="200">
          <template #default="{ row }">{{ formatDate(row.created_at) }}</template>
        </el-table-column>
        <el-table-column label="偏好数" width="100" align="center">
          <template #default="{ row }">
            <el-tag :type="row.preference_count > 0 ? 'success' : 'info'" size="small" round>
              {{ row.preference_count }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="对话数" width="100" align="center">
          <template #default="{ row }">
            <el-tag :type="row.conversation_count > 0 ? 'primary' : 'info'" size="small" round>
              {{ row.conversation_count }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="ID" min-width="280">
          <template #default="{ row }">
            <code class="mono">{{ row.id }}</code>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="180" fixed="right">
          <template #default="{ row }">
            <div class="action-buttons">
              <el-button size="small" class="table-action reset-action" @click="openReset(row)">重置密码</el-button>
              <el-button size="small" class="table-action delete-action" @click="handleDelete(row)">删除</el-button>
            </div>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <!-- 新建用户 -->
    <el-dialog v-model="showCreateDialog" title="新建普通用户" width="420px">
      <el-form label-width="80px">
        <el-form-item label="用户名">
          <el-input v-model="createForm.username" placeholder="至少3个字符" />
        </el-form-item>
        <el-form-item label="初始密码">
          <el-input v-model="createForm.password" type="password" placeholder="至少6个字符" show-password />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showCreateDialog = false">取消</el-button>
        <el-button type="primary" :loading="createLoading" @click="handleCreate">创建</el-button>
      </template>
    </el-dialog>

    <!-- 重置密码 -->
    <el-dialog v-model="showResetDialog" title="重置用户密码" width="420px">
      <el-form label-width="80px">
        <el-form-item label="用户">
          <el-input :model-value="resetForm.username" disabled />
        </el-form-item>
        <el-form-item label="新密码">
          <el-input v-model="resetForm.new_password" type="password" placeholder="至少6个字符" show-password />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showResetDialog = false">取消</el-button>
        <el-button type="primary" :loading="resetLoading" @click="handleReset">重置</el-button>
      </template>
    </el-dialog>

    <!-- 改自己密码 -->
    <el-dialog v-model="showChangePwdDialog" title="修改管理员密码" width="420px">
      <el-form label-width="90px">
        <el-form-item label="原密码">
          <el-input v-model="changePwdForm.old_password" type="password" show-password />
        </el-form-item>
        <el-form-item label="新密码">
          <el-input v-model="changePwdForm.new_password" type="password" show-password placeholder="至少6个字符" />
        </el-form-item>
        <el-form-item label="确认新密码">
          <el-input v-model="changePwdForm.confirm" type="password" show-password />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showChangePwdDialog = false">取消</el-button>
        <el-button type="primary" :loading="changePwdLoading" @click="handleChangePwd">确认修改</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped>
.stat-row {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 16px;
  margin-bottom: 16px;
}

.stat-card {
  display: flex;
  align-items: center;
  gap: 14px;
  padding: 18px 20px;
  background: var(--bg-card);
  border-radius: var(--radius-md);
  box-shadow: var(--shadow-sm);
}

.stat-icon {
  width: 44px;
  height: 44px;
  border-radius: 12px;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.stat-value {
  font-size: 22px;
  font-weight: 700;
  color: var(--text-primary);
  line-height: 1.2;
}

.stat-label {
  font-size: 12px;
  color: var(--text-secondary);
  margin-top: 2px;
}

.mono {
  font-family: 'SFMono-Regular', Consolas, monospace;
  font-size: 12px;
  color: var(--text-secondary);
}

.action-buttons {
  display: flex;
  align-items: center;
  gap: 8px;
}

.table-action {
  height: 26px;
  margin-left: 0 !important;
  padding: 0 8px;
  border-radius: 6px;
  background: transparent !important;
  font-size: 12px;
  font-weight: 600;
  box-shadow: none !important;
}

.reset-action {
  color: var(--brand-primary-dark) !important;
  border: 1px solid var(--brand-primary-light) !important;
}

.reset-action:hover,
.reset-action:focus {
  color: var(--brand-primary-dark) !important;
  background: var(--brand-primary-soft) !important;
  border-color: var(--brand-primary) !important;
}

.delete-action {
  color: #dc2626 !important;
  border: 1px solid rgba(220, 38, 38, 0.18) !important;
}

.delete-action:hover,
.delete-action:focus {
  color: #b91c1c !important;
  background: rgba(220, 38, 38, 0.08) !important;
  border-color: rgba(220, 38, 38, 0.34) !important;
}
</style>
