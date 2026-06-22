import { useRef, useState } from 'react'
import { askQuestion } from '../api'

export default function ChatPanel({ selectedManualTitle, selectedManualId, manualSelector }) {
  const [messages, setMessages] = useState([])
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const chatBoxRef = useRef(null)

  function scrollToBottom() {
    requestAnimationFrame(() => {
      if (chatBoxRef.current) chatBoxRef.current.scrollTop = chatBoxRef.current.scrollHeight
    })
  }

  async function handleSend() {
    const text = input.trim()
    if (!text) return

    setMessages((prev) => [...prev, { role: 'user', text }])
    setInput('')
    setLoading(true)
    scrollToBottom()

    try {
      const data = await askQuestion(text, selectedManualId)
      setMessages((prev) => [...prev, { role: 'ai', text: data.output_message }])
    } catch {
      setMessages((prev) => [...prev, { role: 'ai', text: '통신 에러가 발생했습니다.' }])
    } finally {
      setLoading(false)
      scrollToBottom()
    }
  }

  function handleKeyPress(e) {
    if (e.key === 'Enter') handleSend()
  }

  return (
    <section className="panel">
      <h3 className="panel__title">매뉴얼 Q&A</h3>
      {manualSelector}
      <div className="scope-label">
        {selectedManualTitle ? `"${selectedManualTitle}" 매뉴얼을 대상으로 질문합니다` : '전체 매뉴얼을 대상으로 질문합니다'}
      </div>

      <div className="chat-box" ref={chatBoxRef}>
        {messages.map((m, i) => (
          <div key={i} className={`chat-msg chat-msg--${m.role}`}>
            <span>{m.text}</span>
          </div>
        ))}
        {loading && (
          <div className="chat-msg chat-msg--ai">
            <span>생각 중...</span>
          </div>
        )}
      </div>

      <div className="chat-input-area">
        <input
          type="text"
          placeholder="질문을 입력하세요"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyPress={handleKeyPress}
        />
        <button type="button" className="btn btn--primary" onClick={handleSend}>전송</button>
      </div>
    </section>
  )
}
