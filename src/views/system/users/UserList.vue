<!--
  ──────────────────────────────────────────
  用户管理页面
  提供用户列表展示、搜索过滤、新增/编辑/删除、
  批量启用/禁用/删除、密码重置、角色分配等功能。
  ──────────────────────────────────────────
-->

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { useAuthStore } from '@/stores/auth'
import {
  getUsers,
  getUserDetail,
  createUser,
  updateUser,
  deleteUser,
  batchUpdateStatus,
  batchDeleteUsers,
  resetPassword,
  assignRoles,
} from '@/api/user'
import { kickOut } from '@/api/auth'
import { getRoles } from '@/api/role'
import { formatDateTime } from '@/utils'
import UserFormDialog from './UserFormDialog.vue'

const authStore = useAuthStore()

// ── 页面状态 ──
const loading = ref(false)
const list = ref([])
const total = ref(0)
const selectedIds = ref([])

// 查询条件
const query = reactive({
  page: 1,
  size: 20,
  keyword: '',
  status: undefined,
})

// 弹窗状态
const userDialogVisible = ref(false)       // 新增/编辑弹窗
const editingUserId = ref(null)            // 正在编辑的用户 ID（null = 新增模式）

const passwordDialogVisible = ref(false)   // 密码重置弹窗
const passwordUserId = ref(null)
const passwordForm = reactive({ new_password: '' })

const roleDialogVisible = ref(false)       // 角色分配弹窗
const roleUserId = ref(null)
const roleIds = ref([])                    // 已选角色 ID 列表
const allRoles = ref([])                   // 全部可选角色

// ── 数据加载 ──
/**
 * 分页获取用户列表并刷新表格。
 */
