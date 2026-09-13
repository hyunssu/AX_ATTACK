import { useEffect, useRef, useState } from 'react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { checkpointChatRoom, listRoomMessages, sendRoomMessage } from '../api'
import ChatTracePopover from './ChatTraceModal'

const INACTIVITY_CHECKPOINT_MS = 30 * 60 * 1000

function formatSourceDate(value) {
  if (!value) return '-'
  return new Intl.DateTimeFormat('ko-KR', {
    year: 'numeric', month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit',
  }).format(new Date(value))
}

export default function ChatPanel({ roomId }) {
  const [messages, setMessages] = useState([])
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const [showOtherInput, setShowOtherInput] = useState(false)
  const [otherInput, setOtherInput] = useState('')
  const chatBoxRef = useRef(null)

  useEffect(() => {
    setShowOtherInput(false)
    setOtherInput('')
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

  useEffect(() => {
    if (!roomId || loading || lastMessage?.role !== 'ai') return undefined

    const timerId = window.setTimeout(() => {
      checkpointChatRoom(roomId).catch(() => {})
    }, INACTIVITY_CHECKPOINT_MS)

    return () => window.clearTimeout(timerId)
  }, [roomId, loading, lastMessage?.chat_id, lastMessage?.role])

  useEffect(() => {
    if (!roomId) return undefined
    const timerId = window.setInterval(() => {
      if (loading) return
      listRoomMessages(roomId)
        .then((data) => {
          setMessages((current) => (data.length !== current.length ? data : current))
        })
        .catch(() => {})
    }, 15000)
    return () => window.clearInterval(timerId)
  }, [roomId, loading])

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
    } catch (err) {
      setMessages((prev) => [...prev, { role: 'ai', text: err.message || '통신 에러가 발생했습니다.', type: 'answer', options: [] }])
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
      <div className="chat-panel__header">
        <h3 className="panel__title">매뉴얼·담당자 Q&amp;A</h3>
      </div>

      <div className="chat-box-wrap">
        <div className="chat-box" ref={chatBoxRef}>
          {!roomId && <div className="chat-empty">왼쪽에서 채팅방을 선택하거나 새 대화를 시작하세요</div>}
          {messages.map((m, i) => (
            <div key={i} className={`chat-msg chat-msg--${m.role}`}>
              <div className="chat-msg__col">
                {m.role === 'ai' && m.trace && (
                  <div className="chat-trace-hover">
                    <button type="button" className="chat-trace-toggle" aria-describedby={`chat-trace-${i}`}>
                      답변 과정 보기
                    </button>
                    <ChatTracePopover trace={m.trace} id={`chat-trace-${i}`} />
                  </div>
                )}
                <div className="chat-msg__bubble">
                  {m.role === 'ai' ? <ReactMarkdown remarkPlugins={[remarkGfm]}>{m.text}</ReactMarkdown> : m.text}
                </div>
                {m.role === 'ai' && m.sources?.length > 0 && (
                  <div className="chat-sources">
                    <div className="chat-sources__title">답변 근거</div>
                    {m.sources.map((source, sourceIndex) => (
                      <div key={`${source.type}-${source.id}-${sourceIndex}`} className="chat-source-item">
                        <div>
                          <strong>{source.title}</strong>
                          {source.detail && <span>{source.detail}</span>}
                        </div>
                        <div className="chat-source-item__dates">
                          <time>{source.date_label || '근거 생성일'} {formatSourceDate(source.created_at)}</time>
                          {source.basis_date && source.basis_date !== source.created_at && (
                            <time>{source.basis_date_label || '비교 기준일'} {formatSourceDate(source.basis_date)}</time>
                          )}
                          {source.approved_at && <time>FAQ 승인일 {formatSourceDate(source.approved_at)}</time>}
                        </div>
                      </div>
                    ))}
                  </div>
                )}
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
                  내용수정
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
          placeholder="예: 화면번호 1492 담당자는 누구야?"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyPress={handleKeyPress}
          disabled={!roomId}
        />
        <button type="button" className="btn btn--primary" onClick={handleSend} disabled={!roomId}>전송</button>
      </div>

    </section>
  )
}
