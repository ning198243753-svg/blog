<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import {
  createTag,
  deleteTag,
  getAdminTags,
  getTagUsage,
  updateTag,
} from '@/api/admin'
import EmptyState from '@/components/public/EmptyState.vue'
import SkeletonList from '@/components/public/SkeletonList.vue'
import type { AdminTag, TagUsage } from '@/types/admin'

const tags = ref<AdminTag[]>([])
const loading = ref(true)
const loadError = ref('')

const newName = ref('')
const newColor = ref('#1e5cb8')
const creating = ref(false)
const createError = ref('')

/** 正在重命名的标签 id 与输入值（行内编辑） */
const editingId = ref<number | null>(null)
const editingName = ref('')
const editingError = ref('')
const savingEdit = ref(false)

/** 删除确认：先查 usage 再展示，让确认文案有具体数字 */
const deleteTarget = ref<{ tag: AdminTag; usage: TagUsage | null } | null>(null)
const deleteLoading = ref(false)
const deleteError = ref('')
const deleteSubmitting = ref(false)

async function load(): Promise<void> {
  loading.value = true
  loadError.value = ''
  try {
    tags.value = await getAdminTags()
  } catch (e) {
    loadError.value = e instanceof Error ? e.message : '加载失败'
    tags.value = []
  } finally {
    loading.value = false
  }
}

onMounted(load)

const canCreate = computed(() => newName.value.trim().length > 0 && !creating.value)

async function handleCreate(): Promise<void> {
  if (!canCreate.value) return
  creating.value = true
  createError.value = ''
  try {
    await createTag(newName.value.trim(), newColor.value || null)
    newName.value = ''
    await load()
  } catch (e) {
    // 重名会返回 40003「标签已存在」——这是预期内的用户错误，
    // 原样显示后端文案即可，前端不重复判断一次重名。
    createError.value = e instanceof Error ? e.message : '创建失败'
  } finally {
    creating.value = false
  }
}

// ---- 重命名 ----
function startEdit(tag: AdminTag): void {
  editingId.value = tag.id
  editingName.value = tag.name
  editingError.value = ''
}

function cancelEdit(): void {
  editingId.value = null
  editingName.value = ''
  editingError.value = ''
}

async function submitEdit(tag: AdminTag): Promise<void> {
  const name = editingName.value.trim()
  if (!name || savingEdit.value) return

  if (name === tag.name) {
    cancelEdit()
    return
  }

  savingEdit.value = true
  editingError.value = ''
  try {
    await updateTag(tag.id, { name })
    cancelEdit()
    await load()
  } catch (e) {
    editingError.value = e instanceof Error ? e.message : '保存失败'
  } finally {
    savingEdit.value = false
  }
}

// ---- 删除 ----
async function askDelete(tag: AdminTag): Promise<void> {
  deleteTarget.value = { tag, usage: null }
  deleteLoading.value = true
  deleteError.value = ''
  try {
    const usage = await getTagUsage(tag.id)
    // 用户可能在请求返回前就点了取消 —— 此时不要再写回状态
    if (deleteTarget.value?.tag.id === tag.id) {
      deleteTarget.value = { tag, usage }
    }
  } catch (e) {
    if (deleteTarget.value?.tag.id === tag.id) {
      deleteError.value = e instanceof Error ? e.message : '无法查询使用情况'
    }
  } finally {
    deleteLoading.value = false
  }
}

function cancelDelete(): void {
  deleteTarget.value = null
  deleteError.value = ''
}

async function confirmDelete(): Promise<void> {
  if (!deleteTarget.value || deleteSubmitting.value) return
  deleteSubmitting.value = true
  deleteError.value = ''
  try {
    // 【必须带 force】
    // 后端规定：标签还挂在文章上时不带 force 会返回 409。
    // 前端已经在上一步把影响范围（几篇文章）显示给用户并取得了确认，
    // 所以这里才是 force 的正当使用时机。
    await deleteTag(deleteTarget.value.tag.id, true)
    deleteTarget.value = null
    await load()
  } catch (e) {
    deleteError.value = e instanceof Error ? e.message : '删除失败'
  } finally {
    deleteSubmitting.value = false
  }
}
</script>

