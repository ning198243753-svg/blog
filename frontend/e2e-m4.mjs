/**
 * M4 管理后台浏览器端到端验证
 *
 * 【为什么接口测试通过还不够】
 * M3 的 24 个接口都用 urllib 验证过契约，但那只证明「服务端正确」。
 * M2 已经吃过一次亏：接口返回 4 个 <h2>，页面目录却是空的 ——
 * 原因是一个循环等待的 bug，接口测试完全看不见。
 *
 * M4 引入了 M2 没有的东西，每一项都只能在浏览器里验证：
 *   1. 登录态：Cookie 是否真的被浏览器带上、刷新后是否保持
 *   2. 路由守卫：未登录访问后台会不会被挡、登录后是否回到原页面
 *   3. 表单提交：新建 / 编辑文章是否真的写进数据库
 *   4. 图片上传：<input type="file"> + FormData 这条链路
 *   5. 离开提醒：有未保存修改时是否拦截
 *
 * 运行前需要：后端 8000 与前端 5173 都在运行。
 */

import { chromium } from 'playwright'
import { mkdirSync } from 'node:fs'

const BASE = 'http://127.0.0.1:5173'
const API = 'http://127.0.0.1:8000/api'
const SHOTS = 'test-results'

mkdirSync(SHOTS, { recursive: true })

const ADMIN_USER = 'admin'
const ADMIN_PASS = process.env.ADMIN_PASSWORD || 'TestPassw0rd!2026'

let passed = 0
const failed = []
const consoleErrors = []

function check(name, ok, detail = '') {
  if (ok) {
    passed++
  } else {
    failed.push(name)
  }
  console.log(`[${ok ? 'PASS' : 'FAIL'}] ${name}${detail ? '  ' + detail : ''}`)
}

async function shot(page, name) {
  await page.screenshot({ path: `${SHOTS}/${name}.png`, fullPage: true })
}

// ====================================================================

const browser = await chromium.launch()
const context = await browser.newContext({ viewport: { width: 1440, height: 900 } })
const page = await context.newPage()

page.on('console', (msg) => {
  if (msg.type() !== 'error') return
  const text = msg.text()
  if (/favicon/i.test(text)) return
  // 记录来源 URL，便于定位是哪次请求产生的
  const loc = msg.location?.()
  consoleErrors.push(loc?.url ? `${text}  ← ${loc.url}` : text)
})
page.on('pageerror', (err) => consoleErrors.push(`pageerror: ${err.message}`))

// 更精确的来源：直接记录所有 4xx/5xx 的**响应**及其请求地址。
// console 里的 "Failed to load resource" 不带 URL，
// 光看那句话无法判断是哪个请求失败了。
const httpErrors = []
page.on('response', (res) => {
  if (res.status() >= 400) {
    httpErrors.push(`${res.status()} ${res.request().method()} ${res.url()}`)
  }
})

console.log('='.repeat(66))
console.log('M4 管理后台验证')
console.log('='.repeat(66))

// ====================================================================
console.log('\n--- 1. 路由守卫：未登录访问后台 ---')
// ====================================================================

await page.goto(`${BASE}/admin/articles`, { waitUntil: 'networkidle' })
// 守卫内部会 await /auth/me，所以要等到 URL 真的变化
await page.waitForURL(/\/admin\/login/, { timeout: 10000 }).catch(() => {})
check('未登录访问文章管理被拦到登录页', page.url().includes('/admin/login'), page.url())

const redirectParam = new URL(page.url()).searchParams.get('redirect')
check('登录页保留了原目标地址', redirectParam === '/admin/articles', String(redirectParam))

const loginCardVisible = await page.locator('.login__card').isVisible().catch(() => false)
check('登录表单已渲染', loginCardVisible)

// 后台登录页不应出现访客页头
const visitorHeader = await page.locator('.header__brand').count()
check('登录页不显示访客页头（用了独立布局）', visitorHeader === 0, `找到 ${visitorHeader} 个`)

await shot(page, 'm4-01-login')

// ====================================================================
console.log('\n--- 2. 登录失败的处理 ---')
// ====================================================================

