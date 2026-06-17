import { ref } from 'vue'

export function useAdminAuth() {
  const password = ref('')
  const loading = ref(false)
  const error = ref('')
  const authed = ref(false)
  const token = ref('')

  async function login() {
    const pwd = password.value.trim()
    if (!pwd || loading.value) return
    loading.value = true
    error.value = ''
    try {
      const resp = await fetch('/api/admin/login', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ password: pwd }),
      })
      if (!resp.ok) {
        let msg = '密码错误'
        try { const e = await resp.json(); if (e?.message) msg = e.message } catch { /* */ }
        throw new Error(msg)
      }
      const data = await resp.json()
      if (!data.success) throw new Error(data.message || '登录失败')
      token.value = data.data.token
      authed.value = true
      password.value = ''
    } catch (e) {
      error.value = e instanceof Error ? e.message : '登录失败'
    } finally {
      loading.value = false
    }
  }

  return { password, loading, error, authed, token, login }
}
