import { useRef, useState } from 'react'
import { createManual, previewManualSections } from '../api'
import ManualSectionPreview from './ManualSectionPreview'
import ManualUploadProgressModal from './ManualUploadProgressModal'

export default function ManualUploadForm({ onCreated }) {
  const [title, setTitle] = useState('')
  const [status, setStatus] = useState('')
  const [jobId, setJobId] = useState(null)
  const [submitting, setSubmitting] = useState(false)
  const [previewing, setPreviewing] = useState(false)
  const [preview, setPreview] = useState(null)
  const fileInputRef = useRef(null)

  function handleFileChange() {
    setPreview(null)
  }

  async function handlePreview() {
    const file = fileInputRef.current.files[0]
    if (!file) {
      setStatus('파일을 먼저 선택해 주세요.')
      return
    }

    setPreviewing(true)
    setStatus('')
    setPreview(null)
    try {
      const result = await previewManualSections(file)
      setPreview(result)
    } catch (err) {
      setStatus(`오류: ${err.message}`)
    } finally {
      setPreviewing(false)
    }
  }

  async function handleSubmit(e) {
    e.preventDefault()
    const file = fileInputRef.current.files[0]
    if (!title.trim() || !file) {
      setStatus('제목과 파일을 모두 입력해 주세요.')
      return
    }

    setSubmitting(true)
    setStatus('')
    try {
      const result = await createManual(title.trim(), file)
      setTitle('')
      fileInputRef.current.value = ''
      setPreview(null)
      setJobId(result.job_id)
    } catch (err) {
      setStatus(`오류: ${err.message}`)
    } finally {
      setSubmitting(false)
    }
  }

  function handleDone() {
    setJobId(null)
    setStatus('등록이 완료되었습니다.')
    onCreated()
  }

  function handleClose() {
    setJobId(null)
    onCreated()
  }

  return (
    <form className="upload-form" onSubmit={handleSubmit}>
      <div className="form-field">
        <label htmlFor="manual-title">매뉴얼 제목</label>
        <input
          id="manual-title"
          type="text"
          placeholder="예: 인터넷뱅킹 화면정의서"
          value={title}
          onChange={(e) => setTitle(e.target.value)}
        />
      </div>
      <div className="form-field">
        <label htmlFor="manual-file">파일 (PDF 또는 Markdown)</label>
        <input
          id="manual-file"
          type="file"
          accept="application/pdf,.md,text/markdown"
          ref={fileInputRef}
          onChange={handleFileChange}
        />
      </div>
      <button type="button" className="btn btn--ghost" onClick={handlePreview} disabled={previewing}>
        {previewing ? '분석 중…' : '미리보기'}
      </button>
      {preview && <ManualSectionPreview sections={preview.sections} />}
      <button type="submit" className="btn btn--primary" disabled={submitting}>등록</button>
      {status && <div className="status-text">{status}</div>}
      {jobId && (
        <ManualUploadProgressModal jobId={jobId} onDone={handleDone} onClose={handleClose} />
      )}
    </form>
  )
}
