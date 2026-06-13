<script setup lang="ts">
import { ref, computed } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { userLogin, userRegister, type LoginRequest, type RegisterRequest } from '@/api/user/auth'
import { adminLogin } from '@/api/admin/auth'
import { useUserAuthStore } from '@/stores/userAuth'
import { useAdminAuthStore } from '@/stores/adminAuth'

const router = useRouter()
const userAuthStore = useUserAuthStore()
const adminAuthStore = useAdminAuthStore()

type Mode = 'user-login' | 'user-register' | 'admin-login'
const mode = ref<Mode>('user-login')
const loading = ref(false)

const modeCards: Array<{
  mode: Mode
  label: string
  desc: string
  tone: 'user' | 'register' | 'admin'
}> = [
  { mode: 'user-login', label: '用户登录', desc: '进入个人冰箱', tone: 'user' },
  { mode: 'user-register', label: '用户注册', desc: '创建新账户', tone: 'register' },
  { mode: 'admin-login', label: '管理登录', desc: '进入管理端', tone: 'admin' },
]

const loginForm = ref<LoginRequest>({ username: '', password: '' })
const registerForm = ref<RegisterRequest>({ username: '', password: '' })
const confirmPassword = ref('')

const isAdmin = computed(() => mode.value === 'admin-login')
const activeModeCard = computed(() => modeCards.find(card => card.mode === mode.value) || modeCards[0])

function switchMode(m: Mode) {
  mode.value = m
  loginForm.value = { username: '', password: '' }
  registerForm.value = { username: '', password: '' }
  confirmPassword.value = ''
}

async function handleSubmit() {
  if (mode.value === 'user-login') {
    return doUserLogin()
  }
  if (mode.value === 'admin-login') {
    return doAdminLogin()
  }
  return doUserRegister()
}

async function doUserLogin() {
  if (!loginForm.value.username || !loginForm.value.password) {
    ElMessage.warning('请输入用户名和密码')
    return
  }
  loading.value = true
  try {
    const res = await userLogin(loginForm.value)
    userAuthStore.setAuth(res.token, {
      id: res.user_id,
      username: res.username,
      user_type: 'user',
    })
    ElMessage.success('登录成功')
    router.push('/user')
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail || '登录失败')
  } finally {
    loading.value = false
  }
}

async function doAdminLogin() {
  if (!loginForm.value.username || !loginForm.value.password) {
    ElMessage.warning('请输入管理员账号和密码')
    return
  }
  loading.value = true
  try {
    const res = await adminLogin(loginForm.value)
    adminAuthStore.setAuth(res.token, {
      id: res.admin_id,
      username: res.username,
      user_type: 'admin',
    })
    ElMessage.success('登录成功')
    router.push('/admin')
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail || '登录失败')
  } finally {
    loading.value = false
  }
}

