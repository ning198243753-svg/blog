<script setup lang="ts">
import { useRoute } from 'vue-router'

const route = useRoute()
</script>

<template>
  <section class="placeholder">
    <h1 class="placeholder__title">
      搜索{{ route.query.q ? '：' + route.query.q : '' }}
    </h1>
    <p class="placeholder__hint">
      M2 实现。数据来源：<code>GET /api/articles?q=</code>
    </p>
  </section>
</template>

<style scoped>
.placeholder__title {
  font-size: var(--text-2xl);
}

.placeholder__hint {
  margin-top: var(--space-3);
  font-size: var(--text-sm);
  color: var(--color-text-secondary);
}
</style>