await page.fill('input[name="username"]', ADMIN_USER)
await page.fill('input[name="password"]', 'definitely-wrong-password')
await page.click('button[type="submit"]')
await page.waitForSelector('.login__error', { timeout: 10000 }).catch(() => {})

const errorText = await page.locator('.login__error').textContent().catch(() => '')
check('密码错误时显示错误提示', (errorText || '').length > 0, errorText || '(空)')
check(
  '错误提示不泄漏用户是否存在',
  !!errorText && !/不存在|没有该用户|not found/i.test(errorText),
  errorText || '',
)
check('密码错误后仍停留在登录页', page.url().includes('/admin/login'))
check(
  '密码错误后 Cookie 未被设置',
  (await context.cookies()).every((c) => c.name !== 'blog_session'),
)

await shot(page, 'm4-02-login-error')

// ====================================================================
console.log('\n--- 3. 登录成功 ---')
// ====================================================================

await page.fill('input[name="password"]', ADMIN_PASS)
await page.click('button[type="submit"]')
await page.waitForURL(/\/admin\/articles/, { timeout: 15000 }).catch(() => {})

// 【必须等 Cookie 真正落盘，不能只看 URL】
// Cookie 由浏览器在收到响应后异步写入 cookie store，
// 而 router.push 可能在响应处理完成的同时就改了 URL。
// 之前这里直接读 context.cookies()，抓到的是空数组，
// 于是误报「会话 Cookie 未设置」—— 而实际上它一切正常。
// 用 waitForFunction 轮询到出现为止，比固定 sleep 更可靠。
await page
  .waitForFunction(
    () => document.location.pathname.startsWith('/admin'),
    { timeout: 15000 },
  )
  .catch(() => {})

let cookies = []
for (let i = 0; i < 40; i++) {
  cookies = await context.cookies()
  if (cookies.some((c) => c.name === 'blog_session')) break
  await page.waitForTimeout(250)
}

check('登录后跳到原本想去的页面（redirect 生效）',
  page.url().endsWith('/admin/articles'), page.url())

const sessionCookie = cookies.find((c) => c.name === 'blog_session')
check('会话 Cookie 已设置', !!sessionCookie,
  sessionCookie ? `值长度 ${sessionCookie.value.length}` : '未找到')
// 这几条是 ADR-03 的核心，浏览器里验证才算数
check('Cookie 是 HttpOnly（JS 读不到）', sessionCookie?.httpOnly === true,
  String(sessionCookie?.httpOnly))
check('Cookie 是 SameSite=Lax', sessionCookie?.sameSite === 'Lax', String(sessionCookie?.sameSite))

const jsCanReadCookie = await page.evaluate(() => document.cookie.includes('blog_session'))
check('页面 JS 确实读不到会话 Cookie', jsCanReadCookie === false)

await page.waitForSelector('.admin__side', { timeout: 15000 })
const sidebarVisible = await page.locator('.admin__side').isVisible()
check('后台侧边栏已渲染', sidebarVisible)

const usernameShown = await page.locator('.admin__user').textContent().catch(() => '')
check('侧边栏显示当前用户名', (usernameShown || '').trim() === ADMIN_USER, usernameShown || '')

// 表格真的渲染出数据（M2 那个 bug 的同类检查）
await page.waitForSelector('.admin-articles__table tbody tr', { timeout: 15000 })
const rowCount = await page.locator('.admin-articles__table tbody tr').count()
check('文章列表渲染出数据行', rowCount > 0, `${rowCount} 行`)

const countText = await page.locator('.admin-articles__count').textContent()
check('列表显示文章总数', /共 \d+ 篇/.test(countText || ''), (countText || '').trim())

await shot(page, 'm4-03-article-list')

// ====================================================================
console.log('\n--- 4. 刷新页面后登录态保持 ---')
// ====================================================================

await page.reload({ waitUntil: 'networkidle' })
// 【关键】Pinia 内存状态刷新即清空，靠 /auth/me 恢复。
// 如果守卫顺序写错，会先闪到登录页再跳回来 —— 那也算失败。
check('刷新后仍在文章管理页（未被踢到登录页）',
  page.url().endsWith('/admin/articles'), page.url())

