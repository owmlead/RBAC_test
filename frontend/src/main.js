// ──────────────────────────────────────────
// 应用入口文件
// 初始化 Vue 实例，注册 Pinia、Vue Router、Element Plus
// 并全局注册所有 Element Plus 图标组件
// ──────────────────────────────────────────

import { createApp } from 'vue'
import { createPinia } from 'pinia'

import App from './App.vue'
import router from './router'

// Element Plus UI 框架 + 中文语言包
import ElementPlus from 'element-plus'
import zhCn from 'element-plus/dist/locale/zh-cn.mjs'
import 'element-plus/dist/index.css'

// 创建 Vue 应用实例
const app = createApp(App)

// 注册核心插件
app.use(createPinia())      // 状态管理
app.use(router)              // 路由
app.use(ElementPlus, { locale: zhCn })  // UI 组件库（中文）

// 全局注册所有 Element Plus 图标，模板中可直接按名称使用
import * as ElementPlusIconsVue from '@element-plus/icons-vue'

for (const [key, component] of Object.entries(ElementPlusIconsVue)) {
  app.component(key, component)
}

// 挂载到 #app DOM 节点
app.mount('#app')
