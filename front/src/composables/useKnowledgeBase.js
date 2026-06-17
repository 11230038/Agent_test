import { computed, ref } from 'vue'

export function useKnowledgeBase(token) {
  const structure = ref(null)
  const expandedCategories = ref({})

  async function loadStructure() {
    try {
      const resp = await fetch('/api/admin/knowledge', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ token: token.value }),
      })
      if (resp.ok) {
        const data = await resp.json()
        if (data.success) structure.value = data.data
      }
    } catch { /* ignore */ }
  }

  function toggleCategory(name) {
    expandedCategories.value[name] = !expandedCategories.value[name]
  }

  // ── Upload ──
  const uploadFile = ref(null)
  const uploadCategory = ref('扫地机器人客服')
  const uploadCategoryCustom = ref('')
  const uploading = ref(false)
  const uploadMsg = ref('')
  const customCategories = ref([])

  function allCategories() {
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

  async function doUpload() {
    if (!uploadFile.value || uploading.value) return
    const cat = uploadCategory.value === '__custom__' ? uploadCategoryCustom.value.trim() : uploadCategory.value
    if (!cat) { uploadMsg.value = '请输入分类名称'; return }
    uploading.value = true
    uploadMsg.value = ''
    const form = new FormData()
    form.append('token', token.value)
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
      await loadStructure()
    } catch (e) {
      uploadMsg.value = '❌ ' + (e instanceof Error ? e.message : '上传失败')
    } finally {
      uploading.value = false
    }
  }

  // ── Delete ──
  const deleting = ref(false)
  const deleteTarget = ref(null)
  const deleteError = ref('')
  const deleteFileName = computed(() => deleteTarget.value?.name || '')

  function showDeleteModal(source, name) {
    deleteTarget.value = { source, name }
    deleteError.value = ''
  }
  function cancelDelete() {
    deleteTarget.value = null
    deleteError.value = ''
  }
  async function confirmDelete() {
    const source = deleteTarget.value?.source
    if (!source || deleting.value) return
    deleting.value = true
    deleteError.value = ''
    try {
      const resp = await fetch('/api/admin/delete', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ token: token.value, source }),
      })
      const data = await resp.json()
      if (!resp.ok) throw new Error(data.message || '删除失败')
      deleteTarget.value = null
      await loadStructure()
    } catch (e) {
      deleteError.value = e instanceof Error ? e.message : '删除失败'
    } finally {
      deleting.value = false
    }
  }

  // ── Category Change ──
  const catTarget = ref(null)
  const catNewCategory = ref('')
  const catNewCustom = ref('')
  const changingCat = ref(false)
  const catError = ref('')
  const catFileName = computed(() => catTarget.value?.name || '')
  const catOldCategory = computed(() => catTarget.value?.oldCategory || '')

  function showCatModal(source, name, oldCat) {
    catTarget.value = { source, name, oldCategory: oldCat }
    catNewCategory.value = allCategories().includes(oldCat) ? oldCat : '__custom__'
    catNewCustom.value = allCategories().includes(oldCat) ? '' : oldCat
    catError.value = ''
  }
  function cancelCatChange() {
    catTarget.value = null
    catError.value = ''
  }
  async function confirmCatChange() {
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
        body: JSON.stringify({ token: token.value, source: catTarget.value.source, category: newCat }),
      })
      const data = await resp.json()
      if (!resp.ok) throw new Error(data.message || '更改失败')
      if (catNewCategory.value === '__custom__' && catNewCustom.value.trim()) {
        if (!customCategories.value.includes(catNewCustom.value.trim())) {
          customCategories.value.push(catNewCustom.value.trim())
        }
      }
      catTarget.value = null
      await loadStructure()
    } catch (e) {
      catError.value = e instanceof Error ? e.message : '更改失败'
    } finally {
      changingCat.value = false
    }
  }

  return {
    structure, expandedCategories, loadStructure, toggleCategory,
    uploadFile, uploadCategory, uploadCategoryCustom, uploading, uploadMsg,
    customCategories, allCategories, doUpload,
    deleting, deleteTarget, deleteError, deleteFileName,
    showDeleteModal, cancelDelete, confirmDelete,
    catTarget, catNewCategory, catNewCustom, changingCat, catError,
    catFileName, catOldCategory,
    showCatModal, cancelCatChange, confirmCatChange,
  }
}