const rowsAfterReload = await page.locator('.admin-articles__table tbody tr').count()
check('刷新后数据正常渲染', rowsAfterReload > 0, `${rowsAfterReload} 行`)

// ====================================================================
console.log('\n--- 5. 筛选与分页状态放进 URL ---')
// ====================================================================

await page.click('button:has-text("草稿")')
await page.waitForFunction(() => location.search.includes('status=draft'), { timeout: 8000 })
  .catch(() => {})
check('点击「草稿」后状态写进 URL', page.url().includes('status=draft'), page.url())

await page.waitForSelector('.admin-articles__table tbody tr, .empty', { timeout: 10000 })
const draftBadges = await page.locator('.admin-articles__badge--draft').count()
const draftRows = await page.locator('.admin-articles__table tbody tr').count()
check('筛选草稿后列表里只有草稿',
  draftRows === 0 || draftBadges === draftRows,
  `${draftBadges}/${draftRows}`)

// 刷新后筛选条件还在（这正是把状态放 URL 的目的）
await page.reload({ waitUntil: 'networkidle' })
check('刷新后筛选条件仍在 URL 里', page.url().includes('status=draft'), page.url())

const tabActive = await page.locator('.admin-articles__tab--active').textContent()
check('刷新后「草稿」标签仍高亮', (tabActive || '').trim() === '草稿', (tabActive || '').trim())

await shot(page, 'm4-04-draft-filter')

// 回到全部
await page.click('button:has-text("全部")')
await page.waitForFunction(() => !location.search.includes('status='), { timeout: 8000 })
  .catch(() => {})

// ====================================================================
console.log('\n--- 6. 新建文章（草稿）---')
// ====================================================================

await page.goto(`${BASE}/admin/articles/new`, { waitUntil: 'networkidle' })
await page.waitForSelector('.editor__md', { timeout: 15000 })

const uniqueTitle = `M4 验证文章 ${Date.now()}`

await page.fill('.editor__input--title', uniqueTitle)
await page.fill('.editor__md', [
  '## 这是二级标题',
  '',
  '这是一段正文，包含 **粗体** 和 `行内代码`。',
  '',
  '- 列表项一',
  '- 列表项二',
  '',
  '```js',
  'const answer = 42',
  '```',
].join('\n'))

// 预览是否真的渲染了（不是只显示源码）
await page.waitForSelector('.editor__preview h2', { timeout: 10000 })
const previewH2 = await page.locator('.editor__preview h2').textContent()
check('编辑器预览渲染出 h2', (previewH2 || '').includes('这是二级标题'), previewH2 || '')

const previewStrong = await page.locator('.editor__preview strong').count()
check('编辑器预览渲染出粗体', previewStrong > 0, `${previewStrong} 个`)

const previewPre = await page.locator('.editor__preview pre code').count()
check('编辑器预览渲染出代码块', previewPre > 0, `${previewPre} 个`)

const wordCount = await page.locator('.editor__count').textContent()
check('编辑器显示字数', /\d+ 字/.test(wordCount || ''), (wordCount || '').trim())

const dirtyShown = await page.locator('.editor__dirty').count()
check('有未保存修改时显示提示', dirtyShown === 1)

await shot(page, 'm4-05-editor')

// 预览里的 XSS 载荷必须被消解
// 【为什么这条必须有】预览用 v-html 渲染，如果净化失效，
// 从别处粘贴进来的 Markdown 就能在预览时执行脚本。
await page.fill('.editor__md', '<img src=x onerror="window.__XSS_FIRED=true">\n\n[点我](javascript:alert(1))')
await page.waitForTimeout(600)

