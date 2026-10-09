<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { RouterLink, useRoute, useRouter } from 'vue-router'
import { deleteArticle, getAdminArticles } from '@/api/admin'
import EmptyState from '@/components/public/EmptyState.vue'
import Pagination from '@/components/public/Pagination.vue'
import SkeletonList from '@/components/public/SkeletonList.vue'
import type { ArticleListItem } from '@/types/blog'
import { formatDate } from '@/utils/date'

const route = useRoute()
const router = useRouter()

const items = ref<ArticleListItem[]>([])
const total = ref(0)
const pages = ref(0)
const loading = ref(true)
const error = ref('')

/**
 * 筛选与分页状态全部来自 URL（M2 已确立的规则）。
 *
 * 【为什么状态必须放 URL 而不是本地 ref】
 * 1. 刷新页面后筛选条件还在
 * 2. 可以直接把「草稿列表第 2 页」的链接发给别人（或收藏）
 * 3. 浏览器前进/后退能正确回到上一个筛选状态
 * 本地 ref 在这三点上全部失效，而用户会认为它们是理所当然的。
 */
const status = computed(() => {
  const raw = route.query.status
  return raw === 'draft' || raw === 'published' ? raw : ''
})
const keyword = computed(() => (typeof route.query.q === 'string' ? route.query.q : ''))
const page = computed(() => {
  const raw = Number(route.query.page)
  return Number.isFinite(raw) && raw >= 1 ? Math.floor(raw) : 1
})

/** 搜索框的本地输入值：只在提交时写进 URL，输入过程中不请求 */
const searchInput = ref(keyword.value)

async function load(): Promise<void> {
  loading.value = true
  error.value = ''
  try {
    const data = await getAdminArticles({
      page: page.value,
      page_size: 10,
      status: status.value || undefined,
      q: keyword.value || undefined,
    })
    items.value = data.items
    total.value = data.total
    pages.value = data.pages
  } catch (e) {
    error.value = e instanceof Error ? e.message : '加载失败'
    items.value = []
    total.value = 0
    pages.value = 0
  } finally {
    loading.value = false
  }
}

// immediate: 首次进入即加载；watch 而非 onMounted 是因为
// 切换筛选条件时 URL 变化也要重新加载。
watch(() => route.query, load, { immediate: true })

// URL 的 q 变化时（含前进/后退）同步回输入框，
// 否则用户按后退键会看到输入框里的词和实际结果不一致
watch(keyword, (value) => {
  searchInput.value = value
})

function updateQuery(patch: Record<string, string | number | undefined>): void {
  const next = { ...route.query, ...patch }
  for (const [key, value] of Object.entries(next)) {
    if (value === undefined || value === '' || value === null) delete next[key]
  }
  // 每次改变筛选条件都要回到第 1 页：
  // 否则「在第 5 页筛选出只有 2 条结果」会显示空白，
  // 用户会以为筛选坏了。
  if (!('page' in patch)) delete next.page

  router.push({ path: '/admin/articles', query: next })
}

function selectStatus(value: string): void {
  updateQuery({ status: value || undefined })
}

function submitSearch(): void {
  updateQuery({ q: searchInput.value.trim() || undefined })
}

function changePage(next: number): void {
  updateQuery({ page: next === 1 ? undefined : next })
}

// ---- 删除 ----
//
// 【为什么要二次确认，而且不只是「确定吗」】
// 删除是物理删除，SQLite 没有回收站。
// 确认框里带上标题，是为了让用户能看清自己点的是哪一行 ——
// 表格里误点相邻行的删除按钮是很常见的事。
const deleting = ref<ArticleListItem | null>(null)
const deleteError = ref('')
const deleteSubmitting = ref(false)

function askDelete(item: ArticleListItem): void {
  deleting.value = item
  deleteError.value = ''
}

function cancelDelete(): void {
  deleting.value = null
  deleteError.value = ''
}

