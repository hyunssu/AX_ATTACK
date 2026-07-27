import { useEffect, useRef, useState, useCallback } from 'react'
import { fetchManuals, quickCreateManual, listTrails, createTrail } from '../api'
import EditorPanel from '../components/EditorPanel'
import './MindMapPage.css'

const TAXONOMY = {
  '여신': { color: '#4a7fcb', light: '#daeaf9', en: 'Credit',   subs: ['심사','실행','담보','한도','연체','회수','금리','보증'] },
  '수신': { color: '#4fad8a', light: '#cceee0', en: 'Deposit',  subs: ['예금','적금','청약','이자','만기','신탁','펀드','해지'] },
  '외환': { color: '#8b72d4', light: '#e2dcf8', en: 'FX',       subs: ['환전','송금','무역금융','외화예금','파생상품','수출입','LC'] },
  '자금': { color: '#d4843f', light: '#f8e4ca', en: 'Treasury', subs: ['조달','운용','유동성','결제','콜','채권','RP','리스크'] },
  '카드': { color: '#d45e6e', light: '#f9d5d8', en: 'Card',     subs: ['발급','인증','승인','청구','결제','매출','포인트','분실'] },
  '고객': { color: '#5b9fd4', light: '#cce2f8', en: 'Customer', subs: ['신규개설','실명인증','불만처리','마케팅','CRM','휴면','해지','상속'] },
  '기타': { color: '#8a9bb0', light: '#d8dee4', en: 'Others',   subs: ['보안','컴플라이언스','내부통제','IT시스템','인사','회계','감사'] },
}
const CATS = Object.keys(TAXONOMY)

const MAP_POSITIONS = [
  { x: 520, y: 80  },
  { x: 850, y: 190 },
  { x: 880, y: 460 },
  { x: 640, y: 610 },
  { x: 320, y: 610 },
  { x: 90,  y: 460 },
  { x: 90,  y: 190 },
]
const CENTER = { x: 560, y: 370 }
const CARD_W = 160
const CARD_H = 90

