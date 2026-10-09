<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { getAdminSiteConfig, updateSiteConfig } from '@/api/admin'
import { useSiteStore } from '@/stores/site'
import { renderMarkdownPreview } from '@/utils/markdown-preview'

const siteStore = useSiteStore()

/**
 * 表单字段的定义。
 *
 * 用一张表驱动渲染，而不是手写 8 个 v-model：
 * 手写的话「加载 → 赋值 → 提交时收集」这三个动作各要重复 8 遍，
 * 漏掉一个字段的表现是「改了保存不上」，而且很难一眼看出来。
 */
interface FieldSpec {
  key: string
  label: string
  hint?: string
  /** 不写就是普通文本输入框 */
  type?: 'text' | 'textarea' | 'number' | 'url'
  /** 占一行的宽度 */
  wide?: boolean
}

const GROUPS: { title: string; note?: string; fields: FieldSpec[] }[] = [
  {
    title: '基本信息',
    fields: [
      { key: 'site_title', label: '站点标题', hint: '显示在页头与浏览器标签' },
      { key: 'site_subtitle', label: '副标题', hint: '显示在首页标题下方' },
      { key: 'footer_text', label: '页脚文字', wide: true, hint: '留空则不显示' },
    ],
  },
  {
    title: '作者信息',
    fields: [
      { key: 'author_name', label: '作者名' },
      { key: 'author_intro', label: '关于页内容', type: 'textarea', wide: true, hint: '支持 Markdown' },
    ],
  },
  {
    title: '链接',
    fields: [
      { key: 'github_url', label: 'GitHub 链接', type: 'url', hint: '留空则不显示' },
      { key: 'icp_number', label: '备案号', hint: '留空则不显示' },
    ],
  },
  {
    title: '列表设置',
    fields: [
      { key: 'articles_per_page', label: '每页文章数', type: 'number', hint: '1 – 50' },
    ],
  },
]

const form = ref<Record<string, string>>({})
const loading = ref(true)
const loadError = ref('')
const saving = ref(false)
const saveError = ref('')
const saveOk = ref('')

/** 已保存快照，用于判断是否有未保存修改 */
const savedSnapshot = ref('')

const isDirty = computed(() => JSON.stringify(form.value) !== savedSnapshot.value)

/** 关于页内容的预览开关 */
const showIntroPreview = ref(false)
const introPreview = computed(() => renderMarkdownPreview(form.value.author_intro ?? ''))

async function load(): Promise<void> {
  loading.value = true
  loadError.value = ''
  try {
    const data = await getAdminSiteConfig()
    // 只挑表单认识的键：后端可能返回我们没渲染的配置项，
    // 那些键如果进了 form，保存时会被原样回传 ——
    // 用户没改过却参与提交，等于把未知键也写了一遍。
    const keys = GROUPS.flatMap((g) => g.fields.map((f) => f.key))
    const next: Record<string, string> = {}
    for (const key of keys) {
      next[key] = data.values[key] ?? ''
    }
    form.value = next
    savedSnapshot.value = JSON.stringify(next)
  } catch (e) {
    loadError.value = e instanceof Error ? e.message : '加载失败'
  } finally {
    loading.value = false
  }
}

onMounted(load)

async function handleSave(): Promise<void> {
  if (saving.value) return
  saving.value = true
  saveError.value = ''
  saveOk.value = ''

  try {
    // 只提交变化过的字段。
    //
    // 为什么要这样做：提交全部字段时，后端会对每个键做校验
    // （长度、数字范围）。只要有一个字段非法，整次保存都会失败 ——
    // 包括那些本来就正确的字段。只提交改动过的，
    // 报错就精确指向用户刚改的那一项。
    const previous = JSON.parse(savedSnapshot.value) as Record<string, string>
    const changed: Record<string, string> = {}
    for (const [key, value] of Object.entries(form.value)) {
      if (previous[key] !== value) changed[key] = value
    }

    if (Object.keys(changed).length === 0) {
      saveOk.value = '没有需要保存的修改'
      return
    }

    const data = await updateSiteConfig(changed)
    form.value = { ...form.value, ...data.values }
    savedSnapshot.value = JSON.stringify(form.value)
    saveOk.value = '已保存'

    // 【关键：同步刷新全局站点配置】
    // 页头读的是 site store。不刷新的话，这里保存成功了，
    // 但页头的标题还是旧的 —— 用户会以为没保存上。
    await siteStore.refresh()
  } catch (e) {
    saveError.value = e instanceof Error ? e.message : '保存失败'
  } finally {
    saving.value = false
  }
}

function resetField(key: string): void {
  const previous = JSON.parse(savedSnapshot.value) as Record<string, string>
  form.value[key] = previous[key] ?? ''
}
</script>