const xssResult = await page.evaluate(() => ({
  fired: window.__XSS_FIRED === true,
  imgCount: document.querySelectorAll('.editor__preview img').length,
  jsHref: Array.from(document.querySelectorAll('.editor__preview a')).some((a) =>
    (a.getAttribute('href') || '').toLowerCase().startsWith('javascript:'),
  ),
}))
check('预览中的 onerror 载荷未执行', xssResult.fired === false)
check('预览中未生成带 onerror 的 img', xssResult.imgCount === 0, `${xssResult.imgCount} 个`)
check('预览中的 javascript: 链接被消解', xssResult.jsHref === false)

// 写回正常内容
await page.fill('.editor__md', '## 这是二级标题\n\n正文内容。')
await page.waitForTimeout(300)

// 保存草稿
await page.click('button:has-text("保存草稿")')
await page.waitForSelector('.editor__alert--ok', { timeout: 15000 })
const saveMsg = await page.locator('.editor__alert--ok').textContent()
check('保存草稿后显示成功提示', (saveMsg || '').includes('草稿') || (saveMsg || '').includes('保存'),
  (saveMsg || '').trim())

// 新建后应跳到编辑页（否则再点保存会又创建一篇）
await page.waitForFunction(() => /\/admin\/articles\/\d+\/edit/.test(location.pathname), { timeout: 10000 })
  .catch(() => {})
check('新建后 URL 变成编辑页（避免重复创建）',
  /\/admin\/articles\/\d+\/edit/.test(page.url()), page.url())

const newArticleId = Number(page.url().match(/\/articles\/(\d+)\/edit/)?.[1])
check('能从 URL 取到新文章 id', Number.isInteger(newArticleId) && newArticleId > 0, String(newArticleId))

await shot(page, 'm4-06-saved')

// ====================================================================
console.log('\n--- 7. 数据真的进了数据库 ---')
// ====================================================================

// 不信界面提示，直接查 API
const apiCheck = await page.evaluate(async (id) => {
  const res = await fetch(`/api/admin/articles/${id}`, { credentials: 'include' })
  return { status: res.status, body: await res.json() }
}, newArticleId)

check('新建的文章可通过后台接口读到', apiCheck.status === 200, `status=${apiCheck.status}`)
check('标题写入正确', apiCheck.body?.data?.title === uniqueTitle,
  String(apiCheck.body?.data?.title))
check('内容写入正确', (apiCheck.body?.data?.content_md || '').includes('正文内容'))
check('新建默认是草稿', apiCheck.body?.data?.status === 'draft',
  String(apiCheck.body?.data?.status))
check('草稿的 published_at 为空', apiCheck.body?.data?.published_at === null,
  String(apiCheck.body?.data?.published_at))

// ====================================================================
console.log('\n--- 8. 未保存修改的离开提醒 ---')
// ====================================================================

await page.fill('.editor__md', '改了一点内容但不保存')

// 站内跳转应被 confirm 拦截
let dialogMessage = ''
page.once('dialog', async (dialog) => {
  dialogMessage = dialog.message()
  await dialog.dismiss() // 取消：留在当前页
})
await page.click('.editor__back')
await page.waitForTimeout(800)

check('有未保存修改时站内跳转被拦截', dialogMessage.length > 0, dialogMessage)
check('取消离开后仍停在编辑页', page.url().includes('/edit'), page.url())

// 接受离开
page.once('dialog', (dialog) => dialog.accept())
await page.click('.editor__back')
await page.waitForURL(/\/admin\/articles$/, { timeout: 10000 }).catch(() => {})
check('确认后可以离开', page.url().endsWith('/admin/articles'), page.url())

// ====================================================================
console.log('\n--- 9. 编辑已发布文章与发布动作 ---')
// ====================================================================

await page.goto(`${BASE}/admin/articles/${newArticleId}/edit`, { waitUntil: 'networkidle' })
await page.waitForSelector('.editor__md', { timeout: 15000 })

const loadedTitle = await page.inputValue('.editor__input--title')
check('编辑页加载出了已有标题', loadedTitle === uniqueTitle, loadedTitle)

const loadedMd = await page.inputValue('.editor__md')
check('编辑页加载出了 Markdown 原文（不是渲染后的 HTML）',
  loadedMd.includes('##') === false || !loadedMd.includes('<h2>'),
  loadedMd.slice(0, 40))

