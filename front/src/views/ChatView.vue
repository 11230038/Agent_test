<script setup>
import { computed, nextTick, ref, watch } from 'vue'

const sessionId = ref('sess_' + Math.random().toString(36).slice(2, 10))
const MODE_CHAT = 'chat'
const MODE_SEARCH = 'search'
const MODE_CHAT_ONLY = 'chat_only'
const MODES = [MODE_CHAT_ONLY, MODE_CHAT, MODE_SEARCH]
const MODE_LABELS = { chat_only: '仅聊天', chat: '智能问答', search: '知识库检索' }
const MODE_GREETINGS = {
  chat_only: '嗨～我是小扫，你的扫地机器人聊天伙伴！我们可以随便聊聊，有什么想说的吗？😊',
  chat: '你好，我是扫地机器人智能客服。你可以直接问我产品功能、使用问题或清洁建议。',
  search: '输入关键词搜索知识库，例如"滤网更换"、"WIFI设置"，我会返回匹配的参考资料。',
}
const MODE_TITLES = {
  chat_only: '小扫 · 聊聊天',
  chat: '扫地机器人智能客服',
  search: '知识库检索',
}

function renderMarkdown(text) {
  let html = text
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

  // 内联：加粗
  html = html.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')

  // 段落：双换行分割
  const blocks = html.split(/\n\n+/)
  html = blocks.map(b => {
    b = b.trim()
    if (!b) return ''
    if (/^<(h[1-4]|ul|ol|li|br)/.test(b)) return b
    return '<p>' + b.replace(/\n/g, '<br>') + '</p>'
  }).join('')

  return html
}

