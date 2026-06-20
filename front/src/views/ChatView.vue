<script setup>
import { computed, nextTick, onMounted, ref, watch } from 'vue'

const sessionId = ref('sess_' + Math.random().toString(36).slice(2, 10))
const MODE_CHAT = 'chat'
const MODE_SEARCH = 'search'
const MODE_CHAT_ONLY = 'chat_only'

const availableModes = ref([
  { id: 'chat_only', title: '小扫 · 聊聊天' },
  { id: 'chat', title: '扫地机器人智能客服' },
  { id: 'search', title: '知识库检索' },
])
const MODE_LABELS = { chat_only: '仅聊天', chat: '智能问答', search: '知识库检索' }
const MODE_GREETINGS = ref({
  chat: '你好，我是扫地机器人智能客服。你可以直接问我产品功能、使用问题或清洁建议。',
  chat_only: '嗨～我是小扫，你的扫地机器人聊天伙伴！我们可以随便聊聊，有什么想说的吗？😊',
  search: '输入关键词搜索知识库，例如"滤网更换"、"WIFI设置"，我会返回匹配的参考资料。',
})
const MODE_TITLES = ref({
  chat: '扫地机器人智能客服',
  chat_only: '小扫 · 聊聊天',
  search: '知识库检索',
})
const MODE_SUBTITLES = ref({
  chat: '智能问答 · RAG + 工具',
  chat_only: '纯聊天模式 · 轻松对话',
  search: '知识库检索 · 直接搜索',
})
const MODE_PLACEHOLDERS = ref({
  chat: '请输入你的问题，例如：如何设置扫地机器人定时清扫？',
  chat_only: '随意聊聊吧，例如：今天过得怎么样？',
  search: '输入关键词搜索知识库，例如：滤网更换、WIFI设置',
})

const loadModes = async () => {
  try {
    const resp = await fetch('/api/modes')
    const data = await resp.json()
    if (data.success && data.data.modes) {
      availableModes.value = data.data.modes
      for (const m of data.data.modes) {
        if (m.title) MODE_TITLES.value[m.id] = m.title
        if (m.greeting) MODE_GREETINGS.value[m.id] = m.greeting
        if (m.subtitle) MODE_SUBTITLES.value[m.id] = m.subtitle
        if (m.placeholder) MODE_PLACEHOLDERS.value[m.id] = m.placeholder
      }
    }
  } catch { /* */ }
}

const loadConfig = async () => {
  try {
    const resp = await fetch('/api/config')
    const data = await resp.json()
    if (data.success && data.data.config) {
      const c = data.data.config
      if (c.greeting) Object.assign(MODE_GREETINGS.value, c.greeting)
      if (c.title) Object.assign(MODE_TITLES.value, c.title)
      if (c.subtitle) Object.assign(MODE_SUBTITLES.value, c.subtitle)
      if (c.placeholder) Object.assign(MODE_PLACEHOLDERS.value, c.placeholder)
    }
  } catch { /* fallback */ }
  await loadModes()
}

function renderMarkdown(text) {
  if (!text) return ''
  let html = text
    .replace(/([^\n])(【)/g, '$1\n$2')
    .replace(/\*\*(.+?)\*\*/g, '$1')  // 去除 **bold** 标记
    .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')

  // 标题标记 / 分隔线 → 换行
  html = html.replace(/#{2,4} /g, '<br>')
  html = html.replace(/---/g, '<br>')
  // 编号 / 短横列表 → 换行 + 缩进
  html = html.replace(/(\d+)\. /g, '<br>&nbsp;&nbsp;$1. ')
  html = html.replace(/([^\n])(- )/g, '$1<br>&nbsp;&nbsp;$2')

  // 连续列表项分组
  html = html.replace(/((?:^\- .+\n?)+)/gm, (match) => {
    const items = match.trim().split('\n').map(l => '<li>' + l.replace(/^\- /, '') + '</li>').join('')
    return '<ul>' + items + '</ul>'
  })

  // 段落：双换行分割
  const blocks = html.split(/\n\n+/)
  html = blocks.map(b => {
    b = b.trim()
    if (!b) return ''
    if (/^<(h[1-4]|ul|ol|li|br)/.test(b)) return b
    return '<p>' + b.replace(/\n/g, '<br>') + '</p>'
  }).join('')

  // 参考来源 — 提取到末尾独立显示
  html = html.replace(/([。！？\)）])\s*(?:📎\s*)?参考来源[：:]\s*(.+)/, (_, before, source) => {
    return before + '</p><p class="ref-source"><span class="ref-label">📎 参考来源：</span>' + source + '</p><p>'
  })
  html = html.replace(/<p>\s*<\/p>/g, '')  // 清理空段落

  return html
}