<template>
  <section class="settings">
    <header class="settings__head">
      <div>
        <h1 class="settings__title">站点设置</h1>
        <p class="settings__count">修改后点击保存生效</p>
      </div>
      <div class="settings__actions">
        <span v-if="isDirty" class="settings__dirty">有未保存的修改</span>
        <button
          type="button"
          class="settings__btn settings__btn--primary"
          :disabled="saving || loading || !isDirty"
          @click="handleSave"
        >
          {{ saving ? '保存中…' : '保存' }}
        </button>
      </div>
    </header>

    <p v-if="loadError" class="settings__alert settings__alert--error">{{ loadError }}</p>
    <p v-if="saveError" class="settings__alert settings__alert--error">{{ saveError }}</p>
    <p v-if="saveOk" class="settings__alert settings__alert--ok">{{ saveOk }}</p>

    <div v-if="loading" class="settings__loading">加载中…</div>

    <template v-else>
      <section v-for="group in GROUPS" :key="group.title" class="settings__group">
        <h2 class="settings__group-title">{{ group.title }}</h2>

        <div class="settings__grid">
          <div
            v-for="field in group.fields"
            :key="field.key"
            class="settings__field"
            :class="{ 'settings__field--wide': field.wide }"
          >
            <label class="settings__label" :for="`f-${field.key}`">
              {{ field.label }}
              <span v-if="field.hint" class="settings__hint">{{ field.hint }}</span>
            </label>

            <textarea
              v-if="field.type === 'textarea'"
              :id="`f-${field.key}`"
              v-model="form[field.key]"
              class="settings__input settings__textarea"
              rows="6"
            ></textarea>

            <input
              v-else
              :id="`f-${field.key}`"
              v-model="form[field.key]"
              class="settings__input"
              :type="field.type"
              :min="field.type === 'number' ? 1 : undefined"
              :max="field.type === 'number' ? 50 : undefined"
            />

            <div v-if="field.key === 'author_intro'" class="settings__intro-tools">
              <button
                type="button"
                class="settings__toggle"
                @click="showIntroPreview = !showIntroPreview"
              >
                {{ showIntroPreview ? '隐藏预览' : '预览 Markdown' }}
              </button>
              <button type="button" class="settings__toggle" @click="resetField(field.key)">
                撤销修改
              </button>
            </div>
            <div
              v-if="field.key === 'author_intro' && showIntroPreview"
              class="settings__preview markdown-body"
              v-html="introPreview"
            ></div>
          </div>
        </div>
      </section>

      <p class="settings__note">
        关于页内容目前按纯文本显示，Markdown 渲染尚未接入（已在 README 记录为待办）。
      </p>
    </template>
  </section>
</template>

<style scoped>
.settings__head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: var(--space-4);
  margin-bottom: var(--space-5);
}

.settings__title {
  font-size: var(--text-2xl);
  font-weight: 600;
  color: var(--color-heading);
}

.settings__count {
  margin-top: var(--space-1);
  font-size: var(--text-sm);
  color: var(--color-text-muted);
}

.settings__actions {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  flex-shrink: 0;
}

.settings__dirty {
  font-size: var(--text-xs);
  color: var(--color-warning);
}

.settings__btn {
  padding: var(--space-2) var(--space-4);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
  background: var(--color-bg);
  font-size: var(--text-sm);
  font-family: inherit;
  color: var(--color-text-secondary);
  cursor: pointer;
}

.settings__btn--primary {
  border-color: var(--color-primary);
  background: var(--color-primary);
  color: #fff;
}

.settings__btn:disabled {
  cursor: not-allowed;
  opacity: 0.5;
}

.settings__alert {
  margin-bottom: var(--space-3);
  padding: var(--space-2) var(--space-4);
  border-radius: var(--radius-md);
  font-size: var(--text-sm);
}

.settings__alert--error {
  background: var(--color-bg-soft);
  color: var(--color-danger);
}

.settings__alert--ok {
  background: var(--color-bg-soft);
  color: var(--color-success);
}

.settings__loading {
  padding: var(--space-8);
  text-align: center;
  color: var(--color-text-muted);
}

.settings__group {
  margin-bottom: var(--space-5);
  padding: var(--space-4);
  background: var(--color-bg);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-lg);
}

.settings__group-title {
  margin-bottom: var(--space-4);
  font-size: var(--text-base);
  font-weight: 600;
  color: var(--color-heading);
}

.settings__grid {
  display: grid;
  grid-template-columns: 1fr;
  gap: var(--space-4);
}

@media (min-width: 640px) {
  .settings__grid {
    grid-template-columns: 1fr 1fr;
  }

  .settings__field--wide {
    grid-column: 1 / -1;
  }
}

.settings__field {
  display: flex;
  flex-direction: column;
  gap: var(--space-1);
  min-width: 0;
}

.settings__label {
  font-size: var(--text-sm);
  color: var(--color-text-secondary);
}

.settings__hint {
  font-size: var(--text-xs);
  color: var(--color-text-muted);
}

.settings__input {
  padding: var(--space-2) var(--space-3);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
  background: var(--color-bg);
  font-size: var(--text-sm);
  font-family: inherit;
  color: var(--color-text);
}

.settings__input:focus {
  outline: none;
  border-color: var(--color-primary);
}

.settings__textarea {
  resize: vertical;
  font-family: var(--font-mono);
  line-height: var(--leading-code);
}

.settings__intro-tools {
  display: flex;
  gap: var(--space-2);
}

.settings__toggle {
  padding: var(--space-1) var(--space-2);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-sm);
  background: var(--color-bg);
  font-size: var(--text-xs);
  font-family: inherit;
  color: var(--color-text-secondary);
  cursor: pointer;
}

.settings__toggle:hover {
  border-color: var(--color-primary);
  color: var(--color-primary);
}

.settings__preview {
  max-height: 260px;
  overflow-y: auto;
  padding: var(--space-3);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
  background: var(--color-bg-soft);
  font-size: var(--text-sm);
}

.settings__note {
  font-size: var(--text-xs);
  color: var(--color-text-muted);
}
</style>
