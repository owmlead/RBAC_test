<!--
  ──────────────────────────────────────────
  应用主布局组件（侧边栏 + 顶栏 + 内容区）
  在受保护路由中作为根组件，包裹所有业务页面。
  适配桌面端（可折叠侧边栏）和移动端（抽屉式侧边栏）。
  ──────────────────────────────────────────
-->

<script setup>
import { onUnmounted } from 'vue'
import { useRouter } from 'vue-router'
import { useAppStore } from '@/stores/app'
import SidebarMenu from './SidebarMenu.vue'
import HeaderBar from './HeaderBar.vue'

const router = useRouter()
const appStore = useAppStore()

// 路由切换后自动关闭移动端侧边栏抽屉
const unwatch = router.afterEach(() => {
  appStore.closeMobileDrawer()
})

// 组件卸载时移除路由钩子
onUnmounted(() => {
  unwatch()
})
</script>

<template>
  <div class="app-container">
    <!-- 移动端遮罩层：点击关闭抽屉 -->
    <div
      v-if="appStore.mobileDrawer"
      class="sidebar-overlay"
      @click="appStore.closeMobileDrawer()"
    />
    <!-- 侧边栏：通过 CSS 类切换折叠/展开状态 -->
    <aside
      class="app-sidebar"
      :class="{
        collapsed: appStore.sidebarCollapsed,
        'mobile-open': appStore.mobileDrawer,
      }"
    >
      <!-- 侧边栏 Logo 区域 -->
      <div class="sidebar-logo">
        <el-icon size="22"><Lock /></el-icon>
        <span class="logo-text">RBAC 权限系统</span>
      </div>
      <!-- 动态菜单组件 -->
      <SidebarMenu />
    </aside>
    <!-- 主内容区域 -->
    <div class="app-main">
      <HeaderBar />
      <main class="app-content">
        <!-- 子路由视图 -->
        <router-view />
      </main>
    </div>
  </div>
</template>

<style scoped></style>
