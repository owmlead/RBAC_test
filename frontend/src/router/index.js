// ──────────────────────────────────────────
// 路由配置模块
// 定义公开路由和受保护路由，并在全局前置守卫中实现：
//   1. 登录状态检测与重定向
//   2. 页面刷新后会话恢复
//   3. 基于权限码的路由访问控制
// ──────────────────────────────────────────

import { createRouter, createWebHistory } from 'vue-router'
import { useAuthStore } from '@/stores/auth'

// ── 公开路由（无需登录即可访问）──
const publicRoutes = [
  {
    path: '/login',
    name: 'Login',
    component: () => import('@/views/login/LoginView.vue'),
    meta: { title: '登录', public: true },
  },
  {
    path: '/403',
    name: 'Forbidden',
    component: () => import('@/views/error/403.vue'),
    meta: { title: '无权限', public: true },
  },
  {
    path: '/404',
    name: 'NotFound',
    component: () => import('@/views/error/404.vue'),
    meta: { title: '页面不存在', public: true },
  },
  {
    // 未匹配的任何路径重定向到 404
    path: '/:pathMatch(.*)*',
    redirect: '/404',
  },
]

// ── 受保护路由（需登录 + 权限校验）──
const protectedRoutes = {
  path: '/',
  component: () => import('@/components/layout/AppLayout.vue'),
  redirect: '/dashboard',
  children: [
    {
      path: 'dashboard',
      name: 'Dashboard',
      component: () => import('@/views/dashboard/DashboardView.vue'),
      meta: { title: '仪表盘', icon: 'HomeFilled' },
    },
    {
      path: 'system/user',
      name: 'Users',
      component: () => import('@/views/system/users/UserList.vue'),
      meta: { title: '用户管理', permission: 'user:list' },
    },
    {
      path: 'system/role',
      name: 'Roles',
      component: () => import('@/views/system/roles/RoleList.vue'),
      meta: { title: '角色管理', permission: 'role:list' },
    },
    {
      path: 'system/permission',
      name: 'Permissions',
      component: () => import('@/views/system/permissions/PermissionList.vue'),
      meta: { title: '权限管理', permission: 'permission:list' },
    },
    {
      path: 'audit',
      name: 'AuditLog',
      component: () => import('@/views/system/audit/Log.vue'),
      meta: { title: '审计日志', permission: 'audit:list' },
    },
  ],
}

// 创建路由实例（HTML5 History 模式）
const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes: [...publicRoutes, protectedRoutes],
  // 路由切换后始终滚动到顶部
  scrollBehavior: () => ({ top: 0 }),
})

/**
 * 全局前置路由守卫。
 * 按顺序执行：公开路由放行 → Token 校验 → 会话恢复 → 权限校验
 */
router.beforeEach(async (to, _from) => {
  // 设置页面标题
  document.title = `${to.meta.title || 'RBAC 管理系统'} - RBAC`
  const authStore = useAuthStore()

  // 1. 公开页面直接放行
  if (to.meta.public) {
    // 已登录用户访问登录页 → 重定向到仪表盘
    if (to.path === '/login' && authStore.isLoggedIn) {
      return '/dashboard'
    }
    return true
  }

  // 2. 无 token → 跳转登录页（携带 redirect 参数以便登录后跳回）
  if (!authStore.accessToken) {
    return { path: '/login', query: { redirect: to.fullPath } }
  }

  // 3. 有 token，确保会话已恢复（处理页面刷新场景）
  if (!authStore.user) {
    // user 不在内存中，尝试完整恢复会话
    const restored = await authStore.tryRestoreSession()
    if (!restored) {
      return { path: '/login', query: { redirect: to.fullPath } }
    }
  } else {
    // 每次导航都刷新权限和菜单（确保权限变更后即时生效）
    try {
      await authStore.fetchMenus(authStore.user.id)
    } catch {
      // 菜单加载失败不阻塞导航，权限由后端最终校验
    }
  }

  // 4. 检查路由所需权限
  const requiredPermission = to.meta.permission
  if (requiredPermission && !authStore.hasPermission(requiredPermission)) {
    return '/403'
  }

  return true
})

export default router
