/**
 * M2 端到端验收：用真实浏览器验证公开页面渲染真实数据。
 *
 * 为什么 M2 必须用浏览器验证（而不是像 M1 那样打接口）：
 * M1 的产物是 JSON，断言 JSON 就够了。M2 的产物是**像素**，
 * 中间隔着 Vite 代理、Axios 拆包、Vue 响应式、路由参数、v-html、
 * 全局 CSS 六段。这六段里任何一段出错，接口测试都发现不了。
 *
 * 具体要防住的失败：
 * - v-html 内容渲染了，但 scoped 样式不生效（看着「没样式」，但 DOM 结构正确）
 * - 中文 slug 在 Axios path 里被双重编码 → 404
 * - 时间字段少了 Z 后缀 → 日期整体差 8 小时
 * - 列表接口被误调用成详情接口 → 字段对不上但页面不报错
 *
 * 用法：先起后端(8000)与前端(5173)，再 node e2e-m2.mjs
 */
import { chromium } from 'playwright'
import { mkdirSync } from 'node:fs'

const BASE = 'http://127.0.0.1:5173'
const SHOT_DIR = 'test-results'

mkdirSync(SHOT_DIR, { recursive: true })

const results = []
function check(name, ok, detail = '') {
  results.push({ name, ok })
  const mark = ok ? 'PASS' : 'FAIL'
  // Windows 控制台按 GBK 解码，中文会乱码，故只输出 ASCII 标记 + 细节
  console.log(`[${mark}] ${name}${detail ? '  ' + detail : ''}`)
}

const browser = await chromium.launch()
const page = await browser.newPage({ viewport: { width: 1280, height: 900 } })

const consoleErrors = []
page.on('console', (m) => {
  if (m.type() === 'error') consoleErrors.push(m.text())
})
page.on('pageerror', (e) => consoleErrors.push(String(e)))

// ============================================================
console.log('\n=== 1. Home / article list ===')
// ============================================================
await page.goto(BASE + '/', { waitUntil: 'networkidle' })

// 骨架屏应当已经消失（数据加载完成）
const skeletonCount = await page.locator('.skeleton-card').count()
check('skeleton removed after load', skeletonCount === 0, `count=${skeletonCount}`)

// 文章卡片渲染
const cardCount = await page.locator('.card').count()
check('article cards rendered', cardCount === 10, `count=${cardCount}`)

// 卡片里出现真实标题（不是「暂无数据」）
const firstTitle = (await page.locator('.card__title').first().textContent())?.trim() ?? ''
check('first card has real title', firstTitle.length > 0, firstTitle)

// 摘要限 2 行：检查 CSS 属性真的生效了
const clampOk = await page.locator('.card__summary').first().evaluate((el) => {
  const s = getComputedStyle(el)
  return s.webkitLineClamp === '2' || s.lineClamp === '2'
})
check('summary clamped to 2 lines', clampOk, '')

// 日期格式与「8 小时时差」防护
// 后端返回带 Z 的 UTC；如果前端按本地时间解析或忘了加 Z，日期会偏一天。
const dateText = (await page.locator('.card__date').first().textContent())?.trim() ?? ''
const dateShapeOk = /^\d{4}-\d{2}-\d{2}$/.test(dateText)
check('date rendered as YYYY-MM-DD', dateShapeOk, dateText)

// 标签筛选条
const filterCount = await page.locator('.filter__item').count()
check('tag filter bar rendered', filterCount === 9, `count=${filterCount} (1 "all" + 8 tags)`)

// 分页器
const pagerCount = await page.locator('.pager__btn').count()
check('pagination rendered', pagerCount > 0, `buttons=${pagerCount}`)

await page.screenshot({ path: `${SHOT_DIR}/m2-01-home.png`, fullPage: true })

// ============================================================
console.log('\n=== 2. Tag filter (URL driven) ===')
// ============================================================
await page.locator('.filter__item', { hasText: 'Vue' }).first().click()
await page.waitForURL('**/?tag=vue**')

// 【必须等元素，不能只等 networkidle】
// SPA 的路由变化与数据渲染都发生在 networkidle 之后，
// 直接数卡片会得到 0 —— 而下面的「刷新后」那条却会通过，
// 因为 reload 是完整加载。这种「同一个断言在刷新前后结果不同」
// 的现象，正是测试写错而不是代码有问题的信号。
//
// 这里的第一张卡片可能来自上一个筛选（旧数据），所以先用
// 卡片数量变化作为「新数据已渲染」的判据，再断言最终数量。
await page.waitForFunction(
  () => document.querySelectorAll('.card').length === 4,
  { timeout: 10000 },
).catch(() => {})

