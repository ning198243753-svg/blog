<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { onBeforeRouteLeave, useRoute, useRouter } from 'vue-router'
import {
  createArticle,
  getAdminArticle,
  getAdminTags,
  updateArticle,
  uploadImage,
} from '@/api/admin'
import type { AdminTag } from '@/types/admin'
import { markdownPlainText, renderMarkdownPreview } from '@/utils/markdown-preview'

const route = useRoute()
const router = useRouter()

/** 路由带 :id 就是编辑，否则是新建 */
const articleId = computed(() => {
  const raw = route.params.id
  if (typeof raw !== 'string') return null
  const parsed = Number(raw)
  return Number.isInteger(parsed) && parsed > 0 ? parsed : null
})
const isEdit = computed(() => articleId.value !== null)

// ---- 表单状态 ----
const title = ref('')
const contentMd = ref('')
const summary = ref('')
const status = ref<'draft' | 'published'>('draft')
const selectedTagIds = ref<number[]>([])

const allTags = ref<AdminTag[]>([])

const loading = ref(true)
const loadError = ref('')
const saving = ref(false)
const saveError = ref('')
const saveOk = ref('')

/**
 * 已保存内容的快照，用于判断「有没有未保存的修改」。
 *
 * 【为什么存快照而不是一个 dirty 布尔值】
 * 布尔值需要在每个输入框上挂 change 事件手动置位，
 * 而且用户「改了又改回去」时它是错的（明明没变化却提示未保存）。
 * 快照比较是自动正确的：内容相同就是没变化。
 */
const savedSnapshot = ref('')

function currentSnapshot(): string {
  return JSON.stringify({
    title: title.value,
    contentMd: contentMd.value,
    summary: summary.value,
    status: status.value,
    selectedTagIds: [...selectedTagIds.value].sort((a, b) => a - b),
  })
}

const isDirty = computed(() => currentSnapshot() !== savedSnapshot.value)

// ---- 加载 ----
async function loadTags(): Promise<void> {
  try {
    allTags.value = await getAdminTags()
  } catch {
    // 标签拉取失败不该阻塞写作：文章可以没有标签。
    // 这里静默处理，编辑器仍可正常保存。
    allTags.value = []
  }
}

async function loadArticle(): Promise<void> {
  if (!isEdit.value) {
    // 新建：给出一个空模板，让作者知道 Markdown 能用
    contentMd.value = ''
    savedSnapshot.value = currentSnapshot()
    loading.value = false
    return
  }

  try {
    const data = await getAdminArticle(articleId.value as number)
    title.value = data.title
    contentMd.value = data.content_md
    summary.value = data.summary ?? ''
    status.value = data.status === 'published' ? 'published' : 'draft'
    selectedTagIds.value = data.tags.map((t) => t.id)
    savedSnapshot.value = currentSnapshot()
  } catch (e) {
    loadError.value = e instanceof Error ? e.message : '加载失败'
  } finally {
    loading.value = false
  }
}

onMounted(async () => {
  await Promise.all([loadTags(), loadArticle()])
})

// ---- 标签选择 ----
function toggleTag(id: number): void {
  const index = selectedTagIds.value.indexOf(id)
  if (index >= 0) {
    selectedTagIds.value.splice(index, 1)
  } else {
    selectedTagIds.value.push(id)
  }
}

function isTagSelected(id: number): boolean {
  return selectedTagIds.value.includes(id)
}

// ---- 预览 ----
/**
 * 预览的显示开关。
 *
 * 小屏幕上左右分栏会挤成两条窄缝，所以默认关闭，
 * 由作者决定什么时候看。桌面端默认打开（有足够宽度）。
 */
const showPreview = ref(window.innerWidth >= 1024)

const previewHtml = computed(() => renderMarkdownPreview(contentMd.value))

/** 字数：按纯文本算，与后端的口径接近但不要求一致 */
const wordCount = computed(() => markdownPlainText(contentMd.value).length)

