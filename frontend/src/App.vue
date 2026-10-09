<script setup lang="ts">
import { onMounted } from 'vue'
import { RouterView } from 'vue-router'
import AppHeader from '@/components/layout/AppHeader.vue'
import AppFooter from '@/components/layout/AppFooter.vue'
import { useSiteStore } from '@/stores/site'

const siteStore = useSiteStore()

// 站点配置全站共用，启动时拉取一次（ADR-05：跨页面生存的数据才进 store）
onMounted(() => {
  siteStore.load()
})
</script>

<template>
  <div class="app">
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
