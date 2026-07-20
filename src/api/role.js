// ──────────────────────────────────────────
// 角色管理 API 模块
// 提供角色 CRUD、复制、用户关联等接口
// ──────────────────────────────────────────

import http from './index'

/**
 * 分页查询角色列表（也支持 tree 模式返回树形数据）。
 * @param {{ page?, size?, keyword?, tree? }} params - 查询参数
 */
export function getRoles(params) {
  return http.get('/role/', { params })
}

/**
 * 获取角色详情（含权限列表）。
 * @param {number|string} id - 角色 ID
 */
export function getRoleDetail(id) {
  return http.get(`/role/${id}`)
}

/**
 * 创建新角色。
 * @param {{ role_name, role_code, description?, permissions? }} data - 角色表单数据
 */
export function createRole(data) {
  return http.post('/role/', data)
}

/**
 * 更新角色信息。
 * @param {number|string} id - 角色 ID
 * @param {object} data - 要更新的字段
 */
export function updateRole(id, data) {
  return http.put(`/role/${id}`, data)
}

/**
 * 删除角色。
 * @param {number|string} id - 角色 ID
 */
export function deleteRole(id) {
  return http.delete(`/role/${id}`)
}

/**
 * 复制角色（基于现有角色创建副本）。
 * @param {number|string} id - 源角色 ID
 * @param {{ role_name, role_code }} data - 新角色的名称和编码
 */
export function copyRole(id, data) {
  return http.post(`/role/${id}/copy`, data)
}

/**
 * 查询角色下的用户列表。
 * @param {number|string} id - 角色 ID
 * @param {{ page?, size? }} params - 分页参数
 */
export function getRoleUsers(id, params) {
  return http.get(`/role/${id}/users`, { params })
}

/**
 * 批量移除角色下的用户。
 * @param {number|string} id - 角色 ID
 * @param {{ user_ids: number[] }} data - 待移除的用户 ID 列表
 */
export function removeRoleUsers(id, data) {
  return http.delete(`/role/${id}/users`, { data })
}
