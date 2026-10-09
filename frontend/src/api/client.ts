import axios, { AxiosError } from 'axios'
import type { ApiResponse } from '@/types/api'
import { BizError } from '@/types/api'

/**
 * 全站唯一的 Axios 实例（文档 05 第 6 章）。
 *
 * 组件禁止直接 import axios —— 否则会绕过下面的两个拦截器，
 * 导致 401 处理、错误拆包各写各的。
 *
 * baseURL 用相对路径 /api：开发环境由 Vite 代理转发（vite.config.ts），
 * 生产环境由 Nginx 转发（ADR-04 同源）。代码在两种环境下完全一致。
 */
const client = axios.create({
  baseURL: '/api',
  timeout: 15000,
  withCredentials: true, // ADR-03：会话放在 HttpOnly Cookie 里
})

/** 未登录时的回调，由 router 在初始化时注入，避免 api 层反向依赖 router */
let onUnauthorized: (() => void) | null = null

export function setUnauthorizedHandler(handler: () => void): void {
  onUnauthorized = handler
}

client.interceptors.response.use(
  (response) => {
    const body = response.data as ApiResponse<unknown>

    // 非标准响应（如直接返回文件）不拆包
    if (body === null || typeof body !== 'object' || !('code' in body)) {
      return response.data
    }

    if (body.code !== 0) {
      return Promise.reject(new BizError(body.code, body.message))
    }

    // 直接返回 data：组件里写 const list = await getArticles() 就能拿到数组，
    // 而不是 res.data.data.items。
    // 类型断言是必要的：Axios 的拦截器类型签名固定为返回 AxiosResponse，
    // 而这里刻意改变返回形状。调用方通过 api/*.ts 里的泛型拿到正确类型。
    return body.data as unknown as typeof response
  },
  (error: AxiosError) => {
    const status = error.response?.status
    const body = error.response?.data as ApiResponse<unknown> | undefined

    if (status === 401) {
      onUnauthorized?.()
    }

    // 后端返回了业务响应体时，优先透出它的 message
    if (body && typeof body === 'object' && 'code' in body) {
      return Promise.reject(new BizError(body.code, body.message))
    }

    if (error.code === 'ECONNABORTED') {
      return Promise.reject(new BizError(-1, '请求超时，请检查网络或稍后重试'))
    }

    return Promise.reject(new BizError(-1, error.message || '网络异常'))
  },
)

export default client
