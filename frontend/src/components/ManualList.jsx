import { useEffect, useState, useCallback } from 'react'
import { fetchManuals, fetchVersions } from '../api'
import ManualItem from './ManualItem'
import ManualUploadForm from './ManualUploadForm'

export default function ManualList({ selectedManualId, onSelectManual }) {
  const [manuals, setManuals] = useState([])
  const [versionsByManual, setVersionsByManual] = useState({})

  const loadManuals = useCallback(async () => {
    const list = await fetchManuals()
    setManuals(list)

    const entries = await Promise.all(
      list.map(async (m) => [m.id, await fetchVersions(m.id)])
    )
    setVersionsByManual(Object.fromEntries(entries))
  }, [])

  useEffect(() => {
    loadManuals()
  }, [loadManuals])

  return (
    <section className="panel">
      <ManualUploadForm onCreated={loadManuals} />

      <h3 className="panel__title">매뉴얼 목록</h3>
      <div className="manual-list">
        {manuals.length === 0 && <p className="status-text">등록된 매뉴얼이 없습니다.</p>}
        {manuals.map((manual) => (
          <ManualItem
            key={manual.id}
            manual={manual}
            versions={versionsByManual[manual.id] || []}
            selected={selectedManualId === manual.id}
            onSelect={onSelectManual}
            onVersionAdded={loadManuals}
          />
        ))}
      </div>
    </section>
  )
}