// ---- 保存 ----
async function save(nextStatus?: 'draft' | 'published'): Promise<void> {
  if (saving.value) return
  saveError.value = ''
  saveOk.value = ''

  const trimmedTitle = title.value.trim()
  if (!trimmedTitle) {
    saveError.value = '标题不能为空'
    return
  }
  if (!contentMd.value.trim()) {
    saveError.value = '正文不能为空'
    return
  }

  saving.value = true
  try {
    const payload = {
      title: trimmedTitle,
      content_md: contentMd.value,
      summary: summary.value.trim() || null,
      tag_ids: selectedTagIds.value,
      status: nextStatus ?? status.value,
    }

    if (isEdit.value) {
      // 状态只在明确要求变更时传，避免「保存草稿」意外把已发布的文章变回草稿
      await updateArticle(articleId.value as number, {
        title: payload.title,
        content_md: payload.content_md,
        summary: payload.summary,
        tag_ids: payload.tag_ids,
        ...(nextStatus ? { status: nextStatus } : {}),
      })
      if (nextStatus) status.value = nextStatus
      savedSnapshot.value = currentSnapshot()
      saveOk.value = nextStatus === 'published' ? '已发布' : '已保存'
    } else {
      // 【新建 + 发布：必须分两步，不能一步发布】
      //
      // 文档 06 第 3.3 节：「先保存再改状态，两步不能合并」，
      // 原因是「避免发布了一个空文章」。
      // 这里先按 draft 创建（拿回 id），再单独调用更新把状态改成 published。
      // 中间那一步如果失败，文章会以草稿形式存在 —— 这是可接受的：
      // 内容还在，用户能再次点发布，而不是丢掉整篇。
      const created = await createArticle({
        title: payload.title,
        content_md: payload.content_md,
        summary: payload.summary,
        tag_ids: payload.tag_ids,
        status: 'draft',
      })

      if (nextStatus === 'published') {
        try {
          await updateArticle(created.id, { status: 'published' })
          status.value = 'published'
          saveOk.value = '已发布'
        } catch (e) {
          saveError.value = `文章已保存为草稿，但发布失败：${
            e instanceof Error ? e.message : '未知错误'
          }`
        }
      } else {
        saveOk.value = '已保存为草稿'
      }

      savedSnapshot.value = currentSnapshot()

      // 新建成功后跳到编辑页：否则用户再次点保存会又创建一篇。
      // replace 而不是 push：避免后退键回到空白的「新建」页。
      await router.replace(`/admin/articles/${created.id}/edit`)
    }
  } catch (e) {
    saveError.value = e instanceof Error ? e.message : '保存失败'
  } finally {
    saving.value = false
  }
}

// ---- 图片上传 ----
const uploading = ref(false)
const uploadError = ref('')
const contentEl = ref<HTMLTextAreaElement | null>(null)

/**
 * 上传图片并把 Markdown 语法插入到光标位置。
 *
 * 【为什么插入到光标而不是追加到末尾】
 * 作者通常是「写到某处，插一张图，继续写」。
 * 追加到末尾会让图片跑到文末，作者还得手动剪切粘贴搬回原处 ——
 * 那这个上传功能就只省了一步。
 */
async function handleFiles(files: FileList | File[] | null): Promise<void> {
  if (!files || files.length === 0 || uploading.value) return

  uploading.value = true
  uploadError.value = ''

  try {
    // 逐个上传：一次请求一张，便于对每张单独报告失败原因
    for (const file of Array.from(files)) {
      const result = await uploadImage(file)
      insertAtCursor(`![${file.name.replace(/\.[^.]+$/, '')}](${result.url})`)
    }
  } catch (e) {
    uploadError.value = e instanceof Error ? e.message : '上传失败'
  } finally {
    uploading.value = false
  }
}

function insertAtCursor(text: string): void {
  const el = contentEl.value
  if (!el) {
    contentMd.value += `\n${text}\n`
    return
  }

  const start = el.selectionStart ?? contentMd.value.length
  const end = el.selectionEnd ?? start
  const before = contentMd.value.slice(0, start)
  const after = contentMd.value.slice(end)

  // 前后补换行，避免图片语法粘在上一行文字末尾
  const prefix = before && !before.endsWith('\n') ? '\n' : ''
  const suffix = after && !after.startsWith('\n') ? '\n' : ''
  contentMd.value = `${before}${prefix}${text}${suffix}${after}`

  // 光标移到插入内容之后，方便继续打字
  const caret = start + prefix.length + text.length + suffix.length
  requestAnimationFrame(() => {
    el.focus()
    el.setSelectionRange(caret, caret)
  })
}

