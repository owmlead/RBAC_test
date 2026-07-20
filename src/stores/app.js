// ──────────────────────────────────────────
// 应用全局状态 Store（Pinia）
// 管理侧边栏折叠、移动端抽屉等 UI 布局状态。
// ──────────────────────────────────────────

import { defineStore } from 'pinia'
import { ref } from 'vue'

export const useAppStore = defineStore('app', () => {
  // 桌面端侧边栏是否折叠
  const sidebarCollapsed = ref(false)
  // 移动端侧边栏抽屉是否展开
  const mobileDrawer = ref(false)

  /** 切换桌面端侧边栏的折叠状态。 */
  function toggleSidebar() {
    sidebarCollapsed.value = !sidebarCollapsed.value
  }

  /** 打开移动端侧边栏抽屉。 */
  function openMobileDrawer() {
    mobileDrawer.value = true
  }

  /** 关闭移动端侧边栏抽屉。 */
  function closeMobileDrawer() {
    mobileDrawer.value = false
  }

  /** 切换移动端侧边栏抽屉的展开/关闭状态。 */
  function toggleMobileDrawer() {
    mobileDrawer.value = !mobileDrawer.value
  }

  return {
    sidebarCollapsed,
    mobileDrawer,
    toggleSidebar,
    openMobileDrawer,
    closeMobileDrawer,
    toggleMobileDrawer,
  }
})
