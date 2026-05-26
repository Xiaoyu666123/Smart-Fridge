<script setup lang="ts">
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { login, register, type LoginRequest, type RegisterRequest } from '@/api/auth'
import { useAuthStore } from '@/stores/auth'

const router = useRouter()
const authStore = useAuthStore()

const isLogin = ref(true)
const isAdminLogin = ref(false)
const loading = ref(false)

const loginForm = ref<LoginRequest>({ username: '', password: '' })
const registerForm = ref<RegisterRequest>({ username: '', password: '' })
const confirmPassword = ref('')

function switchMode(login: boolean, admin = false) {
  isLogin.value = login
  isAdminLogin.value = admin
}

async function handleLogin() {
  if (!loginForm.value.username || !loginForm.value.password) {
    ElMessage.warning('请输入用户名和密码')
    return
  }
  loading.value = true
  try {
    const res = await login(loginForm.value)
    if (isAdminLogin.value && res.role !== 'admin') {
      ElMessage.error('该账户不是管理员')
      return
    }
    authStore.setAuth(res.token, { id: res.user_id, username: res.username, role: res.role })
    ElMessage.success('登录成功')
    router.push('/')
  } catch (e: any) {
    const msg = e?.response?.data?.detail || '登录失败'
    ElMessage.error(msg)
  } finally {
    loading.value = false
  }
}

async function handleRegister() {
  if (!registerForm.value.username || !registerForm.value.password) {
    ElMessage.warning('请输入用户名和密码')
    return
  }
  if (registerForm.value.username.length < 3) {
    ElMessage.warning('用户名至少3个字符')
    return
  }
  if (registerForm.value.password.length < 6) {
    ElMessage.warning('密码至少6个字符')
    return
  }
  if (registerForm.value.password !== confirmPassword.value) {
    ElMessage.warning('两次密码不一致')
    return
  }
  loading.value = true
  try {
    const res = await register(registerForm.value)
    authStore.setAuth(res.token, { id: res.user_id, username: res.username, role: res.role })
    ElMessage.success('注册成功')
    router.push('/')
  } catch (e: any) {
    const msg = e?.response?.data?.detail || '注册失败'
    ElMessage.error(msg)
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <div class="login-page">
    <div class="login-card">
      <!-- Logo -->
      <div class="login-brand">
        <img src="/logo.jpg" alt="logo" class="brand-logo" />
        <span class="brand-text">SMART-FRIDGE</span>
      </div>
      <p class="brand-sub">智能冰箱食材管理系统</p>

      <!-- 切换标签 -->
      <div class="tab-bar">
        <div :class="['tab-item', { active: isLogin && !isAdminLogin }]" @click="switchMode(true, false)">用户登录</div>
        <div :class="['tab-item', { active: isLogin && isAdminLogin }]" @click="switchMode(true, true)">管理员登录</div>
        <div :class="['tab-item', { active: !isLogin }]" @click="switchMode(false)">用户注册</div>
      </div>

      <!-- 登录表单 -->
      <el-form v-if="isLogin" class="login-form" @submit.prevent="handleLogin">
        <div v-if="isAdminLogin" class="admin-badge">
          <el-icon><Cpu /></el-icon> 管理员入口
        </div>
        <el-form-item>
          <el-input v-model="loginForm.username" placeholder="用户名" size="large" prefix-icon="User" />
        </el-form-item>
        <el-form-item>
          <el-input v-model="loginForm.password" type="password" placeholder="密码" size="large" prefix-icon="Lock" show-password />
        </el-form-item>
        <el-button type="primary" size="large" :loading="loading" @click="handleLogin" class="submit-btn">
          {{ isAdminLogin ? '管理员登录' : '登录' }}
        </el-button>
      </el-form>

      <!-- 注册表单 -->
      <el-form v-else class="login-form" @submit.prevent="handleRegister">
        <el-form-item>
          <el-input v-model="registerForm.username" placeholder="用户名（至少3个字符）" size="large" prefix-icon="User" />
        </el-form-item>
        <el-form-item>
          <el-input v-model="registerForm.password" type="password" placeholder="密码（至少6个字符）" size="large" prefix-icon="Lock" show-password />
        </el-form-item>
        <el-form-item>
          <el-input v-model="confirmPassword" type="password" placeholder="确认密码" size="large" prefix-icon="Lock" show-password />
        </el-form-item>
        <el-button type="primary" size="large" :loading="loading" @click="handleRegister" class="submit-btn">
          注册
        </el-button>
      </el-form>
    </div>
  </div>
</template>

<style scoped>
.login-page {
  min-height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  background: linear-gradient(135deg, #e8f0ff 0%, #f0f5ff 50%, #e8f0ff 100%);
}

.login-card {
  width: 420px;
  padding: 40px 36px;
  background: #fff;
  border-radius: 16px;
  box-shadow: 0 8px 32px rgba(22, 93, 255, 0.1);
}

.login-brand {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 12px;
  margin-bottom: 4px;
}

.brand-logo {
  width: 40px;
  height: 40px;
  border-radius: 10px;
  object-fit: cover;
}

.brand-text {
  font-size: 24px;
  font-weight: 800;
  color: var(--brand-primary);
  letter-spacing: 1px;
}

.brand-sub {
  text-align: center;
  color: var(--text-secondary);
  font-size: 14px;
  margin-bottom: 28px;
}

.tab-bar {
  display: flex;
  border-bottom: 2px solid #f0f0f0;
  margin-bottom: 24px;
}

.tab-item {
  flex: 1;
  text-align: center;
  padding: 10px 0;
  font-size: 14px;
  font-weight: 500;
  color: var(--text-secondary);
  cursor: pointer;
  transition: all 0.2s;
  border-bottom: 2px solid transparent;
  margin-bottom: -2px;
}

.tab-item:hover {
  color: var(--brand-primary);
}

.tab-item.active {
  color: var(--brand-primary);
  border-bottom-color: var(--brand-primary);
}

.admin-badge {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  padding: 8px 0;
  margin-bottom: 12px;
  background: #fff7e6;
  border: 1px solid #ffd591;
  border-radius: 8px;
  color: #d46b08;
  font-size: 13px;
  font-weight: 500;
}

.login-form {
  margin-top: 0;
}

.submit-btn {
  width: 100%;
  height: 44px;
  font-size: 15px;
  border-radius: 10px;
  margin-top: 4px;
}
</style>
