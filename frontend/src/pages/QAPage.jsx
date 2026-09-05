import { useEffect, useState } from 'react'
import { checkpointChatRoom, createChatRoom, deleteChatRoom, listChatRooms } from '../api'
import ChatPanel from '../components/ChatPanel'

const FAQ_ROOM_VIEW_STORAGE_KEY = 'aither.faq-room-viewed-message-ids'

function loadFaqRoomViews() {
  try {
    return JSON.parse(window.localStorage.getItem(FAQ_ROOM_VIEW_STORAGE_KEY) || '{}')
  } catch {
    return {}
  }
}

export default function QAPage() {
  const [rooms, setRooms] = useState([])
  const [selectedRoomId, setSelectedRoomId] = useState(null)
  const [faqRoomViews, setFaqRoomViews] = useState(loadFaqRoomViews)

  useEffect(() => {
    let active = true
    const refreshRooms = () => {
      listChatRooms()
        .then((data) => { if (active) setRooms(data) })
        .catch(() => {})
    }
    refreshRooms()
    const timer = window.setInterval(refreshRooms, 10000)
    return () => {
      active = false
      window.clearInterval(timer)
    }
  }, [])

  async function handleNewChat() {
    if (selectedRoomId) {
      await checkpointChatRoom(selectedRoomId).catch(() => {})
    }
    const room = await createChatRoom()
    setRooms((prev) => [room, ...prev])
    setSelectedRoomId(room.room_id)
  }

  async function handleDeleteRoom(e, roomId) {
    e.stopPropagation()
    if (!window.confirm('이 채팅방을 삭제할까요?')) return
    await checkpointChatRoom(roomId).catch(() => {})
    await deleteChatRoom(roomId)
    setRooms((prev) => prev.filter((r) => r.room_id !== roomId))
    if (selectedRoomId === roomId) setSelectedRoomId(null)
  }

  async function handleSelectRoom(roomId) {
    if (selectedRoomId && selectedRoomId !== roomId) {
      await checkpointChatRoom(selectedRoomId).catch(() => {})
    }
    const selectedRoom = rooms.find((room) => room.room_id === roomId)
    if (selectedRoom?.latest_faq_agent_chat_id) {
      setFaqRoomViews((current) => {
        const next = {
          ...current,
          [roomId]: selectedRoom.latest_faq_agent_chat_id,
        }
        try {
          window.localStorage.setItem(FAQ_ROOM_VIEW_STORAGE_KEY, JSON.stringify(next))
        } catch {
          // 저장소 사용이 제한된 브라우저에서도 채팅방 열기는 계속 진행한다.
        }
        return next
      })
    }
    setSelectedRoomId(roomId)
  }

  function roomHighlightClass(room) {
    const latestMessageId = Number(room.latest_faq_agent_chat_id || 0)
    if (!latestMessageId) return ''
    const viewedMessageId = Number(faqRoomViews[room.room_id] || 0)
    return viewedMessageId >= latestMessageId
      ? ' qa-room-item--faq-viewed'
      : ' qa-room-item--faq-update'
  }

  return (
    <main className="qa-layout">
      <aside className="qa-sidebar">
        <div className="eyebrow">Q&amp;A</div>
        <p className="qa-sidebar__intro">매뉴얼에 대해 궁금한 점을 물어보세요</p>
        <button type="button" className="btn btn--primary qa-sidebar__new" onClick={handleNewChat}>
          + 새 대화
        </button>
        <div className="qa-room-list">
          {rooms.length === 0 && <div className="qa-room-list__empty">대화 기록이 없습니다</div>}
          {rooms.map((room) => (
            <div
              key={room.room_id}
              role="button"
              tabIndex={0}
              className={`qa-room-item${roomHighlightClass(room)}${room.room_id === selectedRoomId ? ' qa-room-item--active' : ''}`}
              onClick={() => handleSelectRoom(room.room_id)}
            >
              <div className="qa-room-item__main">
                <span className="qa-room-item__title">{room.title}</span>
                <span className="qa-room-item__time">{room.last_change_date} {room.last_change_time}</span>
              </div>
              <button
                type="button"
                className="qa-room-item__delete"
                title="삭제"
                onClick={(e) => handleDeleteRoom(e, room.room_id)}
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