const messages = ref([
  {
    role: 'assistant',
    content: MODE_GREETINGS.value[MODE_CHAT],
  },
])
const inputValue = ref('')
const loading = ref(false)
const abortController = ref(null)
const errorMessage = ref('')
const chatBodyRef = ref(null)
const mode = ref(MODE_CHAT)
const searchResults = ref([])

const canSend = computed(() => Boolean(inputValue.value.trim()) && !loading.value)

const DEFAULT_USER_CONTEXT = {
  user_id: '1004',
  city: '北京',
  month: new Date().toISOString().slice(0, 7),
}

const placeholderText = computed(() => MODE_PLACEHOLDERS.value[mode.value] || '')

const scrollToBottom = async () => {
  await nextTick()
  if (!chatBodyRef.value) return
  chatBodyRef.value.scrollTop = chatBodyRef.value.scrollHeight
}

const newConversation = () => {
  if (abortController.value) abortController.value.abort()
  sessionId.value = 'sess_' + Math.random().toString(36).slice(2, 10)
  messages.value = [{ role: 'assistant', content: MODE_GREETINGS.value[mode.value] }]
  searchResults.value = []
  errorMessage.value = ''
  loading.value = false
  currentSessionName.value = ''
}

const switchMode = (newMode) => {
  mode.value = newMode
  searchResults.value = []
  messages.value = [{ role: 'assistant', content: MODE_GREETINGS.value[newMode] }]
  errorMessage.value = ''
}

// ── 会话侧栏 ──
const showSidebar = ref(false)
const sessions = ref([])
const loadingSessions = ref(false)
const currentSessionName = ref('')

const loadSessions = async () => {
  loadingSessions.value = true
  try {
    const url = mode.value !== 'search'
      ? `/api/sessions?mode=${mode.value}`
      : '/api/sessions'
    const resp = await fetch(url)
    const data = await resp.json()
    if (data.success) {
      sessions.value = data.data.sessions.map(s => ({
        ...s,
        label: new Date(s.last_active * 1000).toLocaleString('zh-CN', { month: 'numeric', day: 'numeric', hour: '2-digit', minute: '2-digit' }),
        title: (s.preview || '').slice(0, 30) || '(空对话)',
      }))
    }
  } catch { /* ignore */ }
  loadingSessions.value = false
}

const loadSession = async (sid) => {
  try {
    const resp = await fetch(`/api/session/${sid}`)
    const data = await resp.json()
    if (data.success && data.data.history.length > 0) {
      sessionId.value = sid
      messages.value = data.data.history
      searchResults.value = []
      errorMessage.value = ''
      showSidebar.value = false
      currentSessionName.value = sid
      await nextTick()
      scrollToBottom()
    }
  } catch { /* ignore */ }
}

const exportConversation = () => {
  if (messages.value.length === 0) return
  const lines = messages.value.map(m => {
    const role = m.role === 'user' ? '我' : '小扫'
    const text = m.content.replace(/\n/g, '\n> ')
    return `### ${role}\n> ${text}\n`
  })
  const md = `# 对话记录\n\n日期: ${new Date().toLocaleString('zh-CN')}\n\n---\n\n${lines.join('\n')}`
  const blob = new Blob([md], { type: 'text/markdown' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = `对话记录_${new Date().toISOString().slice(0, 10)}.md`
  a.click()
  URL.revokeObjectURL(url)
}

onMounted(() => { loadSessions(); loadConfig() })

const sendSearch = async () => {
  const query = inputValue.value.trim()
  if (!query || loading.value) return

  inputValue.value = ''
  errorMessage.value = ''
  loading.value = true
  searchResults.value = []

  try {
    const response = await fetch('/api/rag/search', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ query }),
    })

    if (!response.ok) {
      let detail = '检索失败，请稍后重试。'
      let errData = null
      try { errData = await response.json() } catch { /* ignore */ }
      if (errData && errData.message) detail = errData.message
      throw new Error(detail)
    }

    const data = await response.json()
    if (!data.success) {
      throw new Error(data.message || '检索失败')
    }

    searchResults.value = data.data?.results || []
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '检索失败，请稍后重试。'
  } finally {
    loading.value = false
  }
}

