// ──────────────────────────────────────────
// 认证状态管理 Store（Pinia）
// 管理用户登录状态、Token、权限列表、动态菜单，
// 支持页面刷新后从 localStorage 恢复会话。
// ──────────────────────────────────────────

import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { login as loginApi, logout as logoutApi, refreshToken as refreshTokenApi } from '@/api/auth'
import { getUserPermissions, getUserDetail } from '@/api/user'
import {
  getAccessToken,
  setAccessToken,
  getRefreshToken,
  setRefreshToken,
  clearAuthData,
  setUserInfo,
  getUserInfo,
  removeUserInfo,
} from '@/utils'

export const useAuthStore = defineStore('auth', () => {
  // 尝试从 localStorage 恢复用户信息（页面刷新后保持登录状态）
  const savedUser = getUserInfo()
  const user = ref(savedUser)
  const accessToken = ref(getAccessToken())
  const refreshToken = ref(getRefreshToken())
  const permissions = ref([])
  const menus = ref([])

  // 计算属性：是否已登录
  const isLoggedIn = computed(() => !!accessToken.value && !!user.value)
  // 计算属性：Token 是否有效
  const isTokenValid = computed(() => !!accessToken.value)

  /**
   * 检查当前用户是否拥有指定权限码。
   * 支持通配符 '*'（超级管理员）和模块级通配符 'module:*'
   * @param {string} code - 权限编码，如 'user:create'
   * @returns {boolean} 是否有权限
   */
  function hasPermission(code) {
    if (permissions.value.includes('*')) return true
    if (permissions.value.includes(code)) return true
    // 模块级通配符匹配：如 'user:*' 匹配 'user:create'
    return permissions.value.some((p) => p.endsWith(':*') && code.startsWith(p.slice(0, -1)))
  }

  /**
   * 用户登录：调用 API → 保存 Token → 拉取菜单权限。
   * @param {string} username - 用户名
   * @param {string} password - 密码
   * @param {string} captchaId - 验证码 ID（可选）
   * @param {string} captcha - 验证码文本（可选）
   * @returns {object} 用户信息
   */
  async function login(username, password, captchaId, captcha) {
    const { data: res } = await loginApi({ username, password, captchaId, captcha })
    if (res.code !== 0) throw new Error(res.message)

    const { access_token, refresh_token, user_info } = res.data
    accessToken.value = access_token
    refreshToken.value = refresh_token
    user.value = user_info
    permissions.value = user_info.permissions || []

    // 持久化存储 Token 和用户信息（roles 用于 HeaderBar 下拉显示）
    setAccessToken(access_token)
    setRefreshToken(refresh_token)
    setUserInfo({
      id: user_info.id,
      username: user_info.username,
      real_name: user_info.real_name,
      roles: user_info.roles || [],
    })

    // 拉取动态菜单
    await fetchMenus(user_info.id)

    return user_info
  }

  /**
   * 拉取用户菜单和权限（用于动态路由/侧边栏渲染）。
   * @param {number} userId - 用户 ID
   */
  async function fetchMenus(userId) {
    try {
      const { data: res } = await getUserPermissions(userId)
      if (res.code === 0) {
        menus.value = res.data.menus || []
        permissions.value = res.data.permissions || []
      }
    } catch {
      // 非关键请求，登录响应中的权限已足够使用
    }
  }

  /**
   * 页面刷新后尝试恢复会话。
   * 由路由守卫调用，在跳转登录页之前尝试恢复。
   * @returns {boolean} 是否恢复成功
   */
  async function tryRestoreSession() {
    const token = accessToken.value
    if (!token) return false

    // 已有用户信息 → 仅刷新菜单和权限
    if (user.value) {
      try {
        await fetchMenus(user.value.id)
        return true
      } catch {
        clearState()
        return false
      }
    }

    // 有 Token 但无用户信息 → 从 localStorage 尝试恢复
    const saved = getUserInfo()
    if (!saved || !saved.id) {
      clearState()
      return false
    }

    try {
      // 向后端确认用户仍然存在
      const { data: res } = await getUserDetail(saved.id)
      if (res.code === 0) {
        // 优先用 localStorage 的角色码，否则从 API 返回的对象中提取
        const roles = saved.roles?.length
          ? saved.roles
          : (res.data.roles || []).map(r => typeof r === 'string' ? r : r.role_code)
        user.value = {
          id: saved.id,
          username: saved.username || res.data.username,
          real_name: saved.real_name || res.data.real_name,
          roles,
        }
        await fetchMenus(saved.id)
        return true
      }
    } catch {
      // Token 可能已过期或用户已被删除
    }

    clearState()
    return false
  }

  /**
   * 用户登出：调用 API → 清空本地状态。
   */
  async function logout() {
    try {
      await logoutApi()
    } catch {
      // 即使 API 调用失败也继续清空本地状态
    }
    clearState()
  }

  /**
   * 手动刷新 Access Token。
   */
  async function refresh() {
    const token = refreshToken.value || getRefreshToken()
    if (!token) throw new Error('No refresh token')

    const { data: res } = await refreshTokenApi(token)
    if (res.code !== 0) throw new Error(res.message)

    const { access_token, refresh_token } = res.data
    accessToken.value = access_token
    refreshToken.value = refresh_token
    setAccessToken(access_token)
    setRefreshToken(refresh_token)
  }

  /** 清空所有认证状态和持久化数据。 */
  function clearState() {
    user.value = null
    accessToken.value = null
    refreshToken.value = null
    permissions.value = []
    menus.value = []
    clearAuthData()
    removeUserInfo()
  }

  return {
    user,
    accessToken,
    refreshToken,
    permissions,
    menus,
    isLoggedIn,
    isTokenValid,
    hasPermission,
    login,
    logout,
    refresh,
    fetchMenus,
    tryRestoreSession,
    clearState,
  }
})
