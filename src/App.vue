<!--
  ──────────────────────────────────────────
  根组件 App.vue
  使用 Element Plus 的全局配置提供器包裹路由视图，
  统一设置中文语言环境，并引入全局样式。
  ──────────────────────────────────────────
-->

<script setup>
// Element Plus 中文语言包，用于全局组件（日期选择器等）的本地化
import zhCn from 'element-plus/dist/locale/zh-cn.mjs'
</script>

<template>
  <!-- 全局配置：中文语言环境 -->
  <el-config-provider :locale="zhCn">
    <!-- 根据当前路由动态渲染对应页面组件 -->
    <router-view />
  </el-config-provider>
</template>

<style>
/* 引入全局 CSS 变量和基础样式 */
@import '@/assets/styles/global.css';
</style>
