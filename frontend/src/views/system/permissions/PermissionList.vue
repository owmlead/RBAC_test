<!--
  ──────────────────────────────────────────
  权限资源管理页面
  以树形表格展示菜单/按钮权限结构，支持拖拽排序、
  新增子资源、编辑、删除（级联）、导入导出等操作。
  ──────────────────────────────────────────
-->

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { useAuthStore } from '@/stores/auth'
import {
  getPermissionTree,
  createPermission,
  updatePermission,
  deletePermission,
  sortPermissions,
  exportPermissions,
  importPermissions,
} from '@/api/permission'

const authStore = useAuthStore()

// ── 页面状态 ──
const loading = ref(false)
const treeData = ref([])         // 权限树数据
const expandedKeys = ref([])     // 展开的节点 key

// 弹窗状态
const dialogVisible = ref(false)
const editingPermId = ref(null)  // 正在编辑的权限 ID（null = 新增模式）

const formRef = ref()
// 权限表单数据
const form = reactive({
  name: '',
  code: '',
  type: 'MENU',          // MENU 或 BUTTON
  parent_id: null,
  path: '',
  icon: '',
  sort: 0,
  status: 1,
  api_paths: [],         // 按钮类型关联的 API 路径
})

// 导入文件的隐藏 input 引用
const fileInputRef = ref(null)

// ── 数据加载 ──
/** 获取权限树并展开所有节点 */
async function fetchTree() {
  loading.value = true
  try {
    const { data: res } = await getPermissionTree()
    if (res.code === 0) {
      treeData.value = res.data
      // 默认展开全部节点
      expandAll(res.data)
    }
  } catch {
    // 全局拦截器已提示
  } finally {
    loading.value = false
  }
}

/**
 * 递归展开树的所有节点。
 * @param {Array} nodes - 权限树节点数组
 */
function expandAll(nodes) {
  for (const n of nodes) {
    expandedKeys.value.push(n.id)
    if (n.children) expandAll(n.children)
  }
}

// ── 拖拽排序（占位，实际排序通过"保存排序"按钮提交）──
function handleDragStart(_ev, _id) {}
function handleDrop(_ev, _targetId) {}

/**
 * 提交排序：按每层同级分组，同 parent_id 的节点按当前顺序归一化 sort 值。
 */
async function handleSortSubmit() {
  // 分组：{ parent_id: [id1, id2, ...] }
  const groups = {}
  function collectByParent(nodes, parentId) {
    const key = parentId ?? 'root'
    if (!groups[key]) groups[key] = []
    for (const n of nodes) {
      groups[key].push(n.id)
      if (n.children) collectByParent(n.children, n.id)
    }
  }
  collectByParent(treeData.value, null)

  // 按层拼接：先 root 层，再逐个子层
  const sortedIds = []
  for (const key of Object.keys(groups)) {
    sortedIds.push(...groups[key])
  }

  try {
    const { data: res } = await sortPermissions({ sorted_ids: sortedIds })
    if (res.code === 0) {
      ElMessage.success('排序成功')
      await fetchTree()
    } else {
      ElMessage.error(res.message)
    }
  } catch {
    // 全局拦截器已提示
  }
}

// ── CRUD 操作 ──
/** 重置表单到初始状态 */
function resetForm() {
  form.name = ''
  form.code = ''
  form.type = 'MENU'
  form.parent_id = null
  form.path = ''
  form.icon = ''
  form.sort = 0
  form.status = 1
  form.api_paths = []
}

/**
 * 新增权限资源。
 * @param {number|null} parentId - 父节点 ID（null = 根节点）
 */
function handleCreate(parentId = null) {
  editingPermId.value = null
  resetForm()
  form.parent_id = parentId
  dialogVisible.value = true
}

/** 编辑权限资源（回填表单数据） */
function handleEdit(row) {
  editingPermId.value = row.id
  form.name = row.name
  form.code = row.code
  form.type = row.type
  form.parent_id = row.parent_id
  form.path = row.path || ''
  form.icon = row.icon || ''
  form.sort = row.sort
  form.status = row.status ? 1 : 0
  form.api_paths = row.api_paths || []
  dialogVisible.value = true
}

