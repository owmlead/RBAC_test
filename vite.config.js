import { fileURLToPath, URL } from 'node:url'

import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import vueDevTools from 'vite-plugin-vue-devtools'

// https://vite.dev/config/
export default defineConfig({
  plugins: [
    vue(),
    // vueDevTools(),
  ],
  server: {
    host: '0.0.0.0', // 允许局域网访问
    port: 5173,
    proxy: {
      '/api': {
        target: 'http://localhost:8111',
        changeOrigin: true,
        configure: (proxy, _options) => {
          proxy.on('proxyReq', (proxyReq, req, _res) => {
            // 从 req 中提取访问 Vite 的真实客户端 IP（手机或电脑）
            const realIp = req.socket.remoteAddress?.replace(/^::ffff:/, '') || '127.0.0.1'
            // 手动将真实 IP 写入请求头
            proxyReq.setHeader('X-Forwarded-For', realIp)
            proxyReq.setHeader('X-Real-IP', realIp)
          })
        },
      },
    },
  },
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url)),
    },
  },
})
