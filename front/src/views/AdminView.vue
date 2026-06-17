<script setup>
import { computed, ref } from 'vue'

const password = ref('')
const loading = ref(false)
const error = ref('')
const authed = ref(false)
const structure = ref(null)

// ── 密码验证 ──
const adminToken = ref('')
const unlock = async () => {
  const pwd = password.value.trim()
  if (!pwd || loading.value) return
  loading.value = true
  error.value = ''
  try {
    // 1. 登录获取 token
    const loginResp = await fetch('/api/admin/login', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ password: pwd }),
    })
    if (!loginResp.ok) {
      let msg = '密码错误'
      try { const e = await loginResp.json(); if (e?.message) msg = e.message } catch { /* */ }
      throw new Error(msg)
    }
    const loginData = await loginResp.json()
    if (!loginData.success) throw new Error(loginData.message || '登录失败')
    adminToken.value = loginData.data.token

    // 2. 用 token 获取知识库结构
    const resp = await fetch('/api/admin/knowledge', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ token: adminToken.value }),
    })
    if (!resp.ok) {
      let msg = '加载失败'
      try { const e = await resp.json(); if (e?.message) msg = e.message } catch { /* */ }
      throw new Error(msg)
    }
    const data = await resp.json()
    if (!data.success) throw new Error(data.message || '请求失败')
    authed.value = true
    structure.value = data.data
    loadPrompts()
    password.value = ''
  } catch (e) {
    error.value = e instanceof Error ? e.message : '请求失败'
  } finally {
    loading.value = false
  }
}

const handleKeydown = (e) => {
  if (e.key === 'Enter') unlock()
}

const expandedCategories = ref({})
const toggleCategory = (name) => {
  expandedCategories.value[name] = !expandedCategories.value[name]
}

// ── 刷新结构 ──
const refreshStructure = async () => {
  try {
    const resp = await fetch('/api/admin/knowledge', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ token: adminToken.value }),
    })
    if (resp.ok) {
      const data = await resp.json()
      if (data.success) structure.value = data.data
    }
  } catch { /* ignore */ }
}

// ── 上传 ──
const uploadFile = ref(null)
const uploadCategory = ref('扫地机器人客服')
const uploadCategoryCustom = ref('')
const uploading = ref(false)
const uploadMsg = ref('')

const customCategories = ref([])
const allCategories = () => {
  const cats = ['扫地机器人客服']
  if (structure.value?.categories) {
    structure.value.categories.forEach(c => {
      if (!cats.includes(c.name)) cats.push(c.name)
    })
  }
  customCategories.value.forEach(c => {
    if (!cats.includes(c)) cats.push(c)
  })
  return cats
}
const effectiveCategory = () => {
  return uploadCategory.value === '__custom__' ? uploadCategoryCustom.value.trim() : uploadCategory.value
}

const handleUpload = async () => {
  if (!uploadFile.value || uploading.value) return
  const cat = effectiveCategory()
  if (!cat) { uploadMsg.value = '请输入分类名称'; return }
  uploading.value = true
  uploadMsg.value = ''
  const form = new FormData()
  form.append('token', adminToken.value)
  form.append('category', cat)
  form.append('file', uploadFile.value)
  try {
    const resp = await fetch('/api/admin/upload', { method: 'POST', body: form })
    const data = await resp.json()
    if (!resp.ok) throw new Error(data.message || '上传失败')
    uploadMsg.value = '✅ ' + (data.message || '上传成功')
    uploadFile.value = null
    const input = document.getElementById('file-input')
    if (input) input.value = ''
    if (uploadCategory.value === '__custom__' && uploadCategoryCustom.value.trim()) {
      if (!customCategories.value.includes(uploadCategoryCustom.value.trim())) {
        customCategories.value.push(uploadCategoryCustom.value.trim())
      }
      uploadCategoryCustom.value = ''
      uploadCategory.value = '扫地机器人客服'
    }
    await refreshStructure()
  } catch (e) {
    uploadMsg.value = '❌ ' + (e instanceof Error ? e.message : '上传失败')
  } finally {
    uploading.value = false
  }
}

// ── 删除 ──
const deleting = ref(false)
const deleteTarget = ref(null)
const deleteError = ref('')
const deleteFileName = computed(() => deleteTarget.value?.name || '')
const deleteFileSource = computed(() => deleteTarget.value?.source || '')

