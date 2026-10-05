import { useEffect, useState } from 'react'
import { checkpointChatRoom, createChatRoom, deleteChatRoom, listChatRooms, renameChatRoom } from '../api'
import ChatPanel from '../components/ChatPanel'
import { useAuth } from '../auth'
import './MindMapPage.css'
import './QAPage.css'

const FAQ_ROOM_VIEW_STORAGE_KEY = 'aither.faq-room-viewed-message-ids'

function formatRoomDateTime(dateValue, timeValue) {
  const date = String(dateValue || '').trim()
  const time = String(timeValue || '').trim()
  if (!/^\d{8}$/.test(date) || !/^\d{6}$/.test(time)) return '-'
  return `${date.slice(0, 4)}/${Number(date.slice(4, 6))}/${Number(date.slice(6, 8))} ${time.slice(0, 2)}:${time.slice(2, 4)}:${time.slice(4, 6)}`
}

function loadFaqRoomViews() {
  try {
    return JSON.parse(window.localStorage.getItem(FAQ_ROOM_VIEW_STORAGE_KEY) || '{}')
  } catch {
    return {}
  }
}

export default function QAPage() {
  const { username } = useAuth()
  const favoritesKey = `aither.chat-favorites.${username}`
  const [favorites, setFavorites] = useState({})
  const [rooms, setRooms] = useState([])
  const [selectedRoomId, setSelectedRoomId] = useState(null)
  const [faqRoomViews, setFaqRoomViews] = useState(loadFaqRoomViews)
  const [error, setError] = useState('')
  const [listOpen, setListOpen] = useState(false)

  useEffect(() => {
    try {
      const saved = JSON.parse(localStorage.getItem(favoritesKey) || '{}')
      setFavorites(saved && typeof saved === 'object' && !Array.isArray(saved) ? saved : {})
    } catch {
      setFavorites({})
    }
  }, [favoritesKey])

  function toggleFavorite(event, roomId) {
    event.stopPropagation()
    setFavorites((current) => {
      const next = { ...current }
      if (next[roomId]) delete next[roomId]
      else next[roomId] = Math.max(Date.now(), ...Object.values(current).map((value) => Number(value) || 0)) + 1
      try {
        localStorage.setItem(favoritesKey, JSON.stringify(next))
      } catch {
        setError('즐겨찾기를 브라우저에 저장하지 못했습니다. 새로고침하면 설정이 사라질 수 있습니다.')
      }
      return next
    })
  }

  // 즐겨찾기끼리는 최근 지정 순서, 나머지는 기존 목록 순서를 유지한다.
  const sortedRooms = [...rooms].sort((a, b) =>
    (Number(favorites[b.room_id]) || 0) - (Number(favorites[a.room_id]) || 0))

  useEffect(() => {
    const frame = requestAnimationFrame(() => setListOpen(true))
    return () => cancelAnimationFrame(frame)
  }, [])

  useEffect(() => {
    let active = true
    const refreshRooms = () => {
      listChatRooms()
        .then((data) => {
          if (active) {
            setRooms(data)
            setError('')
          }
        })
        .catch((err) => { if (active) setError(err.message) })
    }
    refreshRooms()
    const timer = window.setInterval(refreshRooms, 10000)
    return () => {
      active = false
      window.clearInterval(timer)
    }
  }, [])

  async function handleNewChat() {
    try {
      if (selectedRoomId) {
        await checkpointChatRoom(selectedRoomId).catch(() => {})
      }
      const room = await createChatRoom()
      setRooms((prev) => [room, ...prev])
      setSelectedRoomId(room.room_id)
      setError('')
    } catch (err) {
      setError(err.message)
    }
  }

  async function handleDeleteRoom(e, roomId) {
    e.stopPropagation()
    if (!window.confirm('이 채팅방을 삭제할까요?')) return
    try {
      await checkpointChatRoom(roomId).catch(() => {})
      await deleteChatRoom(roomId)
      setRooms((prev) => prev.filter((r) => r.room_id !== roomId))
      if (selectedRoomId === roomId) setSelectedRoomId(null)
      setError('')
    } catch (err) {
      setError(err.message)
    }
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

  async function handleRenameRoom(roomId, title) {
    const updated = await renameChatRoom(roomId, title)
    setRooms((current) => current.map((room) => room.room_id === roomId ? { ...room, title: updated.title } : room))
  }

  return (
    <main className="qa-layout">
      <aside className={`qa-sidebar${listOpen ? ' qa-sidebar--open' : ''}`}>
        <div className="eyebrow">Ask chat-bot about Aither manual</div>
        <p className="qa-sidebar__intro">매뉴얼에 대해 궁금한 점을 물어보세요</p>
        <button type="button" className="btn qa-new-chat" onClick={handleNewChat}>새 대화</button>
        {error && <div className="qa-room-list__error" role="alert">{error}</div>}
        <div className="qa-room-list">
          {rooms.length === 0 && <div className="qa-room-list__empty">대화 기록이 없습니다</div>}
          {sortedRooms.map((room) => (
            <div
              key={room.room_id}
              role="button"
              tabIndex={0}
              className={`qa-room-item mm-panel-card${roomHighlightClass(room)}${room.room_id === selectedRoomId ? ' qa-room-item--active' : ''}`}
              onClick={() => handleSelectRoom(room.room_id)}
              onKeyDown={(event) => {
                if (event.target !== event.currentTarget) return
                if (event.key === 'Enter' || event.key === ' ') {
                  event.preventDefault()
                  handleSelectRoom(room.room_id)
                }
              }}
            >
              <div className="qa-room-item__main">
                <span className="qa-room-item__title">{room.title}</span>
                <span className="qa-room-item__time">{formatRoomDateTime(room.last_change_date, room.last_change_time)}</span>
              </div>
              <button
                type="button"
                className={`mm-panel-card__fav${favorites[room.room_id] ? ' mm-panel-card__fav--on' : ''}`}
                title={favorites[room.room_id] ? '즐겨찾기 해제' : '즐겨찾기'}
                aria-label={`${room.title} ${favorites[room.room_id] ? '즐겨찾기 해제' : '즐겨찾기'}`}
                aria-pressed={Boolean(favorites[room.room_id])}
                onClick={(event) => toggleFavorite(event, room.room_id)}
              >
                {favorites[room.room_id] ? '★' : '☆'}
              </button>
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

      <ChatPanel key={selectedRoomId || 'empty'} roomId={selectedRoomId} roomTitle={rooms.find((room) => room.room_id === selectedRoomId)?.title || ''} onRenameRoom={handleRenameRoom} />
    </main>
  )
}
