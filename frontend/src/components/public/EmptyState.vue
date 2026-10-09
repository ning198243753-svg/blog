<script setup lang="ts">
import { RouterLink } from 'vue-router'

/**
 * 空状态（文档 06 第 5.3 节）。
 *
 * 「无数据」和「加载失败」是两种不同的情况，
 * 用同一个组件但文案不同 —— 分不清会让用户不知道该刷新还是该等待。
 *
 * 【为什么同时支持 actionTo 与 action 两种动作】
 * 这两种空状态的「下一步」性质不同：
 * - 无数据时要做的是**导航**（去新建文章），用 <RouterLink> 才正确 ——
 *   用 button 会丢掉「在新标签页打开」这类浏览器原生行为
 * - 加载失败时要做的是**重试**（重新发请求），那不是导航，必须用 button
 *
 * 只支持其中一种，另一种就得在调用方另写一套空状态 UI，
 * 那样「空状态」这件事就会有两个实现。
 */
withDefaults(
  defineProps<{
    title: string
    hint?: string
    actionText?: string
    /** 传了就渲染成链接 */
    actionTo?: string
    /** 传了就渲染成按钮（用于重试这类动作） */
    action?: boolean
  }>(),
  { hint: '', actionText: '', actionTo: '', action: false },
)

const emit = defineEmits<{ (e: 'action'): void }>()
</script>

<template>
  <div class="empty">
    <p class="empty__title">{{ title }}</p>
    <p v-if="hint" class="empty__hint">{{ hint }}</p>

    <RouterLink v-if="actionText && actionTo" class="empty__action" :to="actionTo">
      {{ actionText }}
    </RouterLink>
    <button
      v-else-if="actionText && action"
      type="button"
      class="empty__action empty__action--btn"
      @click="emit('action')"
    >
      {{ actionText }}
    </button>

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

/* 按钮形态（重试）：外观与链接一致，但要清掉浏览器默认的按钮样式 */
.empty__action--btn {
  background: transparent;
  font-family: inherit;
  cursor: pointer;
}

.empty__action--btn:hover {
  background: var(--color-bg-soft);
}
</style>
