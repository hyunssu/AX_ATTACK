import { useCallback, useEffect, useState } from 'react'
import { fetchManuals } from '../api'
import ManualDetailPanel from '../components/ManualDetailPanel'
import ManualList from '../components/ManualList'

export default function ManualsPage() {
  const [manuals, setManuals] = useState([])
  const [selectedManualId, setSelectedManualId] = useState(null)

  const loadManuals = useCallback(async () => {
    const list = await fetchManuals()
    setManuals(list)
  }, [])

  useEffect(() => {
    loadManuals()
  }, [loadManuals])

  function handleSelectManual(id) {
    setSelectedManualId((current) => (current === id ? null : id))
  }

  const selectedManual = manuals.find((m) => m.id === selectedManualId) || null

  return (
    <main className="manuals-layout">
      <ManualList
        manuals={manuals}
        selectedManualId={selectedManualId}
        onSelectManual={handleSelectManual}
      />
      <ManualDetailPanel
        key={selectedManual ? selectedManual.id : 'none'}
        manual={selectedManual}
        onVersionAdded={loadManuals}
      />
    </main>
  )
}
