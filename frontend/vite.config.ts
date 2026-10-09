import { fileURLToPath, URL } from 'node:url'
import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

// ADR-04：前后端同源。开发环境用 Vite 代理把 /api 转发到本机后端，
// 这样开发时的请求路径与生产环境完全一致（生产由 Nginx 转发）。
export default defineConfig({
  plugins: [vue()],
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url)),
    },
  },
  server: {
    port: 5173,
    // 显式绑定 IPv4。
    // Windows 上 Vite 默认只监听 [::1]，而 "localhost" 同时解析出 ::1 与 127.0.0.1；
    // 若某个工具（curl、部分编辑器内置预览）优先用 127.0.0.1 连接，
    // 就会得到 ERR_CONNECTION_REFUSED —— 看起来像「服务没启动」，
    // 其实只是没监听那个地址。绑 127.0.0.1 后两种写法都能连上。
    host: '127.0.0.1',
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true,
      },
      '/uploads': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true,
      },
    },
  },
  build: {
    // NFR-14：首屏体积有硬上限，构建时必须能看到真实体积
    chunkSizeWarningLimit: 150,
  },
})
