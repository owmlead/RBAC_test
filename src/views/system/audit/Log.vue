<!--
  ──────────────────────────────────────────
  审计日志页面
  提供日志的分页查询、多条件筛选（操作人/类型/模块/结果/时间范围）、
  导出和详情查看功能。
  ──────────────────────────────────────────
-->

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { useAuthStore } from '@/stores/auth'
import { getLogs } from '@/api/logs'
import { formatDateTime } from '@/utils'

const authStore = useAuthStore()

// ── 页面状态 ──
const loading = ref(false)
const list = ref([])
const total = ref(0)

// 查询条件
const query = reactive({
  page: 1,
  size: 20,
  start_time: '',
  end_time: '',
  username: '',
  operation: '',
  module: '',
  result: '',
})

// 时间范围选择器双向绑定值
const dateRange = ref(null)

// ── 数据加载 ──
/**
 * 分页查询审计日志（根据当前筛选条件）。
 */
async function fetchData() {
  loading.value = true
  try {
    const { data: res } = await getLogs({
      page: query.page,
      size: query.size,
      username: query.username || undefined,
      operation: query.operation || undefined,
      module: query.module || undefined,
      result: query.result || undefined,
      start_time: query.start_time || undefined,
      end_time: query.end_time || undefined,
    })
    if (res.code === 0) {
      list.value = res.data.list
      total.value = res.data.total
    }
  } catch {
    // 全局拦截器已提示
  } finally {
    loading.value = false
  }
}

/** 搜索：从日期范围选择器中提取起止时间，重置到第一页 */
function handleSearch() {
  if (dateRange.value) {
    query.start_time = dateRange.value[0] || ''
    query.end_time = dateRange.value[1] || ''
  } else {
    query.start_time = ''
    query.end_time = ''
  }
  query.page = 1
  fetchData()
}

/** 重置所有筛选条件 */
function handleReset() {
  query.username = ''
  query.operation = ''
  query.module = ''
  query.result = ''
  query.start_time = ''
  query.end_time = ''
  dateRange.value = null
  query.page = 1
  fetchData()
}

/** 页码变化 */
function handlePageChange(page) {
  query.page = page
  fetchData()
}

/** 每页条数变化 */
function handleSizeChange(size) {
  query.size = size
  query.page = 1
  fetchData()
}

// ── 导出 ──
/**
 * 导出当前筛选条件下的日志（最多100条）为 JSON 文件。
 */
async function handleExport() {
  try {
    if (dateRange.value) {
      query.start_time = dateRange.value[0] || ''
      query.end_time = dateRange.value[1] || ''
    }
    // 拉取前100条作为导出数据
    const { data: res } = await getLogs({
      page: 1,
      size: 100,
      username: query.username || undefined,
      operation: query.operation || undefined,
      module: query.module || undefined,
      result: query.result || undefined,
      start_time: query.start_time || undefined,
      end_time: query.end_time || undefined,
    })
    if (res.code === 0) {
      const blob = new Blob([JSON.stringify(res.data.list, null, 2)], { type: 'application/json' })
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `audit-logs-export-${new Date().toISOString().slice(0, 10)}.json`
      a.click()
      URL.revokeObjectURL(url)
      ElMessage.success('导出成功')
    }
  } catch {
    // 全局拦截器已提示
  }
}

// ── Tag 样式辅助 ──
/**
 * 根据操作类型返回 Element Plus Tag 的颜色类型。
 * @param {string} operation - 操作类型枚举值
 * @returns {string} Tag type
 */
function getOperationTag(operation) {
  const map = {
    LOGIN: 'primary',
    LOGOUT: 'info',
    CREATE: 'success',
    UPDATE: 'warning',
    DELETE: 'danger',
    KICK_OUT: 'danger',
  }
  return map[operation] || 'info'
}

/**
 * 根据执行结果返回 Tag 颜色类型。
 * @param {string} result - 'SUCCESS' 或 'FAIL'
 * @returns {string} Tag type
 */
function getResultTag(result) {
  return result === 'SUCCESS' ? 'success' : 'danger'
}

// ── 详情弹窗 ──
const detailVisible = ref(false)
const detailLog = ref(null)

/** 打开审计日志详情弹窗 */
function handleViewDetail(row) {
  detailLog.value = row
  detailVisible.value = true
}

/**
 * 格式化请求参数 JSON 用于详情展示。
 * @param {string} params - JSON 字符串
 * @returns {string} 格式化后的 JSON 字符串或原始值
 */
function formatParams(params) {
  if (!params) return '-'
  try {
    const obj = JSON.parse(params)
    return JSON.stringify(obj, null, 2)
  } catch {
    return params
  }
}

// 页面挂载时加载日志列表
onMounted(() => {
  fetchData()
})
</script>

