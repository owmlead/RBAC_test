<!--
  ──────────────────────────────────────────
  404 页面不存在
  用户访问未定义的路由时显示。
  ──────────────────────────────────────────
-->

<script setup>
import { useRouter } from 'vue-router'

const router = useRouter()
</script>

<template>
  <div class="error-page">
    <div class="error-code">404</div>
    <div class="error-message">页面不存在</div>
    <el-button type="primary" @click="router.push('/dashboard')">返回首页</el-button>
  </div>
</template>