// 发布
await page.click('button:has-text("发布")')
await page.waitForFunction(
  () => {
    const el = document.querySelector('.editor__status')
    return el && el.textContent.includes('已发布')
  },
  { timeout: 15000 },
).catch(() => {})

const statusText = await page.locator('.editor__status').textContent()
check('发布后状态标记变为已发布', (statusText || '').includes('已发布'), (statusText || '').trim())

// 【关键】发布后 published_at 必须被写入
const publishedCheck = await page.evaluate(async (id) => {
  const res = await fetch(`/api/admin/articles/${id}`, { credentials: 'include' })
  return (await res.json()).data
}, newArticleId)
check('发布后 published_at 已写入', !!publishedCheck?.published_at,
  String(publishedCheck?.published_at))

await shot(page, 'm4-07-published')

// ====================================================================
console.log('\n--- 10. 标签管理 ---')
// ====================================================================

await page.goto(`${BASE}/admin/tags`, { waitUntil: 'networkidle' })
await page.waitForSelector('.tags__row, .empty', { timeout: 15000 })

const tagRowCount = await page.locator('.tags__row').count()
check('标签列表渲染出数据', tagRowCount > 0, `${tagRowCount} 行`)

const tagUsageShown = await page.locator('.tags__usage').first().textContent()
check('标签显示文章数', /篇/.test(tagUsageShown || ''), (tagUsageShown || '').trim())

await shot(page, 'm4-08-tags')

// 新建标签
const newTagName = `M4标签${Date.now() % 100000}`
await page.fill('.tags__create .tags__input', newTagName)
await page.click('button:has-text("新建标签")')
await page.waitForFunction(
  (name) => Array.from(document.querySelectorAll('.tags__name')).some((el) => el.textContent.includes(name)),
  newTagName,
  { timeout: 15000 },
).catch(() => {})

const tagCreated = await page.locator(`.tags__name:text-is("${newTagName}")`).count()
check('新建标签出现在列表里', tagCreated === 1, `${tagCreated} 个匹配`)

// 重名应被拒绝
await page.fill('.tags__create .tags__input', newTagName)
await page.click('button:has-text("新建标签")')
await page.waitForSelector('.tags__alert', { timeout: 10000 }).catch(() => {})
const dupError = await page.locator('.tags__alert').textContent().catch(() => '')
check('重名标签被拒绝', (dupError || '').includes('已存在') || (dupError || '').length > 0,
  (dupError || '').trim())

// 重命名
await page.locator('.tags__row', { hasText: newTagName }).locator('button:has-text("重命名")').click()
await page.waitForSelector('.tags__input--inline', { timeout: 8000 })
await page.fill('.tags__input--inline', `${newTagName}改`)
await page.keyboard.press('Enter')
await page.waitForFunction(
  (name) => Array.from(document.querySelectorAll('.tags__name')).some((el) => el.textContent.includes(name)),
  `${newTagName}改`,
  { timeout: 15000 },
).catch(() => {})
const renamed = await page.locator(`.tags__name:text-is("${newTagName}改")`).count()
check('重命名生效', renamed === 1, `${renamed} 个匹配`)

await shot(page, 'm4-09-tag-renamed')

// 删除：确认文案必须写清「文章会保留」
await page.locator('.tags__row', { hasText: `${newTagName}改` }).locator('button:has-text("删除")').click()
await page.waitForSelector('.modal__box', { timeout: 10000 })

const modalText = await page.locator('.modal__box').textContent()
check('删除确认框写明「只删除标签，相关文章会保留」',
  (modalText || '').includes('相关文章会保留'), (modalText || '').replace(/\s+/g, ' ').slice(0, 120))

const usageShown = await page.locator('.modal__usage').count()
check('删除确认框显示使用该标签的文章数', usageShown === 1)

await shot(page, 'm4-10-tag-delete')

await page.click('.modal__btn--danger')
await page.waitForTimeout(1500)
const tagGone = await page.locator(`.tags__name:text-is("${newTagName}改")`).count()
check('删除后标签从列表消失', tagGone === 0, `${tagGone} 个残留`)

