import { useRef, useState } from 'react'
import { analyzeManualSections, confirmManualSections } from '../api'
import ManualSectionReviewModal from './ManualSectionReviewModal'

export default function ManualUploadForm({ onCreated }) {
  const [hasFile, setHasFile] = useState(false)
  const [langC, setLangC] = useState('ko')
  const [status, setStatus] = useState('')
  const [analyzing, setAnalyzing] = useState(false)
  const [confirming, setConfirming] = useState(false)
  const [confirmError, setConfirmError] = useState('')
  const [analysis, setAnalysis] = useState(null)
  const [sections, setSections] = useState([])
  const [reviewing, setReviewing] = useState(false)
  const fileInputRef = useRef(null)

  function handleFileChange() {
    setStatus('')
    setAnalysis(null)
    setSections([])
    setHasFile(Boolean(fileInputRef.current.files[0]))
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
      const result = await confirmManualSections(analysis, sections, langC, false)
      setReviewing(false)
      setStatus(`${result.results.length}건이 매뉴얼에 추가되었습니다.`)
      setAnalysis(null)
      setSections([])
      setHasFile(false)
      fileInputRef.current.value = ''
      onCreated()
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

  return (
    <div className="upload-form">
      <div className="form-field">
        <label htmlFor="manual-file">파일 (Markdown)</label>
        <input
          id="manual-file"
          type="file"
          accept=".md,text/markdown"
          ref={fileInputRef}
          onChange={handleFileChange}
        />
      </div>
      <div className="upload-form__options">
        <div className="form-field">
          <label>언어</label>
          <div className="radio-group">
            <label>
              <input type="radio" name="lang_c" value="ko" checked={langC === 'ko'} onChange={() => setLangC('ko')} />
              한국어
            </label>
            <label>
              <input type="radio" name="lang_c" value="en" checked={langC === 'en'} onChange={() => setLangC('en')} />
              English
            </label>
          </div>
        </div>
      </div>
      <div className="upload-form__actions">
        <button type="button" className="btn btn--primary" onClick={handleAnalyze} disabled={!hasFile || analyzing}>
          분석하기
        </button>
      </div>
      {status && <div className="status-text">{status}</div>}

      {analyzing && (
        <div className="upload-analyzing-overlay">
          <div className="upload-analyzing-spinner" />
          <span className="upload-analyzing-text">파일을 분석하는 중입니다...</span>
        </div>
      )}

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
    </div>
  )
}
