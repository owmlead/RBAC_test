// ──────────────────────────────────────────
// 认证相关 API 模块
// 封装登录、登出、验证码获取、Token 刷新等接口
// ──────────────────────────────────────────

import http from './index'

/**
 * 获取图形验证码（Base64 图片 + captcha_id）。
 */
export function getCaptcha() {
   return http.get('/auth/captcha')
}

/**
 * 使用 Refresh Token 刷新 Access Token。
 * @param {string} refreshToken - 当前的 Refresh Token
 */
export function refreshToken(refreshToken) {
  return http.post('/auth/refresh', null, {
    headers: { Authorization: `Bearer ${refreshToken}` },
  })
}

/**
 * 用户登出，使当前 Token 失效。
 */
export function logout() {
  return http.post('/auth/logout')
}

/**
 * 用户名/密码登录。
 * @param {{ username, password, captchaId?, captcha? }} data - 登录表单数据
 */
export function login(data) {
  return http.post('/auth/login', data)
}

/**
 * 管理员强制下线指定用户（清除权限缓存）。
 * @param {{ user_id: number }} data - 目标用户 ID
 */
export function kickOut(data) {
  return http.post('/auth/kick-out', data)
}

/**
 * 当前用户修改自己的登录密码（需验证旧密码）。
 * 修改成功后所有已登录设备将被踢下线。
 * @param {{ old_password: string, new_password: string }} data - 旧密码和新密码
 */
export function changePassword(data) {
  return http.put('/auth/change-password', data)
}
