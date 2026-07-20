// ──────────────────────────────────────────
// 权限资源管理 API 模块
// 提供权限树查询、CRUD、排序、导入导出等接口
// ──────────────────────────────────────────

import http from './index'

/**
 * 获取权限树（用于菜单渲染和权限分配界面）。
 * @returns {Promise} 树形权限结构
 */
export function getPermissionTree() {
  return http.get('/permission/tree')
}

/**
 * 创建权限资源（菜单或按钮）。
 * @param {{ name, code, type, parent_id?, path?, icon?, sort? }} data - 权限表单数据
 */
export function createPermission(data) {
  return http.post('/permission/', data)
}

/**
 * 更新权限资源。
 * @param {number|string} id - 权限 ID
 * @param {object} data - 要更新的字段
 */
export function updatePermission(id, data) {
  return http.put(`/permission/${id}`, data)
}

/**
 * 删除权限资源（级联删除子资源）。
 * @param {number|string} id - 权限 ID
 */
export function deletePermission(id) {
  return http.delete(`/permission/${id}`)
}

/**
 * 保存权限排序结果。
 * @param {{ sorted_ids: number[] }} data - 按顺序排列的权限 ID 列表
 */
export function sortPermissions(data) {
  return http.put('/permission/sort', data)
}

/**
 * 导出权限树为 JSON 文件。
 */
export function exportPermissions() {
  return http.get('/permission/export')
}

/**
 * 从 JSON 数据批量导入权限。
 * @param {Array} data - 权限树 JSON 数组
 */
export function importPermissions(data) {
  return http.post('/permission/import', data)
}
