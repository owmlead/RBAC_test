// ──────────────────────────────────────────
// 工具函数模块
// 提供 localStorage Token/用户信息存取、日期格式化等通用功能。
// ──────────────────────────────────────────

// localStorage 键名常量（防止拼写错误）
const TOKEN_KEY = 'rbac_access_token'
const REFRESH_KEY = 'rbac_refresh_token'
const USER_KEY = 'rbac_user'

/** 移除 Access Token。 */
export function removeAccessToken() {
  localStorage.removeItem(TOKEN_KEY)
}

/** 移除 Refresh Token。 */
export function removeRefreshToken() {
  localStorage.removeItem(REFRESH_KEY)
}

/** 清空所有认证相关持久化数据（Token + 用户信息）。 */
export function clearAuthData() {
  removeAccessToken()
  removeRefreshToken()
  removeUserInfo()
  localStorage.removeItem(USER_KEY)
}

/**
 * 保存用户基本信息到 localStorage。
 * @param {{ id, username, real_name }} info - 用户基本信息对象
 */
export function setUserInfo(info) {
  localStorage.setItem('rbac_user_info', JSON.stringify(info))
}

/**
 * 从 localStorage 读取用户基本信息。
 * @returns {object|null} 用户信息对象或 null
 */
export function getUserInfo() {
  try {
    const raw = localStorage.getItem('rbac_user_info')
    return raw ? JSON.parse(raw) : null
  } catch {
    return null
  }
}

/** 移除 localStorage 中的用户信息。 */
export function removeUserInfo() {
  localStorage.removeItem('rbac_user_info')
}

/**
 * 保存 Refresh Token 到 localStorage。
 * @param {string} token - Refresh Token
 */
export function setRefreshToken(token) {
  localStorage.setItem(REFRESH_KEY, token)
}

/**
 * 保存 Access Token 到 localStorage。
 * @param {string} token - Access Token
 */
export function setAccessToken(token) {
  localStorage.setItem(TOKEN_KEY, token)
}

/**
 * 从 localStorage 读取 Refresh Token。
 * @returns {string|null}
 */
export function getRefreshToken() {
  return localStorage.getItem(REFRESH_KEY)
}

/**
 * 从 localStorage 读取 Access Token。
 * @returns {string|null}
 */
export function getAccessToken() {
  return localStorage.getItem(TOKEN_KEY)
}

/**
 * 将 ISO 时间字符串格式化为 yyyy-MM-dd HH:mm:ss。
 * @param {string} isoStr - ISO 8601 格式时间字符串
 * @returns {string} 格式化后的时间字符串，无效输入返回 '-'
 */
export function formatDateTime(isoStr) {
  if (!isoStr) return '-'
  const d = new Date(isoStr)
  // 检查日期是否有效
  if (isNaN(d.getTime())) return '-'

  // 补零工具函数
  const pad = (n) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}:${pad(d.getSeconds())}`
}
