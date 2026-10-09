<script setup lang="ts">
import { computed, ref } from 'vue'
import { RouterLink, useRoute, useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'

const route = useRoute()
const router = useRouter()
const auth = useAuthStore()

const username = ref('')
const password = ref('')
const error = ref('')

/**
 * 登录后的跳转目标。
 *
 * 【为什么要校验 redirect 是不是站内路径】
 * 守卫会把「原本想去的页面」放进 ?redirect=。
 * 如果直接 router.push(redirect)，那么攻击者可以构造
 *   /admin/login?redirect=https://evil.com
 * 让用户登录后被送到站外 —— 这是「开放重定向」漏洞。
 *
 * 只接受以单个 / 开头的相对路径：
 * - "//evil.com" 会被浏览器当成协议相对 URL，也要排除
 * - 完整 http(s) 链接直接忽略，退回后台首页
 */
const redirectTarget = computed(() => {
  const raw = route.query.redirect
  if (typeof raw !== 'string') return '/admin/articles'
  if (!raw.startsWith('/') || raw.startsWith('//')) return '/admin/articles'
  return raw
})

const canSubmit = computed(
  () => username.value.trim().length > 0 && password.value.length > 0 && !auth.loggingIn,
)

async function handleSubmit(): Promise<void> {
  if (!canSubmit.value) return

  error.value = ''
  try {
    await auth.login(username.value.trim(), password.value)
    await router.push(redirectTarget.value)
  } catch (e) {
    // 后端对「用户名不存在」和「密码错误」返回同一句话，
    // 这里原样透出即可 —— 不要在前端补一句「用户名可能不存在」，
    // 那等于把后端刻意隐藏的信息又暴露出来。
    error.value = e instanceof Error ? e.message : '登录失败'
  }
}
</script>

<template>
  <div class="login">
    <div class="login__card">
      <h1 class="login__title">登录</h1>
      <p class="login__hint">仅站点作者可进入</p>

      <form class="login__form" @submit.prevent="handleSubmit">
        <label class="login__field">
          <span class="login__label">用户名</span>
          <input
            v-model="username"
            class="login__input"
            type="text"
            name="username"
            autocomplete="username"
            :disabled="auth.loggingIn"
            required
          />
        </label>

        <label class="login__field">
          <span class="login__label">密码</span>
          <input
            v-model="password"
            class="login__input"
            type="password"
            name="password"
            autocomplete="current-password"
            :disabled="auth.loggingIn"
            required
          />
        </label>

        <p v-if="error" class="login__error" role="alert">{{ error }}</p>

        <button type="submit" class="login__submit" :disabled="!canSubmit">
          {{ auth.loggingIn ? '登录中…' : '登录' }}
        </button>
      </form>

      <RouterLink to="/" class="login__back">← 返回站点</RouterLink>
    </div>
  </div>
</template>

<style scoped>
.login {
  width: 100%;
  max-width: 380px;
}

.login__card {
  padding: var(--space-6);
  background: var(--color-bg);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-lg);
  box-shadow: var(--shadow-sm);
}

.login__title {
  font-size: var(--text-2xl);
  font-weight: 600;
  color: var(--color-heading);
}

.login__hint {
  margin-top: var(--space-1);
  font-size: var(--text-sm);
  color: var(--color-text-muted);
}

.login__form {
  margin-top: var(--space-5);
  display: flex;
  flex-direction: column;
  gap: var(--space-4);
}

.login__field {
  display: flex;
  flex-direction: column;
  gap: var(--space-1);
}

.login__label {
  font-size: var(--text-sm);
  color: var(--color-text-secondary);
}

.login__input {
  padding: var(--space-2) var(--space-3);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
  background: var(--color-bg);
  font-size: var(--text-base);
  font-family: inherit;
  color: var(--color-text);
  transition: border-color var(--transition);
}

.login__input:focus {
  outline: none;
  border-color: var(--color-primary);
}

.login__input:disabled {
  background: var(--color-bg-soft);
  cursor: not-allowed;
}

.login__error {
  padding: var(--space-2) var(--space-3);
  border-radius: var(--radius-md);
  background: var(--color-bg-soft);
  font-size: var(--text-sm);
  color: var(--color-danger);
}

.login__submit {
  padding: var(--space-3);
  border: none;
  border-radius: var(--radius-md);
  background: var(--color-primary);
  font-size: var(--text-base);
  font-family: inherit;
  color: #fff;
  cursor: pointer;
  transition: opacity var(--transition);
}

.login__submit:hover:not(:disabled) {
  opacity: 0.9;
}

.login__submit:disabled {
  cursor: not-allowed;
  opacity: 0.5;
}

.login__back {
  display: inline-block;
  margin-top: var(--space-5);
  font-size: var(--text-sm);
  color: var(--color-text-muted);
}

.login__back:hover {
  color: var(--color-primary);
}
</style>