async function confirmDelete(): Promise<void> {
  if (!deleting.value || deleteSubmitting.value) return
  deleteSubmitting.value = true
  deleteError.value = ''

  try {
    await deleteArticle(deleting.value.id)
    deleting.value = null

    // 【删掉当前页最后一条时要回退一页】
    // 否则会停在一个空列表上，而实际上数据还在前一页 ——
    // 用户会以为「删完之后全没了」。
    const isLastItemOnPage = items.value.length === 1 && page.value > 1
    if (isLastItemOnPage) {
      updateQuery({ page: page.value - 1 })
    } else {
      await load()
    }
  } catch (e) {
    deleteError.value = e instanceof Error ? e.message : '删除失败'
  } finally {
    deleteSubmitting.value = false
  }
}

/** 状态徽标的文案 */
function statusLabel(value: string): string {
  return value === 'published' ? '已发布' : '草稿'
}
</script>

<template>
  <section class="admin-articles">
    <header class="admin-articles__head">
      <div>
        <h1 class="admin-articles__title">文章管理</h1>
        <p class="admin-articles__count">
          共 {{ total }} 篇<template v-if="status || keyword">（已筛选）</template>
        </p>
      </div>
      <RouterLink to="/admin/articles/new" class="admin-articles__new">新建文章</RouterLink>
    </header>

    <!-- 筛选条 -->
    <div class="admin-articles__filters">
      <div class="admin-articles__tabs">
        <button
          v-for="tab in [
            { value: '', label: '全部' },
            { value: 'published', label: '已发布' },
            { value: 'draft', label: '草稿' },
          ]"
          :key="tab.value"
          type="button"
          class="admin-articles__tab"
          :class="{ 'admin-articles__tab--active': status === tab.value }"
          @click="selectStatus(tab.value)"
        >
          {{ tab.label }}
        </button>
      </div>

      <form class="admin-articles__search" @submit.prevent="submitSearch">
        <input
          v-model="searchInput"
          class="admin-articles__input"
          type="search"
          placeholder="搜索标题或摘要"
          maxlength="50"
        />
        <button type="submit" class="admin-articles__search-btn">搜索</button>
      </form>
    </div>

    <SkeletonList v-if="loading" :count="5" />

    <EmptyState
      v-else-if="error"
      title="加载失败"
      :hint="error"
      action-text="重试"
      action
      @action="load"
    />

    <EmptyState
      v-else-if="items.length === 0"
      :title="keyword || status ? '没有符合条件的文章' : '还没有任何文章'"
      :hint="keyword || status ? '试试放宽筛选条件' : '从新建第一篇文章开始'"
      action-text="新建文章"
      action-to="/admin/articles/new"
    />

    <div v-else class="admin-articles__table-wrap">
      <table class="admin-articles__table">
        <thead>
          <tr>
            <th class="admin-articles__th-title">标题</th>
            <th>状态</th>
            <th>标签</th>
            <th>阅读</th>
            <th>发布时间</th>
            <th class="admin-articles__th-ops">操作</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="item in items" :key="item.id">
            <td class="admin-articles__td-title">
              <RouterLink
                v-if="item.status === 'published'"
                :to="`/posts/${item.slug}`"
                target="_blank"
                class="admin-articles__link"
                :title="item.title"
              >
                {{ item.title }}
              </RouterLink>
              <span v-else class="admin-articles__draft-title" :title="item.title">
                {{ item.title }}
              </span>
            </td>
            <td>
              <span
                class="admin-articles__badge"
                :class="`admin-articles__badge--${item.status}`"
              >
                {{ statusLabel(item.status) }}
              </span>
            </td>
            <td class="admin-articles__td-tags">
              <span v-if="item.tags.length === 0" class="admin-articles__muted">—</span>
              <span v-for="tag in item.tags" :key="tag.id" class="admin-articles__tag">
                {{ tag.name }}
              </span>
            </td>
            <td class="admin-articles__td-num">{{ item.view_count }}</td>
            <td class="admin-articles__td-date">
              {{ item.published_at ? formatDate(item.published_at) : '—' }}
            </td>
            <td class="admin-articles__td-ops">
              <RouterLink :to="`/admin/articles/${item.id}/edit`" class="admin-articles__op">
                编辑
              </RouterLink>
              <button
                type="button"
                class="admin-articles__op admin-articles__op--danger"
                @click="askDelete(item)"
              >
                删除
              </button>
            </td>
          </tr>
        </tbody>
      </table>
    </div>

    <Pagination
      v-if="!loading && !error && pages > 1"
      :page="page"
      :pages="pages"
      @change="changePage"
    />

    <!-- 删除确认 -->
    <div v-if="deleting" class="modal" @click.self="cancelDelete">
      <div class="modal__box" role="dialog" aria-modal="true">
        <h2 class="modal__title">确认删除</h2>
        <p class="modal__text">
          即将删除《<strong>{{ deleting.title }}</strong>》。
        </p>
        <p class="modal__warn">删除后无法恢复，关联的标签也会一并解除。</p>
        <p v-if="deleteError" class="modal__error">{{ deleteError }}</p>
        <div class="modal__actions">
          <button
            type="button"
            class="modal__btn"
            :disabled="deleteSubmitting"
            @click="cancelDelete"
          >
            取消
          </button>
          <button
            type="button"
            class="modal__btn modal__btn--danger"
            :disabled="deleteSubmitting"
            @click="confirmDelete"
          >
            {{ deleteSubmitting ? '删除中…' : '确认删除' }}
          </button>
        </div>
      </div>
    </div>
  </section>
