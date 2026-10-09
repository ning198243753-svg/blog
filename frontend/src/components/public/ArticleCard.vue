<script setup lang="ts">
import { RouterLink } from 'vue-router'
import type { ArticleListItem } from '@/types/blog'
import { formatDate } from '@/utils/date'

defineProps<{ article: ArticleListItem }>()
</script>

<template>
  <article class="card">
    <h2 class="card__title">
      <RouterLink class="card__link" :to="`/posts/${article.slug}`">
        {{ article.title }}
      </RouterLink>
    </h2>

    <!-- 摘要限定 2 行（文档 07 第 4.1 节）：
         摘要长度不一会让卡片高度参差，列表看起来杂乱无章。 -->
    <p v-if="article.summary" class="card__summary">{{ article.summary }}</p>

    <div class="card__meta">
      <time class="card__date" :datetime="article.published_at ?? article.created_at">
        {{ formatDate(article.published_at ?? article.created_at) }}
      </time>

      <span v-if="article.tags.length" class="card__tags">
        <RouterLink
          v-for="tag in article.tags"
          :key="tag.id"
          class="card__tag"
          :to="`/tags/${tag.slug}`"
        >
          {{ tag.name }}
        </RouterLink>
      </span>
    </div>
  </article>
</template>

<style scoped>
.card {
  padding: var(--space-5);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
  background: var(--color-bg);
  box-shadow: var(--shadow-sm);
  transition: box-shadow var(--transition), border-color var(--transition);
}

.card:hover {
  border-color: var(--color-primary);
  box-shadow: var(--shadow-md);
}

.card__title {
  font-size: var(--text-xl);
  font-weight: 600;
  line-height: var(--leading-tight);
  color: var(--color-heading);
}

.card__link {
  color: inherit;
  text-decoration: none;
}

.card__link:hover {
  color: var(--color-primary);
}

.card__summary {
  margin-top: var(--space-3);
  font-size: var(--text-base);
  line-height: 1.6;
  color: var(--color-text-secondary);

  /* 限 2 行 + 省略号 */
  display: -webkit-box;
  -webkit-line-clamp: 2;
  line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.card__meta {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: var(--space-2) var(--space-3);
  margin-top: var(--space-4);
  font-size: var(--text-sm);
  color: var(--color-text-secondary);
}

.card__tags {
  display: inline-flex;
  flex-wrap: wrap;
  gap: var(--space-2);
}

/* 标签统一灰底（文档 07 第 2.1 节末注）：
   一个博客里出现五种彩色标签，是「看起来像模板」的主要原因。
   color 字段仅在明确有值时例外——M2 只用灰底。 */
.card__tag {
  padding: 2px var(--space-2);
  border-radius: var(--radius-sm);
  background: var(--color-bg-soft);
  color: var(--color-text-secondary);
  font-size: var(--text-xs);
  text-decoration: none;
  transition: color var(--transition), background var(--transition);
}

.card__tag:hover {
  background: var(--color-primary);
  color: #fff;
}
</style>
