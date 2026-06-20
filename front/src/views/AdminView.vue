<script setup>
import { onMounted, ref } from 'vue'
import { useAdminAuth } from '@/composables/useAdminAuth'
import { useKnowledgeBase } from '@/composables/useKnowledgeBase'
import { useChunkEditor } from '@/composables/useChunkEditor'
import { usePromptEditor } from '@/composables/usePromptEditor'

const bannerDismissed = ref(false)
const allModesDisabled = ref(false)

const checkChatRedirect = () => {
  if (localStorage.getItem('all_modes_disabled') === '1') {
    allModesDisabled.value = true
    localStorage.removeItem('all_modes_disabled')
  }
}

const auth = useAdminAuth()
const kb = useKnowledgeBase(auth.token)
const chunk = useChunkEditor(auth.token, kb.structure, kb.loadStructure)
const prompt = usePromptEditor(auth.token)

// ── 模式管理 ──
const allModes = ref([])
const expandedMode = ref('')
const modePromptContent = ref('')
const loadingPrompt = ref(false)
const savingModeField = ref(false)
const BUILTIN_IDS = ['chat', 'chat_only', 'search']

const loadAllModes = async () => {
  try {
    const [modesResp, configResp] = await Promise.all([
      fetch('/api/modes'),
      fetch('/api/config'),
    ])
    const modesData = await modesResp.json()
    const configData = await configResp.json()
    if (modesData.success) {
      const config = configData.success ? (configData.data.config || {}) : {}
      allModes.value = modesData.data.modes.map(m => ({
        ...m,
        greeting: m.greeting || config.greeting?.[m.id] || '',
        subtitle: m.subtitle || config.subtitle?.[m.id] || '',
        placeholder: m.placeholder || config.placeholder?.[m.id] || '',
        title: m.title || config.title?.[m.id] || m.title,
        isBuiltin: BUILTIN_IDS.includes(m.id),
      }))
      checkChatRedirect()
    }
  } catch { /* */ }
}

const toggleModeExpand = async (mode) => {
  if (expandedMode.value === mode.id) { expandedMode.value = ''; return }
  expandedMode.value = mode.id
  loadingPrompt.value = true
  modePromptContent.value = ''
  try {
    let path = mode.prompt_path || ''
    if (mode.isBuiltin) {
      const builtinPaths = { chat: 'main_prompt', chat_only: 'chat_prompt', search: '' }
      const key = builtinPaths[mode.id]
      if (!key) { modePromptContent.value = '（无提示词）'; return }
      const resp = await fetch('/api/admin/prompts', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ token: auth.token.value }),
      })
      if (!resp.ok) throw new Error()
      const d = await resp.json()
      const p = d.data?.prompts?.find(p => p.path.includes(key))
      if (p) path = p.path
    }
    if (!path) { modePromptContent.value = '（无提示词文件）'; return }
    const resp = await fetch('/api/admin/prompt/read', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ token: auth.token.value, path }),
    })
    if (!resp.ok) throw new Error()
    const d = await resp.json()
    modePromptContent.value = d.data?.content || '（空）'
  } catch { modePromptContent.value = '（无法加载）' }
  finally { loadingPrompt.value = false }
}

const saveModeField = async (modeId, field, value) => {
  if (savingModeField.value) return
  savingModeField.value = true
  try {
    await fetch('/api/admin/config', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ token: auth.token.value, scope: field, mode: modeId, content: value }),
    })
    modeMsg.value = '✅ 已保存'
  } catch { modeMsg.value = '❌ 保存失败' }
  savingModeField.value = false
}

// ── 新建模式 ──
const newModeTitle = ref('')
const newModePrompt = ref(null)
const newModeDataFiles = ref([])
const creatingMode = ref(false)
const creatingMsg = ref('')
const modeMsg = ref('')
const deletingMode = ref('')
const showModeMgr = ref(false)

const wrappedCreateMode = async () => {
  if (!newModeTitle.value.trim()) { modeMsg.value = '❌ 请输入标题'; return }
  creatingMsg.value = '正在创建模式，请稍候...'
  const form = new FormData()
  form.append('token', auth.token.value)
  form.append('title', newModeTitle.value.trim())
  if (newModePrompt.value) form.append('prompt_file', newModePrompt.value)
  for (const f of newModeDataFiles.value) form.append('data_files', f)
  try {
    const resp = await fetch('/api/admin/mode/create', { method: 'POST', body: form })
    const data = await resp.json()
    if (!resp.ok) throw new Error(data.message)
    modeMsg.value = '✅ 模式已创建: ' + data.data.id
    newModeTitle.value = ''
    newModePrompt.value = null
    newModeDataFiles.value = []
    document.getElementById('mode-prompt-input').value = ''
    document.getElementById('mode-data-input').value = ''
    await loadAllModes()
  } catch (e) { modeMsg.value = '❌ ' + (e.message || '创建失败') }
  creatingMsg.value = ''
}

