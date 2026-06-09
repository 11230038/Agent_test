<script setup>
import { computed, nextTick, ref, watch } from 'vue'

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

const canSend = computed(() => Boolean(inputValue.value.trim()) && !loading.value)

const scrollToBottom = async () => {
  await nextTick()

  if (!chatBodyRef.value) {
    return
  }

  chatBodyRef.value.scrollTop = chatBodyRef.value.scrollHeight
}

const sendMessage = async () => {
  const message = inputValue.value.trim()
  if (!message || loading.value) {
    return
  }

  messages.value.push({
    role: 'user',
    content: message,
  })
  inputValue.value = ''
  errorMessage.value = ''
  loading.value = true

  try {
    const response = await fetch('/api/chat', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ message }),
    })

    let data = {}

    try {
      data = await response.json()
    } catch {
      data = {}
    }

    if (!response.ok) {
      throw new Error(data.detail || '请求失败，请稍后重试。')
    }

    messages.value.push({
      role: 'assistant',
      content: data.answer || '暂时没有获取到回答，请稍后再试。',
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
  () => [messages.value.length, loading.value],
  () => {
    void scrollToBottom()
  },
  { immediate: true },
)
</script>

<template>
  <div class="chat-page">
    <section class="chat-card">
      <header class="chat-header">
        <div class="chat-heading">
          <p class="chat-kicker">基础问答</p>
          <h1>扫地机器人智能客服</h1>
          <p class="chat-subtitle">支持最基础的产品咨询与使用问答，适合快速演示。</p>
        </div>
        <div class="chat-status" :class="{ 'chat-status--loading': loading }">
          {{ loading ? '正在思考中' : '可以开始提问' }}
        </div>
      </header>

      <main ref="chatBodyRef" class="chat-body">
        <div
          v-for="(message, index) in messages"
          :key="`${message.role}-${index}`"
          class="message-row"
          :class="`message-row--${message.role}`"
        >
          <div class="message-bubble">
            <span class="message-role">{{ message.role === 'user' ? '我' : '助手' }}</span>
            <p>{{ message.content }}</p>
          </div>
        </div>

        <div v-if="loading" class="message-row message-row--assistant">
          <div class="message-bubble message-bubble--loading">
            <span class="message-role">助手</span>
            <p>正在思考中...</p>
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
          placeholder="请输入你的问题，例如：如何设置扫地机器人定时清扫？"
          :disabled="loading"
          @keydown="handleKeydown"
        />
        <button class="send-button" :disabled="!canSend" @click="sendMessage">
          {{ loading ? '发送中...' : '发送' }}
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
}

.chat-status {
  flex-shrink: 0;
  padding: 10px 14px;
  border-radius: 999px;
  background: #e0f2fe;
  color: #0369a1;
  font-size: 0.88rem;
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

.message-row {
  display: flex;
  margin-bottom: 16px;
}

.message-row--assistant {
  justify-content: flex-start;
}

.message-row--user {
  justify-content: flex-end;
}

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

.message-row--assistant .message-bubble {
  border-bottom-left-radius: 8px;
}

.message-bubble--loading {
  background: #eff6ff;
  color: #1e3a8a;
}

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
  transition:
    border-color 0.2s ease,
    box-shadow 0.2s ease,
    background-color 0.2s ease;
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
  min-width: 120px;
  height: 52px;
  padding: 0 20px;
  border: none;
  border-radius: 16px;
  background: linear-gradient(135deg, #2563eb 0%, #1d4ed8 100%);
  color: #ffffff;
  font: inherit;
  font-weight: 700;
  cursor: pointer;
  transition:
    transform 0.2s ease,
    box-shadow 0.2s ease,
    opacity 0.2s ease;
  box-shadow: 0 14px 28px rgba(37, 99, 235, 0.24);
}

.send-button:hover:enabled {
  transform: translateY(-1px);
}

.send-button:disabled {
  cursor: not-allowed;
  opacity: 0.6;
  box-shadow: none;
}

@media (max-width: 768px) {
  .chat-card {
    height: calc(100vh - 24px);
    border-radius: 20px;
  }

  .chat-header,
  .chat-body,
  .chat-feedback,
  .chat-footer {
    padding-left: 18px;
    padding-right: 18px;
  }

  .chat-header {
    flex-direction: column;
    align-items: flex-start;
    padding-top: 22px;
    padding-bottom: 18px;
  }

  .chat-footer {
    flex-direction: column;
    align-items: stretch;
    padding-bottom: 18px;
  }

  .send-button {
    width: 100%;
  }

  .message-bubble {
    max-width: 88%;
  }
}
</style>
