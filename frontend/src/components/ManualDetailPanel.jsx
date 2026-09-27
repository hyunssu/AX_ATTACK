import { useEffect, useRef, useState } from 'react'
import { addManualVersion, deployManualDraft, fetchManualVersionContent, fetchVersions } from '../api'
import ManualContentViewer from './ManualContentViewer'
import ManualUploadProgressModal from './ManualUploadProgressModal'

const STEP_LABEL = {
  draft: '초안',
  converting: '변환 중',
  chunking: '청킹 중',
  embedding: '임베딩 중',
  done: '배포됨',
  error: '오류',
}

function StepBadge({ step }) {
  if (!step) return null
  const label = STEP_LABEL[step] ?? step
  const mod = step === 'done' ? 'done' : step === 'draft' ? 'draft' : step === 'error' ? 'error' : 'indexing'
  return <span className={`step-badge step-badge--${mod}`}>{label}</span>
}

export default function ManualDetailPanel({ manual, onVersionAdded }) {
  const fileInputRef = useRef(null)
  const [deployFile, setDeployFile] = useState(true)
  const [jobId, setJobId] = useState(null)
  const [error, setError] = useState('')
  const [versions, setVersions] = useState([])
  const [selectedVersionId, setSelectedVersionId] = useState(null)
  const [chunks, setChunks] = useState([])

  const activeVersionId = selectedVersionId ?? (versions.length > 0 ? versions[0].id : null)

  // 최신 draft 버전 (배포 버튼 표시 대상)
  const latestDraftVersion = versions.find(
    (v) => v.index_step === 'draft' && v.id === versions[0]?.id
  ) ?? null

  useEffect(() => {
    if (!manual) return undefined
    let cancelled = false
    fetchVersions(manual.id).then((data) => {
      if (!cancelled) setVersions(data)
    })
    return () => { cancelled = true }
  }, [manual])

  useEffect(() => {
    if (!manual || !activeVersionId) return undefined
    let cancelled = false
    fetchManualVersionContent(manual.id, activeVersionId).then((data) => {
      if (!cancelled) setChunks(data.chunks)
    })
    return () => { cancelled = true }
  }, [manual, activeVersionId])

  function handleAddVersion() {
    fileInputRef.current.click()
  }

  async function handleFileChange(e) {
    const file = e.target.files[0]
    if (!file) return
    e.target.value = ''
    setError('')
    try {
      const result = await addManualVersion(manual.id, file, deployFile)
      if (result.job_id) {
        setJobId(result.job_id)
      } else {
        refreshVersions()
      }
    } catch (err) {
      setError(`오류: ${err.message}`)
    }
  }

  async function handleDeployDraft() {
    setError('')
    try {
      const result = await deployManualDraft(manual.id)
      setJobId(result.job_id)
    } catch (err) {
      setError(`오류: ${err.message}`)
    }
  }

  function refreshVersions() {
    setSelectedVersionId(null)
    fetchVersions(manual.id).then(setVersions)
    onVersionAdded()
  }

  function handleDone() {
    setJobId(null)
    refreshVersions()
  }

  function handleClose() {
    setJobId(null)
    refreshVersions()
  }

  return (
    <section className="manual-detail">
      <div className="manuals-detail__header">
        <div>
          <div className="eyebrow">DOCUMENT DETAIL</div>
          <h1 className="hero__title hero__title--sm">{manual.title}</h1>
        </div>
        <div className="manuals-detail__actions">
          <label className="deploy-toggle">
            <input
              type="checkbox"
              checked={deployFile}
              onChange={(e) => setDeployFile(e.target.checked)}
            />
            바로 배포
          </label>
          <button type="button" className="btn btn--ghost" onClick={handleAddVersion}>버전 추가</button>
          {latestDraftVersion && (
            <button type="button" className="btn btn--primary" onClick={handleDeployDraft}>
              초안 배포
            </button>
          )}
        </div>
        <input
          type="file"
          accept="application/pdf,.md,text/markdown"
          ref={fileInputRef}
          style={{ display: 'none' }}
          onChange={handleFileChange}
        />
      </div>
      {error && <div className="status-text">{error}</div>}
      <ul className="manual-item__versions">
        {versions.length === 0 && <li className="manual-item__version-empty">등록된 버전이 없습니다</li>}
        {versions.map((v) => (
          <li
            key={v.id}
            className={`manual-version-row${v.id === activeVersionId ? ' manual-version-row--selected' : ''}`}
            onClick={() => setSelectedVersionId(v.id)}
          >
            <span className="manual-version-row__label">v{v.version_no} · {v.file_name || '(에디터)'}</span>
            <span className="manual-version-row__meta">
              <StepBadge step={v.index_step} />
              <span className="manual-version-row__date">{v.created_at?.slice(0, 10)}</span>
            </span>
          </li>
        ))}
      </ul>
      {versions.length > 0 && <ManualContentViewer chunks={chunks} />}
      {jobId && (
        <ManualUploadProgressModal jobId={jobId} onDone={handleDone} onClose={handleClose} />
      )}
    </section>
  )
}
