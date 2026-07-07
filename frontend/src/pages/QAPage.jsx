import { useEffect, useState } from 'react'
import { createChatRoom, deleteChatRoom, listChatRooms } from '../api'
import ChatPanel from '../components/ChatPanel'

export default function QAPage() {
  const [engine, setEngine] = useState('langchain')
  const [rooms, setRooms] = useState([])
  const [selectedRoomId, setSelectedRoomId] = useState(null)

  useEffect(() => {
    listChatRooms().then(setRooms)
  }, [])

  async function handleNewChat() {
    const room = await createChatRoom(engine)
    setRooms((prev) => [room, ...prev])
    setSelectedRoomId(room.id)
  }

  async function handleDeleteRoom(e, roomId) {
    e.stopPropagation()
    if (!window.confirm('이 채팅방을 삭제할까요?')) return
    await deleteChatRoom(roomId)
    setRooms((prev) => prev.filter((r) => r.id !== roomId))
    if (selectedRoomId === roomId) setSelectedRoomId(null)
  }

  const engineSelector = (
    <div className="qa-engine-select">
      <label htmlFor="engine-select">엔진</label>
      <select id="engine-select" value={engine} onChange={(e) => setEngine(e.target.value)}>
        <option value="langchain">LangChain</option>
        <option value="langgraph">LangGraph</option>
        <option value="dify">Dify</option>
      </select>
    </div>
  )

  return (
    <main className="qa-layout">
      <aside className="qa-sidebar">
        {engineSelector}
        <button type="button" className="btn btn--primary qa-sidebar__new" onClick={handleNewChat}>
          + 새 대화
        </button>
        <div className="qa-room-list">
          {rooms.length === 0 && <div className="qa-room-list__empty">대화 기록이 없습니다</div>}
          {rooms.map((room) => (
            <div
              key={room.id}
              role="button"
              tabIndex={0}
              className={`qa-room-item${room.id === selectedRoomId ? ' qa-room-item--active' : ''}`}
              onClick={() => setSelectedRoomId(room.id)}
            >
              <div className="qa-room-item__main">
                <span className="qa-room-item__title">{room.title}</span>
                <span className="qa-room-item__engine">{room.engine}</span>
              </div>
              <button
                type="button"
                className="qa-room-item__delete"
                title="삭제"
                onClick={(e) => handleDeleteRoom(e, room.id)}
              >
                ✕
              </button>
            </div>
          ))}
        </div>
      </aside>

      <ChatPanel roomId={selectedRoomId} />
    </main>
  )
}
