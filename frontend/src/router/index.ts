import { createRouter, createWebHistory } from 'vue-router'
import { setUnauthorizedHandler } from '@/api/client'

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
  if (router.currentRoute.value.meta.requiresAuth) {
    router.push({
      path: '/admin/login',
      query: { redirect: router.currentRoute.value.fullPath },
    })
  }
})

router.beforeEach((to) => {
  // M0 阶段还没有登录功能，这里先留好结构（文档 06 第 4.2 节）。
  // M3 实现鉴权后，把下面两段替换为真实的登录态判断：
  //
  // if (to.meta.requiresAuth && !authStore.checked) {
  //   await authStore.fetchMe()          // 恢复登录态（Pinia 刷新即丢失）
  // }
  // if (to.meta.requiresAuth && !authStore.isLoggedIn) {
  //   return { path: '/admin/login', query: { redirect: to.fullPath } }
  // }
  if (to.meta.requiresAuth) {
    return { path: '/admin/login', query: { redirect: to.fullPath } }
  }
  return true
})

// FR-22（v1.3 修订后）：只要求 title 与 description 正确设置，不含 SEO
router.afterEach((to) => {
  const base = 'moon 的学习笔记'
  document.title = to.meta.title ? `${to.meta.title} - ${base}` : base
})

export default router