</template>

<style scoped>
.admin-articles__head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: var(--space-4);
  margin-bottom: var(--space-5);
}

.admin-articles__title {
  font-size: var(--text-2xl);
  font-weight: 600;
  color: var(--color-heading);
}

.admin-articles__count {
  margin-top: var(--space-1);
  font-size: var(--text-sm);
  color: var(--color-text-muted);
}

.admin-articles__new {
  flex-shrink: 0;
  padding: var(--space-2) var(--space-4);
  border-radius: var(--radius-md);
  background: var(--color-primary);
  font-size: var(--text-sm);
  color: #fff;
}

.admin-articles__new:hover {
  opacity: 0.9;
}

/* ---- 筛选 ---- */
.admin-articles__filters {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-3);
  margin-bottom: var(--space-4);
}

.admin-articles__tabs {
  display: flex;
  gap: var(--space-1);
}

.admin-articles__tab {
  padding: var(--space-1) var(--space-3);
  border: 1px solid transparent;
  border-radius: var(--radius-md);
  background: transparent;
  font-size: var(--text-sm);
  font-family: inherit;
  color: var(--color-text-secondary);
  cursor: pointer;
  transition: all var(--transition);
}

.admin-articles__tab:hover {
  color: var(--color-heading);
}

.admin-articles__tab--active {
  background: var(--color-bg);
  border-color: var(--color-border);
  color: var(--color-primary);
  font-weight: 600;
}

.admin-articles__search {
  display: flex;
  gap: var(--space-2);
}

.admin-articles__input {
  width: 180px;
  padding: var(--space-1) var(--space-3);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
  background: var(--color-bg);
  font-size: var(--text-sm);
  font-family: inherit;
  color: var(--color-text);
}

.admin-articles__input:focus {
  outline: none;
  border-color: var(--color-primary);
}

.admin-articles__search-btn {
  padding: var(--space-1) var(--space-3);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
  background: var(--color-bg);
  font-size: var(--text-sm);
  font-family: inherit;
  color: var(--color-text-secondary);
  cursor: pointer;
}

.admin-articles__search-btn:hover {
  border-color: var(--color-primary);
  color: var(--color-primary);
}

/* ---- 表格 ---- */
.admin-articles__table-wrap {
  overflow-x: auto;
  background: var(--color-bg);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-lg);
}

.admin-articles__table {
  width: 100%;
  border-collapse: collapse;
  font-size: var(--text-sm);
}

.admin-articles__table th {
  padding: var(--space-3) var(--space-4);
  text-align: left;
  font-weight: 600;
  color: var(--color-text-secondary);
  border-bottom: 1px solid var(--color-border);
  white-space: nowrap;
}

