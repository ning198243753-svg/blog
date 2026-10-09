/** 统一响应体（ADR-09 / 文档 05 第 1.2 节） */
export interface ApiResponse<T> {
  code: number
  message: string
  data: T
}

/** 分页数据结构（文档 05 第 1.2 节） */
export interface Paginated<T> {
  items: T[]
  total: number
  page: number
  page_size: number
  pages: number
}

/** 业务错误：code 非 0 时由拦截器抛出 */
export class BizError extends Error {
  code: number

  constructor(code: number, message: string) {
    super(message)
    this.name = 'BizError'
    this.code = code
  }
}

export interface HealthData {
  status: string
  db: string
}
