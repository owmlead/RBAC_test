<!--
  ──────────────────────────────────────────
  403 禁止访问页面
  用户尝试访问没有权限的路由时显示。
  ──────────────────────────────────────────
-->

<script setup>
import { useRouter } from 'vue-router'

const router = useRouter()
</script>

<template>
  <div class="error-page">
    <div class="error-code">403</div>
    <div class="error-message">抱歉，您没有权限访问此页面</div>
    <el-button type="primary" @click="router.push('/dashboard')">返回首页</el-button>
  </div>
</template>
