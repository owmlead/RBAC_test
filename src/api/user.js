// ──────────────────────────────────────────
// 用户管理 API 模块
// 提供用户 CRUD、批量操作、密码重置、角色分配等功能接口
// ──────────────────────────────────────────

import http from './index'

/**
 * 分页查询用户列表。
 * @param {{ page?, size?, keyword?, status? }} params - 查询参数
 */
export function getUsers(params) {
  return http.get('/user/', { params })
}

/**
 * 获取单个用户详情（含角色、权限信息）。
 * @param {number|string} id - 用户 ID
 */
export function getUserDetail(id) {
  return http.get(`/user/${id}`)
}

/**
 * 创建新用户。
 * @param {{ username, real_name, password, ... }} data - 用户表单数据
 */
export function createUser(data) {
  return http.post('/user/', data)
}

/**
 * 更新用户信息。
 * @param {number|string} id - 用户 ID
 * @param {object} data - 要更新的字段
 */
export function updateUser(id, data) {
  return http.put(`/user/${id}`, data)
}

/**
 * 删除单个用户。
 * @param {number|string} id - 用户 ID
 */
export function deleteUser(id) {
  return http.delete(`/user/${id}`)
}

/**
 * 批量更新用户启用/禁用状态。
 * @param {{ ids: number[], status: number }} data - 用户 ID 列表和目标状态
 */
export function batchUpdateStatus(data) {
  return http.put('/user/batch-status', data)
}

/**
 * 批量删除用户。
 * @param {{ ids: number[] }} data - 用户 ID 列表
 */
export function batchDeleteUsers(data) {
  return http.delete('/user/batch', { data })
}

/**
 * 重置用户密码（管理员操作）。
 * @param {number|string} id - 用户 ID
 * @param {{ new_password: string }} data - 新密码
 */
export function resetPassword(id, data) {
  return http.put(`/user/${id}/reset-password`, data)
}

/**
 * 为用户分配角色。
 * @param {number|string} id - 用户 ID
 * @param {{ role_ids: number[] }} data - 角色 ID 列表
 */
export function assignRoles(id, data) {
  return http.put(`/user/${id}/roles`, data)
}

/**
 * 获取用户的菜单和权限数据（用于动态路由/菜单渲染）。
 * @param {number|string} id - 用户 ID
 */
export function getUserPermissions(id) {
  return http.get(`/user/${id}/permissions`)
}
