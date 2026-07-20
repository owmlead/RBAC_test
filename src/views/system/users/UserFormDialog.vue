<!--
  ──────────────────────────────────────────
  用户表单弹窗组件（新增/编辑）
  打开时自动加载角色列表，编辑模式下回填用户数据，
  提交时调用创建或更新 API。
  ──────────────────────────────────────────
-->

<script setup>
import { ref, reactive, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { createUser, updateUser, getUserDetail } from '@/api/user'
import { getRoles } from '@/api/role'

const props = defineProps({
  visible: { type: Boolean, default: false },
  /** 编辑时传入用户 ID，新增时为 null */
  userId: { type: [Number, String], default: null },
})

const emit = defineEmits(['update:visible', 'saved'])

const isEdit = ref(false)
const loading = ref(false)
const allRoles = ref([])

const formRef = ref()
// 用户表单数据
const form = reactive({
  username: '',
  real_name: '',
  password: '',
  gender: 0,        // 0=未知, 1=男, 2=女
  email: '',
  phone: '',
  status: 1,        // 1=启用, 0=禁用
  role_ids: [],     // 分配的角色 ID 列表
})

// 表单校验规则
const rules = {
  username: [
    { required: true, message: '请输入用户名', trigger: 'blur' },
    { min: 4, max: 20, message: '用户名长度4-20位', trigger: 'blur' },
  ],
  real_name: [{ required: true, message: '请输入真实姓名', trigger: 'blur' }],
  password: [
    { required: true, message: '请输入密码', trigger: 'blur' },
    { min: 8, message: '密码长度至少8位', trigger: 'blur' },
  ],
}

/**
 * 监听弹窗 visible 变化：
 *  - 打开时加载角色列表，编辑模式加载用户详情回填
 *  - 新增模式重置表单
 */
watch(
  () => props.visible,
  async (val) => {
    if (val) {
      isEdit.value = !!props.userId

      // 加载全部角色供分配选择
      try {
        const { data: res } = await getRoles({ page: 1, size: 100 })
        if (res.code === 0 && 'list' in res.data) {
          allRoles.value = res.data.list
        }
      } catch {
        // 非关键操作
      }

      if (props.userId) {
        // 编辑模式：加载用户现有数据回填表单
        try {
          const { data: res } = await getUserDetail(props.userId)
          if (res.code === 0) {
            const u = res.data
            form.username = u.username
            form.real_name = u.real_name
            form.email = u.email || ''
            form.phone = u.phone || ''
            form.gender = u.gender ?? 0
            form.status = u.status
            form.password = '' // 编辑时不回显密码
            form.role_ids = u.roles?.map((r) => r.id) || []
          }
        } catch {
          // 全局拦截器已提示
        }
      } else {
        // 新增模式：重置表单
        form.username = ''
        form.real_name = ''
        form.password = ''
        form.gender = 0
        form.email = ''
        form.phone = ''
        form.status = 1
        form.role_ids = []
      }
    }
  },
)

/**
 * 提交表单：校验通过后调用创建或更新 API。
 */
async function handleSubmit() {
  const valid = await formRef.value?.validate().catch(() => false)
  if (!valid) return

  loading.value = true
  try {
    if (isEdit.value && props.userId) {
      // 编辑模式：仅提交可修改的字段
      const { data: res } = await updateUser(props.userId, {
        real_name: form.real_name,
        email: form.email || undefined,
        phone: form.phone || undefined,
        status: form.status,
      })
      if (res.code === 0) {
        ElMessage.success('用户更新成功')
        emit('saved')
        emit('update:visible', false)
      } else {
        ElMessage.error(res.message)
      }
    } else {
      // 新增模式：提交完整表单
      const { data: res } = await createUser({
        username: form.username,
        real_name: form.real_name,
        password: form.password,
        gender: form.gender,
        email: form.email || undefined,
        phone: form.phone || undefined,
        role_ids: form.role_ids,
      })
      if (res.code === 0) {
        ElMessage.success('用户创建成功')
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
    :title="isEdit ? '编辑用户' : '新增用户'"
    width="560px"
    @close="handleClose"
  >
    <el-form ref="formRef" :model="form" :rules="rules" label-width="100px">
      <el-form-item label="用户名" prop="username">
        <el-input
          v-model="form.username"
          :disabled="isEdit"
          placeholder="4-20位字母数字下划线"
        />
      </el-form-item>
      <el-form-item label="真实姓名" prop="real_name">
        <el-input v-model="form.real_name" placeholder="请输入真实姓名" />
      </el-form-item>
      <el-form-item v-if="!isEdit" label="性别">
        <el-radio-group v-model="form.gender">
          <el-radio :value="0">未知</el-radio>
          <el-radio :value="1">男</el-radio>
          <el-radio :value="2">女</el-radio>
        </el-radio-group>
      </el-form-item>
      <el-form-item v-if="!isEdit" label="密码" prop="password">
        <el-input
          v-model="form.password"
          type="password"
          show-password
          placeholder="至少8位，含字母数字特殊字符至少两种"
        />
      </el-form-item>
      <el-form-item label="邮箱">
        <el-input v-model="form.email" placeholder="请输入邮箱" />
      </el-form-item>
      <el-form-item label="手机号">
        <el-input v-model="form.phone" placeholder="请输入手机号" />
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

    </el-form>
    <template #footer>
      <el-button @click="handleClose">取消</el-button>
      <el-button type="primary" :loading="loading" @click="handleSubmit">
        {{ isEdit ? '保存' : '创建' }}
      </el-button>
    </template>
  </el-dialog>
</template>

<style scoped></style>
