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
  const data = await res.json()
  if (!res.ok) throw new Error(data.detail || '메시지를 전송하지 못했습니다.')
  return data
}

async function readResponse(res, fallbackMessage) {
  const raw = await res.text()
  let data = {}
  if (raw) {
    try {
      data = JSON.parse(raw)
    } catch {
      if (!res.ok) throw new Error(`${fallbackMessage} (서버 응답 ${res.status})`)
      throw new Error('서버가 올바른 JSON 형식으로 응답하지 않았습니다.')
    }
  }
  if (!res.ok) throw new Error(data.detail || fallbackMessage)
  return data
}

export async function checkpointChatRoom(roomId) {
  const res = await fetch(`/api/chat/rooms/${roomId}/checkpoint`, {
    method: 'POST',
    headers: authHeaders(),
  })
  const data = await res.json()
  if (!res.ok) throw new Error(data.detail || '대화를 FAQ 체크포인트로 정리하지 못했습니다.')
  return data
}

export async function checkpointStaleRooms() {
  const res = await fetch('/api/chat/checkpoints/stale', {
    method: 'POST',
    headers: authHeaders(),
  })
  const data = await res.json()
  if (!res.ok) throw new Error(data.detail || '이전 대화 복구 점검에 실패했습니다.')
  return data
}

export async function checkpointAllRooms() {
  const res = await fetch('/api/chat/checkpoints/all', {
    method: 'POST',
    headers: authHeaders(),
  })
  const data = await res.json()
  if (!res.ok) throw new Error(data.detail || '로그아웃 전 대화 정리에 실패했습니다.')
  return data
}

export async function listFaqs(status = 'pending', query = '') {
  const params = new URLSearchParams({ status, query })
  const res = await fetch(`/api/faqs?${params.toString()}`, { headers: authHeaders() })
  return readResponse(res, 'FAQ 목록을 가져오지 못했습니다.')
}

export async function getFaq(faqId) {
  const res = await fetch(`/api/faqs/${faqId}`, { headers: authHeaders() })
  return readResponse(res, 'FAQ 상세를 가져오지 못했습니다.')
}

export async function approveFaq(faqId, payload) {
  const res = await fetch(`/api/faqs/${faqId}/approve`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', ...authHeaders() },
    body: JSON.stringify(payload),
  })
  return readResponse(res, 'FAQ를 승인하지 못했습니다.')
}

export async function rejectFaq(faqId) {
  const res = await fetch(`/api/faqs/${faqId}/reject`, {
    method: 'POST',
    headers: authHeaders(),
  })
  return readResponse(res, 'FAQ를 반려하지 못했습니다.')
}