async function doUserRegister() {
  const f = registerForm.value
  if (!f.username || !f.password) {
    ElMessage.warning('请输入用户名和密码')
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
  if (f.password !== confirmPassword.value) {
    ElMessage.warning('两次密码不一致')
    return
  }
  loading.value = true
  try {
    const res = await userRegister(f)
    userAuthStore.setAuth(res.token, {
      id: res.user_id,
      username: res.username,
      user_type: 'user',
    })
    ElMessage.success('注册成功')
    router.push('/user')
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail || '注册失败')
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <div class="login-page" :class="{ 'admin-theme': isAdmin }">
    <div class="login-card">
      <div class="login-brand">
        <img src="/logo.jpg" alt="logo" class="brand-logo" />
        <span class="brand-text">SMART-FRIDGE</span>
      </div>
      <p class="brand-sub">智能冰箱食材管理系统</p>

      <!-- 业务入口切换 -->
      <div class="mode-switch" role="tablist" aria-label="登录方式切换">
        <button
          v-for="card in modeCards"
          :key="card.mode"
          type="button"
          role="tab"
          :aria-selected="mode === card.mode"
          :class="['mode-tab', `tone-${card.tone}`, { active: mode === card.mode }]"
          @click="switchMode(card.mode)"
        >
          <span class="mode-tab-shutter left" aria-hidden="true"></span>
          <span class="mode-tab-shutter right" aria-hidden="true"></span>
          <span class="mode-tab-copy">
            <span class="mode-tab-label">{{ card.label }}</span>
          </span>
        </button>
      </div>

      <Transition name="window-open" mode="out-in">
        <div :key="mode" :class="['window-content-panel', `tone-${activeModeCard.tone}`]">
          <div class="window-leaf left" aria-hidden="true"></div>
          <div class="window-leaf right" aria-hidden="true"></div>

          <div class="mode-panel">
            <span class="mode-panel-copy">
              <span class="mode-panel-label">{{ activeModeCard.label }}</span>
              <span class="mode-panel-desc">{{ activeModeCard.desc }}</span>
            </span>
          </div>

          <!-- 管理员模式下显示警示徽章 -->
          <div v-if="isAdmin" class="admin-badge">
            <el-icon :size="14"><Lock /></el-icon> 管理端入口，仅授权账户可登录
          </div>

          <!-- 登录表单（普通用户/管理员共用，靠 mode 区分提交逻辑） -->
          <el-form v-if="mode !== 'user-register'" class="login-form" @submit.prevent="handleSubmit">
            <el-form-item>
              <el-input
                v-model="loginForm.username"
                :placeholder="isAdmin ? '管理员账号' : '用户名'"
                size="large"
                prefix-icon="User"
              />
            </el-form-item>
            <el-form-item>
              <el-input
                v-model="loginForm.password"
                type="password"
                placeholder="密码"
                size="large"
                prefix-icon="Lock"
                show-password
                @keyup.enter="handleSubmit"
              />
            </el-form-item>
            <el-button
              type="primary"
              size="large"
              :loading="loading"
              @click="handleSubmit"
              :class="['submit-btn', { 'admin-btn': isAdmin }]"
            >
              {{ isAdmin ? '管理登录' : '登录' }}
            </el-button>
          </el-form>

          <!-- 注册表单 -->
          <el-form v-else class="login-form" @submit.prevent="handleSubmit">
            <el-form-item>
              <el-input v-model="registerForm.username" placeholder="用户名（至少3个字符）" size="large" prefix-icon="User" />
            </el-form-item>
            <el-form-item>
              <el-input v-model="registerForm.password" type="password" placeholder="密码（至少6个字符）" size="large" prefix-icon="Lock" show-password />
            </el-form-item>
            <el-form-item>
              <el-input v-model="confirmPassword" type="password" placeholder="确认密码" size="large" prefix-icon="Lock" show-password @keyup.enter="handleSubmit" />
            </el-form-item>
            <el-button type="primary" size="large" :loading="loading" @click="handleSubmit" class="submit-btn">
              注册
            </el-button>
          </el-form>
        </div>
      </Transition>
    </div>
  </div>
</template>

<style scoped>
.login-page {
  min-height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  background:
    linear-gradient(90deg, rgba(255, 255, 255, 0.035) 1px, transparent 1px),
    linear-gradient(180deg, rgba(255, 255, 255, 0.035) 1px, transparent 1px),
    linear-gradient(110deg, rgba(8, 10, 12, 0.92) 0%, rgba(14, 18, 20, 0.78) 42%, rgba(8, 10, 12, 0.88) 100%),
    url("https://images.pexels.com/photos/16146919/pexels-photo-16146919.jpeg?auto=compress&cs=tinysrgb&w=1920");
  background-size: 48px 48px, 48px 48px, auto, cover;
  background-position: center, center, center, center;
  padding: 24px;
  transition: background 0.4s;
}

.login-page.admin-theme {
  background:
    linear-gradient(90deg, rgba(255, 255, 255, 0.035) 1px, transparent 1px),
    linear-gradient(180deg, rgba(255, 255, 255, 0.035) 1px, transparent 1px),
    linear-gradient(110deg, rgba(18, 10, 6, 0.92) 0%, rgba(35, 20, 13, 0.8) 46%, rgba(8, 10, 12, 0.9) 100%),
    url("https://images.pexels.com/photos/16146919/pexels-photo-16146919.jpeg?auto=compress&cs=tinysrgb&w=1920");
  background-size: 48px 48px, 48px 48px, auto, cover;
}

.login-card {
  position: relative;
  z-index: 0;
  width: 440px;
  padding: 36px 36px 34px;
  background: #f6f3ec;
  border: 1px solid rgba(255, 255, 255, 0.44);
  border-radius: 4px;
  box-shadow:
    0 26px 70px rgba(0, 0, 0, 0.42),
    0 3px 0 rgba(255, 255, 255, 0.35) inset;
  overflow: visible;
}

.login-card::before,
.login-card::after {
  content: '';
  position: absolute;
  inset: 10px;
  background: #e5ded2;
  border-radius: 4px;
  box-shadow: 0 18px 38px rgba(0, 0, 0, 0.28);
  z-index: -1;
}

.login-card::before {
  transform: rotate(-3deg) translate(-7px, 9px);
}

.login-card::after {
  background: #d8d0c3;
  transform: rotate(3deg) translate(8px, 13px);
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
  border-radius: 4px;
  object-fit: cover;
  box-shadow: 0 6px 14px rgba(0, 0, 0, 0.18);
}

.brand-text {
  font-size: 23px;
  font-weight: 800;
  color: #1d2730;
  letter-spacing: 0;
}

.brand-sub {
  text-align: center;
  color: #6c6258;
  font-size: 14px;
  margin: 0 0 22px;
}

.mode-switch {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 8px;
  margin: 18px 0 16px;
  perspective: 900px;
}

.mode-tab {
  min-width: 0;
  height: 48px;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 8px;
  border: 1px solid #cbc1b2;
  border-radius: 3px;
  background: #efe7dc;
  color: #26313a;
  cursor: pointer;
  overflow: hidden;
  position: relative;
  text-align: center;
  transform-style: preserve-3d;
  transition:
    border-color 0.2s ease,
    box-shadow 0.2s ease,
    transform 0.2s ease;
}

.mode-tab:hover {
  border-color: #2d7f77;
  transform: translateY(-1px);
}

.mode-tab.active {
  border-color: var(--mode-color, #2d7f77);
  color: #f8f4ee;
  background: #1f2b31;
  box-shadow: 0 8px 18px rgba(31, 43, 49, 0.18);
}

.mode-tab-shutter {
  position: absolute;
  top: 6px;
  bottom: 6px;
  width: calc(50% - 6px);
  border: 1px solid rgba(255, 255, 255, 0.12);
  background: rgba(255, 255, 255, 0.08);
  box-shadow: inset 0 0 0 1px rgba(255, 255, 255, 0.08);
  opacity: 0;
  pointer-events: none;
  transition:
    opacity 0.28s ease,
    transform 0.42s cubic-bezier(0.2, 0.8, 0.2, 1);
}

.mode-tab-shutter.left {
  left: 6px;
  border-radius: 3px 1px 1px 3px;
  transform-origin: left center;
}

.mode-tab-shutter.right {
  right: 6px;
  border-radius: 1px 3px 3px 1px;
  transform-origin: right center;
}

.mode-tab.active .mode-tab-shutter.left {
  opacity: 1;
  transform: rotateY(-62deg);
}

.mode-tab.active .mode-tab-shutter.right {
  opacity: 1;
  transform: rotateY(62deg);
}

.mode-tab-copy {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  flex-direction: column;
  width: 100%;
  min-width: 0;
  position: relative;
  z-index: 1;
}

.mode-tab-label {
  max-width: 100%;
  color: inherit;
  font-size: 15px;
  font-weight: 800;
  line-height: 1.15;
  text-align: center;
  white-space: nowrap;
}

.window-content-panel {
  position: relative;
  overflow: hidden;
  padding: 18px 16px 16px;
  border: 1px solid #d5cbbd;
  border-radius: 4px;
  background: #fbf8f2;
  box-shadow:
    0 10px 24px rgba(46, 37, 27, 0.08),
    0 1px 0 rgba(255, 255, 255, 0.9) inset;
  transform-origin: center top;
}

.window-leaf {
  position: absolute;
  top: 10px;
  bottom: 10px;
  width: calc(50% - 10px);
  border: 1px solid rgba(45, 127, 119, 0.16);
  background: rgba(45, 127, 119, 0.06);
  opacity: 0.35;
  pointer-events: none;
}

.window-leaf.left {
  left: 10px;
  border-radius: 4px 1px 1px 4px;
  transform: perspective(720px) rotateY(-72deg);
  transform-origin: left center;
}

.window-leaf.right {
  right: 10px;
  border-radius: 1px 4px 4px 1px;
  transform: perspective(720px) rotateY(72deg);
  transform-origin: right center;
}

.mode-panel {
  position: relative;
  z-index: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 0;
  min-height: 58px;
  margin-bottom: 16px;
  text-align: center;
}

.mode-panel :deep(.mode-panel-mark),
.mode-panel-mark {
  display: none !important;
}

.mode-panel-copy {
  display: flex;
  flex-direction: column;
  align-items: center;
  width: 100%;
  min-width: 0;
}

.mode-panel-label {
  font-size: 18px;
  font-weight: 800;
  line-height: 1.2;
  color: #1d2730;
}

.mode-panel-desc {
  margin-top: 5px;
  font-size: 13px;
  color: #6c6258;
}

.login-form {
  position: relative;
  z-index: 1;
}

.login-form :deep(.el-form-item) {
  margin-bottom: 14px;
}

.login-form :deep(.el-input__wrapper) {
  height: 44px;
  border-radius: 3px;
  background: #f4eee5;
  box-shadow: inset 0 0 0 1px #d6cab9;
}

.login-form :deep(.el-input__wrapper.is-focus) {
  box-shadow: inset 0 0 0 1px var(--mode-color), 0 0 0 3px rgba(45, 127, 119, 0.12);
}

.login-form :deep(.el-input__inner) {
  color: #1d2730;
}

.window-open-enter-active,
.window-open-leave-active {
  transition:
    opacity 0.28s ease,
    clip-path 0.38s cubic-bezier(0.2, 0.8, 0.2, 1),
    transform 0.38s cubic-bezier(0.2, 0.8, 0.2, 1);
}

.window-open-enter-from {
  opacity: 0;
  clip-path: inset(0 48% 0 48% round 14px);
  transform: perspective(780px) rotateY(-18deg) scale(0.98);
}

.window-open-leave-to {
  opacity: 0;
  clip-path: inset(0 48% 0 48% round 14px);
  transform: perspective(780px) rotateY(18deg) scale(0.98);
}

.tone-user {
  --mode-color: #2d7f77;
}

.tone-register {
  --mode-color: #3f8f52;
}

.tone-admin {
  --mode-color: #b4612d;
}

.admin-badge {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  padding: 8px 0;
  margin-bottom: 16px;
  background: #fff2e6;
  border: 1px solid #e8c9aa;
  border-radius: 3px;
  color: #9a4d20;
  font-size: 13px;
  font-weight: 500;
}

.submit-btn {
  width: 100%;
  height: 44px;
  font-size: 15px;
  border-radius: 3px;
  margin-top: 4px;
  background: #2d7f77 !important;
  border-color: #2d7f77 !important;
  box-shadow: 0 10px 18px rgba(45, 127, 119, 0.22);
}

.submit-btn:hover {
  background: #246960 !important;
  border-color: #246960 !important;
}

.submit-btn.admin-btn {
  background: #b4612d !important;
  border-color: #b4612d !important;
  box-shadow: 0 10px 18px rgba(180, 97, 45, 0.22);
}

.submit-btn.admin-btn:hover {
  background: #934b22 !important;
  border-color: #934b22 !important;
}

@media (max-width: 560px) {
  .login-page {
    padding: 24px;
  }

  .login-card {
    width: 100%;
    padding: 30px 22px;
  }

  .brand-text {
    font-size: 20px;
  }

  .mode-switch {
    grid-template-columns: 1fr;
    gap: 8px;
  }

  .mode-tab {
    height: 58px;
  }

  .mode-tab-label {
    white-space: normal;
  }
}
</style>
