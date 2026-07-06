import { useEffect, useRef, useState } from 'react'
import { addManualVersion, fetchManualVersionContent, fetchVersions } from '../api'
import ManualContentViewer from './ManualContentViewer'
import ManualUploadProgressModal from './ManualUploadProgressModal'

export default function ManualDetailPanel({ manual, onVersionAdded }) {
  const fileInputRef = useRef(null)
  const [jobId, setJobId] = useState(null)
  const [error, setError] = useState('')
  const [versions, setVersions] = useState([])
  const [selectedVersionId, setSelectedVersionId] = useState(null)
  const [chunks, setChunks] = useState([])

  const activeVersionId = selectedVersionId ?? (versions.length > 0 ? versions[0].id : null)

  useEffect(() => {
    if (!manual) return undefined
    let cancelled = false
    fetchVersions(manual.id).then((data) => {
      if (!cancelled) setVersions(data)
    })
    return () => {
      cancelled = true
    }
  }, [manual])

  useEffect(() => {
    if (!manual || !activeVersionId) return undefined
    let cancelled = false
    fetchManualVersionContent(manual.id, activeVersionId).then((data) => {
      if (!cancelled) setChunks(data.chunks)
    })
    return () => {
      cancelled = true
    }
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
      const result = await addManualVersion(manual.id, file)
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

  if (!manual) {
    return (
      <section className="manuals-detail panel">
        <div className="manuals-detail__empty">왼쪽에서 매뉴얼을 선택하세요</div>
      </section>
    )
  }

  return (
    <section className="manuals-detail panel">
      <div className="manuals-detail__header">
        <h3 className="panel__title">{manual.title}</h3>
        <button type="button" className="btn btn--ghost" onClick={handleAddVersion}>버전 추가</button>
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
            v{v.version_no} · {v.file_name}
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
