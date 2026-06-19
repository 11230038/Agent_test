<script setup>
import { useAdminAuth } from '@/composables/useAdminAuth'
import { useKnowledgeBase } from '@/composables/useKnowledgeBase'
import { useChunkEditor } from '@/composables/useChunkEditor'
import { usePromptEditor } from '@/composables/usePromptEditor'

const auth = useAdminAuth()
const kb = useKnowledgeBase(auth.token)
const chunk = useChunkEditor(auth.token, kb.structure, kb.loadStructure)
const prompt = usePromptEditor(auth.token)

// 登录成功后加载数据
const unlock = async () => {
  await auth.login()
  if (auth.authed.value) {
    await kb.loadStructure()
    await prompt.loadPrompts()
  }
}
const handleKeydown = (e) => { if (e.key === 'Enter') unlock() }
</script>

<template>
  <div class="admin-page">
    <!-- ═══ 密码门 ═══ -->
    <section v-if="!auth.authed.value" class="gate-card">
      <h1>🔐 管理页面</h1>
      <p class="gate-desc">请输入管理密码以查看和编辑知识库</p>
      <div class="password-row">
        <input v-model="auth.password.value" type="password" class="password-input" placeholder="输入密码"
          :disabled="auth.loading.value" @keydown="handleKeydown" />
        <button class="unlock-btn" :disabled="auth.loading.value" @click="unlock">
          {{ auth.loading.value ? '验证中...' : '确认' }}
        </button>
      </div>
      <p v-if="auth.error.value" class="error-msg">{{ auth.error.value }}</p>
    </section>

    <!-- ═══ 管理面板 ═══ -->
    <section v-else class="structure-panel">
      <header class="panel-header">
        <h1>📚 知识库内容结构</h1>
        <p class="panel-sub">集合：<strong>{{ kb.structure.value.collection_name }}</strong></p>
      </header>

      <!-- 概览 -->
      <div class="overview-cards">
        <div class="overview-card"><span class="ov-number">{{ kb.structure.value.chunk_count }}</span><span class="ov-label">总 Chunk</span></div>
        <div class="overview-card"><span class="ov-number">{{ kb.structure.value.category_count }}</span><span class="ov-label">分类数</span></div>
        <div class="overview-card"><span class="ov-number">{{ kb.structure.value.tracked_file_count }}</span><span class="ov-label">已追踪文件</span></div>
        <div class="overview-card overview-card--action" @click="kb.loadStructure()">
          <span class="ov-number">🔄</span><span class="ov-label">刷新数据</span>
        </div>
      </div>

      <!-- ═══ 上传区域 ═══ -->
      <div class="upload-card">
        <h2>📤 上传文档</h2>
        <div class="upload-row">
          <input id="file-input" type="file" accept=".pdf,.txt" @change="e => kb.uploadFile = e.target.files[0]"
            :disabled="kb.uploading.value" />
          <div class="category-combo">
            <select v-model="kb.uploadCategory.value" :disabled="kb.uploading.value">
              <option v-for="c in kb.allCategories()" :key="c" :value="c">{{ c }}</option>
              <option value="__custom__">＋ 新分类...</option>
            </select>
            <input v-if="kb.uploadCategory.value === '__custom__'" v-model="kb.uploadCategoryCustom.value"
              class="cat-input" placeholder="输入新分类名" :disabled="kb.uploading.value" />
          </div>
          <button class="action-btn action-btn--upload" :disabled="!kb.uploadFile || kb.uploading.value" @click="kb.doUpload()">
            {{ kb.uploading.value ? '上传中...' : '上传' }}
          </button>
        </div>
        <p v-if="kb.uploadMsg.value" class="action-msg" :class="{ 'msg-error': kb.uploadMsg.value.startsWith('❌') }">{{ kb.uploadMsg.value }}</p>
      </div>

      <!-- ═══ 提示词管理 ═══ -->
      <div class="prompts-card">
        <h2>📝 提示词管理 <button class="mini-btn" title="刷新" @click="prompt.loadPrompts()">🔄</button></h2>
        <div class="prompts-list">
          <div v-for="p in prompt.prompts.value" :key="p.path" class="prompt-row" @click="prompt.startPromptEdit(p)">
            <span class="prompt-icon">📄</span>
            <span class="prompt-name">{{ p.name }}</span>
            <span class="prompt-file">{{ p.filename }}</span>
            <span v-if="p.exists" class="prompt-size">{{ (p.size / 1024).toFixed(1) }} KB</span>
            <span v-else class="prompt-missing">缺失</span>
          </div>
        </div>
        <p v-if="prompt.promptMsg.value && !prompt.editingPrompt.value" class="action-msg" :class="{ 'msg-error': prompt.promptMsg.value.startsWith('❌') }">{{ prompt.promptMsg.value }}</p>
      </div>

      <!-- ═══ Chunk 检索栏 ═══ -->
      <div class="search-bar">
        <span class="search-icon">🔍</span>
        <input v-model="chunk.chunkSearch.value" class="search-input" placeholder="输入关键词检索 chunk..."
          @input="chunk.onSearchInput()" />
        <button v-if="chunk.chunkSearch.value" class="search-clear" @click="chunk.clearSearch()">✕</button>
        <span v-if="chunk.debouncedSearch.value" class="search-count">找到 {{ chunk.searchResults.value.length }} 个匹配 chunk</span>
      </div>

      <!-- 检索结果 -->
      <div v-if="chunk.debouncedSearch.value && chunk.searchResults.value.length > 0" class="search-results-panel">
        <div v-for="r in chunk.searchResults.value" :key="r.chunk_id" class="search-result-item" @click="chunk.startChunkEdit(r)">
          <div class="sr-context">
            <span class="sr-cat">{{ r.category }}</span>
            <span class="sr-file">📄 {{ r.file }}</span>
            <span class="sr-id">{{ r.chunk_id.slice(-8) }}</span>
          </div>
          <p class="sr-content">{{ r.content_preview }}</p>
        </div>
      </div>
      <div v-if="chunk.debouncedSearch.value && chunk.searchResults.value.length === 0" class="empty-state">
        <p>未找到匹配的 chunk</p>
      </div>

      <!-- ═══ 分类列表 ═══ -->
      <div v-if="!chunk.debouncedSearch.value">
        <div v-if="kb.structure.value.chunk_count === 0" class="empty-state">
          <p>知识库为空，请上传文档。</p>
        </div>

        <div v-for="cat in kb.structure.value.categories" :key="cat.name" class="category-card">
          <div class="category-header" @click="kb.toggleCategory(cat.name)">
            <span class="cat-toggle">{{ kb.expandedCategories.value[cat.name] ? '▼' : '▶' }}</span>
            <span class="cat-name">{{ cat.name }}</span>
            <div class="cat-badges">
              <span class="badge badge--files">{{ cat.file_count }} 文件</span>
              <span class="badge badge--chunks">{{ cat.total_chunks }} chunks</span>
            </div>
          </div>

          <div v-if="kb.expandedCategories.value[cat.name]" class="category-body">
            <div v-for="file in cat.files" :key="file.source" class="file-card">
              <div class="file-header">
                <span class="file-icon">📄</span>
                <span class="file-name">{{ file.name }}</span>
                <span class="file-stats">{{ file.chunk_count }} chunks · {{ file.total_chars }} 字</span>
                <button class="mini-btn mini-btn--cat" title="改分类" @click.stop="kb.showCatModal(file.source, file.name, cat.name)">📁</button>
                <button class="mini-btn mini-btn--del" title="删除文件"
                  :disabled="kb.deleting.value"
                  @click.stop="kb.showDeleteModal(file.source, file.name)">🗑️</button>
              </div>

              <div class="chunk-list">
                <div v-for="c in file.chunks" :key="c.chunk_id" class="chunk-item"
                  :class="{ 'chunk-item--editing': chunk.editingChunk.value?.chunk_id === c.chunk_id }"
                  @click="chunk.startChunkEdit(c)">
                  <span class="chunk-id">{{ c.chunk_id.slice(-8) }}</span>
                  <span class="chunk-preview">{{ c.content_preview }}</span>
                  <span class="chunk-len">{{ c.char_count }}字</span>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </section>

    <!-- ═══ Chunk 编辑弹窗 ═══ -->
    <Teleport to="body">
      <div v-if="chunk.editingChunk.value" class="modal-overlay" @click.self="chunk.cancelChunkEdit()">
        <div class="modal-card modal-card--wide">
          <h2>✏️ 编辑 Chunk</h2>
          <div class="chunk-edit-meta">
            <span class="meta-tag">分类：{{ chunk.editingChunk.value.category }}</span>
            <span class="meta-tag">文件：{{ chunk.editingChunk.value.file }}</span>
            <span class="meta-tag">ID：{{ chunk.editingChunk.value.chunk_id }}</span>
          </div>
          <textarea v-model="chunk.chunkEditContent.value" class="chunk-edit-textarea"
            :disabled="chunk.savingChunk.value" rows="10"></textarea>
          <p class="chunk-edit-chars">{{ chunk.chunkEditContent.value.length }} 字符</p>
          <p v-if="chunk.chunkEditMsg.value" class="action-msg" :class="{ 'msg-error': chunk.chunkEditMsg.value.startsWith('❌') }">{{ chunk.chunkEditMsg.value }}</p>
          <div class="modal-actions">
            <button class="action-btn action-btn--upload" :disabled="chunk.savingChunk.value" @click="chunk.saveChunk()">
              {{ chunk.savingChunk.value ? '保存中...' : '保存修改' }}
            </button>
            <button class="action-btn action-btn--cancel" :disabled="chunk.savingChunk.value" @click="chunk.cancelChunkEdit()">取消</button>
          </div>
        </div>
      </div>
    </Teleport>

    <!-- ═══ 提示词编辑弹窗 ═══ -->
    <Teleport to="body">
      <div v-if="prompt.editingPrompt.value" class="modal-overlay" @click.self="prompt.cancelPromptEdit()">
        <div class="modal-card modal-card--wide">
          <h2>📝 编辑提示词</h2>
          <p class="modal-sub">{{ prompt.editingPrompt.value.name }}（{{ prompt.editingPrompt.value.filename }}）</p>
          <textarea v-model="prompt.promptContent.value" class="prompt-edit-textarea"
            :disabled="prompt.savingPrompt.value" rows="18"></textarea>
          <p class="chunk-edit-chars">{{ prompt.promptContent.value.length }} 字符</p>
          <p v-if="prompt.promptMsg.value" class="action-msg" :class="{ 'msg-error': prompt.promptMsg.value.startsWith('❌') }">{{ prompt.promptMsg.value }}</p>
          <div class="modal-actions">
            <button class="action-btn action-btn--upload" :disabled="prompt.savingPrompt.value" @click="prompt.savePrompt()">
              {{ prompt.savingPrompt.value ? '保存中...' : '保存修改' }}
            </button>
            <button class="action-btn action-btn--cancel" :disabled="prompt.savingPrompt.value" @click="prompt.cancelPromptEdit()">取消</button>
          </div>
        </div>
      </div>
    </Teleport>

    <!-- ═══ 改分类弹窗 ═══ -->
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
            <input v-if="kb.catNewCategory.value === '__custom__'" v-model="kb.catNewCustom.value"
              class="cat-input" placeholder="输入新分类名" :disabled="kb.changingCat.value" />
          </div>
          <p v-if="kb.catError.value" class="modal-error">{{ kb.catError.value }}</p>
          <div class="modal-actions">
            <button class="action-btn action-btn--upload" :disabled="kb.changingCat.value" @click="kb.confirmCatChange()">
              {{ kb.changingCat.value ? '更改中...' : '确认更改' }}
            </button>
            <button class="action-btn action-btn--cancel" :disabled="kb.changingCat.value" @click="kb.cancelCatChange()">取消</button>
          </div>
        </div>
      </div>
    </Teleport>

    <!-- ═══ 删除确认弹窗 ═══ -->
    <Teleport to="body">
      <div v-if="kb.deleteTarget.value" class="modal-overlay" @click.self="kb.cancelDelete()">
        <div class="modal-card">
          <h2>⚠️ 确认删除</h2>
          <p class="modal-body">确定要删除文档 <strong>{{ kb.deleteFileName.value }}</strong> 吗？</p>
          <p class="modal-warn">此操作将从磁盘和向量库中永久移除该文件，不可恢复。</p>
          <p v-if="kb.deleteError.value" class="modal-error">{{ kb.deleteError.value }}</p>
          <div class="modal-actions">
            <button class="action-btn action-btn--del" :disabled="kb.deleting.value" @click="kb.confirmDelete()">
              {{ kb.deleting.value ? '删除中...' : '确认删除' }}
            </button>
            <button class="action-btn action-btn--cancel" :disabled="kb.deleting.value" @click="kb.cancelDelete()">取消</button>
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
.upload-card { margin-bottom: 20px; padding: 20px; border: 1px solid rgba(148, 163, 184, 0.2); border-radius: 16px; background: rgba(255,255,255,0.5); box-shadow: 0 4px 12px rgba(15, 23, 42, 0.03); }
.upload-card h2 { font-size: 1.05rem; font-weight: 700; color: #0f172a; margin-bottom: 12px; }
.upload-row { display: flex; gap: 10px; align-items: center; flex-wrap: wrap; }
.upload-row input[type="file"] { font-size: 0.88rem; }
.category-combo { display: flex; gap: 8px; align-items: center; }
.category-combo select { padding: 8px 12px; border: 1px solid rgba(148, 163, 184, 0.4); border-radius: 10px; font: inherit; font-size: 0.86rem; outline: none; }
.cat-input { padding: 8px 12px; border: 1px solid rgba(148, 163, 184, 0.4); border-radius: 10px; font: inherit; font-size: 0.86rem; width: 130px; outline: none; }

/* ── 提示词管理 ── */
.prompts-card { margin-bottom: 20px; padding: 20px; border: 1px solid rgba(148, 163, 184, 0.2); border-radius: 16px; background: rgba(255,255,255,0.5); box-shadow: 0 4px 12px rgba(15, 23, 42, 0.03); }
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
.mini-btn--cat:hover { background: #e0f2fe; }
.mini-btn:disabled { opacity: 0.4; cursor: not-allowed; }
.action-msg { margin-top: 10px; font-size: 0.86rem; color: #15803d; }
.msg-error { color: #dc2626; }

/* ── 弹窗 ── */
.modal-overlay { position: fixed; inset: 0; z-index: 1000; display: flex; align-items: center; justify-content: center; background: rgba(15, 23, 42, 0.45); backdrop-filter: blur(4px); }
.modal-card { width: min(440px, 92vw); padding: 32px; border-radius: 20px; background: #fff; box-shadow: 0 24px 60px rgba(15, 23, 42, 0.2); text-align: center; }
.modal-card--wide { width: min(680px, 94vw); text-align: left; }
.modal-card h2 { font-size: 1.3rem; font-weight: 700; color: #0f172a; margin-bottom: 16px; }
.modal-body { font-size: 1rem; color: #334155; margin-bottom: 8px; }
.modal-body strong { color: #0f172a; }
.modal-warn { font-size: 0.84rem; color: #dc2626; margin-bottom: 20px; }
.modal-error { margin-bottom: 12px; padding: 8px 12px; border-radius: 8px; background: #fef2f2; color: #dc2626; font-size: 0.84rem; }
.modal-actions { display: flex; gap: 12px; justify-content: center; }
.modal-sub { font-size: 0.88rem; color: #64748b; margin-bottom: 16px; }

/* ── Chunk 编辑弹窗 ── */
.chunk-edit-meta { display: flex; gap: 10px; flex-wrap: wrap; margin-bottom: 16px; }
.meta-tag { font-size: 0.76rem; padding: 3px 10px; border-radius: 999px; background: #f1f5f9; color: #475569; }
.chunk-edit-textarea { width: 100%; padding: 14px; border: 1px solid rgba(148, 163, 184, 0.3); border-radius: 12px; font: inherit; font-size: 0.9rem; line-height: 1.7; resize: vertical; outline: none; color: #0f172a; }
.chunk-edit-textarea:focus { border-color: rgba(37, 99, 235, 0.5); box-shadow: 0 0 0 3px rgba(37, 99, 235, 0.08); }
.chunk-edit-chars { margin-top: 8px; font-size: 0.78rem; color: #94a3b8; }

/* ── 改分类弹窗 ── */
.cat-modal-row { display: flex; align-items: center; gap: 10px; margin-bottom: 16px; font-size: 0.9rem; }
.cat-modal-row label { font-weight: 600; color: #0f172a; }
.cat-modal-select { padding: 8px 12px; border: 1px solid rgba(148, 163, 184, 0.4); border-radius: 10px; font: inherit; font-size: 0.88rem; outline: none; }
.old-cat-tag { display: inline-block; padding: 2px 10px; border-radius: 999px; background: #eff6ff; color: #2563eb; font-weight: 600; font-size: 0.82rem; }

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
