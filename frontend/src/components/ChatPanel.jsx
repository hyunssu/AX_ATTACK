import { useEffect, useRef, useState } from 'react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { listRoomMessages, sendRoomMessage } from '../api'
import ChatTraceModal from './ChatTraceModal'

export default function ChatPanel({ roomId }) {
  const [messages, setMessages] = useState([])
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const [showOtherInput, setShowOtherInput] = useState(false)
  const [otherInput, setOtherInput] = useState('')
  const [openTraceIndex, setOpenTraceIndex] = useState(null)
  const chatBoxRef = useRef(null)

  useEffect(() => {
    setShowOtherInput(false)
    setOtherInput('')
    setOpenTraceIndex(null)
    if (!roomId) {
      setMessages([])
      return
    }
    listRoomMessages(roomId).then((data) => {
      setMessages(data)
      scrollToBottom()
    })
  }, [roomId])

  function scrollToBottom() {
    requestAnimationFrame(() => {
      if (chatBoxRef.current) chatBoxRef.current.scrollTop = chatBoxRef.current.scrollHeight
    })
  }

  const lastMessage = messages[messages.length - 1]
  const rawOptions = lastMessage?.role === 'ai' && lastMessage.type === 'clarify' ? lastMessage.options : []
  const pendingOptions = rawOptions.filter((opt) => !opt.includes('기타'))

  async function sendMessage(text) {
    if (!text || loading || !roomId) return

    setMessages((prev) => [...prev, { role: 'user', text }])
    setShowOtherInput(false)
    setOtherInput('')
    setInput('')
    setLoading(true)
    scrollToBottom()

    try {
      const aiMessage = await sendRoomMessage(roomId, text)
      setMessages((prev) => [...prev, aiMessage])
    } catch {
      setMessages((prev) => [...prev, { role: 'ai', text: '통신 에러가 발생했습니다.', type: 'answer', options: [] }])
    } finally {
      setLoading(false)
      scrollToBottom()
    }
  }

  function handleSend() {
    sendMessage(input.trim())
  }

  function handleOtherSend() {
    sendMessage(otherInput.trim())
  }

  function handleKeyPress(e) {
    if (e.key === 'Enter') handleSend()
  }

  function handleOtherKeyPress(e) {
    if (e.key === 'Enter') handleOtherSend()
  }

  return (
    <section className="panel chat-panel">
      <h3 className="panel__title">매뉴얼 Q&A</h3>

      <div className="chat-box-wrap">
        <div className="chat-box" ref={chatBoxRef}>
          {!roomId && <div className="chat-empty">왼쪽에서 채팅방을 선택하거나 새 대화를 시작하세요</div>}
          {messages.map((m, i) => (
            <div key={i} className={`chat-msg chat-msg--${m.role}`}>
              <div className="chat-msg__col">
                {m.role === 'ai' && m.trace && (
                  <button
                    type="button"
                    className="chat-trace-toggle"
                    onClick={() => setOpenTraceIndex(i)}
                  >
                    답변 과정 보기
                  </button>
                )}
                <div className="chat-msg__bubble">
                  {m.role === 'ai' ? <ReactMarkdown remarkPlugins={[remarkGfm]}>{m.text}</ReactMarkdown> : m.text}
                </div>
              </div>
            </div>
          ))}
          {loading && (
            <div className="chat-msg chat-msg--ai">
              <div className="chat-msg__bubble">생각 중...</div>
            </div>
          )}
        </div>

        {pendingOptions.length > 0 && !loading && (
          <div className="clarify-options clarify-options--overlay">
            {!showOtherInput ? (
              <>
                {pendingOptions.map((opt, j) => (
                  <button
                    key={j}
                    type="button"
                    className="btn btn--option"
                    onClick={() => sendMessage(opt)}
                  >
                    {opt}
                  </button>
                ))}
                <button type="button" className="btn btn--option" onClick={() => setShowOtherInput(true)}>
                  기타
                </button>
              </>
            ) : (
              <div className="clarify-other-input">
                <button type="button" className="btn btn--ghost clarify-back" onClick={() => setShowOtherInput(false)}>
                  ← 뒤로
                </button>
                <input
                  type="text"
                  autoFocus
                  placeholder="직접 입력하세요"
                  value={otherInput}
                  onChange={(e) => setOtherInput(e.target.value)}
                  onKeyPress={handleOtherKeyPress}
                />
                <button type="button" className="btn btn--primary" onClick={handleOtherSend}>전송</button>
              </div>
            )}
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
          disabled={!roomId}
        />
        <button type="button" className="btn btn--primary" onClick={handleSend} disabled={!roomId}>전송</button>
      </div>

      {openTraceIndex !== null && messages[openTraceIndex]?.trace && (
        <ChatTraceModal trace={messages[openTraceIndex].trace} onClose={() => setOpenTraceIndex(null)} />
      )}
    </section>
  )
}
