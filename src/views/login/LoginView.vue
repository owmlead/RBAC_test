<!--
  ──────────────────────────────────────────
  登录页面
  提供用户名/密码登录表单，支持验证码（失败3次后显示），
  登录成功后跳转到 redirect 参数指定的页面或仪表盘。
  ──────────────────────────────────────────
-->

<script setup>
import { ref, reactive } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import { getCaptcha } from '@/api/auth'
import { ElMessage } from 'element-plus'

const router = useRouter()
const route = useRoute()
const authStore = useAuthStore()

const loginFormRef = ref()
const loading = ref(false)
const showCaptcha = ref(false)

// 登录表单数据
const form = reactive({
  username: '',
  password: '',
  captcha: '',
})

// 验证码数据：{ captcha_id, captcha_image (Base64) }
const captchaData = ref(null)

// 登录失败计数（达到 3 次后显示验证码）
let failCount = 0

/**
 * 获取图形验证码。
 */
async function fetchCaptcha() {
  try {
    const { data: res } = await getCaptcha()
    if (res.code === 0) {
      captchaData.value = res.data
    }
  } catch {
    // 验证码获取失败，非关键错误
  }
}

/**
 * 提交登录表单。
 * 验证码在 failCount >= 3 时随请求发送。
 */
async function handleLogin() {
  // 前端基础校验
  if (!form.username || !form.password) {
    ElMessage.warning('请输入用户名和密码')
    return
  }

  loading.value = true
  try {
    await authStore.login(
      form.username,
      form.password,
      captchaData.value?.captcha_id,
      form.captcha || undefined,
    )
    ElMessage.success('登录成功')
    failCount = 0

    // 登录成功后跳转到 redirect 参数指定的页面（或默认仪表盘）
    const redirectParam = route.query.redirect
    const redirect = Array.isArray(redirectParam) ? redirectParam[0] : redirectParam
    const target = redirect || '/dashboard'
    await router.push(target)
  } catch (err) {
    failCount++
    const msg = err?.response?.data?.message || err?.message || '登录失败'
    ElMessage.error(msg)

    // 失败 3 次后显示验证码
    if (failCount >= 3) {
      showCaptcha.value = true
      await fetchCaptcha()
    }
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <div class="login-container">
    <div class="login-card">
      <h1 class="login-title">RBAC 权限管理系统</h1>
      <p class="login-subtitle">基于角色的访问控制管理平台</p>

      <!-- 登录表单：回车键触发表单提交 -->
      <el-form ref="loginFormRef" :model="form" size="large" @keyup.enter="handleLogin">
        <el-form-item>
          <el-input v-model="form.username" placeholder="用户名" prefix-icon="User" clearable />
        </el-form-item>

        <el-form-item>
          <el-input
            v-model="form.password"
            type="password"
            placeholder="密码"
            prefix-icon="Lock"
            show-password
            clearable
          />
        </el-form-item>

        <!-- 验证码区域：失败 3 次后显示，点击图片可刷新 -->
        <el-form-item v-if="showCaptcha">
          <div style="display: flex; gap: 12px; width: 100%">
            <el-input v-model="form.captcha" placeholder="验证码" style="flex: 1" />
            <img
              v-if="captchaData"
              :src="captchaData.captcha_image"
              alt="验证码"
              style="height: 40px; cursor: pointer; border-radius: 4px"
              title="点击刷新验证码"
              @click="fetchCaptcha"
            />
          </div>
        </el-form-item>

        <el-form-item>
          <el-button type="primary" :loading="loading" style="width: 100%" @click="handleLogin">
            {{ loading ? '登录中...' : '登 录' }}
          </el-button>
        </el-form-item>
      </el-form>
    </div>
  </div>
</template>
