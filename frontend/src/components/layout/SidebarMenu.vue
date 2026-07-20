<!--
  ──────────────────────────────────────────
  侧边栏菜单组件
  根据用户权限动态渲染菜单树，支持折叠模式。
  图标名称从后端（Ant Design 风格）映射到 Element Plus 图标组件。
  ──────────────────────────────────────────
-->

<script setup>
import { computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import { useAppStore } from '@/stores/app'

const route = useRoute()
const router = useRouter()
const authStore = useAuthStore()
const appStore = useAppStore()

/**
 * 后端图标名 → Element Plus 图标组件名映射表。
 * 后端使用 Ant Design 风格命名（如 SettingOutlined），
 * 前端需要转换为 Element Plus 的图标组件名。
 */
const iconMap = {
  SettingOutlined: 'Setting',
  UserOutlined: 'User',
  TeamOutlined: 'UserFilled',
  LockOutlined: 'Lock',
  HomeFilled: 'HomeFilled',
  FileTextOutlined: 'Document',
  ApartmentOutlined: 'Grid',
  AuditOutlined: 'Document',
  MenuOutlined: 'Menu',
  DashboardOutlined: 'DataAnalysis',
}

/**
 * 根据后端图标名获取对应的 Element Plus 图标组件名。
 * 先精确匹配映射表，再尝试去掉 Outlined/Filled/TwoTone 后缀。
 * @param {string} iconName - 后端返回的图标名称
 * @returns {string} Element Plus 图标组件名
 */
function getIcon(iconName) {
  if (!iconName) return 'Menu'
  // 优先精确匹配映射表
  if (iconMap[iconName]) return iconMap[iconName]
  // 去掉 Ant Design 风格后缀后返回
  const stripped = iconName.replace(/(Outlined|Filled|TwoTone)$/, '')
  return stripped || 'Menu'
}

/**
 * 将后端返回的菜单树转换为 el-menu 所需的配置格式。
 * 仅保留 type === 'MENU' 的节点作为菜单项。
 * @param {Array} menus - 后端菜单树
 * @returns {Array} el-menu 配置数组
 */
function buildMenuConfig(menus) {
  return menus.map((item) => {
    const config = {
      index: item.path || item.code,
      title: item.name,
      icon: item.icon,
    }
    if (item.children && item.children.length > 0) {
      // 过滤出菜单类型的子节点（排除按钮类型）
      const children = item.children.filter((c) => c.type === 'MENU')
      if (children.length > 0) {
        config.children = buildMenuConfig(children)
      }
    }
    return config
  })
}

// 计算属性：转换后的菜单配置
const menuConfigs = computed(() => buildMenuConfig(authStore.menus))

// 当前激活菜单高亮
const activeMenu = computed(() => route.path)

/**
 * 菜单选择回调：以 '/' 开头的作为路由跳转，否则按权限编码映射路由。
 * @param {string} index - 菜单项的 index 值
 */
function handleSelect(index) {
  if (index.startsWith('/')) {
    router.push(index)
  } else {
    // 权限编码 → 路由路径映射
    const routeMap = {
      system: '/dashboard',
      'user:manage': '/system/user',
      'role:manage': '/system/role',
      'permission:manage': '/system/permission',
      'audit:manage': '/audit',
    }
    const path = routeMap[index]
    if (path) router.push(path)
  }
}
</script>

<template>
  <el-menu
    :default-active="activeMenu"
    :collapse="appStore.sidebarCollapsed"
    background-color="#304156"
    text-color="#bfcbd9"
    active-text-color="#409eff"
    @select="handleSelect"
  >
    <!-- 仪表盘菜单项对所有用户可见 -->
    <el-menu-item index="/dashboard">
      <el-icon><HomeFilled/></el-icon>
      <template #title>仪表盘</template>
    </el-menu-item>

    <!-- 根据权限动态渲染菜单 -->
    <template v-for="menu in menuConfigs" :key="menu.index">
      <!-- 有子菜单 → 使用 el-sub-menu 展示二级菜单 -->
      <el-sub-menu v-if="menu.children && menu.children.length > 0" :index="menu.index">
        <template #title>
          <el-icon>
            <component :is="getIcon(menu.icon)" />
          </el-icon>
          <span>{{ menu.title }}</span>
        </template>
        <el-menu-item v-for="child in menu.children" :key="child.index" :index="child.index">
          {{ child.title }}
        </el-menu-item>
      </el-sub-menu>

      <!-- 无子菜单 → 单层菜单项 -->
      <el-menu-item v-else :index="menu.index">
        <el-icon>
          <component :is="getIcon(menu.icon)" />
        </el-icon>
        <template #title>{{ menu.title }}</template>
      </el-menu-item>
    </template>
  </el-menu>
</template>

<style scoped></style>