export default function MindMapPage() {
  const [view, setView] = useState('card')
  const [manuals, setManuals] = useState([])
  const [loading, setLoading] = useState(true)
  const [selectedCat, setSelectedCat] = useState(null)
  const [selectedManual, setSelectedManual] = useState(null)
  const [customTrails, setCustomTrails] = useState([])

  const [transform, setTransform] = useState({ x: 0, y: 0, scale: 1 })
  const panStart = useRef(null)
  const stageRef = useRef(null)

  const refreshManuals = useCallback(() => {
    fetchManuals()
      .then(data => setManuals(Array.isArray(data) ? data : []))
      .catch(() => {})
  }, [])

  useEffect(() => {
    fetchManuals()
      .then(data => { setManuals(Array.isArray(data) ? data : []); setLoading(false) })
      .catch(() => setLoading(false))
  }, [])

  useEffect(() => {
    if (!selectedCat) { setCustomTrails([]); return }
    listTrails(selectedCat)
      .then(trails => setCustomTrails(Array.isArray(trails) ? trails : []))
      .catch(() => setCustomTrails([]))
  }, [selectedCat])

  const handleManualAdd = useCallback(async (title, subCategory) => {
    const realSub = subCategory === '기타' ? null : subCategory
    const newManual = await quickCreateManual(title, [selectedCat], realSub)
    refreshManuals()
    return newManual
  }, [selectedCat, refreshManuals])

  const handleAddTrail = useCallback(async (name) => {
    await createTrail(selectedCat, name)
    setCustomTrails(prev => prev.includes(name) ? prev : [...prev, name])
  }, [selectedCat])

  const byCategory = CATS.reduce((acc, cat) => {
    acc[cat] = manuals.filter(m => Array.isArray(m.categories) && m.categories[0] === cat)
    return acc
  }, {})

  const groupBySub = (catManuals, cat, extraTrails = []) => {
    const subs = TAXONOMY[cat].subs
    const grouped = {}
    const unsorted = []
    for (const m of catManuals) {
      const sub = m.sub_category
      if (sub && (subs.includes(sub) || extraTrails.includes(sub))) {
        if (!grouped[sub]) grouped[sub] = []
        grouped[sub].push(m)
      } else {
        unsorted.push(m)
      }
    }
    // 사전정의 subs (매뉴얼 있는 것만)
    const result = subs.filter(s => grouped[s]).map(s => ({ sub: s, items: grouped[s] }))
    // 커스텀 트레일 (빈 컬럼도 포함)
    for (const trail of extraTrails) {
      if (!subs.includes(trail)) {
        result.push({ sub: trail, items: grouped[trail] || [] })
      }
    }
    if (unsorted.length) result.push({ sub: '기타', items: unsorted })
    return result
  }

  const onMouseDown = useCallback(e => {
    if (e.button !== 0) return
    panStart.current = { mx: e.clientX, my: e.clientY, tx: transform.x, ty: transform.y }
    e.preventDefault()
  }, [transform])
  const onMouseMove = useCallback(e => {
    if (!panStart.current) return
    setTransform(t => ({ ...t, x: panStart.current.tx + e.clientX - panStart.current.mx, y: panStart.current.ty + e.clientY - panStart.current.my }))
  }, [])
  const onMouseUp = useCallback(() => { panStart.current = null }, [])
  const onWheel = useCallback(e => {
    e.preventDefault()
    setTransform(t => ({ ...t, scale: Math.min(2.5, Math.max(0.3, t.scale * (e.deltaY < 0 ? 1.1 : 0.9))) }))
  }, [])
  useEffect(() => {
    const el = stageRef.current
    if (!el) return
    el.addEventListener('wheel', onWheel, { passive: false })
    return () => el.removeEventListener('wheel', onWheel)
  }, [onWheel])

  // 패널에 표시할 카드 순서: 선택된 것 맨 위, 나머지 아래
  const panelCats = selectedCat
    ? [selectedCat, ...CATS.filter(c => c !== selectedCat)]
    : CATS

  return (
    <div className="mm-page">
      <div className="mm-toolbar">
        <span className="mm-toolbar__title">MIND MAP</span>
        <div className="mm-view-toggle">
          <button className={`mm-toggle-btn${view === 'card' ? ' active' : ''}`} onClick={() => setView('card')}>카드 뷰</button>
          <button className={`mm-toggle-btn${view === 'map' ? ' active' : ''}`} onClick={() => setView('map')}>맵 뷰</button>
        </div>
      </div>

      {loading ? (
        <div className="mm-loading">매뉴얼을 불러오는 중...</div>
      ) : (
        <div className="mm-body">

          {/* 왼쪽 패널 — 카드 클릭 시 슬라이드 인 */}
          <div className={`mm-panel${selectedCat ? ' mm-panel--open' : ''}`}>
            <button className="mm-panel__close" onClick={() => setSelectedCat(null)} title="닫기">✕</button>
            <div className="mm-panel__cards">
              {panelCats.map(cat => (
                <PanelCard
                  key={cat}
                  cat={cat}
                  count={byCategory[cat].length}
                  selected={cat === selectedCat}
                  onClick={() => setSelectedCat(cat === selectedCat ? null : cat)}
                />
              ))}
            </div>
          </div>

          {/* 메인 영역 (오른쪽) */}
          <div className="mm-main">
            {selectedCat ? (
              <TrelloBoard
                cat={selectedCat}
                sections={groupBySub(byCategory[selectedCat], selectedCat, customTrails)}
                onManualSelect={setSelectedManual}
                onAdd={handleManualAdd}
                onAddTrail={handleAddTrail}
              />
            ) : view === 'card' ? (
              <CardView byCategory={byCategory} onSelect={setSelectedCat} />
            ) : (
              <MapView
                byCategory={byCategory}
                transform={transform}
                stageRef={stageRef}
                onMouseDown={onMouseDown}
                onMouseMove={onMouseMove}
                onMouseUp={onMouseUp}
                onSelect={setSelectedCat}
              />
            )}
          </div>

          {/* 에디터 패널 (오른쪽 슬라이드) */}
          <div className={`mm-editor${selectedManual ? ' mm-editor--open' : ''}`}>
            <EditorPanel manual={selectedManual} onClose={() => setSelectedManual(null)} />
          </div>

        </div>
      )}
    </div>
  )
}

/* ── Category card (카드/맵 뷰 메인 영역용) ─────── */
function CategoryCard({ cat, count, onClick }) {
  const tax = TAXONOMY[cat]
  return (
    <div
      className="mm-cat-card"
      style={{ '--cat-color': tax.color, '--cat-light': tax.light }}
      onClick={onClick}
    >
      <div className="mm-cat-card__accent" />
      <div className="mm-cat-card__en">{tax.en}</div>
      <div className="mm-cat-card__ko">{cat}</div>
      <div className="mm-cat-card__count">{count}개 매뉴얼</div>
    </div>
  )
}

