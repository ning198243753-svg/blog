<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { RouterLink, useRoute, useRouter } from 'vue-router'
import { getArticlesByTag, getTags } from '@/api/blog'
import ArticleCard from '@/components/public/ArticleCard.vue'
import EmptyState from '@/components/public/EmptyState.vue'
import Pagination from '@/components/public/Pagination.vue'
import SkeletonList from '@/components/public/SkeletonList.vue'
import type { ArticleListItem, Tag } from '@/types/blog'

const route = useRoute()
const router = useRouter()

const tags = ref<Tag[]>([])
const articles = ref<ArticleListItem[]>([])
const total = ref(0)
const pages = ref(0)

const loadingTags = ref(true)
const loadingList = ref(false)
const error = ref('')

/** 当前标签 slug；为空表示「标签总览」 */
const currentSlug = computed(() => {
  const raw = route.params.slug
  return typeof raw === 'string' && raw ? raw : ''
})

const currentTag = computed(() => tags.value.find((t) => t.slug === currentSlug.value) ?? null)

const currentPage = computed(() => {
  const raw = Number(route.query.page)
  return Number.isInteger(raw) && raw > 0 ? raw : 1
})

async function loadTags() {
  loadingTags.value = true
  try {
    tags.value = await getTags()
  } catch (e) {
    error.value = e instanceof Error ? e.message : '标签加载失败'
  } finally {
    loadingTags.value = false
  }
}

async function loadArticles() {
  if (!currentSlug.value) {
    articles.value = []
    total.value = 0
    pages.value = 0
    return
  }

  loadingList.value = true
  error.value = ''
  try {
    const res = await getArticlesByTag(currentSlug.value, currentPage.value)
    articles.value = res.items
    total.value = res.total
    pages.value = res.pages
  } catch (e) {
    error.value = e instanceof Error ? e.message : '文章加载失败'
    articles.value = []
  } finally {
    loadingList.value = false
  }
}

function changePage(p: number) {
  router.push({ query: { page: p === 1 ? undefined : String(p) } })
  window.scrollTo({ top: 0 })
}

onMounted(loadTags)
watch(() => route.params.slug, loadArticles, { immediate: true })
watch(() => route.query.page, loadArticles)
</script>

<template>
  <section class="tags">
    <header class="tags__header">
      <h1 class="tags__title">{{ currentTag ? currentTag.name : '标签' }}</h1>
      <p v-if="!currentSlug" class="tags__subtitle">
        共 {{ tags.length }} 个标签。点击任意标签查看该标签下的文章。
      </p>
      <p v-else class="tags__subtitle">
        该标签下有 {{ total }} 篇文章。
        <RouterLink class="tags__all" to="/tags">← 全部标签</RouterLink>
      </p>
    </header>

    <!-- 标签总览
         文档 06 明确写着「不做字号按热度变化的花哨效果」——
         数据量小时反而显得杂乱。这里统一字号，用数量徽标体现热度差异。 -->
    <nav v-if="!currentSlug" class="cloud" aria-label="全部标签">
      <SkeletonList v-if="loadingTags" :count="1" />
      <EmptyState v-else-if="!tags.length" title="还没有任何标签" hint="发布文章并打标签后会出现在这里。" />
      <template v-else>
        <RouterLink
          v-for="tag in tags"
          :key="tag.id"
          class="cloud__item"
          :to="`/tags/${tag.slug}`"
        >
          {{ tag.name }}
          <span class="cloud__count">{{ tag.article_count }}</span>
        </RouterLink>
      </template>
    </nav>

    <!-- 单标签下的文章列表 -->
    <template v-else>
      <SkeletonList v-if="loadingList" :count="3" />
      <EmptyState
        v-else-if="error"
        title="加载失败"
        :hint="error"
        action-text="回到标签列表"
        action-to="/tags"
      />
      <EmptyState
        v-else-if="!articles.length"
        title="这个标签下还没有文章"
        hint="换一个标签看看，或者回到首页浏览全部文章。"
        action-text="回到首页"
        action-to="/"
      />
      <template v-else>
        <div class="tags__list">
          <ArticleCard v-for="article in articles" :key="article.id" :article="article" />
        </div>
        <Pagination :page="currentPage" :pages="pages" @change="changePage" />
      </template>
    </template>
  </section>
</template>

<style scoped>
.tags {
  padding-top: var(--space-6);
}

.tags__header {
  padding-bottom: var(--space-5);
  border-bottom: 1px solid var(--color-border);
}

.tags__title {
  font-size: var(--text-3xl);
  color: var(--color-heading);
}

.tags__subtitle {
  margin-top: var(--space-2);
  font-size: var(--text-sm);
  color: var(--color-text-secondary);
}

.tags__all {
  margin-left: var(--space-2);
  color: var(--color-primary);
  text-decoration: none;
}

.tags__all:hover {
  text-decoration: underline;
}

.cloud {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-3);
  margin-top: var(--space-6);
}

.cloud__item {
  display: inline-flex;
  align-items: center;
  gap: var(--space-2);
  padding: var(--space-2) var(--space-4);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-full);
  color: var(--color-text);
  font-size: var(--text-base);
  text-decoration: none;
  transition: all var(--transition);
}

.cloud__item:hover {
  border-color: var(--color-primary);
  color: var(--color-primary);
}

.cloud__count {
  font-size: var(--text-xs);
  color: var(--color-text-muted);
}

.tags__list {
  display: flex;
  flex-direction: column;
  gap: var(--space-5);
  margin-top: var(--space-6);
}
</style>
