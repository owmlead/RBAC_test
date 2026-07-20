// ──────────────────────────────────────────
// 审计日志 API 模块
// 提供日志的分页查询接口（默认仅审计员可访问）
// ──────────────────────────────────────────

import http from './index'

/**
 * 分页查询审计日志。
 * @param {{ page?, size?, username?, operation?, module?, result?, start_time?, end_time? }} params - 筛选条件
 */
export function getLogs(params) {
  return http.get('/logs/', { params })
}
