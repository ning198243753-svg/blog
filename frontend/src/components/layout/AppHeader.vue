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
