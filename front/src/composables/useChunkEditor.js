import { computed, ref } from 'vue'

export function useChunkEditor(token, structure, loadStructure) {
  // ── Search ──
  const chunkSearch = ref('')
  const debouncedSearch = ref('')
  let searchTimer = null

  function onSearchInput() {
    clearTimeout(searchTimer)
    searchTimer = setTimeout(() => { debouncedSearch.value = chunkSearch.value.trim().toLowerCase() }, 250)
  }
  function clearSearch() {
    chunkSearch.value = ''
    debouncedSearch.value = ''
  }

  const allChunks = computed(() => {
    const list = []
    if (!structure.value?.categories) return list
    for (const cat of structure.value.categories) {
      for (const file of cat.files) {
        for (const chunk of file.chunks) {
          list.push({
            ...chunk,
            category: cat.name,
            file: file.name,
            source: file.source,
            _contentLower: (chunk.content_preview || '').toLowerCase(),
          })
        }
      }
    }
    return list
  })

  const searchResults = computed(() => {
    if (!debouncedSearch.value) return []
    const q = debouncedSearch.value
    return allChunks.value.filter(c => c._contentLower.includes(q))
  })

  // ── Edit ──
  const editingChunk = ref(null)
  const chunkEditContent = ref('')
  const savingChunk = ref(false)
  const chunkEditMsg = ref('')

  function startChunkEdit(chunk) {
    const flat = allChunks.value.find(c => c.chunk_id === chunk.chunk_id)
    if (!flat) return
    editingChunk.value = {
      chunk_id: chunk.chunk_id,
      content_preview: flat.content_preview,
      category: flat.category,
      file: flat.file,
    }
    chunkEditContent.value = flat.content_preview || ''
    chunkEditMsg.value = ''
  }
  function cancelChunkEdit() {
    editingChunk.value = null
    chunkEditContent.value = ''
    chunkEditMsg.value = ''
  }
  async function saveChunk() {
    if (!editingChunk.value || savingChunk.value) return
    const content = chunkEditContent.value.trim()
    if (!content) { chunkEditMsg.value = '内容不能为空'; return }
    savingChunk.value = true
    chunkEditMsg.value = ''
    try {
      const resp = await fetch('/api/admin/chunk/update', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ token: token.value, chunk_id: editingChunk.value.chunk_id, content }),
      })
      const data = await resp.json()
      if (!resp.ok) throw new Error(data.message || '更新失败')
      chunkEditMsg.value = '✅ 已保存'
      await loadStructure()
      editingChunk.value = null
    } catch (e) {
      chunkEditMsg.value = '❌ ' + (e instanceof Error ? e.message : '更新失败')
    } finally {
      savingChunk.value = false
    }
  }

  return {
    chunkSearch, debouncedSearch, onSearchInput, clearSearch,
    allChunks, searchResults,
    editingChunk, chunkEditContent, savingChunk, chunkEditMsg,
    startChunkEdit, cancelChunkEdit, saveChunk,
  }
}
