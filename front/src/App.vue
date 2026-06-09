<script setup>
import { computed, ref } from 'vue'

const messages = ref([
  {
    role: 'assistant',
    content: '你好，我是扫地机器人智能客服。你可以直接问我产品功能、使用问题或清洁建议。',
  },
])
const inputValue = ref('')
const loading = ref(false)
const errorMessage = ref('')

const canSend = computed(() => inputValue.value.trim() && !loading.value)

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

    const data = await response.json()

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
</script>

<template>
  <div class="chat-page">
    <section class="chat-card">
      <header class="chat-header">
        <div>
          <p class="chat-kicker">基础问答</p>
          <h1>扫地机器人智能客服</h1>
        </div>
        <p class="chat-subtitle">只保留最基础的问答能力，适合快速演示。</p>
      </header>

      <main class="chat-body">
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

      <p v-if="errorMessage" class="error-text">{{ errorMessage }}</p>

      <footer class="chat-footer">
        <textarea
          v-model="inputValue"
          class="chat-input"
          rows="3"
          placeholder="请输入你的问题..."
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
