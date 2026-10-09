/** 鉴权相关类型（对应文档 05 第 3 章） */

/**
 * 当前登录用户。
 *
 * 【刻意不包含 password_hash】
 * 后端也不会返回它（服务层手工挑字段，不依赖响应模型过滤）。
 * 两边都不带，是为了让「不小心把哈希发到前端」这件事没有发生的路径。
 */
export interface CurrentUser {
  id: number
  username: string
  /** ISO 8601 带 Z 后缀；用 formatDate 解析，不要直接 new Date() */
  created_at: string
}