<template>
  <div>
    <div class="page-card">
      <div class="page-card-header">
        <span class="page-card-title">审计日志</span>
        <div>
          <el-button v-if="authStore.hasPermission('audit:list')" @click="handleExport">
            <el-icon><Download /></el-icon>
            导出日志
          </el-button>
        </div>
      </div>

      <!-- Search Bar -->
      <div class="search-bar">
        <el-input v-model="query.username" placeholder="操作人" clearable style="width: 140px" />
        <el-select v-model="query.operation" placeholder="操作类型" clearable style="width: 120px">
          <el-option label="登录" value="LOGIN" />
          <el-option label="登出" value="LOGOUT" />
          <el-option label="创建" value="CREATE" />
          <el-option label="更新" value="UPDATE" />
          <el-option label="删除" value="DELETE" />
        </el-select>
        <el-select v-model="query.module" placeholder="模块" clearable style="width: 120px">
          <el-option label="认证" value="AUTH" />
          <el-option label="用户" value="USER" />
          <el-option label="角色" value="ROLE" />
          <el-option label="权限" value="PERMISSION" />
        </el-select>
        <el-select v-model="query.result" placeholder="结果" clearable style="width: 100px">
          <el-option label="成功" value="SUCCESS" />
          <el-option label="失败" value="FAIL" />
        </el-select>
        <el-date-picker
          v-model="dateRange"
          type="datetimerange"
          range-separator="至"
          start-placeholder="开始时间"
          end-placeholder="结束时间"
          format="YYYY-MM-DD HH:mm:ss"
          value-format="YYYY-MM-DDTHH:mm:ss"
          style="width: 360px"
        />
        <el-button type="primary" @click="handleSearch">
          <el-icon><Search /></el-icon>
          搜索
        </el-button>
        <el-button @click="handleReset">重置</el-button>
      </div>

      <!-- Table -->
      <el-table :data="list" v-loading="loading" border stripe max-height="calc(100vh - 380px)">
        <el-table-column prop="id" label="ID" width="70" />
        <el-table-column prop="username" label="操作人" width="100" />
        <el-table-column label="操作类型" width="90" align="center">
          <template #default="{ row }">
            <el-tag :type="getOperationTag(row.operation)" size="small">
              {{ row.operation }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="module" label="模块" width="90" align="center" />
        <el-table-column prop="description" label="描述" min-width="220" show-overflow-tooltip />
        <el-table-column prop="ip" label="IP" width="140" />
        <el-table-column label="结果" width="70" align="center">
          <template #default="{ row }">
            <el-tag :type="getResultTag(row.result)" size="small">
              {{ row.result === 'SUCCESS' ? '成功' : '失败' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作时间" width="170">
          <template #default="{ row }">
            {{ formatDateTime(row.create_time) }}
          </template>
        </el-table-column>
        <el-table-column label="详情" width="70" align="center">
          <template #default="{ row }">
            <el-button size="small" link type="primary" @click="handleViewDetail(row)">
              查看
            </el-button>
          </template>
        </el-table-column>
      </el-table>

      <!-- Pagination -->
      <div style="margin-top: 16px; display: flex; justify-content: flex-end">
        <el-pagination
          v-model:current-page="query.page"
          v-model:page-size="query.size"
          :total="total"
          :page-sizes="[10, 20, 50, 100]"
          layout="total, sizes, prev, pager, next, jumper"
          @current-change="handlePageChange"
          @size-change="handleSizeChange"
        />
      </div>
    </div>

    <!-- Detail Dialog -->
    <el-dialog v-model="detailVisible" title="审计日志详情" width="600px">
      <template v-if="detailLog">
        <el-descriptions :column="2" border>
          <el-descriptions-item label="ID">{{ detailLog.id }}</el-descriptions-item>
          <el-descriptions-item label="操作人">{{ detailLog.username }}</el-descriptions-item>
          <el-descriptions-item label="操作类型">
            <el-tag :type="getOperationTag(detailLog.operation)" size="small">
              {{ detailLog.operation }}
            </el-tag>
          </el-descriptions-item>
          <el-descriptions-item label="模块">{{ detailLog.module }}</el-descriptions-item>
          <el-descriptions-item label="描述" :span="2">
            {{ detailLog.description }}
          </el-descriptions-item>
          <el-descriptions-item label="IP">{{ detailLog.ip || '-' }}</el-descriptions-item>
          <el-descriptions-item label="结果">
            <el-tag :type="getResultTag(detailLog.result)" size="small">
              {{ detailLog.result === 'SUCCESS' ? '成功' : '失败' }}
            </el-tag>
          </el-descriptions-item>
          <el-descriptions-item label="操作时间" :span="2">
            {{ formatDateTime(detailLog.create_time) }}
          </el-descriptions-item>
        </el-descriptions>
        <div v-if="detailLog.request_params" style="margin-top: 16px">
          <h4 style="margin-bottom: 8px">请求参数（已脱敏）</h4>
          <pre
            style="
              background: #f5f7fa;
              padding: 12px;
              border-radius: 4px;
              font-size: 12px;
              max-height: 200px;
              overflow: auto;
            "
          >{{ formatParams(detailLog.request_params) }}</pre>
        </div>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped>
.search-bar {
  display: flex;
  gap: 10px;
  margin-bottom: 16px;
  align-items: center;
  flex-wrap: wrap;
}
</style>
