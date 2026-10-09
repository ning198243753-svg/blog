/** 业务实体类型（与后端 schemas 一一对应，文档 05） */

/** 标签（GET /api/tags） */
export interface Tag {
  id: number
  name: string
  slug: string
  color: string | null
  article_count: number
}

/** 文章列表项（GET /api/articles）
 *
 * 刻意**不含正文**：后端 ArticleListItem 与 ArticleDetail 是两个类，
 * 类型层面就禁止列表返回 content_html ——
 * 20KB × 10 条 = 200KB 会直接突破 NFR-14 的首屏 150KB 预算。
 */
export interface ArticleListItem {
  id: number
  title: string
  slug: string
  summary: string | null
  status: string
  view_count: number
  published_at: string | null
  created_at: string
  updated_at: string
  tags: Tag[]
}

/** 相邻文章（上一篇 / 下一篇）
 *
 * prev = 更早发布的一篇，next = 更晚发布的一篇。
 * 没有相邻文章时后端返回 null（不是空对象），前端据此隐藏该侧。
 */
export interface ArticleNeighbor {
  title: string
  slug: string
}

/** 文章详情（GET /api/articles/{slug}）
 *
 * content_md 不在其中：公开接口不返回 Markdown 原文，
 * 只返回渲染后的 content_html（ADR-06）。
 */
export interface ArticleDetail extends ArticleListItem {
  content_html: string
  prev: ArticleNeighbor | null
  next: ArticleNeighbor | null
}

/** 归档分组（GET /api/archive） */
export interface ArchiveGroup {
  year: number
  month: number
  count: number
  articles: ArticleListItem[]
}

/** 站点配置（GET /api/site） */
export interface SiteConfigData {
  values: Record<string, string>
}
