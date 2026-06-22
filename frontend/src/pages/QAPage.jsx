import { useEffect, useState } from 'react'
import { fetchManuals } from '../api'
import ChatPanel from '../components/ChatPanel'

export default function QAPage() {
  const [manuals, setManuals] = useState([])
  const [selectedManualId, setSelectedManualId] = useState('')

  useEffect(() => {
    fetchManuals().then(setManuals)
  }, [])

  const selectedManual = manuals.find((m) => m.id === Number(selectedManualId))

  const manualSelector = (
    <div className="qa-scope-select">
      <label htmlFor="manual-select">질문 대상 매뉴얼</label>
      <select
        id="manual-select"
        value={selectedManualId}
        onChange={(e) => setSelectedManualId(e.target.value)}
      >
        <option value="">전체 매뉴얼</option>
        {manuals.map((m) => (
          <option key={m.id} value={m.id}>{m.title}</option>
        ))}
      </select>
    </div>
  )

  return (
    <main className="page-layout">
      <ChatPanel
        manualSelector={manualSelector}
        selectedManualId={selectedManualId ? Number(selectedManualId) : null}
        selectedManualTitle={selectedManual ? selectedManual.title : null}
      />
    </main>
  )
}
