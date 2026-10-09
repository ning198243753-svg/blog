import { defineStore } from 'pinia'
import { computed, ref } from 'vue'

import { getSiteConfig } from '@/api/blog'

/**
 * 站点配置 store（ADR-05 / 文档 06 第 5.1 节）。
 *
 * 【为什么必须进 store，而不是各页面各拉一次】
 * 站点标题、副标题出现在页头（每一页）和首页 hero 里。
 * 各组件自己请求的后果：
 * 1. 每个页面都多一次 /api/site 请求
 * 2. 后台改完配置后，已经在内存里的其他组件不会更新 ——
 *    表现为「改了标题，页头还是旧的，刷新才好」
 *
 * 【为什么用 in-flight 去重而不是简单的 loaded 标记】
 * 页头和首页会**同时**调用 load()（同一帧内）。
 * 只判断 loaded 的话，两个调用都会看到 loaded=false，
 * 于是并发发出两个请求 —— 正好是我们想避免的事。
 * 所以这里缓存的是 Promise 本身：第二个调用直接复用第一个的结果。
 */

/** 后端没返回某个键时用的兜底值 */
const FALLBACK = {
  site_title: 'moon 的学习笔记',
  site_subtitle: '记录 · 整理 · 复现',
  author_name: 'moon',
  author_intro: '',
  footer_text: '',
  icp_number: '',
  github_url: '',
  articles_per_page: '10',
} as const

export type SiteConfigKey = keyof typeof FALLBACK

export const useSiteStore = defineStore('site', () => {
  const values = ref<Record<string, string>>({ ...FALLBACK })
  const loading = ref(false)
  const error = ref('')

  /** 进行中的请求。用途见文件顶部说明 */
  let inflight: Promise<void> | null = null

  /**
   * 以「后端值优先、键缺失则兜底」的方式合并配置。
   *
   * 【为什么不直接用空字符串判断「有没有值」】
   * 空字符串是**合法值**：作者清空「备案号」就是想让它不显示。
   * 如果写成 `value !== ''` 才算有值，清空后前端会退回兜底值 ——
   * 表现为「删掉备案号又冒出来了」，而且刷新也不会好。
   *
   * 正确的判断是「这个键存在吗」，不是「这个值非空吗」。
   */
  function merge(next: Record<string, string>): void {
    const merged: Record<string, string> = { ...FALLBACK }
    for (const key of Object.keys(FALLBACK)) {
      if (Object.prototype.hasOwnProperty.call(next, key)) {
        const value = next[key]
        if (typeof value === 'string') {
          merged[key] = value
        }
      }
    }
    values.value = merged
  }

  async function load(force = false): Promise<void> {
    if (!force && inflight) return inflight
    if (!force && Object.keys(values.value).length && loadedOnce) return

    loading.value = true
    error.value = ''

    inflight = (async () => {
      try {
        const data = await getSiteConfig()
        merge(data.values ?? {})
        loadedOnce = true
      } catch (e) {
        // 站点配置拉取失败不应该让整页白屏 ——
        // 兜底值已经让页面能正常显示，这里只记录错误供调试。
        error.value = e instanceof Error ? e.message : '站点配置加载失败'
      } finally {
        loading.value = false
        inflight = null
      }
    })()

    return inflight
  }

  /** 是否成功加载过一次（用于避免重复请求） */
  let loadedOnce = false

  /** 后台保存配置后调用：强制刷新，让页头立刻反映新标题 */
  async function refresh(): Promise<void> {
    loadedOnce = false
    await load(true)
  }

  const title = computed(() => values.value.site_title)
  const subtitle = computed(() => values.value.site_subtitle)

  return { values, loading, error, title, subtitle, load, refresh }
})