const sendMessage = async () => {
  if (mode.value === MODE_SEARCH) {
    return sendSearch()
  }

  const message = inputValue.value.trim()
  if (!message || loading.value) return

  messages.value.push({ role: 'user', content: message })
  inputValue.value = ''
  errorMessage.value = ''
  loading.value = true
  abortController.value = new AbortController()

  const history = messages.value.slice(-16, -1).map((m) => ({ role: m.role, content: m.content }))
  let idx = -1  // 提升到 try 外部，供 catch 使用

  try {
    const response = await fetch('/api/chat/stream', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ message, history, session_id: sessionId.value, user_context: DEFAULT_USER_CONTEXT, mode: mode.value }),
      signal: abortController.value.signal,
    })

    if (!response.ok) {
      let detail = '请求失败，请稍后重试。'
      let errData = null
      try { errData = await response.json() } catch { /* ignore */ }
      if (errData && errData.message) detail = errData.message
      throw new Error(detail)
    }

    const reader = response.body.getReader()
    const decoder = new TextDecoder()
    let buf = ''
    let content = ''

    messages.value.push({ role: 'assistant', content: '' })
    idx = messages.value.length - 1

    while (true) {
      const { done, value } = await reader.read()
      if (done) {
        buf += decoder.decode()
        for (const line of buf.split('\n')) {
          if (line.startsWith('data: ')) {
            const t = line.slice(6)
            if (t.trim()) content += t
          }
        }
        break
      }
      buf += decoder.decode(value, { stream: true })
      const lines = buf.split('\n')
      buf = lines.pop() || ''
      for (const line of lines) {
        if (!line.startsWith('data: ')) continue
        const t = line.slice(6)
        if (!t.trim()) continue
        if (t.startsWith('[ERROR]')) throw new Error(t.slice(8))
        content += t
        messages.value[idx].content = content.trim()
        await nextTick()
        scrollToBottom()
      }
    }
    messages.value[idx].content = content.trim()
  } catch (error) {
    const isAborted =
      error?.name === 'AbortError' ||
      (error instanceof DOMException && error.name === 'AbortError') ||
      (error?.message || '').includes('abort') ||
      (error?.message || '').includes('AbortError') ||
      (error?.message || '').includes('The operation was aborted') ||
      abortController.value?.signal?.aborted === true

    if (isAborted) {
      if (idx >= 0 && messages.value[idx]) {
        const current = messages.value[idx].content.trim()
        messages.value[idx].content = current
          ? current + '\n\n---\n*⏹ 输出已被终止*'
          : '*⏹ 输出已被终止*'
      }
    } else {
      errorMessage.value = error instanceof Error ? error.message : '请求失败，请稍后重试。'
    }
  } finally {
    loading.value = false
    abortController.value = null
  }
}

const stopGeneration = () => {
  if (abortController.value) {
    abortController.value.abort()
  }
}

const handleKeydown = async (event) => {
  if (event.key === 'Enter' && !event.shiftKey) {
    event.preventDefault()
    await sendMessage()
  }
}

watch(
  () => [messages.value.length, searchResults.value.length, loading.value],
  () => { void scrollToBottom() },
  { immediate: true },
)
</script>

