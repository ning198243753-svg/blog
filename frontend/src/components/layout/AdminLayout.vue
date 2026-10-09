<script setup lang="ts">
import { computed, ref } from 'vue'
import { RouterLink, RouterView, useRoute, useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'

const route = useRoute()
const router = useRouter()
const auth = useAuthStore()

/**
 * 侧边导航。登录页不显示（那时还没有登录态，
 * 显示一堆点进去又被弹回来的链接没有意义）。
 */
const nav = [
  { to: '/admin/articles', label: '文章管理' },
  { to: '/admin/tags', label: '标签管理' },
  { to: '/admin/settings', label: '站点设置' },
]

const isLoginPage = computed(() => route.name === 'admin-login')

/** 退出中：禁用按钮，避免连点导致多次请求 */
const loggingOut = ref(false)
const logoutError = ref('')

async function handleLogout(): Promise<void> {
  if (loggingOut.value) return
  loggingOut.value = true
  logoutError.value = ''
  try {
    await auth.logout()
    await router.push('/admin/login')
  } catch (e) {
    logoutError.value = e instanceof Error ? e.message : '退出失败'
  } finally {
    loggingOut.value = false
  }
}
</script>

<template>
  <div class="admin">
    <!-- 登录页：只渲染内容，不显示导航 -->
    <main v-if="isLoginPage" class="admin__solo">
      <RouterView />
    </main>

    <template v-else>
      <aside class="admin__side">
        <RouterLink to="/" class="admin__brand" title="返回站点首页">
          <span class="admin__brand-text">管理后台</span>
        </RouterLink>

        <nav class="admin__nav">
          <RouterLink
            v-for="item in nav"
            :key="item.to"
            :to="item.to"
            class="admin__link"
            :class="{ 'admin__link--active': route.path.startsWith(item.to) }"
          >
            {{ item.label }}
          </RouterLink>
        </nav>

        <div class="admin__foot">
          <p v-if="auth.user" class="admin__user">{{ auth.user.username }}</p>
          <button
            type="button"
            class="admin__logout"
            :disabled="loggingOut"
            @click="handleLogout"
          >
            {{ loggingOut ? '退出中…' : '退出登录' }}
          </button>
          <p v-if="logoutError" class="admin__error">{{ logoutError }}</p>
        </div>
      </aside>

      <main class="admin__main">
        <RouterView />
      </main>
    </template>
  </div>
</template>

<style scoped>
.admin {
  display: flex;
  min-height: 100vh;
  background: var(--color-bg-soft);
}

/* ---- 登录页：居中单栏 ---- */
.admin__solo {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: var(--space-5);
  background: var(--color-bg);
}

/* ---- 侧边栏 ---- */
.admin__side {
  width: 200px;
  flex-shrink: 0;
  display: flex;
  flex-direction: column;
  padding: var(--space-5) var(--space-3);
  background: var(--color-bg);
  border-right: 1px solid var(--color-border);
}

.admin__brand {
  display: block;
  padding: 0 var(--space-3) var(--space-5);
  font-size: var(--text-lg);
  font-weight: 600;
  color: var(--color-heading);
}

.admin__brand-text {
  white-space: nowrap;
}

.admin__nav {
  display: flex;
  flex-direction: column;
  gap: var(--space-1);
  flex: 1;
}

.admin__link {
  padding: var(--space-2) var(--space-3);
  border-radius: var(--radius-md);
  font-size: var(--text-sm);
  color: var(--color-text-secondary);
  transition: all var(--transition);
}

.admin__link:hover {
  background: var(--color-bg-soft);
  color: var(--color-heading);
}

/* 用 class 而不是 router-link-active：
   子路由（/admin/articles/new）也应高亮父项，
   router-link-active 默认只匹配精确前缀，这里手动控制更明确。 */
.admin__link--active {
  background: var(--color-bg-soft);
  color: var(--color-primary);
  font-weight: 600;
}

.admin__foot {
  padding-top: var(--space-4);
  border-top: 1px solid var(--color-border);
}

.admin__user {
  padding: 0 var(--space-3);
  margin-bottom: var(--space-2);
  font-size: var(--text-xs);
  color: var(--color-text-muted);
}

.admin__logout {
  width: 100%;
  padding: var(--space-2) var(--space-3);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
  background: transparent;
  font-size: var(--text-sm);
  color: var(--color-text-secondary);
  cursor: pointer;
  transition: all var(--transition);
}

.admin__logout:hover:not(:disabled) {
  border-color: var(--color-danger);
  color: var(--color-danger);
}

.admin__logout:disabled {
  cursor: not-allowed;
  opacity: 0.6;
}

.admin__error {
  margin-top: var(--space-2);
  padding: 0 var(--space-3);
  font-size: var(--text-xs);
  color: var(--color-danger);
}

/* ---- 主区域 ---- */
.admin__main {
  flex: 1;
  min-width: 0; /* 防止宽表格把布局撑破 */
  padding: var(--space-5);
}

@media (min-width: 1024px) {
  .admin__side {
    width: 220px;
    padding: var(--space-6) var(--space-4);
  }

  .admin__main {
    padding: var(--space-6) var(--space-7);
  }
}
</style>
