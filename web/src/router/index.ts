import { createRouter, createWebHistory } from 'vue-router'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    // 根路径默认进入登录页
    { path: '/', redirect: '/login' },
    // 统一登录页（同时承载用户登录、用户注册、管理员登录）
    {
      path: '/login',
      name: 'Login',
      component: () => import('@/views/user/Login.vue'),
      meta: { title: '登录', userType: 'public' },
    },
    // 旧入口兼容
    { path: '/user/login', redirect: '/login' },
    { path: '/admin/login', redirect: '/login' },

    // 全屏可视化大屏（admin token 鉴权，独立路由不进 layout）
    {
      path: '/admin/screen',
      name: 'AdminScreen',
      component: () => import('@/views/admin/Screen.vue'),
      meta: { title: '可视化大屏', userType: 'admin' },
    },

    // ---- 管理员入口 ----
    {
      path: '/admin',
      component: () => import('@/components/AdminLayout.vue'),
      meta: { userType: 'admin' },
      redirect: '/admin/dashboard',
      children: [
        {
          path: 'dashboard',
          name: 'AdminDashboard',
          component: () => import('@/views/admin/Dashboard.vue'),
          meta: { title: '数据大盘', userType: 'admin' },
        },
        {
          path: 'inventory',
          name: 'AdminInventory',
          component: () => import('@/views/admin/Inventory.vue'),
          meta: { title: '库存管理', userType: 'admin' },
        },
        {
          path: 'fridge-map',
          name: 'AdminFridgeMap',
          component: () => import('@/views/admin/FridgeMap.vue'),
          meta: { title: '冰箱视图', userType: 'admin' },
        },
        {
          path: 'batch-recognize',
          name: 'AdminBatchRecognize',
          component: () => import('@/views/admin/BatchRecognize.vue'),
          meta: { title: '整柜批量识别', userType: 'admin' },
        },
        {
          path: 'pending-labels',
          name: 'AdminPendingLabels',
          component: () => import('@/views/admin/PendingLabels.vue'),
          meta: { title: '标签缓冲', userType: 'admin' },
        },
        {
          path: 'devices',
          name: 'AdminDevices',
          component: () => import('@/views/admin/Devices.vue'),
          meta: { title: '设备管理', userType: 'admin' },
        },
        {
          path: 'device-ingest',
          name: 'AdminDeviceIngest',
          component: () => import('@/views/admin/DeviceIngest.vue'),
          meta: { title: '端侧联调', userType: 'admin' },
        },
        {
          path: 'agent',
          name: 'AdminAgentConfig',
          component: () => import('@/views/admin/AgentConfig.vue'),
          meta: { title: 'Agent 配置', userType: 'admin' },
        },
        {
          path: 'vision-assist',
          name: 'AdminVisionAssist',
          component: () => import('@/views/admin/VisionAssist.vue'),
          meta: { title: '视觉辅助策略', userType: 'admin' },
        },
        {
          path: 'categories',
          name: 'AdminCategoryConfig',
          component: () => import('@/views/admin/CategoryConfig.vue'),
          meta: { title: '品类配置', userType: 'admin' },
        },
        {
          path: 'workflow',
          name: 'AdminWorkflow',
          component: () => import('@/views/admin/Workflow.vue'),
          meta: { title: '工作流', userType: 'admin' },
        },
        {
          path: 'logs',
          name: 'AdminLogs',
          component: () => import('@/views/admin/Logs.vue'),
          meta: { title: '系统日志', userType: 'admin' },
        },
        {
          path: 'audit',
          name: 'AdminAudit',
          component: () => import('@/views/admin/Audit.vue'),
          meta: { title: '操作审计', userType: 'admin' },
        },
        {
          path: 'usage',
          name: 'AdminUsage',
          component: () => import('@/views/admin/Usage.vue'),
          meta: { title: 'Token 用量', userType: 'admin' },
        },
        {
          path: 'perf',
          name: 'AdminPerf',
          component: () => import('@/views/admin/Perf.vue'),
          meta: { title: '性能监控', userType: 'admin' },
        },
        {
          path: 'waste',
          name: 'AdminWasteAnalytics',
          component: () => import('@/views/admin/WasteAnalytics.vue'),
          meta: { title: '浪费分析', userType: 'admin' },
        },
        {
          path: 'lifecycle',
          name: 'AdminLifecycle',
          component: () => import('@/views/admin/Lifecycle.vue'),
          meta: { title: '食材生命周期', userType: 'admin' },
        },
        {
          path: 'users',
          name: 'AdminUserManagement',
          component: () => import('@/views/admin/UserManagement.vue'),
          meta: { title: '用户管理', userType: 'admin' },
        },
      ],
    },

    // ---- 普通用户入口 ----
    {
      path: '/user',
      component: () => import('@/components/UserLayout.vue'),
      meta: { userType: 'user' },
      redirect: '/user/home',
      children: [
        {
          path: 'home',
          name: 'UserHome',
          component: () => import('@/views/user/Home.vue'),
          meta: { title: '首页', userType: 'user' },
        },
        {
          path: 'inventory',
          name: 'UserInventory',
          component: () => import('@/views/user/Inventory.vue'),
          meta: { title: '库存查看', userType: 'user' },
        },
        {
          path: 'expiring',
          name: 'UserExpiring',
          component: () => import('@/views/user/Expiring.vue'),
          meta: { title: '临期处理', userType: 'user' },
        },
        {
          path: 'fridge-map',
          name: 'UserFridgeMap',
          component: () => import('@/views/user/FridgeMap.vue'),
          meta: { title: '冰箱视图', userType: 'user' },
        },
        {
          path: 'chat',
          name: 'UserChat',
          component: () => import('@/views/user/Chat.vue'),
          meta: { title: 'AI对话', userType: 'user' },
        },
        {
          path: 'recognize',
          name: 'UserRecognize',
          component: () => import('@/views/user/Recognize.vue'),
          meta: { title: '食材识别', userType: 'user' },
        },
        {
          path: 'preferences',
          name: 'UserPreferences',
          component: () => import('@/views/user/Preferences.vue'),
          meta: { title: '偏好设置', userType: 'user' },
        },
        {
          path: 'recipes',
          name: 'UserRecipes',
          component: () => import('@/views/user/Recipes.vue'),
          meta: { title: '我的食谱', userType: 'user' },
        },
        {
          path: 'nutrition',
          name: 'UserNutrition',
          component: () => import('@/views/user/Nutrition.vue'),
          meta: { title: '健康饮食', userType: 'user' },
        },
        {
          path: 'environment',
          name: 'UserEnvironment',
          component: () => import('@/views/user/Environment.vue'),
          meta: { title: '查看天气', userType: 'user' },
        },
        {
          path: 'achievements',
          name: 'UserAchievements',
          component: () => import('@/views/user/Achievements.vue'),
          meta: { title: '我的成就', userType: 'user' },
        },
        {
          path: 'shopping',
          name: 'UserShopping',
          component: () => import('@/views/user/Shopping.vue'),
          meta: { title: '购物清单', userType: 'user' },
        },
      ],
    },

    // 兜底 404 -> 统一登录页
    { path: '/:pathMatch(.*)*', redirect: '/login' },
  ],
})

router.beforeEach((to, _from, next) => {
  const userType = to.meta.userType as string | undefined
  const adminToken = localStorage.getItem('admin_token')
  const userToken = localStorage.getItem('user_token')

  // 公共页面（登录页）：已登录则跳到对应主页（管理员优先）
  if (userType === 'public') {
    if (adminToken) return next('/admin')
    if (userToken) return next('/user')
    return next()
  }

  // 需要管理员身份
  if (userType === 'admin') {
    if (!adminToken) return next('/login')
    return next()
  }

  // 需要普通用户身份
  if (userType === 'user') {
    if (!userToken) return next('/login')
    return next()
  }

  next()
})

export default router
