import { useRef, useState } from 'react'
import { createManual } from '../api'

export default function ManualUploadForm({ onCreated }) {
  const [title, setTitle] = useState('')
  const [status, setStatus] = useState('')
  const fileInputRef = useRef(null)

  async function handleSubmit(e) {
    e.preventDefault()
    const file = fileInputRef.current.files[0]
    if (!title.trim() || !file) {
      setStatus('제목과 파일을 모두 입력해 주세요.')
      return
    }

    setStatus('업로드 및 인덱싱 중입니다...')
    try {
      await createManual(title.trim(), file)
      setStatus('등록이 완료되었습니다.')
      setTitle('')
      fileInputRef.current.value = ''
      onCreated()
    } catch (err) {
      setStatus(`오류: ${err.message}`)
    }
  }

  return (
    <form className="upload-form" onSubmit={handleSubmit}>
      <h3 className="panel__title">매뉴얼 등록</h3>
      <input
        type="text"
        placeholder="매뉴얼 제목"
        value={title}
        onChange={(e) => setTitle(e.target.value)}
      />
      <input type="file" accept="application/pdf" ref={fileInputRef} />
      <button type="submit" className="btn btn--primary">등록</button>
      {status && <div className="status-text">{status}</div>}
    </form>
  )
}
