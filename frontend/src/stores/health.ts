import { defineStore } from 'pinia'
import { ref } from 'vue'
import type { HealthData } from '@/types/api'
import { getHealth } from '@/api/health'

/**
 * 开发期临时 store：仅用于验证前后端连通（M0 任务 0.9）。
 *
 * M1 起会被真实的业务 store 取代（auth / site）。
 * 保留它的理由是：M0 需要一个「看得见」的证据证明链路是通的，
 * 不能只靠「终端没报错」来判断。
 */
export const useHealthStore = defineStore('health', () => {
  const data = ref<HealthData | null>(null)
  const loading = ref(false)
  const error = ref<string | null>(null)

  async function check(): Promise<void> {
    loading.value = true
    error.value = null
    try {
      data.value = await getHealth()
    } catch (e) {
      error.value = e instanceof Error ? e.message : String(e)
      data.value = null
    } finally {
      loading.value = false
    }
  }

  return { data, loading, error, check }
})