/** 提交权限表单（新增或更新） */
async function handleSubmit() {
  if (!formRef.value) return
  const valid = await formRef.value.validate().catch(() => false)
  if (!valid) return

  try {
    if (editingPermId.value) {
      // 编辑模式
      const { data: res } = await updatePermission(editingPermId.value, {
        name: form.name,
        parent_id: form.parent_id,
        path: form.path || null,
        icon: form.icon || null,
        sort: form.sort,
        status: form.status,
        api_paths: form.api_paths.length > 0 ? form.api_paths : null,
      })
      if (res.code === 0) {
        ElMessage.success('资源更新成功')
        dialogVisible.value = false
        await fetchTree()
      } else {
        ElMessage.error(res.message)
      }
    } else {
      // 新增模式
      const { data: res } = await createPermission({
        name: form.name,
        code: form.code,
        type: form.type,
        parent_id: form.parent_id,
        path: form.path || null,
        icon: form.icon || null,
        sort: form.sort,
        status: form.status,
        api_paths: form.api_paths.length > 0 ? form.api_paths : null,
      })
      if (res.code === 0) {
        ElMessage.success('资源创建成功')
        dialogVisible.value = false
        await fetchTree()
      } else {
        ElMessage.error(res.message)
      }
    }
  } catch {
    // 全局拦截器已提示
  }
}

/**
 * 删除权限资源（级联删除所有子资源）。
 * @param {object} row - 权限节点数据
 */
async function handleDelete(row) {
  try {
    await ElMessageBox.confirm(
      `确定要删除资源 "${row.name}" 吗？删除父资源会级联删除所有子资源。`,
      '确认删除',
      { type: 'warning', confirmButtonText: '确定删除' },
    )
  } catch {
    return // 用户取消
  }
  try {
    const { data: res } = await deletePermission(row.id)
    if (res.code === 0) {
      ElMessage.success('资源已删除')
      await fetchTree()
    } else {
      ElMessage.error(res.message)
    }
  } catch (err) {
    // 全局拦截器已提示
  }
}

// ── 导入导出 ──
/** 导出权限树为 JSON 文件下载 */
async function handleExport() {
  try {
    const { data: res } = await exportPermissions()
    if (res.code === 0) {
      // 构造 Blob 并触发浏览器下载
      const blob = new Blob([JSON.stringify(res.data, null, 2)], { type: 'application/json' })
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `permissions-export-${new Date().toISOString().slice(0, 10)}.json`
      a.click()
      URL.revokeObjectURL(url)
      ElMessage.success('导出成功')
    }
  } catch {
    // 全局拦截器已提示
  }
}

/** 触发隐藏的文件选择器点击 */
function handleImportClick() {
  fileInputRef.value?.click()
}

/**
 * 处理导入文件：读取 JSON → 解析 → 调用导入 API。
 * @param {Event} ev - 文件 input 的 change 事件
 */
async function handleImportFile(ev) {
  const target = ev.target
  const file = target.files?.[0]
  if (!file) return

  try {
    const text = await file.text()
    const data = JSON.parse(text)
    // 兼容多种 JSON 格式：直接数组 / { data: [...] }
    const items = Array.isArray(data) ? data : data.data || data
    const { data: res } = await importPermissions(items)
    if (res.code === 0) {
      ElMessage.success('导入成功')
      await fetchTree()
    } else {
      ElMessage.error(res.message)
    }
    // 重置文件 input 以便重复导入同一文件
    target.value = ''
  } catch {
    // 全局拦截器已提示
  }
}

/**
 * 快捷切换权限启用/禁用状态。
 * @param {object} row - 权限节点数据
 * @param {boolean} val - 新状态
 */
async function handleStatusChange(row, val) {
  try {
    const { data: res } = await updatePermission(row.id, { status: val ? 1 : 0 })
    if (res.code === 0) {
      row.status = val
      ElMessage.success(val ? '已启用' : '已禁用')
    } else {
      ElMessage.error(res.message)
    }
  } catch {
    // 全局拦截器已提示
  }
}

// ── 辅助函数 ──
/**
 * 获取权限类型的 Element Plus Tag 颜色类型。
 * @param {string} type - 'MENU' 或 'BUTTON'
 * @returns {string} Tag 的 type 属性值
 */
function getTypeTag(type) {
  return type === 'MENU' ? 'primary' : 'info'
}

/**
 * 获取权限类型的显示文本。
 * @param {string} type - 'MENU' 或 'BUTTON'
 * @returns {string} 中文标签
 */
function getTypeLabel(type) {
  return type === 'MENU' ? '菜单' : '按钮'
}

// 页面挂载时加载权限树
onMounted(() => {
  fetchTree()
})
</script>