.admin-articles__table td {
  padding: var(--space-3) var(--space-4);
  border-bottom: 1px solid var(--color-border);
  color: var(--color-text);
  vertical-align: middle;
}

.admin-articles__table tr:last-child td {
  border-bottom: none;
}

.admin-articles__th-title,
.admin-articles__td-title {
  min-width: 200px;
  max-width: 380px;
}

.admin-articles__link {
  display: block;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  color: var(--color-heading);
}

.admin-articles__link:hover {
  color: var(--color-primary);
}

.admin-articles__draft-title {
  display: block;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  color: var(--color-text-secondary);
}

.admin-articles__badge {
  display: inline-block;
  padding: 2px var(--space-2);
  border-radius: var(--radius-sm);
  font-size: var(--text-xs);
  white-space: nowrap;
}

.admin-articles__badge--published {
  background: var(--color-bg-soft);
  color: var(--color-primary);
}

/* 草稿用中性灰，不用警告色：草稿是正常状态，不是错误 */
.admin-articles__badge--draft {
  background: var(--color-bg-soft);
  color: var(--color-text-muted);
}

.admin-articles__td-tags {
  max-width: 180px;
}

.admin-articles__tag {
  display: inline-block;
  margin-right: var(--space-1);
  padding: 1px var(--space-2);
  border-radius: var(--radius-sm);
  background: var(--color-bg-soft);
  font-size: var(--text-xs);
  color: var(--color-text-secondary);
  white-space: nowrap;
}

.admin-articles__muted {
  color: var(--color-text-muted);
}

.admin-articles__td-num,
.admin-articles__td-date {
  color: var(--color-text-secondary);
  white-space: nowrap;
}

.admin-articles__th-ops,
.admin-articles__td-ops {
  text-align: right;
  white-space: nowrap;
}

.admin-articles__op {
  padding: var(--space-1) var(--space-2);
  border: none;
  background: transparent;
  font-size: var(--text-sm);
  font-family: inherit;
  color: var(--color-primary);
  cursor: pointer;
}

.admin-articles__op:hover {
  text-decoration: underline;
}

.admin-articles__op--danger {
  color: var(--color-danger);
}

/* ---- 删除确认弹层 ---- */
.modal {
  position: fixed;
  inset: 0;
  z-index: var(--z-modal);
  display: flex;
  align-items: center;
  justify-content: center;
  padding: var(--space-4);
  background: rgba(0, 0, 0, 0.4);
}

.modal__box {
  width: 100%;
  max-width: 420px;
  padding: var(--space-5);
  background: var(--color-bg);
  border-radius: var(--radius-lg);
  box-shadow: var(--shadow-md);
}

.modal__title {
  font-size: var(--text-lg);
  font-weight: 600;
  color: var(--color-heading);
}

.modal__text {
  margin-top: var(--space-3);
  font-size: var(--text-sm);
  color: var(--color-text);
  word-break: break-word;
}

.modal__warn {
  margin-top: var(--space-2);
  font-size: var(--text-sm);
  color: var(--color-danger);
}

.modal__error {
  margin-top: var(--space-2);
  font-size: var(--text-sm);
  color: var(--color-danger);
}

.modal__actions {
  display: flex;
  justify-content: flex-end;
  gap: var(--space-3);
  margin-top: var(--space-5);
}

.modal__btn {
  padding: var(--space-2) var(--space-4);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
  background: var(--color-bg);
  font-size: var(--text-sm);
  font-family: inherit;
  color: var(--color-text-secondary);
  cursor: pointer;
}

.modal__btn:hover:not(:disabled) {
  border-color: var(--color-text-muted);
}

.modal__btn--danger {
  border-color: var(--color-danger);
  background: var(--color-danger);
  color: #fff;
}

.modal__btn--danger:hover:not(:disabled) {
  opacity: 0.9;
}

.modal__btn:disabled {
  cursor: not-allowed;
  opacity: 0.6;
}
</style>