<template>
  <section class="tags">
    <header class="tags__head">
      <h1 class="tags__title">标签管理</h1>
      <p class="tags__count">共 {{ tags.length }} 个标签</p>
    </header>

    <!-- 新建 -->
    <form class="tags__create" @submit.prevent="handleCreate">
      <input
        v-model="newName"
        class="tags__input"
        type="text"
        placeholder="新标签名称"
        maxlength="30"
        :disabled="creating"
      />
      <label class="tags__color">
        <span class="tags__color-label">颜色</span>
        <input v-model="newColor" type="color" class="tags__color-input" />
      </label>
      <button type="submit" class="tags__btn tags__btn--primary" :disabled="!canCreate">
        {{ creating ? '创建中…' : '新建标签' }}
      </button>
    </form>
    <p v-if="createError" class="tags__alert">{{ createError }}</p>

    <SkeletonList v-if="loading" :count="3" />

    <EmptyState
      v-else-if="loadError"
      title="加载失败"
      :hint="loadError"
      action-text="重试"
      action
      @action="load"
    />

    <EmptyState
      v-else-if="tags.length === 0"
      title="还没有标签"
      hint="在上方输入名称即可创建第一个标签"
    />

    <div v-else class="tags__list">
      <div v-for="tag in tags" :key="tag.id" class="tags__row">
        <!-- 重命名态 -->
        <template v-if="editingId === tag.id">
          <input
            v-model="editingName"
            class="tags__input tags__input--inline"
            type="text"
            maxlength="30"
            @keydown.enter.prevent="submitEdit(tag)"
            @keydown.esc="cancelEdit"
          />
          <span class="tags__slug">{{ tag.slug }}</span>
          <span v-if="editingError" class="tags__row-error">{{ editingError }}</span>
          <div class="tags__ops">
            <button
              type="button"
              class="tags__op"
              :disabled="savingEdit"
              @click="submitEdit(tag)"
            >
              {{ savingEdit ? '保存中…' : '保存' }}
            </button>
            <button type="button" class="tags__op" :disabled="savingEdit" @click="cancelEdit">
              取消
            </button>
          </div>
        </template>

        <!-- 展示态 -->
        <template v-else>
          <span
            class="tags__dot"
            :style="{ background: tag.color || 'var(--color-border)' }"
            aria-hidden="true"
          ></span>
          <span class="tags__name">{{ tag.name }}</span>
          <code class="tags__slug">{{ tag.slug }}</code>
          <span class="tags__usage">{{ tag.article_count }} 篇</span>
          <div class="tags__ops">
            <button type="button" class="tags__op" @click="startEdit(tag)">重命名</button>
            <button
              type="button"
              class="tags__op tags__op--danger"
              @click="askDelete(tag)"
            >
              删除
            </button>
          </div>
        </template>
      </div>
    </div>

    <!-- 删除确认 -->
    <div v-if="deleteTarget" class="modal" @click.self="cancelDelete">
      <div class="modal__box" role="dialog" aria-modal="true">
        <h2 class="modal__title">确认删除标签</h2>

        <p class="modal__text">
          即将删除标签「<strong>{{ deleteTarget.tag.name }}</strong>」。
        </p>

        <!-- 【这条文案是文档 06 明确要求的】
             「只删除标签，相关文章会保留」必须写出来。
             用户看到「删除」两个字时最容易的误解是「文章也会被删」，
             那条误解会让人不敢删标签，于是标签越积越多。 -->
        <p class="modal__note">只删除这个标签，相关文章会保留。</p>

        <p v-if="deleteLoading" class="modal__loading">正在查询使用情况…</p>
        <p v-else-if="deleteTarget.usage" class="modal__usage">
          当前有 <strong>{{ deleteTarget.usage.article_count }}</strong> 篇文章使用它
          <template v-if="deleteTarget.usage.published_count !== deleteTarget.usage.article_count">
            （其中 {{ deleteTarget.usage.published_count }} 篇已发布）
          </template>
          ，删除后这些文章将不再带有该标签。
        </p>

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
            :disabled="deleteSubmitting || deleteLoading"
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
.tags__head {
  margin-bottom: var(--space-4);
}