<template>
  <div>
  <div class="chat-page">
    <section class="chat-card">
      <header class="chat-header">
        <div class="header-left">
          <div class="avatar-ring">
            <span class="avatar-icon">{{ mode === MODE_CHAT_ONLY ? '💬' : mode === MODE_CHAT ? '🤖' : '🔍' }}</span>
          </div>
          <div class="chat-heading">
            <h1>{{ MODE_TITLES[mode] }}</h1>
            <p class="chat-subtitle">
              {{ MODE_SUBTITLES[mode] }}
            </p>
          </div>
        </div>
        <div class="header-right">
          <select class="mode-select" :value="mode" @change="e => switchMode(e.target.value)">
            <option v-for="m in availableModes" :key="m.id" :value="m.id">{{ m.id === 'chat_only' ? '💬 仅聊天' : m.id === 'chat' ? '🤖 智能问答' : m.id === 'search' ? '🔍 知识库检索' : '📌 ' + m.title }}</option>
          </select>
          <div class="header-actions">
            <button v-if="mode !== MODE_SEARCH" class="icon-btn" title="历史对话" @click="showSidebar = !showSidebar; loadSessions()">📋</button>
            <button v-if="mode !== MODE_SEARCH" class="icon-btn" title="导出对话" @click="exportConversation">📥</button>
            <button class="new-chat-btn" @click="newConversation">＋ 新对话</button>
            <div class="chat-status" :class="{ 'chat-status--loading': loading }">
              {{ loading ? '生成中...' : '在线' }}
            </div>
          </div>
        </div>
      </header>

      <main ref="chatBodyRef" class="chat-body">
        <div v-if="mode !== MODE_SEARCH">
          <div
            v-for="(message, index) in messages"
            :key="`msg-${index}`"
            class="message-row"
            :class="`message-row--${message.role}`"
          >
            <div class="msg-avatar">{{ message.role === 'user' ? '👤' : '🤖' }}</div>
            <div class="msg-body">
              <div class="msg-sender">{{ message.role === 'user' ? '我' : '小扫' }}</div>
              <div class="message-bubble">
                <p v-if="message.role === 'user'">{{ message.content }}</p>
                <div v-else class="markdown-body" v-html="renderMarkdown(message.content)"></div>
              </div>
            </div>
          </div>
        </div>

        <div v-if="mode === MODE_SEARCH && searchResults.length > 0" class="search-results">
          <p class="search-summary">🔍 找到 {{ searchResults.length }} 条结果</p>
          <div v-for="(r, idx) in searchResults" :key="`sr-${idx}`" class="result-card">
            <div class="result-header">
              <span class="result-index">#{{ idx + 1 }}</span>
              <span class="result-score">{{ r.score.toFixed(3) }}</span>
              <span class="result-category">{{ r.category }}</span>
              <span class="result-source">📄 {{ r.source }}</span>
            </div>
            <p class="result-content">{{ r.content }}</p>
          </div>
        </div>

        <div v-if="mode === MODE_SEARCH && !loading && searchResults.length === 0 && !errorMessage" class="search-empty">
          <p>输入关键词搜索知识库，例如"滤网更换"、"WIFI设置"</p>
        </div>

        <div v-if="loading" class="message-row message-row--assistant">
          <div class="msg-avatar">🤖</div>
          <div class="msg-body">
            <div class="msg-sender">小扫</div>
            <div class="message-bubble message-bubble--loading">
              <span class="loading-dots">思考中<span class="dot">.</span><span class="dot">.</span><span class="dot">.</span></span>
            </div>
          </div>
        </div>
      </main>

      <p v-if="errorMessage" class="error-text">{{ errorMessage }}</p>

      <footer class="chat-footer">
        <textarea
          v-model="inputValue"
          class="chat-input"
          rows="2"
          :placeholder="placeholderText"
          :disabled="loading"
          @keydown="handleKeydown"
        />
        <button
          v-if="loading && mode !== MODE_SEARCH"
          class="send-button send-button--stop"
          @click="stopGeneration"
        >停止</button>
        <button
          v-else
          class="send-button"
          :class="{ 'send-button--search': mode === MODE_SEARCH }"
          :disabled="!canSend"
          @click="sendMessage"
        >
          {{ mode === MODE_SEARCH ? '搜索' : '发送' }}
        </button>
      </footer>
    </section>
  </div>

  <!-- ═══ 历史会话侧栏 ═══ -->
  <Teleport to="body">
    <div v-if="showSidebar" class="sidebar-overlay" @click.self="showSidebar = false">
      <div class="sidebar-panel">
        <div class="sidebar-header">
          <h3>📋 历史对话 · {{ MODE_LABELS[mode] }}</h3>
          <button class="icon-btn" @click="showSidebar = false">✕</button>
        </div>
        <div class="sidebar-body">
          <div v-if="loadingSessions" class="sidebar-empty">加载中...</div>
          <div v-else-if="sessions.length === 0" class="sidebar-empty">暂无历史对话</div>
          <div
            v-for="s in sessions"
            :key="s.session_id"
            class="session-item"
            :class="{ 'session-item--active': s.session_id === sessionId }"
            @click="loadSession(s.session_id)"
          >
            <span class="session-name">{{ s.title }}</span>
            <span class="session-meta">{{ s.msg_count }} 条 · {{ s.label }}</span>
          </div>
        </div>
      </div>
    </div>
  </Teleport>
  </div>
</template>

