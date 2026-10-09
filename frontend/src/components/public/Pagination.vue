<script setup lang="ts">
import { computed } from 'vue'

const props = defineProps<{
  page: number
  pages: number
}>()

const emit = defineEmits<{ (e: 'change', page: number): void }>()

/** 最多显示 7 个页码，超出用省略号 —— 页码太多会把分页器撑成两行 */
const visible = computed(() => {
  const { page, pages } = props
  if (pages <= 7) return Array.from({ length: pages }, (_, i) => i + 1)

  if (page <= 4) return [1, 2, 3, 4, 5, '...', pages]
  if (page >= pages - 3) return [1, '...', pages - 4, pages - 3, pages - 2, pages - 1, pages]
  return [1, '...', page - 1, page, page + 1, '...', pages]
})

function go(p: number | string) {
  if (typeof p !== 'number' || p === props.page) return
  emit('change', p)
}
</script>

<template>
  <nav v-if="pages > 1" class="pager" aria-label="分页">
    <button class="pager__btn" :disabled="page <= 1" @click="go(page - 1)">上一页</button>

    <button
      v-for="(p, i) in visible"
      :key="`${p}-${i}`"
      class="pager__btn"
      :class="{ 'pager__btn--current': p === page, 'pager__btn--gap': p === '...' }"
      :disabled="p === '...'"
      :aria-current="p === page ? 'page' : undefined"
      @click="go(p)"
    >
      {{ p }}
    </button>

    <button class="pager__btn" :disabled="page >= pages" @click="go(page + 1)">下一页</button>
  </nav>
</template>

<style scoped>
.pager {
  display: flex;
  flex-wrap: wrap;
  justify-content: center;
  gap: var(--space-2);
  margin-top: var(--space-6);
}

.pager__btn {
  min-width: 36px;
  height: 36px;
  padding: 0 var(--space-3);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
  background: var(--color-bg);
  color: var(--color-text-secondary);
  font-size: var(--text-sm);
  font-family: inherit;
  cursor: pointer;
  transition: all var(--transition);
}

.pager__btn:hover:not(:disabled) {
  border-color: var(--color-primary);
  color: var(--color-primary);
}

.pager__btn:disabled {
  cursor: not-allowed;
  opacity: 0.45;
}

.pager__btn--current {
  border-color: var(--color-primary);
  background: var(--color-primary);
  color: #fff;
}

.pager__btn--gap {
  border-color: transparent;
  background: transparent;
  opacity: 1;
}
</style>
