<script setup lang="ts">
import { RouterLink } from 'vue-router'
import { useSiteStore } from '@/stores/site'

const site = useSiteStore()

const nav = [
  { to: '/', label: '首页' },
  { to: '/tags', label: '标签' },
  { to: '/archive', label: '归档' },
  { to: '/about', label: '关于' },
]
</script>

<template>
  <header class="header">
    <div class="header__inner">
      <RouterLink to="/" class="header__brand">{{ site.title }}</RouterLink>
      <nav class="header__nav">
        <RouterLink v-for="item in nav" :key="item.to" :to="item.to" class="header__link">
          {{ item.label }}
        </RouterLink>
      </nav>

      <!-- 搜索入口：文档 06 表格 2 要求页头右侧有搜索。
           这里用链接而非展开式输入框 —— 展开式需要处理失焦、Esc、点击外部关闭，
           而搜索本身已有独立页面，链接的交互成本更低且行为可预期。 -->
      <RouterLink to="/search" class="header__search" aria-label="搜索">
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" aria-hidden="true">
          <circle cx="11" cy="11" r="7" stroke="currentColor" stroke-width="2" />
          <path d="M16.5 16.5 21 21" stroke="currentColor" stroke-width="2" stroke-linecap="round" />
        </svg>
      </RouterLink>
    </div>
  </header>
</template>

<style scoped>
.header {
  position: sticky;
  top: 0;
  z-index: var(--z-header);
  height: var(--header-height);
  background: rgba(255, 255, 255, 0.85);
  backdrop-filter: blur(8px);
  border-bottom: 1px solid var(--color-border);
}

.header__inner {
  height: 100%;
  max-width: var(--content-max);
  margin: 0 auto;
  padding: 0 var(--space-4);
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-4);
}

.header__brand {
  font-size: var(--text-lg);
  font-weight: 600;
  color: var(--color-heading);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.header__nav {
  display: flex;
  gap: var(--space-4);
  flex-shrink: 0;
}

.header__link {
  font-size: var(--text-sm);
  color: var(--color-text-secondary);
  transition: color var(--transition);
}

.header__link:hover,
.header__link.router-link-active {
  color: var(--color-primary);
}

.header__link.router-link-active {
  font-weight: 600;
}

.header__search {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 36px;
  height: 36px;
  flex-shrink: 0;
  border-radius: var(--radius-md);
  color: var(--color-text-secondary);
  transition: color var(--transition), background var(--transition);
}

.header__search:hover {
  background: var(--color-bg-soft);
  color: var(--color-primary);
}

.header__search.router-link-active {
  color: var(--color-primary);
}

@media (min-width: 1024px) {
  .header__inner {
    padding: 0 var(--space-5);
  }

  .header__nav {
    gap: var(--space-5);
  }

  .header__link {
    font-size: var(--text-base);
  }
}
</style>