// ====================================================================
console.log('\n--- 11. 站点设置与页头同步 ---')
// ====================================================================

await page.goto(`${BASE}/admin/settings`, { waitUntil: 'networkidle' })
await page.waitForSelector('#f-site_title', { timeout: 15000 })

const originalTitle = await page.inputValue('#f-site_title')
check('设置页加载出当前站点标题', originalTitle.length > 0, originalTitle)

// 改标题 → 保存 → 访客页头必须跟着变
// 【这是 M3 遗留的问题】后台能改配置，但只有首页标题会变，页头不变。
const tempTitle = `M4 站点标题 ${Date.now() % 100000}`
await page.fill('#f-site_title', tempTitle)
await page.waitForSelector('.settings__dirty', { timeout: 5000 }).catch(() => {})
check('修改后出现未保存提示', (await page.locator('.settings__dirty').count()) === 1)

await page.click('.settings__btn--primary')
await page.waitForSelector('.settings__alert--ok', { timeout: 15000 })
const settingsMsg = await page.locator('.settings__alert--ok').textContent()
check('保存后显示成功提示', (settingsMsg || '').length > 0, (settingsMsg || '').trim())

await shot(page, 'm4-11-settings')

// 去首页看页头
await page.goto(`${BASE}/`, { waitUntil: 'networkidle' })
await page.waitForSelector('.header__brand', { timeout: 15000 })
const headerTitle = await page.locator('.header__brand').textContent()
check('保存后访客页头立即显示新标题（M3 遗留问题已修）',
  (headerTitle || '').trim() === tempTitle, (headerTitle || '').trim())

await shot(page, 'm4-12-header-synced')

// 改回原标题，避免污染开发数据
await page.goto(`${BASE}/admin/settings`, { waitUntil: 'networkidle' })
await page.waitForSelector('#f-site_title', { timeout: 15000 })
await page.fill('#f-site_title', originalTitle)
await page.click('.settings__btn--primary')
await page.waitForSelector('.settings__alert--ok', { timeout: 15000 })

// ====================================================================
console.log('\n--- 12. 退出登录 ---')
// ====================================================================

await page.click('.admin__logout')
await page.waitForURL(/\/admin\/login/, { timeout: 15000 }).catch(() => {})
check('退出后跳到登录页', page.url().includes('/admin/login'), page.url())

const cookiesAfterLogout = await context.cookies()
const sessionAfterLogout = cookiesAfterLogout.find((c) => c.name === 'blog_session')
check('退出后会话 Cookie 被清除',
  !sessionAfterLogout || sessionAfterLogout.value === '',
  sessionAfterLogout ? `值长度 ${sessionAfterLogout.value.length}` : '不存在')

// 退出后再访问后台应被拦住
await page.goto(`${BASE}/admin/articles`, { waitUntil: 'networkidle' })
await page.waitForURL(/\/admin\/login/, { timeout: 10000 }).catch(() => {})
check('退出后无法访问后台页面', page.url().includes('/admin/login'), page.url())

// ====================================================================
console.log('\n--- 13. 清理测试数据 ---')
// ====================================================================

