import { useState } from 'react'
import Header from './components/Header'
import ManualList from './components/ManualList'
import ChatPanel from './components/ChatPanel'
import './App.css'

function App() {
  const [selectedManualId, setSelectedManualId] = useState(null)
  const [selectedManualTitle, setSelectedManualTitle] = useState(null)

  function handleSelectManual(id, title) {
    if (selectedManualId === id) {
      setSelectedManualId(null)
      setSelectedManualTitle(null)
    } else {
      setSelectedManualId(id)
      setSelectedManualTitle(title)
    }
  }

  return (
    <>
      <Header />
      <main className="app-layout">
        <ManualList selectedManualId={selectedManualId} onSelectManual={handleSelectManual} />
        <ChatPanel selectedManualId={selectedManualId} selectedManualTitle={selectedManualTitle} />
      </main>
    </>
  )
}

export default App
