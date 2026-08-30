import { useEffect, useRef, useState } from 'react'
import { analyzeManualSections, confirmManualSections } from '../api'
import ManualMultiJobProgressModal from './ManualMultiJobProgressModal'
import ManualSectionReviewModal from './ManualSectionReviewModal'

export default function ManualUploadForm({ onCreated }) {
  const [hasFile, setHasFile] = useState(false)
  const [status, setStatus] = useState('')
  const [analyzing, setAnalyzing] = useState(false)
  const [confirming, setConfirming] = useState(false)
  const [confirmError, setConfirmError] = useState('')
  const [analysis, setAnalysis] = useState(null)
  const [sections, setSections] = useState([])
  const [reviewing, setReviewing] = useState(false)
  const [jobs, setJobs] = useState(null)
  const fileInputRef = useRef(null)
  const previewUrlRef = useRef(null)

  useEffect(() => {
    return () => {
      if (previewUrlRef.current) URL.revokeObjectURL(previewUrlRef.current)
    }
  }, [])

  function revokePreview() {
    if (previewUrlRef.current) {
      URL.revokeObjectURL(previewUrlRef.current)
      previewUrlRef.current = null
    }
  }

  function handleFileChange() {
    setStatus('')
    setAnalysis(null)
    setSections([])
    revokePreview()

    const file = fileInputRef.current.files[0]
    setHasFile(Boolean(file))
    if (file) previewUrlRef.current = URL.createObjectURL(file)
  }

  function handleViewOriginal() {
    if (previewUrlRef.current) window.open(previewUrlRef.current, '_blank')
  }

  async function handleAnalyze() {
    const file = fileInputRef.current.files[0]
    if (!file) {
      setStatus('파일을 먼저 선택해 주세요.')
      return
    }

    setAnalyzing(true)
    setStatus('')
    try {
      const result = await analyzeManualSections(file)
      setAnalysis(result)
      setSections(result.sections.map((section) => ({ ...section, include: true })))
      setReviewing(true)
    } catch (err) {
      setStatus(`오류: ${err.message}`)
    } finally {
      setAnalyzing(false)
    }
  }

  async function handleConfirm() {
    if (!analysis) return
    setConfirming(true)
    setConfirmError('')
    try {
      const result = await confirmManualSections(analysis.source_document_id, sections)
      setReviewing(false)
      setJobs(result.results)
    } catch (err) {
      setConfirmError(`오류: ${err.message}`)
    } finally {
      setConfirming(false)
    }
  }

  function handleCancelReview() {
    setReviewing(false)
    setConfirmError('')
    setAnalysis(null)
    setSections([])
  }

  function handleDone() {
    setJobs(null)
    setAnalysis(null)
    setSections([])
    setHasFile(false)
    fileInputRef.current.value = ''
    revokePreview()
    setStatus('등록이 완료되었습니다.')
    onCreated()
  }

  function handleClose() {
    setJobs(null)
    onCreated()
  }

  return (
    <div className="upload-form">
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
      <div className="upload-form__actions">
        <button type="button" className="btn btn--ghost" onClick={handleViewOriginal} disabled={!hasFile}>
          원문 보기
        </button>
        <button type="button" className="btn btn--primary" onClick={handleAnalyze} disabled={!hasFile || analyzing}>
          {analyzing ? '분석 중…' : '분석하기'}
        </button>
      </div>
      {status && <div className="status-text">{status}</div>}
      {reviewing && (
        <ManualSectionReviewModal
          sections={sections}
          onChange={setSections}
          onConfirm={handleConfirm}
          onCancel={handleCancelReview}
          confirming={confirming}
          error={confirmError}
        />
      )}
      {jobs && (
        <ManualMultiJobProgressModal jobs={jobs} onDone={handleDone} onClose={handleClose} />
      )}
    </div>
  )
}