const handleDelete = (source, name) => {
  deleteTarget.value = { source, name }
  deleteError.value = ''
}
const cancelDelete = () => {
  deleteTarget.value = null
  deleteError.value = ''
}
const confirmDelete = async () => {
  const source = deleteFileSource.value
  if (!source || deleting.value) return
  deleting.value = true
  deleteError.value = ''
  try {
    const resp = await fetch('/api/admin/delete', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ token: adminToken.value, source }),
    })
    const data = await resp.json()
    if (!resp.ok) throw new Error(data.message || '删除失败')
    deleteTarget.value = null
    await refreshStructure()
  } catch (e) {
    deleteError.value = e instanceof Error ? e.message : '删除失败'
  } finally {
    deleting.value = false
  }
}

// ── 改分类 ──
const catTarget = ref(null)  // { source, name, oldCategory }
const catNewCategory = ref('')
const catNewCustom = ref('')
const changingCat = ref(false)
const catError = ref('')

const catFileName = computed(() => catTarget.value?.name || '')
const catOldCategory = computed(() => catTarget.value?.oldCategory || '')

const startCatChange = (source, name, oldCat) => {
  catTarget.value = { source, name, oldCategory: oldCat }
  catNewCategory.value = allCategories().includes(oldCat) ? oldCat : '__custom__'
  catNewCustom.value = allCategories().includes(oldCat) ? '' : oldCat
  catError.value = ''
}

const cancelCatChange = () => {
  catTarget.value = null
  catError.value = ''
}

const confirmCatChange = async () => {
  if (!catTarget.value || changingCat.value) return
  const newCat = catNewCategory.value === '__custom__'
    ? catNewCustom.value.trim()
    : catNewCategory.value
  if (!newCat) { catError.value = '分类不能为空'; return }
  if (newCat === catOldCategory.value) { catError.value = '分类未改变'; return }

  changingCat.value = true
  catError.value = ''
  try {
    const resp = await fetch('/api/admin/category', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ token: adminToken.value, source: catTarget.value.source, category: newCat }),
    })
    const data = await resp.json()
    if (!resp.ok) throw new Error(data.message || '更改失败')
    if (catNewCategory.value === '__custom__' && catNewCustom.value.trim()) {
      if (!customCategories.value.includes(catNewCustom.value.trim())) {
        customCategories.value.push(catNewCustom.value.trim())
      }
    }
    catTarget.value = null
    await refreshStructure()
  } catch (e) {
    catError.value = e instanceof Error ? e.message : '更改失败'
  } finally {
    changingCat.value = false
  }
}

// ── 提示词管理 ──
const prompts = ref([])
const editingPrompt = ref(null)
const promptContent = ref('')
const savingPrompt = ref(false)
const promptMsg = ref('')

const loadPrompts = async () => {
  try {
    const resp = await fetch('/api/admin/prompts', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ token: adminToken.value }),
    })
    if (resp.ok) {
      const data = await resp.json()
      if (data.success) prompts.value = data.data.prompts
    }
  } catch { /* ignore */ }
}

const startPromptEdit = async (prompt) => {
  promptMsg.value = ''
  try {
    const resp = await fetch('/api/admin/prompt/read', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ token: adminToken.value, path: prompt.path }),
    })
    if (!resp.ok) throw new Error('读取失败')
    const data = await resp.json()
    editingPrompt.value = { ...prompt, content: data.data.content }
    promptContent.value = data.data.content
  } catch (e) {
    promptMsg.value = '❌ ' + (e instanceof Error ? e.message : '读取失败')
  }
}

const cancelPromptEdit = () => {
  editingPrompt.value = null
  promptContent.value = ''
}

