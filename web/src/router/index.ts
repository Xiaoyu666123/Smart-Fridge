import { createRouter, createWebHistory } from 'vue-router'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    {
      path: '/login',
      name: 'Login',
      component: () => import('@/views/Login.vue'),
      meta: { title: '登录', public: true },
    },
    {
      path: '/',
      name: 'Inventory',
      component: () => import('@/views/Inventory.vue'),
      meta: { title: '库存概览' },
    },
    {
      path: '/chat',
      name: 'Chat',
      component: () => import('@/views/Chat.vue'),
      meta: { title: 'AI 食谱推荐' },
    },
    {
      path: '/recognize',
      name: 'Recognize',
      component: () => import('@/views/Recognize.vue'),
      meta: { title: '食材识别' },
    },
    {
      path: '/preferences',
      name: 'Preferences',
      component: () => import('@/views/Preferences.vue'),
      meta: { title: '偏好设置' },
    },
    {
      path: '/environment',
      name: 'Environment',
      component: () => import('@/views/Environment.vue'),
      meta: { title: '环境信息' },
    },
    {
      path: '/agent',
      name: 'AgentConfig',
      component: () => import('@/views/AgentConfig.vue'),
      meta: { title: 'Agent 管理', admin: true },
    },
    {
      path: '/workflow',
      name: 'Workflow',
      component: () => import('@/views/Workflow.vue'),
      meta: { title: '工作流管理', admin: true },
    },
    {
      path: '/logs',
      name: 'Logs',
      component: () => import('@/views/Logs.vue'),
      meta: { title: '系统日志', admin: true },
    },
  ],
})

router.beforeEach((to, _from, next) => {
  const token = localStorage.getItem('token')
  if (!to.meta.public && !token) {
    next('/login')
  } else if (to.path === '/login' && token) {
    next('/')
  } else {
    next()
  }
})

export default router
