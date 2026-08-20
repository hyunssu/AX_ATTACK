import { getToken } from './auth'

function authHeaders() {
  const token = getToken()
  return token ? { Authorization: `Bearer ${token}` } : {}
}

async function apiFetch(url, options = {}) {
  const res = await fetch(url, options)
  if (res.status === 401) {
    localStorage.removeItem('manual_system_token')
    localStorage.removeItem('manual_system_username')
    window.location.href = '/login'
    return null
  }
  return res
}

export async function login(username, password) {
  const res = await fetch('/api/auth/login', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ username, password }),
  })
  const data = await res.json()
  if (!res.ok) throw new Error(data.detail || '로그인에 실패했습니다.')
  return data
}

export async function fetchManuals() {
  const res = await apiFetch('/api/manuals', { headers: authHeaders() })
  return res ? res.json() : []
}

export async function fetchVersions(manualId) {
  const res = await apiFetch(`/api/manuals/${manualId}/versions`, { headers: authHeaders() })
  return res ? res.json() : []
}

export async function analyzeManualSections(file, contextCategory = null, contextExtraSubs = null) {
  const formData = new FormData()
  formData.append('file', file)
  if (contextCategory) formData.append('context_category', contextCategory)
  if (contextExtraSubs) formData.append('context_extra_subs', JSON.stringify(contextExtraSubs))
  const res = await apiFetch('/api/manuals/analyze', {
    method: 'POST',
    headers: authHeaders(),
    body: formData,
  })
  if (!res) throw new Error('인증이 필요합니다.')
  const data = await res.json()
  if (!res.ok) throw new Error(data.detail || '분석에 실패했습니다.')
  return data
}

export async function confirmManualSections(sourceDocumentId, sections) {
  const res = await apiFetch('/api/manuals/confirm', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', ...authHeaders() },
    body: JSON.stringify({ source_document_id: sourceDocumentId, sections }),
  })
  if (!res) throw new Error('인증이 필요합니다.')
  const data = await res.json()
  if (!res.ok) throw new Error(data.detail || '등록에 실패했습니다.')
  return data
}

export async function reclassifySection(title, content) {
  const res = await apiFetch('/api/manuals/reclassify-section', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', ...authHeaders() },
    body: JSON.stringify({ title, content }),
  })
  if (!res) throw new Error('인증이 필요합니다.')
  const data = await res.json()
  if (!res.ok) throw new Error(data.detail || '재분류에 실패했습니다.')
  return data
}

export async function addManualVersion(manualId, file) {
  const formData = new FormData()
  formData.append('file', file)
  const res = await apiFetch(`/api/manuals/${manualId}/versions`, {
    method: 'POST',
    headers: authHeaders(),
    body: formData,
  })
  if (!res) throw new Error('인증이 필요합니다.')
  const data = await res.json()
  if (!res.ok) throw new Error(data.detail || '버전 추가에 실패했습니다.')
  return data
}

export async function fetchManualVersionContent(manualId, versionId) {
  const res = await apiFetch(`/api/manuals/${manualId}/versions/${versionId}/content`, { headers: authHeaders() })
  return res ? res.json() : { chunks: [] }
}

export async function fetchUploadJobStatus(jobId) {
  const res = await apiFetch(`/api/manuals/jobs/${jobId}`, { headers: authHeaders() })
  if (!res) throw new Error('인증이 필요합니다.')
  const data = await res.json()
  if (!res.ok) throw new Error(data.detail || '진행 상태를 가져오지 못했습니다.')
  return data
}

export async function createChatRoom(engine) {
  const res = await apiFetch('/api/chat/rooms', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', ...authHeaders() },
    body: JSON.stringify({ engine: engine || 'langchain' }),
  })
  return res ? res.json() : null
}

export async function listChatRooms() {
  const res = await apiFetch('/api/chat/rooms', { headers: authHeaders() })
  return res ? res.json() : []
}

export async function deleteChatRoom(roomId) {
  const res = await apiFetch(`/api/chat/rooms/${roomId}`, {
    method: 'DELETE',
    headers: authHeaders(),
  })
  return res ? res.json() : null
}

export async function listRoomMessages(roomId) {
  const res = await apiFetch(`/api/chat/rooms/${roomId}/messages`, { headers: authHeaders() })
  return res ? res.json() : []
}

export async function sendRoomMessage(roomId, message) {
  const res = await apiFetch(`/api/chat/rooms/${roomId}/messages`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', ...authHeaders() },
    body: JSON.stringify({ input_message: message }),
  })
  return res ? res.json() : null
}

export async function listTrails(category) {
  const res = await apiFetch(`/api/manuals/trails?category=${encodeURIComponent(category)}`, { headers: authHeaders() })
  return res ? res.json() : []
}

export async function createTrail(category, name) {
  const res = await apiFetch('/api/manuals/trails', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', ...authHeaders() },
    body: JSON.stringify({ category, name }),
  })
  if (!res) throw new Error('인증이 필요합니다.')
  const data = await res.json()
  if (!res.ok) throw new Error(data.detail || '트레일 생성에 실패했습니다.')
  return data
}

export async function quickCreateManual(title, categories, subCategory) {
  const res = await apiFetch('/api/manuals/quick-create', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', ...authHeaders() },
    body: JSON.stringify({ title, categories, sub_category: subCategory }),
  })
  if (!res) throw new Error('인증이 필요합니다.')
  const data = await res.json()
  if (!res.ok) throw new Error(data.detail || '생성에 실패했습니다.')
  return data
}

export async function setManualSubCategory(manualId, subCategory) {
  const res = await apiFetch(`/api/manuals/${manualId}/sub-category`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json', ...authHeaders() },
    body: JSON.stringify({ sub_category: subCategory }),
  })
  if (!res) throw new Error('인증이 필요합니다.')
  return res.json()
}

export async function dismissManualAiSuggestion(manualId) {
  const res = await apiFetch(`/api/manuals/${manualId}/ai-suggested-sub`, {
    method: 'DELETE',
    headers: authHeaders(),
  })
  if (!res) throw new Error('인증이 필요합니다.')
  return res.json()
}

export async function getManualDraft(manualId) {
  const res = await apiFetch(`/api/manuals/${manualId}/draft`, { headers: authHeaders() })
  return res ? res.json() : { content: [], status: 'no_draft', from_chunks: true }
}

export async function saveManualDraft(manualId, content) {
  const res = await apiFetch(`/api/manuals/${manualId}/draft`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json', ...authHeaders() },
    body: JSON.stringify({ content }),
  })
  return res ? res.json() : null
}

export async function deployManualDraft(manualId) {
  const res = await apiFetch(`/api/manuals/${manualId}/deploy`, {
    method: 'POST',
    headers: authHeaders(),
  })
  if (!res) throw new Error('인증이 필요합니다.')
  const data = await res.json()
  if (!res.ok) throw new Error(data.detail || '배포에 실패했습니다.')
  return data
}