const savePrompt = async () => {
  if (!editingPrompt.value || savingPrompt.value) return
  savingPrompt.value = true
  promptMsg.value = ''
  try {
    const resp = await fetch('/api/admin/prompt/write', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ token: adminToken.value, path: editingPrompt.value.path, content: promptContent.value }),
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

// ── Chunk 检索 ──
const chunkSearch = ref('')
const debouncedSearch = ref('')
let searchTimer = null
const onSearchInput = () => {
  clearTimeout(searchTimer)
  searchTimer = setTimeout(() => { debouncedSearch.value = chunkSearch.value.trim().toLowerCase() }, 250)
}
const clearSearch = () => {
  chunkSearch.value = ''
  debouncedSearch.value = ''
}

// 收集所有 chunk 为扁平列表（含上下文信息）
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

// ── Chunk 编辑 ──
const editingChunk = ref(null)  // { chunk_id, content: full text, category, file }
const chunkEditContent = ref('')
const savingChunk = ref(false)
const chunkEditMsg = ref('')

const startChunkEdit = async (chunk) => {
  // 从完整结构中找到 chunk 的完整内容
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

const cancelChunkEdit = () => {
  editingChunk.value = null
  chunkEditContent.value = ''
  chunkEditMsg.value = ''
}

const saveChunk = async () => {
  if (!editingChunk.value || savingChunk.value) return
  const content = chunkEditContent.value.trim()
  if (!content) { chunkEditMsg.value = '内容不能为空'; return }
  savingChunk.value = true
  chunkEditMsg.value = ''
  try {
    const resp = await fetch('/api/admin/chunk/update', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ token: adminToken.value, chunk_id: editingChunk.value.chunk_id, content }),
    })
    const data = await resp.json()
    if (!resp.ok) throw new Error(data.message || '更新失败')
    chunkEditMsg.value = '✅ 已保存'
    await refreshStructure()
    editingChunk.value = null
  } catch (e) {
    chunkEditMsg.value = '❌ ' + (e instanceof Error ? e.message : '更新失败')
  } finally {
    savingChunk.value = false
  }
}
</script>

