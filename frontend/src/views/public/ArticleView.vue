<script setup lang="ts">
import { onMounted, ref, watch } from 'vue'
import { RouterLink, useRoute } from 'vue-router'
import { getArticle } from '@/api/blog'
import EmptyState from '@/components/public/EmptyState.vue'
import SkeletonList from '@/components/public/SkeletonList.vue'
import type { ArticleDetail } from '@/types/blog'
import { formatDate } from '@/utils/date'

const route = useRoute()

const article = ref<ArticleDetail | null>(null)
const loading = ref(true)
const error = ref('')
const notFound = ref(false)

const contentEl = ref<HTMLElement | null>(null)
const toc = ref<{ id: string; text: string; level: number }[]>([])

/**
 * 从已渲染的正文里提取 h2/h3 生成目录（文档 06 表格 8：目录由 DOM 自动生成，不手写）。
 *
 * 【这里踩过一个坑，把原因写清楚】
 *
 * 第一版：赋值 article 之后 `await nextTick()` 再查 DOM —— 目录永远为空。
 * 第二版：改成轮询等 contentEl 出现 —— 还是空，而且这次是「死等」。
 *
 * 真正的原因是**加载流程与 DOM 渲染互相等待**：
 *
 *     loading.value = true
 *     article.value = await getArticle(slug)
 *     await buildToc()              ← 此时模板还在 v-if="loading" 分支
 *     finally { loading.value = false }   ← buildToc 返回后 loading 才变 false
 *
 * 也就是说 buildToc 运行时，markdown-body 与 contentEl **根本还没被创建**；
 * 而 contentEl 要等 loading 变 false 才出现，loading 又要等 buildToc 返回。
 * 无论 nextTick 还是轮询，都是在等一个此刻不可能存在的东西。
 *
 * 正确做法是把「目录生成」从加载流程里摘出来，改为**监听正文内容**：
 * 只要 contentEl 被赋值（说明 v-else 分支已经渲染出来了），就重建目录。
 * 这样既不依赖 tick 数量，也不依赖加载顺序。
 */
function rebuildToc() {
  const el = contentEl.value
  toc.value = []
  if (!el) return

  const headings = el.querySelectorAll('h2, h3')
  headings.forEach((node, i) => {
    const id = `heading-${i}`
    node.id = id
    toc.value.push({
      id,
      text: node.textContent ?? '',
      level: node.tagName === 'H2' ? 2 : 3,
    })
  })
}

// flush: 'post' 让回调在 DOM 更新之后执行 —— ref 此刻已经指向真实元素。
// 监听 contentEl 而不是 article：ref 赋值发生在元素挂载那一刻，
// 这正是「DOM 已经就绪」的准确信号。
watch(contentEl, rebuildToc, { flush: 'post' })

async function load() {
  const slug = String(route.params.slug ?? '')
  if (!slug) return

  loading.value = true
  error.value = ''
  notFound.value = false
  article.value = null
  toc.value = []

  try {
    article.value = await getArticle(slug)
    // 目录不在这里生成 —— 见上方 watch(contentEl)。
    // 这里只负责把数据放进去，渲染与目录由 Vue 的响应式流程驱动。
  } catch (e) {
    // 草稿在后端返回 404（不是 403），所以「不存在」与「未发布」在这里表现为同一种结果。
    // 这是刻意的：告诉访客「文章存在但你没权限」等于泄露了草稿的存在。
    const code = (e as { code?: number })?.code
    if (code === 40400) {
      notFound.value = true
    } else {
      error.value = e instanceof Error ? e.message : '加载失败'
    }
  } finally {
    loading.value = false
  }
}

function scrollTo(id: string) {
  const el = document.getElementById(id)
  if (el) {
    // 减去固定页头高度，否则标题会被页头盖住
    const top = el.getBoundingClientRect().top + window.scrollY - 80
    window.scrollTo({ top, behavior: 'smooth' })
  }
}

onMounted(load)
watch(() => route.params.slug, load)
</script>