const toggleMode = async (modeId) => {
  try {
    const resp = await fetch(`/api/admin/mode/toggle/${modeId}?token=${auth.token.value}`, { method: 'POST' })
    const data = await resp.json()
    if (data.success) await loadAllModes()
  } catch { /* */ }
}

const deleteMode = async (modeId) => {
  if (deletingMode.value) return
  deletingMode.value = modeId
  try {
    const resp = await fetch(`/api/admin/mode/${modeId}?token=${auth.token.value}`, { method: 'DELETE' })
    const data = await resp.json()
    if (!resp.ok) throw new Error(data.message)
    modeMsg.value = '✅ 已删除'
    await loadAllModes()
  } catch (e) { modeMsg.value = '❌ ' + (e.message || '删除失败') }
  deletingMode.value = ''
}

// ── 登录 ──
const unlock = async () => {
  await auth.login()
  if (auth.authed.value) {
    await kb.loadStructure()
    await prompt.loadPrompts()
    await loadAllModes()
  }
}
const handleKeydown = (e) => { if (e.key === 'Enter') unlock() }

onMounted(() => { loadAllModes() })
</script>

<template>
  <div class="admin-page">
    <Teleport to="body">
      <div v-if="allModesDisabled && !bannerDismissed" class="mode-warn-overlay">
        <div class="mode-warn-modal">
          <h2>⚠️ 所有模式已禁用</h2>
          <p>聊天页面暂不可用，请到「模式管理」启用至少一个模式后再访问。</p>
          <div class="modal-actions"><button class="action-btn action-btn--upload" @click="bannerDismissed = true">知道了</button></div>
        </div>
      </div>
    </Teleport>

    <section v-if="!auth.authed.value" class="gate-card">
      <h1>🔐 管理页面</h1>
      <p class="gate-desc">请输入管理密码</p>
      <div class="password-row">
        <input v-model="auth.password.value" type="password" class="password-input" placeholder="输入密码"
          :disabled="auth.loading.value" @keydown="handleKeydown" />
        <button class="unlock-btn" :disabled="auth.loading.value" @click="unlock">
          {{ auth.loading.value ? '验证中...' : '确认' }}
        </button>
      </div>
      <p v-if="auth.error.value" class="error-msg">{{ auth.error.value }}</p>
    </section>

    <section v-else class="structure-panel">
      <header class="panel-header">
        <h1>📚 知识库管理</h1>
      </header>

      <div class="header-actions-row">
        <button class="action-btn mode-mgr-btn" @click="showModeMgr = true">⚙️ 模式管理</button>
      </div>

      <div class="overview-cards">
        <div class="overview-card"><span class="ov-number">{{ kb.structure.value?.chunk_count ?? '-' }}</span><span class="ov-label">总 Chunk</span></div>
        <div class="overview-card"><span class="ov-number">{{ kb.structure.value?.category_count ?? '-' }}</span><span class="ov-label">分类</span></div>
        <div class="overview-card"><span class="ov-number">{{ kb.structure.value?.tracked_file_count ?? '-' }}</span><span class="ov-label">文件</span></div>
        <div class="overview-card overview-card--action" @click="kb.loadStructure()"><span class="ov-number">🔄</span><span class="ov-label">刷新</span></div>
      </div>

      <!-- ═══ 上传 ═══ -->
      <div class="section-card">
        <h2>📤 上传文档</h2>
        <div class="upload-row">
          <input id="file-input" type="file" accept=".pdf,.txt" @change="e => kb.uploadFile = e.target.files[0]" :disabled="kb.uploading.value" />
          <div class="category-combo">
            <select v-model="kb.uploadCategory.value" :disabled="kb.uploading.value">
              <option v-for="c in kb.allCategories()" :key="c" :value="c">{{ c }}</option>
              <option value="__custom__">＋ 新分类...</option>
            </select>
            <input v-if="kb.uploadCategory.value === '__custom__'" v-model="kb.uploadCategoryCustom.value" class="cat-input" placeholder="新分类名" :disabled="kb.uploading.value" />
          </div>
          <button class="action-btn action-btn--upload" :disabled="!kb.uploadFile || kb.uploading.value" @click="kb.doUpload()">{{ kb.uploading.value ? '上传中' : '上传' }}</button>
        </div>
        <p v-if="kb.uploadMsg.value" class="action-msg" :class="{ 'msg-error': kb.uploadMsg.value.startsWith('❌') }">{{ kb.uploadMsg.value }}</p>
      </div>

      <!-- ═══ 提示词管理 ═══ -->
      <div class="section-card">
        <h2>📝 提示词管理 <button class="mini-btn" @click="prompt.loadPrompts()">🔄</button></h2>
        <div class="prompts-list">
          <div v-for="p in prompt.prompts.value" :key="p.path" class="prompt-row" @click="prompt.startPromptEdit(p)">
            <span class="prompt-icon">📄</span><span class="prompt-name">{{ p.name }}</span>
            <span class="prompt-file">{{ p.filename }}</span>
            <span v-if="p.exists" class="prompt-size">{{ (p.size / 1024).toFixed(1) }} KB</span>
            <span v-else class="prompt-missing">缺失</span>
          </div>
        </div>
        <p v-if="prompt.promptMsg.value && !prompt.editingPrompt.value" class="action-msg" :class="{ 'msg-error': prompt.promptMsg.value.startsWith('❌') }">{{ prompt.promptMsg.value }}</p>
      </div>

      <!-- ═══ 模式管理 ═══ -->
      <div class="section-card">
        <h2>⚙️ 模式管理</h2>
        <div v-for="m in allModes" :key="m.id" class="mode-card">
          <div class="mode-card-header" @click="toggleModeExpand(m)">
            <span class="mode-toggle">{{ expandedMode === m.id ? '▼' : '▶' }}</span>
            <span class="mode-icon">{{ m.isBuiltin ? (m.id === 'chat' ? '🤖' : m.id === 'chat_only' ? '💬' : '🔍') : '📌' }}</span>
            <span class="mode-name">{{ m.title }}</span>
            <span class="mode-badge" :class="m.isBuiltin ? 'badge--builtin' : 'badge--custom'">{{ m.isBuiltin ? '内置' : '自定义' }}</span>
            <span class="mode-badge" :class="m.enabled ? 'badge--on' : 'badge--off'">{{ m.enabled ? '启用' : '禁用' }}</span>
            <span class="mode-id">{{ m.id }}</span>
            <button v-if="!m.isBuiltin" class="mini-btn mini-btn--del" :disabled="deletingMode === m.id" @click.stop="deleteMode(m.id)">🗑️</button>
          </div>
          <div v-if="expandedMode === m.id" class="mode-card-body">
            <div class="mode-field">
              <label>问候语</label>
              <textarea v-model="m.greeting" rows="2" class="mode-field-input" />
              <button class="action-btn action-btn--upload" @click="saveModeField(m.id, 'greeting', m.greeting)">保存</button>
            </div>
            <div class="mode-field">
              <label>副标题</label>
              <input v-model="m.subtitle" class="mode-field-input" />
              <button class="action-btn action-btn--upload" @click="saveModeField(m.id, 'subtitle', m.subtitle)">保存</button>
            </div>
            <div class="mode-field">
              <label>输入提示</label>
              <input v-model="m.placeholder" class="mode-field-input" />
              <button class="action-btn action-btn--upload" @click="saveModeField(m.id, 'placeholder', m.placeholder)">保存</button>
            </div>
            <div v-if="m.id !== 'search'" class="mode-field mode-field--prompt">
              <label>提示词</label>
              <span class="mode-prompt-file">{{ m.isBuiltin ? '内置' : (m.prompt_name || 'LLM 生成') }}</span>
              <textarea v-if="!loadingPrompt" v-model="modePromptContent" rows="8" class="mode-field-input mode-prompt-text" />
              <p v-else class="mode-loading">加载中...</p>
            </div>
            <div v-if="m.data_files && m.data_files.length" class="mode-field">
              <label>数据文件</label>
              <span class="mode-data-list">{{ m.data_files.join('、') }}</span>
            </div>
          </div>
        </div>
        <p v-if="modeMsg" class="action-msg" :class="{ 'msg-error': modeMsg.startsWith('❌') }">{{ modeMsg }}</p>
      </div>

      <!-- ═══ 新建模式 ═══ -->
      <div class="section-card mode-create-card">
        <h2>➕ 新建模式</h2>
        <div class="mode-create-row">
          <input v-model="newModeTitle" class="mode-title-input" placeholder="模式标题（必填）" :disabled="creatingMode" />
          <div class="mode-file-group"><label class="file-label">提示词(可选)：</label><input id="mode-prompt-input" type="file" accept=".txt" @change="e => newModePrompt = e.target.files[0]" :disabled="creatingMode" /></div>
          <div class="mode-file-group"><label class="file-label">数据文件：</label><input id="mode-data-input" type="file" accept=".pdf,.txt" multiple @change="e => newModeDataFiles = [...e.target.files]" :disabled="creatingMode" /></div>
          <button class="action-btn action-btn--upload" :disabled="creatingMode" @click="wrappedCreateMode">{{ creatingMode ? '创建中' : '创建' }}</button>
        </div>
        <p class="mode-hint">只填标题即可，提示词和数据文件可选。所有文本由 LLM 自动生成。</p>
      </div>

      <!-- ═══ 分类列表 ═══ -->
      <div>
        <div v-if="!kb.structure.value || kb.structure.value.chunk_count === 0" class="empty-state"><p>知识库为空，请上传文档。</p></div>
        <div v-for="cat in (kb.structure.value?.categories || [])" :key="cat.name" class="category-card">
          <div class="category-header" @click="kb.toggleCategory(cat.name)">
            <span class="cat-toggle">{{ kb.expandedCategories.value[cat.name] ? '▼' : '▶' }}</span>
            <span class="cat-name">{{ cat.name }}</span>
            <div class="cat-badges"><span class="badge badge--files">{{ cat.file_count }} 文件</span><span class="badge badge--chunks">{{ cat.total_chunks }} chunks</span></div>
          </div>
          <div v-if="kb.expandedCategories.value[cat.name]" class="category-body">
            <div v-for="file in cat.files" :key="file.source" class="file-card">
              <div class="file-header">
                <span class="file-icon">📄</span><span class="file-name">{{ file.name }}</span>
                <span class="file-stats">{{ file.chunk_count }} chunks · {{ file.total_chars }} 字</span>
                <button class="mini-btn mini-btn--cat" title="改分类" @click.stop="kb.showCatModal(file.source, file.name, cat.name)">📁</button>
                <button class="mini-btn mini-btn--del" title="删除" :disabled="kb.deleting.value" @click.stop="kb.showDeleteModal(file.source, file.name)">🗑️</button>
              </div>
              <div class="chunk-list">
                <div v-for="c in file.chunks" :key="c.chunk_id" class="chunk-item" :class="{ 'chunk-item--editing': chunk.editingChunk.value?.chunk_id === c.chunk_id }" @click="chunk.startChunkEdit(c)">
                  <span class="chunk-id">{{ c.chunk_id.slice(-8) }}</span><span class="chunk-preview">{{ c.content_preview }}</span><span class="chunk-len">{{ c.char_count }}字</span>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </section>

    <!-- ═══ 弹窗 ═══ -->
    <Teleport to="body">
      <div v-if="showModeMgr" class="modal-overlay" @click.self="showModeMgr = false">
        <div class="modal-card modal-card--wide">
          <h2>⚙️ 模式管理</h2>
          <div class="mode-mgr-list">
            <div v-for="m in allModes" :key="m.id" class="mode-mgr-item">
              <span class="mode-mgr-icon">{{ m.isBuiltin ? '🔒' : '📌' }}</span>
              <span class="mode-mgr-name">{{ m.title }}</span>
              <span class="mode-mgr-id">{{ m.id }}</span>
              <span v-if="m.isBuiltin" class="mode-mgr-builtin">内置</span>
              <button class="action-btn" :class="m.enabled ? 'action-btn--del' : 'action-btn--upload'" @click="toggleMode(m.id)">{{ m.enabled ? '禁用' : '启用' }}</button>
            </div>
          </div>
          <div class="modal-actions" style="margin-top:16px">
            <button class="action-btn action-btn--cancel" @click="showModeMgr = false">关闭</button>
          </div>
        </div>
      </div>
    </Teleport>
    <Teleport to="body">
      <div v-if="creatingMsg" class="modal-overlay"><div class="modal-card"><h2>⏳ 创建中</h2><p class="modal-body">{{ creatingMsg }}</p></div></div>
    </Teleport>
    <Teleport to="body">
      <div v-if="chunk.editingChunk.value" class="modal-overlay" @click.self="chunk.cancelChunkEdit()">
        <div class="modal-card modal-card--wide">
          <h2>✏️ 编辑 Chunk</h2>
          <div class="chunk-edit-meta">
            <span class="meta-tag">分类：{{ chunk.editingChunk.value.category }}</span>
            <span class="meta-tag">文件：{{ chunk.editingChunk.value.file }}</span>
            <span class="meta-tag">ID：{{ chunk.editingChunk.value.chunk_id }}</span>
          </div>
          <textarea v-model="chunk.chunkEditContent.value" class="chunk-edit-textarea" :disabled="chunk.savingChunk.value" rows="10"></textarea>
          <p class="chunk-edit-chars">{{ chunk.chunkEditContent.value.length }} 字符</p>
          <p v-if="chunk.chunkEditMsg.value" class="action-msg" :class="{ 'msg-error': chunk.chunkEditMsg.value.startsWith('❌') }">{{ chunk.chunkEditMsg.value }}</p>
          <div class="modal-actions">
            <button class="action-btn action-btn--upload" :disabled="chunk.savingChunk.value" @click="chunk.saveChunk()">{{ chunk.savingChunk.value ? '保存中' : '保存' }}</button>
            <button class="action-btn action-btn--cancel" :disabled="chunk.savingChunk.value" @click="chunk.cancelChunkEdit()">取消</button>
          </div>
        </div>
      </div>
    </Teleport>
    <Teleport to="body">
      <div v-if="prompt.editingPrompt.value" class="modal-overlay" @click.self="prompt.cancelPromptEdit()">
        <div class="modal-card modal-card--wide">
          <h2>📝 编辑提示词</h2>
          <p class="modal-sub">{{ prompt.editingPrompt.value.name }}（{{ prompt.editingPrompt.value.filename }}）</p>
          <textarea v-model="prompt.promptContent.value" class="prompt-edit-textarea" :disabled="prompt.savingPrompt.value" rows="18"></textarea>
          <p class="chunk-edit-chars">{{ prompt.promptContent.value.length }} 字符</p>
          <p v-if="prompt.promptMsg.value" class="action-msg" :class="{ 'msg-error': prompt.promptMsg.value.startsWith('❌') }">{{ prompt.promptMsg.value }}</p>
          <div class="modal-actions">
            <button class="action-btn action-btn--upload" :disabled="prompt.savingPrompt.value" @click="prompt.savePrompt()">{{ prompt.savingPrompt.value ? '保存中' : '保存' }}</button>
            <button class="action-btn action-btn--cancel" :disabled="prompt.savingPrompt.value" @click="prompt.cancelPromptEdit()">取消</button>
          </div>
        </div>
      </div>
    </Teleport>
    <Teleport to="body">
      <div v-if="kb.catTarget.value" class="modal-overlay" @click.self="kb.cancelCatChange()">
        <div class="modal-card">
          <h2>📁 更改分类</h2>
          <p class="modal-body">文档 <strong>{{ kb.catFileName.value }}</strong></p>
          <p class="modal-sub">当前分类：<span class="old-cat-tag">{{ kb.catOldCategory.value }}</span></p>
          <div class="cat-modal-row">
            <label>新分类：</label>
            <select v-model="kb.catNewCategory.value" class="cat-modal-select" :disabled="kb.changingCat.value">
              <option v-for="c in kb.allCategories()" :key="c" :value="c">{{ c }}</option>
              <option value="__custom__">＋ 新分类...</option>
            </select>
            <input v-if="kb.catNewCategory.value === '__custom__'" v-model="kb.catNewCustom.value" class="cat-input" placeholder="新分类名" :disabled="kb.changingCat.value" />
          </div>
          <p v-if="kb.catError.value" class="modal-error">{{ kb.catError.value }}</p>
          <div class="modal-actions">
            <button class="action-btn action-btn--upload" :disabled="kb.changingCat.value" @click="kb.confirmCatChange()">{{ kb.changingCat.value ? '更改中' : '确认' }}</button>
            <button class="action-btn action-btn--cancel" :disabled="kb.changingCat.value" @click="kb.cancelCatChange()">取消</button>
          </div>
        </div>
      </div>
    </Teleport>
    <Teleport to="body">
      <div v-if="kb.deleteTarget.value" class="modal-overlay" @click.self="kb.cancelDelete()">
        <div class="modal-card">
          <h2>⚠️ 确认删除</h2>
          <p class="modal-body">确定要删除文档 <strong>{{ kb.deleteFileName.value }}</strong>？</p>
          <p class="modal-warn">此操作将从磁盘和向量库中永久移除该文件，不可恢复。</p>
          <p v-if="kb.deleteError.value" class="modal-error">{{ kb.deleteError.value }}</p>
          <div class="modal-actions">
            <button class="action-btn action-btn--del" :disabled="kb.deleting.value" @click="kb.confirmDelete()">{{ kb.deleting.value ? '删除中' : '确认删除' }}</button>
            <button class="action-btn action-btn--cancel" :disabled="kb.deleting.value" @click="kb.cancelDelete()">取消</button>
          </div>
        </div>
      </div>
    </Teleport>
  </div>