function onPaste(event: ClipboardEvent): void {
  const files = event.clipboardData?.files
  if (files && files.length > 0) {
    event.preventDefault()
    void handleFiles(files)
  }
}

function onDrop(event: DragEvent): void {
  const files = event.dataTransfer?.files
  if (files && files.length > 0) {
    event.preventDefault()
    void handleFiles(files)
  }
}

function onFileInputChange(event: Event): void {
  const input = event.target as HTMLInputElement
  void handleFiles(input.files)
  // 清空 value：否则连续选同一个文件不会触发 change
  input.value = ''
}

// ---- 离开提醒 ----
//
// 【两类离开必须都拦】
// 1. 站内路由跳转 → onBeforeRouteLeave
// 2. 关闭标签页 / 刷新 / 输入别的网址 → beforeunload
// 只做前者的话，作者关浏览器就丢内容，而那正是最常见的场景。
function onBeforeUnload(event: BeforeUnloadEvent): void {
  if (!isDirty.value) return
  event.preventDefault()
  // 现代浏览器忽略自定义文案，用默认提示；returnValue 是触发条件
  event.returnValue = ''
}

onMounted(() => {
  window.addEventListener('beforeunload', onBeforeUnload)
})
onBeforeUnmount(() => {
  window.removeEventListener('beforeunload', onBeforeUnload)
})

onBeforeRouteLeave(() => {
  if (!isDirty.value) return true
  return window.confirm('有未保存的修改，确定要离开吗？')
})

// ---- 快捷键 ----
function onKeydown(event: KeyboardEvent): void {
  // Ctrl/Cmd + S 保存草稿。阻止浏览器默认的「保存网页」对话框。
  if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === 's') {
    event.preventDefault()
    void save()
  }
}
</script>

