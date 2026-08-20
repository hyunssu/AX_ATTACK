import { useEffect, useRef, useState, useCallback } from 'react'
import { fetchManuals, quickCreateManual, listTrails, createTrail, setManualSubCategory, dismissManualAiSuggestion, analyzeManualSections, confirmManualSections } from '../api'
import EditorPanel from '../components/EditorPanel'
import ManualSectionReviewModal from '../components/ManualSectionReviewModal'
import ManualMultiJobProgressModal from '../components/ManualMultiJobProgressModal'
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
      .then(trails => setCustomTrails(Array.isArray(trails) ? trails.filter(t => t && t !== 'null') : []))
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

  const handleAcceptAi = useCallback(async (manual) => {
    await setManualSubCategory(manual.id, manual.ai_suggested_sub)
    refreshManuals()
  }, [refreshManuals])

  const handleRejectAi = useCallback(async (manual) => {
    await dismissManualAiSuggestion(manual.id)
    refreshManuals()
  }, [refreshManuals])

  const handleUploaded = useCallback(() => {
    refreshManuals()
    if (selectedCat) {
      listTrails(selectedCat)
        .then(trails => setCustomTrails(Array.isArray(trails) ? trails : []))
        .catch(() => {})
    }
  }, [refreshManuals, selectedCat])

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
    function onMove(ev) {
      if (!panStart.current) return
      setTransform(t => ({ ...t, x: panStart.current.tx + ev.clientX - panStart.current.mx, y: panStart.current.ty + ev.clientY - panStart.current.my }))
    }
    function onUp() {
      panStart.current = null
      window.removeEventListener('mousemove', onMove)
      window.removeEventListener('mouseup', onUp)
    }
    window.addEventListener('mousemove', onMove)
    window.addEventListener('mouseup', onUp)
  }, [transform])
  const onMouseMove = null
  const onMouseUp = null
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
        <span className="mm-toolbar__title">MANUAL</span>
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
                onAcceptAi={handleAcceptAi}
                onRejectAi={handleRejectAi}
                customTrails={customTrails}
                onUploaded={handleUploaded}
              />
            ) : view === 'card' ? (
              <CardView byCategory={byCategory} onSelect={setSelectedCat} />
            ) : (
              <MapView
                byCategory={byCategory}
                transform={transform}
                stageRef={stageRef}
                onMouseDown={onMouseDown}
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
function MapView({ byCategory, transform, stageRef, onMouseDown, onSelect }) {
  return (
    <div
      className="mm-map-stage"
      ref={stageRef}
      onMouseDown={onMouseDown}
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
function TrelloBoard({ cat, sections, onManualSelect, onAdd, onAddTrail, onAcceptAi, onRejectAi, customTrails, onUploaded }) {
  const [uploadOpen, setUploadOpen] = useState(false)
  const tax = TAXONOMY[cat]

  function handleUploaded() {
    setUploadOpen(false)
    onUploaded()
  }

  return (
    <div className="mm-trello" style={{ '--cat-color': tax.color, '--cat-light': tax.light }}>
      <div className="mm-trello__header">
        <span className="mm-trello__en">{tax.en}</span>
        <span className="mm-trello__ko">{cat}</span>
        <span className="mm-trello__total">{sections.reduce((s, g) => s + g.items.length, 0)}개 매뉴얼</span>
        <button className="mm-trello__upload-btn" onClick={() => setUploadOpen(true)}>
          ↑ 파일 업로드
        </button>
      </div>
      <div className="mm-trello__board">
        {sections.length === 0 ? (
          <TrelloAddColumn color={tax.color} sub={null} onAdd={onAdd} />
        ) : (
          sections.map(({ sub, items }) => (
            <TrelloColumn key={sub} sub={sub} items={items} color={tax.color} onManualSelect={onManualSelect} onAdd={onAdd} onAcceptAi={onAcceptAi} onRejectAi={onRejectAi} />
          ))
        )}
        <NewTrailColumn color={tax.color} onAddTrail={onAddTrail} />
      </div>
      {uploadOpen && (
        <TrelloUploadModal cat={cat} tax={tax} customTrails={customTrails} onClose={() => setUploadOpen(false)} onCreated={handleUploaded} />
      )}
    </div>
  )
}

/* ── 파일 드래그앤드롭 존 ──────────────────────────────── */
function FileDropZone({ file, color, onChange }) {
  const [dragging, setDragging] = useState(false)
  const inputRef = useRef(null)

  function pickFile(f) {
    if (!f || !f.name.match(/\.(pdf|md)$/i)) return
    onChange(f)
  }

  return (
    <div
      className={`mm-drop-zone${dragging ? ' mm-drop-zone--drag' : ''}${file ? ' mm-drop-zone--filled' : ''}`}
      style={{ '--cat-color': color }}
      onDragOver={e => { e.preventDefault(); setDragging(true) }}
      onDragLeave={() => setDragging(false)}
      onDrop={e => { e.preventDefault(); setDragging(false); pickFile(e.dataTransfer.files[0]) }}
      onClick={() => !file && inputRef.current?.click()}
    >
      <input
        ref={inputRef}
        type="file"
        accept="application/pdf,.md,text/markdown"
        style={{ display: 'none' }}
        onChange={e => pickFile(e.target.files[0])}
      />
      {file ? (
        <div className="mm-drop-zone__file">
          <span className="mm-drop-zone__file-icon">📄</span>
          <span className="mm-drop-zone__file-name">{file.name}</span>
          <button className="mm-drop-zone__clear" title="파일 제거"
            onClick={e => { e.stopPropagation(); onChange(null) }}>✕</button>
        </div>
      ) : (
        <>
          <div className="mm-drop-zone__icon">↑</div>
          <div className="mm-drop-zone__main">PDF 또는 Markdown 파일을 드래그하거나</div>
          <button className="mm-drop-zone__pick-btn"
            onClick={e => { e.stopPropagation(); inputRef.current?.click() }}>파일 선택</button>
          <div className="mm-drop-zone__hint">.pdf · .md</div>
        </>
      )}
    </div>
  )
}

/* ── MindMap 전용 파일 업로드 모달 ─────────────────────── */
function TrelloUploadModal({ cat, tax, customTrails, onClose, onCreated }) {
  const [file, setFile] = useState(null)
  const [analyzing, setAnalyzing] = useState(false)
  const [status, setStatus] = useState('')
  const [analysis, setAnalysis] = useState(null)
  const [sections, setSections] = useState([])
  const [reviewing, setReviewing] = useState(false)
  const [confirming, setConfirming] = useState(false)
  const [confirmError, setConfirmError] = useState('')
  const [jobs, setJobs] = useState(null)
  const fileUrlRef = useRef(null)

  useEffect(() => () => { if (fileUrlRef.current) URL.revokeObjectURL(fileUrlRef.current) }, [])

  const predefinedSubs = TAXONOMY[cat]?.subs || []
  const availableSubs = [...predefinedSubs, ...customTrails.filter(t => !predefinedSubs.includes(t))]

  function handleFileChange(newFile) {
    if (fileUrlRef.current) { URL.revokeObjectURL(fileUrlRef.current); fileUrlRef.current = null }
    setFile(newFile)
    setStatus('')
    setAnalysis(null)
    setSections([])
    if (newFile) fileUrlRef.current = URL.createObjectURL(newFile)
  }

  async function handleAnalyze() {
    if (!file) return
    setAnalyzing(true)
    setStatus('')
    try {
      const result = await analyzeManualSections(file, cat, availableSubs)
      setAnalysis(result)
      // Option A: 해당 카테고리 이외 섹션은 기본 제외
      setSections(result.sections.map(s => ({ ...s, include: s.categories.includes(cat) })))
      setReviewing(true)
    } catch (err) {
      setStatus(`오류: ${err.message}`)
    } finally {
      setAnalyzing(false)
    }
  }

  async function handleConfirm() {
    if (!analysis) return
    setConfirming(true)
    setConfirmError('')
    try {
      const result = await confirmManualSections(analysis.source_document_id, sections)
      setReviewing(false)
      setJobs(result.results)
    } catch (err) {
      setConfirmError(`오류: ${err.message}`)
    } finally {
      setConfirming(false)
    }
  }

  function handleDone() {
    setJobs(null)
    onCreated()
  }

  const outsideClick = e => {
    if (e.target === e.currentTarget && !reviewing && !jobs) onClose()
  }

  return (
    <div className="modal-overlay" onClick={outsideClick}>
      <div className="modal-card modal-card--xl mm-upload-modal"
        style={{ '--cat-color': tax.color, '--cat-light': tax.light }}>

        <div className="mm-upload-modal__head">
          <div>
            <div className="mm-upload-modal__cat-en">{tax.en}</div>
            <div className="mm-upload-modal__cat-ko">{cat} — 파일 업로드</div>
          </div>
          <button className="mm-upload-modal__close" onClick={onClose} title="닫기">✕</button>
        </div>

        <p className="mm-upload-modal__desc">
          파일을 분석하면 섹션별로 자동 분류합니다.
          <strong> {cat} 이외</strong> 분류된 섹션은 검토 화면에서 기본적으로 제외됩니다.
        </p>

        <FileDropZone file={file} color={tax.color} onChange={handleFileChange} />

        <div className="mm-upload-modal__actions">
          {file && (
            <button className="btn btn--ghost"
              onClick={() => fileUrlRef.current && window.open(fileUrlRef.current, '_blank')}>
              원문 보기
            </button>
          )}
          <button
            className="mm-upload-modal__analyze-btn"
            style={{ background: tax.color }}
            onClick={handleAnalyze}
            disabled={!file || analyzing}
          >
            {analyzing ? '분석 중…' : '분석하기 →'}
          </button>
        </div>

        {status && <div className="status-text">{status}</div>}

        {reviewing && (
          <ManualSectionReviewModal
            sections={sections}
            onChange={setSections}
            onConfirm={handleConfirm}
            onCancel={() => { setReviewing(false); setConfirmError(''); setAnalysis(null); setSections([]) }}
            confirming={confirming}
            error={confirmError}
            contextCategory={cat}
            availableSubs={availableSubs}
          />
        )}
        {jobs && (
          <ManualMultiJobProgressModal jobs={jobs} onDone={handleDone} onClose={handleDone} />
        )}
      </div>
    </div>
  )
}

function TrelloColumn({ sub, items, color, onManualSelect, onAdd, onAcceptAi, onRejectAi }) {
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
          <TrelloCard key={m.id} manual={m} color={color} onClick={() => onManualSelect(m)} onAcceptAi={onAcceptAi} onRejectAi={onRejectAi} />
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
  const [error, setError] = useState('')
  const inputRef = useRef(null)

  useEffect(() => { if (open) inputRef.current?.focus() }, [open])

  const handleSubmit = async (e) => {
    e.preventDefault()
    if (!name.trim()) return
    setError('')
    try {
      await onAddTrail(name.trim())
      setName(''); setOpen(false)
    } catch (err) {
      setError(err.message || '트레일 생성에 실패했습니다.')
    }
  }

  return (
    <div className="mm-trello-new-trail">
      {open ? (
        <form className="mm-trello-add-form mm-trello-add-form--top" onSubmit={handleSubmit}>
          <input
            ref={inputRef}
            className="mm-trello-add-input"
            value={name}
            onChange={e => { setName(e.target.value); setError('') }}
            placeholder="트레일 이름..."
            onKeyDown={e => e.key === 'Escape' && (setName(''), setError(''), setOpen(false))}
          />
          {error && <div className="mm-trello-add-error">{error}</div>}
          <div className="mm-trello-add-actions">
            <button type="submit" className="mm-trello-add-btn" style={{ background: color }}>만들기</button>
            <button type="button" className="mm-trello-cancel-btn" onClick={() => { setName(''); setError(''); setOpen(false) }}>✕</button>
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

function TrelloCard({ manual, color, onClick, onAcceptAi, onRejectAi }) {
  const date = manual.created_at
    ? new Date(manual.created_at).toLocaleDateString('ko-KR', { month: 'short', day: 'numeric' })
    : ''
  return (
    <div className="mm-trello-card" style={{ '--cat-color': color }} onClick={onClick}>
      <div className="mm-trello-card__bar" />
      <div className="mm-trello-card__title">{manual.title}</div>
      {manual.ai_suggested_sub && (
        <div className="mm-ai-badge" onClick={e => e.stopPropagation()}>
          <span className="mm-ai-badge__label">AI 추천: {manual.ai_suggested_sub}</span>
          <button className="mm-ai-badge__accept" onClick={() => onAcceptAi(manual)} title="수락">✓</button>
          <button className="mm-ai-badge__reject" onClick={() => onRejectAi(manual)} title="거절">✕</button>
        </div>
      )}
      {date && <div className="mm-trello-card__date">{date}</div>}
    </div>
  )
}
