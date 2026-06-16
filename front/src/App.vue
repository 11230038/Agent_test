<script setup>
import { useRouter, useRoute } from 'vue-router'

const router = useRouter()
const route = useRoute()

const isAdmin = route.path === '/admin'
</script>

<template>
  <div id="app-shell">
    <nav class="app-nav">
      <span class="nav-brand" @click="router.push('/')">🤖 小扫助手</span>
      <div class="nav-links">
        <button
          class="nav-link"
          :class="{ active: route.path === '/' }"
          @click="router.push('/')"
        >聊天</button>
        <button
          class="nav-link"
          :class="{ active: route.path === '/admin' }"
          @click="router.push('/admin')"
        >⚙️ 管理</button>
      </div>
    </nav>
    <router-view />
  </div>
</template>

<style>
body {
  margin: 0;
  font-family: 'Segoe UI', 'PingFang SC', 'Microsoft YaHei', sans-serif;
  -webkit-font-smoothing: antialiased;
}

*,
*::before,
*::after {
  box-sizing: border-box;
}
</style>

<style scoped>
#app-shell {
  min-height: 100vh;
}

.app-nav {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 28px;
  height: 56px;
  border-bottom: 1px solid rgba(148, 163, 184, 0.18);
  background: rgba(255, 255, 255, 0.82);
  backdrop-filter: blur(8px);
  position: sticky;
  top: 0;
  z-index: 10;
}

.nav-brand {
  font-size: 1.1rem;
  font-weight: 700;
  color: #0f172a;
  cursor: pointer;
  user-select: none;
}

.nav-links {
  display: flex;
  gap: 4px;
}

.nav-link {
  padding: 8px 18px;
  border: none;
  border-radius: 10px;
  background: transparent;
  color: #475569;
  font: inherit;
  font-size: 0.9rem;
  font-weight: 600;
  cursor: pointer;
  transition: background 0.15s, color 0.15s;
}

.nav-link:hover { background: #f1f5f9; color: #0f172a; }
.nav-link.active { background: #eff6ff; color: #2563eb; }
</style>