async function fetchData() {
  loading.value = true
  try {
    const { data: res } = await getUsers({
      page: query.page,
      size: query.size,
      keyword: query.keyword || undefined,
      status: query.status,
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

/** 搜索：重置到第一页并查询 */
function handleSearch() {
  query.page = 1
  fetchData()
}

/** 重置搜索条件并重新查询 */
function handleReset() {
  query.keyword = ''
  query.status = undefined
  query.page = 1
  fetchData()
}

/** 页码变化回调 */
function handlePageChange(page) {
  query.page = page
  fetchData()
}

/** 每页条数变化回调 */
function handleSizeChange(size) {
  query.size = size
  query.page = 1
  fetchData()
}

// ── 多选处理 ──
/** 表格多选变化时同步 selectedIds */
function handleSelectionChange(rows) {
  selectedIds.value = rows.map((r) => r.id)
}

// ── CRUD 操作 ──
/** 打开新增用户弹窗 */
function handleCreate() {
  editingUserId.value = null
  userDialogVisible.value = true
}

/** 打开编辑用户弹窗 */
function handleEdit(row) {
  editingUserId.value = row.id
  userDialogVisible.value = true
}

/** 用户表单保存成功后的回调 */
async function handleUserSaved() {
  userDialogVisible.value = false
  await fetchData()
}

/** 删除单个用户（带确认对话框） */
async function handleDelete(row) {
  try {
    await ElMessageBox.confirm(`确定要删除用户 "${row.username}" 吗？`, '确认删除', {
      type: 'warning',
    })
  } catch {
    return // 用户取消
  }
  try {
    const { data: res } = await deleteUser(row.id)
    if (res.code === 0) {
      ElMessage.success('用户已删除')
      await fetchData()
    } else {
      ElMessage.error(res.message)
    }
  } catch {
    // 全局拦截器已提示
  }
}

// ── 批量操作 ──
/** 批量删除已选用户 */
async function handleBatchDelete() {
  if (!selectedIds.value.length) {
    ElMessage.warning('请先选择用户')
    return
  }
  try {
    await ElMessageBox.confirm(
      `确定要批量删除 ${selectedIds.value.length} 个用户吗？`,
      '确认删除',
      { type: 'warning' },
    )
  } catch {
    return // 用户取消
  }
  try {
    const { data: res } = await batchDeleteUsers({ ids: selectedIds.value })
    if (res.code === 0) {
      ElMessage.success('批量删除成功')
      await fetchData()
    } else {
      ElMessage.error(res.message)
    }
  } catch {
    // 全局拦截器已提示
  }
}

/**
 * 批量启用/禁用已选用户。
 * @param {number} status - 1=启用, 0=禁用
 */
async function handleBatchStatus(status) {
  if (!selectedIds.value.length) {
    ElMessage.warning('请先选择用户')
    return
  }
  try {
    const action = status === 1 ? '启用' : '禁用'
    await ElMessageBox.confirm(
      `确定要批量${action} ${selectedIds.value.length} 个用户吗？`,
      `确认${action}`,
      {
        type: 'warning',
      },
    )
    const { data: res } = await batchUpdateStatus({ ids: selectedIds.value, status })
    if (res.code === 0) {
      ElMessage.success(`批量${action}成功`)
      await fetchData()
    } else {
      ElMessage.error(res.message)
    }
  } catch {
    // 用户取消操作
  }
}

// ── 密码重置 ──
/** 打开密码重置弹窗 */
function handleResetPassword(row) {
  passwordUserId.value = row.id
  passwordForm.new_password = ''
  passwordDialogVisible.value = true
}

/** 提交密码重置（至少8位） */
async function handlePasswordSubmit() {
  if (!passwordUserId.value) return
  if (!passwordForm.new_password || passwordForm.new_password.length < 8) {
    ElMessage.warning('密码长度至少8位')
    return
  }
  try {
    const { data: res } = await resetPassword(passwordUserId.value, {
      new_password: passwordForm.new_password,
    })
    if (res.code === 0) {
      ElMessage.success('密码重置成功')
      passwordDialogVisible.value = false
    } else {
      ElMessage.error(res.message)
    }
  } catch {
    // 全局拦截器已提示
  }
}

// ── 踢人下线 ──
/** 管理员强制下线指定用户 */
async function handleKickOut(row) {
  try {
    await ElMessageBox.confirm(
      `确定要强制下线用户 "${row.username}" 吗？`,
      '确认下线',
      { type: 'warning', confirmButtonText: '确定下线' },
    )
  } catch {
    return // 用户取消
  }
  try {
    const { data: res } = await kickOut({ user_id: row.id })
    if (res.code === 0) {
      ElMessage.success('用户已强制下线')
    } else {
      ElMessage.error(res.message)
    }
  } catch {
    // 全局拦截器已提示
  }
}

// ── 角色分配 ──
/** 打开角色分配弹窗（加载全部角色 + 当前用户角色） */
async function handleAssignRole(row) {
  roleUserId.value = row.id
  // 获取全部角色列表（上限100个）
  const { data: rolesRes } = await getRoles({ page: 1, size: 100 })
  if (rolesRes.code === 0 && 'list' in rolesRes.data) {
    allRoles.value = (rolesRes.data ).list
  }
  // 获取用户当前已分配的角色
  const { data: detailRes } = await getUserDetail(row.id)
  if (detailRes.code === 0) {
    roleIds.value = detailRes.data.roles?.map((r) => r.id) || []
  }
  roleDialogVisible.value = true
}

/** 提交角色分配 */
async function handleRoleSubmit() {
  if (!roleUserId.value) return
  try {
    const { data: res } = await assignRoles(roleUserId.value, {
      role_ids: roleIds.value,
    })
    if (res.code === 0) {
      ElMessage.success('角色分配成功')
      roleDialogVisible.value = false
      await fetchData()
    } else {
      ElMessage.error(res.message)
    }
  } catch {
    // 全局拦截器已提示
  }
}

// 页面挂载时加载用户列表
onMounted(() => {
  fetchData()
})
</script>

<template>
  <div>
    <div class="page-card">
      <div class="page-card-header">
        <span class="page-card-title">用户管理</span>
      </div>

      <!-- Search Bar -->
      <div class="search-bar">
        <el-input
          v-model="query.keyword"
          placeholder="用户名 / 姓名 / 邮箱"
          clearable
          style="width: 240px"
          @keyup.enter="handleSearch"
        />
        <el-select v-model="query.status" placeholder="状态" clearable style="width: 120px">
          <el-option label="启用" :value="1" />
          <el-option label="禁用" :value="0" />
        </el-select>
        <el-button type="primary" @click="handleSearch">
          <el-icon><Search /></el-icon>
          搜索
        </el-button>
        <el-button @click="handleReset">重置</el-button>
      </div>

      <!-- Toolbar -->
      <div style="margin-bottom: 12px; display: flex; gap: 8px">
        <el-button
          v-if="authStore.hasPermission('user:create')"
          type="primary"
          @click="handleCreate"
        >
          <el-icon><Plus /></el-icon>
          新增用户
        </el-button>
        <el-button
          v-if="authStore.hasPermission('user:update')"
          :disabled="!selectedIds.length"
          @click="handleBatchStatus(1)"
        >
          批量启用
        </el-button>
        <el-button
          v-if="authStore.hasPermission('user:update')"
          :disabled="!selectedIds.length"
          @click="handleBatchStatus(0)"
        >
          批量禁用
        </el-button>
        <el-button
          v-if="authStore.hasPermission('user:delete')"
          type="danger"
          :disabled="!selectedIds.length"
          @click="handleBatchDelete"
        >
          <el-icon><Delete /></el-icon>
          批量删除
        </el-button>
      </div>

      <!-- Table -->
      <el-table
        :data="list"
        v-loading="loading"
        border
        stripe
        @selection-change="handleSelectionChange"
      >
        <el-table-column type="selection" width="45" />
        <el-table-column prop="id" label="ID" width="60" />
        <el-table-column prop="username" label="用户名" width="120" />
        <el-table-column prop="real_name" label="真实姓名" width="100" />
        <el-table-column prop="email" label="邮箱" min-width="180" />
        <el-table-column prop="phone" label="手机号" width="130" />
        <el-table-column label="状态" width="80" align="center">
          <template #default="{ row }">
            <el-tag :type="row.status ? 'success' : 'danger'" size="small">
              {{ row.status ? '启用' : '禁用' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="最后登录" width="170">
          <template #default="{ row }">
            {{ formatDateTime(row.last_login_time) }}
          </template>
        </el-table-column>
        <el-table-column label="创建时间" width="170">
          <template #default="{ row }">
            {{ formatDateTime(row.create_time) }}
          </template>
        </el-table-column>
        <el-table-column label="操作" width="280" fixed="right">
          <template #default="{ row }">
            <el-button
              v-if="authStore.hasPermission('user:update')"
              size="small"
              type="primary"
              link
              @click="handleEdit(row)"
            >
              编辑
            </el-button>
            <el-button
              v-if="authStore.hasPermission('user:assign-role')"
              size="small"
              type="warning"
              link
              @click="handleAssignRole(row)"
            >
              角色
            </el-button>
            <el-button
              v-if="authStore.hasPermission('user:reset-password')"
              size="small"
              type="info"
              link
              @click="handleResetPassword(row)"
            >
              重置密码
            </el-button>
            <el-button
              v-if="authStore.hasPermission('user:kick')"
              size="small"
              type="danger"
              link
              @click="handleKickOut(row)"
            >
              踢人
            </el-button>
            <el-button
              v-if="authStore.hasPermission('user:delete')"
              size="small"
              type="danger"
              link
              @click="handleDelete(row)"
            >
              删除
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

    <!-- User Form Dialog -->
    <UserFormDialog
      v-model:visible="userDialogVisible"
      :user-id="editingUserId"
      @saved="handleUserSaved"
    />

    <!-- Reset Password Dialog -->
    <el-dialog v-model="passwordDialogVisible" title="重置密码" width="420px">
      <el-form>
        <el-form-item label="新密码">
          <el-input
            v-model="passwordForm.new_password"
            type="password"
            show-password
            placeholder="请输入新密码（至少8位）"
          />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="passwordDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="handlePasswordSubmit">确定</el-button>
      </template>
    </el-dialog>

    <!-- Role Assignment Dialog -->
    <el-dialog v-model="roleDialogVisible" title="分配角色" width="500px">
      <el-checkbox-group v-model="roleIds">
        <el-checkbox v-for="role in allRoles" :key="role.id" :label="role.id" :value="role.id">
          {{ role.role_name }} ({{ role.role_code }})
        </el-checkbox>
      </el-checkbox-group>
      <template #footer>
        <el-button @click="roleDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="handleRoleSubmit">确定</el-button>
      </template>
    </el-dialog>
  </div>
</template>
