/**
 * 时间格式化。
 *
 * 为什么要单独一个文件而不是组件里 toLocaleDateString：
 * 后端返回的是带 Z 的 ISO 8601（UTC），必须**先按 UTC 解析再转本地时区**，
 * 否则在中国会整体差 8 小时 —— 10 月 1 日的文章会显示成 9 月 30 日。
 *
 * new Date('2026-10-01T00:00:00Z') 会正确按 UTC 解析，
 * 而 new Date('2026-10-01 00:00:00')（无 Z）会被当作本地时间 ——
 * 这正是后端 schemas 把时间字段声明为 str 而不是 datetime 的原因：
 * Pydantic 序列化 datetime 时不带 Z。
 */

/** 转为「2026-10-01」 */
export function formatDate(iso: string | null | undefined): string {
  if (!iso) return ''
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return ''

  const y = d.getFullYear()
  const m = String(d.getMonth() + 1).padStart(2, '0')
  const day = String(d.getDate()).padStart(2, '0')
  return `${y}-${m}-${day}`
}

/** 转为「10-01」（归档页用，年份已在分组标题上） */
export function formatMonthDay(iso: string | null | undefined): string {
  if (!iso) return ''
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return ''
  const m = String(d.getMonth() + 1).padStart(2, '0')
  const day = String(d.getDate()).padStart(2, '0')
  return `${m}-${day}`
}

/** 转为「2026 年 10 月 1 日」 */
export function formatDateCN(iso: string | null | undefined): string {
  if (!iso) return ''
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return ''
  return `${d.getFullYear()} 年 ${d.getMonth() + 1} 月 ${d.getDate()} 日`
}
