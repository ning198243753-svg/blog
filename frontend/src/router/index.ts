import { createRouter, createWebHistory } from 'vue-router'
import { setUnauthorizedHandler } from '@/api/client'
import { useAuthStore } from '@/stores/auth'
import { useSiteStore } from '@/stores/site'

/**
 * 路由表（文档 06 第 4.1 节）。
 *
 * 两个规则必须遵守：
 * 1. 全部页面用动态 import —— NFR-14 要求后台代码不得进入访客首屏包；
 * 2. 需要登录的页面用 meta.requiresAuth 标记，不在守卫里逐个判断路径。
 */
const router = createRouter({
  // ADR-07：history 模式，配合 Nginx 的 try_files 使用
  history: createWebHistory(),
  routes: [
    // ---- 访客页面 ----
    {
      path: '/',
      name: 'home',
      component: () => import('@/views/public/HomeView.vue'),
      meta: { title: '首页' },
    },
    {
      path: '/posts/:slug',
      name: 'article',
      component: () => import('@/views/public/ArticleView.vue'),
    },
    {
      path: '/tags',
      name: 'tags',
      component: () => import('@/views/public/TagView.vue'),
      meta: { title: '标签' },
    },
    {
      path: '/tags/:slug',
      name: 'tag-detail',
      component: () => import('@/views/public/TagView.vue'),
    },
    {
      path: '/archive',
      name: 'archive',
      component: () => import('@/views/public/ArchiveView.vue'),
      meta: { title: '归档' },
    },
    {
      path: '/search',
      name: 'search',
      component: () => import('@/views/public/SearchView.vue'),
      meta: { title: '搜索' },
    },
    {
      path: '/about',
      name: 'about',
      component: () => import('@/views/public/AboutView.vue'),
      meta: { title: '关于' },
    },

    // ---- 后台页面（需登录）----
    {
      path: '/admin/login',
      name: 'admin-login',
      component: () => import('@/views/admin/LoginView.vue'),
      meta: { title: '登录' },
    },
    {
      path: '/admin/articles',
      name: 'admin-articles',
      component: () => import('@/views/admin/ArticleListView.vue'),
      meta: { title: '文章管理', requiresAuth: true },
    },
    {
      path: '/admin/articles/new',
      name: 'admin-article-new',
      component: () => import('@/views/admin/ArticleEditView.vue'),
      meta: { title: '新建文章', requiresAuth: true },
    },
    {
      path: '/admin/articles/:id/edit',
      name: 'admin-article-edit',
      component: () => import('@/views/admin/ArticleEditView.vue'),
      meta: { title: '编辑文章', requiresAuth: true },
    },
    {
      path: '/admin/tags',
      name: 'admin-tags',
      component: () => import('@/views/admin/TagManageView.vue'),
      meta: { title: '标签管理', requiresAuth: true },
    },
    {
      path: '/admin/settings',
      name: 'admin-settings',
      component: () => import('@/views/admin/SettingsView.vue'),
      meta: { title: '站点设置', requiresAuth: true },
    },

    // ---- 404 兜底 ----
    {
      path: '/:pathMatch(.*)*',
      name: 'not-found',
      component: () => import('@/views/public/NotFoundView.vue'),
      meta: { title: '页面不存在' },
    },
  ],
  scrollBehavior(_to, _from, savedPosition) {
    return savedPosition ?? { top: 0 }
  },
})

// 401 时由 api 层回调到这里，避免 api 层反向依赖 router
setUnauthorizedHandler(() => {
  // 这里只做两件事：清本地登录态、跳到登录页。
  // 不在 api 层直接跳转，是因为 api 层不该知道路由的存在。
  const auth = useAuthStore()
  auth.clear()

  if (router.currentRoute.value.meta.requiresAuth) {
    router.push({
      path: '/admin/login',
      query: { redirect: router.currentRoute.value.fullPath },
    })
  }
})

router.beforeEach(async (to) => {
  // 站点配置在首次进入时拉一次。放在守卫里而不是 App.vue 的 onMounted：
  // 守卫是 await 的，能保证页面渲染时页头已经有正确的标题，
  // 否则会先显示兜底标题再跳变成真实标题。
  void useSiteStore().load()

  if (!to.meta.requiresAuth) {
    return true
  }

  const auth = useAuthStore()

  // 【顺序很关键：先确认登录态，再判断】
  //
  // Pinia 是内存状态，刷新页面即清空。所以首次进入后台时
  // user 是 null —— 但那表示「还不知道」，不表示「未登录」。
  // 如果直接判断 isLoggedIn，刷新后台页面会先跳到登录页，
  // 等 /auth/me 返回 200 才发现其实已登录 —— 用户看到一次闪烁。
  //
  // ensureLoaded 内部用 Promise 去重，并发导航不会重复请求。
  await auth.ensureLoaded()

  if (!auth.isLoggedIn) {
    return { path: '/admin/login', query: { redirect: to.fullPath } }
  }

  return true
})

// 已登录时访问登录页 → 直接进后台。
// 不处理的话，用户点了浏览器「后退」会看到一个没有意义的登录表单。
router.beforeEach((to) => {
  if (to.name !== 'admin-login') return true
  const auth = useAuthStore()
  if (!auth.resolved || !auth.isLoggedIn) return true
  const redirect = to.query.redirect
  return typeof redirect === 'string' && redirect ? redirect : { path: '/admin/articles' }
})

// FR-22（v1.3 修订后）：只要求 title 与 description 正确设置，不含 SEO
router.afterEach((to) => {
  const base = 'moon 的学习笔记'
  document.title = to.meta.title ? `${to.meta.title} - ${base}` : base
})

export default router