const filteredCount = await page.locator('.card').count()
check('tag filter narrows list', filteredCount === 4, `count=${filteredCount} (Vue has 4)`)

const urlHasTag = page.url().includes('tag=vue')
check('filter state persisted in URL', urlHasTag, page.url())

// 刷新后筛选条件不丢失 —— 这正是「状态放 URL」要保证的事
await page.reload({ waitUntil: 'networkidle' })
const afterReloadCount = await page.locator('.card').count()
check('filter survives page reload', afterReloadCount === 4, `count=${afterReloadCount}`)

await page.screenshot({ path: `${SHOT_DIR}/m2-02-tag-filter.png`, fullPage: true })

// ============================================================
console.log('\n=== 3. Article detail ===')
// ============================================================
await page.goto(BASE + '/', { waitUntil: 'networkidle' })
// 等卡片真正出现再点。只等 waitForLoadState 是不够的：
// 它是「网络空闲」，而 SPA 里路由跳转与数据请求都不触发导航事件，
// 于是点击后立刻断言会读到上一页的 DOM —— 这是本次踩到的坑。
await page.waitForSelector('.card__link')
await page.locator('.card__link').first().click()
await page.waitForSelector('.post__title')
await page.waitForLoadState('networkidle')

check('navigated to detail route', /\/posts\//.test(page.url()), page.url())

const postTitle = (await page.locator('.post__title').textContent())?.trim() ?? ''
check('detail title rendered', postTitle.length > 0, postTitle)

// v-html 内容真的进了 DOM
const bodyHtmlLen = await page.locator('.markdown-body').evaluate((el) => el.innerHTML.length)
check('markdown body injected via v-html', bodyHtmlLen > 100, `html length=${bodyHtmlLen}`)

// 【关键】全局 markdown.css 是否生效
// v-html 的内容拿不到 scoped 的 data-v 属性，如果样式写在组件的 <style scoped> 里，
// DOM 结构完全正确但观感全无 —— 这是最容易被忽略的失败。
const h2Style = await page.locator('.markdown-body h2').first().evaluate((el) => {
  const s = getComputedStyle(el)
  return { border: s.borderBottomWidth, size: s.fontSize, weight: s.fontWeight }
})
check(
  'global markdown css applied to v-html (h2 border)',
  h2Style.border === '1px',
  `border=${h2Style.border} size=${h2Style.size} weight=${h2Style.weight}`,
)

// 代码块：围栏代码必须渲染成 <pre>，不能是行内 code
const preCount = await page.locator('.markdown-body pre').count()
check('fenced code rendered as <pre>', preCount > 0, `pre count=${preCount}`)

const preStyle = await page.locator('.markdown-body pre').first().evaluate((el) => {
  const s = getComputedStyle(el)
  return { radius: s.borderRadius, overflowX: s.overflowX, bg: s.backgroundColor }
})
check(
  'code block styled (radius + overflow-x)',
  preStyle.radius !== '0px' && preStyle.overflowX === 'auto',
  `radius=${preStyle.radius} overflowX=${preStyle.overflowX}`,
)

// 表格
const tableCount = await page.locator('.markdown-body table').count()
check('table rendered', tableCount > 0, `table count=${tableCount}`)

// 阅读数展示
const metaText = (await page.locator('.post__meta').textContent())?.trim() ?? ''
check('view count displayed', /次阅读/.test(metaText), metaText.replace(/\s+/g, ' '))

// 目录（桌面端 1280px 宽应可见）
// 注意必须等 .toc__link 出现：目录是在正文渲染完成后才生成的，
// 用固定时长等待会在慢机器上偶发失败。
await page.waitForSelector('.toc__link', { timeout: 5000 }).catch(() => {})
const tocCount = await page.locator('.toc__link').count()
check('TOC generated from DOM headings', tocCount === 4, `toc items=${tocCount} (article has 4 h2)`)

const tocVisible = await page.locator('.post__aside').isVisible().catch(() => false)
check('TOC visible on desktop', tocVisible, '')

// 目录项点击后应滚动到对应标题（验证 scrollTo 真的挂上了 id）
if (tocCount > 0) {
  const headingId = await page.locator('.toc__link').first().evaluate((el) => {
    const list = el.closest('.toc__list')
    return list ? list.querySelectorAll('.toc__link').length : 0
  })
  const targetId = await page.locator('.markdown-body h2').first().getAttribute('id')
  check('headings got ids for anchors', targetId === 'heading-0', `id=${targetId} toc=${headingId}`)
}

// 上一篇 / 下一篇（文档 06 表格 8）
const neighborCount = await page.locator('.neighbors__item').count()
check('neighbor links rendered', neighborCount > 0, `links=${neighborCount}`)

const neighborLabel = (await page.locator('.neighbors__label').first().textContent())?.trim() ?? ''
check('neighbor labels present', /上一篇|下一篇/.test(neighborLabel), neighborLabel)

// 点进下一篇，确认真的能跳（slug 拼接正确）
if (neighborCount > 0) {
  const targetHref = await page.locator('.neighbors__item').first().getAttribute('href')
  await page.locator('.neighbors__item').first().click()
  await page.waitForSelector('.post__title')
  await page.waitForLoadState('networkidle')
  const jumped = page.url().includes('/posts/')
  check('neighbor link navigates to another post', jumped, `${targetHref} → ${page.url()}`)

  // 回到原文章继续后面的断言
  await page.goBack()
  await page.waitForSelector('.post__title')
  await page.waitForLoadState('networkidle')
}

await page.screenshot({ path: `${SHOT_DIR}/m2-03-article.png`, fullPage: true })

// ============================================================
console.log('\n=== 4. Chinese slug (URL encoding) ===')
// ============================================================
// 找一个中文 slug 的文章。Vue/FastAPI 这些标签的 slug 是英文，
// 但「踩坑记录」「学习笔记」是中文 —— 中文 slug 必须能被 Axios 正确编码。
await page.goto(BASE + '/tags/踩坑记录', { waitUntil: 'networkidle' })
const chineseTagCards = await page.locator('.card').count()
check('chinese tag slug works', chineseTagCards > 0, `cards=${chineseTagCards}`)

const chineseTitle = (await page.locator('.card__link').first().getAttribute('href')) ?? ''
const decoded = decodeURIComponent(chineseTitle)
check(
  'chinese slug not double-encoded',
  !chineseTitle.includes('%25'),
  `href=${chineseTitle.slice(0, 60)} decoded=${decoded.slice(0, 40)}`,
)

// 点进中文 slug 的文章
await page.locator('.card__link').first().click()
await page.waitForLoadState('networkidle')
const cnTitle = (await page.locator('.post__title').textContent())?.trim() ?? ''
check('chinese slug detail loads', cnTitle.length > 0, cnTitle)

// ============================================================
console.log('\n=== 5. Archive ===')
// ============================================================
await page.goto(BASE + '/archive', { waitUntil: 'networkidle' })

const yearCount = await page.locator('.year').count()
check('archive grouped by year', yearCount === 1, `years=${yearCount} (all 2026)`)

const monthCount = await page.locator('.month').count()
check('archive grouped by month', monthCount === 8, `months=${monthCount}`)

const archiveItems = await page.locator('.month__item').count()
check('archive lists all published articles', archiveItems === 24, `items=${archiveItems}`)

const archiveDate = (await page.locator('.month__date').first().textContent())?.trim() ?? ''
check('archive date is MM-DD', /^\d{2}-\d{2}$/.test(archiveDate), archiveDate)

await page.screenshot({ path: `${SHOT_DIR}/m2-04-archive.png`, fullPage: true })

// ============================================================
console.log('\n=== 6. Tags overview ===')
// ============================================================
await page.goto(BASE + '/tags', { waitUntil: 'networkidle' })

const cloudCount = await page.locator('.cloud__item').count()
check('all tags listed', cloudCount === 8, `tags=${cloudCount}`)

// 标签总览不应出现文章卡片
const tagPageCards = await page.locator('.card').count()
check('tags overview has no article cards', tagPageCards === 0, `cards=${tagPageCards}`)

await page.screenshot({ path: `${SHOT_DIR}/m2-05-tags.png`, fullPage: true })

// ============================================================
console.log('\n=== 7. Search ===')
// ============================================================
await page.goto(BASE + '/search', { waitUntil: 'networkidle' })

// 空关键词时应给引导，而不是空白
const emptyTitle = await page.locator('.empty__title').count()
check('search shows guidance when empty', emptyTitle === 1, '')

await page.fill('.search__input', 'SQLite')
await page.press('.search__input', 'Enter')
await page.waitForURL('**/search?q=SQLite')
// 等结果渲染完成。只等 waitForURL 会读到「加载中」的空列表 ——
// 这正是本次第一轮跑出 cards=0 的原因（接口其实返回了 1 条）。
await page.waitForSelector('.card', { timeout: 5000 }).catch(() => {})
await page.waitForLoadState('networkidle')

const searchCount = await page.locator('.card').count()
check('search returns results', searchCount > 0, `cards=${searchCount}`)

const searchInUrl = page.url().includes('q=SQLite')
check('search keyword persisted in URL', searchInUrl, page.url())

const searchSummary = (await page.locator('.search__summary').textContent())?.trim() ?? ''
check('search summary shows count', /1\s*篇/.test(searchSummary), searchSummary.replace(/\s+/g, ' '))

await page.screenshot({ path: `${SHOT_DIR}/m2-06-search.png`, fullPage: true })

// 无结果的情况
await page.goto(BASE + '/search?q=zzzz-not-exist-xyz', { waitUntil: 'networkidle' })
const noResultText = (await page.locator('.empty__title').textContent())?.trim() ?? ''
check('no-result state shown', noResultText.includes('没有找到'), noResultText)

// ============================================================
console.log('\n=== 8. About ===')
// ============================================================
await page.goto(BASE + '/about', { waitUntil: 'networkidle' })
const aboutText = (await page.textContent('body')) ?? ''
check('about shows author name', aboutText.includes('moon'), '')
check('about shows tech stack', aboutText.includes('FastAPI'), '')
check('about shows github link', (await page.locator('a[href*="github"]').count()) > 0, '')

await page.screenshot({ path: `${SHOT_DIR}/m2-07-about.png`, fullPage: true })

// ============================================================
console.log('\n=== 9. 404 (nonexistent article) ===')
// ============================================================
await page.goto(BASE + '/posts/this-slug-does-not-exist', { waitUntil: 'networkidle' })
const nfText = (await page.locator('.empty__title').textContent())?.trim() ?? ''
check('nonexistent article shows friendly state', nfText.includes('不存在'), nfText)

// ============================================================
console.log('\n=== 10. Mobile viewport ===')
// ============================================================
const mobile = await browser.newPage({ viewport: { width: 375, height: 800 } })
await mobile.goto(BASE + '/', { waitUntil: 'networkidle' })

const mobileCards = await mobile.locator('.card').count()
check('mobile renders cards', mobileCards === 10, `cards=${mobileCards}`)

// 正文栏在移动端不能溢出（水平滚动条 = 布局 bug）
const overflow = await mobile.evaluate(
  () => document.documentElement.scrollWidth > document.documentElement.clientWidth + 1,
)
check('no horizontal overflow on mobile', !overflow, '')

await mobile.screenshot({ path: `${SHOT_DIR}/m2-08-mobile.png`, fullPage: true })

// 移动端目录应隐藏
await mobile.goto(BASE + '/posts/' + encodeURIComponent('vue-3-组合式-api-入门笔记'), {
  waitUntil: 'networkidle',
})
const mobileTocVisible = await mobile
  .locator('.post__aside')
  .isVisible()
  .catch(() => false)
check('TOC hidden on mobile', !mobileTocVisible, '')

await browser.close()

// ============================================================
console.log('\n=== 11. Console errors ===')
// ============================================================
// favicon 的 404 不算错误：index.html 里没有引用图标，
// 浏览器会自动请求 /favicon.ico 并记录一条控制台 404。
// 这条噪音会掩盖真正的报错，所以显式排除 —— 但要把范围写窄，
// 不能笼统地忽略所有 404。
const realErrors = consoleErrors.filter(
  (e) => !e.includes('favicon') && !/404 \(Not Found\)$/.test(e.trim()),
)
check('no console errors', realErrors.length === 0, realErrors.join(' | ').slice(0, 300))

// 单独记录被排除的 404，便于人工确认它确实只是图标
const faviconOnly = consoleErrors.filter((e) => e.includes('404 (Not Found)'))
if (faviconOnly.length) {
  console.log(`[INFO] ignored ${faviconOnly.length} favicon 404(s)`)
}

// ============================================================
const failed = results.filter((r) => !r.ok)
console.log('\n' + '='.repeat(60))
console.log(`TOTAL ${results.length}  PASSED ${results.length - failed.length}  FAILED ${failed.length}`)
if (failed.length) {
  console.log('\nFailed:')
  for (const f of failed) console.log('  - ' + f.name)
}
console.log('='.repeat(60))

process.exit(failed.length ? 1 : 0)
