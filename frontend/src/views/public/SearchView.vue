<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { RouterLink, useRoute, useRouter } from 'vue-router'
import { searchArticles } from '@/api/blog'
import ArticleCard from '@/components/public/ArticleCard.vue'
import EmptyState from '@/components/public/EmptyState.vue'
import Pagination from '@/components/public/Pagination.vue'
import SkeletonList from '@/components/public/SkeletonList.vue'
import type { ArticleListItem } from '@/types/blog'

const route = useRoute()
const router = useRouter()

const input = ref('')
const articles = ref<ArticleListItem[]>([])
const total = ref(0)
const pages = ref(0)
const loading = ref(false)
const error = ref('')
/** 是否已经执行过一次搜索（区别于「刚进页面还没搜」） */
const searched = ref(false)

/** 关键词写在 URL 里（文档 06 表格 12）：刷新与分享都不丢失 */
const keyword = computed(() => {
  const raw = route.query.q
  return typeof raw === 'string' ? raw.trim() : ''
})

const currentPage = computed(() => {
  const raw = Number(route.query.page)
  return Number.isInteger(raw) && raw > 0 ? raw : 1
})

async function run() {
  if (!keyword.value) {
    articles.value = []
    total.value = 0
    pages.value = 0
    searched.value = false
    return
  }

  loading.value = true
  error.value = ''
  try {
    const res = await searchArticles(keyword.value, currentPage.value)
    articles.value = res.items
    total.value = res.total
    pages.value = res.pages
  } catch (e) {
    error.value = e instanceof Error ? e.message : '搜索失败'
    articles.value = []
    total.value = 0
    pages.value = 0
  } finally {
    loading.value = false
    searched.value = true
  }
}

function submit() {
  const q = input.value.trim()
  // 输入即搜会造成请求风暴（文档 06 表格 12），所以只在回车/点击时触发。
  // 切关键词时把 page 清掉，避免带着旧页码去查新词。
  router.push({ query: q ? { q } : {} })
}

function changePage(p: number) {
  router.push({ query: { ...route.query, page: p === 1 ? undefined : String(p) } })
  window.scrollTo({ top: 0 })
}

onMounted(() => {
  // 从 URL 回填输入框（比如用户直接打开 /search?q=sqlite）
  input.value = keyword.value
  run()
})

watch(() => route.query, () => {
  input.value = keyword.value
  run()
})
</script>

<template>
  <section class="search">
    <header class="search__header">
      <h1 class="search__title">搜索</h1>
    </header>

    <form class="search__form" @submit.prevent="submit">
      <input
        v-model="input"
        class="search__input"
        type="search"
        placeholder="搜索文章标题、摘要或正文…"
        aria-label="搜索关键词"
      />
      <button class="search__btn" type="submit" :disabled="!input.trim()">搜索</button>
    </form>

    <p v-if="keyword && !loading" class="search__summary">
      「{{ keyword }}」的搜索结果<span v-if="!error">（{{ total }} 篇）</span>
    </p>

    <SkeletonList v-if="loading" :count="3" />

    <EmptyState
      v-else-if="error"
      title="搜索失败"
      :hint="error"
      action-text="回到首页"
      action-to="/"
    />

    <!-- 三种「没有内容」的情况要分开处理，否则用户不知道该做什么 -->
    <EmptyState
      v-else-if="!keyword"
      title="输入关键词开始搜索"
      hint="搜索范围包括标题、摘要与正文。"
    >
      <p class="search__suggest">
        也可以 <RouterLink to="/tags">按标签浏览</RouterLink> 或
        <RouterLink to="/archive">按归档浏览</RouterLink>。
      </p>
    </EmptyState>

    <EmptyState
      v-else-if="searched && !articles.length"
      title="没有找到相关文章"
      hint="试试其他关键词，或者换个说法。"
      action-text="浏览全部标签"
      action-to="/tags"
    />

    <template v-else-if="articles.length">
      <div class="search__list">
        <ArticleCard v-for="article in articles" :key="article.id" :article="article" />
      </div>
      <Pagination :page="currentPage" :pages="pages" @change="changePage" />
    </template>
  </section>
</template>

<style scoped>
.search {
  padding-top: var(--space-6);
}

.search__header {
  padding-bottom: var(--space-5);
}

.search__title {
  font-size: var(--text-3xl);
  color: var(--color-heading);
}

.search__form {
  display: flex;
  gap: var(--space-3);
}

.search__input {
  flex: 1;
  min-width: 0;
  height: 40px;
  padding: 0 var(--space-4);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
  background: var(--color-bg);
  color: var(--color-text);
  font-size: var(--text-base);
  font-family: inherit;
  transition: border-color var(--transition);
}

.search__input:focus {
  outline: none;
  border-color: var(--color-primary);
}

.search__btn {
  flex-shrink: 0;
  height: 40px;
  padding: 0 var(--space-5);
  border: 1px solid var(--color-primary);
  border-radius: var(--radius-md);
  background: var(--color-primary);
  color: #fff;
  font-size: var(--text-base);
  transition: background var(--transition);
}

.search__btn:hover:not(:disabled) {
  background: var(--color-primary-hover);
  border-color: var(--color-primary-hover);
}

.search__btn:disabled {
  cursor: not-allowed;
  opacity: 0.5;
}

.search__summary {
  margin-top: var(--space-5);
  font-size: var(--text-sm);
  color: var(--color-text-secondary);
}

.search__list {
  display: flex;
  flex-direction: column;
  gap: var(--space-5);
  margin-top: var(--space-5);
}

.search__suggest {
  margin-top: var(--space-4);
  font-size: var(--text-sm);
  color: var(--color-text-muted);
}

.search__suggest a {
  color: var(--color-primary);
  text-decoration: none;
}

.search__suggest a:hover {
  text-decoration: underline;
}
</style>