<template>
  <div class="admin-page">
    <!-- ═══ 密码门 ═══ -->
    <section v-if="!authed" class="gate-card">
      <h1>🔐 管理页面</h1>
      <p class="gate-desc">请输入管理密码以查看和编辑知识库</p>
      <div class="password-row">
        <input v-model="password" type="password" class="password-input" placeholder="输入密码"
          :disabled="loading" @keydown="handleKeydown" />
        <button class="unlock-btn" :disabled="loading" @click="unlock">
          {{ loading ? '验证中...' : '确认' }}
        </button>
      </div>
      <p v-if="error" class="error-msg">{{ error }}</p>
    </section>

    <!-- ═══ 管理面板 ═══ -->
    <section v-else class="structure-panel">
      <header class="panel-header">
        <h1>📚 知识库内容结构</h1>
        <p class="panel-sub">集合：<strong>{{ structure.collection_name }}</strong></p>
      </header>

      <!-- 概览 -->
      <div class="overview-cards">
        <div class="overview-card"><span class="ov-number">{{ structure.chunk_count }}</span><span class="ov-label">总 Chunk</span></div>
        <div class="overview-card"><span class="ov-number">{{ structure.category_count }}</span><span class="ov-label">分类数</span></div>
        <div class="overview-card"><span class="ov-number">{{ structure.tracked_file_count }}</span><span class="ov-label">已追踪文件</span></div>
        <div class="overview-card overview-card--action" @click="refreshStructure">
          <span class="ov-number">🔄</span><span class="ov-label">刷新数据</span>
        </div>
      </div>

      <!-- ═══ 上传区域 ═══ -->
      <div class="upload-card">
        <h2>📤 上传文档</h2>
        <div class="upload-row">
          <input id="file-input" type="file" accept=".pdf,.txt" @change="e => uploadFile = e.target.files[0]"
            :disabled="uploading" />
          <div class="category-combo">
            <select v-model="uploadCategory" :disabled="uploading">
              <option v-for="c in allCategories()" :key="c" :value="c">{{ c }}</option>
              <option value="__custom__">＋ 新分类...</option>
            </select>
            <input v-if="uploadCategory === '__custom__'" v-model="uploadCategoryCustom"
              class="cat-input" placeholder="输入新分类名" :disabled="uploading" />
          </div>
          <button class="action-btn action-btn--upload" :disabled="!uploadFile || uploading" @click="handleUpload">
            {{ uploading ? '上传中...' : '上传' }}
          </button>
        </div>
        <p v-if="uploadMsg" class="action-msg" :class="{ 'msg-error': uploadMsg.startsWith('❌') }">{{ uploadMsg }}</p>
      </div>

      <!-- ═══ 提示词管理 ═══ -->
      <div class="prompts-card">
        <h2>📝 提示词管理 <button class="mini-btn" title="刷新" @click="loadPrompts">🔄</button></h2>
        <div class="prompts-list">
          <div v-for="p in prompts" :key="p.path" class="prompt-row" @click="startPromptEdit(p)">
            <span class="prompt-icon">📄</span>
            <span class="prompt-name">{{ p.name }}</span>
            <span class="prompt-file">{{ p.filename }}</span>
            <span v-if="p.exists" class="prompt-size">{{ (p.size / 1024).toFixed(1) }} KB</span>
            <span v-else class="prompt-missing">缺失</span>
          </div>
        </div>
        <p v-if="promptMsg && !editingPrompt" class="action-msg" :class="{ 'msg-error': promptMsg.startsWith('❌') }">{{ promptMsg }}</p>
      </div>

      <!-- ═══ Chunk 检索栏 ═══ -->
      <div class="search-bar">
        <span class="search-icon">🔍</span>
        <input v-model="chunkSearch" class="search-input" placeholder="输入关键词检索 chunk，例如：滤网、故障..."
          @input="onSearchInput" />
        <button v-if="chunkSearch" class="search-clear" @click="clearSearch">✕</button>
        <span v-if="debouncedSearch" class="search-count">找到 {{ searchResults.length }} 个匹配 chunk</span>
      </div>

      <!-- 检索结果（扁平列表） -->
      <div v-if="debouncedSearch && searchResults.length > 0" class="search-results-panel">
        <div v-for="r in searchResults" :key="r.chunk_id" class="search-result-item" @click="startChunkEdit(r)">
          <div class="sr-context">
            <span class="sr-cat">{{ r.category }}</span>
            <span class="sr-file">📄 {{ r.file }}</span>
            <span class="sr-id">{{ r.chunk_id.slice(-8) }}</span>
          </div>
          <p class="sr-content">{{ r.content_preview }}</p>
        </div>
      </div>
      <div v-if="debouncedSearch && searchResults.length === 0" class="empty-state">
        <p>未找到匹配的 chunk</p>
      </div>

      <!-- ═══ 分类列表（非检索模式显示） ═══ -->
      <div v-if="!debouncedSearch">
        <div v-if="structure.chunk_count === 0" class="empty-state">
          <p>知识库为空，请上传文档。</p>
        </div>

        <div v-for="cat in structure.categories" :key="cat.name" class="category-card">
          <div class="category-header" @click="toggleCategory(cat.name)">
            <span class="cat-toggle">{{ expandedCategories[cat.name] ? '▼' : '▶' }}</span>
            <span class="cat-name">{{ cat.name }}</span>
            <div class="cat-badges">
              <span class="badge badge--files">{{ cat.file_count }} 文件</span>
              <span class="badge badge--chunks">{{ cat.total_chunks }} chunks</span>
            </div>
          </div>

          <div v-if="expandedCategories[cat.name]" class="category-body">
            <div v-for="file in cat.files" :key="file.source" class="file-card">
              <div class="file-header">
                <span class="file-icon">📄</span>
                <span class="file-name">{{ file.name }}</span>
                <span class="file-stats">{{ file.chunk_count }} chunks · {{ file.total_chars }} 字</span>
                <button class="mini-btn mini-btn--cat" title="改分类" @click.stop="startCatChange(file.source, file.name, cat.name)">📁</button>
                <button class="mini-btn mini-btn--del" title="删除文件"
                  :disabled="deleting"
                  @click.stop="handleDelete(file.source, file.name)">🗑️</button>
              </div>

              <!-- Chunk 列表 -->
              <div class="chunk-list">
                <div v-for="chunk in file.chunks" :key="chunk.chunk_id" class="chunk-item"
                  :class="{ 'chunk-item--editing': editingChunk?.chunk_id === chunk.chunk_id }"
                  @click="startChunkEdit(chunk)">
                  <span class="chunk-id">{{ chunk.chunk_id.slice(-8) }}</span>
                  <span class="chunk-preview">{{ chunk.content_preview }}</span>
                  <span class="chunk-len">{{ chunk.char_count }}字</span>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </section>

    <!-- ═══ Chunk 编辑弹窗 ═══ -->
    <Teleport to="body">
      <div v-if="editingChunk" class="modal-overlay" @click.self="cancelChunkEdit">
        <div class="modal-card modal-card--wide">
          <h2>✏️ 编辑 Chunk</h2>
          <div class="chunk-edit-meta">
            <span class="meta-tag">分类：{{ editingChunk.category }}</span>
            <span class="meta-tag">文件：{{ editingChunk.file }}</span>
            <span class="meta-tag">ID：{{ editingChunk.chunk_id }}</span>
          </div>
          <textarea v-model="chunkEditContent" class="chunk-edit-textarea"
            :disabled="savingChunk" rows="10"></textarea>
          <p class="chunk-edit-chars">{{ chunkEditContent.length }} 字符</p>
          <p v-if="chunkEditMsg" class="action-msg" :class="{ 'msg-error': chunkEditMsg.startsWith('❌') }">{{ chunkEditMsg }}</p>
          <div class="modal-actions">
            <button class="action-btn action-btn--upload" :disabled="savingChunk" @click="saveChunk">
              {{ savingChunk ? '保存中...' : '保存修改' }}
            </button>
            <button class="action-btn action-btn--cancel" :disabled="savingChunk" @click="cancelChunkEdit">取消</button>
          </div>
        </div>
      </div>
    </Teleport>

    <!-- ═══ 改分类弹窗 ═══ -->
    <Teleport to="body">
      <div v-if="catTarget" class="modal-overlay" @click.self="cancelCatChange">
        <div class="modal-card">
          <h2>📁 更改分类</h2>
          <p class="modal-body">
            文档 <strong>{{ catFileName }}</strong>
          </p>
          <p class="modal-sub">当前分类：<span class="old-cat-tag">{{ catOldCategory }}</span></p>

          <div class="cat-modal-row">
            <label>新分类：</label>
            <select v-model="catNewCategory" class="cat-modal-select" :disabled="changingCat">
              <option v-for="c in allCategories()" :key="c" :value="c">{{ c }}</option>
              <option value="__custom__">＋ 新分类...</option>
            </select>
            <input
              v-if="catNewCategory === '__custom__'"
              v-model="catNewCustom"
              class="cat-input"
              placeholder="输入新分类名"
              :disabled="changingCat"
            />
          </div>

          <p v-if="catError" class="modal-error">{{ catError }}</p>
          <div class="modal-actions">
            <button class="action-btn action-btn--upload" :disabled="changingCat" @click="confirmCatChange">
              {{ changingCat ? '更改中...' : '确认更改' }}
            </button>
            <button class="action-btn action-btn--cancel" :disabled="changingCat" @click="cancelCatChange">取消</button>
          </div>
        </div>
      </div>
    </Teleport>

    <!-- ═══ 提示词编辑弹窗 ═══ -->
    <Teleport to="body">
      <div v-if="editingPrompt" class="modal-overlay" @click.self="cancelPromptEdit">
        <div class="modal-card modal-card--wide">
          <h2>📝 编辑提示词</h2>
          <p class="modal-sub">{{ editingPrompt.name }}（{{ editingPrompt.filename }}）</p>
          <textarea v-model="promptContent" class="prompt-edit-textarea"
            :disabled="savingPrompt" rows="18"></textarea>
          <p class="chunk-edit-chars">{{ promptContent.length }} 字符</p>
          <p v-if="promptMsg" class="action-msg" :class="{ 'msg-error': promptMsg.startsWith('❌') }">{{ promptMsg }}</p>
          <div class="modal-actions">
            <button class="action-btn action-btn--upload" :disabled="savingPrompt" @click="savePrompt">
              {{ savingPrompt ? '保存中...' : '保存修改' }}
            </button>
            <button class="action-btn action-btn--cancel" :disabled="savingPrompt" @click="cancelPromptEdit">取消</button>
          </div>
        </div>
      </div>
    </Teleport>

    <!-- ═══ 删除确认弹窗 ═══ -->
    <Teleport to="body">
      <div v-if="deleteTarget" class="modal-overlay" @click.self="cancelDelete">
        <div class="modal-card">
          <h2>⚠️ 确认删除</h2>
          <p class="modal-body">
            确定要删除文档 <strong>{{ deleteFileName }}</strong> 吗？
          </p>
          <p class="modal-warn">此操作将从磁盘和向量库中永久移除该文件，不可恢复。</p>
          <p v-if="deleteError" class="modal-error">{{ deleteError }}</p>
          <div class="modal-actions">
            <button class="action-btn action-btn--del" :disabled="deleting" @click="confirmDelete">
              {{ deleting ? '删除中...' : '确认删除' }}
            </button>
            <button class="action-btn action-btn--cancel" :disabled="deleting" @click="cancelDelete">取消</button>
          </div>
        </div>
      </div>
    </Teleport>
  </div>