const messages = ref([
  {
    role: 'assistant',
    content: MODE_GREETINGS[MODE_CHAT],
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

const placeholderText = computed(() => {
  if (mode.value === MODE_SEARCH) return '输入关键词搜索知识库，例如：滤网更换、WIFI设置'
  if (mode.value === MODE_CHAT_ONLY) return '随意聊聊吧，例如：今天过得怎么样？'
  return '请输入你的问题，例如：如何设置扫地机器人定时清扫？'
})

const scrollToBottom = async () => {
  await nextTick()
  if (!chatBodyRef.value) return
  chatBodyRef.value.scrollTop = chatBodyRef.value.scrollHeight
}

const newConversation = () => {
  if (abortController.value) abortController.value.abort()
  sessionId.value = 'sess_' + Math.random().toString(36).slice(2, 10)
  messages.value = [{ role: 'assistant', content: MODE_GREETINGS[mode.value] }]
  searchResults.value = []
  errorMessage.value = ''
  loading.value = false
}

const switchMode = (newMode) => {
  mode.value = newMode
  searchResults.value = []
  messages.value = [{ role: 'assistant', content: MODE_GREETINGS[newMode] }]
  errorMessage.value = ''
}

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
  <div class="chat-page">
    <section class="chat-card">
      <header class="chat-header">
        <div class="chat-heading">
          <p class="chat-kicker">{{ MODE_LABELS[mode] }}</p>
          <h1>{{ MODE_TITLES[mode] }}</h1>
          <p class="chat-subtitle">
            {{ mode === MODE_CHAT_ONLY ? '纯聊天模式，不使用工具和知识库，陪你轻松对话。' : mode === MODE_CHAT ? '智能问答模式，支持多轮对话、知识库检索与上下文理解。' : '知识库检索模式，直接查看匹配的参考资料及相关性分值。' }}
          </p>
        </div>
        <div class="header-right">
          <select class="mode-select" :value="mode" @change="e => switchMode(e.target.value)">
            <option v-for="m in MODES" :key="m" :value="m">{{ m === MODE_CHAT_ONLY ? '💬 仅聊天' : m === MODE_CHAT ? '🤖 智能问答' : '🔍 知识库检索' }}</option>
          </select>
          <div class="header-actions">
            <button class="new-chat-btn" @click="newConversation">＋ 新对话</button>
            <div class="chat-status" :class="{ 'chat-status--loading': loading }">
              {{ loading ? '正在查询...' : '可以开始提问' }}
            </div>
          </div>
        </div>
      </header>

      <main ref="chatBodyRef" class="chat-body">
        <!-- 对话消息（聊天 / 仅聊天 / 智能问答） -->
        <div v-if="mode !== MODE_SEARCH">
          <div
            v-for="(message, index) in messages"
            :key="`msg-${index}`"
            class="message-row"
            :class="`message-row--${message.role}`"
          >
            <div class="message-bubble">
              <span class="message-role">{{ message.role === 'user' ? '我' : '助手' }}</span>
              <p v-if="message.role === 'user'">{{ message.content }}</p>
            <div v-else class="markdown-body" v-html="renderMarkdown(message.content)"></div>
            </div>
          </div>
        </div>

        <!-- 检索模式结果 -->
        <div v-if="mode === MODE_SEARCH && searchResults.length > 0" class="search-results">
          <p class="search-summary">找到 {{ searchResults.length }} 条相关参考资料</p>
          <div v-for="(r, idx) in searchResults" :key="`sr-${idx}`" class="result-card">
            <div class="result-header">
              <span class="result-index">#{{ idx + 1 }}</span>
              <span class="result-score">相关性 {{ r.score.toFixed(3) }}</span>
              <span class="result-category">{{ r.category }}</span>
            </div>
            <p class="result-content">{{ r.content }}</p>
            <div class="result-footer">
              <span class="result-source">📄 {{ r.source }}</span>
            </div>
          </div>
        </div>

        <div v-if="mode === MODE_SEARCH && !loading && searchResults.length === 0 && !errorMessage" class="search-empty">
          <p>输入关键词搜索知识库，例如"滤网更换"、"WIFI设置"</p>
        </div>

        <div v-if="loading" class="message-row message-row--assistant">
          <div class="message-bubble message-bubble--loading">
            <span class="message-role">系统</span>
            <p>正在{{ mode === MODE_SEARCH ? '检索' : '思考' }}中...</p>
          </div>
        </div>
      </main>

      <div class="chat-feedback">
        <p class="input-hint">按 Enter 发送，Shift + Enter 换行</p>
        <p v-if="errorMessage" class="error-text">{{ errorMessage }}</p>
      </div>

      <footer class="chat-footer">
        <textarea
          v-model="inputValue"
          class="chat-input"
          rows="3"
          :placeholder="placeholderText"
          :disabled="loading"
          @keydown="handleKeydown"
        />
        <button
          v-if="loading && mode !== MODE_SEARCH"
          class="send-button send-button--stop"
          @click="stopGeneration"
        >
          ⏹ 停止生成
        </button>
        <button
          v-else
          class="send-button"
          :class="{ 'send-button--search': mode === MODE_SEARCH }"
          :disabled="!canSend"
          @click="sendMessage"
        >
          {{ loading ? '查询中...' : mode === MODE_SEARCH ? '搜索' : '发送' }}
        </button>
      </footer>
    </section>
  </div>
</template>

<style scoped>
.chat-page {
  min-height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
}

.chat-card {
  width: min(960px, 100%);
  height: min(760px, calc(100vh - 48px));
  display: flex;
  flex-direction: column;
  border: 1px solid rgba(148, 163, 184, 0.24);
  border-radius: 24px;
  background: rgba(255, 255, 255, 0.88);
  box-shadow: 0 24px 60px rgba(15, 23, 42, 0.12);
  backdrop-filter: blur(10px);
  overflow: hidden;
}

.chat-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
  padding: 28px 28px 20px;
  border-bottom: 1px solid rgba(148, 163, 184, 0.16);
}

.chat-heading h1 {
  margin-top: 8px;
  font-size: clamp(1.6rem, 2.6vw, 2.2rem);
  font-weight: 700;
  color: #0f172a;
}

.chat-kicker {
  font-size: 0.82rem;
  font-weight: 700;
  letter-spacing: 0.12em;
  color: #2563eb;
}

.chat-subtitle {
  margin-top: 10px;
  color: #475569;
  font-size: 0.88rem;
}

.header-actions {
  display: flex;
  align-items: center;
  gap: 8px;
}

.header-right {
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  gap: 8px;
  flex-shrink: 0;
}

.new-chat-btn {
  padding: 6px 14px;
  border: 1.5px solid rgba(37, 99, 235, 0.25);
  border-radius: 10px;
  background: #eff6ff;
  color: #2563eb;
  font: inherit;
  font-size: 0.8rem;
  font-weight: 600;
  cursor: pointer;
  transition: background 0.15s, border-color 0.15s;
}

.new-chat-btn:hover {
  background: #dbeafe;
  border-color: #2563eb;
}

.mode-select {
  padding: 8px 14px;
  border: 1.5px solid rgba(148, 163, 184, 0.4);
  border-radius: 12px;
  background: #fff;
  color: #0f172a;
  font-size: 0.82rem;
  font-weight: 600;
  cursor: pointer;
  outline: none;
  appearance: auto;
}

.chat-status {
  padding: 8px 14px;
  border-radius: 999px;
  background: #e0f2fe;
  color: #0369a1;
  font-size: 0.82rem;
  font-weight: 600;
}

.chat-status--loading {
  background: #dbeafe;
  color: #1d4ed8;
}

.chat-body {
  flex: 1;
  overflow-y: auto;
  padding: 24px 28px;
  background: linear-gradient(180deg, rgba(248, 250, 252, 0.9) 0%, rgba(241, 245, 249, 0.75) 100%);
}

/* ── 检索结果卡片 ── */
.search-results {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.search-summary {
  font-size: 0.88rem;
  color: #475569;
  margin-bottom: 4px;
}

.result-card {
  padding: 16px;
  border: 1px solid rgba(148, 163, 184, 0.2);
  border-radius: 14px;
  background: #ffffff;
  box-shadow: 0 4px 12px rgba(15, 23, 42, 0.04);
}

.result-header {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 8px;
}

.result-index {
  font-size: 0.78rem;
  font-weight: 700;
  color: #94a3b8;
}

.result-score {
  font-size: 0.78rem;
  font-weight: 600;
  padding: 2px 10px;
  border-radius: 999px;
  background: #dcfce7;
  color: #15803d;
}

.result-category {
  font-size: 0.76rem;
  padding: 2px 8px;
  border-radius: 999px;
  background: #eff6ff;
  color: #2563eb;
}

.result-content {
  font-size: 0.92rem;
  line-height: 1.7;
  color: #1e293b;
  white-space: pre-wrap;
  word-break: break-word;
}

.result-footer {
  margin-top: 10px;
  font-size: 0.78rem;
  color: #94a3b8;
}

.search-empty {
  text-align: center;
  padding: 60px 20px;
  color: #94a3b8;
  font-size: 0.92rem;
}

/* ── 对话消息（保留） ── */
.message-row {
  display: flex;
  margin-bottom: 16px;
}

.message-row--assistant { justify-content: flex-start; }
.message-row--user { justify-content: flex-end; }

.message-bubble {
  max-width: min(78%, 560px);
  padding: 14px 16px;
  border-radius: 20px;
  background: #ffffff;
  color: #0f172a;
  box-shadow: 0 10px 24px rgba(15, 23, 42, 0.08);
}

.message-row--user .message-bubble {
  background: linear-gradient(135deg, #2563eb 0%, #1d4ed8 100%);
  color: #eff6ff;
  border-bottom-right-radius: 8px;
}

.message-row--assistant .message-bubble { border-bottom-left-radius: 8px; }
.message-bubble--loading { background: #eff6ff; color: #1e3a8a; }

.message-role {
  display: inline-block;
  margin-bottom: 6px;
  font-size: 0.8rem;
  font-weight: 700;
  opacity: 0.8;
}

.message-bubble p {
  white-space: pre-wrap;
  word-break: break-word;
  line-height: 1.7;
}

.markdown-body strong { font-weight: 700; }
.markdown-body ul { padding-left: 18px; margin: 4px 0; }
.markdown-body li { line-height: 1.6; margin: 2px 0; }
.markdown-body hr { border: none; border-top: 1px solid #e2e8f0; margin: 12px 0; }
.markdown-body p { margin: 6px 0; line-height: 1.7; }

.chat-feedback {
  padding: 14px 28px 0;
}

.input-hint {
  font-size: 0.86rem;
  color: #64748b;
}

.error-text {
  margin-top: 8px;
  color: #dc2626;
  font-size: 0.92rem;
}

.chat-footer {
  display: flex;
  gap: 14px;
  align-items: flex-end;
  padding: 16px 28px 28px;
}

.chat-input {
  flex: 1;
  min-height: 88px;
  padding: 14px 16px;
  border: 1px solid rgba(148, 163, 184, 0.4);
  border-radius: 18px;
  background: rgba(255, 255, 255, 0.94);
  color: #0f172a;
  font: inherit;
  line-height: 1.7;
  resize: none;
  outline: none;
  transition: border-color 0.2s ease, box-shadow 0.2s ease;
}

.chat-input:focus {
  border-color: rgba(37, 99, 235, 0.6);
  box-shadow: 0 0 0 4px rgba(37, 99, 235, 0.12);
}

.chat-input:disabled {
  cursor: not-allowed;
  background: rgba(241, 245, 249, 0.9);
}

.send-button {
  min-width: 100px;
  height: 52px;
  padding: 0 20px;
  border: none;
  border-radius: 16px;
  background: linear-gradient(135deg, #2563eb 0%, #1d4ed8 100%);
  color: #ffffff;
  font: inherit;
  font-weight: 700;
  cursor: pointer;
  transition: transform 0.2s ease, box-shadow 0.2s ease;
  box-shadow: 0 14px 28px rgba(37, 99, 235, 0.24);
}

.send-button:hover:enabled { transform: translateY(-1px); }
.send-button:disabled { cursor: not-allowed; opacity: 0.6; box-shadow: none; }

.send-button--search {
  background: linear-gradient(135deg, #059669 0%, #047857 100%);
  box-shadow: 0 14px 28px rgba(5, 150, 105, 0.24);
}

.send-button--stop {
  background: linear-gradient(135deg, #dc2626 0%, #991b1b 100%);
  box-shadow: 0 14px 28px rgba(220, 38, 38, 0.3);
  animation: pulse-stop 1.5s ease-in-out infinite;
}

@keyframes pulse-stop {
  0%, 100% { box-shadow: 0 14px 28px rgba(220, 38, 38, 0.3); }
  50% { box-shadow: 0 14px 36px rgba(220, 38, 38, 0.5); }
}

@media (max-width: 768px) {
  .chat-card {
    height: calc(100vh - 24px);
    border-radius: 20px;
  }

  .chat-header, .chat-body, .chat-feedback, .chat-footer {
    padding-left: 18px;
    padding-right: 18px;
  }

  .chat-header {
    flex-direction: column;
    align-items: flex-start;
    padding-top: 22px;
    padding-bottom: 18px;
  }

  .header-right {
    flex-direction: row;
    align-items: center;
    width: 100%;
  }

  .chat-footer {
    flex-direction: column;
    align-items: stretch;
    padding-bottom: 18px;
  }

  .send-button { width: 100%; }
  .message-bubble { max-width: 88%; }
}
</style>