/* ── 오른쪽 패널 카드 ──────────────────────────── */
function PanelCard({ cat, count, selected, onClick }) {
  const tax = TAXONOMY[cat]
  return (
    <div
      className={`mm-panel-card${selected ? ' mm-panel-card--selected' : ''}`}
      style={{ '--cat-color': tax.color, '--cat-light': tax.light }}
      onClick={onClick}
    >
      <div className="mm-panel-card__accent" />
      <div className="mm-panel-card__body">
        <div className="mm-panel-card__en">{tax.en}</div>
        <div className="mm-panel-card__ko">{cat}</div>
        <div className="mm-panel-card__count">{count}개</div>
      </div>
    </div>
  )
}

/* ── 카드 그리드 뷰 ─────────────────────────────── */
function CardView({ byCategory, onSelect }) {
  return (
    <div className="mm-card-grid">
      {CATS.map(cat => (
        <CategoryCard key={cat} cat={cat} count={byCategory[cat].length} onClick={() => onSelect(cat)} />
      ))}
    </div>
  )
}

/* ── 맵 뷰 ──────────────────────────────────────── */
function MapView({ byCategory, transform, stageRef, onMouseDown, onMouseMove, onMouseUp, onSelect }) {
  return (
    <div
      className="mm-map-stage"
      ref={stageRef}
      onMouseDown={onMouseDown}
      onMouseMove={onMouseMove}
      onMouseUp={onMouseUp}
      onMouseLeave={onMouseUp}
    >
      <div
        className="mm-map-canvas"
        style={{ transform: `translate(${transform.x}px, ${transform.y}px) scale(${transform.scale})` }}
      >
        <svg className="mm-map-svg" viewBox="0 0 1200 800" xmlns="http://www.w3.org/2000/svg">
          {CATS.map((cat, i) => {
            const pos = MAP_POSITIONS[i]
            return (
              <line key={cat}
                x1={CENTER.x} y1={CENTER.y}
                x2={pos.x + CARD_W / 2} y2={pos.y + CARD_H / 2}
                stroke={TAXONOMY[cat].color} strokeWidth="2" strokeDasharray="6 4" opacity="0.55"
              />
            )
          })}
          <circle cx={CENTER.x} cy={CENTER.y} r="34" fill="white" stroke="#e0e0e0" strokeWidth="1.5" />
          <text x={CENTER.x} y={CENTER.y - 6} textAnchor="middle" fontSize="9" fill="#888" fontWeight="700" letterSpacing="1">MANUAL</text>
          <text x={CENTER.x} y={CENTER.y + 9} textAnchor="middle" fontSize="9" fill="#888" letterSpacing="1">MAP</text>
        </svg>
        {CATS.map((cat, i) => {
          const pos = MAP_POSITIONS[i]
          return (
            <div key={cat} className="mm-map-card-wrap" style={{ left: pos.x, top: pos.y, width: CARD_W }}>
              <CategoryCard cat={cat} count={byCategory[cat].length} onClick={() => onSelect(cat)} />
            </div>
          )
        })}
      </div>
      <div className="mm-map-hint">스크롤로 확대/축소 · 드래그로 이동</div>
    </div>
  )
}

/* ── Trello 보드 ─────────────────────────────────── */
function TrelloBoard({ cat, sections, onManualSelect, onAdd, onAddTrail }) {
  const tax = TAXONOMY[cat]
  return (
    <div className="mm-trello" style={{ '--cat-color': tax.color, '--cat-light': tax.light }}>
      <div className="mm-trello__header">
        <span className="mm-trello__en">{tax.en}</span>
        <span className="mm-trello__ko">{cat}</span>
        <span className="mm-trello__total">{sections.reduce((s, g) => s + g.items.length, 0)}개 매뉴얼</span>
      </div>
      <div className="mm-trello__board">
        {sections.length === 0 ? (
          <TrelloAddColumn color={tax.color} sub={null} onAdd={onAdd} />
        ) : (
          sections.map(({ sub, items }) => (
            <TrelloColumn key={sub} sub={sub} items={items} color={tax.color} onManualSelect={onManualSelect} onAdd={onAdd} />
          ))
        )}
        <NewTrailColumn color={tax.color} onAddTrail={onAddTrail} />
      </div>
    </div>
  )
}