<template>
  <section class="post">
    <SkeletonList v-if="loading" :count="1" />

    <EmptyState
      v-else-if="notFound"
      title="这篇文章不存在或尚未发布"
      hint="可能是链接输错了，或者文章已被移除。"
      action-text="回到首页"
      action-to="/"
    />

    <EmptyState
      v-else-if="error"
      title="加载失败"
      :hint="error"
      action-text="回到首页"
      action-to="/"
    />

    <template v-else-if="article">
      <div class="post__layout">
        <article class="post__main">
          <header class="post__header">
            <h1 class="post__title">{{ article.title }}</h1>
            <div class="post__meta">
              <time :datetime="article.published_at ?? article.created_at">
                {{ formatDate(article.published_at ?? article.created_at) }}
              </time>
              <span class="post__sep">·</span>
              <span>{{ article.view_count }} 次阅读</span>
            </div>
            <div v-if="article.tags.length" class="post__tags">
              <RouterLink
                v-for="tag in article.tags"
                :key="tag.id"
                class="post__tag"
                :to="`/tags/${tag.slug}`"
              >
                {{ tag.name }}
              </RouterLink>
            </div>
          </header>

          <hr class="post__divider" />

          <!-- 正文：后端已完成 Markdown → HTML → bleach 白名单过滤（ADR-06）。
               这里只负责插入，阅读样式由 markdown.css 的 .markdown-body 控制。 -->
          <div ref="contentEl" class="markdown-body" v-html="article.content_html" />

          <!-- 上一篇 / 下一篇（文档 06 表格 8：没有相邻文章时该侧不显示）
               prev = 更早发布的一篇，next = 更晚发布的一篇。
               两篇都不存在时整块不渲染，而不是留两个空位。 -->
          <nav v-if="article.prev || article.next" class="neighbors" aria-label="相邻文章">
            <RouterLink
              v-if="article.prev"
              class="neighbors__item neighbors__item--prev"
              :to="`/posts/${article.prev.slug}`"
            >
              <span class="neighbors__label">← 上一篇</span>
              <span class="neighbors__title">{{ article.prev.title }}</span>
            </RouterLink>
            <span v-else class="neighbors__spacer" />

            <RouterLink
              v-if="article.next"
              class="neighbors__item neighbors__item--next"
              :to="`/posts/${article.next.slug}`"
            >
              <span class="neighbors__label">下一篇 →</span>
              <span class="neighbors__title">{{ article.next.title }}</span>
            </RouterLink>
          </nav>

          <footer class="post__footer">
            <RouterLink class="post__back" to="/">← 返回首页</RouterLink>
          </footer>
        </article>

        <!-- 目录：仅桌面端显示（文档 06 表格 4：窄屏隐藏） -->
        <aside v-if="toc.length" class="post__aside">
          <nav class="toc" aria-label="本文目录">
            <p class="toc__title">本文目录</p>
            <ul class="toc__list">
              <li v-for="item in toc" :key="item.id" :class="`toc__item toc__item--h${item.level}`">
                <button class="toc__link" @click="scrollTo(item.id)">{{ item.text }}</button>
              </li>
            </ul>
          </nav>
        </aside>
      </div>
    </template>
  </section>
</template>

<style scoped>
.post {
  padding-top: var(--space-6);
}

.post__layout {
  display: block;
}

@media (min-width: 1024px) {
  /* 两栏布局仅在 ≥1024px 启用（文档 06 表格 4） */
  .post__layout {
    display: grid;
    grid-template-columns: minmax(0, var(--content-max)) 200px;
    gap: var(--space-7);
    justify-content: center;
    align-items: start;
  }
}

.post__header {
  padding-bottom: var(--space-5);
}

.post__title {
  font-size: var(--text-3xl);
  font-weight: 700;
  line-height: var(--leading-tight);
  color: var(--color-heading);
}

.post__meta {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  margin-top: var(--space-4);
  font-size: var(--text-sm);
  color: var(--color-text-secondary);
}

.post__sep {
  color: var(--color-text-muted);
}

.post__tags {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-2);
  margin-top: var(--space-4);
}

.post__tag {
  padding: 2px var(--space-2);
  border-radius: var(--radius-sm);
  background: var(--color-bg-soft);
  color: var(--color-text-secondary);
  font-size: var(--text-xs);
  text-decoration: none;
  transition: all var(--transition);
}

.post__tag:hover {
  background: var(--color-primary);
  color: #fff;
}

.post__divider {
  height: 1px;
  border: none;
  margin: 0;
  background: var(--color-border);
}

.post__footer {
  margin-top: var(--space-6);
  padding-top: var(--space-5);
  border-top: 1px solid var(--color-border);
}

/* 相邻文章：两栏对照，缺失的一侧用等宽占位保持另一侧不跑位 */
.neighbors {
  display: grid;
  grid-template-columns: 1fr;
  gap: var(--space-4);
  margin-top: var(--space-7);
  padding-top: var(--space-6);
  border-top: 1px solid var(--color-border);
}

@media (min-width: 640px) {
  .neighbors {
    grid-template-columns: 1fr 1fr;
  }
}

.neighbors__spacer {
  display: none;
}

.neighbors__item {
  display: flex;
  flex-direction: column;
  gap: var(--space-1);
  padding: var(--space-4);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
  text-decoration: none;
  transition: all var(--transition);
}

.neighbors__item:hover {
  border-color: var(--color-primary);
  background: var(--color-bg-soft);
}

.neighbors__item--next {
  text-align: right;
}

.neighbors__label {
  font-size: var(--text-xs);
  color: var(--color-text-muted);
}

.neighbors__title {
  font-size: var(--text-base);
  color: var(--color-heading);
  line-height: var(--leading-tight);
}

.post__back {
  font-size: var(--text-sm);
  color: var(--color-primary);
  text-decoration: none;
}

.post__back:hover {
  text-decoration: underline;
}

.post__aside {
  position: sticky;
  top: calc(var(--header-height) + var(--space-5));
  display: none;
}

@media (min-width: 1024px) {
  .post__aside {
    display: block;
  }
}

.toc {
  padding-left: var(--space-4);
  border-left: 2px solid var(--color-border);
}

.toc__title {
  margin-bottom: var(--space-3);
  font-size: var(--text-xs);
  font-weight: 600;
  color: var(--color-text-muted);
  letter-spacing: 0.06em;
}

.toc__list {
  list-style: none;
  padding: 0;
  margin: 0;
}

.toc__item--h3 {
  padding-left: var(--space-3);
}

.toc__link {
  display: block;
  width: 100%;
  padding: var(--space-1) 0;
  border: none;
  background: none;
  color: var(--color-text-secondary);
  font-size: var(--text-sm);
  font-family: inherit;
  text-align: left;
  cursor: pointer;
  transition: color var(--transition);
}

.toc__link:hover {
  color: var(--color-primary);
}
</style>
