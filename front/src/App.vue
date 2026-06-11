<script setup>
import { computed, nextTick, ref, watch } from 'vue'

const SESSION_ID = 'sess_' + Math.random().toString(36).slice(2, 10)
const MODE_CHAT = 'chat'
const MODE_SEARCH = 'search'

const messages = ref([
  {
    role: 'assistant',
    content: '你好，我是扫地机器人智能客服。你可以直接问我产品功能、使用问题或清洁建议。',
  },
])
const inputValue = ref('')
const loading = ref(false)
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

const placeholderText = computed(() =>
  mode.value === MODE_SEARCH
    ? '输入关键词搜索知识库，例如：滤网更换、WIFI设置'
    : '请输入你的问题，例如：如何设置扫地机器人定时清扫？'
)

const scrollToBottom = async () => {
  await nextTick()
  if (!chatBodyRef.value) return
  chatBodyRef.value.scrollTop = chatBodyRef.value.scrollHeight
}

const toggleMode = () => {
  mode.value = mode.value === MODE_CHAT ? MODE_SEARCH : MODE_CHAT
  searchResults.value = []
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

  const history = messages.value.slice(0, -1).map((m) => ({ role: m.role, content: m.content }))

  try {
    const response = await fetch('/api/chat', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ message, history, session_id: SESSION_ID, user_context: DEFAULT_USER_CONTEXT }),
    })

    const data = await response.json()

    if (!response.ok || data.success === false) {
      throw new Error(data.message || '请求失败，请稍后重试。')
    }

    messages.value.push({
      role: 'assistant',
      content: data.data?.answer || '暂时没有获取到回答，请稍后再试。',
    })
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '请求失败，请稍后重试。'
  } finally {
    loading.value = false
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
          <p class="chat-kicker">{{ mode === MODE_CHAT ? '智能问答' : '知识库检索' }}</p>
          <h1>扫地机器人智能客服</h1>
          <p class="chat-subtitle">
            {{ mode === MODE_CHAT ? '支持多轮对话与上下文理解，回答逐字流式输出。' : '直接搜索知识库，查看匹配的参考资料及相似度。' }}
          </p>
        </div>
        <div class="header-right">
          <button class="mode-toggle" :class="{ 'mode-toggle--search': mode === MODE_SEARCH }" @click="toggleMode">
            {{ mode === MODE_CHAT ? '🔍 检索模式' : '💬 对话模式' }}
          </button>
          <div class="chat-status" :class="{ 'chat-status--loading': loading }">
            {{ loading ? '正在查询...' : '可以开始提问' }}
          </div>
        </div>
      </header>

      <main ref="chatBodyRef" class="chat-body">
        <!-- 对话模式消息 -->
        <div v-if="mode === MODE_CHAT">
          <div
            v-for="(message, index) in messages"
            :key="`msg-${index}`"
            class="message-row"
            :class="`message-row--${message.role}`"
          >
            <div class="message-bubble">
              <span class="message-role">{{ message.role === 'user' ? '我' : '助手' }}</span>
              <p>{{ message.content }}</p>
            </div>
          </div>
        </div>

        <!-- 检索模式结果 -->
        <div v-if="mode === MODE_SEARCH && searchResults.length > 0" class="search-results">
          <p class="search-summary">找到 {{ searchResults.length }} 条相关参考资料</p>
          <div v-for="(r, idx) in searchResults" :key="`sr-${idx}`" class="result-card">
            <div class="result-header">
              <span class="result-index">#{{ idx + 1 }}</span>
              <span class="result-score">相似度 {{ (r.score * 100).toFixed(1) }}%</span>
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

.header-right {
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  gap: 8px;
  flex-shrink: 0;
}

.mode-toggle {
  padding: 6px 16px;
  border: 1.5px solid #2563eb;
  border-radius: 999px;
  background: transparent;
  color: #2563eb;
  font-size: 0.82rem;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.2s;
}

.mode-toggle:hover {
  background: #eff6ff;
}

.mode-toggle--search {
  background: #2563eb;
  color: #fff;
}

.mode-toggle--search:hover {
  background: #1d4ed8;
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