function TrelloColumn({ sub, items, color, onManualSelect, onAdd }) {
  const [adding, setAdding] = useState(false)
  const [title, setTitle] = useState('')
  const inputRef = useRef(null)

  useEffect(() => { if (adding) inputRef.current?.focus() }, [adding])

  const handleSubmit = async (e) => {
    e.preventDefault()
    if (!title.trim()) return
    try { await onAdd(title.trim(), sub) } catch {}
    setTitle(''); setAdding(false)
  }

  return (
    <div className="mm-trello-col">
      <div className="mm-trello-col__header" style={{ color }}>
        <span className="mm-trello-col__name">{sub}</span>
        <span className="mm-trello-col__count">{items.length}</span>
      </div>
      <div className="mm-trello-col__cards">
        {items.map(m => (
          <TrelloCard key={m.id} manual={m} color={color} onClick={() => onManualSelect(m)} />
        ))}
      </div>
      {adding ? (
        <form className="mm-trello-add-form" onSubmit={handleSubmit}>
          <input
            ref={inputRef}
            className="mm-trello-add-input"
            value={title}
            onChange={e => setTitle(e.target.value)}
            placeholder="제목 입력..."
            onKeyDown={e => e.key === 'Escape' && (setTitle(''), setAdding(false))}
          />
          <div className="mm-trello-add-actions">
            <button type="submit" className="mm-trello-add-btn" style={{ background: color }}>추가</button>
            <button type="button" className="mm-trello-cancel-btn" onClick={() => { setTitle(''); setAdding(false) }}>✕</button>
          </div>
        </form>
      ) : (
        <button className="mm-trello-col__add" style={{ '--col-color': color }} onClick={() => setAdding(true)}>
          + 추가
        </button>
      )}
    </div>
  )
}

/* 빈 보드 또는 새 그룹 추가용 컬럼 */
function TrelloAddColumn({ color, sub, onAdd }) {
  const [adding, setAdding] = useState(false)
  const [title, setTitle] = useState('')
  const inputRef = useRef(null)

  useEffect(() => { if (adding) inputRef.current?.focus() }, [adding])

  const handleSubmit = async (e) => {
    e.preventDefault()
    if (!title.trim()) return
    try { await onAdd(title.trim(), sub) } catch {}
    setTitle(''); setAdding(false)
  }

  return (
    <div className="mm-trello-col mm-trello-col--empty">
      {adding ? (
        <form className="mm-trello-add-form mm-trello-add-form--top" onSubmit={handleSubmit}>
          <input
            ref={inputRef}
            className="mm-trello-add-input"
            value={title}
            onChange={e => setTitle(e.target.value)}
            placeholder="제목 입력..."
            onKeyDown={e => e.key === 'Escape' && (setTitle(''), setAdding(false))}
          />
          <div className="mm-trello-add-actions">
            <button type="submit" className="mm-trello-add-btn" style={{ background: color }}>추가</button>
            <button type="button" className="mm-trello-cancel-btn" onClick={() => { setTitle(''); setAdding(false) }}>✕</button>
          </div>
        </form>
      ) : (
        <button className="mm-trello-col__add mm-trello-col__add--empty" style={{ '--col-color': color }} onClick={() => setAdding(true)}>
          + 첫 번째 매뉴얼 추가
        </button>
      )}
    </div>
  )
}

/* ── 새 트레일(컬럼) 추가 버튼 ──────────────────────── */
function NewTrailColumn({ color, onAddTrail }) {
  const [open, setOpen] = useState(false)
  const [name, setName] = useState('')
  const inputRef = useRef(null)

  useEffect(() => { if (open) inputRef.current?.focus() }, [open])

  const handleSubmit = async (e) => {
    e.preventDefault()
    if (!name.trim()) return
    try { await onAddTrail(name.trim()) } catch {}
    setName(''); setOpen(false)
  }

  return (
    <div className="mm-trello-new-trail">
      {open ? (
        <form className="mm-trello-add-form mm-trello-add-form--top" onSubmit={handleSubmit}>
          <input
            ref={inputRef}
            className="mm-trello-add-input"
            value={name}
            onChange={e => setName(e.target.value)}
            placeholder="트레일 이름..."
            onKeyDown={e => e.key === 'Escape' && (setName(''), setOpen(false))}
          />
          <div className="mm-trello-add-actions">
            <button type="submit" className="mm-trello-add-btn" style={{ background: color }}>만들기</button>
            <button type="button" className="mm-trello-cancel-btn" onClick={() => { setName(''); setOpen(false) }}>✕</button>
          </div>
        </form>
      ) : (
        <button className="mm-trello-new-trail__btn" style={{ '--col-color': color }} onClick={() => setOpen(true)}>
          + 새 트레일
        </button>
      )}
    </div>
  )
}

function TrelloCard({ manual, color, onClick }) {
  const date = manual.created_at
    ? new Date(manual.created_at).toLocaleDateString('ko-KR', { month: 'short', day: 'numeric' })
    : ''
  return (
    <div className="mm-trello-card" style={{ '--cat-color': color }} onClick={onClick}>
      <div className="mm-trello-card__bar" />
      <div className="mm-trello-card__title">{manual.title}</div>
      {date && <div className="mm-trello-card__date">{date}</div>}
    </div>
  )
}