<style scoped>
.chat-page {
  min-height: calc(100vh - 60px);
  display: flex; align-items: center; justify-content: center;
  padding: 20px;
}
.chat-card {
  width: min(1000px, 100%);
  height: min(800px, calc(100vh - 100px));
  display: flex; flex-direction: column;
  border: 1px solid rgba(148,163,184,0.05);
  border-radius: 30px;
  background: rgba(255,255,255,0.5);
  box-shadow: 0 2px 20px rgba(15,23,42,0.03);
  backdrop-filter: blur(22px) saturate(1.05);
  overflow: hidden;
}

.chat-header {
  display: flex; align-items: center; justify-content: space-between;
  gap: 16px; padding: 18px 24px;
  background: rgba(255,255,255,0.5);
  border-bottom: 1px solid rgba(148,163,184,0.05);
}
.header-left { display: flex; align-items: center; gap: 12px; }
.avatar-ring {
  width: 42px; height: 42px; border-radius: 50%;
  background: linear-gradient(135deg, rgba(37,99,235,0.1), rgba(124,58,237,0.06));
  display: flex; align-items: center; justify-content: center;
  border: 2px solid rgba(37,99,235,0.08);
  flex-shrink: 0;
}
.avatar-icon { font-size: 1.2rem; }
.chat-heading h1 { font-size: 1.2rem; font-weight: 700; color: #0f172a; }
.chat-subtitle { color: #94a3b8; font-size: 0.78rem; margin-top: 1px; }

.header-right { display: flex; flex-direction: column; align-items: flex-end; gap: 8px; flex-shrink: 0; }
.header-actions { display: flex; align-items: center; gap: 8px; }

.icon-btn {
  width: 32px; height: 32px;
  border: 1px solid rgba(148,163,184,0.1);
  border-radius: 10px;
  background: rgba(255,255,255,0.5);
  font-size: 1rem; cursor: pointer;
  display: flex; align-items: center; justify-content: center;
  transition: all 0.15s;
}
.icon-btn:hover { background: #fff; border-color: rgba(37,99,235,0.25); box-shadow: 0 2px 8px rgba(37,99,235,0.06); }

.new-chat-btn {
  padding: 7px 14px;
  border: 1px solid rgba(37,99,235,0.1);
  border-radius: 10px;
  background: rgba(239,246,255,0.4);
  color: #2563eb;
  font: inherit; font-size: 0.78rem; font-weight: 600;
  cursor: pointer; transition: all 0.2s;
}
.new-chat-btn:hover { background: #dbeafe; border-color: rgba(37,99,235,0.25); transform: translateY(-1px); }

.mode-select {
  padding: 8px 14px;
  border: 1px solid rgba(148,163,184,0.12);
  border-radius: 12px;
  background: rgba(255,255,255,0.5);
  color: #334155; font-size: 0.78rem; font-weight: 600;
  cursor: pointer; outline: none; transition: all 0.2s;
}
.mode-select:hover { border-color: rgba(37,99,235,0.25); }

.chat-status {
  padding: 6px 12px; border-radius: 999px;
  background: rgba(239,246,255,0.6); color: #2563eb;
  font-size: 0.74rem; font-weight: 600;
  display: flex; align-items: center; gap: 5px;
}
.chat-status::before { content: ''; width: 7px; height: 7px; border-radius: 50%; background: #22c55e; }
.chat-status--loading::before { background: #f59e0b; animation: blink 1s infinite; }
.chat-status--loading { background: rgba(254,243,199,0.6); color: #b45309; }
@keyframes blink { 0%,100%{opacity:1} 50%{opacity:0.3} }

.chat-body { flex: 1; overflow-y: auto; padding: 20px 28px; scroll-behavior: smooth; }

/* ── 检索结果 ── */
.search-results { display: flex; flex-direction: column; gap: 10px; }
.search-summary { font-size: 0.84rem; color: #64748b; margin-bottom: 4px; }
.result-card {
  padding: 16px 18px; border-radius: 16px;
  background: rgba(255,255,255,0.5);
  border: 1px solid rgba(148,163,184,0.06);
  backdrop-filter: blur(6px);
}
.result-header { display: flex; align-items: center; gap: 10px; margin-bottom: 10px; flex-wrap: wrap; }
.result-index { font-size: 0.74rem; font-weight: 700; color: #94a3b8; }
.result-score { font-size: 0.7rem; font-weight: 600; padding: 2px 8px; border-radius: 999px; background: #dcfce7; color: #15803d; }
.result-category { font-size: 0.7rem; padding: 2px 8px; border-radius: 999px; background: #eff6ff; color: #2563eb; }
.result-source { font-size: 0.7rem; color: #94a3b8; }
.result-content { font-size: 0.88rem; line-height: 1.65; color: #334155; white-space: pre-wrap; word-break: break-word; }
.search-empty { text-align: center; padding: 60px 20px; color: #94a3b8; }

/* ── 对话消息 ── */
.message-row { display: flex; gap: 10px; margin-bottom: 22px; align-items: flex-start; }
.message-row--user { flex-direction: row-reverse; }

.msg-avatar {
  width: 34px; height: 34px; border-radius: 50%;
  background: rgba(255,255,255,0.5);
  border: 1px solid rgba(148,163,184,0.06);
  display: flex; align-items: center; justify-content: center;
  font-size: 0.9rem; flex-shrink: 0;
}
.msg-body { max-width: min(78%, 620px); }
.msg-sender { font-size: 0.72rem; font-weight: 600; color: #94a3b8; margin-bottom: 4px; padding: 0 4px; }
.message-row--user .msg-sender { text-align: right; }

.message-bubble {
  padding: 12px 16px; border-radius: 18px;
  background: rgba(255,255,255,0.5);
  color: #1e293b; line-height: 1.65;
  box-shadow: 0 1px 6px rgba(15,23,42,0.03);
  border: 1px solid rgba(148,163,184,0.04);
  backdrop-filter: blur(6px);
}
.message-row--user .message-bubble {
  background: linear-gradient(135deg, #3b82f6, #2563eb);
  color: #fff; border: none;
  border-bottom-right-radius: 8px;
  box-shadow: 0 4px 14px rgba(37,99,235,0.18);
}
.message-row--assistant .message-bubble { border-bottom-left-radius: 8px; }
.message-bubble--loading {
  background: rgba(239,246,255,0.5); color: #2563eb;
  border: 1px solid rgba(37,99,235,0.06);
}

.loading-dots { font-size: 0.88rem; }
.dot { animation: dot-bounce 1.4s infinite; }
.dot:nth-child(2) { animation-delay: 0.2s; }
.dot:nth-child(3) { animation-delay: 0.4s; }
@keyframes dot-bounce { 0%,80%,100%{opacity:0.2} 40%{opacity:1} }

.message-bubble p { white-space: pre-wrap; word-break: break-word; }

/* ── Markdown ── */
.markdown-body { line-height: 1.7; color: #1e293b; word-break: break-word; }
.markdown-body h1,.markdown-body h2,.markdown-body h3,.markdown-body h4 { margin: 14px 0 8px; font-weight: 700; color: #0f172a; }
.markdown-body h1 { font-size: 1.3rem; border-bottom: 2px solid #e2e8f0; padding-bottom: 4px; }
.markdown-body h2 { font-size: 1.15rem; }
.markdown-body h3 { font-size: 1.02rem; }
.markdown-body p { margin: 4px 0; }
.markdown-body strong { font-weight: 700; }
.markdown-body a { color: #2563eb; }
.markdown-body ul,.markdown-body ol { padding-left: 20px; margin: 4px 0; }
.markdown-body li { margin: 2px 0; }
.markdown-body blockquote { margin: 8px 0; padding: 6px 14px; border-left: 3px solid #2563eb; background: #f0f6ff; border-radius: 0 6px 6px 0; }
.markdown-body code { padding: 2px 5px; border-radius: 4px; background: #f1f5f9; color: #c7254e; font-family: 'Consolas',monospace; font-size: 0.87em; }
.markdown-body pre { margin: 8px 0; padding: 12px 14px; border-radius: 10px; background: #1e293b; color: #e2e8f0; overflow-x: auto; font-size: 0.82rem; }
.markdown-body pre code { padding: 0; background: none; color: inherit; }
.markdown-body table { width: 100%; margin: 10px 0; border-collapse: collapse; font-size: 0.84rem; }
.markdown-body th,.markdown-body td { padding: 7px 10px; border: 1px solid #e2e8f0; text-align: left; }
.markdown-body th { background: #f8fafc; font-weight: 700; }
.markdown-body tr:nth-child(even) td { background: #f8fafc; }
.markdown-body hr { border: none; border-top: 1px solid #e2e8f0; margin: 14px 0; }
.markdown-body :deep(.ref-source) { display: none; }

/* ── Input ── */
.error-text { margin: 0 28px; color: #dc2626; font-size: 0.84rem; }

.chat-footer { display: flex; gap: 10px; align-items: flex-end; padding: 12px 22px 18px; }

.chat-input {
  flex: 1; min-height: 48px; max-height: 120px;
  padding: 12px 16px;
  border: 1.5px solid rgba(148,163,184,0.15);
  border-radius: 18px;
  background: rgba(255,255,255,0.5);
  color: #0f172a; font: inherit; line-height: 1.6;
  resize: none; outline: none;
  transition: all 0.25s;
}
.chat-input:focus { border-color: rgba(37,99,235,0.35); box-shadow: 0 0 0 4px rgba(37,99,235,0.05); background: rgba(255,255,255,0.75); }
.chat-input:disabled { opacity: 0.5; }

.send-button {
  min-width: 72px; height: 42px; padding: 0 16px;
  border: none; border-radius: 14px;
  background: linear-gradient(135deg, #3b82f6, #2563eb);
  color: #fff; font: inherit; font-weight: 700; font-size: 0.86rem;
  cursor: pointer; transition: all 0.2s;
  box-shadow: 0 4px 12px rgba(37,99,235,0.2);
  flex-shrink: 0;
}
.send-button:hover:enabled { transform: translateY(-2px); box-shadow: 0 6px 18px rgba(37,99,235,0.3); }
.send-button:disabled { opacity: 0.4; box-shadow: none; cursor: not-allowed; }
.send-button--search { background: linear-gradient(135deg, #10b981, #059669); box-shadow: 0 4px 12px rgba(5,150,105,0.2); }
.send-button--stop { background: linear-gradient(135deg, #ef4444, #dc2626); box-shadow: 0 4px 12px rgba(220,38,38,0.25); animation: pulse-stop 1.5s ease-in-out infinite; }
@keyframes pulse-stop { 0%,100%{box-shadow:0 4px 12px rgba(220,38,38,0.25)} 50%{box-shadow:0 4px 20px rgba(220,38,38,0.45)} }

/* ── 历史侧栏 ── */
.sidebar-overlay {
  position: fixed; inset: 0; z-index: 2000;
  display: flex; justify-content: flex-end;
  background: rgba(15,23,42,0.2);
  backdrop-filter: blur(4px);
}
.sidebar-panel {
  width: 340px; height: 100vh;
  background: rgba(255,255,255,0.85);
  backdrop-filter: blur(20px);
  box-shadow: -8px 0 40px rgba(15,23,42,0.08);
  display: flex; flex-direction: column;
}
.sidebar-header {
  display: flex; align-items: center; justify-content: space-between;
  padding: 20px 22px;
  border-bottom: 1px solid rgba(148,163,184,0.08);
  background: linear-gradient(180deg, rgba(248,250,255,0.9), transparent);
}
.sidebar-header h3 { font-size: 1.1rem; font-weight: 700; color: #0f172a; }
.sidebar-body { flex: 1; overflow-y: auto; padding: 10px 12px; }
.sidebar-empty { text-align: center; padding: 60px 20px; color: #94a3b8; font-size: 0.88rem; }
.session-item {
  padding: 13px 16px; border-radius: 12px; cursor: pointer;
  transition: all 0.15s; margin-bottom: 3px;
  display: flex; flex-direction: column; gap: 3px;
  border: 1px solid transparent;
}
.session-item:hover { background: #f8faff; border-color: rgba(37,99,235,0.08); }
.session-item--active { background: #eff6ff; border-color: rgba(37,99,235,0.15); }
.session-name { font-size: 0.88rem; font-weight: 600; color: #1e293b; }
.session-meta { font-size: 0.74rem; color: #94a3b8; }

@media (max-width: 768px) {
  .sidebar-panel { width: 100vw; }
  .chat-page { padding: 8px; }
  .chat-card { height: calc(100vh - 16px); border-radius: 20px; }
  .chat-header,.chat-body { padding-left: 14px; padding-right: 14px; }
  .chat-header { flex-wrap: wrap; padding-top: 14px; padding-bottom: 12px; }
  .header-right { flex-direction: row; align-items: center; width: 100%; }
  .chat-footer { flex-direction: column; align-items: stretch; padding: 10px 14px 14px; }
  .send-button { width: 100%; }
  .msg-body { max-width: 85%; }
}
</style>
