<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { RouterLink, useRoute, useRouter } from 'vue-router'
import { getArticles, getSiteConfig, getTags } from '@/api/blog'
import ArticleCard from '@/components/public/ArticleCard.vue'
import EmptyState from '@/components/public/EmptyState.vue'
import Pagination from '@/components/public/Pagination.vue'
import SkeletonList from '@/components/public/SkeletonList.vue'
import type { ArticleListItem, Tag } from '@/types/blog'

const route = useRoute()
const router = useRouter()

const articles = ref<ArticleListItem[]>([])
const tags = ref<Tag[]>([])
const total = ref(0)
const pages = ref(0)
const loading = ref(true)
const error = ref('')

const siteTitle = ref('moon 的学习笔记')
const siteSubtitle = ref('记录 · 整理 · 复现')

/**
 * 列表状态全部来自 URL，不放在组件内部 state（文档 06 第 5.1 节）。
 *
 * 为什么：刷新、分享链接、浏览器前进后退都必须还原同一个页面。
 * 如果用内部 state，用户翻到第 3 页再刷新就会跳回第 1 页。
 */
const currentPage = computed(() => {
  const raw = Number(route.query.page)
  return Number.isInteger(raw) && raw > 0 ? raw : 1
})

const currentTag = computed(() => {
  const raw = route.query.tag
  return typeof raw === 'string' && raw ? raw : ''
})

const activeTagName = computed(() => {
  if (!currentTag.value) return ''
  return tags.value.find((t) => t.slug === currentTag.value)?.name ?? currentTag.value
})

async function load() {
  loading.value = true
  error.value = ''
  try {
    const res = await getArticles({
      page: currentPage.value,
      tag: currentTag.value || undefined,
    })
    articles.value = res.items
    total.value = res.total
    pages.value = res.pages
  } catch (e) {
    error.value = e instanceof Error ? e.message : '加载失败'
    articles.value = []
    total.value = 0
    pages.value = 0
  } finally {
    loading.value = false
  }
}

function changePage(p: number) {
  // 保留 tag，翻页时不丢掉筛选条件
  router.push({ query: { ...route.query, page: p === 1 ? undefined : String(p) } })
  window.scrollTo({ top: 0 })
}

function selectTag(slug: string) {
  // 切标签时把页码重置回第 1 页 —— 否则从「第 3 页」切到只有 1 页的标签会显示空列表
  router.push({ query: slug ? { tag: slug } : {} })
}

onMounted(async () => {
  // 站点配置与标签一次取回；失败不阻塞文章列表
  try {
    const site = await getSiteConfig()
    siteTitle.value = site.values.site_title || siteTitle.value
    siteSubtitle.value = site.values.site_subtitle || siteSubtitle.value
  } catch {
    /* 用默认值即可 */
  }
  try {
    tags.value = await getTags()
  } catch {
    /* 标签条取不到就不显示 */
  }
})

// 监听整个 query：page 与 tag 任一变化都要重新拉取
watch(() => route.query, load, { immediate: true })
</script>

<template>
  <section class="home">
    <header class="home__hero">
      <h1 class="home__title">{{ siteTitle }}</h1>
      <p class="home__subtitle">{{ siteSubtitle }}</p>
    </header>

    <!-- 标签筛选条（文档 06 表格 6） -->
    <nav v-if="tags.length" class="filter" aria-label="按标签筛选">
      <button
        class="filter__item"
        :class="{ 'filter__item--active': !currentTag }"
        @click="selectTag('')"
      >
        全部
      </button>
      <button
        v-for="tag in tags"
        :key="tag.id"
        class="filter__item"
        :class="{ 'filter__item--active': currentTag === tag.slug }"
        @click="selectTag(tag.slug)"
      >
        {{ tag.name }}
        <span class="filter__count">{{ tag.article_count }}</span>
      </button>
    </nav>

    <p v-if="currentTag" class="home__filtering">
      正在查看「{{ activeTagName }}」下的文章（{{ total }} 篇）
      <button class="home__clear" @click="selectTag('')">清除筛选</button>
    </p>

    <!-- 加载中 -->
    <SkeletonList v-if="loading" :count="3" />

    <!-- 加载失败：「失败」与「没有数据」必须区分，否则用户不知道该刷新还是该等待 -->
    <EmptyState
      v-else-if="error"
      title="加载失败"
      :hint="error"
      action-text="回到首页"
      action-to="/"
    />

    <!-- 空状态 -->
    <EmptyState
      v-else-if="!articles.length"
      :title="currentTag ? '这个标签下还没有文章' : '还没有发布任何文章'"
      hint="文章发布后会出现在这里。"
      action-text="看看所有标签"
      action-to="/tags"
    />

    <template v-else>
      <div class="home__list">
        <ArticleCard v-for="article in articles" :key="article.id" :article="article" />
      </div>
      <Pagination :page="currentPage" :pages="pages" @change="changePage" />
    </template>

    <p class="home__more">
      也可以 <RouterLink to="/archive">按归档浏览</RouterLink> 或
      <RouterLink to="/tags">查看全部标签</RouterLink>。
    </p>
  </section>
</template>

<style scoped>
.home {
  padding-top: var(--space-6);
}

.home__hero {
  padding-bottom: var(--space-6);
  border-bottom: 1px solid var(--color-border);
}

.home__title {
  font-size: var(--text-3xl);
  color: var(--color-heading);
}

.home__subtitle {
  margin-top: var(--space-3);
  font-size: var(--text-lg);
  color: var(--color-text-secondary);
}

.filter {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-2);
  margin-top: var(--space-6);
}

.filter__item {
  display: inline-flex;
  align-items: center;
  gap: var(--space-1);
  height: 32px;
  padding: 0 var(--space-3);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-full);
  background: var(--color-bg);
  color: var(--color-text-secondary);
  font-size: var(--text-sm);
  font-family: inherit;
  cursor: pointer;
  transition: all var(--transition);
}

.filter__item:hover {
  border-color: var(--color-primary);
  color: var(--color-primary);
}

.filter__item--active {
  border-color: var(--color-primary);
  background: var(--color-primary);
  color: #fff;
}

.filter__count {
  font-size: var(--text-xs);
  opacity: 0.7;
}

.home__filtering {
  margin-top: var(--space-4);
  font-size: var(--text-sm);
  color: var(--color-text-secondary);
}

.home__clear {
  margin-left: var(--space-2);
  border: none;
  background: none;
  color: var(--color-primary);
  font-size: var(--text-sm);
  font-family: inherit;
  cursor: pointer;
}

.home__list {
  display: flex;
  flex-direction: column;
  gap: var(--space-5);
  margin-top: var(--space-6);
}

.home__more {
  margin-top: var(--space-7);
  padding-top: var(--space-5);
  border-top: 1px solid var(--color-border);
  font-size: var(--text-sm);
  color: var(--color-text-muted);
}

.home__more a {
  color: var(--color-primary);
  text-decoration: none;
}

.home__more a:hover {
  text-decoration: underline;
}
</style>
