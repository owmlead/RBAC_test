<!--
  ──────────────────────────────────────────
  角色表单弹窗组件（新增/编辑）
  打开时自动加载权限树，编辑模式下回填角色数据及已分配权限，
  提交时构建权限列表并调用创建或更新 API。
  ──────────────────────────────────────────
-->

<script setup>
import { ref, reactive, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { getRoles, createRole, updateRole, getRoleDetail } from '@/api/role'
import { getPermissionTree } from '@/api/permission'
import PermissionTree from '@/components/common/PermissionTree.vue'

const props = defineProps({
  visible: { type: Boolean, default: false },
  /** 编辑时传入角色 ID，新增时为 null */
  roleId: { type: [Number, String], default: null },
})

const emit = defineEmits(['update:visible', 'saved'])

const isEdit = ref(false)
const loading = ref(false)
const allRoles = ref([])                           // 全部角色列表（用于父角色选择）
const permTreeData = ref([])                       // 权限树数据
const checkedPermissions = ref(new Map())          // 已勾选的权限 Map

const formRef = ref()
const form = reactive({
  role_name: '',
  role_code: '',
  description: '',
  parent_role_ids: [],
  status: 1,
})

const rules = {
  role_name: [{ required: true, message: '请输入角色名称', trigger: 'blur' }],
  role_code: [{ required: true, message: '请输入角色编码', trigger: 'blur' }],
}

/**
 * 监听弹窗 visible 变化：
 *  - 打开时加载权限树，编辑模式加载角色详情回填
 *  - 新增模式重置表单
 */
watch(
  () => props.visible,
  async (val) => {
    if (val) {
      isEdit.value = !!props.roleId

      // 加载全部角色（用于父角色选择，排除自身）
      try {
        const { data: r } = await getRoles({ page: 1, size: 100 })
        if (r.code === 0 && r.data?.list) allRoles.value = r.data.list
      } catch {}
      // 加载权限树供分配
      try {
        const { data: res } = await getPermissionTree()
        if (res.code === 0) {
          permTreeData.value = res.data
        }
      } catch {
        // 非关键操作
      }

      if (props.roleId) {
        // 编辑模式：加载角色现有数据回填
        try {
          const { data: res } = await getRoleDetail(props.roleId)
          if (res.code === 0) {
            const role = res.data
            form.role_name = role.role_name
            form.role_code = role.role_code
            form.description = role.description || ''
            form.parent_role_ids = role.parent_role_ids || []
            form.status = role.status ? 1 : 0

            // 将角色现有的权限数据构建为 Map 供 PermissionTree 使用
            const map = new Map()
            function walkPerms(nodes) {
              for (const node of nodes) {
                map.set(node.id, { checked: node.checked, is_deny: node.is_deny })
                if (node.children) walkPerms(node.children)
              }
            }
            walkPerms(role.permissions)
            checkedPermissions.value = map
          }
        } catch {
          // 全局拦截器已提示
        }
      } else {
        // 新增模式：重置表单
        form.role_name = ''
        form.role_code = ''
        form.description = ''
        form.parent_role_ids = []
        form.status = 1
        checkedPermissions.value = new Map()
      }
    }
  },
)

/**
 * 权限树勾选状态变化回调。
 * @param {Map} val - 更新后的勾选 Map
 */
function handlePermissionUpdate(val) {
  checkedPermissions.value = val
}

/**
 * 提交表单：校验通过后构建权限数组，调用创建或更新 API。
 */
async function handleSubmit() {
  const valid = await formRef.value?.validate().catch(() => false)
  if (!valid) return

  // 仅提交已勾选的权限项
  const permissions = []
  checkedPermissions.value.forEach((value, permId) => {
    if (value.checked) {
      permissions.push({ permission_id: permId, is_deny: value.is_deny })
    }
  })

  loading.value = true
  try {
    if (isEdit.value && props.roleId) {
      const { data: res } = await updateRole(props.roleId, {
        role_name: form.role_name,
        description: form.description,
        parent_role_ids: form.parent_role_ids.length > 0 ? form.parent_role_ids : undefined,
        permissions,
        status: !!form.status,
      })
      if (res.code === 0) {
        ElMessage.success('角色更新成功')
        emit('saved')
        emit('update:visible', false)
      } else {
        ElMessage.error(res.message)
      }
    } else {
      const { data: res } = await createRole({
        role_name: form.role_name,
        role_code: form.role_code,
        description: form.description,
        parent_role_ids: form.parent_role_ids.length > 0 ? form.parent_role_ids : undefined,
        permissions,
      })
      if (res.code === 0) {
        ElMessage.success('角色创建成功')
        emit('saved')
        emit('update:visible', false)
      } else {
        ElMessage.error(res.message)
      }
    }
  } catch {
    // 全局拦截器已提示
  } finally {
    loading.value = false
  }
}

/** 关闭弹窗 */
function handleClose() {
  emit('update:visible', false)
}
</script>

<template>
  <el-dialog
    :model-value="visible"
    :title="isEdit ? '编辑角色' : '新增角色'"
    width="800px"
    @close="handleClose"
  >
    <el-form ref="formRef" :model="form" :rules="rules" label-width="100px">
      <el-row :gutter="16">
        <el-col :span="12">
          <el-form-item label="角色名称" prop="role_name">
            <el-input v-model="form.role_name" placeholder="请输入角色名称" />
          </el-form-item>
        </el-col>
        <el-col :span="12">
          <el-form-item label="角色编码" prop="role_code">
            <el-input
              v-model="form.role_code"
              :disabled="isEdit"
              placeholder="大写字母+下划线，如 EDITOR"
            />
          </el-form-item>
        </el-col>
      </el-row>
      <el-form-item label="描述">
        <el-input
          v-model="form.description"
          type="textarea"
          placeholder="角色描述（选填）"
        />
      </el-form-item>
      <el-form-item label="父角色">
        <el-select
          v-model="form.parent_role_ids"
          multiple
          filterable
          placeholder="选择父角色（可选，用于角色继承）"
          style="width: 100%"
        >
          <el-option
            v-for="r in allRoles.filter(r => !isEdit || r.id !== props.roleId)"
            :key="r.id"
            :label="`${r.role_name} (${r.role_code})`"
            :value="r.id"
          />
        </el-select>
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
      <el-form-item label="权限分配">
        <div v-if="permTreeData.length" class="perm-tree-scroll">
          <PermissionTree
            :tree-data="permTreeData"
            :checked-permissions="checkedPermissions"
            @update="handlePermissionUpdate"
          />
        </div>
        <el-empty v-else description="暂无权限资源" :image-size="60" />
      </el-form-item>
    </el-form>
    <template #footer>
      <el-button @click="handleClose">取消</el-button>
      <el-button type="primary" :loading="loading" @click="handleSubmit">
        {{ isEdit ? '保存' : '创建' }}
      </el-button>
    </template>
  </el-dialog>
</template>

<style scoped>
.perm-tree-scroll {
  max-height: 500px;
  overflow-y: auto;
  border: 1px solid #ebeef5;
  border-radius: 4px;
  padding: 8px;
}
</style>

<style scoped></style>
