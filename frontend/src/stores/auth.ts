import { defineStore } from 'pinia'
import { computed, ref } from 'vue'

import { getCurrentUser, login as loginApi, logout as logoutApi } from '@/api/auth'
import { BizError } from '@/types/api'
import type { CurrentUser } from '@/types/auth'

/**
 * 登录态 store。
 *
 * 【为什么只存用户信息，不存令牌】
 * 会话是 HttpOnly Cookie（ADR-03），JavaScript **读不到它**，
 * 这是刻意的设计：XSS 拿不到会话。
 * 所以前端不管理令牌，只管理「当前用户是谁」这个展示用的信息，
 * 真正的鉴权由浏览器自动带上 Cookie、服务端校验。
 *
 * 【刷新页面后登录态怎么恢复】
 * Pinia 是内存状态，刷新即清空。所以每次应用启动时调一次
 * GET /api/auth/me：Cookie 还在就返回用户信息，不在就 401。
 * 这个请求是必需的 —— 否则刷新后后台页面会闪一下登录页。
 */
export const useAuthStore = defineStore('auth', () => {
  const user = ref<CurrentUser | null>(null)

  /**
   * 是否已经向服务端确认过一次登录态。
   *
   * 【为什么不能只用 user !== null 判断「未登录」】
   * 初始状态下 user 是 null，但它表示「还不知道」，
   * 不表示「未登录」。路由守卫如果直接看 user === null 就跳登录页，
   * 那么刷新后台页面时会**先跳到登录页**，等 /auth/me 返回 200
   * 才发现其实已登录 —— 用户会看到一次明显的闪烁。
   *
   * 所以守卫要先 await ensureLoaded()，再判断 user。
   */
  const resolved = ref(false)

  const isLoggedIn = computed(() => user.value !== null)

  /** 登录中：防止重复提交（按钮禁用 + 请求去重） */
  const loggingIn = ref(false)

  /** 进行中的 /auth/me 请求，用于并发去重（见 site store 的同类处理） */
  let inflight: Promise<void> | null = null

  async function ensureLoaded(force = false): Promise<void> {
    if (resolved.value && !force) return
    if (inflight) return inflight

    inflight = (async () => {
      try {
        user.value = await getCurrentUser()
      } catch {
        // 401 是正常情况（没登录），不需要报错。
        // 其他错误（网络不通）也当作未登录处理：
        // 让用户看到登录页并尝试登录，比卡在一个加载中的页面好。
        user.value = null
      } finally {
        resolved.value = true
        inflight = null
      }
    })()

    return inflight
  }

  async function login(username: string, password: string): Promise<void> {
    loggingIn.value = true
    try {
      user.value = await loginApi(username, password)
      resolved.value = true
    } finally {
      loggingIn.value = false
    }
  }

  async function logout(): Promise<void> {
    try {
      await logoutApi()
    } catch (e) {
      // 登出接口失败也要清掉本地状态：
      // 否则用户点了「退出」却还停在后台页面，会以为没生效。
      // 服务端 Cookie 会在过期后自然失效。
      if (!(e instanceof BizError)) throw e
    } finally {
      user.value = null
      resolved.value = true
    }
  }

  /** 被 401 拦截时调用：清掉本地状态，让守卫把用户送去登录页 */
  function clear(): void {
    user.value = null
    resolved.value = true
  }

  return { user, resolved, isLoggedIn, loggingIn, ensureLoaded, login, logout, clear }
})