<template>
  <section class="editor" @keydown="onKeydown">
    <header class="editor__head">
      <RouterLink to="/admin/articles" class="editor__back">← 返回列表</RouterLink>
      <h1 class="editor__heading">{{ isEdit ? '编辑文章' : '新建文章' }}</h1>
      <div class="editor__actions">
        <span v-if="status === 'published'" class="editor__status">已发布</span>
        <span v-else class="editor__status editor__status--draft">草稿</span>
        <button
          type="button"
          class="editor__btn"
          :disabled="saving || loading"
          @click="save()"
        >
          {{ saving ? '保存中…' : '保存草稿' }}
        </button>
        <button
          type="button"
          class="editor__btn editor__btn--primary"
          :disabled="saving || loading"
          @click="save('published')"
        >
          {{ saving ? '发布中…' : '发布' }}
        </button>
      </div>
    </header>

    <p v-if="loadError" class="editor__alert editor__alert--error">{{ loadError }}</p>
    <p v-if="saveError" class="editor__alert editor__alert--error">{{ saveError }}</p>
    <p v-if="saveOk" class="editor__alert editor__alert--ok">{{ saveOk }}</p>
    <p v-if="uploadError" class="editor__alert editor__alert--error">{{ uploadError }}</p>

    <div v-if="loading" class="editor__loading">加载中…</div>

    <template v-else>
      <!-- 标题 -->
      <label class="editor__field">
        <span class="editor__label">标题</span>
        <input
          v-model="title"
          class="editor__input editor__input--title"
          type="text"
          maxlength="200"
          placeholder="文章标题"
        />
      </label>

      <!-- 标签 -->
      <div class="editor__field">
        <span class="editor__label">标签</span>
        <div v-if="allTags.length === 0" class="editor__hint">
          还没有标签，可在
          <RouterLink to="/admin/tags" class="editor__link">标签管理</RouterLink>
          中创建
        </div>
        <div v-else class="editor__tags">
          <button
            v-for="tag in allTags"
            :key="tag.id"
            type="button"
            class="editor__tag"
            :class="{ 'editor__tag--on': isTagSelected(tag.id) }"
            @click="toggleTag(tag.id)"
          >
            {{ tag.name }}
          </button>
        </div>
      </div>

      <!-- 摘要 -->
      <label class="editor__field">
        <span class="editor__label">
          摘要
          <span class="editor__label-hint">留空则自动截取正文前 150 字</span>
        </span>
        <textarea
          v-model="summary"
          class="editor__input editor__summary"
          rows="2"
          maxlength="300"
          placeholder="列表页显示的一句话简介"
        ></textarea>
      </label>

      <!-- 编辑区与预览 -->
      <div class="editor__body">
        <div class="editor__pane">
          <div class="editor__pane-head">
            <span class="editor__pane-title">Markdown</span>
            <div class="editor__pane-tools">
              <label class="editor__upload">
                <input
                  type="file"
                  accept="image/jpeg,image/png,image/webp,image/gif"
                  multiple
                  class="editor__file"
                  :disabled="uploading"
                  @change="onFileInputChange"
                />
                {{ uploading ? '上传中…' : '插入图片' }}
              </label>
              <button
                type="button"
                class="editor__toggle"
                @click="showPreview = !showPreview"
              >
                {{ showPreview ? '隐藏预览' : '显示预览' }}
              </button>
            </div>
          </div>
          <textarea
            ref="contentEl"
            v-model="contentMd"
            class="editor__md"
            spellcheck="false"
            placeholder="在这里写 Markdown…&#10;&#10;可以直接把图片拖进来或粘贴进来"
            @paste="onPaste"
            @drop="onDrop"
            @dragover.prevent
          ></textarea>
        </div>

        <div v-if="showPreview" class="editor__pane">
          <div class="editor__pane-head">
            <span class="editor__pane-title">预览</span>
            <span class="editor__pane-note">样式与线上一致，细节以后端渲染为准</span>
          </div>
          <div
            v-if="contentMd.trim()"
            class="editor__preview markdown-body"
            v-html="previewHtml"
          ></div>
          <p v-else class="editor__preview-empty">还没有内容</p>
        </div>
      </div>

      <!-- 底部状态 -->
      <footer class="editor__foot">
        <span v-if="isDirty" class="editor__dirty">有未保存的修改</span>
        <span v-else class="editor__saved">已保存</span>
        <span class="editor__count">{{ wordCount }} 字</span>
      </footer>
    </template>
  </section>
</template>

<style scoped>
.editor {
  display: flex;
  flex-direction: column;
  gap: var(--space-4);
}

.editor__head {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  flex-wrap: wrap;
}

.editor__back {
  font-size: var(--text-sm);
  color: var(--color-text-muted);
}

.editor__back:hover {
  color: var(--color-primary);
}

.editor__heading {
  flex: 1;
  font-size: var(--text-xl);
  font-weight: 600;
  color: var(--color-heading);
}

.editor__actions {
  display: flex;
  align-items: center;
  gap: var(--space-2);
}

.editor__status {
  padding: 2px var(--space-2);
  border-radius: var(--radius-sm);
  background: var(--color-bg-soft);
  font-size: var(--text-xs);
  color: var(--color-primary);
}

.editor__status--draft {
  color: var(--color-text-muted);
}

.editor__btn {
  padding: var(--space-2) var(--space-4);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
  background: var(--color-bg);
  font-size: var(--text-sm);
  font-family: inherit;
  color: var(--color-text-secondary);
  cursor: pointer;
  transition: all var(--transition);
}

.editor__btn:hover:not(:disabled) {
  border-color: var(--color-primary);
  color: var(--color-primary);
}

.editor__btn--primary {
  border-color: var(--color-primary);
  background: var(--color-primary);
  color: #fff;
}

.editor__btn--primary:hover:not(:disabled) {
  opacity: 0.9;
  color: #fff;
}

.editor__btn:disabled {
  cursor: not-allowed;
  opacity: 0.6;
}

.editor__alert {
  padding: var(--space-2) var(--space-4);
  border-radius: var(--radius-md);
  font-size: var(--text-sm);
}

