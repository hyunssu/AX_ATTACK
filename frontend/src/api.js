import { getToken } from './auth'

function authHeaders() {
  const token = getToken()
  return token ? { Authorization: `Bearer ${token}` } : {}
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
  const res = await fetch('/api/manuals', { headers: authHeaders() })
  return res.json()
}

export async function fetchVersions(manualId) {
  const res = await fetch(`/api/manuals/${manualId}/versions`, { headers: authHeaders() })
  return res.json()
}

export async function createManual(title, file) {
  const formData = new FormData()
  formData.append('file', file)
  const res = await fetch(`/api/manuals?title=${encodeURIComponent(title)}`, {
    method: 'POST',
    headers: authHeaders(),
    body: formData,
  })
  const data = await res.json()
  if (!res.ok) throw new Error(data.detail || '등록에 실패했습니다.')
  return data
}

export async function previewManualSections(file) {
  const formData = new FormData()
  formData.append('file', file)
  const res = await fetch('/api/manuals/preview-sections', {
    method: 'POST',
    headers: authHeaders(),
    body: formData,
  })
  const data = await res.json()
  if (!res.ok) throw new Error(data.detail || '미리보기에 실패했습니다.')
  return data
}

export async function addManualVersion(manualId, file) {
  const formData = new FormData()
  formData.append('file', file)
  const res = await fetch(`/api/manuals/${manualId}/versions`, {
    method: 'POST',
    headers: authHeaders(),
    body: formData,
  })
  const data = await res.json()
  if (!res.ok) throw new Error(data.detail || '버전 추가에 실패했습니다.')
  return data
}

export async function fetchManualVersionContent(manualId, versionId) {
  const res = await fetch(`/api/manuals/${manualId}/versions/${versionId}/content`, { headers: authHeaders() })
  return res.json()
}

export async function fetchUploadJobStatus(jobId) {
  const res = await fetch(`/api/manuals/jobs/${jobId}`, { headers: authHeaders() })
  const data = await res.json()
  if (!res.ok) throw new Error(data.detail || '진행 상태를 가져오지 못했습니다.')
  return data
}

export async function createChatRoom(engine) {
  const res = await fetch('/api/chat/rooms', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', ...authHeaders() },
    body: JSON.stringify({ engine: engine || 'langchain' }),
  })
  return res.json()
}

export async function listChatRooms() {
  const res = await fetch('/api/chat/rooms', { headers: authHeaders() })
  return res.json()
}

export async function deleteChatRoom(roomId) {
  const res = await fetch(`/api/chat/rooms/${roomId}`, {
    method: 'DELETE',
    headers: authHeaders(),
  })
  return res.json()
}

export async function listRoomMessages(roomId) {
  const res = await fetch(`/api/chat/rooms/${roomId}/messages`, { headers: authHeaders() })
  return res.json()
}

export async function sendRoomMessage(roomId, message) {
  const res = await fetch(`/api/chat/rooms/${roomId}/messages`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', ...authHeaders() },
    body: JSON.stringify({ input_message: message }),
  })
  return res.json()
}
