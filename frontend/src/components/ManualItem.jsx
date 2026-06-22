import { useRef } from 'react'
import { addManualVersion } from '../api'

export default function ManualItem({ manual, versions, selected, onSelect, onVersionAdded }) {
  const fileInputRef = useRef(null)

  async function handleAddVersion(e) {
    e.stopPropagation()
    fileInputRef.current.click()
  }

  async function handleFileChange(e) {
    const file = e.target.files[0]
    if (!file) return
    await addManualVersion(manual.id, file)
    e.target.value = ''
    onVersionAdded()
  }

  return (
    <div
      className={`manual-item${selected ? ' manual-item--selected' : ''}`}
      onClick={() => onSelect(manual.id, manual.title)}
    >
      <div className="manual-item__title">{manual.title}</div>
      <ul className="manual-item__versions">
        {versions.length === 0 && <li className="manual-item__version-empty">등록된 버전이 없습니다</li>}
        {versions.map((v) => (
          <li key={v.id}>v{v.version_no} · {v.file_name}</li>
        ))}
      </ul>
      <button type="button" className="btn btn--ghost" onClick={handleAddVersion}>버전 추가</button>
      <input
        type="file"
        accept="application/pdf"
        ref={fileInputRef}
        style={{ display: 'none' }}
        onChange={handleFileChange}
      />
    </div>
  )
}
