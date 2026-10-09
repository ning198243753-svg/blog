<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { RouterLink } from 'vue-router'
import { getArchive } from '@/api/blog'
import EmptyState from '@/components/public/EmptyState.vue'
import SkeletonList from '@/components/public/SkeletonList.vue'
import type { ArchiveGroup } from '@/types/blog'
import { formatMonthDay } from '@/utils/date'

const groups = ref<ArchiveGroup[]>([])
const loading = ref(true)
const error = ref('')

/**
 * 接口返回的是「年月分组」的平铺数组，这里再按年聚合一次。
 *
 * 为什么不在后端直接返回三级结构：
 * 「年」是纯展示层的聚合 —— 归档接口只负责按月切分，
 * 前端按年归并的成本是几行代码，而多一层接口结构会让
 * 将来「按月分页」之类的改动变复杂。
 */
const years = computed(() => {
  const map = new Map<number, { year: number; count: number; months: ArchiveGroup[] }>()
  for (const g of groups.value) {
    let entry = map.get(g.year)
    if (!entry) {
      entry = { year: g.year, count: 0, months: [] }
      map.set(g.year, entry)
    }
    entry.months.push(g)
    entry.count += g.count
  }
  return [...map.values()].sort((a, b) => b.year - a.year)
})

const totalCount = computed(() => groups.value.reduce((sum, g) => sum + g.count, 0))

onMounted(async () => {
  try {
    groups.value = await getArchive()
  } catch (e) {
    error.value = e instanceof Error ? e.message : '归档加载失败'
  } finally {
    loading.value = false
  }
})
</script>

<template>
  <section class="archive">
    <header class="archive__header">
      <h1 class="archive__title">归档</h1>
      <p v-if="!loading && !error" class="archive__subtitle">
        共 {{ totalCount }} 篇文章，按年月排列。
      </p>
    </header>

    <SkeletonList v-if="loading" :count="2" />

    <EmptyState
      v-else-if="error"
      title="加载失败"
      :hint="error"
      action-text="回到首页"
      action-to="/"
    />

    <EmptyState
      v-else-if="!years.length"
      title="还没有归档内容"
      hint="文章发布后会按月归入这里。"
      action-text="回到首页"
      action-to="/"
    />

    <!-- 年 → 月 → 文章 三级分组（文档 06 表格 10）
         不做折叠交互：归档页的价值在于一眼扫完。 -->
    <div v-else class="archive__body">
      <section v-for="y in years" :key="y.year" class="year">
        <h2 class="year__title">
          {{ y.year }} 年
          <span class="year__count">{{ y.count }} 篇</span>
        </h2>

        <div v-for="m in y.months" :key="`${y.year}-${m.month}`" class="month">
          <h3 class="month__title">{{ m.month }} 月</h3>
          <ul class="month__list">
            <li v-for="a in m.articles" :key="a.id" class="month__item">
              <time class="month__date" :datetime="a.published_at ?? a.created_at">
                {{ formatMonthDay(a.published_at ?? a.created_at) }}
              </time>
              <RouterLink class="month__link" :to="`/posts/${a.slug}`">
                {{ a.title }}
              </RouterLink>
            </li>
          </ul>
        </div>
      </section>
    </div>
  </section>
</template>

<style scoped>
.archive {
  padding-top: var(--space-6);
}

.archive__header {
  padding-bottom: var(--space-5);
  border-bottom: 1px solid var(--color-border);
}

.archive__title {
  font-size: var(--text-3xl);
  color: var(--color-heading);
}

.archive__subtitle {
  margin-top: var(--space-2);
  font-size: var(--text-sm);
  color: var(--color-text-secondary);
}

.archive__body {
  margin-top: var(--space-6);
}

.year + .year {
  margin-top: var(--space-7);
}

.year__title {
  display: flex;
  align-items: baseline;
  gap: var(--space-3);
  padding-bottom: var(--space-2);
  font-size: var(--text-2xl);
  color: var(--color-heading);
}

.year__count {
  font-size: var(--text-sm);
  font-weight: 400;
  color: var(--color-text-muted);
}

.month {
  margin-top: var(--space-5);
}

.month__title {
  margin-bottom: var(--space-3);
  font-size: var(--text-lg);
  font-weight: 600;
  color: var(--color-text-secondary);
}

.month__list {
  list-style: none;
  padding: 0;
  margin: 0;
  border-left: 2px solid var(--color-border);
}

.month__item {
  display: flex;
  align-items: baseline;
  gap: var(--space-4);
  padding: var(--space-2) 0 var(--space-2) var(--space-4);
  position: relative;
}

/* 时间轴圆点：让「一条时间线」这件事在视觉上成立 */
.month__item::before {
  content: '';
  position: absolute;
  left: -5px;
  top: 14px;
  width: 8px;
  height: 8px;
  border-radius: var(--radius-full);
  background: var(--color-border);
  transition: background var(--transition);
}

.month__item:hover::before {
  background: var(--color-primary);
}

.month__date {
  flex-shrink: 0;
  width: 52px;
  font-size: var(--text-sm);
  color: var(--color-text-muted);
  font-variant-numeric: tabular-nums;
}

.month__link {
  color: var(--color-text);
  text-decoration: none;
  transition: color var(--transition);
}

.month__link:hover {
  color: var(--color-primary);
}
</style>
