// ──────────────────────────────────────────
// HTTP 请求模块（Axios 实例 + 拦截器）
// 提供统一的请求/响应处理：
//   - 自动附加 Bearer Token
//   - 401 自动刷新 Token 队列机制
//   - 全局 HTTP 状态码错误提示
// ──────────────────────────────────────────

import axios from 'axios'
import { ElMessage } from 'element-plus'
import {
  getAccessToken,
  getRefreshToken,
  setAccessToken,
  setRefreshToken,
  clearAuthData,
  removeUserInfo,
} from '@/utils'

// 创建 Axios 实例，基础 URL 为 /api
const http = axios.create({
  baseURL: '/api',
  timeout: 15000,
  headers: { 'Content-Type': 'application/json' },
})

// ── Token 刷新状态 ──
// 防止多个并发请求同时刷新 Token
let isRefreshing = false
let refreshSubscribers = []

/**
 * 将回调加入等待队列，待 Token 刷新完成后统一执行。
 * @param {Function} cb - 收到新 Token 后的回调
 */
function subscribeTokenRefresh(cb) {
  refreshSubscribers.push(cb)
}

/**
 * Token 刷新成功，通知所有等待中的请求继续执行。
 * @param {string} token - 新的 Access Token
 */
function onTokenRefreshed(token) {
  refreshSubscribers.forEach((cb) => cb(token))
  refreshSubscribers = []
}

// ── 提取后端错误消息 ──
/**
 * 从 Axios 错误对象中提取可读的错误消息。
 * 兼容 FastAPI 422 校验错误和业务异常统一格式。
 * @param {Error} error - Axios 错误对象
 * @returns {string} 可读的错误消息
 */
function extractErrorMessage(error) {
  // FastAPI 422 参数校验错误：提取各字段的 msg 拼接
  if (error.response?.status === 422) {
    const detail = error.response?.data?.detail
    if (Array.isArray(detail) && detail.length > 0) {
      return detail.map((d) => d.msg).join('; ')
    }
  }
  // 业务异常统一格式: { code, message, data }
  return error.response?.data?.message || error.message || '未知错误'
}

// ── 全局错误提示（各 status code） ──
/**
 * 根据 HTTP 状态码显示对应的 Element Plus 消息提示。
 * @param {Error} error - Axios 错误对象
 */
function handleGlobalError(error) {
  const status = error.response?.status
  const msg = extractErrorMessage(error)

  // 401: token 刷新已在下面处理，这里只处理刷新失败的兜底
  if (status === 401 && !error.config?._retry) {
    return // 下面会处理
  }

  switch (status) {
    case 400:
      ElMessage.error(msg || '请求参数错误')
      break
    case 403:
      // 权限不足不弹提示：前端已通过 v-if 隐藏无权限的按钮，
      // 路由守卫已拦截无权限的页面跳转。
      break
    case 404:
      ElMessage.error(msg || '请求的资源不存在')
      break
    case 409:
      ElMessage.warning(msg || '操作冲突，请检查数据')
      break
    case 422:
      ElMessage.error(msg || '参数校验失败')
      break
    case 500:
      ElMessage.error('服务器内部错误，请稍后重试')
      break
    default:
      if (status >= 500) {
        ElMessage.error('服务器异常，请稍后重试')
      }
  }
}

// ── 请求拦截器 ──
// 每个请求自动附加 Authorization 头
http.interceptors.request.use(
  (config) => {
    const token = getAccessToken()
    if (token) {
      config.headers.Authorization = `Bearer ${token}`
    }
    return config
  },
  (error) => Promise.reject(error),
)

// ── 响应拦截器 ──
// 成功：原样返回；失败：统一处理 401 刷新 / 全局错误提示
http.interceptors.response.use(
  (response) => response,
  async (error) => {
    const originalRequest = error.config

    // 登录和刷新接口不自动处理（避免死循环）
    if (
      originalRequest.url.includes('/auth/login') ||
      originalRequest.url.includes('/auth/refresh')
    ) {
      return Promise.reject(error)
    }

    // 401 → 尝试刷新 token
    if (error.response?.status === 401 && !originalRequest._retry) {
      const refreshToken = getRefreshToken()

      // 无 Refresh Token，直接踢出到登录页
      if (!refreshToken) {
        clearAuthData()
        removeUserInfo()
        window.location.href = '/login'
        return Promise.reject(error)
      }

      // 已有刷新请求在进行中，将当前请求加入等待队列
      if (isRefreshing) {
        return new Promise((resolve) => {
          subscribeTokenRefresh((token) => {
            originalRequest.headers.Authorization = `Bearer ${token}`
            originalRequest._retry = true
            resolve(http(originalRequest))
          })
        })
      }

      // 发起 Token 刷新请求
      originalRequest._retry = true
      isRefreshing = true

      try {
        const { data } = await axios.post('/api/auth/refresh', null, {
          headers: { Authorization: `Bearer ${refreshToken}` },
        })
        if (data.code === 0) {
          const { access_token, refresh_token } = data.data
          setAccessToken(access_token)
          setRefreshToken(refresh_token)
          // 通知所有等待中的请求
          onTokenRefreshed(access_token)
          originalRequest.headers.Authorization = `Bearer ${access_token}`
          return http(originalRequest)
        }
      } catch (refreshError) {
        // 刷新失败：清空认证数据，跳转登录页
        clearAuthData()
        removeUserInfo()
        window.location.href = '/login'
        return Promise.reject(refreshError)
      } finally {
        isRefreshing = false
      }
    }

    // 非 401 错误或刷新失败：显示全局错误提示
    handleGlobalError(error)

    return Promise.reject(error)
  },
)

export default http
