export async function fetchManuals() {
  const res = await fetch('/api/manuals')
  return res.json()
}

export async function fetchVersions(manualId) {
  const res = await fetch(`/api/manuals/${manualId}/versions`)
  return res.json()
}

export async function createManual(title, file) {
  const formData = new FormData()
  formData.append('file', file)
  const res = await fetch(`/api/manuals?title=${encodeURIComponent(title)}`, {
    method: 'POST',
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
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
  return res.json()
}
