import client from '@/api/client'
import type { Paginated } from '@/types/api'
import type {
  ArchiveGroup,
  ArticleDetail,
  ArticleListItem,
  SiteConfigData,
  Tag,
} from '@/types/blog'

/**
 * 公开接口封装（文档 05 第 2 章，共 8 个）。
 *
 * 为什么要有这一层：组件里不出现 URL 字符串。
 * 将来接口路径调整（或加缓存、加防抖）时只改这里一处。
 *
 * 返回类型直接是业务数据 —— client.ts 的拦截器已经拆掉了 {code,message,data} 外壳。
 */

export interface ArticleQuery {
  page?: number
  page_size?: number
  tag?: string
  q?: string
}

export function getArticles(params: ArticleQuery = {}): Promise<Paginated<ArticleListItem>> {
  // 丢掉 undefined / 空字符串，避免拼出 ?tag=&page= 这类无意义参数
  const clean: Record<string, string | number> = {}
  for (const [key, value] of Object.entries(params)) {
    if (value !== undefined && value !== null && value !== '') {
      clean[key] = value
    }
  }
  return client.get('/articles', { params: clean }) as unknown as Promise<
    Paginated<ArticleListItem>
  >
}

export function getArticle(slug: string): Promise<ArticleDetail> {
  // slug 可能是中文（ADR-07：不做拼音转换）。
  // Axios 会自动对 path 做百分号编码，所以这里不需要手动 encodeURIComponent；
  // 手动编码反而会导致双重编码（%25E5%25AD%25A6），后端解出来是乱码。
  return client.get(`/articles/${slug}`) as unknown as Promise<ArticleDetail>
}

export function getTags(): Promise<Tag[]> {
  return client.get('/tags') as unknown as Promise<Tag[]>
}

export function getArticlesByTag(slug: string, page = 1): Promise<Paginated<ArticleListItem>> {
  return client.get(`/tags/${slug}`, { params: { page } }) as unknown as Promise<
    Paginated<ArticleListItem>
  >
}

export function getArchive(): Promise<ArchiveGroup[]> {
  return client.get('/archive') as unknown as Promise<ArchiveGroup[]>
}

export function searchArticles(q: string, page = 1): Promise<Paginated<ArticleListItem>> {
  return client.get('/search', { params: { q, page } }) as unknown as Promise<
    Paginated<ArticleListItem>
  >
}

export function getSiteConfig(): Promise<SiteConfigData> {
  return client.get('/site') as unknown as Promise<SiteConfigData>
}