</template>

<style scoped>
.admin-page { min-height: 100vh; display: flex; align-items: flex-start; justify-content: center; padding: 48px 24px; }

/* ── 密码门 ── */
.gate-card { width: min(480px, 100%); margin-top: 80px; padding: 48px 36px; border: 1px solid rgba(148, 163, 184, 0.24); border-radius: 24px; background: rgba(255, 255, 255, 0.92); box-shadow: 0 24px 60px rgba(15, 23, 42, 0.1); text-align: center; }
.gate-card h1 { font-size: 1.8rem; font-weight: 700; color: #0f172a; margin-bottom: 8px; }
.gate-desc { color: #64748b; font-size: 0.92rem; margin-bottom: 28px; }
.password-row { display: flex; gap: 12px; }
.password-input { flex: 1; padding: 14px 16px; border: 1px solid rgba(148, 163, 184, 0.4); border-radius: 14px; font: inherit; font-size: 1rem; outline: none; transition: border-color 0.2s, box-shadow 0.2s; }
.password-input:focus { border-color: rgba(37, 99, 235, 0.5); box-shadow: 0 0 0 3px rgba(37, 99, 235, 0.1); }
.unlock-btn { min-width: 88px; padding: 12px 22px; border: none; border-radius: 14px; background: linear-gradient(135deg, #2563eb, #1d4ed8); color: #fff; font: inherit; font-weight: 700; cursor: pointer; transition: transform 0.15s, box-shadow 0.15s; }
.unlock-btn:hover:enabled { transform: translateY(-1px); box-shadow: 0 8px 20px rgba(37, 99, 235, 0.3); }
.unlock-btn:disabled { opacity: 0.6; cursor: not-allowed; }
.error-msg { margin-top: 14px; color: #dc2626; font-size: 0.9rem; }

/* ── 管理面板 ── */
.structure-panel { width: min(960px, 100%); }
.panel-header { margin-bottom: 24px; }
.panel-header h1 { font-size: 1.8rem; font-weight: 700; color: #0f172a; }
.panel-sub { margin-top: 4px; color: #64748b; font-size: 0.9rem; }
.overview-cards { display: flex; gap: 12px; margin-bottom: 24px; flex-wrap: wrap; }
.overview-card { flex: 1; min-width: 110px; padding: 18px 16px; border: 1px solid rgba(148, 163, 184, 0.16); border-radius: 16px; background: #fff; box-shadow: 0 4px 12px rgba(15, 23, 42, 0.04); text-align: center; }
.overview-card--action { cursor: pointer; transition: background 0.15s; }
.overview-card--action:hover { background: #f8fafc; }
.ov-number { display: block; font-size: 1.8rem; font-weight: 800; color: #2563eb; }
.ov-label { font-size: 0.78rem; color: #64748b; margin-top: 2px; }
.empty-state { text-align: center; padding: 60px 20px; color: #94a3b8; }

/* ── 上传 ── */
.upload-card { margin-bottom: 20px; padding: 20px; border: 1px solid rgba(148, 163, 184, 0.2); border-radius: 16px; background: #ffffff; box-shadow: 0 4px 12px rgba(15, 23, 42, 0.03); }
.upload-card h2 { font-size: 1.05rem; font-weight: 700; color: #0f172a; margin-bottom: 12px; }
.upload-row { display: flex; gap: 10px; align-items: center; flex-wrap: wrap; }
.upload-row input[type="file"] { font-size: 0.88rem; }
.category-combo { display: flex; gap: 8px; align-items: center; }
.category-combo select { padding: 8px 12px; border: 1px solid rgba(148, 163, 184, 0.4); border-radius: 10px; font: inherit; font-size: 0.86rem; outline: none; }
.cat-input { padding: 8px 12px; border: 1px solid rgba(148, 163, 184, 0.4); border-radius: 10px; font: inherit; font-size: 0.86rem; width: 130px; outline: none; }

/* ── 提示词管理 ── */
.prompts-card { margin-bottom: 20px; padding: 20px; border: 1px solid rgba(148, 163, 184, 0.2); border-radius: 16px; background: #ffffff; box-shadow: 0 4px 12px rgba(15, 23, 42, 0.03); }
.prompts-card h2 { font-size: 1.05rem; font-weight: 700; color: #0f172a; margin-bottom: 12px; display: flex; align-items: center; gap: 8px; }
.prompts-list { display: flex; flex-direction: column; gap: 6px; }
.prompt-row { display: flex; align-items: center; gap: 10px; padding: 10px 14px; border-radius: 10px; background: #f8fafc; border: 1px solid rgba(148, 163, 184, 0.08); cursor: pointer; transition: border-color 0.12s, background 0.12s; }
.prompt-row:hover { border-color: #93c5fd; background: #eff6ff; }
.prompt-icon { font-size: 0.9rem; }
.prompt-name { font-weight: 600; color: #1e293b; font-size: 0.88rem; }
.prompt-file { font-family: monospace; font-size: 0.76rem; color: #64748b; }
.prompt-size { font-size: 0.74rem; color: #94a3b8; margin-left: auto; }
.prompt-missing { font-size: 0.74rem; color: #dc2626; margin-left: auto; font-weight: 600; }
.prompt-edit-textarea { width: 100%; padding: 14px; border: 1px solid rgba(148, 163, 184, 0.3); border-radius: 12px; font: inherit; font-size: 0.86rem; line-height: 1.7; resize: vertical; outline: none; color: #0f172a; font-family: 'Consolas', 'Courier New', monospace; }
.prompt-edit-textarea:focus { border-color: rgba(37, 99, 235, 0.5); box-shadow: 0 0 0 3px rgba(37, 99, 235, 0.08); }

/* ── 检索栏 ── */
.search-bar { display: flex; align-items: center; gap: 10px; margin-bottom: 20px; padding: 12px 16px; border: 1px solid rgba(148, 163, 184, 0.2); border-radius: 14px; background: #fff; }
.search-icon { font-size: 1rem; }
.search-input { flex: 1; border: none; outline: none; font: inherit; font-size: 0.92rem; color: #0f172a; }
.search-input::placeholder { color: #94a3b8; }
.search-clear { border: none; background: #e2e8f0; color: #64748b; border-radius: 50%; width: 24px; height: 24px; font-size: 0.8rem; cursor: pointer; display: flex; align-items: center; justify-content: center; }
.search-clear:hover { background: #cbd5e1; }
.search-count { font-size: 0.78rem; color: #2563eb; font-weight: 600; white-space: nowrap; }

/* ── 检索结果 ── */
.search-results-panel { display: flex; flex-direction: column; gap: 8px; margin-bottom: 24px; }
.search-result-item { padding: 14px; border: 1px solid rgba(148, 163, 184, 0.14); border-radius: 12px; background: #fff; cursor: pointer; transition: border-color 0.15s, box-shadow 0.15s; }
.search-result-item:hover { border-color: #93c5fd; box-shadow: 0 2px 8px rgba(37, 99, 235, 0.1); }
.sr-context { display: flex; gap: 10px; align-items: center; margin-bottom: 6px; }
.sr-cat { font-size: 0.7rem; padding: 2px 8px; border-radius: 999px; background: #eff6ff; color: #2563eb; font-weight: 600; }
.sr-file { font-size: 0.76rem; color: #64748b; }
.sr-id { font-family: monospace; font-size: 0.68rem; color: #94a3b8; margin-left: auto; }
.sr-content { font-size: 0.84rem; color: #334155; line-height: 1.5; white-space: pre-wrap; word-break: break-word; }

/* ── 按钮 ── */
.action-btn { padding: 8px 18px; border: none; border-radius: 10px; font: inherit; font-size: 0.84rem; font-weight: 600; cursor: pointer; transition: transform 0.12s, background 0.15s; }
.action-btn:hover:enabled { transform: translateY(-1px); }
.action-btn:disabled { opacity: 0.5; cursor: not-allowed; }
.action-btn--upload { background: linear-gradient(135deg, #2563eb, #1d4ed8); color: #fff; }
.action-btn--del { background: #dc2626; color: #fff; }
.action-btn--cancel { background: #f1f5f9; color: #475569; }
.mini-btn { border: none; background: transparent; cursor: pointer; font-size: 0.95rem; padding: 2px 6px; border-radius: 6px; transition: background 0.12s; }
.mini-btn:hover { background: #f1f5f9; }
.mini-btn--del:hover { background: #fee2e2; }
.mini-btn:disabled { opacity: 0.4; cursor: not-allowed; }
.action-msg { margin-top: 10px; font-size: 0.86rem; color: #15803d; }
.msg-error { color: #dc2626; }

/* ── 弹窗 ── */
.modal-overlay { position: fixed; inset: 0; z-index: 1000; display: flex; align-items: center; justify-content: center; background: rgba(15, 23, 42, 0.45); backdrop-filter: blur(4px); }
.modal-card { width: min(440px, 92vw); padding: 32px; border-radius: 20px; background: #ffffff; box-shadow: 0 24px 60px rgba(15, 23, 42, 0.2); text-align: center; }
.modal-card--wide { width: min(680px, 94vw); text-align: left; }
.modal-card h2 { font-size: 1.3rem; font-weight: 700; color: #0f172a; margin-bottom: 16px; }
.modal-body { font-size: 1rem; color: #334155; margin-bottom: 8px; }
.modal-body strong { color: #0f172a; }
.modal-warn { font-size: 0.84rem; color: #dc2626; margin-bottom: 20px; }
.modal-error { margin-bottom: 12px; padding: 8px 12px; border-radius: 8px; background: #fef2f2; color: #dc2626; font-size: 0.84rem; }
.modal-actions { display: flex; gap: 12px; justify-content: center; }

.modal-sub { font-size: 0.9rem; color: #64748b; margin-bottom: 16px; }
.old-cat-tag { display: inline-block; padding: 3px 10px; border-radius: 999px; background: #f1f5f9; color: #475569; font-weight: 600; font-size: 0.82rem; }
.cat-modal-row { display: flex; align-items: center; gap: 10px; margin-bottom: 20px; font-size: 0.9rem; }
.cat-modal-row label { font-weight: 600; color: #334155; white-space: nowrap; }
.cat-modal-select { padding: 8px 14px; border: 1px solid rgba(148, 163, 184, 0.4); border-radius: 10px; font: inherit; font-size: 0.88rem; outline: none; background: #fff; }

/* ── Chunk 编辑弹窗 ── */
.chunk-edit-meta { display: flex; gap: 10px; flex-wrap: wrap; margin-bottom: 16px; }
.meta-tag { font-size: 0.76rem; padding: 3px 10px; border-radius: 999px; background: #f1f5f9; color: #475569; }
.chunk-edit-textarea { width: 100%; padding: 14px; border: 1px solid rgba(148, 163, 184, 0.3); border-radius: 12px; font: inherit; font-size: 0.9rem; line-height: 1.7; resize: vertical; outline: none; color: #0f172a; }
.chunk-edit-textarea:focus { border-color: rgba(37, 99, 235, 0.5); box-shadow: 0 0 0 3px rgba(37, 99, 235, 0.08); }
.chunk-edit-chars { margin-top: 8px; font-size: 0.78rem; color: #94a3b8; }

/* ── 分类卡片 ── */
.category-card { margin-bottom: 14px; border: 1px solid rgba(148, 163, 184, 0.16); border-radius: 16px; background: #fff; box-shadow: 0 4px 12px rgba(15, 23, 42, 0.03); overflow: hidden; }
.category-header { display: flex; align-items: center; gap: 12px; padding: 14px 20px; cursor: pointer; user-select: none; transition: background 0.15s; }
.category-header:hover { background: #f8fafc; }
.cat-toggle { font-size: 0.7rem; color: #94a3b8; }
.cat-name { font-size: 1.05rem; font-weight: 700; color: #0f172a; flex: 1; }
.cat-badges { display: flex; gap: 8px; }
.badge { padding: 4px 12px; border-radius: 999px; font-size: 0.72rem; font-weight: 600; }
.badge--files { background: #eff6ff; color: #2563eb; }
.badge--chunks { background: #dcfce7; color: #15803d; }
.category-body { padding: 0 20px 14px; }

/* ── 文件卡片 ── */
.file-card { margin-top: 12px; padding: 14px; border: 1px solid rgba(148, 163, 184, 0.12); border-radius: 12px; background: #f8fafc; }
.file-header { display: flex; align-items: center; gap: 8px; margin-bottom: 8px; }
.file-icon { font-size: 1rem; }
.file-name { font-weight: 600; color: #1e293b; flex: 1; }
.file-stats { font-size: 0.76rem; color: #94a3b8; margin-right: 8px; }

.mini-btn--cat:hover { background: #e0f2fe; }

/* ── Chunk 列表 ── */
.chunk-list { display: flex; flex-direction: column; gap: 5px; }
.chunk-item { display: flex; align-items: flex-start; gap: 10px; padding: 7px 12px; border-radius: 8px; background: #fff; font-size: 0.82rem; border: 1px solid rgba(148, 163, 184, 0.08); cursor: pointer; transition: border-color 0.15s, background 0.15s; }
.chunk-item:hover { border-color: #93c5fd; background: #f8faff; }
.chunk-item--editing { border-color: #2563eb; background: #eff6ff; }
.chunk-id { font-family: monospace; font-size: 0.7rem; color: #94a3b8; flex-shrink: 0; }
.chunk-preview { flex: 1; color: #334155; line-height: 1.5; word-break: break-word; }
.chunk-len { flex-shrink: 0; font-size: 0.7rem; color: #94a3b8; }

@media (max-width: 768px) {
  .admin-page { padding: 24px 12px; }
  .gate-card { padding: 32px 20px; margin-top: 32px; }
  .password-row { flex-direction: column; }
  .overview-cards { flex-direction: column; }
  .upload-row { flex-direction: column; align-items: stretch; }
  .category-combo { flex-direction: column; }
  .search-bar { flex-wrap: wrap; }
  .chunk-edit-meta { flex-direction: column; gap: 4px; }
}
</style>
