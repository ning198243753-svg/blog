<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { RouterLink } from 'vue-router'
import { getSiteConfig } from '@/api/blog'
import EmptyState from '@/components/public/EmptyState.vue'
import SkeletonList from '@/components/public/SkeletonList.vue'

/**
 * 关于页数据来自 site_config（文档 06 第 2.6 节）。
 *
 * 注意占位符里曾写「数据来源 GET /api/about」—— 那个接口不存在。
 * 站点配置统一走 GET /api/site，返回 8 个键值对。
 */

const values = ref<Record<string, string>>({})
const loading = ref(true)
const error = ref('')

const authorName = ref('')
const authorIntro = ref('')
const githubUrl = ref('')
const siteTitle = ref('')

onMounted(async () => {
  try {
    const res = await getSiteConfig()
    values.value = res.values
    authorName.value = res.values.author_name ?? ''
    authorIntro.value = res.values.author_intro ?? ''
    githubUrl.value = res.values.github_url ?? ''
    siteTitle.value = res.values.site_title ?? ''
  } catch (e) {
    error.value = e instanceof Error ? e.message : '加载失败'
  } finally {
    loading.value = false
  }
})
</script>

<template>
  <section class="about">
    <header class="about__header">
      <h1 class="about__title">关于</h1>
    </header>

    <SkeletonList v-if="loading" :count="1" />

    <EmptyState
      v-else-if="error"
      title="加载失败"
      :hint="error"
      action-text="回到首页"
      action-to="/"
    />

    <div v-else class="about__body">
      <section v-if="authorIntro || authorName" class="block">
        <h2 class="block__title">自我介绍</h2>
        <p v-if="authorName" class="about__name">{{ authorName }}</p>
        <!-- author_intro 在数据库里是纯文本。
             文档 06 写的是「Markdown 渲染后的 HTML」，但目前后端
             /api/site 返回的是原文，没有渲染字段。
             所以这里按纯文本显示 —— 保持 white-space: pre-line
             让用户在配置里换行也能正常呈现。 -->
        <p v-if="authorIntro" class="about__intro">{{ authorIntro }}</p>
      </section>

      <section class="block">
        <h2 class="block__title">本站技术栈</h2>
        <ul class="stack">
          <li class="stack__item">
            <span class="stack__label">前端</span>
            <span class="stack__value">Vue 3（组合式 API）+ Vite + TypeScript + Pinia</span>
          </li>
          <li class="stack__item">
            <span class="stack__label">后端</span>
            <span class="stack__value">FastAPI + Uvicorn + Pydantic + SQLAlchemy</span>
          </li>
          <li class="stack__item">
            <span class="stack__label">数据</span>
            <span class="stack__value">SQLite（WAL 模式）+ Alembic 迁移</span>
          </li>
          <li class="stack__item">
            <span class="stack__label">部署</span>
            <span class="stack__value">Ubuntu + Docker Compose + Nginx + HTTPS</span>
          </li>
        </ul>
      </section>

      <section v-if="githubUrl" class="block">
        <h2 class="block__title">联系方式</h2>
        <p class="about__contact">
          GitHub：
          <a :href="githubUrl" target="_blank" rel="noopener noreferrer">{{ githubUrl }}</a>
        </p>
      </section>

      <section class="block">
        <h2 class="block__title">关于本站</h2>
        <p class="about__note">
          {{ siteTitle || '本站' }} 是一个个人学习博客，用来记录学习笔记、知识整理与实践总结。
        </p>
        <p class="about__note">
          本站不使用统计脚本与广告，也不收集访客信息。内容按
          <RouterLink to="/archive">归档</RouterLink> 与
          <RouterLink to="/tags">标签</RouterLink> 两种方式组织。
        </p>
      </section>
    </div>
  </section>
</template>

<style scoped>
.about {
  padding-top: var(--space-6);
}

.about__header {
  padding-bottom: var(--space-5);
  border-bottom: 1px solid var(--color-border);
}

.about__title {
  font-size: var(--text-3xl);
  color: var(--color-heading);
}

.about__body {
  margin-top: var(--space-6);
}

.block + .block {
  margin-top: var(--space-7);
}

.block__title {
  margin-bottom: var(--space-4);
  padding-bottom: var(--space-2);
  font-size: var(--text-2xl);
  color: var(--color-heading);
  border-bottom: 1px solid var(--color-border);
}

.about__name {
  font-size: var(--text-lg);
  font-weight: 600;
  color: var(--color-text);
}

.about__intro {
  margin-top: var(--space-3);
  color: var(--color-text-secondary);
  /* 让配置文本里的换行能被保留 */
  white-space: pre-line;
}

.stack {
  list-style: none;
  padding: 0;
  margin: 0;
}

.stack__item {
  display: flex;
  gap: var(--space-4);
  padding: var(--space-2) 0;
}

.stack__label {
  flex-shrink: 0;
  width: 48px;
  font-size: var(--text-sm);
  color: var(--color-text-muted);
}

.stack__value {
  font-size: var(--text-base);
  color: var(--color-text);
}

.about__contact,
.about__note {
  color: var(--color-text-secondary);
}

.about__note + .about__note {
  margin-top: var(--space-3);
}

.about__note a {
  color: var(--color-primary);
  text-decoration: none;
}

.about__note a:hover {
  text-decoration: underline;
}
</style>
