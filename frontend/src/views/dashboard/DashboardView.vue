<!--
  ──────────────────────────────────────────
  仪表盘页面（首页）
  展示系统统计概览（用户/角色/权限/日志总数）
  以及基于权限的快速导航卡片。
  ──────────────────────────────────────────
-->

<script setup>
import { ref, onMounted } from 'vue'
import { useAuthStore } from '@/stores/auth'
import http from '@/api/index'

const authStore = useAuthStore()

const stats = ref({ userCount: 0, roleCount: 0, permCount: 0, logCount: 0 })

onMounted(async () => {
  try {
    const { data: res } = await http.get('/dashboard/stats')
    if (res.code === 0) Object.assign(stats.value, res.data)
  } catch {
    // 非关键数据，静默失败
  }
})
</script>

<template>
  <div>
    <!-- 欢迎语 -->
    <h2 style="margin-bottom: 20px">
      欢迎回来，{{ authStore.user?.real_name || authStore.user?.username }}
    </h2>

    <!-- 统计卡片行 -->
    <div class="stats-row">
      <div class="stat-card" v-if="authStore.hasPermission('user:list')">
        <div class="stat-icon blue"><el-icon size="28"><User /></el-icon></div>
        <div class="stat-info"><h3>{{ stats.userCount }}</h3><p>用户总数</p></div>
      </div>

      <div class="stat-card" v-if="authStore.hasPermission('role:list')">
        <div class="stat-icon green"><el-icon size="28"><UserFilled /></el-icon></div>
        <div class="stat-info"><h3>{{ stats.roleCount }}</h3><p>角色总数</p></div>
      </div>

      <div class="stat-card" v-if="authStore.hasPermission('permission:list')">
        <div class="stat-icon orange"><el-icon size="28"><Lock /></el-icon></div>
        <div class="stat-info"><h3>{{ stats.permCount }}</h3><p>权限资源</p></div>
      </div>

      <div class="stat-card" v-if="authStore.hasPermission('audit:list')">
        <div class="stat-icon purple"><el-icon size="28"><Document /></el-icon></div>
        <div class="stat-info"><h3>{{ stats.logCount }}</h3><p>审计日志</p></div>
      </div>
    </div>

    <!-- 快速导航区域 -->
    <div class="page-card">
      <div class="page-card-header">
        <span class="page-card-title">快速导航</span>
      </div>
      <el-row :gutter="16">
        <!-- 每个卡片根据用户权限显示/隐藏 -->
        <el-col :span="6" v-if="authStore.hasPermission('user:list')">
          <el-card shadow="hover" class="nav-card" @click="$router.push('/system/user')">
            <el-icon size="32" color="#409eff"><User /></el-icon>
            <p>用户管理</p>
          </el-card>
        </el-col>
        <el-col :span="6" v-if="authStore.hasPermission('role:list')">
          <el-card shadow="hover" class="nav-card" @click="$router.push('/system/role')">
            <el-icon size="32" color="#67c23a"><UserFilled /></el-icon>
            <p>角色管理</p>
          </el-card>
        </el-col>
        <el-col :span="6" v-if="authStore.hasPermission('permission:list')">
          <el-card shadow="hover" class="nav-card" @click="$router.push('/system/permission')">
            <el-icon size="32" color="#e6a23c"><Lock /></el-icon>
            <p>权限管理</p>
          </el-card>
        </el-col>
        <el-col :span="6" v-if="authStore.hasPermission('audit:list')">
          <el-card shadow="hover" class="nav-card" @click="$router.push('/audit')">
            <el-icon size="32" color="#9b59b6"><Document /></el-icon>
            <p>审计日志</p>
          </el-card>
        </el-col>
      </el-row>
    </div>
  </div>
</template>

<style scoped>
/* 导航卡片：hover 时轻微上浮 */
.nav-card {
  cursor: pointer;
  text-align: center;
  padding: 20px 0;
}
.nav-card:hover {
  transform: translateY(-2px);
}
.nav-card p {
  margin-top: 12px;
  font-size: 14px;
  color: #606266;
}
</style>
