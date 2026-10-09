/** 后台接口（文档 05 第 4、5 章）
 *
 * 这些接口都需要登录。前端不做额外的登录判断 ——
 * 服务端是唯一的鉴权点，前端拦截 401 即可。
 * 路由守卫只负责「别让用户在未登录时看到后台页面」这一体验问题。
 */

import client from './client'
import type {
  AdminTag,
  ArticleAdminDetail,
  ArticleCreatePayload,
  ArticleUpdatePayload,
  TagDeleteResult,
  TagUsage,
  UploadResult,
} from '@/types/admin'
import type { ArticleListItem, SiteConfigData, Tag } from '@/types/blog'
import type { Paginated } from '@/types/api'

/** 后台文章列表的筛选条件 */
export interface AdminArticleQuery {
  page?: number
  page_size?: number
  /** 不传返回全部（草稿 + 已发布） */
  status?: 'draft' | 'published'
  q?: string
}

/**
 * 后台文章列表（含草稿）。
 *
 * 与公开的 getArticles 的关键差别：
 * - 不传 status 时返回**全部**文章，不只是已发布
 * - 排序按 created_at 倒序（后台关心「最近编辑了什么」，
 *   而草稿没有 published_at）
 */
export async function getAdminArticles(
  query: AdminArticleQuery = {},
): Promise<Paginated<ArticleListItem>> {
  return client.get('/admin/articles', { params: cleanParams(query) })
}

/**
 * 后台文章详情：额外返回 content_md。
 *
 * 按 id 查询而不是 slug：后台处理的是「数据库里的第几行」，
 * 而且草稿也有 slug，用 slug 会让它变成可枚举的。
 */
export async function getAdminArticle(id: number): Promise<ArticleAdminDetail> {
  return client.get(`/admin/articles/${id}`)
}

/** 新建文章，返回新文章 id */
export async function createArticle(payload: ArticleCreatePayload): Promise<{ id: number }> {
  return client.post('/admin/articles', payload)
}

/**
 * 更新文章（局部更新）。
 *
 * 【为什么这里要删掉 undefined 的键】
 * 后端用 model_dump(exclude_unset=True) 判断「哪些字段被传了」。
 * Axios 序列化 JSON 时会丢掉值为 undefined 的键，所以这里其实
 * 只要不传 undefined 就够了 —— 但显式清理能让意图更清楚，
 * 也避免有人后来改成传 null 而引入 bug（传 null 会被当成
 * 「要把它设成空」，与「不改」是两回事）。
 */
export async function updateArticle(
  id: number,
  payload: ArticleUpdatePayload,
): Promise<{ id: number }> {
  return client.put(`/admin/articles/${id}`, cleanParams(payload))
}

/** 删除文章（物理删除，不可恢复） */
export async function deleteArticle(id: number): Promise<null> {
  return client.delete(`/admin/articles/${id}`)
}

// ------------------------------------------------------------------
// 标签
// ------------------------------------------------------------------

/** 后台标签列表：article_count 含草稿（与公开 /tags 的口径不同） */
export async function getAdminTags(): Promise<AdminTag[]> {
  return client.get('/admin/tags')
}

export async function createTag(name: string, color?: string | null): Promise<{ id: number }> {
  return client.post('/admin/tags', cleanParams({ name, color }))
}

export async function updateTag(
  id: number,
  payload: { name?: string; color?: string | null },
): Promise<{ id: number }> {
  return client.put(`/admin/tags/${id}`, cleanParams(payload))
}

/**
 * 查询标签被多少篇文章使用。
 *
 * 前端的删除确认框先调它，好把「会影响 5 篇文章」写具体 ——
 * 一个具体数字比「确定要删除吗」有用得多。
 */
export async function getTagUsage(id: number): Promise<TagUsage> {
  return client.get(`/admin/tags/${id}/usage`)
}

/**
 * 删除标签。
 *
 * 【force 参数不是可选的便利选项】
 * 后端规定：标签还挂在文章上时必须传 force=true，否则返回 409。
 * 所以前端流程是「先查 usage → 弹确认框 → 用户确认后带 force 删」，
 * 而不是「直接带 force 删掉再报告影响」。
 */
export async function deleteTag(id: number, force = false): Promise<TagDeleteResult> {
  return client.delete(`/admin/tags/${id}`, { params: force ? { force: true } : {} })
}

// ------------------------------------------------------------------
// 站点配置
// ------------------------------------------------------------------

export async function getAdminSiteConfig(): Promise<SiteConfigData> {
  return client.get('/admin/site')
}

/**
 * 更新站点配置（只写传了的键）。
 *
 * 未知的键会被后端拒绝（400）而不是静默忽略 ——
 * 那条校验的意义在于：拼错的键会变成「改了配置但页面没变」，
 * 而数据库里确实多了一行，排查时非常困惑。
 */
export async function updateSiteConfig(values: Record<string, string>): Promise<SiteConfigData> {
  return client.put('/admin/site', { values })
}

// ------------------------------------------------------------------
// 图片上传
// ------------------------------------------------------------------

/**
 * 上传图片。
 *
 * 【为什么必须用 FormData 而不能直接 POST 二进制】
 * 后端声明的是 UploadFile = File(...)，FastAPI 要求
 * multipart/form-data 且字段名必须是 file（文档 05 第 4.7 节）。
 *
 * 【为什么让浏览器自己设 Content-Type】
 * multipart 的 Content-Type 里必须带 boundary 参数
 * （形如 multipart/form-data; boundary=----WebKitFormBoundaryXXX）。
 * 手工设置会漏掉 boundary，服务端无法解析。
 * 所以这里**不能**给 axios 传 Content-Type 头 ——
 * 让浏览器从 FormData 里自己读。
 */
export async function uploadImage(file: File): Promise<UploadResult> {
  const form = new FormData()
  form.append('file', file)
  return client.post('/admin/upload', form)
}

// ------------------------------------------------------------------

/**
 * 去掉值为 undefined / null / 空字符串的参数。
 *
 * 【为什么签名用 `T extends object` 而不是 `Record<string, unknown>`】
 * 后者要求类型带字符串索引签名，而 AdminArticleQuery 这类
 * 有明确字段的 interface 没有索引签名，传进去会报
 *   「Index signature for type 'string' is missing」
 * 强迫所有请求类型都加索引签名，等于为了工具的方便
 * 牺牲类型精确性 —— 那样字段名写错就不会被发现了。
 *
 * 用 `T extends object` + Object.entries 即可，
 * 保留调用方的精确类型。
 *
 * 【为什么空字符串也要去掉】
 * 筛选条件为空时，URL 里出现 ?q= 会让后端收到空字符串，
 * 而搜索接口对空关键词返回 422（文档 05 规定「空关键词被拒」）。
 * 去掉它才能表达「不筛选」。
 */
function cleanParams<T extends object>(input: T): Record<string, unknown> {
  const out: Record<string, unknown> = {}
  for (const [key, value] of Object.entries(input)) {
    if (value === undefined || value === null || value === '') continue
    out[key] = value
  }
  return out
}

export type { Tag }