.tags__title {
  font-size: var(--text-2xl);
  font-weight: 600;
  color: var(--color-heading);
}

.tags__count {
  margin-top: var(--space-1);
  font-size: var(--text-sm);
  color: var(--color-text-muted);
}

.tags__create {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  margin-bottom: var(--space-4);
}

.tags__input {
  flex: 1;
  min-width: 0;
  max-width: 260px;
  padding: var(--space-2) var(--space-3);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
  background: var(--color-bg);
  font-size: var(--text-sm);
  font-family: inherit;
  color: var(--color-text);
}

.tags__input:focus {
  outline: none;
  border-color: var(--color-primary);
}

.tags__input--inline {
  max-width: 200px;
}

.tags__color {
  display: flex;
  align-items: center;
  gap: var(--space-2);
}

.tags__color-label {
  font-size: var(--text-sm);
  color: var(--color-text-muted);
}

.tags__color-input {
  width: 32px;
  height: 30px;
  padding: 2px;
  border: 1px solid var(--color-border);
  border-radius: var(--radius-sm);
  background: var(--color-bg);
  cursor: pointer;
}

.tags__btn {
  padding: var(--space-2) var(--space-4);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
  background: var(--color-bg);
  font-size: var(--text-sm);
  font-family: inherit;
  color: var(--color-text-secondary);
  cursor: pointer;
}

.tags__btn--primary {
  border-color: var(--color-primary);
  background: var(--color-primary);
  color: #fff;
}

.tags__btn:disabled {
  cursor: not-allowed;
  opacity: 0.5;
}

.tags__alert {
  margin-bottom: var(--space-3);
  padding: var(--space-2) var(--space-4);
  border-radius: var(--radius-md);
  background: var(--color-bg-soft);
  font-size: var(--text-sm);
  color: var(--color-danger);
}

.tags__list {
  background: var(--color-bg);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-lg);
  overflow: hidden;
}

.tags__row {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  padding: var(--space-3) var(--space-4);
  border-bottom: 1px solid var(--color-border);
  font-size: var(--text-sm);
}

.tags__row:last-child {
  border-bottom: none;
}

.tags__dot {
  width: 10px;
  height: 10px;
  flex-shrink: 0;
  border-radius: var(--radius-full);
}

.tags__name {
  font-weight: 600;
  color: var(--color-heading);
}

.tags__slug {
  flex: 1;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-family: var(--font-mono);
  font-size: var(--text-xs);
  color: var(--color-text-muted);
}

.tags__usage {
  color: var(--color-text-secondary);
  white-space: nowrap;
}

.tags__row-error {
  color: var(--color-danger);
  font-size: var(--text-xs);
}

.tags__ops {
  display: flex;
  gap: var(--space-2);
  flex-shrink: 0;
}

.tags__op {
  padding: var(--space-1) var(--space-2);
  border: none;
  background: transparent;
  font-size: var(--text-sm);
  font-family: inherit;
  color: var(--color-primary);
  cursor: pointer;
}

.tags__op:hover {
  text-decoration: underline;
}

.tags__op--danger {
  color: var(--color-danger);
}

/* ---- 弹层（与文章列表页一致的结构）---- */
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
  max-width: 440px;
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
}

.modal__note {
  margin-top: var(--space-2);
  padding: var(--space-2) var(--space-3);
  border-radius: var(--radius-md);
  background: var(--color-bg-soft);
  font-size: var(--text-sm);
  color: var(--color-text-secondary);
}

.modal__usage {
  margin-top: var(--space-3);
  font-size: var(--text-sm);
  color: var(--color-text-secondary);
}

.modal__loading {
  margin-top: var(--space-3);
  font-size: var(--text-sm);
  color: var(--color-text-muted);
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

.modal__btn--danger {
  border-color: var(--color-danger);
  background: var(--color-danger);
  color: #fff;
}

.modal__btn:disabled {
  cursor: not-allowed;
  opacity: 0.6;
}
</style>
