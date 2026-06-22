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

export async function askQuestion(message, manualId) {
  const body = { input_message: message }
  if (manualId) body.manual_id = manualId
  const res = await fetch('/api/chat', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', ...authHeaders() },
    body: JSON.stringify(body),
  })
  return res.json()
}