.editor__alert--error {
  background: var(--color-bg-soft);
  color: var(--color-danger);
}

.editor__alert--ok {
  background: var(--color-bg-soft);
  color: var(--color-success);
}

.editor__loading {
  padding: var(--space-8);
  text-align: center;
  color: var(--color-text-muted);
}

.editor__field {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
}

.editor__label {
  display: flex;
  align-items: baseline;
  gap: var(--space-2);
  font-size: var(--text-sm);
  color: var(--color-text-secondary);
}

.editor__label-hint {
  font-size: var(--text-xs);
  color: var(--color-text-muted);
}

.editor__hint {
  font-size: var(--text-sm);
  color: var(--color-text-muted);
}

.editor__link {
  color: var(--color-primary);
}

.editor__input {
  padding: var(--space-2) var(--space-3);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
  background: var(--color-bg);
  font-size: var(--text-base);
  font-family: inherit;
  color: var(--color-text);
}

.editor__input:focus {
  outline: none;
  border-color: var(--color-primary);
}

.editor__input--title {
  font-size: var(--text-lg);
  font-weight: 600;
}

.editor__summary {
  resize: vertical;
  font-size: var(--text-sm);
}

.editor__tags {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-2);
}

.editor__tag {
  padding: var(--space-1) var(--space-3);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-full);
  background: var(--color-bg);
  font-size: var(--text-sm);
  font-family: inherit;
  color: var(--color-text-secondary);
  cursor: pointer;
  transition: all var(--transition);
}

.editor__tag:hover {
  border-color: var(--color-primary);
}

.editor__tag--on {
  border-color: var(--color-primary);
  background: var(--color-primary);
  color: #fff;
}

/* ---- 编辑区 ---- */
.editor__body {
  display: flex;
  gap: var(--space-4);
  align-items: stretch;
}

.editor__pane {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  background: var(--color-bg);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-lg);
  overflow: hidden;
}

.editor__pane-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-2);
  padding: var(--space-2) var(--space-3);
  border-bottom: 1px solid var(--color-border);
  background: var(--color-bg-soft);
}

.editor__pane-title {
  font-size: var(--text-sm);
  font-weight: 600;
  color: var(--color-text-secondary);
}

.editor__pane-note {
  font-size: var(--text-xs);
  color: var(--color-text-muted);
}

.editor__pane-tools {
  display: flex;
  align-items: center;
  gap: var(--space-2);
}

.editor__upload,
.editor__toggle {
  padding: var(--space-1) var(--space-2);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-sm);
  background: var(--color-bg);
  font-size: var(--text-xs);
  font-family: inherit;
  color: var(--color-text-secondary);
  cursor: pointer;
}

.editor__upload:hover,
.editor__toggle:hover {
  border-color: var(--color-primary);
  color: var(--color-primary);
}

/* 隐藏原生 file 控件：它的外观无法统一，且「选择文件」文案太长 */
.editor__file {
  display: none;
}

.editor__md {
  flex: 1;
  min-height: 460px;
  padding: var(--space-4);
  border: none;
  resize: vertical;
  background: var(--color-bg);
  font-family: var(--font-mono);
  font-size: var(--text-sm);
  line-height: var(--leading-code);
  color: var(--color-text);
}

.editor__md:focus {
  outline: none;
}

.editor__preview {
  flex: 1;
  min-height: 460px;
  max-height: 720px;
  overflow-y: auto;
  padding: var(--space-4);
}

.editor__preview-empty {
  padding: var(--space-4);
  font-size: var(--text-sm);
  color: var(--color-text-muted);
}

/* ---- 底部 ---- */
.editor__foot {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding-top: var(--space-2);
  font-size: var(--text-xs);
}

.editor__dirty {
  color: var(--color-warning);
}

.editor__saved {
  color: var(--color-text-muted);
}

.editor__count {
  color: var(--color-text-muted);
}

/* 窄屏：预览改为上下排列会太窄，直接让作者用按钮切换 */
@media (max-width: 1023px) {
  .editor__body {
    flex-direction: column;
  }

  .editor__md,
  .editor__preview {
    min-height: 320px;
  }
}
</style>
