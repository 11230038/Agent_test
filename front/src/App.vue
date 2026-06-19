<script setup>
import { useRouter, useRoute } from 'vue-router'

const router = useRouter()
const route = useRoute()

const isAdmin = route.path === '/admin'
</script>

<template>
  <div id="app-shell">
    <nav class="app-nav">
      <span class="nav-brand" @click="router.push('/')">
        <span class="brand-icon">🤖</span>
        <span class="brand-text">小扫助手</span>
      </span>
      <div class="nav-links">
        <button class="nav-link" :class="{ active: route.path === '/' }" @click="router.push('/')">💬 聊天</button>
        <button class="nav-link" :class="{ active: route.path === '/admin' }" @click="router.push('/admin')">⚙️ 管理</button>
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
#app-shell { min-height: 100vh; }

.app-nav {
  display: flex; align-items: center; justify-content: space-between;
  padding: 0 32px; height: 60px;
  background: rgba(255,255,255,0.5);
  backdrop-filter: blur(20px) saturate(1.3);
  border-bottom: 1px solid rgba(148,163,184,0.08);
  box-shadow:
    0 1px 3px rgba(15,23,42,0.03),
    0 4px 12px rgba(15,23,42,0.04);
  position: sticky; top: 0; z-index: 100;
}

.app-nav::after {
  content: '';
  position: absolute; bottom: 0; left: 32px; right: 32px; height: 1px;
  background: linear-gradient(90deg, transparent, rgba(37,99,235,0.15), rgba(124,58,237,0.15), transparent);
}

.nav-brand {
  display: flex; align-items: center; gap: 10px;
  cursor: pointer; user-select: none;
}
.brand-icon {
  font-size: 1.5rem;
  filter: drop-shadow(0 2px 4px rgba(37,99,235,0.2));
  transition: transform 0.2s;
}
.nav-brand:hover .brand-icon { transform: scale(1.1) rotate(-5deg); }
.brand-text {
  font-size: 1.2rem; font-weight: 800; letter-spacing: -0.01em;
  background: linear-gradient(135deg, #2563eb 0%, #7c3aed 60%, #a855f7 100%);
  -webkit-background-clip: text; -webkit-text-fill-color: transparent;
  background-clip: text;
}

.nav-links {
  display: flex; gap: 6px;
  background: rgba(241,245,249,0.5);
  padding: 4px; border-radius: 14px;
  border: 1px solid rgba(148,163,184,0.06);
}

.nav-link {
  padding: 8px 22px; border: none; border-radius: 11px;
  background: transparent; color: #64748b;
  font: inherit; font-size: 0.88rem; font-weight: 600;
  cursor: pointer; transition: all 0.2s;
}
.nav-link:hover { color: #334155; }
.nav-link.active {
  background: #fff;
  color: #2563eb;
  box-shadow: 0 1px 3px rgba(15,23,42,0.06), 0 1px 2px rgba(15,23,42,0.04);
}
</style>
