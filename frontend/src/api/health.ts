import client from './client'
import type { HealthData } from '@/types/api'

/**
 * 健康检查（文档 05 第 2.8 节）。
 * 用途是部署验证（SM-04）：确认后端容器已启动且数据库可读。
 *
 * 注意返回类型直接写 HealthData 而不是 AxiosResponse<HealthData>：
 * 因为 client.ts 的响应拦截器已经把 { code, message, data } 拆成了 data。
 */
export function getHealth(): Promise<HealthData> {
  return client.get('/health')
}
