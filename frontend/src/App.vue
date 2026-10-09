<script setup lang="ts">
import { computed } from 'vue'
import { RouterView, useRoute } from 'vue-router'
import AdminLayout from '@/components/layout/AdminLayout.vue'
import AppFooter from '@/components/layout/AppFooter.vue'
import AppHeader from '@/components/layout/AppHeader.vue'

const route = useRoute()

/**
 * 后台使用独立布局，不显示访客的页头与页脚。
 *
 * 【为什么登录页也归后台布局】
 * 登录页是进入后台的入口，套上访客页头会让人以为
 * 「点首页链接能回去，登录是个公开页面」。
 * 实际上登录页属于管理区域，用同一套布局更连贯。
 *
 * 用 meta 标记而不是判断路径前缀（/admin）：
 * 路径前缀是偶然的，将来后台换成 /manage 就会漏掉这里的判断，
 * 而 meta 是路由表里显式声明的。
 */
const isAdmin = computed(() => route.path.startsWith('/admin'))
</script>

<template>
  <AdminLayout v-if="isAdmin" />
  <div v-else class="app">
    <AppHeader />
    <main class="app__main">
      <RouterView />
    </main>
    <AppFooter />
  </div>
</template>

<style scoped>
.app {
  display: flex;
  flex-direction: column;
  min-height: 100vh;
}

.app__main {
  flex: 1;
  width: 100%;
  max-width: var(--content-max);
  margin: 0 auto;
  padding: var(--space-6) var(--space-4);
}

@media (min-width: 1024px) {
  .app__main {
    padding: var(--space-7) var(--space-5);
  }
}
</style>