<template>
  <div>
    <div class="page-card">
      <div class="page-card-header">
        <span class="page-card-title">权限资源管理</span>
        <div style="display: flex; gap: 8px">
          <el-button v-if="authStore.hasPermission('permission:list')" @click="handleExport">
            <el-icon><Download /></el-icon>
            导出
          </el-button>
          <el-button v-if="authStore.hasPermission('permission:create')" @click="handleImportClick">
            <el-icon><Upload /></el-icon>
            导入
          </el-button>
          <input
            ref="fileInputRef"
            type="file"
            accept=".json"
            style="display: none"
            @change="handleImportFile"
          />
          <el-button v-if="authStore.hasPermission('permission:update')" @click="handleSortSubmit">
            <el-icon><Sort /></el-icon>
            保存排序
          </el-button>
          <el-button
            v-if="authStore.hasPermission('permission:create')"
            type="primary"
            @click="handleCreate(null)"
          >
            <el-icon><Plus /></el-icon>
            新增根资源
          </el-button>
        </div>
      </div>

      <!-- Tree Table -->
      <el-table :data="treeData" v-loading="loading" row-key="id" border stripe default-expand-all>
        <el-table-column label="资源名称" min-width="240">
          <template #default="{ row }">
            <span
              :draggable="true"
              @dragstart="handleDragStart($event, row.id)"
              @drop="handleDrop($event, row.id)"
              style="cursor: grab"
            >
              <el-icon size="14" class="mr-8"><Rank /></el-icon>
            </span>
            <el-icon v-if="row.type === 'MENU'" size="16" class="mr-8" color="#409eff">
              <Folder />
            </el-icon>
            <el-icon v-else size="16" class="mr-8" color="#909399">
              <Link />
            </el-icon>
            <span>{{ row.name }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="code" label="权限编码" width="180" />
        <el-table-column label="类型" width="80" align="center">
          <template #default="{ row }">
            <el-tag :type="getTypeTag(row.type)" size="small">
              {{ getTypeLabel(row.type) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="path" label="路由" width="150" />
        <el-table-column prop="icon" label="图标" width="100" align="center" />
        <el-table-column prop="sort" label="排序" width="60" align="center" />
        <el-table-column label="状态" width="70" align="center">
          <template #default="{ row }">
            <el-switch :model-value="row.status" size="small" @change="(val) => handleStatusChange(row, val)" />
          </template>
        </el-table-column>
        <el-table-column label="操作" width="220" fixed="right">
          <template #default="{ row }">
            <el-button
              v-if="authStore.hasPermission('permission:create') && row.type === 'MENU'"
              size="small"
              type="success"
              link
              @click="handleCreate(row.id)"
            >
              添加子
            </el-button>
            <el-button
              v-if="authStore.hasPermission('permission:update')"
              size="small"
              type="primary"
              link
              @click="handleEdit(row)"
            >
              编辑
            </el-button>
            <el-button
              v-if="authStore.hasPermission('permission:delete')"
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
    </div>

    <!-- Permission Form Dialog -->
    <el-dialog
      v-model="dialogVisible"
      :title="editingPermId ? '编辑资源' : '新增资源'"
      width="600px"
    >
      <el-form ref="formRef" :model="form" label-width="100px">
        <el-form-item label="资源名称" required>
          <el-input v-model="form.name" placeholder="如：用户管理" />
        </el-form-item>
        <el-form-item v-if="!editingPermId" label="权限编码" required>
          <el-input v-model="form.code" placeholder="如：user:list" />
        </el-form-item>
        <el-form-item label="资源类型" required>
          <el-radio-group v-model="form.type">
            <el-radio value="MENU">菜单</el-radio>
            <el-radio value="BUTTON">按钮</el-radio>
          </el-radio-group>
        </el-form-item>
        <el-form-item v-if="form.type === 'MENU'" label="路由路径">
          <el-input v-model="form.path" placeholder="如：/system/user" />
        </el-form-item>
        <el-form-item v-if="form.type === 'MENU'" label="图标">
          <el-input v-model="form.icon" placeholder="如：user, setting, lock" />
        </el-form-item>
        <el-form-item label="排序号">
          <el-input-number v-model="form.sort" :min="0" />
        </el-form-item>
        <el-form-item label="状态">
          <el-switch
            v-model="form.status"
            :active-value="1"
            :inactive-value="0"
            active-text="启用"
            inactive-text="禁用"
          />
        </el-form-item>
        <el-form-item v-if="form.type === 'BUTTON'" label="API路径">
          <el-select
            v-model="form.api_paths"
            multiple
            filterable
            allow-create
            placeholder="输入API路径后回车添加"
            style="width: 100%"
          >
            <el-option v-for="item in form.api_paths" :key="item" :label="item" :value="item" />
          </el-select>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" @click="handleSubmit">
          {{ editingPermId ? '保存' : '创建' }}
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>
