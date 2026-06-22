import { useState } from 'react'
import ManualList from '../components/ManualList'

export default function ManualsPage() {
  const [selectedManualId, setSelectedManualId] = useState(null)

  function handleSelectManual(id) {
    setSelectedManualId((current) => (current === id ? null : id))
  }

  return (
    <main className="page-layout">
      <ManualList selectedManualId={selectedManualId} onSelectManual={handleSelectManual} />
    </main>
  )
}
