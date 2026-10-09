<script setup lang="ts">
import { computed, onMounted } from 'vue'
import { useHealthStore } from '@/stores/health'

const health = useHealthStore()

onMounted(() => {
  health.check()
})

const stateClass = computed(() => {
  if (health.loading) return 'loading'
  if (health.error) return 'error'
  if (health.data) return 'ok'
  return 'idle'
})
</script>

<template>
  <section class="home">
    <h1 class="home__title">moon 的学习笔记</h1>
    <p class="home__subtitle">记录 · 整理 · 复现</p>

    <!-- M0 的验收证据：链路是否连通必须「看得见」，不能只靠终端没报错 -->
    <div class="status" :class="`status--${stateClass}`">
      <span class="status__dot" />
      <span class="status__text">
        <template v-if="health.loading">正在检测后端…</template>
        <template v-else-if="health.error">后端未连接：{{ health.error }}</template>
        <template v-else-if="health.data">
          后端已连接　status={{ health.data.status }}　db={{ health.data.db }}
        </template>
        <template v-else>尚未检测</template>
      </span>
    </div>

    <p class="home__hint">
      当前为 M0 骨架阶段。文章列表、标签、归档等页面将在 M1–M2 实现。
    </p>
  </section>
</template>

<style scoped>
.home {
  padding-top: var(--space-6);
}

.home__title {
  font-size: var(--text-3xl);
}

.home__subtitle {
  margin-top: var(--space-2);
  font-size: var(--text-lg);
  color: var(--color-text-secondary);
}

.home__hint {
  margin-top: var(--space-6);
  font-size: var(--text-sm);
  color: var(--color-text-muted);
}

.status {
  display: inline-flex;
  align-items: center;
  gap: var(--space-2);
  margin-top: var(--space-5);
  padding: var(--space-3) var(--space-4);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
  background: var(--color-bg-soft);
  font-size: var(--text-sm);
}

.status__dot {
  width: 8px;
  height: 8px;
  border-radius: var(--radius-full);
  background: var(--color-text-muted);
}

.status--ok .status__dot {
  background: var(--color-success);
}

.status--error .status__dot {
  background: var(--color-danger);
}

.status--ok .status__text {
  color: var(--color-success);
}

.status--error .status__text {
  color: var(--color-danger);
}
</style>
