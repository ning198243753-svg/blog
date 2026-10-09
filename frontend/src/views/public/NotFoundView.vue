<script setup lang="ts">
import { RouterLink } from 'vue-router'
</script>

<template>
  <section class="nf">
    <p class="nf__code">404</p>
    <h1 class="nf__title">这里没有东西</h1>
    <div class="nf__actions">
      <RouterLink to="/" class="nf__btn nf__btn--primary">回到首页</RouterLink>
      <RouterLink to="/tags" class="nf__btn">看看标签</RouterLink>
    </div>
  </section>
</template>

<style scoped>
.nf {
  padding: var(--space-8) 0;
  text-align: center;
}

.nf__code {
  font-size: 64px;
  font-weight: 700;
  line-height: 1;
  color: var(--color-border);
  margin: 0;
}

.nf__title {
  margin-top: var(--space-4);
  font-size: var(--text-xl);
}

.nf__actions {
  margin-top: var(--space-6);
  display: flex;
  gap: var(--space-4);
  justify-content: center;
}

.nf__btn {
  padding: 10px 20px;
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
  font-size: var(--text-sm);
  color: var(--color-text);
  transition: all var(--transition);
}

.nf__btn--primary {
  background: var(--color-primary);
  border-color: var(--color-primary);
  color: #fff;
}

.nf__btn:hover {
  border-color: var(--color-primary);
  color: var(--color-primary);
}

.nf__btn--primary:hover {
  background: var(--color-primary-hover);
  color: #fff;
}
</style>
