<script setup lang="ts">
import { useRoute } from 'vue-router'

const route = useRoute()
</script>

<template>
  <section class="placeholder">
    <h1 class="placeholder__title">
      {{ route.params.id ? '编辑文章' : '新建文章' }}
    </h1>
    <p class="placeholder__hint">M3 实现。编辑器与实时预览见文档 06 第 3.3 节</p>
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
