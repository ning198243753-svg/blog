/** 鉴权接口（文档 05 第 3 章）
 *
 * 三个接口都很短，但都是登录态的入口/出口，值得单独一个文件 ——
 * 混在 blog.ts 里会让「公开接口」与「需要登录的接口」看起来一样。
 */

import client from './client'
import type { CurrentUser } from '@/types/auth'

/** 登录。成功后服务端下发 HttpOnly Cookie，前端拿不到也不需要拿 */
export async function login(username: string, password: string): Promise<CurrentUser> {
  return client.post('/auth/login', { username, password })
}

/** 登出。不需要登录态也能调用（令牌过期时也能退出） */
export async function logout(): Promise<null> {
  return client.post('/auth/logout')
}

/**
 * 获取当前用户。
 *
 * 未登录时后端返回 401，Axios 拦截器会转成 BizError(40100)。
 * 调用方（auth store）把它当作「未登录」而非错误。
 */
export async function getCurrentUser(): Promise<CurrentUser> {
  return client.get('/auth/me')
}
