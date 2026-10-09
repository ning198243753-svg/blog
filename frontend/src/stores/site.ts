import { defineStore } from 'pinia'
import { ref } from 'vue'

/**
 * 站点配置 store（ADR-05 / 文档 06 第 5.1 节）。
 * 站点标题等配置跨页面生存且多个组件需要，因此进 store。
 *
 * M0 阶段后端还没有 /api/site，先用占位值；
 * M1 实现该接口后把 load() 里的占位替换为真实请求即可。
 */
export const useSiteStore = defineStore('site', () => {
  const title = ref('moon 的学习笔记')
  const subtitle = ref('记录 · 整理 · 复现')
  const loaded = ref(false)

  async function load(): Promise<void> {
    if (loaded.value) return
    // TODO(M1)：改为 await getSite()，接口见文档 05 第 2.5 节
    loaded.value = true
  }

  return { title, subtitle, loaded, load }
})
