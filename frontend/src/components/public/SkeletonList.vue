<script setup lang="ts">
/**
 * 骨架屏（文档 06 第 5.3 节「三个必须做好的细节」之一）。
 *
 * 为什么必须有：3Mbps 下接口往返 + 首屏渲染有肉眼可见的等待，
 * 白屏会让人以为站点坏了。骨架屏给出「正在加载」的确定反馈。
 *
 * 故意不做闪烁动画：动画会让页面看起来在「抖」，
 * 而且 prefers-reduced-motion 用户需要额外处理。
 */
withDefaults(defineProps<{ count?: number }>(), { count: 3 })
</script>

<template>
  <div class="skeleton-list" aria-hidden="true">
    <div v-for="i in count" :key="i" class="skeleton-card">
      <div class="skeleton-bar skeleton-bar--title" />
      <div class="skeleton-bar skeleton-bar--line" />
      <div class="skeleton-bar skeleton-bar--line skeleton-bar--short" />
      <div class="skeleton-bar skeleton-bar--meta" />
    </div>
  </div>
</template>

<style scoped>
.skeleton-list {
  display: flex;
  flex-direction: column;
  gap: var(--space-5);
}

.skeleton-card {
  padding: var(--space-5);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
  background: var(--color-bg);
}

.skeleton-bar {
  height: 14px;
  border-radius: var(--radius-sm);
  background: var(--color-bg-soft);
}

.skeleton-bar--title {
  height: 24px;
  width: 55%;
}

.skeleton-bar--line {
  margin-top: var(--space-3);
  width: 100%;
}

.skeleton-bar--short {
  width: 72%;
}

.skeleton-bar--meta {
  margin-top: var(--space-4);
  height: 12px;
  width: 30%;
}
</style>