</template>

<style scoped>
.admin-page { min-height: 100vh; display: flex; align-items: flex-start; justify-content: center; padding: 48px 24px; }
.gate-card { width: min(480px, 100%); margin-top: 80px; padding: 48px 36px; border: 1px solid rgba(148,163,184,0.24); border-radius: 24px; background: rgba(255,255,255,0.92); box-shadow: 0 24px 60px rgba(15,23,42,0.1); text-align: center; }
.gate-card h1 { font-size: 1.8rem; font-weight: 700; color: #0f172a; margin-bottom: 8px; }
.gate-desc { color: #64748b; font-size: 0.92rem; margin-bottom: 28px; }
.password-row { display: flex; gap: 12px; }
.password-input { flex: 1; padding: 14px 16px; border: 1px solid rgba(148,163,184,0.4); border-radius: 14px; font: inherit; font-size: 1rem; outline: none; transition: border-color 0.2s, box-shadow 0.2s; }
.password-input:focus { border-color: rgba(37,99,235,0.5); box-shadow: 0 0 0 3px rgba(37,99,235,0.1); }
.unlock-btn { min-width: 88px; padding: 12px 22px; border: none; border-radius: 14px; background: linear-gradient(135deg, #2563eb, #1d4ed8); color: #fff; font: inherit; font-weight: 700; cursor: pointer; transition: transform 0.15s, box-shadow 0.15s; }
.unlock-btn:hover:enabled { transform: translateY(-1px); box-shadow: 0 8px 20px rgba(37,99,235,0.3); }
.unlock-btn:disabled { opacity: 0.6; cursor: not-allowed; }
.error-msg { margin-top: 14px; color: #dc2626; font-size: 0.9rem; }

.mode-warn-overlay { position: fixed; inset: 0; z-index: 2000; display: flex; align-items: center; justify-content: center; background: rgba(15,23,42,0.5); backdrop-filter: blur(4px); }
.mode-warn-modal { width: min(440px,92vw); padding: 36px; border-radius: 20px; background: #fff; box-shadow: 0 24px 60px rgba(15,23,42,0.2); text-align: center; }
.mode-warn-modal h2 { font-size: 1.3rem; font-weight: 700; color: #0f172a; margin-bottom: 14px; }
.mode-warn-modal p { color: #64748b; font-size: 0.92rem; line-height: 1.6; margin-bottom: 20px; }

.structure-panel { width: min(1000px, 100%); }
.header-actions-row { display: flex; justify-content: flex-end; margin-bottom: 16px; }
.mode-mgr-btn { background: linear-gradient(135deg, #7c3aed, #6d28d9); color: #fff; padding: 8px 18px; }
.mode-mgr-btn:hover { transform: translateY(-1px); }

.mode-mgr-list { display: flex; flex-direction: column; gap: 6px; }
.mode-mgr-item { display: flex; align-items: center; gap: 10px; padding: 10px 14px; border-radius: 10px; background: rgba(255,255,255,0.5); border: 1px solid rgba(148,163,184,0.08); }
.mode-mgr-icon { font-size: 1rem; }
.mode-mgr-name { font-weight: 600; color: #1e293b; font-size: 0.9rem; flex: 1; }
.mode-mgr-id { font-size: 0.76rem; color: #94a3b8; font-family: monospace; }
.mode-mgr-builtin { font-size: 0.78rem; color: #94a3b8; }

.panel-header { margin-bottom: 24px; }
.panel-header h1 { font-size: 1.8rem; font-weight: 700; color: #0f172a; }
.overview-cards { display: flex; gap: 12px; margin-bottom: 24px; flex-wrap: wrap; }
.overview-card { flex: 1; min-width: 110px; padding: 18px 16px; border: 1px solid rgba(148,163,184,0.16); border-radius: 16px; background: rgba(255,255,255,0.5); box-shadow: 0 4px 12px rgba(15,23,42,0.04); text-align: center; }
.overview-card--action { cursor: pointer; transition: background 0.15s; }
.overview-card--action:hover { background: rgba(255,255,255,0.7); }
.ov-number { display: block; font-size: 1.8rem; font-weight: 800; color: #2563eb; }
.ov-label { font-size: 0.78rem; color: #64748b; margin-top: 2px; }
.empty-state { text-align: center; padding: 60px 20px; color: #94a3b8; }

/* ── Section Card ── */
.section-card { margin-bottom: 20px; padding: 20px; border: 1px solid rgba(148,163,184,0.12); border-radius: 16px; background: rgba(255,255,255,0.5); box-shadow: 0 4px 12px rgba(15,23,42,0.03); }
.section-card h2 { font-size: 1.05rem; font-weight: 700; color: #0f172a; margin-bottom: 12px; display: flex; align-items: center; gap: 8px; }

.upload-row { display: flex; gap: 10px; align-items: center; flex-wrap: wrap; }
.upload-row input[type="file"] { font-size: 0.88rem; }
.category-combo { display: flex; gap: 8px; align-items: center; }
.category-combo select { padding: 8px 12px; border: 1px solid rgba(148,163,184,0.4); border-radius: 10px; font: inherit; font-size: 0.86rem; outline: none; }
.cat-input { padding: 8px 12px; border: 1px solid rgba(148,163,184,0.4); border-radius: 10px; font: inherit; font-size: 0.86rem; width: 130px; outline: none; }

.prompts-list { display: flex; flex-direction: column; gap: 6px; }
.prompt-row { display: flex; align-items: center; gap: 10px; padding: 10px 14px; border-radius: 10px; background: rgba(255,255,255,0.4); border: 1px solid rgba(148,163,184,0.06); cursor: pointer; transition: all 0.12s; }
.prompt-row:hover { border-color: #93c5fd; background: #eff6ff; }
.prompt-icon { font-size: 0.9rem; }
.prompt-name { font-weight: 600; color: #1e293b; font-size: 0.88rem; }
.prompt-file { font-family: monospace; font-size: 0.76rem; color: #64748b; }
.prompt-size { font-size: 0.74rem; color: #94a3b8; margin-left: auto; }
.prompt-missing { font-size: 0.74rem; color: #dc2626; margin-left: auto; font-weight: 600; }
.prompt-edit-textarea { width: 100%; padding: 14px; border: 1px solid rgba(148,163,184,0.3); border-radius: 12px; font: inherit; font-size: 0.86rem; line-height: 1.7; resize: vertical; outline: none; color: #0f172a; font-family: 'Consolas', monospace; }
.prompt-edit-textarea:focus { border-color: rgba(37,99,235,0.5); box-shadow: 0 0 0 3px rgba(37,99,235,0.08); }

/* ── 模式管理 ── */
.mode-card { margin-bottom: 8px; border-radius: 12px; background: rgba(255,255,255,0.4); border: 1px solid rgba(148,163,184,0.08); overflow: hidden; }
.mode-card-header { display: flex; align-items: center; gap: 8px; padding: 10px 14px; cursor: pointer; transition: background 0.12s; }
.mode-card-header:hover { background: rgba(255,255,255,0.4); }
.mode-toggle { font-size: 0.6rem; color: #94a3b8; }
.mode-icon { font-size: 1rem; }
.mode-name { font-weight: 600; color: #1e293b; font-size: 0.88rem; }
.mode-badge { padding: 2px 8px; border-radius: 999px; font-size: 0.68rem; font-weight: 600; }
.badge--builtin { background: #eff6ff; color: #2563eb; }
.badge--custom { background: #fef3c7; color: #d97706; }
.badge--on { background: #dcfce7; color: #15803d; cursor: pointer; }
.badge--off { background: #f1f5f9; color: #94a3b8; cursor: pointer; text-decoration: line-through; }
.mode-id { font-size: 0.74rem; color: #94a3b8; font-family: monospace; flex: 1; text-align: right; }
.mode-card-body { padding: 0 14px 14px; display: flex; flex-direction: column; gap: 8px; }
.mode-field { display: flex; align-items: center; gap: 8px; }
.mode-field label { font-size: 0.76rem; font-weight: 600; color: #64748b; min-width: 55px; }
.mode-field-input { flex: 1; padding: 6px 10px; border: 1px solid rgba(148,163,184,0.2); border-radius: 8px; font: inherit; font-size: 0.8rem; outline: none; color: #0f172a; background: rgba(255,255,255,0.4); resize: vertical; }
.mode-field-input:focus { border-color: rgba(37,99,235,0.4); }
.mode-field--prompt { flex-direction: column; align-items: stretch; }
.mode-prompt-text { font-family: 'Consolas', monospace; font-size: 0.76rem !important; }
.mode-prompt-file { font-size: 0.72rem; color: #94a3b8; margin-left: auto; }
.mode-data-list { font-size: 0.78rem; color: #475569; }
.mode-loading { font-size: 0.8rem; color: #94a3b8; padding: 12px; }

/* ── 新建模式 ── */
.mode-create-card { border-style: dashed; border-color: rgba(37,99,235,0.2); background: rgba(239,246,255,0.4); }
.mode-create-row { display: flex; gap: 10px; align-items: center; flex-wrap: wrap; margin-bottom: 8px; }
.mode-title-input { padding: 8px 12px; border: 1px solid rgba(148,163,184,0.25); border-radius: 10px; font: inherit; font-size: 0.86rem; outline: none; width: 160px; background: rgba(255,255,255,0.4); }
.mode-title-input:focus { border-color: rgba(37,99,235,0.4); }
.mode-file-group { display: flex; align-items: center; gap: 4px; font-size: 0.8rem; }
.file-label { color: #64748b; font-weight: 600; white-space: nowrap; }
.mode-file-group input[type="file"] { font-size: 0.76rem; max-width: 140px; }
.mode-hint { font-size: 0.74rem; color: #94a3b8; }

/* ── 按钮 ═── */
.action-btn { padding: 7px 16px; border: none; border-radius: 10px; font: inherit; font-size: 0.8rem; font-weight: 600; cursor: pointer; transition: all 0.15s; }
.action-btn:hover:enabled { transform: translateY(-1px); }
.action-btn:disabled { opacity: 0.5; cursor: not-allowed; }
.action-btn--upload { background: linear-gradient(135deg, #2563eb, #1d4ed8); color: #fff; }
.action-btn--del { background: #dc2626; color: #fff; }
.action-btn--cancel { background: #f1f5f9; color: #475569; }
.mini-btn { border: none; background: transparent; cursor: pointer; font-size: 0.9rem; padding: 2px 6px; border-radius: 6px; }
.mini-btn:hover { background: #f1f5f9; }
.mini-btn--del:hover { background: #fee2e2; }
.mini-btn--cat:hover { background: #e0f2fe; }
.mini-btn:disabled { opacity: 0.4; cursor: not-allowed; }
.action-msg { margin-top: 10px; font-size: 0.84rem; color: #15803d; }
.msg-error { color: #dc2626; }

/* ── 分类 ═── */
.category-card { margin-bottom: 14px; border: 1px solid rgba(148,163,184,0.1); border-radius: 16px; background: rgba(255,255,255,0.5); overflow: hidden; }
.category-header { display: flex; align-items: center; gap: 12px; padding: 14px 20px; cursor: pointer; user-select: none; transition: background 0.15s; }
.category-header:hover { background: rgba(255,255,255,0.4); }
.cat-toggle { font-size: 0.65rem; color: #94a3b8; }
.cat-name { font-size: 1.05rem; font-weight: 700; color: #0f172a; flex: 1; }
.cat-badges { display: flex; gap: 8px; }
.badge { padding: 4px 12px; border-radius: 999px; font-size: 0.7rem; font-weight: 600; }
.badge--files { background: #eff6ff; color: #2563eb; }
.badge--chunks { background: #dcfce7; color: #15803d; }
.category-body { padding: 0 20px 14px; }
.file-card { margin-top: 12px; padding: 14px; border: 1px solid rgba(148,163,184,0.08); border-radius: 12px; background: rgba(255,255,255,0.4); }
.file-header { display: flex; align-items: center; gap: 8px; margin-bottom: 8px; }
.file-icon { font-size: 1rem; }
.file-name { font-weight: 600; color: #1e293b; flex: 1; }
.file-stats { font-size: 0.74rem; color: #94a3b8; margin-right: 8px; }
.chunk-list { display: flex; flex-direction: column; gap: 5px; }
.chunk-item { display: flex; align-items: flex-start; gap: 10px; padding: 7px 12px; border-radius: 8px; background: rgba(255,255,255,0.4); font-size: 0.8rem; border: 1px solid rgba(148,163,184,0.06); cursor: pointer; transition: all 0.12s; }
.chunk-item:hover { border-color: #93c5fd; background: #f8faff; }
.chunk-item--editing { border-color: #2563eb; background: #eff6ff; }
.chunk-id { font-family: monospace; font-size: 0.68rem; color: #94a3b8; flex-shrink: 0; }
.chunk-preview { flex: 1; color: #334155; line-height: 1.5; }
.chunk-len { flex-shrink: 0; font-size: 0.68rem; color: #94a3b8; }

/* ── 弹窗 ═── */
.modal-overlay { position: fixed; inset: 0; z-index: 1000; display: flex; align-items: center; justify-content: center; background: rgba(15,23,42,0.45); backdrop-filter: blur(4px); }
.modal-card { width: min(440px, 92vw); padding: 32px; border-radius: 20px; background: #fff; box-shadow: 0 24px 60px rgba(15,23,42,0.2); text-align: center; }
.modal-card--wide { width: min(680px, 94vw); text-align: left; }
.modal-card h2 { font-size: 1.3rem; font-weight: 700; color: #0f172a; margin-bottom: 16px; }
.modal-body { font-size: 1rem; color: #334155; margin-bottom: 8px; }
.modal-body strong { color: #0f172a; }
.modal-warn { font-size: 0.84rem; color: #dc2626; margin-bottom: 20px; }
.modal-error { margin-bottom: 12px; padding: 8px 12px; border-radius: 8px; background: #fef2f2; color: #dc2626; font-size: 0.84rem; }
.modal-actions { display: flex; gap: 12px; justify-content: center; }
.modal-sub { font-size: 0.88rem; color: #64748b; margin-bottom: 16px; }
.chunk-edit-meta { display: flex; gap: 10px; flex-wrap: wrap; margin-bottom: 16px; }
.meta-tag { font-size: 0.76rem; padding: 3px 10px; border-radius: 999px; background: #f1f5f9; color: #475569; }
.chunk-edit-textarea { width: 100%; padding: 14px; border: 1px solid rgba(148,163,184,0.3); border-radius: 12px; font: inherit; font-size: 0.9rem; line-height: 1.7; resize: vertical; outline: none; color: #0f172a; }
.chunk-edit-textarea:focus { border-color: rgba(37,99,235,0.5); box-shadow: 0 0 0 3px rgba(37,99,235,0.08); }
.chunk-edit-chars { margin-top: 8px; font-size: 0.78rem; color: #94a3b8; }
.cat-modal-row { display: flex; align-items: center; gap: 10px; margin-bottom: 16px; font-size: 0.9rem; }
.cat-modal-row label { font-weight: 600; color: #0f172a; }
.cat-modal-select { padding: 8px 12px; border: 1px solid rgba(148,163,184,0.4); border-radius: 10px; font: inherit; font-size: 0.88rem; outline: none; }
.old-cat-tag { display: inline-block; padding: 2px 10px; border-radius: 999px; background: #eff6ff; color: #2563eb; font-weight: 600; font-size: 0.82rem; }

@media (max-width: 768px) {
  .admin-page { padding: 24px 12px; }
  .gate-card { padding: 32px 20px; margin-top: 32px; }
  .password-row { flex-direction: column; }
  .overview-cards { flex-direction: column; }
  .upload-row { flex-direction: column; align-items: stretch; }
  .category-combo { flex-direction: column; }
  .search-bar { flex-wrap: wrap; }
  .chunk-edit-meta { flex-direction: column; gap: 4px; }
  .mode-create-row { flex-direction: column; align-items: stretch; }
}
</style>
