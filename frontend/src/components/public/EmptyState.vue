<script setup lang="ts">
import { RouterLink } from 'vue-router'

/**
 * 空状态（文档 06 第 5.3 节）。
 *
 * 「无数据」和「加载失败」是两种不同的情况，
 * 用同一个组件但文案不同 —— 分不清会让用户不知道该刷新还是该等待。
 */
withDefaults(
  defineProps<{
    title: string
    hint?: string
    actionText?: string
    actionTo?: string
  }>(),
  { hint: '', actionText: '', actionTo: '' },
)
</script>

<template>
  <div class="empty">
    <p class="empty__title">{{ title }}</p>
    <p v-if="hint" class="empty__hint">{{ hint }}</p>
    <RouterLink v-if="actionText && actionTo" class="empty__action" :to="actionTo">
      {{ actionText }}
    </RouterLink>
    <slot />
  </div>
</template>

<style scoped>
.empty {
  padding: var(--space-8) var(--space-5);
  border: 1px dashed var(--color-border);
  border-radius: var(--radius-md);
  text-align: center;
}

.empty__title {
  font-size: var(--text-lg);
  color: var(--color-text);
}

.empty__hint {
  margin-top: var(--space-2);
  font-size: var(--text-sm);
  color: var(--color-text-muted);
}

.empty__action {
  display: inline-block;
  margin-top: var(--space-4);
  padding: 0 var(--space-4);
  height: 36px;
  line-height: 34px;
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
  color: var(--color-primary);
  font-size: var(--text-sm);
  text-decoration: none;
  transition: all var(--transition);
}

.empty__action:hover {
  border-color: var(--color-primary);
  background: var(--color-bg-soft);
}
</style>