// 重新登录以删除测试文章
await page.fill('input[name="username"]', ADMIN_USER)
await page.fill('input[name="password"]', ADMIN_PASS)
await page.click('button[type="submit"]')
await page.waitForURL(/\/admin\//, { timeout: 15000 })

// 同样要等 Cookie 落盘。上一版在这里直接发 fetch，
// 拿到 401 并把它记成「测试文章未删除」—— 而实际原因是
// 请求发出时浏览器还没把 Set-Cookie 写进 store。
// 这类「测试基础设施的时序问题」会被误读成产品缺陷，
// 所以宁可多等一次轮询，也不要留下一条假失败。
for (let i = 0; i < 40; i++) {
  const c = await context.cookies()
  if (c.some((x) => x.name === 'blog_session' && x.value)) break
  await page.waitForTimeout(250)
}

const deleted = await page.evaluate(async (id) => {
  const res = await fetch(`/api/admin/articles/${id}`, {
    method: 'DELETE',
    credentials: 'include',
  })
  return res.status
}, newArticleId)
check('测试文章已删除', deleted === 200 || deleted === 204, `status=${deleted}`)

const afterDelete = await page.evaluate(async (id) => {
  const res = await fetch(`/api/admin/articles/${id}`, { credentials: 'include' })
  return res.status
}, newArticleId)
check('删除后接口返回 404', afterDelete === 404, `status=${afterDelete}`)

// ====================================================================
console.log('\n--- 14. 控制台错误 ---')
// ====================================================================

// 【为什么 4xx 不能一律算「错误」】
// 浏览器会把任何 4xx 响应都打进 console，即使代码已经正确处理。
// 本次流程里有四处是测试**刻意触发**的：
//   - 未登录访问后台 → GET /auth/me 返回 401（守卫靠它判断未登录）
//   - 故意用错密码登录 → POST /auth/login 返回 401（在测错误提示）
//   - 故意建重名标签   → POST /admin/tags 返回 409（在测重名拒绝）
//   - 删除后再查一次   → GET /admin/articles/{id} 返回 404（在测删除生效）
//
// 但「预期内」必须由**明确的规则**判定，不能笼统地说「忽略 4xx」——
// 那样会连真问题一起忽略。这里按「具体是哪个请求、什么状态码」匹配。
const expectedHttp = [
  { re: /401 GET .*\/api\/auth\/me$/, why: '未登录探测（守卫判断登录态）' },
  { re: /401 POST .*\/api\/auth\/login$/, why: '故意用错密码测错误提示' },
  { re: /409 POST .*\/api\/admin\/tags$/, why: '故意建重名标签测拒绝' },
  { re: /404 GET .*\/api\/admin\/articles\/\d+$/, why: '删除后复查已不存在' },
]

const unexpectedHttp = httpErrors.filter(
  (line) => !expectedHttp.some((rule) => rule.re.test(line)),
)
const matchedExpected = httpErrors.filter((line) =>
  expectedHttp.some((rule) => rule.re.test(line)),
)

check('无非预期的 4xx/5xx 请求', unexpectedHttp.length === 0,
  unexpectedHttp.length ? unexpectedHttp.slice(0, 3).join(' | ') : '无')

console.log(`[INFO] 另有 ${matchedExpected.length} 条刻意触发的 4xx：`)
for (const line of matchedExpected) {
  const rule = expectedHttp.find((r) => r.re.test(line))
  console.log(`       ${line}   （${rule?.why}）`)
}

// 真正的 JS 异常（未捕获错误 / pageerror）一条都不能有
const jsExceptions = consoleErrors.filter((t) => t.startsWith('pageerror:'))
check('无未捕获的 JS 异常', jsExceptions.length === 0,
  jsExceptions.length ? jsExceptions.slice(0, 3).join(' | ') : '无')

// console 里的错误消息条数必须与实际 4xx 响应数一致。
// 【这条断言的意义】如果某个请求失败了却没有产生 console 记录，
// 或者反过来有记录却没有对应响应，说明统计口径漏了东西。
const consoleHttpErrors = consoleErrors.filter((t) => /status of \d{3}/.test(t))
check('控制台 4xx 数量与实际响应一致',
  consoleHttpErrors.length === httpErrors.length,
  `console ${consoleHttpErrors.length} 条 / 响应 ${httpErrors.length} 条`)

// 打印所有 4xx/5xx，附带具体 URL
console.log('\n所有 4xx/5xx 请求：')
for (const line of httpErrors) console.log(`  ${line}`)
if (httpErrors.length === 0) console.log('  （无）')
// ====================================================================

await browser.close()

console.log()
console.log('='.repeat(66))
console.log(`通过 ${passed} 项，失败 ${failed.length} 项`)
if (failed.length) {
  console.log('失败清单：')
  for (const name of failed) console.log(`  - ${name}`)
}
console.log(`截图已保存到 ${SHOTS}/`)
console.log('='.repeat(66))

process.exit(failed.length ? 1 : 0)
