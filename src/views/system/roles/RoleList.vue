<!--
  ──────────────────────────────────────────
  角色管理页面
  支持列表视图和树形视图切换，提供角色 CRUD、复制、
  查看/移除关联用户等功能。
  ──────────────────────────────────────────
-->

<script setup>
import { ref, reactive, computed, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { useAuthStore } from '@/stores/auth'
import {
  getRoles,
  createRole,
  updateRole,
  deleteRole,
  copyRole,
  getRoleUsers,
  removeRoleUsers,
} from '@/api/role'
import { formatDateTime } from '@/utils'
import RoleFormDialog from './RoleFormDialog.vue'

const authStore = useAuthStore()

// ── 页面状态 ──
const loading = ref(false)
const viewMode = ref('table')   // 'table' 或 'tree'
const list = ref([])            // 列表视图数据
const treeData = ref([])        // 树形视图数据
const total = ref(0)

const query = reactive({
  page: 1,
  size: 20,
  keyword: '',
})

// 父角色名称映射 {id: role_name}
const allRoleNames = computed(() => {
  const map = {}
  for (const r of list.value) map[r.id] = r.role_name
  return map
})

// 弹窗状态
const roleDialogVisible = ref(false)   // 新增/编辑弹窗
const editingRoleId = ref(null)

const copyDialogVisible = ref(false)   // 复制角色弹窗
const copyRoleId = ref(null)
const copyForm = reactive({ role_name: '', role_code: '' })

const usersDialogVisible = ref(false)  // 查看关联用户弹窗
const usersRoleId = ref(null)
const usersList = ref([])
const usersTotal = ref(0)

// ── 数据加载 ──
/** 分页获取角色列表（列表视图） */
async function fetchTableData() {
  loading.value = true
  try {
    const { data: res } = await getRoles({
      page: query.page,
      size: query.size,
      keyword: query.keyword || undefined,
    })
    if (res.code === 0 && 'list' in res.data) {
      list.value = res.data.list
      total.value = res.data.total
    }
  } catch {
    // 全局拦截器已提示
  } finally {
    loading.value = false
  }
}

/** 获取角色树（树形视图） */
async function fetchTreeData() {
  loading.value = true
  try {
    const { data: res } = await getRoles({ tree: true })
    if (res.code === 0 && Array.isArray(res.data)) {
      treeData.value = res.data
    }
  } catch {
    // 全局拦截器已提示
  } finally {
    loading.value = false
  }
}

/** 搜索（重置到第一页） */
function handleSearch() {
  query.page = 1
  fetchTableData()
}

/** 重置搜索条件 */
function handleReset() {
  query.keyword = ''
  query.page = 1
  fetchTableData()
}

/** 页码变化 */
function handlePageChange(page) {
  query.page = page
  fetchTableData()
}

/** 每页条数变化 */
function handleSizeChange(size) {
  query.size = size
  query.page = 1
  fetchTableData()
}

// ── 视图模式切换 ──
/** 切换列表/树形视图 */
function toggleView() {
  viewMode.value = viewMode.value === 'table' ? 'tree' : 'table'
  if (viewMode.value === 'table') {
    fetchTableData()
  } else {
    fetchTreeData()
  }
}

// ── CRUD 操作 ──
/** 新增角色 */
function handleCreate() {
  editingRoleId.value = null
  roleDialogVisible.value = true
}

/** 编辑角色 */
function handleEdit(row) {
  editingRoleId.value = row.id
  roleDialogVisible.value = true
}

/** 角色表单保存成功回调 */
async function handleRoleSaved() {
  roleDialogVisible.value = false
  if (viewMode.value === 'table') await fetchTableData()
  else await fetchTreeData()
}

/** 删除角色（带确认对话框） */
async function handleDelete(row) {
  try {
    await ElMessageBox.confirm(`确定要删除角色 "${row.role_name}" 吗？`, '确认删除', {
      type: 'warning',
    })
  } catch {
    return // 用户取消
  }
  try {
    const { data: res } = await deleteRole(row.id)
    if (res.code === 0) {
      ElMessage.success('角色已删除')
      if (viewMode.value === 'table') await fetchTableData()
      else await fetchTreeData()
    } else {
      ElMessage.error(res.message)
    }
  } catch (err) {
    // 全局拦截器已提示
  }
}

// ── 复制角色 ──
/** 打开复制角色弹窗（默认名称加"(副本)"后缀） */
function handleCopy(row) {
  copyRoleId.value = row.id
  copyForm.role_name = row.role_name + ' (副本)'
  copyForm.role_code = row.role_code + '_COPY'
  copyDialogVisible.value = true
}

/** 提交复制角色 */
async function handleCopySubmit() {
  if (!copyRoleId.value) return
  try {
    const { data: res } = await copyRole(copyRoleId.value, copyForm)
    if (res.code === 0) {
      ElMessage.success('角色复制成功')
      copyDialogVisible.value = false
      if (viewMode.value === 'table') await fetchTableData()
      else await fetchTreeData()
    } else {
      ElMessage.error(res.message)
    }
  } catch {
    // 全局拦截器已提示
  }
}

// ── 查看角色关联用户 ──
/** 打开关联用户弹窗 */
async function handleViewUsers(row) {
  usersRoleId.value = row.id
  try {
    const { data: res } = await getRoleUsers(row.id, { page: 1, size: 100 })
    if (res.code === 0) {
      usersList.value = res.data.list
      usersTotal.value = res.data.total
    }
  } catch {
    // 全局拦截器已提示
  }
  usersDialogVisible.value = true
}

/** 从角色中移除某个用户 */
async function handleRemoveUser(userId) {
  if (!usersRoleId.value) return
  try {
    await ElMessageBox.confirm('确定要移除该用户吗？', '确认移除', { type: 'warning' })
    const { data: res } = await removeRoleUsers(usersRoleId.value, { user_ids: [userId] })
    if (res.code === 0) {
      ElMessage.success('已移除用户')
      // 从本地列表中移除，避免重新请求
      usersList.value = usersList.value.filter((u) => u.id !== userId)
      usersTotal.value--
    } else {
      ElMessage.error(res.message)
    }
  } catch {
    // 用户取消
  }
}

// 页面挂载时加载列表数据
onMounted(() => {
  fetchTableData()
})
</script>

<template>
  <div>
    <div class="page-card">
      <div class="page-card-header">
        <span class="page-card-title">角色管理</span>
        <div style="display: flex; gap: 8px;">
          <el-button @click="toggleView">
            <el-icon><Sort /></el-icon>
            {{ viewMode === 'table' ? '树形视图' : '列表视图' }}
          </el-button>
          <el-button
            v-if="authStore.hasPermission('role:create')"
            type="primary"
            @click="handleCreate"
          >
            <el-icon><Plus /></el-icon>
            新增角色
          </el-button>
        </div>
      </div>

      <!-- Table View -->
      <template v-if="viewMode === 'table'">
        <div class="search-bar">
          <el-input
            v-model="query.keyword"
            placeholder="角色名称 / 编码"
            clearable
            style="width: 240px"
            @keyup.enter="handleSearch"
          />
          <el-button type="primary" @click="handleSearch">搜索</el-button>
          <el-button @click="handleReset">重置</el-button>
        </div>

        <el-table :data="list" v-loading="loading" border stripe>
          <el-table-column prop="id" label="ID" width="60" />
          <el-table-column prop="role_name" label="角色名称" width="140" />
          <el-table-column prop="role_code" label="角色编码" width="160" />
          <el-table-column label="父角色" width="140">
            <template #default="{ row }">
              {{ (row.parent_role_ids || []).map(id => allRoleNames[id] || id).join(', ') || '-' }}
            </template>
          </el-table-column>
          <el-table-column prop="description" label="描述" min-width="180" />
          <el-table-column label="状态" width="80" align="center">
            <template #default="{ row }">
              <el-tag :type="row.status ? 'success' : 'danger'" size="small">
                {{ row.status ? '启用' : '禁用' }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column label="关联用户" width="90" align="center">
            <template #default="{ row }">
              <el-button size="small" link type="primary" @click="handleViewUsers(row)">
                {{ row.user_count || 0 }} 人
              </el-button>
            </template>
          </el-table-column>
          <el-table-column label="创建时间" width="170">
            <template #default="{ row }">
              {{ formatDateTime(row.create_time) }}
            </template>
          </el-table-column>
          <el-table-column label="操作" width="240" fixed="right">
            <template #default="{ row }">
              <el-button
                v-if="authStore.hasPermission('role:update')"
                size="small"
                type="primary"
                link
                @click="handleEdit(row)"
              >
                编辑
              </el-button>
              <el-button
                v-if="authStore.hasPermission('role:create')"
                size="small"
                type="success"
                link
                @click="handleCopy(row)"
              >
                复制
              </el-button>
              <el-button
                v-if="authStore.hasPermission('role:delete')"
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
      </template>

      <!-- Tree View -->
      <template v-else>
        <el-tree
          :data="treeData"
          node-key="id"
          default-expand-all
          :props="{ label: 'role_name', children: 'children' }"
          v-loading="loading"
        >
          <template #default="{ node, data }">
            <span style="flex: 1; display: flex; align-items: center; gap: 8px;">
              <span>{{ data.role_name }}</span>
              <el-tag size="small" type="info">{{ data.role_code }}</el-tag>
              <span v-if="data.description" class="text-info" style="font-size: 12px;">
                {{ data.description }}
              </span>
            </span>
            <span style="margin-left: auto;">
              <el-button
                v-if="authStore.hasPermission('role:update')"
                size="small"
                link
                type="primary"
                @click="handleEdit(data)"
              >
                编辑
              </el-button>
              <el-button
                v-if="authStore.hasPermission('role:delete')"
                size="small"
                link
                type="danger"
                @click="handleDelete(data)"
              >
                删除
              </el-button>
            </span>
          </template>
        </el-tree>
      </template>
    </div>

    <!-- Role Form Dialog -->
    <RoleFormDialog
      v-model:visible="roleDialogVisible"
      :role-id="editingRoleId"
      @saved="handleRoleSaved"
    />

    <!-- Copy Role Dialog -->
    <el-dialog v-model="copyDialogVisible" title="复制角色" width="450px">
      <el-form :model="copyForm" label-width="100px">
        <el-form-item label="角色名称">
          <el-input v-model="copyForm.role_name" />
        </el-form-item>
        <el-form-item label="角色编码">
          <el-input v-model="copyForm.role_code" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="copyDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="handleCopySubmit">确定复制</el-button>
      </template>
    </el-dialog>

    <!-- View Role Users Dialog -->
    <el-dialog v-model="usersDialogVisible" title="角色关联用户" width="600px">
      <el-table :data="usersList" max-height="400" border stripe>
        <el-table-column prop="id" label="ID" width="60" />
        <el-table-column prop="username" label="用户名" width="120" />
        <el-table-column prop="real_name" label="真实姓名" min-width="120" />
        <el-table-column label="操作" width="100" align="center">
          <template #default="{ row }">
            <el-button
              v-if="authStore.hasPermission('role:assign-user')"
              size="small"
              type="danger"
              link
              @click="handleRemoveUser(row.id)"
            >
              移除
            </el-button>
          </template>
        </el-table-column>
      </el-table>
      <div style="margin-top: 8px; color: #909399; font-size: 12px;">
        共 {{ usersTotal }} 个用户
      </div>
    </el-dialog>
  </div>
</template>
