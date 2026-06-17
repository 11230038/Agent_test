import { ref } from 'vue'

export function usePromptEditor(token) {
  const prompts = ref([])
  const editingPrompt = ref(null)
  const promptContent = ref('')
  const savingPrompt = ref(false)
  const promptMsg = ref('')

  async function loadPrompts() {
    try {
      const resp = await fetch('/api/admin/prompts', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ token: token.value }),
      })
      if (resp.ok) {
        const data = await resp.json()
        if (data.success) prompts.value = data.data.prompts
      }
    } catch { /* ignore */ }
  }

  async function startPromptEdit(prompt) {
    promptMsg.value = ''
    try {
      const resp = await fetch('/api/admin/prompt/read', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ token: token.value, path: prompt.path }),
      })
      if (!resp.ok) throw new Error('读取失败')
      const data = await resp.json()
      editingPrompt.value = { ...prompt, content: data.data.content }
      promptContent.value = data.data.content
    } catch (e) {
      promptMsg.value = '❌ ' + (e instanceof Error ? e.message : '读取失败')
    }
  }
  function cancelPromptEdit() {
    editingPrompt.value = null
    promptContent.value = ''
  }
  async function savePrompt() {
    if (!editingPrompt.value || savingPrompt.value) return
    savingPrompt.value = true
    promptMsg.value = ''
    try {
      const resp = await fetch('/api/admin/prompt/write', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ token: token.value, path: editingPrompt.value.path, content: promptContent.value }),
      })
      const data = await resp.json()
      if (!resp.ok) throw new Error(data.message || '保存失败')
      promptMsg.value = '✅ 提示词已保存'
      editingPrompt.value = null
    } catch (e) {
      promptMsg.value = '❌ ' + (e instanceof Error ? e.message : '保存失败')
    } finally {
      savingPrompt.value = false
    }
  }

  return {
    prompts, editingPrompt, promptContent, savingPrompt, promptMsg,
    loadPrompts, startPromptEdit, cancelPromptEdit, savePrompt,
  }
}
