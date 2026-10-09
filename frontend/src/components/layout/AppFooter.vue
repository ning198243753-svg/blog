<script setup lang="ts">
import { RouterLink } from 'vue-router'

const year = new Date().getFullYear()
</script>

<template>
  <footer class="footer">
    <div class="footer__inner">
      <p class="footer__line">© {{ year }} moon 的学习笔记</p>
      <p class="footer__line">
        <!-- 后台入口刻意做成不显眼的小字：你知道它在哪，访客不会注意（文档 06 第 1.2 节） -->
        <RouterLink to="/admin/articles" class="footer__admin">管理后台</RouterLink>
      </p>
    </div>
  </footer>
</template>

<style scoped>
.footer {
  border-top: 1px solid var(--color-border);
  margin-top: var(--space-7);
}

.footer__inner {
  max-width: var(--content-max);
  margin: 0 auto;
  padding: var(--space-6) var(--space-4);
  text-align: center;
}

.footer__line {
  margin: 0;
  font-size: var(--text-sm);
  color: var(--color-text-muted);
}

.footer__line + .footer__line {
  margin-top: var(--space-2);
}

.footer__admin {
  font-size: var(--text-xs);
  color: var(--color-text-muted);
}

.footer__admin:hover {
  color: var(--color-primary);
}

@media (min-width: 1024px) {
  .footer__inner {
    padding: var(--space-7) var(--space-5);
  }
}
</style>
