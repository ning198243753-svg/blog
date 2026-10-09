/**
 * M0-0.9 端到端验收：真实浏览器渲染，检查「后端已连接」是否出现在页面上。
 *
 * 为什么必须用真实浏览器：
 * 前面的 curl 只能证明「后端返回了正确 JSON」，
 * 但这条链路上还有 Vite 代理、Axios 拦截器拆包、Pinia 状态、Vue 渲染四段。
 * 任何一段错了，curl 都看不出来。
 */
import { chromium } from 'playwright'

const BASE = 'http://127.0.0.1:5173'

// Windows 控制台按 GBK 解码，中文输出会乱码；用 ASCII 前缀保证可读
const results = []
function check(name, ok, detail = '') {
  results.push({ name, ok })
  console.log(`[${ok ? 'PASS' : 'FAIL'}] ${name}  ${detail}`)
}

const browser = await chromium.launch()
const page = await browser.newPage()

// ---- 1. 首页渲染 ----
await page.goto(BASE + '/', { waitUntil: 'networkidle' })
const bodyText = await page.textContent('body')

check('首页标题渲染', bodyText.includes('moon'), '')
check('副标题渲染', bodyText.includes('记录'), '')

const statusEl = await page.textContent('.status')
check('状态条出现在页面上', await page.locator('.status').count() === 1, statusEl.trim())
check('状态为「后端已连接」', statusEl.includes('后端已连接'), statusEl.trim())
check('状态显示 db=ok', statusEl.includes('db=ok'), '')

// ---- 2. 路由懒加载：导航到其它页面 ----
await page.click('a[href="/about"]')
await page.waitForURL('**/about')
await page.waitForLoadState('networkidle')
const aboutText = await page.textContent('body')
check('点击导航跳转到 /about', page.url().endsWith('/about'), page.url())
check('关于页内容渲染', aboutText.includes('关于'), '')

// ---- 3. 404 路由 ----
await page.goto(BASE + '/definitely-not-a-page', { waitUntil: 'networkidle' })
const nfText = await page.textContent('body')
check('404 页面渲染', nfText.includes('404'), '')

// ---- 4. 未登录访问后台 → 跳登录页 ----
await page.goto(BASE + '/admin/articles', { waitUntil: 'networkidle' })
check('未登录访问后台被重定向', page.url().includes('/admin/login'), page.url())

// ---- 5. 控制台无报错 ----
const errors = []
page.on('console', (m) => { if (m.type() === 'error') errors.push(m.text()) })
page.on('pageerror', (e) => errors.push(String(e)))
await page.goto(BASE + '/', { waitUntil: 'networkidle' })
await page.waitForTimeout(800)
check('浏览器控制台无报错', errors.length === 0, errors.join(' | ').slice(0, 200))

// ---- 6. 截图留证 ----
await page.setViewportSize({ width: 1280, height: 800 })
await page.goto(BASE + '/', { waitUntil: 'networkidle' })
await page.screenshot({ path: 'e2e-shots/m0-home-desktop.png', fullPage: true })

await page.setViewportSize({ width: 375, height: 700 })
await page.goto(BASE + '/', { waitUntil: 'networkidle' })
await page.screenshot({ path: 'e2e-shots/m0-home-mobile.png', fullPage: true })

await browser.close()

const failed = results.filter((r) => !r.ok)
console.log('')
console.log('FAILED:', failed.length ? failed.map((f) => f.name) : 'none')
process.exit(failed.length ? 1 : 0)
