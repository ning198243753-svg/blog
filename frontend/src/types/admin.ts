/** 后台接口相关类型（对应文档 05 第 4、5 章） */

import type { ArticleListItem, Tag } from './blog'

/**
 * 后台文章详情（GET /api/admin/articles/{id}）
 *
 * 比公开详情多 content_md —— 编辑器必须拿到 Markdown 原文才能继续修改。
 * 公开接口刻意不返回它：访客用不到，返回只是白白增加体积。
 */
export interface ArticleAdminDetail extends ArticleListItem {
  content_html: string
  content_md: string
}

/** 新建文章请求体（POST /api/admin/articles） */
export interface ArticleCreatePayload {
  title: string
  content_md: string
  /** 留空则由后端按标题自动生成 */
  slug?: string | null
  /** 留空则后端从正文自动提取 */
  summary?: string | null
  status?: 'draft' | 'published'
  tag_ids?: number[]
}

/**
 * 更新文章请求体（PUT /api/admin/articles/{id}）
 *
 * 【只传要改的字段，不要传 undefined 以外的空值】
 * 后端用 model_dump(exclude_unset=True) 实现局部更新：
 * 没传的键保持原值。但**传了 null 和没传是两回事** ——
 * 传 { title: null } 会走到后端的 title 分支并报「标题不能为空」。
 * 所以构造请求体时要真的把不要的键删掉，
 * 而不是填 null 或空字符串。
 *
 * slug 不在这里：文档 05 规定 PUT 保持原 slug 不变，
 * 允许改 slug 会让已发布的链接失效。
 */
export interface ArticleUpdatePayload {
  title?: string
  summary?: string | null
  content_md?: string
  status?: 'draft' | 'published'
  tag_ids?: number[]
}

/** 标签使用情况（GET /api/admin/tags/{id}/usage） */
export interface TagUsage {
  id: number
  name: string
  slug: string
  /** 含草稿 */
  article_count: number
  /** 只含已发布 */
  published_count: number
}

/** 删除标签结果（DELETE /api/admin/tags/{id}?force=true） */
export interface TagDeleteResult {
  deleted_id: number
  affected_articles: number
}

/** 后台标签（GET /api/admin/tags）—— article_count 含草稿 */
export type AdminTag = Tag

/** 图片上传结果（POST /api/admin/upload） */
export interface UploadResult {
  /** 直接放进 <img src> 的路径，形如 /uploads/a3f9c2.webp */
  url: string
  filename: string
  width: number
  height: number
  size: number
  format: string
  /** 以下为原图信息，用于确认压缩真的生效 */
  source_format: string
  source_size: number
  source_width: number
  source_height: number
  /** 多帧图片（GIF 动图）会被保留动画 */
  animated: boolean
  frames: number
}
