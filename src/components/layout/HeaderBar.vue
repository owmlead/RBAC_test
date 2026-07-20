<!--
  ──────────────────────────────────────────
  顶部导航栏组件
  包含侧边栏折叠按钮（桌面端/移动端）、面包屑导航、用户下拉菜单（角色/登出）。
  响应式适配：桌面端显示折叠切换图标，移动端显示汉堡菜单图标。
  ──────────────────────────────────────────
-->

<script setup>
import { ref, reactive } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import { useAppStore } from '@/stores/app'
import { ElMessage } from 'element-plus'
import { changePassword } from '@/api/auth'

const router = useRouter()
const authStore = useAuthStore()
const appStore = useAppStore()

// ── 修改密码弹窗状态 ──
const passwordDialogVisible = ref(false)
const passwordForm = reactive({
  old_password: '',
  new_password: '',
  confirm_password: '',
})
const passwordLoading = ref(false)

/**
 * 用户登出：调用 Store 清理状态，跳转到登录页。
 */
async function handleLogout() {
  try {
    await authStore.logout()
    ElMessage.success('已退出登录')
    router.push('/login')
  } catch {
    // API 失败时强制清空本地状态
    authStore.clearState()
    router.push('/login')
  }
}

/** 打开修改密码弹窗 */
function openChangePasswordDialog() {
  passwordForm.old_password = ''
  passwordForm.new_password = ''
  passwordForm.confirm_password = ''
  passwordDialogVisible.value = true
}

/** 提交修改密码 */
async function handlePasswordSubmit() {
  if (!passwordForm.old_password) {
    ElMessage.warning('请输入当前密码')
    return
  }
  if (!passwordForm.new_password || passwordForm.new_password.length < 8) {
    ElMessage.warning('新密码长度至少8位')
    return
  }
  if (passwordForm.new_password !== passwordForm.confirm_password) {
    ElMessage.warning('两次输入的新密码不一致')
    return
  }
  passwordLoading.value = true
  try {
    const { data: res } = await changePassword({
      old_password: passwordForm.old_password,
      new_password: passwordForm.new_password,
    })
    if (res.code === 0) {
      ElMessage.success('密码修改成功，请重新登录')
      passwordDialogVisible.value = false
      // 修改密码后所有设备被踢下线，清空状态跳转登录页
      authStore.clearState()
      router.push('/login')
    } else {
      ElMessage.error(res.message)
    }
  } catch {
    // 全局拦截器已提示
  } finally {
    passwordLoading.value = false
  }
}

/**
 * 下拉菜单命令分发。
 * @param {string} command - 菜单项的命令标识
 */
function handleCommand(command) {
  if (command === 'changePassword') {
    openChangePasswordDialog()
  } else if (command === 'logout') {
    handleLogout()
  }
}
</script>

<template>
  <header class="app-header">
    <div class="header-left">
      <!-- 桌面端：侧边栏折叠/展开切换按钮 -->
      <el-icon class="collapse-btn desktop-only" size="20" @click="appStore.toggleSidebar()">
        <Fold v-if="!appStore.sidebarCollapsed" />
        <Expand v-else />
      </el-icon>
      <!-- 移动端：汉堡菜单按钮（打开抽屉） -->
      <el-icon class="collapse-btn mobile-only" size="20" @click="appStore.toggleMobileDrawer()">
        <Menu />
      </el-icon>

      <!-- 面包屑导航 -->
      <el-breadcrumb separator="/" class="header-breadcrumb">
        <el-breadcrumb-item :to="{ path: '/dashboard' }">首页</el-breadcrumb-item>
      </el-breadcrumb>
    </div>

    <div class="header-right">
      <!-- 用户下拉菜单 -->
      <el-dropdown trigger="click" @command="handleCommand">
        <span class="header-user">
          <el-icon size="18"><UserFilled /></el-icon>
          <span class="header-username">{{ authStore.user?.real_name || authStore.user?.username || '用户' }}</span>
          <el-icon size="12"><ArrowDown /></el-icon>
        </span>
        <template #dropdown>
          <el-dropdown-menu>
            <!-- 显示用户角色（禁用态，不可点击） -->
            <el-dropdown-item disabled>
              <span class="text-info">{{ authStore.user?.roles?.join(', ') || '' }}</span>
            </el-dropdown-item>
            <!-- 修改密码 -->
            <el-dropdown-item command="changePassword">
              <el-icon><Lock /></el-icon>
              修改密码
            </el-dropdown-item>
            <!-- 退出登录 -->
            <el-dropdown-item divided command="logout">
              <el-icon><SwitchButton /></el-icon>
              退出登录
            </el-dropdown-item>
          </el-dropdown-menu>
        </template>
      </el-dropdown>
    </div>
  </header>

  <!-- 修改密码弹窗 -->
  <el-dialog v-model="passwordDialogVisible" title="修改密码" width="420px" :close-on-click-modal="false">
    <el-form :model="passwordForm" @submit.prevent="handlePasswordSubmit">
      <el-form-item label="当前密码">
        <el-input
          v-model="passwordForm.old_password"
          type="password"
          show-password
          placeholder="请输入当前密码"
        />
      </el-form-item>
      <el-form-item label="新密码">
        <el-input
          v-model="passwordForm.new_password"
          type="password"
          show-password
          placeholder="请输入新密码（至少8位）"
        />
      </el-form-item>
      <el-form-item label="确认新密码">
        <el-input
          v-model="passwordForm.confirm_password"
          type="password"
          show-password
          placeholder="请再次输入新密码"
          @keyup.enter="handlePasswordSubmit"
        />
      </el-form-item>
    </el-form>
    <template #footer>
      <el-button @click="passwordDialogVisible = false">取消</el-button>
      <el-button type="primary" :loading="passwordLoading" @click="handlePasswordSubmit">确定</el-button>
    </template>
  </el-dialog>
</template>

<style scoped>
/* 折叠按钮基础样式 */
.collapse-btn {
  cursor: pointer;
  color: #606266;
  flex-shrink: 0;
}
.collapse-btn:hover {
  color: var(--primary-color);
}

/* Desktop-only: shown on screens >= 768px */
.desktop-only {
  display: inline-flex;
}
.mobile-only {
  display: none;
}

.header-breadcrumb {
  min-width: 0;
}

/* 用户名过长时省略号显示 */
.header-username {
  max-width: 80px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

/* 移动端适配：隐藏桌面端按钮，显示移动端汉堡菜单，隐藏面包屑 */
@media (max-width: 767px) {
  .desktop-only {
    display: none;
  }
  .mobile-only {
    display: inline-flex;
  }
  .header-breadcrumb {
    display: none;
  }
}
</style>
